/*
 * Atmosphere - 综合监控：土壤湿度 + 流速 + 水泵(PWM调速)
 * 土壤湿度: AO→A2, DO→D2, VCC→5V, GND→GND
 * 流速 YF-S401: 红→5V, 黄→D8, 黑→GND
 * 水泵: IO→D9（PWM 脚，软启动/调速；高电平占空比越大抽水越快）
 * 串口命令: 发速度值 0~255 + 换行（0=停，255=全速）
 */

const int SOIL_AO = A2;
const int SOIL_DO = 2;
const int PUMP_PIN = 9;   // 改到 D9（PWM 脚）
const int FLOW_PIN = 8;

const int RAMP_STEP = 10;   // 每步调速幅度（0~255 共约 26 步）
const int RAMP_MS = 20;     // 每步间隔 20ms（软启动约 0.5 秒）

volatile unsigned long pulseCount = 0;
volatile unsigned long cmdCount = 0;   // 收到命令计数（诊断用）
unsigned long lastTime = 0;
float totalFlow = 0;
int lastFlowState = HIGH;

int targetSpeed = 0;      // 目标速度 0~255
int currentSpeed = 0;     // 当前实际速度 0~255（平滑逼近 target）
unsigned long lastRamp = 0;

void setup() {
  Serial.begin(9600);
  pinMode(SOIL_DO, INPUT_PULLUP);
  pinMode(PUMP_PIN, OUTPUT);
  analogWrite(PUMP_PIN, 0);   // 初始停止
  pinMode(7, OUTPUT);          // 兜底：旧 IO 若还接 D7，强制拉低停泵（防浮空误开）
  digitalWrite(7, LOW);
  pinMode(FLOW_PIN, INPUT_PULLUP);
  lastFlowState = digitalRead(FLOW_PIN);
  lastTime = millis();
}

void loop() {
  // 读速度命令（非阻塞：累积数字直到换行）
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

  // 平滑调速：currentSpeed 逐步逼近 targetSpeed（软启动/软停/平滑跟随）
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

  // 轮询流速脉冲（上升沿）
  int cur = digitalRead(FLOW_PIN);
  if (lastFlowState == LOW && cur == HIGH) pulseCount++;
  lastFlowState = cur;

  // 每秒统计输出
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

    // 输出合并 JSON
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
