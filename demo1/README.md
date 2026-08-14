# 🌊 Atmosphere — Demo 1

> **山洪 + 泥石流智能监测预警 · 野外溪流 / 漂流点**
> **Flash-flood & debris-flow early warning for outdoor streams & drifting sites**

[![GitHub](https://img.shields.io/badge/GitHub-liangaustin%2FAtmosphere-4fc3f7)](https://github.com/liangaustin/Atmosphere)
[![Board](https://img.shields.io/badge/Board-Arduino%20Nano-00979D)](#-硬件连接--hardware-wiring)
[![Sensor](https://img.shields.io/badge/Sensors-Soil%20%7C%20Flow%20%7C%20Wind%20%7C%20DHT11-43a047)](#-硬件连接--hardware-wiring)
[![Model](https://img.shields.io/badge/Model-v2%20%7C%20Sliding%20Baseline-fb8c00)](#-预警模型--warning-model)
[![Web](https://img.shields.io/badge/Web-8080%20Dashboard-42a5f5)](#-快速开始--quick-start)

---

## 📑 目录 / Contents

- [📖 项目简介 / Overview](#-项目简介--overview)
- [🎯 应用场景 / Scenarios](#-应用场景--scenarios)
- [🏗️ 系统架构 / Architecture](#%EF%B8%8F-系统架构--architecture)
- [🔌 硬件连接 / Hardware Wiring](#-硬件连接--hardware-wiring)
- [📁 目录结构 / Folder Structure](#-目录结构--folder-structure)
- [🚀 快速开始 / Quick Start](#-快速开始--quick-start)
- [🧠 预警模型 / Warning Model](#-预警模型--warning-model)
- [📜 版本历史 / Version History](#-版本历史--version-history)
- [📄 文档索引 / Docs](#-文档索引--docs)
- [⚠️ 已知问题 / Known Issues](#️-已知问题--known-issues)

---

## 📖 项目简介 / Overview

**中文**：Atmosphere 面向野外溪流、漂流点等场景，实时采集**土壤湿度、水流速、风速、温湿度**四类环境数据，通过网页与 LCD 双端监控，用数学模型（泥石流危险指数 + 山洪流量近似 + 滑动基准 + 滞回保持）输出 **0~3 分级预警**，辅助判断山洪、泥石流风险。Demo 1 打通「采集 → 控制 → 监控 → 预警」全链路。

**English**: Atmosphere monitors soil moisture, water flow, wind speed, and temperature/humidity at outdoor streams and drifting sites. It provides live monitoring via web dashboard **and on-site LCD**, and outputs **0–3 graded warnings** via mathematical models (debris-flow danger index + flash-flood flow approximation + sliding baseline + hysteresis hold). Demo 1 completes the full "sense → control → monitor → warn" pipeline.

---

## 🎯 应用场景 / Scenarios

| 场景 / Scenario | 系统做什么 / What the system does |
| --- | --- |
| 🏞️ 漂流点 / Drifting sites | 上游暴雨时水流暴涨 → 山洪路径 F 秒级响应，现场 LCD 显示预警等级 |
| 🏔️ 泥石流沟谷 / Debris-flow valleys | 土壤饱和（≥85% 或超当地 P90）→ 持续一级预警，不依赖流量 |
| 🌪️ 强对流天气 / Severe convection | 风速 ≥25/40/60 km/h 分级预警 + 60 秒突涨 12 km/h 秒级升级 |
| 📡 偏远无网现场 / Remote sites | LCD 本地显示四路核心数据，网页仅作中控台 |

---

## 🏗️ 系统架构 / Architecture

```
┌─────────────┐   ┌──────────────┐   ┌───────────────┐
│ Arduino Nano│──▶│  server.py    │──▶│  Web :8080    │
│ 土壤/流速/DHT│   │  模型 v2 计算 │   │  曲线+预警卡  │
│ 水泵 PWM/LCD │◀──│  LCD 下发     │   └───────────────┘
└─────────────┘   │  (D行协议)    │
     ▲ 115200     └──────▲───────┘
     │                    │ HTTP
┌────┴─────────┐  ┌───────┴──────┐
│ 风速电脑 :8001│──│ 另一台 OpenClaw│（协作开发）
│ wind JSON    │  │  :8131        │
└──────────────┘  └──────────────┘
```

- **采集端**：Arduino Nano（土壤 A2/D2、流速 D8、DHT11 D4、水泵 D9、LCD I2C）
- **服务端**：`server.py`（串口 115200 + 模型推理 + 网页 8080 + LCD 数据下发）
- **风速**：外部电脑 HTTP `192.168.1.200:8001/wind` 接入（LCD 显示 + 预警模型）

---

## 🔌 硬件连接 / Hardware Wiring

**主控 / Controller**：Arduino Nano（ATmega328P，新 Bootloader，串口 115200）

| 设备 / Device | 接线 / Wiring |
| --- | --- |
| 土壤湿度 / Soil moisture | AO→A2，DO→D2，VCC→5V，GND→GND |
| 流速 YF-S401 / Flow | 红 Red→5V，黄 Yellow→D8（信号），黑 Black→GND |
| 温湿度 DHT11 | s→D4，v→5V，g→GND |
| 水泵 / Pump | D9（PWM 调速，软启动，**独立供电 + 共地**） |
| LCD 1602 (I2C) | SCL→A5，SDA→A4（地址 0x27） |
| 风速 / Wind | 外部电脑 Arduino UNO A0（0~5V 三杯式），HTTP 转发 |

> ⚠️ YF-S401 实测量程 **0.05~3 L/min**，系数 3433.8（脉冲数 / 3433.8 = 升）；低于启动流量转子不转。

---

## 📁 目录结构 / Folder Structure

```
demo 1/
├── README.md                    # 本文件（中英双语导航）
├── zh-CN/                       # 中文版（语言 → 算法版本 → 实现迭代）
│   ├── 第一版算法部分/           # 第一版算法：风速基准线 + 滑动基准（beta1-4）
│   │   ├── beta1/ … beta4/      # 每版：FlowSensor.ino + server.py + 说明文档.md
│   └── 第二版算法部分/           # 第二版算法：标定对齐 + 快速滑动基准（beta5 起）
│       └── beta5/               # LCD 显示 + 算法 v2 + 风速接入
├── en-US/                       # 英文版（同结构 / same structure）
│   ├── algorithm-v1/beta1-4/
│   └── algorithm-v2/beta5/
├── algorithm-iterations/        # 数学预警模型技术文档（v1/v2，中英）
├── weather/                     # 风速 + 温湿度模块（网络服务 + Arduino）
└── media/                       # 图片与视频
```

> 📂 **结构约定**：中间层 = **算法版本**（v1/v2），最内层 = **实现迭代**（beta）。beta1-4 属第一版算法；beta5 起属第二版算法（数学预警模型 v2，详见 `algorithm-iterations/`）。

---

## 🚀 快速开始 / Quick Start

```bash
# 1. 烧录固件（Arduino IDE，板卡 Nano + 新 Bootloader，115200）
#    zh-CN/第二版算法部分/beta5/FlowSensor.ino

# 2. 启动服务端（串口 /dev/cu.usbserial-14120）
python3 -u server.py

# 3. 打开网页
http://localhost:8080
```

> 风速来自 `http://192.168.1.200:8001/wind`，需保持该服务在线（10 秒窗口判在线）。

---

## 🧠 预警模型 / Warning Model

详细技术文档（中英双语、含优势/缺陷/迭代记录）见 **`algorithm-iterations/`**：

| 文档 / Doc | 内容 / Content |
| --- | --- |
| [v1 第一版技术文档](./algorithm-iterations/zh-CN/数学预警模型第一版技术文档.md) | 风速基准线 + 滑动基准（beta1-4） |
| [v2 第二版技术文档](./algorithm-iterations/zh-CN/数学预警模型第二版技术文档.md) | 标定对齐 + 快速滑动基准（beta5 起） |

**一句话版 / TL;DR**：

```
最终等级 = max(泥石流 D, 山洪 F, 风速, 流量尖峰, 突变, 土壤饱和)   ← 0~3
D = 0.30·S̄ + 0.35·Q̄ + 0.20·dQ̄ + 0.15·ΔS̄     （泥石流，土壤<60% 跳过）
F = 0.60·Q̄ + 0.40·dQ̄                          （山洪，不受土壤门槛限制）
```

- **等级 / Levels**：0=正常 · 1=一级 · 2=二级 · **3=三级（最高）**
- **滑动基准**：24h 窗口 [P10,P95] 归一化，冷启动 **15 分钟**
- **滞回保持**：触发后保持（一级 10s / 二级 15s / 三级 20s），防抖
- **标定**：Q_MAX=3 L/min、DQ_MAX=0.5、尖峰回退 /0.5（对齐 YF-S401 实测）

---

## 📜 版本历史 / Version History

| 版本 / Version | 算法 / Algorithm | 核心改动 / Key changes |
| --- | --- | --- |
| beta1 | v1 | 原始算法 D<0.30 无门槛；水泵 D7 数字开关 |
| beta2 | v1 | 加门槛（土壤<60%）+ 三级阈值 0.30→0.45 |
| beta3 | v1 | 水泵 D9 PWM 调速 + 网页滑块 + 功率显示 |
| beta4 | v1 | 尖峰滑动基准（自适应 P95）+ 整机功率（**Demo 1 最终版**） |
| **beta5** | **v2** | **LCD 显示（风速/土湿/流速/预警 0-3）+ 算法 v2（标定对齐、山洪 F、滞回、土壤饱和）+ 风速接入** |

> 🏁 **规划 / Plan**：Demo 1 完结于 beta4，beta5 起进入**算法迭代阶段**（数学预警模型 v2，归档 `algorithm-iterations/`）。超声波水位方案已砍（与流速重叠，不做曼宁 70%）。

---

## 📄 文档索引 / Docs

| 位置 / Path | 说明 / Description |
| --- | --- |
| `algorithm-iterations/` | 数学预警模型技术文档（v1/v2，中英） |
| `weather/` | 风速 + 温湿度模块（王立辉，网络服务 + Arduino 代码） |
| `media/` | 演示图片与视频 |
| `README.md` | 本文件（导航 + 版本历史） |

---

## ⚠️ 已知问题 / Known Issues

1. **水泵供电 / Pump power**：必须独立供电（只共地），否则高速拉垮 5V 复位断联。
2. **流量计量程窄 / Flow sensor range**：YF-S401 仅 0.05~3 L/min，真实洪水流量超量程——v2 标定参数面向当前测试环境，换环境需重新标定。
3. **风速依赖外部电脑 / Wind dependency**：8001 服务离线时风速路径失效（LCD 风速显示 0）；物理迁移到综合板为后续项。
4. **硬阈值分级 / Hard thresholds**：0.45/0.55/0.75 阶梯跳变，无置信度/持续性判定（滞回已缓解闪断）。
