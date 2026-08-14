// 风速仪表盘服务器：数据来自 8001 端口的风速转发服务（wind_server.py 独占串口）
// 启动：node server.js （或 npm start）
// 打开浏览器访问打印出来的地址，默认 http://localhost:3000

const http = require('http');
const fs = require('fs');
const path = require('path');

const PUB = path.join(__dirname, 'public');
const FORWARD_URL = 'http://127.0.0.1:8001/wind';   // 8001 转发接口（wind_server.py）

let clients = new Set();
let paused = false;
let state = { connected: false, portName: null, baud: 9600, error: null, last: null, count: 0, score: null };

// ============ 加分/预警引擎 ============
const SAMPLES_MAX_AGE = 90 * 60 * 1000;   // 样本保留 90 分钟（够算“一小时前”对比）
const samples = [];                        // {t, kmh, temp, hum}

function pushSample(v) {
  samples.push(v);
  const cutoff = Date.now() - SAMPLES_MAX_AGE;
  while (samples.length && samples[0].t < cutoff) samples.shift();
}

// 某字段在 [ageMin, ageMax] 毫秒前的均值；数据不足返回 NaN
function meanField(field, ageMin, ageMax) {
  const now = Date.now();
  let sum = 0, n = 0;
  for (const s of samples) {
    const age = now - s.t;
    if (age >= ageMin && age <= ageMax && s[field] != null) { sum += s[field]; n++; }
  }
  return n ? sum / n : NaN;
}

// 阵风：最近 gustWin 毫秒内的最大风速（km/h）
function gustPeak(gustWin) {
  const now = Date.now();
  let mx = NaN;
  for (const s of samples) {
    const age = now - s.t;
    if (age <= gustWin && s.kmh != null && (isNaN(mx) || s.kmh > mx)) mx = s.kmh;
  }
  return mx;
}

// 露点（Magnus 公式）
function dewPoint(t, rh) {
  const a = 17.625, b = 243.04;
  const g = Math.log(rh / 100) + a * t / (b + t);
  return b * g / (a - g);
}

const MIN = 60 * 1000;
const fmt = v => isNaN(v) ? '--' : v.toFixed(1);
const pct = v => isNaN(v) ? '--' : (v * 100).toFixed(0) + '%';
// 返回当前得分评估：{ score, level, rules, ruleStates:[{name,pts,active,note}], metrics, baselineKmh, gustMs }
// level: 0=正常 1=一级(≥4) 2=二级(≥6) 3=三级(≥8)；得分 = 当前满足条件的分值合计
function computeScore() {
  const ruleStates = [];
  let score = 0;
  const add = (name, pts, ok, note) => {
    ruleStates.push({ name, pts, active: !!ok, note: note || '' });
    if (ok) score += pts;
  };

  const gust = gustPeak(3000);                        // 阵风：最近 3 秒峰值
  const gustMs = gust / 3.6;
  const mean2Ms = meanField('kmh', 0, 2 * MIN) / 3.6; // 2 分钟平均 m/s
  const baselineKmh = meanField('kmh', 0, 30 * MIN);  // 基准线：30 分钟平均 km/h
  const baselineMs = baselineKmh / 3.6;

  // 1. 阵风骤增：2分钟平均 ≥ 基线2倍 且 阵风 ≥ 5m/s
  add('阵风骤增', 3, !isNaN(mean2Ms) && !isNaN(baselineMs) && baselineMs > 0.1 && mean2Ms >= 2 * baselineMs && gustMs >= 5,
    '2分钟均值 ' + fmt(mean2Ms) + ' vs 2×基准线 ' + fmt(2 * baselineMs) + ' m/s');
  // 2. 静风后突风：平均 < 1.5m/s 且 阵风 ≥ 4m/s
  add('静风后突风', 2, !isNaN(mean2Ms) && mean2Ms < 1.5 && gustMs >= 4,
    '均值 ' + fmt(mean2Ms) + ' <1.5 且 阵风 ' + fmt(gustMs) + ' ≥4 m/s');
  // 3. 大风：阵风 ≥ 5m/s
  add('大风', 2, gustMs >= 5, '阵风 ' + fmt(gustMs) + ' ≥5 m/s');

  const tempNow = meanField('temp', 0, 30 * 1000);
  const temp15 = meanField('temp', 14 * MIN, 16 * MIN);
  // 4. 温度骤降：现在比 15 分钟前低 5℃
  add('温度骤降', 2, !isNaN(tempNow) && !isNaN(temp15) && tempNow <= temp15 - 5,
    '当前 ' + fmt(tempNow) + ' vs 15分钟前 ' + fmt(temp15) + ' ℃');

  const hum10 = meanField('hum', 0, 10 * MIN);
  const hum60 = meanField('hum', 55 * MIN, 65 * MIN);
  const humNow = meanField('hum', 0, 30 * 1000);
  // 5. 湿度骤升：10分钟均值比一小时前提升 ≥15%
  add('湿度骤升', 2, !isNaN(hum10) && !isNaN(hum60) && hum60 > 0 && hum10 >= hum60 * 1.15,
    '10min均值 ' + fmt(hum10) + ' vs 1h前 ' + fmt(hum60) + ' %');
  // 6. 湿度高且突然上升：≥80% 且一小时提升 ≥15%
  add('湿度高且突然上升', 3, !isNaN(humNow) && !isNaN(hum60) && humNow >= 80 && hum60 > 0 && (humNow - hum60) / hum60 >= 0.15,
    '当前 ' + fmt(humNow) + ' ≥80% 且 1h内升 ' + pct((humNow - hum60) / hum60));
  // 7. 湿度接近饱和：≥90%
  add('湿度接近饱和', 1, !isNaN(humNow) && humNow >= 90, '当前 ' + fmt(humNow) + ' ≥90%');
  // 8. 露点贴近气温：气温-露点 ≤2℃ 且 湿度 ≥70%
  let dewDiff = null;
  if (!isNaN(tempNow) && !isNaN(humNow) && humNow >= 70) {
    dewDiff = tempNow - dewPoint(tempNow, humNow);
  }
  add('露点贴近气温', 2, dewDiff != null && dewDiff <= 2,
    dewDiff == null ? '湿度<70%，暂不参与' : '温差 ' + fmt(dewDiff) + ' ≤2℃');

  const level = score >= 8 ? 3 : score >= 6 ? 2 : score >= 4 ? 1 : 0;
  const rules = ruleStates.filter(r => r.active).map(r => ({ name: r.name, pts: r.pts }));
  return {
    score, level, rules, ruleStates,
    metrics: {
      gustMs: isNaN(gustMs) ? null : gustMs,
      mean2Ms: isNaN(mean2Ms) ? null : mean2Ms,
      baselineMs: isNaN(baselineMs) ? null : baselineMs,
      tempNow: isNaN(tempNow) ? null : tempNow,
      temp15: isNaN(temp15) ? null : temp15,
      hum10: isNaN(hum10) ? null : hum10,
      hum60: isNaN(hum60) ? null : hum60,
      humNow: isNaN(humNow) ? null : humNow,
      dewDiff: dewDiff
    },
    baselineKmh: isNaN(baselineKmh) ? null : baselineKmh,
    gustMs: isNaN(gustMs) ? null : gustMs
  };
}
// ======================================

function broadcast(obj) {
  const data = 'data: ' + JSON.stringify(obj) + '\n\n';
  for (const res of clients) {
    try { res.write(data); } catch (e) { clients.delete(res); }
  }
}

// 解析一行串口数据（兼容两种格式）
function parseLine(line) {
  line = (line || '').trim();
  if (!line) return null;
  // 格式1：电压,风速[,温度[,湿度]]  (0.51,51.3,26.5,55.0 或 0.00,0.0,NaN,NaN)
  const nums = line.split(',').map(s => parseFloat(s.trim()));
  if (nums.length >= 2 && !isNaN(nums[0]) && !isNaN(nums[1])) {
    const t = nums.length >= 3 ? nums[2] : NaN;
    const h = nums.length >= 4 ? nums[3] : NaN;
    return { volt: nums[0], kmh: nums[1], temp: isNaN(t) ? null : t, hum: isNaN(h) ? null : h };
  }
  // 格式2：01 例程的文本  电压=0.51V 风速=51.3 km/h
  const km = line.match(/风速=([\d.]+)/);
  if (km) {
    const vm = line.match(/电压=([\d.]+)/);
    const tm = line.match(/温度=([\d.]+)/);
    const hm = line.match(/湿度=([\d.]+)/);
    return { kmh: parseFloat(km[1]), volt: vm ? parseFloat(vm[1]) : null, temp: tm ? parseFloat(tm[1]) : null, hum: hm ? parseFloat(hm[1]) : null };
  }
  // 格式3：只有单个数字
  const n = parseFloat(line);
  if (!isNaN(n)) return { kmh: n, volt: null };
  return null;
}

// ============ 数据源：轮询 8001 转发接口（不再直接占串口） ============
function numOrNull(x) {
  const n = parseFloat(x);
  return isNaN(n) ? null : n;
}

function markDown(msg) {
  if (state.connected || state.error !== msg) {
    state = { ...state, connected: false, error: msg };
    broadcast(state);
  }
}

function pollForward() {
  if (paused) { setTimeout(pollForward, 1000); return; }
  http.get(FORWARD_URL, (res) => {
    let body = '';
    res.on('data', c => body += c);
    res.on('end', () => {
      try {
        const j = JSON.parse(body);
        const kmh = parseFloat(j.wind_kmh);
        if (!isNaN(kmh)) {
          const v = { volt: null, kmh, temp: numOrNull(j.temp), hum: numOrNull(j.hum), t: Date.now() };
          if (!state.connected) {
            state = { ...state, connected: true, portName: 'COM3 (经8001转发)', baud: 9600, error: null };
            broadcast(state);
          }
          state.last = v;
          state.count++;
          pushSample(v);
          const ev = computeScore();
          state.score = ev;
          broadcast({ type: 'data', ...v, ...ev });
        }
      } catch (e) {
        markDown('转发数据解析失败: ' + e.message);
      }
      setTimeout(pollForward, 1000);
    });
  }).on('error', (e) => {
    markDown('8001 转发不可用: ' + e.message);
    setTimeout(pollForward, 2000);
  });
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://x');

  // 静态页面
  if (url.pathname === '/' || url.pathname === '/index.html') {
    const f = path.join(PUB, 'index.html');
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    fs.createReadStream(f).pipe(res);
    return;
  }
  // 串口列表（已改为经 8001 转发，这里返回固定信息）
  if (url.pathname === '/api/ports') {
    res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
    res.end(JSON.stringify({ ports: [{ path: 'COM3', desc: '经 8001 转发（wind_server.py）' }] }));
    return;
  }
  // 连接 / 断开（切换轮询开关）
  if (url.pathname === '/api/connect' && req.method === 'POST') {
    paused = false;
    if (!state.connected) { state = { ...state, error: null }; broadcast(state); }
    res.writeHead(200); res.end('ok');
    return;
  }
  if (url.pathname === '/api/disconnect') {
    paused = true;
    state = { ...state, connected: false, error: '已暂停（由网页断开）' };
    broadcast(state);
    res.writeHead(200); res.end('ok');
    return;
  }
  // 状态
  if (url.pathname === '/api/status') {
    res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
    res.end(JSON.stringify(state));
    return;
  }
  // SSE 数据流
  if (url.pathname === '/api/stream') {
    res.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
    });
    res.write('retry: 2000\n\n');
    clients.add(res);
    res.write('data: ' + JSON.stringify(state) + '\n\n');
    req.on('close', () => clients.delete(res));
    return;
  }
  res.writeHead(404); res.end('not found');
});

// 端口：默认 3000，被占用则顺延 3001/3002…
let currentPort = 3000;

function onServerError(e) {
  if (e.code === 'EADDRINUSE') {
    currentPort += 1;
    console.log('端口 ' + (currentPort - 1) + ' 被占用，改用 ' + currentPort);
    server.listen(currentPort, onListening);
  } else {
    console.error('服务器错误:', e.message);
    process.exit(1);
  }
}

function onListening() {
  console.log('==============================================');
  console.log('  风速仪表盘已启动!');
  console.log('  浏览器打开: http://localhost:' + currentPort);
  console.log('  数据源: 8001 转发 (wind_server.py)');
  console.log('  Ctrl+C 停止');
  console.log('==============================================');
}

server.on('close', () => {});
process.on('SIGINT', () => process.exit(0));
// 兜底：任何未捕获异常只记录日志，不让服务器崩溃
process.on('uncaughtException', (e) => {
  console.error('未捕获异常(已忽略):', e.message);
});

server.on('error', onServerError);
if (process.env.PORT) currentPort = parseInt(process.env.PORT, 10) || 3000;
server.listen(currentPort, onListening);
pollForward();
