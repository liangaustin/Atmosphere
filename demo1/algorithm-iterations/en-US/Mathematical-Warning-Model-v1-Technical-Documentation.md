# Mathematical Warning Model · v1 Technical Documentation

**Version:** v1 (first release)
**Algorithm name:** Wind baseline + sliding baseline warning model
**Date:** 2026-08-14

---

## 1. Overview

The v1 model consists of **5 independent warning paths**, computed every second. The final level is the **maximum** of all paths:

```
Final level = max(Debris flow D, Flash flood F, Wind, Flow spike, Surge)
```

Levels: 0 = Normal / 1 = Level-3 warning / 2 = Level-2 warning / 3 = Level-1 warning (most severe)

---

## 2. Warning Paths

### 2.1 Debris Flow (four-factor weighted)

```
D = 0.30 × S̄ + 0.35 × Q̄ + 0.20 × dQ̄ + 0.15 × ΔS̄
```

| Factor | Meaning | Normalization |
|--------|---------|---------------|
| S̄ | Soil moisture level | Sliding baseline [P10,P95] percentile; fallback: reading/100 |
| Q̄ | Flow level | Sliding baseline; fallback: flow/30 L/min |
| dQ̄ | Flow change rate | min(rate/5 L/min/s, 1) |
| ΔS̄ | Soil 10-min rise | min(rise/15%, 1) |

**Gate:** soil moisture < 60% (unsaturated) → debris flow path skipped (debris flow cannot start in dry soil).

**Thresholds:** D ≥ 0.45 → L3 / ≥ 0.55 → L2 / ≥ 0.75 → L1

**Special rules (priority):**
- Soil above local P90 + rising flow + 5-min continuous rise → L1 directly
- Soil above local P90 + flow ≥ 70% of channel capacity → L2 directly
- Soil 10-min rise ≥ 20% → at least L3

> v1 weight adjustment note: soil moisture 0.40 → 0.30 (soil saturates easily and dominated the score); flow raised to the highest weight 0.35 (flash-flood signal is more critical); ΔS̄ 0.10 → 0.15.

### 2.2 Flash Flood (independent index, new in this version)

```
F = 0.60 × Q̄ + 0.40 × dQ̄
```

- **Not gated by soil moisture** — triggers on flow surge alone, simulating upstream rainstorm floods (water arrives before soil saturates)
- Same thresholds: F ≥ 0.45 → L3 / ≥ 0.55 → L2 / ≥ 0.75 → L1
- Acts as a flow-based approximation of the Manning equation (ultrasonic water-level sensor not yet available, so flow level + change rate substitute for the 70% Manning component)

### 2.3 Wind

| Wind speed | Level |
|------------|-------|
| ≥ 25 km/h | L3 |
| ≥ 40 km/h | L2 |
| ≥ 60 km/h | L1 |

- Wind risk index: `wind_risk = min(wind/40, 1)` (for display)
- Strong wind treated as a precursor of severe convection (flash-flood trigger)

### 2.4 Flow Spike

- Per-second flow change rate compared against the local 24h historical distribution; above P95 = high risk
- spike_risk ≥ 0.8 → L3; ≥ 1.0 (above P95) → L2
- Fallback when baseline insufficient: rate ≥ 2 L/min/s = full scale

### 2.5 Surge (second-level response)

| Surge | Trigger |
|-------|---------|
| Soil rises ≥ 20% within 5 s | L3 immediately (saturation/seepage signal) |
| Wind rises ≥ 12 km/h within 60 s | L3 immediately (sudden gale) |

---

## 3. Sliding Baseline (core mechanism)

- **Window:** 24 h, sampled once per minute
- **Normalization:** map current value to the [P10, P95] range of local history → 0~1 relative position
- **Purpose:** self-adapts to local climate — 20% moisture can be "high" in arid regions, 60% only "high" in humid regions; no manual threshold calibration
- **Cold start:** baseline inactive until 2 h of data; falls back to absolute thresholds (soil/100, flow/30)

---

## 4. Strengths

1. **Adaptive:** sliding baseline makes one algorithm work across climates without recalibration
2. **Independent paths:** debris flow / flash flood / wind / spike / surge do not interfere; a failed path does not block others; soil gate cannot block the flood path
3. **Second-level surge response:** sudden events (soil saturation, gale, flow surge) do not wait for 5–10 min windows
4. **Simple & explainable:** no neural networks or complex statistics — weighted sums + thresholds, easy to deploy, debug, and explain to field staff
5. **Cold-start capable:** falls back to absolute thresholds when baseline data is insufficient

---

## 5. Limitations

1. **Missing 70% Manning component:** no ultrasonic water-level sensor, so the main Manning equation (R = 0.7M + 0.3S) cannot run; flow approximation reduces accuracy
2. **Fixed wind thresholds:** 25/40/60 km/h are empirical; not adapted to local wind climate (coastal vs inland "strong wind" differ)
3. **Soil <60% hard gate may miss events:** upstream rainstorm floods can occur while local soil is still dry — mitigated by the flood F path, but F depends on the flow sensor; a failed flow sensor means missed alerts
4. **Cold-start window:** first 2 h uses absolute fallbacks, which may misjudge extreme climates (very arid/humid)
5. **Narrow flow-sensor range:** YF-S401 measures 0.3–3 L/min only; very low/high flows are inaccurate, degrading Q̄ and dQ̄
6. **10-min soil-rise lag:** ΔS̄ needs a 10-min window; sudden wetting relies on the surge path (5 s +20%), leaving a gap in between
7. **Hard thresholds:** 0.45/0.55/0.75 step jumps with no probability/confidence output; boundary values (0.44 vs 0.45) jump semantically

---

## 6. Characteristics

1. **Real-time:** recomputed every second; web page refreshes every 0.5 s
2. **Visualized:** warning card shows 8 metrics — debris D, flood F, soil S̄, flow Q̄, dQ̄, ΔS̄, spike risk, wind risk
3. **Multi-sensor fusion:** soil moisture + water flow + wind + temperature/humidity (DHT11)
4. **Explainable:** every level can be traced to a specific path and factor, suitable for review/demo presentations
5. **Modular:** 5 independent paths; any path can be replaced separately in future versions (e.g., add the Manning 70% component) without affecting the others

---

## 7. Version Plan (iteration direction)

- **v2 (planned):** add ultrasonic water-level sensor → complete the Manning 70% component (R = 0.7M + 0.3S)
- **v2 (planned):** sliding-baseline adaptation for wind thresholds (replace fixed 25/40/60)
- **v2 (planned):** confidence/persistence check (trigger only after N seconds above threshold to reduce single-point false alarms)
