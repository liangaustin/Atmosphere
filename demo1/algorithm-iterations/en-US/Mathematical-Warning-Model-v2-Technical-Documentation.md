# Mathematical Warning Model · v2 Technical Documentation

**Version:** v2 (second release)
**Algorithm name:** Sensor-calibrated + fast sliding baseline warning model
**Date:** 2026-08-14

---

## 1. Changes from v1

| Item | v1 | v2 | Reason |
|------|----|----|--------|
| Level naming | 1 = Level-3 / 3 = Level-1 (Level-1 most severe) | **0 = Normal / 1 = Level 1 / 2 = Level 2 / 3 = Level 3 (Level 3 most severe)** | Standardized level system: larger number = more severe, maximum is Level 3 |
| Debris-flow weights | 0.40S+0.30Q+0.20dQ+0.10ΔS | **0.30S+0.35Q+0.20dQ+0.15ΔS** | Soil saturates easily and used to dominate the score, weight lowered; flow (flash-flood signal) raised to the highest weight |
| Q_MAX (full-channel flow) | 30 L/min | **3 L/min** | Aligned with YF-S401 measured range (measured max ~1.7) |
| DQ_MAX (change-rate cap) | 5 L/min/s | **0.5 L/min/s** | Measured per-second jumps ~0.3 |
| Spike fallback threshold | 2.0 | **0.5** | Same as above; lets flow data truly participate in inference |
| Sliding-baseline cold start | 2 hours | **15 minutes** | Adapts to local climate faster |
| Flash-flood independent path F | 0.6Q̄+0.4dQ̄ | Retained | Flow surge triggers independently, not gated by soil threshold |
| LCD display | None | **Wind / soil moisture / flow / warning level** | On-site visualization |
| Flow pulse diagnostics | Single-edge counting | **Rising/falling edges counted separately + D8 level** | Quickly locate wiring/edge-direction problems |

---

## 2. Algorithm Structure (v2)

```
Final level = max(Debris flow D, Flash flood F, Wind, Flow spike, Surge, Soil saturation)   ← 0~3
```

**Level definitions (larger number = more severe):**

| Level | Meaning | Example trigger |
|-------|---------|-----------------|
| 0 | Normal | All factors below thresholds |
| 1 | Level-1 warning (mildest) | D/F ≥ 0.45, or wind ≥ 25 km/h, or surge |
| 2 | Level-2 warning | D/F ≥ 0.55, or wind ≥ 40 km/h, or spike ≥ P95 |
| 3 | Level-3 warning (most severe) | D/F ≥ 0.75, or wind ≥ 60 km/h |

### 2.1 Debris Flow Path

```
D = 0.30 × S̄ + 0.35 × Q̄ + 0.20 × dQ̄ + 0.15 × ΔS̄
```

- Path skipped while soil < 60% (unsaturated) — flash flood / wind paths are **not** gated
- **Special rules:** soil above local P90 + rising flow + 5-min continuous rise → Level 3 directly; soil above local P90 + flow ≥ 70% of channel capacity → Level 2; soil 10-min rise ≥ 20% → at least Level 1

### 2.2 Flash Flood Path (independent index)

```
F = 0.60 × Q̄ + 0.40 × dQ̄
```

- **Not gated by the soil threshold** — triggers on flow surge alone
- Acts as a flow-based approximation of the 70% Manning component (this scheme does not use an ultrasonic water-level sensor — water level overlaps with flow rate functionally, flow is the core)

### 2.3 Wind Path

| Wind speed | Level |
|------------|-------|
| ≥ 25 km/h | Level 1 |
| ≥ 40 km/h | Level 2 |
| ≥ 60 km/h | Level 3 |

### 2.4 Flow Spike Path

- Per-second flow change rate above local historical P95 → **Level 2**; ≥ 0.8 normalized → **Level 1**

### 2.5 Surge Path (second-level response)

| Surge | Trigger |
|-------|---------|
| Soil rises ≥ 20% within 5 s | Level 1 immediately |
| Wind rises ≥ 12 km/h within 60 s | Level 1 immediately |

### 2.6 Soil Saturation Path (new in v2)

Soil ≥ 85% or above local P90 → **at least Level 1** (saturated soil is itself a hazard, independent of flow; persists until soil drops)

### 2.7 Hysteresis Hold (new in v2, debounce)

- Upgrade: takes effect immediately and is held
- Downgrade: only after the hold time — Level 1: 10 s / Level 2: 15 s / Level 3: 20 s
- Prevents level flickering from single-point jitter / momentary drops

---

## 3. Sliding Baseline (v2 adjustments)

- **Window:** 24 h, sampled once per minute; current value mapped to the local [P10, P95] range → 0~1 relative position
- **Cold start shortened to 15 minutes:** baseline activates after 15 min of data; the previous 2-hour wait is removed
- **Fallback when data insufficient (absolute values, aligned to sensor range):** Qn = flow/3, dQn = change-rate/0.5

---

## 4. LCD Display (new in v2)

- **Hardware:** I2C LCD 1602 (SCL→A5, SDA→A4, address 0x27)
- **Displayed content (ASCII, refreshed every second):**

```
W12.3 S45% F0.50     ← wind km/h · soil moisture % · flow L/min
ALARM:3 L3           ← warning level 0~3 (0=normal, 3=most severe)
```

- Wind and warning level are pushed from the server (server.py) over serial (protocol `D<wind>,<level>`); soil moisture and flow are read locally by the Arduino

---

## 5. Strengths

1. **Flow data truly participates in inference:** after calibration parameters are aligned with the sensor range, Q̄/dQ̄ change from "squashed mosquito legs" into effective factors; the flash-flood path responds to real flow changes
2. **Sliding baseline activates quickly:** 15-min cold start — self-adapts to local climate a quarter hour after power-on
3. **Standardized level system:** 0~3, larger number = more severe; LCD/web/docs use a consistent convention (Level 3 = highest)
4. **On-site visualization:** LCD shows the four core data streams in real time, observable without a computer/web page
5. **Diagnostics:** dual-edge pulse counting + level output — wiring/signal problems located within 30 s
6. Retains all v1 advantages: independent multi-paths, simple and explainable, cold-start capable

---

## 6. Limitations

1. **Flow sensor range still narrow:** YF-S401 measured 0.05~3 L/min; real flood flows far exceed this — calibration parameters serve the current test environment (pump + pipe) and must be recalibrated when the environment changes
2. **Wind data depends on an external computer** (192.168.1.200:8001): when that service is offline the wind path is disabled (LCD wind shows 0)
3. **15-min sliding baseline may still be unstable:** under sudden weather, the first 15 minutes of baseline are low quality; absolute fallback precision is limited
4. **Surge thresholds remain empirical** (soil +20%/5 s, wind +12 km/h/60 s), not statistically calibrated
5. **LCD is ASCII-only:** cannot display Chinese; field staff must learn the 0~3 number meanings
6. **Hard level thresholds:** 0.45/0.55/0.75 step jumps with no confidence/persistence check (single-point jitter may cause false alarms)

---

## 7. Characteristics

1. **Real-time:** recomputed every second + LCD refreshed every second + web page refreshed every 0.5 s
2. **Dual-end display:** web page (full metrics) + LCD (core on-site metrics)
3. **Calibratable parameters:** Q_MAX/DQ_MAX/spike threshold come from measurements, not guesses
4. **Modular:** 5 independent paths, each can be iterated separately later

---

## 8. Version Plan

- **v2.x candidates:** calibrate surge thresholds from historical distribution (replacing empirical values); ~~add persistence check (trigger only after N consecutive seconds above threshold, debounce)~~ — implemented: hysteresis hold (Level 1: 10 s / Level 2: 15 s / Level 3: 20 s)
- **v3 candidates:** wind sensor onboard (sensor migrated to the integrated board, removing external-computer dependency); LCD shows flash-flood F / debris-flow D values
