# Atmosphere — 山洪 + 泥石流智能监测预警系统
# Atmosphere — Flash Flood & Debris Flow Monitoring & Early Warning

> **Demo 1** · 野外溪流 / 漂流点山洪与泥石流智能监测预警
> **Demo 1** · Smart flash-flood & debris-flow early warning for outdoor streams / drifting sites

---

## 📖 项目简介 / Overview

**中文**：Atmosphere 面向野外溪流、漂流点等场景，实时采集土壤湿度、水流流速、风速三类环境数据，通过网页实时监控，并用数学模型（泥石流危险指数 + 山洪流量近似/尖峰检测）输出分级预警，辅助判断山洪、泥石流风险。Demo 1 已打通「采集 → 控制 → 监控 → 预警」全链路。

**English**: Atmosphere monitors soil moisture, water flow, and wind speed in real time at outdoor streams and drifting sites. It provides a live web dashboard and outputs graded early warnings via mathematical models (debris-flow danger index + flash-flood flow approximation / spike detection) to help assess flash-flood and debris-flow risk. Demo 1 completes the full "sense → control → monitor → warn" pipeline.

---

## ✨ 功能特性 / Features

| 功能 / Feature | 说明 / Description |
| --- | --- |
| 🌱 土壤湿度 / Soil moisture | AO 模拟量 + DO 数字断线检测，百分比显示 |
| 💧 流速 / Flow | YF-S401 霍尔传感器，实时流速（L/min）+ 累计流量 |
| 🌬️ 风速 / Wind | 三杯式风速传感器（另一台电脑采集，HTTP 转发集成） |
| 🚰 水泵控制 / Pump control | 网页滑块 PWM 调速（0~100%）+ 软启动 + 整机功率显示，控制 D9 |
| 🌐 Web 监控 / Web dashboard | 端口 8080，实时数据 + 气象 + 预警卡片 |
| 🧠 预警模型 / Warning model | 泥石流危险指数 + 山洪尖峰 + 滑动基准 + 分级档位 |

---

## 🔌 硬件连接 / Hardware Wiring

**主控 / Controller**：Arduino Nano（ATmega328P，新 Bootloader）

| 设备 / Device | 接线 / Wiring |
| --- | --- |
| 土壤湿度传感器 / Soil moisture sensor | AO→A2，DO→D2，VCC→5V，GND→GND |
| 流速传感器 YF-S401 / Flow sensor | 红 Red→5V，黄 Yellow→D8（信号 signal），黑 Black→GND |
| 水泵 / Pump | D9（**PWM 调速 / PWM speed control**，占空比越大越快，软启动） |
| 风速传感器 / Wind sensor | 另一台电脑 Arduino UNO A0（0~5V 三杯式），HTTP 转发 |

> ⚠️ 流速传感器 YF-S401 最小启动流量 0.3 L/min，低于此值转子不转；流量换算系数 **3433.8**（脉冲数 / 3433.8 = 升）。
> ⚠️ YF-S401 minimum flow is 0.3 L/min; below this the rotor does not spin. Conversion factor **3433.8** (pulses / 3433.8 = liters).

---

## 📁 目录结构 / Folder Structure

```
demo 1/
├── README.md                 # 本文件（中英双语 + 版本历史）/ this file (bilingual + version history)
├── zh-CN/                    # 中文版 / Chinese（语言 → 算法 → 版本）
│   └── algorithm-v1/         # 第一版算法：风速基准线 + 滑动基准（涵盖 beta1-4）
│       ├── beta1/            # 第一版：原始算法 D<0.30，水泵 D7 开关
│       │   ├── FlowSensor.ino
│       │   ├── server.py
│       │   └── 说明文档.md
│       ├── beta2/            # 第二版：门槛 + 三级阈值 D<0.45
│       │   ├── FlowSensor.ino
│       │   ├── server.py
│       │   └── 说明文档.md
│       ├── beta3/            # 第三版：水泵 D9 PWM 调速 + 滑块 + 功率
│       │   ├── FlowSensor.ino
│       │   ├── server.py
│       │   └── 说明文档.md
│       └── beta4/            # 第四版（最新 · Demo 1 最终版）：尖峰滑动基准 + 整机功率
│           ├── FlowSensor.ino
│           ├── server.py
│           └── 说明文档.md
├── en-US/                    # 英文版 / English（同结构 / same structure）
│   └── algorithm-v1/         # Algorithm v1: wind baseline + sliding baseline
│       ├── beta1/ … beta4/   # 每版含 FlowSensor.ino + server.py + Documentation.md
├── algorithm-iterations/     # 算法迭代文档归档（v1/v2 技术文档，zh-CN + en-US）
├── weather/                  # 风速 + 温湿度模块（网络服务 + Arduino）
└── media/                    # 图片与视频 / photos & videos
    ├── *.jpg
    ├── *.mp4
    └── *.mov
```

> 📂 **结构说明 / Structure note**：中间层为**算法版本**（`algorithm-v1` = 第一版算法：风速基准线 + 滑动基准）。beta1-4 是第一版算法内部的 4 次实现迭代。后续算法迭代（数学预警模型 v2 等）归档于 `algorithm-iterations/`（中英技术文档），与 v1 并行。

---

## 📜 版本历史 / Version History

Demo 1 代码按迭代版本归档（beta1 → beta4），每版独立文件夹，改动如下：

| 版本 / Version | 核心改动 / Key changes |
| --- | --- |
| **beta1**（第一版） | 原始算法：泥石流 D<0.30 无门槛；水泵 D7 数字开关（串口单字节 '1'/'0'） |
| **beta2**（第二版） | 加门槛（土壤<60% 判安全）+ 三级阈值 0.30→0.45；水泵仍 D7 开关 |
| **beta3**（第三版） | 水泵改 D9 PWM 调速 + 网页滑块（0~100%）+ 功率显示（单泵满载 1.25W） |
| **beta4**（第四版 · **Demo 1 最终版**） | 尖峰检测改滑动基准（自适应 P95）+ 功率改整机功率（固定 0.4W + 占空比×泵） |

> 🏁 **版本规划 / Version Plan**：**beta4 是 Demo 1 的最终版本**，Demo 1 到此完结，不再出 beta5。后续进入**算法迭代阶段**：数学预警模型 v1 → v2（传感器标定对齐 YF-S401 实测量程、滑动基准冷启动缩短至 15 分钟、预警等级规范为 0=正常 / 1=一级 / 2=二级 / 3=三级且 3=最高）。~~超声波水位方案已砍掉~~（水位与流速传感器功能重叠，不做曼宁公式 70% 分量）。迭代文档归档于 `algorithm-iterations/`。
> 🏁 **Version plan**: **beta4 is the final version of Demo 1**; Demo 1 is complete and there will be no beta5. Development then moves to the **algorithm iteration phase**: mathematical warning model v1 → v2 (sensor calibration aligned with the measured YF-S401 range, sliding-baseline cold start shortened to 15 minutes, warning levels standardized to 0=Normal / 1=Level 1 / 2=Level 2 / 3=Level 3 with 3 = most severe). ~~The ultrasonic water-level plan is dropped~~ (water level overlaps with the flow sensor; the 70% Manning component will not be implemented). Iteration docs are archived under `algorithm-iterations/`.

> `.ino` 固件只有两个变体：D7 数字开关版（beta1/2）与 D9 PWM 调速版（beta3/4）；门槛/阈值/尖峰/功率等逻辑改动都在 `server.py`。
> The `.ino` firmware has only two variants: D7 on/off (beta1/2) and D9 PWM (beta3/4); all gate/threshold/spike/power logic changes live in `server.py`.

---

## 🚀 快速开始 / Quick Start

**中文**：
1. 用 Arduino IDE 编译并上传 `zh-CN/FlowSensor.ino`（或英文版）到 Arduino Nano。
2. 运行 `python3 -u server.py`（串口 `/dev/cu.usbserial-14120`）。
3. 浏览器打开 `http://localhost:8080`。

**English**:
1. Compile & upload `en-US/FlowSensor.ino` (or the Chinese version) to the Arduino Nano using Arduino IDE.
2. Run `python3 -u server.py` (serial port `/dev/cu.usbserial-14120`).
3. Open `http://localhost:8080` in a browser.

> 风速来自另一台电脑的 HTTP 服务 `http://192.168.1.200:8001/wind`，需保持该服务在线。
> Wind data comes from another computer's HTTP service at `http://192.168.1.200:8001/wind`; keep it online.

---

## 🧠 预警模型 / Warning Model

### 泥石流 / Debris Flow（已完整落地 / fully implemented）

危险指数 / Danger index：

```
D = 0.40·S̄ + 0.30·Q̄ + 0.20·dQ̄ + 0.10·ΔS̄
```

| 因子 / Factor | 含义 / Meaning |
| --- | --- |
| S̄ | 土壤湿度归一化 / normalized soil moisture |
| Q̄ | 流量归一化 / normalized flow |
| dQ̄ | 流量突变 / flow spike |
| ΔS̄ | 土壤湿度涨幅 / soil-moisture rise |

**门槛 / Gate**：土壤湿度 < 60%（土体未饱和）时直接判安全，泥石流起不来，不参与 D 分级。

**Gate**: soil moisture < 60% (not saturated) is judged safe directly — debris flow cannot initiate — and does not enter D leveling.

**特殊规则 / Special rules**：土壤高湿 + 流量连涨 5 分钟 → 直接升到一级；土壤高湿且流量高 → 二级；土壤湿度涨幅 ≥20% → 至少三级。

**Special rules**: high soil moisture + 5-min sustained flow rise → Level 1; high soil moisture + high flow → Level 2; soil rise ≥20% → at least Level 3.

### 山洪 / Flash Flood（已落地 / implemented）

- **曼宁公式 70% 分量 / Manning 70% component**：~~原计划用超声波水位传感器补全，方案已砍掉~~（水位与流速传感器功能重叠，流速为核心，不做曼宁 70%）。
- **Manning 70%**: ~~planned with an ultrasonic water-level sensor; the plan is dropped~~ (water level overlaps with the flow sensor; flow is the core, no Manning 70%).
- **流量近似路径 / Flow-approximation path**（算法 v2 起 / since v2）：`F = 0.60·Q̄ + 0.40·dQ̄`，独立于土壤门槛，流量暴涨即触发。
- **Flow-approximation path**: `F = 0.60·Q̄ + 0.40·dQ̄`, independent of the soil gate — triggers on flow surge alone.
- **尖峰检测 / Spike detection**：用流量秒级变化率近似，滑动基准自适应（对比当地流量变化率历史分布，超 P95 判高风险）。
- **Spike detection**: approximated by per-second flow change rate; sliding-baseline adaptive (vs local flow-change history, >P95 = high risk).

### 滑动基准 / Sliding Baseline（气候自适应 / climate-adaptive）

**中文**：为避免绝对值阈值（如「土壤湿度 60%」）在不同地区气候下不适用，模型维护一个 **24 小时滑动窗口**，用 P10/P95 分位数把当前值映射为「相对当地正常范围的偏离程度（0~1）」。数据积累 **2 小时**后自动启用（算法 v2 起缩短为 **15 分钟**）；不足时回退到绝对值阈值。

**English**: To avoid fixed thresholds (e.g. "soil moisture 60%") not fitting different climates, the model keeps a **24-hour sliding window** and maps the current value onto the P10/P95 percentile range, yielding a "relative deviation from local normal (0~1)". It activates after **2 hours** of data (shortened to **15 minutes** since algorithm v2); before that it falls back to absolute thresholds.

### 预警档位 / Warning Levels（v1：一级最严重 / v1: Level 1 = most severe）

| 档位 / Level | 颜色 / Color | 泥石流 D 阈值 / Debris-flow D |
| --- | --- | --- |
| 🟢 正常 Normal | 绿 Green | D < 0.45 |
| 🟡 三级 Level 3 | 黄 Yellow | 0.45 ≤ D < 0.55 |
| 🟠 二级 Level 2 | 橙 Orange | 0.55 ≤ D < 0.75 |
| 🔴 一级 Level 1 | 红 Red | D ≥ 0.75 |

> 📌 上表为 Demo 1（v1）档位体系。**算法 v2 起等级规范为 0=正常 / 1=一级 / 2=二级 / 3=三级（3=最高）**，详见 `algorithm-iterations/`。
> 📌 The table above is the Demo 1 (v1) level system. **Since algorithm v2 the levels are standardized as 0=Normal / 1=Level 1 / 2=Level 2 / 3=Level 3 (3 = most severe)** — see `algorithm-iterations/`.

---

## ⚠️ 已知问题 / Known Issues

1. **水泵供电 / Pump power**：水泵从 Arduino 取电，高速时电流大仍会拉垮 5V 断电复位（PWM 软启动已缓解启动冲击，但治标不治本）。**需改为独立供电**（单独 5V 电源，VCC 不再接 Arduino 5V，只共地）。
   **Pump powered from Arduino** sags the 5V rail under high speed, resetting the board (PWM soft-start eases inrush but is not a cure). **Use an independent power supply** (separate 5V source; pump VCC no longer on Arduino 5V, only common ground).

2. **山洪曼宁 / Flash-flood Manning**：~~原计划 Demo 2 用超声波水位传感器补全曼宁 70% 分量，方案已砍掉~~（水位与流速功能重叠），由流量近似路径 `F = 0.60·Q̄ + 0.40·dQ̄`（算法 v2）替代。
   **Flash-flood Manning**: ~~the plan to complete the 70% Manning component with an ultrasonic water-level sensor in Demo 2 is dropped~~ (water level overlaps with flow), replaced by the flow-approximation path `F = 0.60·Q̄ + 0.40·dQ̄` (algorithm v2).

3. **尖峰回退阈值 / Spike fallback threshold**：滑动基准数据不足（<2h）时回退到固定阈值 `2.0 L/min/s`，此参数待实测标定。
   **Spike fallback threshold** `2.0 L/min/s` (used before the sliding baseline has 2h of data) still needs field calibration.

---

## 📄 文档说明 / Documentation Note

- 中文版与英文版代码逻辑完全一致，仅注释与界面文字不同。
- The Chinese and English versions are logically identical; only comments and UI text differ.
- 图片与视频放在 `media/`（素材不分语言）。
- Photos & videos live in `media/` (language-neutral media).
