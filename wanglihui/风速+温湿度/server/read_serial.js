// 串口原始数据读取器：打开 COM3 读 N 秒（默认 8），打印收到的每一行
const { SerialPort } = require('serialport');
const { ReadlineParser } = require('@serialport/parser-readline');

const duration = parseInt(process.argv[2] || '8', 10) * 1000;
const port = new SerialPort({ path: 'COM3', baudRate: 9600 });
const parser = port.pipe(new ReadlineParser({ delimiter: '\n' }));

let count = 0;
const samples = [];

parser.on('data', (line) => {
  line = line.trim();
  if (!line) return;
  count++;
  samples.push(line);
  console.log('[' + count + '] ' + line);
});

port.on('error', (e) => { console.error('ERR:', e.message); process.exit(1); });

setTimeout(() => {
  console.log('--- 共收到 ' + count + ' 行 ---');
  port.close(() => process.exit(0));
}, duration);
