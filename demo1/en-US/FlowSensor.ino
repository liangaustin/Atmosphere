/*
 * Atmosphere - Integrated Monitoring: Soil Moisture + Flow + Pump (PWM speed control)
 * Soil moisture: AO->A2, DO->D2, VCC->5V, GND->GND
 * Flow sensor YF-S401: Red->5V, Yellow->D8, Black->GND
 * Pump: IO->D9 (PWM pin, soft-start / speed control; higher duty = faster pumping)
 * Serial command: send speed 0~255 + newline (0=stop, 255=full speed)
 */

const int SOIL_AO = A2;
const int SOIL_DO = 2;
const int PUMP_PIN = 9;   // moved to D9 (PWM pin)
const int FLOW_PIN = 8;

const int RAMP_STEP = 10;   // speed step per tick (~26 steps across 0~255)
const int RAMP_MS = 20;     // ms between steps (~0.5s soft start)

volatile unsigned long pulseCount = 0;
volatile unsigned long cmdCount = 0;   // received-command counter (diagnostics)
unsigned long lastTime = 0;
float totalFlow = 0;
int lastFlowState = HIGH;

int targetSpeed = 0;      // target speed 0~255
int currentSpeed = 0;     // actual speed 0~255 (ramps toward target)
unsigned long lastRamp = 0;

void setup() {
  Serial.begin(9600);
  pinMode(SOIL_DO, INPUT_PULLUP);
  pinMode(PUMP_PIN, OUTPUT);
  analogWrite(PUMP_PIN, 0);   // start stopped
  pinMode(7, OUTPUT);          // fallback: force old D7 LOW to stop pump (prevents floating mis-trigger)
  digitalWrite(7, LOW);
  pinMode(FLOW_PIN, INPUT_PULLUP);
  lastFlowState = digitalRead(FLOW_PIN);
  lastTime = millis();
}

void loop() {
  // read speed command (non-blocking: accumulate digits until newline)
  static int speedBuf = -1;
  while (Serial.available()) {
    char c = Serial.read();
    if (c >= '0' && c <= '9') {
      if (speedBuf < 0) speedBuf = 0;
      speedBuf = speedBuf * 10 + (c - '0');
    } else if (c == '\n' || c == '\r') {
      if (speedBuf >= 0) {
        targetSpeed = constrain(speedBuf, 0, 255);
        cmdCount++;
        speedBuf = -1;
      }
    }
  }

  // smooth ramp: currentSpeed approaches targetSpeed (soft start/stop/follow)
  if (millis() - lastRamp >= RAMP_MS) {
    lastRamp = millis();
    if (currentSpeed < targetSpeed) {
      currentSpeed += RAMP_STEP;
      if (currentSpeed > targetSpeed) currentSpeed = targetSpeed;
      analogWrite(PUMP_PIN, currentSpeed);
    } else if (currentSpeed > targetSpeed) {
      currentSpeed -= RAMP_STEP;
      if (currentSpeed < targetSpeed) currentSpeed = targetSpeed;
      analogWrite(PUMP_PIN, currentSpeed);
    }
  }

  // poll flow pulses (rising edge)
  int cur = digitalRead(FLOW_PIN);
  if (lastFlowState == LOW && cur == HIGH) pulseCount++;
  lastFlowState = cur;

  // stats output every second
  unsigned long now = millis();
  if (now - lastTime >= 1000) {
    // flow
    unsigned long pulses = pulseCount;
    pulseCount = 0;
    float flowPerSec = pulses / 3433.8;
    float flowPerMin = flowPerSec * 60;
    totalFlow += flowPerSec;

    // soil moisture (with disconnect detection)
    int raw = analogRead(SOIL_AO);
    int minV = raw, maxV = raw;
    for (int i = 0; i < 4; i++) {
      delay(10);
      int v = analogRead(SOIL_AO);
      if (v < minV) minV = v;
      if (v > maxV) maxV = v;
    }
    int jitter = maxV - minV;
    bool disconnected = (jitter > 200) || (raw > 1010);
    int percent = disconnected ? -1 : constrain(map(raw, 0, 1023, 100, 0), 0, 100);
    bool dry = digitalRead(SOIL_DO);

    // output combined JSON
    Serial.print("{\"pump\":");
    Serial.print(currentSpeed > 0 ? 1 : 0);
    Serial.print(",\"speed\":");
    Serial.print(currentSpeed);
    Serial.print(",\"target_speed\":");
    Serial.print(targetSpeed);
    Serial.print(",\"cmd_count\":");
    Serial.print(cmdCount);
    Serial.print(",\"soil_raw\":");
    Serial.print(raw);
    Serial.print(",\"soil_percent\":");
    Serial.print(percent);
    Serial.print(",\"soil_dry\":");
    Serial.print(dry ? "true" : "false");
    Serial.print(",\"soil_connected\":");
    Serial.print(disconnected ? "false" : "true");
    Serial.print(",\"flow_pulses\":");
    Serial.print(pulses);
    Serial.print(",\"flow\":");
    Serial.print(flowPerMin, 3);
    Serial.print(",\"total\":");
    Serial.print(totalFlow, 3);
    Serial.println("}");

    lastTime = now;
  }
}
