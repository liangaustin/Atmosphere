# Hardware 代码目录

## soil-monitor — 土壤湿度传感器

- `SoilMonitor.ino` — Arduino Nano 程序（AO→A0, DO→D2, VCC→5V, GND→GND）
  - 输出 JSON：raw / percent / dry / jitter / connected
  - 带断线检测（抖动 >200 或 raw >1010 判为脱落）
  - 500ms 采样间隔
- `server.py` — Web 实时监控（端口 8080，环形仪表盘）
- `log_humidity.py` — 串口数据日志记录

## blink-alternate — 板载 LED 测试

- `BlinkAlternate.ino` — 快闪 3 下 + 慢闪 3 下，验证烧录环境
