# Atmosphere Demo 1 Documentation (Fourth Edition · Demo 1 Final)

# 1. Project Overview

Atmosphere is a smart monitoring and early-warning system for flash floods and debris flows at outdoor streams / drifting sites.

Demo 1 implements: soil moisture, flow, and wind sensing + pump PWM speed control + web monitoring + early-warning model.

# 2. Hardware Connections

Main controller: Arduino Nano (ATmega328P, new bootloader)

Soil moisture sensor: AO->A2 (analog), DO->D2 (digital / disconnection detect), VCC->5V, GND->GND

Flow sensor YF-S401: Red->5V, Yellow->D8 (signal), Black->GND

Pump: IO to D9 (PWM pin, soft-start / speed control, higher duty = faster); VCC/GND to power, D7 pulled LOW as fallback

Wind sensor (3-cup, 0~5V): on another computer's Arduino UNO A0, forwarded to this machine via HTTP

# 3. Software Implementation

Two files (both included in this folder):

FlowSensor.ino — Arduino firmware: three-channel sensing + pump PWM speed control (soft start), outputs one JSON line per second over serial (9600)

server.py — Python web service (port 8080): serial reading + wind HTTP integration + warning model + web page (with pump slider speed control + total power display)

Serial command: send speed value 0~255 + newline (0 = stop, 255 = full speed).

Pump speed control: D9 PWM + soft start (0→255 ramps smoothly over ~0.5s, smoothing out inrush current).

Web slider: drag 0~100% for real-time speed control (150ms debounce); total power = fixed 0.4W + duty cycle × pump full-load power (default 1.25W estimate, calibratable).

Wind endpoint: remote computer http://192.168.1.200:8001/wind returns JSON (wind_ms / wind_kmh / temp / hum).

# 4. Warning Model

Debris flow (fully implemented):

Danger index D = 0.40·S̄ + 0.30·Q̄ + 0.20·dQ̄ + 0.10·ΔS̄

S̄ normalized soil moisture, Q̄ normalized flow, dQ̄ flow spike, ΔS̄ soil-moisture rise

Gate: soil moisture < 60% (not saturated) is judged safe directly, does not enter D leveling

Special rules: high soil moisture + sustained flow rise -> escalate level

Flash flood (partially implemented):

Manning formula 70% (needs ultrasonic water-level sensor, not yet implemented)

Spike detection 30% (approximated by per-second flow change rate, sliding-baseline adaptive, >local P95 = high risk)

Sliding baseline (climate-adaptive):

A 24-hour sliding window uses P10/P95 percentiles to judge "how far above local normal"; activates after 2 hours of data.

Warning levels (Level 1 = most severe):

🟢 Normal: D < 0.45 (soil moisture < 60% is judged safe directly)

🟡 Level 3 Alert: 0.45 ≤ D < 0.55

🟠 Level 2 Alert: 0.55 ≤ D < 0.75

🔴 Level 1 Alert: D ≥ 0.75

# 5. How to Run

Compile and upload FlowSensor.ino to the Arduino Nano

Run: python3 -u server.py

Open http://localhost:8080 in a browser and drag the slider to adjust pump speed

# 6. Known Issues

Pump powered from the Arduino causes unstable supply and repeated USB resets at high speed (soft start only eases inrush) — needs an independent power supply

Total power is an estimate (no current sensor); full-load power needs calibration from the pump nameplate

Flash-flood Manning 70% missing ultrasonic water-level sensor, pending

Spike sliding baseline implemented; fallback fixed threshold (2.0 L/min/s) still needs field calibration
