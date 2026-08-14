# 风速 + 温湿度模块（王立辉负责）

野外溪流/漂流点山洪智能监测预警系统 —— 风速 + 温湿度监测单元。

## 模块组成

| 文件 | 说明 |
| ---- | ---- |
| `01_WindSensor.ino` | 风速传感器基础版：三杯式风速计 → 风速 km/h / m/s，超 10 km/h 板载 LED 报警 |
| `wind_server.py` | 基础版配套转发服务：读串口 → HTTP :8001/wind 返回 JSON |
| `风速+温湿度/` | 完整版：风速 + DHT11 温湿度 + 网页仪表盘 + 智能预警 |

## 硬件接线

- 风速传感器：红线 → A0，黑线 → GND（三杯式风速计，0~5V 模拟输出）
- DHT11：v → 5V，s → D4，g → GND
- 报警 LED：板载 D13

## 运行方式

```bash
# 1. 烧录 Arduino（完整版）
#    Arduino IDE 打开 风速+温湿度/02_WindTempHumidity.ino，选 Arduino UNO + 对应端口
#    波特率 9600，串口输出 CSV：电压,风速,温度,湿度

# 2. 启动转发服务（8001 端口，供局域网其他电脑调用）
cd 风速+温湿度/server
python3 wind_server.py        # 改 SERIAL_PORT 为实际串口号

# 3. 启动网页仪表盘（3000 端口）
npm install                   # 首次运行装依赖
node server.js
# 浏览器打开 http://localhost:3000
```

Windows 下可双击 `风速+温湿度/server/启动仪表盘.bat` 一键启动（自动先起 8001 转发，再起仪表盘）。

## 架构

```
Arduino UNO（串口 9600，CSV 输出）
   │
   ▼
wind_server.py ── 独占串口，解析数据，缓存最新值
   │              HTTP :8001/wind → {"wind_kmh","wind_ms","temp","hum","time"}
   ▼
server.js ── 每 1 秒轮询 8001，加分预警引擎 + SSE 推送
   │
   ▼
浏览器 http://localhost:3000（仪表盘：风速曲线 / 温湿度 / 阵风 / 30 分钟基准线 / 分级预警）
```

## 与综合监控联动

本模块的 `http://<风速电脑IP>:8001/wind` JSON 接口被综合监控网页（土壤湿度 + 流速 + 水泵）调用，显示风速、温度、湿度；10 秒无响应自动判为离线。

## 备注

- `wind_server.py`（模块根目录）为基础版配套服务，只解析 `01_WindSensor.ino` 的文本格式；`风速+温湿度/server/wind_server.py` 为完整版，同时兼容文本格式和 CSV 格式
- 接线图见 `风速+温湿度/图片1~3.jpg`
