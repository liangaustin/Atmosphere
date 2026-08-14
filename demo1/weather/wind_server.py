#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
风速数据发送服务（跑在风速传感器那台电脑上）
读 Arduino UNO 串口的风速，通过 HTTP 开放给局域网内其他电脑。

用法：
1. 装 pyserial:  pip3 install pyserial
2. 把 SERIAL_PORT 改成你的实际串口号
3. 运行:  python3 wind_server.py
4. 验证:  浏览器打开 http://localhost:8001/wind 应看到 {"wind_ms": .., "wind_kmh": ..}
"""
import serial, time, json, re, threading, http.server

# ===== 改成你的串口号 =====
# Windows: "COM3" 之类（设备管理器 → 端口 里看）
# macOS:   "/dev/cu.usbserial-xxxx"（用 ls /dev/cu.usbserial-* 查看）
SERIAL_PORT = "COM3"
WEB_PORT = 8001

latest = {"wind_ms": 0.0, "wind_kmh": 0.0, "time": ""}

def read_serial():
    global latest
    while True:
        try:
            ser = serial.Serial(SERIAL_PORT, 9600, timeout=1)
            time.sleep(1)
            print("串口已连接:", SERIAL_PORT)
            while True:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                # 解析 "风速=60.0 km/h (16.7 m/s)" 里的两个数字
                m = re.search(r'([\d.]+)\s*km/h\s*\(([\d.]+)\s*m/s\)', line)
                if m:
                    latest["wind_kmh"] = float(m.group(1))
                    latest["wind_ms"] = float(m.group(2))
                    latest["time"] = time.strftime("%H:%M:%S")
        except Exception as e:
            print("串口错误，5秒后重连:", e)
            time.sleep(5)

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass
    def do_GET(self):
        if self.path == '/wind':
            body = json.dumps(latest).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == '__main__':
    threading.Thread(target=read_serial, daemon=True).start()
    print("风速服务已启动: http://localhost:%d/wind" % WEB_PORT)
    http.server.HTTPServer(('0.0.0.0', WEB_PORT), Handler).serve_forever()
