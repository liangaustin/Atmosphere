/*
 * Atmosphere - Integrated Monitoring: Soil Moisture + Flow + Pump (digital on/off)
 * Soil moisture: AO->A2, DO->D2, VCC->5V, GND->GND
 * Flow sensor YF-S401: Red->5V, Yellow->D8, Black->GND
 * Pump: IO->D7 (high = pumping)
 * Serial command: single byte '1' pump on / '0' pump off
 */

const int SOIL_AO = A2;
const int SOIL_DO = 2;
const int PUMP_PIN = 7;   // pump digital on/off (high = pumping)
const int FLOW_PIN = 8;

volatile unsigned long pulseCount = 0;
volatile unsigned long cmdCount = 0;   // received-command counter (diagnostics)
unsigned long lastTime = 0;
float totalFlow = 0;
int lastFlowState = HIGH;

int pumpState = 0;   // 0=stop, 1=pumping

void setup() {
  Serial.begin(9600);
  pinMode(SOIL_DO, INPUT_PULLUP);
  pinMode(PUMP_PIN, OUTPUT);
  digitalWrite(PUMP_PIN, LOW);   // start stopped (high = pumping, LOW = stop)
  pinMode(FLOW_PIN, INPUT_PULLUP);
  lastFlowState = digitalRead(FLOW_PIN);
  lastTime = millis();
}

void loop() {
  // read command (single byte '1' on / '0' off)
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '1') { pumpState = 1; digitalWrite(PUMP_PIN, HIGH); cmdCount++; }
    else if (c == '0') { pumpState = 0; digitalWrite(PUMP_PIN, LOW); cmdCount++; }
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
    Serial.print(pumpState);
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
