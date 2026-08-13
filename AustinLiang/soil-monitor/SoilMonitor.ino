/*
 * Atmosphere - 土壤湿度传感器测试（带断线检测）
 * AO → A0，DO → D2，VCC → 5V，GND → GND
 */

const int AO_PIN = A0;
const int DO_PIN = 2;

void setup() {
  Serial.begin(9600);
  pinMode(DO_PIN, INPUT_PULLUP);  // 启用内部上拉，拔掉时稳定为 HIGH
}

void loop() {
  int raw = analogRead(AO_PIN);

  // 断线检测：读5次，看波动
  int minV = raw, maxV = raw;
  for (int i = 0; i < 4; i++) {
    delay(10);
    int v = analogRead(AO_PIN);
    if (v < minV) minV = v;
    if (v > maxV) maxV = v;
  }
  int jitter = maxV - minV;

  // 悬空引脚噪声大且值接近1023（上拉），或波动超过200判为断线
  bool disconnected = (jitter > 200) || (raw > 1010);

  int percent = disconnected ? -1 : constrain(map(raw, 0, 1023, 100, 0), 0, 100);
  bool dry = digitalRead(DO_PIN);

  Serial.print("{\"raw\":");
  Serial.print(raw);
  Serial.print(",\"percent\":");
  Serial.print(percent);
  Serial.print(",\"dry\":");
  Serial.print(dry ? "true" : "false");
  Serial.print(",\"jitter\":");
  Serial.print(jitter);
  Serial.print(",\"connected\":");
  Serial.print(disconnected ? "false" : "true");
  Serial.println("}");

  delay(500);
}
