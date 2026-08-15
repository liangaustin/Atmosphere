#!/usr/bin/env python3
"""Atmosphere - 综合监控：土壤湿度 + 流速 + 水泵控制"""
import json, time, http.server, threading, sys
import urllib.request
from collections import deque
import serial

SERIAL_PORT = "/dev/cu.usbserial-14120"
WIND_URL = "http://192.168.1.200:8001/wind"
WEB_PORT = 8080
latest = {
    "pump": 0, "soil_raw": 0, "soil_percent": -1, "soil_dry": False,
    "soil_connected": True, "flow_pulses": 0, "flow": 0.0, "total": 0.0,
    "wind_ms": 0.0, "wind_kmh": 0.0, "wind_time": "", "wind_connected": False,
    "temp": 0.0, "hum": 0.0,
    "time": ""
}

ser = None
serial_lock = threading.Lock()

def read_serial():
    global latest, ser
    while True:
        try:
            with serial_lock:
                ser = serial.Serial(SERIAL_PORT, 9600, timeout=0.5)
                # 禁用 DTR/RTS，避免串口开关时触发 Arduino 自动复位
                ser.dtr = False
                ser.rts = False
            time.sleep(0.5)
            print(f"✅ 串口已连接: {SERIAL_PORT}", flush=True)
            last_read = time.time()
            while True:
                with serial_lock:
                    if ser is None:
                        raise TimeoutError("serial closed")
                    line = ser.readline()
                if line:
                    try:
                        data = json.loads(line.decode(errors='ignore').strip())
                        data["time"] = time.strftime("%H:%M:%S")
                        latest.update(data)
                        last_read = time.time()
                    except json.JSONDecodeError:
                        pass
                else:
                    # readline 超时返回空 → 累计 30 秒无数据才重连（减少复位频率）
                    if time.time() - last_read > 30:
                        print("⚠️ 30秒无数据，强制重连串口", flush=True)
                        raise TimeoutError("serial idle timeout")
        except Exception as e:
            print(f"❌ 串口错误，5秒后重连: {e}", flush=True)
            try:
                with serial_lock:
                    if ser:
                        ser.close()
            except Exception:
                pass
            ser = None
            time.sleep(5)

def fetch_wind():
    global latest
    last_ok = [0.0]
    while True:
        try:
            req = urllib.request.Request(WIND_URL, headers={'User-Agent': 'curl/7.64'})
            with urllib.request.urlopen(req, timeout=5) as r:
                d = json.loads(r.read().decode())
                latest["wind_ms"] = d.get("wind_ms", 0.0)
                latest["wind_kmh"] = d.get("wind_kmh", 0.0)
                latest["wind_time"] = d.get("time", "")
                latest["temp"] = d.get("temp", 0.0)
                latest["hum"] = d.get("hum", 0.0)
                last_ok[0] = time.time()
        except Exception:
            pass
        # 10 秒内有成功就算在线（容错对方时通时断）
        latest["wind_connected"] = (time.time() - last_ok[0]) < 10
        time.sleep(1)

# ══════════ 预警模型 ══════════
# 预警档位：0 正常 / 1 三级预警 / 2 二级预警 / 3 一级预警（一级最严重）
LV_TEXT = ["🟢 正常", "🟡 三级预警", "🟠 二级预警", "🔴 一级预警"]

# 泥石流模型标定参数
Q_MAX = 30.0    # 满槽流量 L/min
DQ_MAX = 5.0    # 流量变化率上限 L/min/s
DS_MAX = 15.0   # 土壤10分钟变化上限 %

flow_hist = deque(maxlen=300)   # 5分钟流量历史（每秒一点）
soil_hist = deque(maxlen=600)   # 10分钟湿度历史（每秒一点）
hist_lock = threading.Lock()

# ── 滑动基准（24小时窗口，每分钟一点，自适应地区气候）──
BASE_LEN = 1440        # 24h × 60min
BASE_MIN = 120         # 至少 2 小时数据才启用滑动基准
flow_base = deque(maxlen=BASE_LEN)
soil_base = deque(maxlen=BASE_LEN)
base_last = [0.0]      # 上次基准采样时间

def pct(data, p):
    """排序后取第 p 百分位（0-100）"""
    if not data:
        return None
    s = sorted(data)
    idx = int(len(s) * p / 100.0)
    idx = max(0, min(len(s) - 1, idx))
    return s[idx]

def sliding_norm(v, base):
    """把当前值映射到该地 [P10, P95] 区间的 0~1 相对偏离；数据不足返回 None"""
    if len(base) < BASE_MIN:
        return None
    p10 = pct(base, 10)
    p95 = pct(base, 95)
    if p95 - p10 < 1e-6:
        return None
    return max(0.0, min(1.0, (v - p10) / (p95 - p10)))

model = {
    "debris_D": 0.0, "debris_lv": 0, "debris_lv_text": LV_TEXT[0],
    "Sn": 0.0, "Qn": 0.0, "dQn": 0.0, "dSn": 0.0,
    "spike": 0.0, "spike_risk": 0.0,
    "final_lv": 0, "final_lv_text": LV_TEXT[0],
}

def rising_5min():
    """流量是否连续5分钟上升（5段60秒窗口，≥4段上升判定为持续上涨）"""
    if len(flow_hist) < 300:
        return False
    seg = []
    for i in range(5):
        vals = [flow_hist[j][1] for j in range(-300 + i * 60, -240 + i * 60)]
        seg.append(sum(vals) / 60.0)
    up = sum(1 for i in range(4) if seg[i + 1] > seg[i])
    return up >= 4

def model_loop():
    global model
    while True:
        try:
            with hist_lock:
                t = time.time()
                flow = latest.get("flow", 0.0)
                soil = latest.get("soil_percent", -1)
                if soil < 0:
                    soil = 0
                flow_hist.append((t, flow))
                soil_hist.append((t, soil))

                # 每分钟采样到 24h 滑动基准窗口
                if t - base_last[0] >= 60:
                    base_last[0] = t
                    flow_base.append(flow)
                    soil_base.append(soil)

                # ── 泥石流四因子归一化（滑动基准自适应，数据不足回退绝对值）──
                Sn = sliding_norm(soil, soil_base)
                if Sn is None:
                    Sn = soil / 100.0
                Qn = sliding_norm(flow, flow_base)
                if Qn is None:
                    Qn = min(flow / Q_MAX, 1.0)
                dq = (flow_hist[-1][1] - flow_hist[-60][1]) / 60.0 if len(flow_hist) >= 60 else 0.0
                dqn = min(abs(dq) / DQ_MAX, 1.0)
                ds = 0.0
                if len(soil_hist) >= 600:
                    ds = soil_hist[-1][1] - soil_hist[-600][1]
                    if ds < 0:
                        ds = 0
                dsn = min(ds / DS_MAX, 1.0)

                # 综合危险指数 D = 0.40S̄ + 0.30Q̄ + 0.20(dQ/dt)̄ + 0.10(ΔS)̄
                D = 0.40 * Sn + 0.30 * Qn + 0.20 * dqn + 0.10 * dsn

                # ── 泥石流分级（特殊规则优先）──
                # 土壤"高湿"判定：优先滑动基准 P90，数据不足回退绝对 60%
                _sp90 = pct(soil_base, 90)
                soil_high = (soil > _sp90) if _sp90 is not None else (soil >= 60)

                debris_lv = 0
                if soil_high and dq > 0 and rising_5min():
                    debris_lv = 3
                elif soil_high and Qn >= 0.70:
                    debris_lv = 2
                if ds >= 20 and debris_lv < 1:
                    debris_lv = 1
                if debris_lv == 0:
                    if D >= 0.75:
                        debris_lv = 3
                    elif D >= 0.55:
                        debris_lv = 2
                    elif D >= 0.30:   # 原始三级阈值（v2 起改为 0.45）
                        debris_lv = 1

                # ── 山洪尖峰（30%分量，用流量秒级变化率近似；曼宁需水位暂缺）──
                spike = max(0.0, flow_hist[-1][1] - flow_hist[-2][1]) if len(flow_hist) >= 2 else 0.0
                spike_risk = min(spike / 2.0, 1.0)  # 2.0 L/min/s 拉满（待标定）

                final_lv = debris_lv  # 山洪曼宁缺水位，暂取泥石流等级

                model.update({
                    "debris_D": round(D, 3), "debris_lv": debris_lv,
                    "debris_lv_text": LV_TEXT[debris_lv],
                    "Sn": round(Sn, 3), "Qn": round(Qn, 3),
                    "dQn": round(dqn, 3), "dSn": round(dsn, 3),
                    "spike": round(spike, 3), "spike_risk": round(spike_risk, 3),
                    "final_lv": final_lv, "final_lv_text": LV_TEXT[final_lv],
                    "baseline_ready": len(soil_base) >= BASE_MIN,
                    "soil_p90": round(_sp90, 1) if _sp90 is not None else -1,
                })
        except Exception as e:
            print(f"模型计算错误: {e}", flush=True)
        time.sleep(1)

HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Atmosphere — 综合监控</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,system-ui,sans-serif;background:#0b1218;color:#e0e0e0;
  min-height:100vh;padding:24px;display:flex;flex-direction:column;align-items:center}
h1{font-size:1.6em;color:#4fc3f7;margin-bottom:4px}
.sub{color:#78909c;margin-bottom:24px;font-size:.85em}
.grid{display:flex;gap:16px;flex-wrap:wrap;justify-content:center;max-width:900px}
.card{background:#1a2a36;border-radius:18px;padding:24px 26px;flex:1;min-width:260px;max-width:320px;text-align:center}
.card h2{font-size:1em;color:#90a4ae;font-weight:600;margin-bottom:14px;letter-spacing:.5px}
.big{font-size:2.8em;font-weight:800;line-height:1;margin:6px 0}
.unit{font-size:.4em;color:#78909c;font-weight:400}
/* 湿度进度条 */
.bar{height:10px;background:#1e3a4a;border-radius:6px;overflow:hidden;margin:14px 0 6px}
.bar .fill{height:100%;background:linear-gradient(90deg,#43a047,#4fc3f7);border-radius:6px;transition:width .4s}
.tag{font-size:.8em;padding:4px 12px;border-radius:14px;display:inline-block}
.tag.wet{background:#1b5e20;color:#81c784}
.tag.dry{background:#5d4037;color:#ffab91}
.tag.disconn{background:#b71c1c;color:#ffcdd2}
/* 水泵开关 */
.switch{width:110px;height:110px;border-radius:50%;border:none;font-size:1.05em;font-weight:700;
  cursor:pointer;margin:10px auto 6px;display:block;transition:all .2s;color:#fff}
.switch.off{background:#455a64;box-shadow:0 4px 12px rgba(0,0,0,.4)}
.switch.on{background:#2e7d32;box-shadow:0 4px 20px rgba(46,125,50,.6)}
.switch:active{transform:scale(.94)}
.row{display:flex;gap:10px;margin-top:14px}
.mini{flex:1;background:#1e3a4a;border-radius:10px;padding:10px}
.mini .lb{font-size:.68em;color:#78909c}
.mini .vl{font-size:1.15em;font-weight:600;margin-top:4px}
.time{color:#546e7a;font-size:.75em;margin-top:20px}
</style>
</head>
<body>
<h1>🌊 Atmosphere</h1>
<div class="sub">土壤湿度 · 流速 · 水泵 · 风速 综合监控</div>

<div class="grid">
  <!-- 土壤湿度卡片 -->
  <div class="card">
    <h2>🌱 土壤湿度</h2>
    <div class="big"><span id="soil">--</span><span class="unit">%</span></div>
    <div class="bar"><div class="fill" id="soilBar" style="width:0%"></div></div>
    <span class="tag disconn" id="soilTag">--</span>
    <div class="row">
      <div class="mini"><div class="lb">原始值 A0</div><div class="vl" id="soilRaw">--</div></div>
      <div class="mini"><div class="lb">数字 DO</div><div class="vl" id="soilDO">--</div></div>
    </div>
  </div>

  <!-- 流速卡片 -->
  <div class="card">
    <h2>💧 流速</h2>
    <div class="big"><span id="flow">0.000</span><span class="unit">L/min</span></div>
    <div class="row">
      <div class="mini"><div class="lb">脉冲/秒</div><div class="vl" id="pulses">--</div></div>
      <div class="mini"><div class="lb">累计流量</div><div class="vl" id="total">--</div></div>
    </div>
  </div>

  <!-- 水泵卡片 -->
  <div class="card">
    <h2>🚰 水泵</h2>
    <button class="switch off" id="pumpBtn">💧 关</button>
    <div class="time" id="time" style="margin-top:14px">--</div>
  </div>

  <!-- 气象卡片 -->
  <div class="card">
    <h2>🌬️ 气象</h2>
    <div class="big"><span id="wind">--</span><span class="unit">km/h</span></div>
    <span class="tag disconn" id="windTag">--</span>
    <div class="row">
      <div class="mini"><div class="lb">米/秒</div><div class="vl" id="windMs">--</div></div>
      <div class="mini"><div class="lb">更新时间</div><div class="vl" id="windTime">--</div></div>
    </div>
    <div class="row">
      <div class="mini"><div class="lb">温度</div><div class="vl" id="tempV">--</div></div>
      <div class="mini"><div class="lb">湿度</div><div class="vl" id="humV">--</div></div>
    </div>
  </div>

  <!-- 预警卡片 -->
  <div class="card" style="flex-basis:100%;max-width:100%">
    <h2>🚨 综合预警</h2>
    <div class="big" id="alertLv" style="font-size:2.4em">--</div>
    <div class="row" style="flex-wrap:wrap;justify-content:center">
      <div class="mini"><div class="lb">泥石流 D</div><div class="vl" id="debrisD">--</div></div>
      <div class="mini"><div class="lb">土湿 S̄</div><div class="vl" id="fSn">--</div></div>
      <div class="mini"><div class="lb">流量 Q̄</div><div class="vl" id="fQn">--</div></div>
      <div class="mini"><div class="lb">突变 dQ̄</div><div class="vl" id="fdQn">--</div></div>
      <div class="mini"><div class="lb">土湿涨 ΔS̄</div><div class="vl" id="fdSn">--</div></div>
      <div class="mini"><div class="lb">尖峰风险</div><div class="vl" id="spikeRisk">--</div></div>
    </div>
  </div>
</div>

<script>
let pumpState = 0;

async function update(){
  try{
    let r=await fetch('/data');
    let d=await r.json();
    // 土壤湿度
    let soilEl = document.getElementById('soil');
    let tagEl = document.getElementById('soilTag');
    if(!d.soil_connected){
      soilEl.textContent = '--';
      tagEl.textContent = '⚠️ 传感器断线';
      tagEl.className = 'tag disconn';
      document.getElementById('soilBar').style.width = '0%';
    } else {
      let p = d.soil_percent;
      soilEl.textContent = p;
      document.getElementById('soilBar').style.width = p + '%';
      if(d.soil_dry){
        tagEl.textContent = '☀️ 偏干';
        tagEl.className = 'tag dry';
      } else {
        tagEl.textContent = '💦 湿润';
        tagEl.className = 'tag wet';
      }
    }
    document.getElementById('soilRaw').textContent = d.soil_raw;
    document.getElementById('soilDO').textContent = d.soil_dry ? 'HIGH(干)' : 'LOW(湿)';
    // 流速
    document.getElementById('flow').textContent = d.flow.toFixed(3);
    document.getElementById('pulses').textContent = d.flow_pulses;
    document.getElementById('total').textContent = d.total.toFixed(2) + ' L';
    // 水泵
    pumpState = d.pump;
    renderPump();
    document.getElementById('time').textContent = d.time;
    // 气象（风速+温湿度）
    let windEl = document.getElementById('wind');
    let windTagEl = document.getElementById('windTag');
    if(d.wind_connected){
      windEl.textContent = d.wind_kmh.toFixed(1);
      windTagEl.textContent = '在线';
      windTagEl.className = 'tag wet';
      document.getElementById('windMs').textContent = d.wind_ms.toFixed(2) + ' m/s';
      document.getElementById('windTime').textContent = d.wind_time;
      document.getElementById('tempV').textContent = (d.temp ?? 0).toFixed(1) + '℃';
      document.getElementById('humV').textContent = (d.hum ?? 0).toFixed(0) + '%';
    } else {
      windEl.textContent = '--';
      windTagEl.textContent = '⚠️ 离线';
      windTagEl.className = 'tag disconn';
      document.getElementById('windMs').textContent = '--';
      document.getElementById('windTime').textContent = '--';
      document.getElementById('tempV').textContent = '--';
      document.getElementById('humV').textContent = '--';
    }
    // 预警
    const lvColors = ['#43a047', '#fdd835', '#fb8c00', '#e53935'];
    let alertEl = document.getElementById('alertLv');
    alertEl.textContent = d.final_lv_text || '--';
    alertEl.style.color = lvColors[d.final_lv] || '#e0e0e0';
    document.getElementById('debrisD').textContent = (d.debris_D ?? 0).toFixed(3);
    document.getElementById('fSn').textContent = (d.Sn ?? 0).toFixed(2);
    document.getElementById('fQn').textContent = (d.Qn ?? 0).toFixed(2);
    document.getElementById('fdQn').textContent = (d.dQn ?? 0).toFixed(2);
    document.getElementById('fdSn').textContent = (d.dSn ?? 0).toFixed(2);
    document.getElementById('spikeRisk').textContent = (((d.spike_risk ?? 0) * 100).toFixed(0)) + '%';
  }catch(e){}
}

function renderPump(){
  let btn = document.getElementById('pumpBtn');
  if(pumpState === 1){
    btn.className = 'switch on';
    btn.textContent = '💧 抽水中';
  } else {
    btn.className = 'switch off';
    btn.textContent = '💧 关';
  }
}

async function togglePump(){
  let v = pumpState === 1 ? '0' : '1';  // 单字节命令
  try{
    await fetch('/pump?cmd=' + v, {method:'POST'});
  }catch(e){}
  // 不手动改状态，等服务器返回真实值（避免竞态回跳）
  setTimeout(update, 150);
}

document.getElementById('pumpBtn').addEventListener('click', togglePump);
setInterval(update, 500);
update();
</script>
</body>
</html>"""

class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path == '/data':
            payload = dict(latest)
            payload.update(model)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())
        elif self.path in ('/', '/index.html'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML.encode())
        else:
            super().do_GET()

    def do_POST(self):
        if self.path.startswith('/pump'):
            import urllib.parse as up
            q = up.parse_qs(up.urlparse(self.path).query)
            cmd = q.get('cmd', [''])[0]
            if cmd in ('1', '0'):
                try:
                    with serial_lock:
                        if ser is not None:
                            ser.write(cmd.encode())
                            ser.flush()
                            print(f"📤 已写命令 {cmd}", flush=True)
                        else:
                            print("⚠️ ser 为 None，命令未发送", flush=True)
                except Exception as e:
                    print(f"写串口错误: {e}", flush=True)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == '__main__':
    threading.Thread(target=read_serial, daemon=True).start()
    threading.Thread(target=fetch_wind, daemon=True).start()
    threading.Thread(target=model_loop, daemon=True).start()
    print(f"🌐 http://localhost:{WEB_PORT}")
    http.server.ThreadingHTTPServer(('', WEB_PORT), Handler).serve_forever()
