#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 风速数据 HTTP 接口服务（供其他电脑的综合监控调用）
# 读取 Arduino UNO 串口(9600) → 解析风速 → HTTP 服务 8001 → GET /wind 返回 JSON
# 兼容两种串口输出格式：
#   1) 01_WindSensor 文本格式: ADC=xxx 电压=x.xxV 风速=x.x km/h (x.x m/s)
#   2) 02_WindTempHumidity CSV 格式: 电压,风速,温度,湿度  (0.20,19.5,40.1,33.0)
# 串口断线自动重连（5 秒重试）
import serial, time, json, re, math, threading, http.server

SERIAL_PORT = "COM3"   # Arduino 串口号（设备管理器里查看，改这里）
WEB_PORT = 8001        # HTTP 端口

latest = {"wind_ms": 0.0, "wind_kmh": 0.0, "time": "", "temp": None, "hum": None}

def num(x):
    """安全转 float：NaN/空值 → None"""
    try:
        v = float(x)
        return None if math.isnan(v) else v
    except (ValueError, TypeError):
        return None

def parse_line(line):
    # 格式1：文本格式 风速=x.x km/h (x.x m/s)
    m = re.search(r'([\d.]+)\s*km/h\s*\(([\d.]+)\s*m/s\)', line)
    if m:
        return float(m.group(1)), float(m.group(2)), None, None
    # 格式2：CSV 格式 电压,风速,温度,湿度
    parts = line.split(',')
    if len(parts) >= 2:
        try:
            kmh = float(parts[1])
            temp = num(parts[2]) if len(parts) >= 3 else None
            hum = num(parts[3]) if len(parts) >= 4 else None
            return kmh, kmh / 3.6, temp, hum
        except ValueError:
            pass
    return None

def read_serial():
    global latest
    while True:
        try:
            ser = serial.Serial(SERIAL_PORT, 9600, timeout=1)
            time.sleep(1)
            print("serial connected:", SERIAL_PORT, flush=True)
            while True:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                r = parse_line(line)
                if r:
                    latest["wind_kmh"] = r[0]
                    latest["wind_ms"] = r[1]
                    latest["temp"] = r[2]
                    latest["hum"] = r[3]
                    latest["time"] = time.strftime("%H:%M:%S")
        except Exception as e:
            print("serial error, retry in 5s:", e, flush=True)
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
    print("wind server up: http://localhost:%d/wind" % WEB_PORT, flush=True)
    http.server.ThreadingHTTPServer(('0.0.0.0', WEB_PORT), Handler).serve_forever()
