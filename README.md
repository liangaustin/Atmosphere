# Atmosphere：野外溪流 / 漂流点山洪与泥石流智能监测预警

[![Arduino](https://img.shields.io/badge/Arduino-Nano%20ATmega328P-00979D.svg)](https://www.arduino.cc/)
[![Python](https://img.shields.io/badge/Python-3-green.svg)](https://www.python.org/)
[![Sensor](https://img.shields.io/badge/Sensors-Soil%20%7C%20Flow%20%7C%20Wind%20%7C%20DHT11-43a047.svg)](demo1/README.md)
[![Model](https://img.shields.io/badge/Model-v2%20%7C%20Sliding%20Baseline-fb8c00.svg)](demo1/algorithm-iterations/README.md)
[![Web](https://img.shields.io/badge/Web-8080%20Dashboard-42a5f5.svg)](demo1/README.md)
[![License](https://img.shields.io/badge/License-自定义-lightgrey.svg)](LICENSE)

`Atmosphere` 是一套面向**民间自发漂流活动与野外游泳区域（野泳池）**的低成本、高实效智能监测预警系统。它通过部署在溪流/漂流点的传感器单元，实时采集**土壤湿度、水流速、风速、温湿度**等环境数据，用多因子数学模型判定山洪与泥石流风险等级（0~3 级），并通过**网页监控 + 现场 LCD** 双端呈现，在危险来临前为现场人员争取撤离时间。

> ⚠️ 本系统是**辅助决策工具**，不替代救生员与现场安全管理。山洪预警的黄金法则是**上游预警**——请结合上游雨量/水位遥测站构成完整预警链。
> ⚠️ This is a **decision-support tool**, not a substitute for lifeguards or on-site safety management. The golden rule of flash-flood warning is **upstream early warning** — integrate with upstream rainfall/water-level stations for a complete chain.

## 目录 / Contents

- [主要功能 / Features](#主要功能--features)
- [项目背景 / Background](#项目背景--background)
- [团队分工 / Team](#团队分工--team)
- [硬件方案 / Hardware](#硬件方案--hardware)
- [预警模型 / Warning Model](#预警模型--warning-model)
- [快速开始 / Quick Start](#快速开始--quick-start)
- [项目结构 / Structure](#项目结构--structure)
- [版本历史 / Version History](#版本历史--version-history)
- [文档索引 / Docs](#文档索引--docs)
- [已知限制 / Known Limitations](#已知限制--known-limitations)
- [常见问题 / FAQ](#常见问题--faq)
- [二次开发 / Development](#二次开发--development)
- [贡献 / Contributing](#贡献--contributing)

---

## 主要功能 / Features

- **多传感器融合监测**：土壤湿度、水流速、风速、温湿度四路数据，同一块 Arduino Nano 采集。
- **山洪预警**：山洪路径 F（流量水平 + 流量突变），不受土壤门槛限制，流量暴涨即触发。
- **泥石流预警**：多因子危险指数 D（土湿 + 流量 + 突变 + 涨幅），含土壤饱和度门槛与滑动基准自适应。
- **分级预警**：0=正常 / 1=一级 / 2=二级 / 3=三级（**数字越大越严重**），网页 + LCD 双端显示。
- **现场 LCD**：1602 I2C 屏实时显示风速 / 土湿 / 流速 / 预警等级，不依赖电脑即可观测。
- **综合监控网页**：单页显示四卡 + 实时曲线 + 预警详情（端口 8080），支持水泵 PWM 滑块远程调速。
- **滑动基准自适应**：24 小时窗口 [P10,P95] 分位数归一化，自动适应当地气候，冷启动 15 分钟。
- **滞回防抖**：预警触发后保持（一级 10s / 二级 15s / 三级 20s），避免等级闪烁。
- **断线自愈**：传感器断线检测 + 串口自动重连 + 水泵独立供电防复位。

---

## 项目背景 / Background

民间自发漂流、野泳等亲水活动在山区溪流（天然河道）十分常见，但普遍缺乏有效监管，险情响应滞后。夏季短历时强降雨引发的山洪，可在数分钟内将涓涓细流变成汹涌洪流——据水利部副部长叶建春在国新办发布会介绍（2020年6月），**多年统计下山洪灾害伤亡人数约占洪涝灾害伤亡人数的 70%**，其中涉水游泳、溯溪属于高风险行为。

**核心目标**：以单点 300-400 元的低成本硬件，为漂流点 / 野泳区提供「采集 → 判断 → 预警 → 撤离」的完整闭环，同时保护周边平民安全。

---

## 团队分工 / Team

| 模块 / Module | 职责 / Responsibility | 负责人 / Lead |
|---------------|------------------------|---------------|
| 硬件 / Hardware | 检测（收集数据） | 王立辉（Wang Li Hui） |
| 软件 / Software | Web APP（监控、警报、水泵控制） | 梁振宇（Austin Liang） |
| 预测 / Prediction | AI（分析数据、判断风险） | 待定 / TBD |

---

## 硬件方案 / Hardware

### 传感器单元（单点成本 300-400 元）

| 部件 / Part | 型号 / Spec | 接线 / Wiring |
|-------------|-------------|---------------|
| 主控 / MCU | Arduino Nano（ATmega328P，Optiboot，115200） | FQBN `arduino:avr:nano:cpu=atmega328` |
| 土壤湿度 / Soil | 电容式，AO→A2，DO→D2 | VCC→5V，GND→GND，断线检测（raw=1023 或抖动>200） |
| 水流速 / Flow | YF-S401 霍尔流量计 | 红→5V，黄→D8（信号），黑→GND；系数 3433.8 |
| 风速 / Wind | 三杯式风速计（0~5V 模拟输出） | 红→A0，黑→GND；V=ADC×5/1024，km/h=100×V |
| 温湿度 / DHT11 | 数字单总线 | s→D4，v→5V，g→GND |
| 水泵 / Pump | 直流抽水泵，D9 PWM 调速 | 软启动步长 10/20ms；**独立供电 + 共地** |
| 现场显示 / LCD | 1602 I2C（地址 0x27） | SCL→A5，SDA→A4 |
| 联网 / Network | NB-IoT 主 + LoRa 备（规划） | 低功耗、小数据量 |

> ⚠️ **供电铁律**：水泵必须**独立供电**（单独 5V 电源，只共地）。从 Arduino 5V 取电会拉垮 5V → CH340 掉电 → 板子复位断联。

### 软件环境

- Python 3（pyserial）+ Arduino IDE / arduino-cli
- 浏览器访问综合监控网页（http://localhost:8080）

---

## 预警模型 / Warning Model

**等级体系（数字越大越严重）**：`0 = 正常 / 1 = 一级 / 2 = 二级 / 3 = 三级（最高）`

```
最终等级 = max(泥石流 D, 山洪 F, 风速, 流量尖峰, 突变, 土壤饱和)   ← 0~3
```

| 路径 / Path | 公式 / Formula | 说明 / Note |
|-------------|----------------|-------------|
| 泥石流 D | `D = 0.30·S̄ + 0.35·Q̄ + 0.20·dQ̄ + 0.15·ΔS̄` | 土壤 <60% 时跳过本路径 |
| 山洪 F | `F = 0.60·Q̄ + 0.40·dQ̄` | 独立于土壤门槛，流量暴涨即触发 |
| 风速 | ≥25 / ≥40 / ≥60 km/h | 分别触发一级 / 二级 / 三级 |
| 流量尖峰 | 秒级变化率超当地 P95 | 二级；归一化 ≥0.8 → 一级 |
| 突变 | 土壤 5s 涨 ≥20% / 风速 60s 涨 ≥12 km/h | 立即一级 |
| 土壤饱和 | ≥85% 或超当地 P90 | 至少一级（不依赖流量） |

- **阈值**：D/F ≥ 0.45 → 一级；≥ 0.55 → 二级；≥ 0.75 → 三级。
- **滑动基准**：24h 窗口 [P10,P95] 归一化，冷启动 15 分钟；数据不足回退绝对值（Q_MAX=3 L/min、DQ_MAX=0.5，对齐 YF-S401 实测）。
- **滞回保持**：升级立即生效并保持；降级需超过保持时间（一级 10s / 二级 15s / 三级 20s）。
- 完整推导见 [`demo1/algorithm-iterations/`](demo1/algorithm-iterations/README.md)（v1/v2 技术文档，中英双语）。

---

## 快速开始 / Quick Start

```bash
# 1. 烧录固件（Arduino IDE，板卡 Nano + 新 Bootloader，115200）
#    demo1/zh-CN/第二版算法部分/beta5/FlowSensor.ino
#    或 arduino-cli：
#    arduino-cli compile --fqbn arduino:avr:nano:cpu=atmega328 <ino路径>
#    arduino-cli upload -p /dev/cu.usbserial-xxxx --fqbn arduino:avr:nano:cpu=atmega328 <ino路径>

# 2. 启动服务端（串口 /dev/cu.usbserial-14120）
cd demo1/zh-CN/第二版算法部分/beta5/
python3 -u server.py

# 3. 打开网页
http://localhost:8080
```

---

## 项目结构 / Structure

```
Atmosphere/
├── README.md                  # 本文件（新版导航）/ this file
├── README_CLASSIC.md          # 旧版 README 存档 / classic README archive
├── demo1/                     # Demo 1：算法归档 + 文档（zh-CN / en-US / weather / media）
│   ├── README.md              # demo1 详细导航（徽章 + 结构 + 快速开始）
│   ├── zh-CN/                 # 中文版：第一版算法部分(beta1-4) + 第二版算法部分(beta5)
│   ├── en-US/                 # 英文版（同结构）
│   ├── algorithm-iterations/  # 数学预警模型技术文档（v1/v2，中英）
│   ├── weather/               # 风速 + 温湿度模块（王立辉）
│   └── media/                 # 演示图片与视频
├── AustinLiang/               # 梁振宇工作区（土壤湿度）
├── wanglihui/                 # 王立辉工作区（风速）
└── GJJ/                       # 团队成员工作区
```

> 📂 **结构约定**：demo1 内中间层 = **算法版本**（第一版算法部分 = beta1-4，第二版算法部分 = beta5 起），最内层 = **实现迭代**（beta）。

---

## 版本历史 / Version History

| 版本 / Version | 算法 / Algorithm | 核心改动 / Key changes |
| --- | --- | --- |
| beta1 | v1 | 原始算法 D<0.30 无门槛；水泵 D7 数字开关 |
| beta2 | v1 | 加门槛（土壤<60%）+ 三级阈值 0.30→0.45 |
| beta3 | v1 | 水泵 D9 PWM 调速 + 网页滑块 + 功率显示 |
| beta4 | v1 | 尖峰滑动基准（自适应 P95）+ 整机功率（**Demo 1 最终版**） |
| **beta5** | **v2** | **LCD 显示（风速/土湿/流速/预警 0-3）+ 算法 v2（标定对齐、山洪 F、滞回、土壤饱和）+ 温湿度本地** |

> 🏁 **规划 / Plan**：Demo 1 完结于 beta4；beta5 起进入算法迭代阶段（数学预警模型 v2）。超声波水位方案已砍（与流速重叠，不做曼宁 70%）。

---

## 文档索引 / Docs

| 位置 / Path | 说明 / Description |
| --- | --- |
| [`demo1/README.md`](demo1/README.md) | Demo 1 详细导航（目录结构、快速开始、版本历史） |
| [`demo1/algorithm-iterations/`](demo1/algorithm-iterations/README.md) | 数学预警模型技术文档（v1/v2，中英双语，含优势/缺陷/迭代记录） |
| [`demo1/weather/`](demo1/weather/README.md) | 风速 + 温湿度模块（王立辉，网络服务 + Arduino 代码） |
| `demo1/media/` | 演示图片与视频 |

---

## 已知限制 / Known Limitations

1. **流量计量程窄 / Flow sensor range**：YF-S401 实测 0.05~3 L/min，真实洪水流量超量程——v2 标定参数面向当前测试环境，换环境需重新标定。
2. **突变阈值为经验值 / Empirical surge thresholds**：土壤 5s+20%、风速 60s+12km/h 未做统计标定。
3. **LCD 仅 ASCII / ASCII-only LCD**：1602 无中文字库，现场人员需熟悉 0~3 数字含义。
4. **硬阈值分级 / Hard thresholds**：0.45/0.55/0.75 阶梯跳变，无置信度/持续性判定（滞回已缓解闪断）。

---

## 常见问题 / FAQ

**Q1：水泵一开 Arduino 就重启/断连？**
水泵不能从 Arduino 5V 取电（会拉垮 5V → CH340 掉电 → 板子复位）。必须**独立 5V 电源**，GND 与 Arduino 共地，D9 只发 PWM 信号。

**Q2：LCD 不亮 / 花屏？**
① 检查 I2C 地址（默认 0x27，部分模块是 0x3F，改固件 `lcd(0x27, 16, 2)`）；② 确认 SCL→A5、SDA→A4 没接反；③ 旋转背光电位器调对比度。

**Q3：流速一直为 0？**
YF-S401 最小启动流量 0.3 L/min，低于此值转子不转（吹气测不了，必须通水）。接线：红→5V，黄→D8（信号），黑→GND。

**Q4：风速数值异常 / 静止也有读数？**
三杯式风速计部分型号存在零点偏移（静止时输出 ~0.1-0.2V ≈ 10-20 km/h）。可在固件里读静止 ADC 值做零点校准（读数减去零点再换算）。

**Q5：网页风速显示 0 / 离线？**
风速默认来自外部电脑 HTTP 服务（`192.168.1.200:8001/wind`），该服务离线时风速路径失效。风速传感器接入本机 A0 后自动切换本地模式（`wind_source: local`）。

**Q6：串口连不上 / 找不到端口？**
拔插 USB 后端口号会变，用 `ls /dev/cu.* | grep usbserial` 确认，改 `server.py` 里的 `SERIAL_PORT`。烧录时波特率选 115200（Optiboot 新 Bootloader）。

**Q7：预警一直不触发？**
① 土壤 <60% 时泥石流路径跳过（正常）；② 滑动基准冷启动需 15 分钟；③ 检查网页预警卡里的 D/F 数值是否在阈值附近（0.45/0.55/0.75）。

---

## 二次开发 / Development

- **算法迭代**：新算法版本在 `demo1/algorithm-iterations/` 归档，每代一份技术文档（优势 / 缺陷 / 特点），随迭代更新。
- **固件**：`FlowSensor.ino` 模块化，新增传感器 = 加引脚定义 + 每秒块加采集 + JSON 加字段。
- **服务端**：`server.py` 内嵌网页 + 预警模型，五路径独立计算，可单独迭代。
- **协作开发**：双 OpenClaw 协作（桥 8090 + 对端 8131），任务经桥下发，代码经桥/仓库同步。

---

## 贡献 / Contributing

欢迎提交 Issue 与 PR。涉及硬件接线、标定参数、算法阈值的改动，请在提交前更新对应文档（`demo1/algorithm-iterations/`）。本项目为教学 / 竞赛 / 公益性质，文档一律不署名。
