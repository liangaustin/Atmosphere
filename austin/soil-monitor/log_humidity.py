#!/usr/bin/env python3
"""记录土壤湿度到 CSV"""
import serial, time, sys, os

PORT = sys.argv[1] if len(sys.argv) > 1 else "/dev/cu.usbserial-14110"
OUT = os.path.expanduser("~/Desktop/soil_log.csv")

print(f"📝 开始记录到: {OUT}")
print(f"⏱  时间戳                      |  原始值 |  湿度% | 抖动 | 状态")
print("-" * 70)

with open(OUT, "w") as f:
    f.write("timestamp,raw,percent,jitter,dry,connected\n")

ser = serial.Serial(PORT, 9600, timeout=1)
time.sleep(1)

start = time.time()
count = 0
try:
    while True:
        line = ser.readline().decode(errors='ignore').strip()
        if not line: continue
        try:
            import json
            d = json.loads(line)
        except:
            continue

        elapsed = time.time() - start
        ts = time.strftime("%H:%M:%S")
        t = f"{int(elapsed//60)}:{int(elapsed%60):02d}"
        status = "⚠️脱落" if not d["connected"] else ("干燥" if d["dry"] else "潮湿")

        print(f"  [{ts}] (+{t:>5s}) | {d['raw']:5d} | {d['percent']:5d}% | {d['jitter']:4d} | {status}")

        with open(OUT, "a") as f:
            f.write(f"{ts},{d['raw']},{d['percent']},{d['jitter']},{d['dry']},{d['connected']}\n")

        count += 1
except KeyboardInterrupt:
    print(f"\n✅ 已记录 {count} 条，保存到 {OUT}")
    ser.close()
