#!/usr/bin/env python3
"""土壤湿度 Web 监控"""
import json, time, http.server, threading, sys
import serial

SERIAL_PORT = "/dev/cu.usbserial-14120"
WEB_PORT = 8080
latest = {"raw": 0, "percent": -1, "dry": True, "connected": False, "jitter": 0, "time": ""}

def read_serial():
    global latest
    try:
        ser = serial.Serial(SERIAL_PORT, 9600, timeout=1)
        time.sleep(1)
        print(f"✅ 串口已连接: {SERIAL_PORT}")
        while True:
            line = ser.readline().decode(errors='ignore').strip()
            try:
                data = json.loads(line)
                data["time"] = time.strftime("%H:%M:%S")
                latest = data
            except json.JSONDecodeError:
                pass
    except Exception as e:
        print(f"❌ 串口错误: {e}")
        sys.exit(1)

HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Atmosphere — 土壤湿度</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,system-ui,sans-serif;background:#0f1923;color:#e0e0e0;
  min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:20px}
h1{font-size:1.8em;color:#4fc3f7;margin-bottom:5px}
.sub{color:#78909c;margin-bottom:25px;font-size:.9em}
.card{background:#1a2a36;border-radius:16px;padding:30px 40px;max-width:480px;width:100%;text-align:center}
.gauge{position:relative;width:200px;height:200px;margin:0 auto 20px}
.gauge svg{transform:rotate(-90deg)}
.gauge .bg{fill:none;stroke:#1e3a4a;stroke-width:10}
.gauge .fill{fill:none;stroke-width:10;stroke-linecap:round;transition:all .5s ease}
.gauge .val{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);font-size:2.6em;font-weight:700}
.gauge .unit{font-size:.35em;color:#78909c}
.status{font-size:1.1em;padding:6px 18px;border-radius:20px;display:inline-block;margin:10px 0}
.status.wet{background:#1b5e20;color:#81c784}
.status.dry{background:#b71c1c;color:#ef9a9a}
.status.off{background:#37474f;color:#90a4ae}
.row{display:flex;gap:10px;margin-top:15px}
.col{flex:1;background:#1e3a4a;border-radius:10px;padding:12px}
.col .lb{font-size:.7em;color:#78909c}
.col .vl{font-size:1.1em;font-weight:600;margin-top:4px}
.time{color:#546e7a;font-size:.75em;margin-top:15px}
.warn{background:#3e2723;color:#ffab91;padding:8px 15px;border-radius:8px;display:inline-block;margin:10px 0;font-size:.9em}
</style>
</head>
<body>
<h1>🌱 Atmosphere</h1>
<div class="sub">土壤湿度实时监测</div>
<div class="card" id="card">
  <div class="gauge">
    <svg width="200" height="200" viewBox="0 0 200 200">
      <circle class="bg" cx="100" cy="100" r="85"/>
      <circle class="fill" id="arc" cx="100" cy="100" r="85"
        stroke-dasharray="534" stroke-dashoffset="534"/>
    </svg>
    <div class="val"><span id="percent">--</span><span class="unit">%</span></div>
  </div>
  <div id="warnBox"></div>
  <div class="status off" id="status">等待数据...</div>
  <div class="row">
    <div class="col"><div class="lb">📊 原始值</div><div class="vl" id="raw">--</div></div>
    <div class="col"><div class="lb">⚡ 数字输出</div><div class="vl" id="do">--</div></div>
    <div class="col"><div class="lb">📶 抖动</div><div class="vl" id="jitter">--</div></div>
  </div>
  <div class="time" id="time">--</div>
</div>

<script>
const ARC = 534;
const arc = document.getElementById('arc');
function getColor(p){
  if(p<20) return '#ff7043';
  if(p<40) return '#ffa726';
  if(p<60) return '#66bb6a';
  if(p<80) return '#29b6f6';
  return '#42a5f5';
}
async function update(){
  try{
    let r=await fetch('/data');
    let d=await r.json();
    let con = d.connected;
    document.getElementById('raw').textContent = d.raw;
    document.getElementById('do').textContent = d.dry?'🔴 高(干)':'🟢 低(湿)';
    document.getElementById('jitter').textContent = d.jitter;
    document.getElementById('time').textContent = d.time;

    let warnBox = document.getElementById('warnBox');
    let statusEl = document.getElementById('status');
    let percentEl = document.getElementById('percent');

    if(!con){
      warnBox.innerHTML = '<div class="warn">⚠️ 传感器未连接或已脱落</div>';
      statusEl.textContent = '未连接';
      statusEl.className = 'status off';
      percentEl.textContent = '--';
      arc.setAttribute('stroke-dashoffset', ARC);
      arc.setAttribute('stroke', '#37474f');
    } else {
      warnBox.innerHTML = '';
      percentEl.textContent = d.percent;
      let offset = ARC - (d.percent/100)*ARC;
      arc.setAttribute('stroke-dashoffset', offset);
      arc.setAttribute('stroke', getColor(d.percent));
      statusEl.textContent = d.dry?'干燥':'潮湿';
      statusEl.className = 'status '+(d.dry?'dry':'wet');
    }
  }catch(e){}
}
setInterval(update, 500);
update();
</script>
</body>
</html>"""

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/data':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(latest).encode())
        elif self.path in ('/', '/index.html'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML.encode())
        else:
            super().do_GET()

if __name__ == '__main__':
    t = threading.Thread(target=read_serial, daemon=True)
    t.start()
    print(f"🌐 http://localhost:{WEB_PORT}")
    http.server.HTTPServer(('', WEB_PORT), Handler).serve_forever()
