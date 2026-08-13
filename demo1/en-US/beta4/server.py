#!/usr/bin/env python3
"""Atmosphere - Integrated Monitoring: Soil Moisture + Flow + Pump Control"""
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
                # Disable DTR/RTS to avoid triggering Arduino auto-reset on port open/close
                ser.dtr = False
                ser.rts = False
            time.sleep(0.5)
            print(f"✅ Serial connected: {SERIAL_PORT}", flush=True)
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
                    # readline timeout returns empty → reconnect only after 30s idle (reduce reset frequency)
                    if time.time() - last_read > 30:
                        print("⚠️ No data for 30s, force reconnect", flush=True)
                        raise TimeoutError("serial idle timeout")
        except Exception as e:
            print(f"❌ Serial error, reconnect in 5s: {e}", flush=True)
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
        # Consider online if succeeded within last 10s (tolerate flaky peer)
        latest["wind_connected"] = (time.time() - last_ok[0]) < 10
        time.sleep(1)

# ══════════ Alert Model ══════════
# Alert levels: 0 Normal / 1 Level 3 / 2 Level 2 / 3 Level 1 (Level 1 = most severe)
LV_TEXT = ["🟢 Normal", "🟡 Level 3 Alert", "🟠 Level 2 Alert", "🔴 Level 1 Alert"]

# Debris-flow model calibration parameters
Q_MAX = 30.0    # full-channel flow L/min
DQ_MAX = 5.0    # flow rate-of-change cap L/min/s
DS_MAX = 15.0   # soil 10-min change cap %

flow_hist = deque(maxlen=300)   # 5-min flow history (1 point/sec)
soil_hist = deque(maxlen=600)   # 10-min soil history (1 point/sec)
hist_lock = threading.Lock()

# ── Sliding baseline (24h window, 1 point/min, adapts to local climate) ──
BASE_LEN = 1440        # 24h × 60min
BASE_MIN = 120         # require at least 2h of data before enabling baseline
flow_base = deque(maxlen=BASE_LEN)
soil_base = deque(maxlen=BASE_LEN)
spike_base = deque(maxlen=BASE_LEN)   # spike baseline (per-second flow change rate)
base_last = [0.0]      # last baseline sample time

def pct(data, p):
    """Return the p-th percentile (0-100) of sorted data"""
    if not data:
        return None
    s = sorted(data)
    idx = int(len(s) * p / 100.0)
    idx = max(0, min(len(s) - 1, idx))
    return s[idx]

def sliding_norm(v, base):
    """Map current value to 0~1 relative position within local [P10, P95] band; None if insufficient data"""
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
    """Whether flow has risen for 5 consecutive minutes (5×60s windows, ≥4 rising → sustained)"""
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

                # sample into 24h baseline window every minute
                if t - base_last[0] >= 60:
                    base_last[0] = t
                    flow_base.append(flow)
                    soil_base.append(soil)
                    _spk = flow_hist[-1][1] - flow_hist[-2][1] if len(flow_hist) >= 2 else 0.0
                    spike_base.append(max(0.0, _spk))

                # ── debris-flow four-factor normalization (sliding baseline, fallback to absolute) ──
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

                # hazard index D = 0.40S̄ + 0.30Q̄ + 0.20(dQ/dt)̄ + 0.10(ΔS)̄
                D = 0.40 * Sn + 0.30 * Qn + 0.20 * dqn + 0.10 * dsn

                # ── debris-flow leveling (special rules first) ──
                # soil "high moisture": prefer sliding-baseline P90, fallback to absolute 60%
                _sp90 = pct(soil_base, 90)
                soil_high = (soil > _sp90) if _sp90 is not None else (soil >= 60)

                debris_lv = 0
                # gate: if soil unsaturated (<60%), debris flow cannot initiate → safe, skip D grading
                if soil >= 60:
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
                        elif D >= 0.45:   # 0.30→0.45, soil moisture alone (≤0.40) no longer triggers Level 3
                            debris_lv = 1

                # ── flood spike (30% component, approximated by per-second flow change; Manning needs water level TBD) ──
                spike = max(0.0, flow_hist[-1][1] - flow_hist[-2][1]) if len(flow_hist) >= 2 else 0.0
                # spike uses sliding baseline: vs local historical flow-change distribution, >P95 = high risk
                spike_risk = sliding_norm(spike, spike_base)
                if spike_risk is None:
                    spike_risk = min(spike / 2.0, 1.0)  # fallback fixed threshold when baseline insufficient

                final_lv = debris_lv  # flood Manning lacks water level, use debris level for now

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
            print(f"Model error: {e}", flush=True)
        time.sleep(1)

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Atmosphere — Integrated Monitoring</title>
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
/* soil progress bar */
.bar{height:10px;background:#1e3a4a;border-radius:6px;overflow:hidden;margin:14px 0 6px}
.bar .fill{height:100%;background:linear-gradient(90deg,#43a047,#4fc3f7);border-radius:6px;transition:width .4s}
.tag{font-size:.8em;padding:4px 12px;border-radius:14px;display:inline-block}
.tag.wet{background:#1b5e20;color:#81c784}
.tag.dry{background:#5d4037;color:#ffab91}
.tag.disconn{background:#b71c1c;color:#ffcdd2}
/* pump switch */
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
<div class="sub">Soil Moisture · Flow · Pump · Wind Integrated Monitoring</div>

<div class="grid">
  <!-- Soil moisture card -->
  <div class="card">
    <h2>🌱 Soil Moisture</h2>
    <div class="big"><span id="soil">--</span><span class="unit">%</span></div>
    <div class="bar"><div class="fill" id="soilBar" style="width:0%"></div></div>
    <span class="tag disconn" id="soilTag">--</span>
    <div class="row">
      <div class="mini"><div class="lb">Raw AO</div><div class="vl" id="soilRaw">--</div></div>
      <div class="mini"><div class="lb">Digital DO</div><div class="vl" id="soilDO">--</div></div>
    </div>
  </div>

  <!-- Flow card -->
  <div class="card">
    <h2>💧 Flow</h2>
    <div class="big"><span id="flow">0.000</span><span class="unit">L/min</span></div>
    <div class="row">
      <div class="mini"><div class="lb">Pulses/s</div><div class="vl" id="pulses">--</div></div>
      <div class="mini"><div class="lb">Total</div><div class="vl" id="total">--</div></div>
    </div>
  </div>

  <!-- Pump card -->
  <div class="card">
    <h2>🚰 Pump</h2>
    <button class="switch off" id="pumpBtn">💧 Off</button>
    <div class="row" style="margin-top:14px">
      <div class="mini" style="flex:1"><div class="lb">Speed</div><div class="vl" id="speedLbl">0%</div></div>
      <div class="mini" style="flex:1"><div class="lb">Total Power</div><div class="vl" id="powerLbl">0.40 W</div></div>
    </div>
    <input type="range" id="speedSlider" min="0" max="100" value="0"
      style="width:100%;margin-top:12px;accent-color:#2e7d32">
    <div class="time" id="time" style="margin-top:8px">--</div>
  </div>

  <!-- Weather card -->
  <div class="card">
    <h2>🌬️ Weather</h2>
    <div class="big"><span id="wind">--</span><span class="unit">km/h</span></div>
    <span class="tag disconn" id="windTag">--</span>
    <div class="row">
      <div class="mini"><div class="lb">m/s</div><div class="vl" id="windMs">--</div></div>
      <div class="mini"><div class="lb">Updated</div><div class="vl" id="windTime">--</div></div>
    </div>
    <div class="row">
      <div class="mini"><div class="lb">Temp</div><div class="vl" id="tempV">--</div></div>
      <div class="mini"><div class="lb">Humidity</div><div class="vl" id="humV">--</div></div>
    </div>
  </div>

  <!-- Alert card -->
  <div class="card" style="flex-basis:100%;max-width:100%">
    <h2>🚨 Alert</h2>
    <div class="big" id="alertLv" style="font-size:2.4em">--</div>
    <div class="row" style="flex-wrap:wrap;justify-content:center">
      <div class="mini"><div class="lb">Debris D</div><div class="vl" id="debrisD">--</div></div>
      <div class="mini"><div class="lb">Soil S̄</div><div class="vl" id="fSn">--</div></div>
      <div class="mini"><div class="lb">Flow Q̄</div><div class="vl" id="fQn">--</div></div>
      <div class="mini"><div class="lb">Surge dQ̄</div><div class="vl" id="fdQn">--</div></div>
      <div class="mini"><div class="lb">Soil Rise ΔS̄</div><div class="vl" id="fdSn">--</div></div>
      <div class="mini"><div class="lb">Spike Risk</div><div class="vl" id="spikeRisk">--</div></div>
    </div>
  </div>
</div>

<script>
let pumpState = 0;
let pumpSpeedPct = 0;
const PUMP_MAX_WATT = 1.25;   // estimated pump full-load power (5V×250mA), calibrate per nameplate
const BASE_POWER = 0.4;       // fixed system power estimate: Arduino Nano ~0.25W + soil ~0.05W + flow YF-S401 ~0.1W

async function update(){
  try{
    let r=await fetch('/data');
    let d=await r.json();
    // soil moisture
    let soilEl = document.getElementById('soil');
    let tagEl = document.getElementById('soilTag');
    if(!d.soil_connected){
      soilEl.textContent = '--';
      tagEl.textContent = '⚠️ Sensor disconnected';
      tagEl.className = 'tag disconn';
      document.getElementById('soilBar').style.width = '0%';
    } else {
      let p = d.soil_percent;
      soilEl.textContent = p;
      document.getElementById('soilBar').style.width = p + '%';
      if(d.soil_dry){
        tagEl.textContent = '☀️ Dry';
        tagEl.className = 'tag dry';
      } else {
        tagEl.textContent = '💦 Wet';
        tagEl.className = 'tag wet';
      }
    }
    document.getElementById('soilRaw').textContent = d.soil_raw;
    document.getElementById('soilDO').textContent = d.soil_dry ? 'HIGH(dry)' : 'LOW(wet)';
    // flow
    document.getElementById('flow').textContent = d.flow.toFixed(3);
    document.getElementById('pulses').textContent = d.flow_pulses;
    document.getElementById('total').textContent = d.total.toFixed(2) + ' L';
    // pump
    pumpState = d.pump;
    pumpSpeedPct = Math.round((d.speed ?? 0) / 255 * 100);
    renderPump();
    document.getElementById('time').textContent = d.time;
    // weather (wind + temp + humidity)
    let windEl = document.getElementById('wind');
    let windTagEl = document.getElementById('windTag');
    if(d.wind_connected){
      windEl.textContent = d.wind_kmh.toFixed(1);
      windTagEl.textContent = 'Online';
      windTagEl.className = 'tag wet';
      document.getElementById('windMs').textContent = d.wind_ms.toFixed(2) + ' m/s';
      document.getElementById('windTime').textContent = d.wind_time;
      document.getElementById('tempV').textContent = (d.temp ?? 0).toFixed(1) + '℃';
      document.getElementById('humV').textContent = (d.hum ?? 0).toFixed(0) + '%';
    } else {
      windEl.textContent = '--';
      windTagEl.textContent = '⚠️ Offline';
      windTagEl.className = 'tag disconn';
      document.getElementById('windMs').textContent = '--';
      document.getElementById('windTime').textContent = '--';
      document.getElementById('tempV').textContent = '--';
      document.getElementById('humV').textContent = '--';
    }
    // alert
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
  let slider = document.getElementById('speedSlider');
  if(pumpState === 1){
    btn.className = 'switch on';
    btn.textContent = '💧 Pumping';
  } else {
    btn.className = 'switch off';
    btn.textContent = '💧 Off';
  }
  document.getElementById('speedLbl').textContent = pumpSpeedPct + '%';
  document.getElementById('powerLbl').textContent = (BASE_POWER + pumpSpeedPct / 100 * PUMP_MAX_WATT).toFixed(2) + ' W';
  if (document.activeElement !== slider) {
    slider.value = pumpSpeedPct;
  }
}

async function togglePump(){
  let v = pumpState === 1 ? 0 : 255;  // off→0, on→full 255
  try{
    await fetch('/pump?speed=' + v, {method:'POST'});
  }catch(e){}
  // don't set state manually; wait for server's true value (avoid race flicker)
  setTimeout(update, 150);
}

let lastSpeedSend = 0;
document.getElementById('speedSlider').addEventListener('input', function(){
  let v = parseInt(this.value);
  document.getElementById('speedLbl').textContent = v + '%';
  let now = Date.now();
  if (now - lastSpeedSend > 150) {  // 150ms debounce to avoid flooding serial while dragging
    lastSpeedSend = now;
    fetch('/pump?speed=' + Math.round(v * 2.55), {method:'POST'}).catch(()=>{});
  }
});

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
            speed = q.get('speed', [None])[0]
            v = None
            if speed is not None:
                try:
                    v = max(0, min(255, int(speed)))
                except ValueError:
                    v = None
            elif cmd in ('ON', 'OFF'):
                v = 255 if cmd == 'ON' else 0
            if v is not None:
                try:
                    with serial_lock:
                        if ser is not None:
                            ser.write((str(v) + '\n').encode())
                            ser.flush()
                            print(f"📤 Wrote speed {v}", flush=True)
                        else:
                            print("⚠️ ser is None, command not sent", flush=True)
                except Exception as e:
                    print(f"Serial write error: {e}", flush=True)
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
