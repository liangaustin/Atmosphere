/*
 * Atmosphere - 综合监控：土壤湿度 + 流速 + 水泵（数字开关）
 * 土壤湿度：AO->A2, DO->D2, VCC->5V, GND->GND
 * 流速传感器 YF-S401：红->5V, 黄->D8, 黑->GND
 * 水泵：IO->D7（高电平抽水）
 * 串口命令：单字节 '1' 开泵 / '0' 关泵
 */

const int SOIL_AO = A2;
const int SOIL_DO = 2;
const int PUMP_PIN = 7;   // 水泵数字开关（高电平抽水）
const int FLOW_PIN = 8;

volatile unsigned long pulseCount = 0;
volatile unsigned long cmdCount = 0;   // 收到命令计数（诊断用）
unsigned long lastTime = 0;
float totalFlow = 0;
int lastFlowState = HIGH;

int pumpState = 0;   // 0=停，1=抽水

void setup() {
  Serial.begin(9600);
  pinMode(SOIL_DO, INPUT_PULLUP);
  pinMode(PUMP_PIN, OUTPUT);
  digitalWrite(PUMP_PIN, LOW);   // 初始停止（高电平抽水，LOW 停）
  pinMode(FLOW_PIN, INPUT_PULLUP);
  lastFlowState = digitalRead(FLOW_PIN);
  lastTime = millis();
}

void loop() {
  // 读取命令（单字节 '1' 开 / '0' 关）
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '1') { pumpState = 1; digitalWrite(PUMP_PIN, HIGH); cmdCount++; }
    else if (c == '0') { pumpState = 0; digitalWrite(PUMP_PIN, LOW); cmdCount++; }
  }

  // 轮询流速脉冲（上升沿）
  int cur = digitalRead(FLOW_PIN);
  if (lastFlowState == LOW && cur == HIGH) pulseCount++;
  lastFlowState = cur;

  // 每秒输出一次统计
  unsigned long now = millis();
  if (now - lastTime >= 1000) {
    // 流速
    unsigned long pulses = pulseCount;
    pulseCount = 0;
    float flowPerSec = pulses / 3433.8;
    float flowPerMin = flowPerSec * 60;
    totalFlow += flowPerSec;

    // 土壤湿度（带断线检测）
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

    // 输出组合 JSON
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
