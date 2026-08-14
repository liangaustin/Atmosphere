/*
 * Atmosphere - 综合监控：土壤湿度 + 流速 + 水泵(PWM调速) + 温湿度(DHT11)
 * 土壤湿度: AO→A2, DO→D2, VCC→5V, GND→GND
 * 流速 YF-S401: 红→5V, 黄→D8, 黑→GND
 * 水泵: IO→D9（PWM 脚，软启动/调速；高电平占空比越大抽水越快）
 * 温湿度 DHT11: v→5V, s→D4, g→GND（需 DHT sensor library）
 * 串口命令: 发速度值 0~255 + 换行（0=停，255=全速）
 */

#include <DHT.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// I2C LCD 1602（SCL→A5, SDA→A4；地址 0x27，若屏不亮改 0x3F）
LiquidCrystal_I2C lcd(0x27, 16, 2);

const int SOIL_AO = A2;
const int SOIL_DO = 2;
const int PUMP_PIN = 9;   // 改到 D9（PWM 脚）
const int FLOW_PIN = 8;
const int DHTPIN = 4;     // DHT11 数据脚
#define DHTTYPE DHT11
DHT dht(DHTPIN, DHTTYPE);
float dhtTemp = NAN;      // 最近一次温度
float dhtHum = NAN;       // 最近一次湿度
bool dhtOk = false;       // DHT11 是否读数成功
unsigned long lastDHT = 0;

const int RAMP_STEP = 10;   // 每步调速幅度（0~255 共约 26 步）
const int RAMP_MS = 20;     // 每步间隔 20ms（软启动约 0.5 秒）

volatile unsigned long pulseCount = 0;
volatile unsigned long risePulses = 0;   // 诊断：上升沿累计
volatile unsigned long fallPulses = 0;   // 诊断：下降沿累计
volatile unsigned long cmdCount = 0;   // 收到命令计数（诊断用）
unsigned long lastTime = 0;
float totalFlow = 0;
int lastFlowState = HIGH;

int targetSpeed = 0;      // 目标速度 0~255
int currentSpeed = 0;     // 当前实际速度 0~255（平滑逼近 target）
unsigned long lastRamp = 0;

// LCD 显示数据（由 server.py 通过串口 D 行下发）
bool lcdMode = false;
String lcdBuf = "";
float lcdWind = 0.0;      // 风速 km/h
int lcdLv = 0;            // 预警等级 0~3（3=三级最严重）
bool lcdHasData = false;

void setup() {
  Serial.begin(115200);
  dht.begin();
  // LCD 初始化并显示测试字样
  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print("Good Morning");
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
  // 读速度命令（非阻塞：累积数字直到换行）+ LCD 数据行（D 开头）
  static int speedBuf = -1;
  while (Serial.available()) {
    char c = Serial.read();
    if (lcdMode) {
      if (c == '\n' || c == '\r') {
        // 解析 "12.3,2" → 风速,预警等级
        int comma = lcdBuf.indexOf(',');
        if (comma > 0) {
          lcdWind = lcdBuf.substring(0, comma).toFloat();
          lcdLv = lcdBuf.substring(comma + 1).toInt();
          if (lcdLv < 0) lcdLv = 0;
          if (lcdLv > 3) lcdLv = 3;
          lcdHasData = true;
        }
        lcdMode = false;
        lcdBuf = "";
      } else if (lcdBuf.length() < 20) {
        lcdBuf += c;
      }
    } else if (c == 'D') {
      lcdMode = true;
      lcdBuf = "";
    } else if (c >= '0' && c <= '9') {
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

  // 轮询流速脉冲（上升沿 + 下降沿分开计数，诊断沿方向）
  int cur = digitalRead(FLOW_PIN);
  if (lastFlowState == LOW && cur == HIGH) { pulseCount++; risePulses++; }
  if (lastFlowState == HIGH && cur == LOW) fallPulses++;
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

    // 温湿度（DHT11 最快 1 秒读一次，失败保留旧值）
    if (now - lastDHT >= 1000) {
      float t = dht.readTemperature();
      float h = dht.readHumidity();
      if (!isnan(t) && !isnan(h)) {
        dhtTemp = t;
        dhtHum = h;
        dhtOk = true;
      } else {
        dhtOk = false;
      }
      lastDHT = now;
    }

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

    // LCD 刷新（收到过 D 行才更新）：行1 风速·土湿·流速，行2 预警等级
    // 注意：AVR snprintf 不支持 %f，全部用整数运算
    if (lcdHasData) {
      int w10 = (int)(lcdWind * 10 + 0.5);          // 风速×10
      int f100 = (int)(flowPerMin * 100 + 0.5);     // 流速×100
      int p = percent < 0 ? 0 : percent;
      char line1[17], line2[17];
      snprintf(line1, sizeof(line1), "W%2d.%d S%2d%% F%d.%02d", w10 / 10, w10 % 10, p, f100 / 100, f100 % 100);
      snprintf(line2, sizeof(line2), "ALARM:%d %s", lcdLv, lcdLv == 0 ? "OK" : (lcdLv == 1 ? "L1" : (lcdLv == 2 ? "L2" : "L3")));
      lcd.setCursor(0, 0);
      lcd.print(line1);
      lcd.setCursor(0, 1);
      lcd.print(line2);
    }

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
    Serial.print(",\"temp\":");
    if (dhtOk) Serial.print(dhtTemp, 1); else Serial.print("null");
    Serial.print(",\"hum\":");
    if (dhtOk) Serial.print(dhtHum, 1); else Serial.print("null");
    Serial.print(",\"dht_ok\":");
    Serial.print(dhtOk ? "true" : "false");
    Serial.print(",\"flow_pulses\":");
    Serial.print(pulses);
    Serial.print(",\"rise_pulses\":");
    Serial.print(risePulses);
    Serial.print(",\"fall_pulses\":");
    Serial.print(fallPulses);
    Serial.print(",\"d8_level\":");
    Serial.print(digitalRead(FLOW_PIN) ? 1 : 0);
    Serial.print(",\"flow\":");
    Serial.print(flowPerMin, 3);
    Serial.print(",\"total\":");
    Serial.print(totalFlow, 3);
    Serial.println("}");

    lastTime = now;
  }
}