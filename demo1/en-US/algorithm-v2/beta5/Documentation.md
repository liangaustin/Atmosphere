# Atmosphere Demo 1 Documentation (beta5 · Algorithm v2, first archive)

## 1. Project Overview

Atmosphere is a smart flash-flood & debris-flow monitoring and early-warning system for outdoor streams / drifting sites.

beta5 is the **first archive of Algorithm v2**: built on beta4, it adds an on-site LCD display, upgrades the model to v2 (sensor-calibrated + fast sliding baseline + hysteresis hold + soil-saturation rule), and integrates wind data over the network.

## 2. Hardware Wiring

Controller: Arduino Nano (ATmega328P, new bootloader)

- Soil moisture: AO→A2 (analog), DO→D2 (digital/disconnect detect), VCC→5V, GND→GND
- Flow sensor YF-S401: red→5V, yellow→D8 (signal), black→GND
- Pump: IO→D9 (PWM pin, soft-start/speed; higher duty = faster pumping); independent power supply recommended (common ground only)
- Temp/humidity DHT11: v→5V, s→D4, g→GND (requires DHT sensor library)
- LCD 1602 (I2C): SCL→A5, SDA→A4, address 0x27 (try 0x3F if blank)
- Wind sensor (cup anemometer, 0~5V): on another computer's Arduino UNO A0, forwarded via HTTP 8001

## 3. Software Implementation

Two files (both included in this folder):

**FlowSensor.ino** — Arduino firmware (serial **115200**, one JSON line per second):
- Three data paths: soil moisture (with disconnect detection), flow (YF-S401 pulse counting), temp/humidity (DHT11)
- Pump PWM speed control + soft start (0→255, ~0.5 s smooth ramp); D7 pulled low as a failsafe
- Flow pulses counted on **rising and falling edges separately + D8 level output** (diagnose edge direction / wiring)
- LCD: line 1 `W12.3 S45% F0.50` (wind km/h · soil % · flow L/min), line 2 `ALARM:3 L3` (warning level 0~3)
- LCD data pushed from the server over serial via the **D-line protocol**: `D<wind km/h>,<level>\n` (e.g. `D12.3,2`)

**server.py** — Python web service (port 8080):
- Serial reading + wind HTTP integration (polls `http://192.168.1.200:8001/wind`) + v2 warning model + web page (pump slider, four cards + charts + warning card)
- `lcd_sender` thread: pushes the D line (wind + current level) to the Arduino every second
- Web page metrics: debris D / flood F / soil S / flow Q / dQ / ΔS / spike risk / wind risk

## 4. Warning Model (Algorithm v2)

**Level system (larger number = more severe): 0 = Normal / 1 = Level 1 / 2 = Level 2 / 3 = Level 3 (highest)**

```
Final level = max(Debris flow D, Flash flood F, Wind, Flow spike, Surge, Soil saturation)   ← 0~3
```

**Debris-flow path:**

```
D = 0.30·S̄ + 0.35·Q̄ + 0.20·dQ̄ + 0.15·ΔS̄
```

- Gate: path skipped while soil < 60% (unsaturated) — flash flood / wind are not gated
- Thresholds: D ≥ 0.75 → Level 3; ≥ 0.55 → Level 2; ≥ 0.45 → Level 1
- Special rules: soil above local P90 + rising flow + 5-min continuous rise → Level 3 directly; soil above local P90 + flow ≥ 70% of capacity → Level 2; soil 10-min rise ≥ 20% → at least Level 1

**Flash-flood path (independent index):**

```
F = 0.60·Q̄ + 0.40·dQ̄
```

- Not gated by the soil threshold — triggers on flow surge alone; same thresholds (0.45/0.55/0.75)
- Flow-based approximation of the 70% Manning component (ultrasonic water-level plan dropped; flow is the core)

**Wind path:** ≥25 km/h → Level 1; ≥40 km/h → Level 2; ≥60 km/h → Level 3

**Flow-spike path:** per-second change rate above local historical P95 → Level 2; normalized ≥ 0.8 → Level 1 (fallback when baseline insufficient: rate ≥ 0.5 L/min/s = full scale)

**Surge path (second-level response):** soil rises ≥ 20% within 5 s / wind rises ≥ 12 km/h within 60 s → Level 1 immediately

**Soil-saturation path (new in v2):** soil ≥ 85% or above local P90 → at least Level 1 (saturated soil is itself a hazard, independent of flow)

**Hysteresis hold (new in v2):** level upgrades take effect immediately and are held; downgrades only after the hold time — Level 1: 10 s / Level 2: 15 s / Level 3: 20 s (debounce)

**Sliding baseline:** 24 h window sampled once per minute; current value mapped onto the local [P10, P95] → 0~1; **cold start 15 minutes**; fallback to absolute values when insufficient (Qn=flow/3, dQn=rate/0.5)

## 5. How to Run

1. Compile and upload FlowSensor.ino to the Arduino Nano (serial monitor at **115200**)
2. Run `python3 -u server.py`
3. Open `http://localhost:8080` in a browser; drag the slider to control pump speed
4. Keep the wind service `http://192.168.1.200:8001/wind` online

## 6. Version Status

beta5 is the **first archive of Algorithm v2**: after Demo 1 ended, development moved to the algorithm-iteration phase (warning model v1→v2; docs under `demo1/algorithm-iterations/`). The ultrasonic water-level plan is dropped (overlaps with the flow sensor; no Manning 70%).

## 7. Known Issues

- Wind data depends on an external computer (192.168.1.200:8001); when offline, the wind path is disabled and LCD wind shows 0 — physical migration to the integrated board is a follow-up item
- Narrow flow-sensor range (YF-S401 measured 0.05~3 L/min); calibration serves the current test environment and must be redone if it changes
- Surge thresholds remain empirical (soil +20%/5 s, wind +12 km/h/60 s), not statistically calibrated
- LCD is ASCII-only; cannot display Chinese; field staff must learn the 0~3 level meanings