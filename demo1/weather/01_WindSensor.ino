/*
 * 01 风速传感器（三杯式风速计，0~5V 模拟电压输出）
 * 新增功能：风速 > 10 km/h 时触发报警（板载 LED 闪烁 + 串口警告）
 *
 * 接线：
 *   传感器 红线 → UNO A0
 *   传感器 黑线 → UNO GND
 *   报警指示  → 引脚 13（默认板载 LED，可外接有源蜂鸣器实现声音报警）
 *
 * 换算公式（官方例程给的标准公式）：
 *   电压 V = ADC值 × 5.0 / 1024
 *   风速(km/h) = 100 × V
 *   例：读到 1V → 100 km/h；0.5V → 50 km/h
 *
 * 打开串口监视器（Ctrl+Shift+M），波特率选 9600，就能看到风速。
 * 对着传感器吹气，数值会明显变大。
 * 风速超过 10 km/h 时：板载 LED 快速闪烁报警，串口打印警告。
 */

const int WIND_PIN = A0;                // 模拟输入引脚（风速传感器）
const int ALARM_PIN = 13;               // 报警引脚：默认板载 LED，可外接有源蜂鸣器
const float WIND_ALARM_THRESHOLD = 10.0; // 报警阈值：风速 > 10 km/h 触发报警

void setup() {
  Serial.begin(9600);         // 打开串口，波特率 9600
  pinMode(ALARM_PIN, OUTPUT); // 报警引脚设为输出模式
}

void loop() {
  int adc = analogRead(WIND_PIN);       // 1. 读 ADC 原始值 0~1023
  float volt = adc * (5.0 / 1024.0);    // 2. 换算成电压 0~5V
  float kmh  = 100.0 * volt;            // 3. 官方公式：km/h
  float ms   = kmh / 3.6;               // 4. 顺便转成 m/s

  Serial.print("ADC=");
  Serial.print(adc);
  Serial.print("  电压=");
  Serial.print(volt, 2);
  Serial.print("V  风速=");
  Serial.print(kmh, 1);
  Serial.print(" km/h (");
  Serial.print(ms, 1);
  Serial.println(" m/s)");

  // 报警判断：风速超过阈值 → LED 快速闪烁 + 串口警告
  if (kmh > WIND_ALARM_THRESHOLD) {
    Serial.println("!!! 警告：风速超过 10 km/h，请注意防范强风 !!!");
    digitalWrite(ALARM_PIN, HIGH);   // 报警 LED 亮
    delay(200);
    digitalWrite(ALARM_PIN, LOW);    // 报警 LED 灭
    delay(200);                      // 快速闪烁（约 0.4 秒一个周期）
  } else {
    digitalWrite(ALARM_PIN, LOW);    // 风速正常，关闭报警
    delay(500);                      // 每 0.5 秒刷新一次
  }
}
