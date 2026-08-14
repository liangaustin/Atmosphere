/*
 * 02 风速 + 温湿度（DHT11）实时监测程序
 *
 * 功能：
 *   1. 三杯式风速传感器 → 风速（km/h）和电压（V）
 *   2. DHT11 温湿度传感器 → 温度（℃）和湿度（%）
 *   3. 风速 > 10 km/h 时板载 LED（引脚13）闪烁报警
 *   4. 串口输出 CSV：电压,风速,温度,湿度
 *      - 串口监视器：直接看 4 个数值
 *      - 串口绘图器（工具→串口绘图器）：画 4 条曲线
 *      - 风速仪表盘（node server.js）：显示电压/风速/温度
 *
 * 接线：
 *   风速传感器：红线 → A0，黑线 → GND
 *   DHT11：     v → 5V，s → D4，g → GND
 *   （如果板子上没有 D4，s 线可接任意空闲数字脚，改下面 DHTPIN）
 *
 * 需要安装库：工具 → 管理库 → 搜索 "DHT sensor library"（Adafruit）
 * 波特率：9600
 */

#include <DHT.h>

// ============ 配置区 ============
#define DHTPIN 4         // DHT11 数据脚（s）。板子上没有 D4 就换一个空闲数字脚，如 2/3/5/7，并把线接过去
#define DHTTYPE DHT11    // DHT22 就把这里改成 DHT22
#define WIND_PIN A0      // 风速传感器（红线）
#define ALARM_PIN 13     // 报警 LED（板载）
#define WIND_ALARM 10.0  // 风速报警阈值 km/h
// ================================

DHT dht(DHTPIN, DHTTYPE);

float tempC = NAN;          // 最近一次温度
float hum = NAN;            // 最近一次湿度
unsigned long lastDHT = 0;  // 上次读 DHT11 的时间
unsigned long lastBlink = 0;
bool ledOn = false;

void setup() {
  Serial.begin(9600);
  dht.begin();
  pinMode(ALARM_PIN, OUTPUT);
}

void loop() {
  // ---------- 1. 风速 ----------
  int adc = analogRead(WIND_PIN);
  float volt = adc * (5.0 / 1024.0);  // 电压 V
  float kmh = 100.0 * volt;           // 风速 km/h

  // ---------- 2. 温湿度（DHT11 最快 1 秒读一次，不能太频繁） ----------
  if (millis() - lastDHT >= 1000) {
    float h = dht.readHumidity();
    float t = dht.readTemperature();
    if (!isnan(h) && !isnan(t)) {  // 只有读成功才更新，读失败保留旧值
      hum = h;
      tempC = t;
    }
    lastDHT = millis();
  }

  // ---------- 3. 风速报警（LED 闪烁，不阻塞主循环） ----------
  if (kmh > WIND_ALARM) {
    if (millis() - lastBlink >= 200) {  // 每 0.2 秒翻转一次
      ledOn = !ledOn;
      digitalWrite(ALARM_PIN, ledOn ? HIGH : LOW);
      lastBlink = millis();
    }
  } else {
    digitalWrite(ALARM_PIN, LOW);
  }

  // ---------- 4. 串口输出 CSV：电压,风速,温度,湿度 ----------
  Serial.print(volt, 2);
  Serial.print(",");
  Serial.print(kmh, 1);
  Serial.print(",");
  if (isnan(tempC)) Serial.print("NaN");  // DHT11 没读到过 → NaN，仪表盘显示 "--"
  else Serial.print(tempC, 1);
  Serial.print(",");
  if (isnan(hum)) Serial.println("NaN");
  else Serial.println(hum, 1);

  delay(200);  // 风速每 0.2 秒刷新一次
}
