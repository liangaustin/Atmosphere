/*
 * 板载 LED 测试 — 快闪 + 慢闪交替
 * Arduino UNO 板载 LED 在 pin 13（LED_BUILTIN）
 */

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
}

void loop() {
  // 快闪 3 次
  for (int i = 0; i < 3; i++) {
    digitalWrite(LED_BUILTIN, HIGH);
    delay(100);
    digitalWrite(LED_BUILTIN, LOW);
    delay(100);
  }
  // 慢闪 3 次
  for (int i = 0; i < 3; i++) {
    digitalWrite(LED_BUILTIN, HIGH);
    delay(500);
    digitalWrite(LED_BUILTIN, LOW);
    delay(500);
  }
}
