/* 比价探针前端逻辑：调用后端 /api/search 并渲染结果与图表 */

/* 31 平台权威清单（与后端 price_collector/sources/registry.py 一致） */
const PLATFORMS = [
  ["jd", "京东"], ["taobao", "淘宝"], ["pdd", "拼多多"], ["tmall", "天猫"],
  ["vip", "唯品会"], ["suning", "苏宁易购"], ["douyin", "抖音电商"],
  ["kuaishou", "快手电商"], ["wechat", "微信小店"], ["xiaohongshu", "小红书"],
  ["c1688", "1688"],
  ["meituan", "美团闪购"], ["jdnow", "京东秒送"], ["tbflash", "淘宝闪购"], ["hema", "盒马"],
  ["dewu", "得物"], ["yanxuan", "网易严选"], ["miyoupin", "小米有品"],
  ["xianyu", "闲鱼"], ["zhuanzhuan", "转转"],
  ["tmallglobal", "天猫国际"], ["jdglobal", "京东国际"], ["kaola", "考拉海购"], ["douyinglobal", "抖音全球购"],
  ["temu", "Temu"], ["shein", "SHEIN"], ["tiktokshop", "TikTok Shop"],
  ["aliexpress", "AliExpress"], ["shopee", "Shopee"], ["lazada", "Lazada"], ["amazon", "Amazon"],
];
const PLATFORM_NAMES = {};
const PLATFORM_COLORS = {
  jd: "#e1251b", taobao: "#ff6a00", pdd: "#d9264d", tmall: "#ff0036",
  vip: "#e60012", suning: "#ff6600", douyin: "#161823", kuaishou: "#ff4906",
  wechat: "#07c160", xiaohongshu: "#ff2442", c1688: "#ff7300",
  meituan: "#f6a700", jdnow: "#e1251b", tbflash: "#ff6a00", hema: "#1ba05c",
  dewu: "#161823", yanxuan: "#c0392b", miyoupin: "#ff6700", xianyu: "#f5c518", zhuanzhuan: "#ff6a00",
  tmallglobal: "#ff0036", jdglobal: "#e1251b", kaola: "#00a0e9", douyinglobal: "#161823",
  temu: "#fb7701", shein: "#f50046", tiktokshop: "#000000", aliexpress: "#e62e04",
  shopee: "#ee4d2d", lazada: "#1a4ea1", amazon: "#ff9900",
};
PLATFORMS.forEach(([k, n]) => { PLATFORM_NAMES[k] = n; });

const charts = {};
let lastData = null;

/* 渲染 31 平台 chips（默认全选） */
function renderChips() {
  const box = document.getElementById("platform-chips");
  box.innerHTML = PLATFORMS.map(([k, n]) => `
    <label class="chip" style="--c:${PLATFORM_COLORS[k] || "#64748b"}">
      <input type="checkbox" name="platform" value="${k}" checked />
      <span>${n}</span>
    </label>`).join("");
}

/* ---------- 主题 ---------- */
function initTheme() {
  const saved = localStorage.getItem("pp-theme");
  const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  const theme = saved || (prefersDark ? "dark" : "light");
  document.documentElement.setAttribute("data-theme", theme);
}
function toggleTheme() {
  const cur = document.documentElement.getAttribute("data-theme");
  const next = cur === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  localStorage.setItem("pp-theme", next);
  if (lastData) render(lastData); // 主题变化时重绘图表配色
}

/* ---------- 初始化 ---------- */
document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  document.getElementById("theme-toggle").addEventListener("click", toggleTheme);
  renderChips();
  initCharts();
  document.getElementById("search-form").addEventListener("submit", onSearch);
  showStatus("输入关键词后点击「开始采集」，将真实请求所选 31 个平台", "ok");
});

function initCharts() {
  charts.trend = echarts.init(document.getElementById("chart-trend"));
  charts.compare = echarts.init(document.getElementById("chart-compare"));
  charts.dist = echarts.init(document.getElementById("chart-dist"));
  window.addEventListener("resize", () => {
    Object.values(charts).forEach((c) => c && c.resize());
  });
}

/* 依据当前主题返回图表配色 */
function chartTheme() {
  const dark = document.documentElement.getAttribute("data-theme") === "dark";
  return {
    dark,
    text: dark ? "#c2cdda" : "#334155",
    sub: dark ? "#8a99ad" : "#64748b",
    axis: dark ? "#233147" : "#e2e8f0",
    cross: dark ? "rgba(255,255,255,.06)" : "rgba(15,23,42,.04)",
    tooltipBg: dark ? "#16233a" : "#ffffff",
    tooltipBorder: dark ? "#233147" : "#e2e8f0",
  };
}

/* ---------- 可配置 API 后端 ----------
 * 默认同域。指向外部免费后端时按优先级解析：
 *   1) 页面常量 window.PP_API_BASE  2) ?api=https://... (写入localStorage)
 *   3) localStorage['pp-api-base']  4) 空串=同域
 */
function resolveApiBase() {
  try {
    let base = window.PP_API_BASE || "";
    const q = new URLSearchParams(location.search).get("api");
    if (q) { base = q; localStorage.setItem("pp-api-base", q); }
    else if (!base) base = localStorage.getItem("pp-api-base") || "";
    return base.replace(/\/+$/, "");
  } catch (e) { return ""; }
}
function apiUrl(path) { return resolveApiBase() + path; }

/* ---------- 搜索 ---------- */
async function onSearch(e) {
  e.preventDefault();
  await runSearch();
}

function selectedPlatforms() {
  return Array.from(document.querySelectorAll('input[name="platform"]:checked')).map((el) => el.value);
}

async function runSearch() {
  const keyword = document.getElementById("keyword").value.trim();
  const source = "live"; // 已移除示例/mock 路径，固定真实抓取
  const platforms = selectedPlatforms();

  if (!keyword) { showStatus("请输入商品关键词", "error"); return; }
  if (!platforms.length) { showStatus("请至少选择一个平台", "error"); return; }

  const btn = document.getElementById("btn-search");
  btn.disabled = true;
  btn.innerHTML = '<span class="status__dot" style="display:inline-block;margin:0"></span> 采集中…';
  showStatus("正在采集并清洗数据…", "loading");

  const qs = new URLSearchParams({ keyword, source, platforms: platforms.join(",") });
  try {
    const resp = await fetch(apiUrl("/api/search?" + qs.toString()));
    const data = await resp.json();
    if (!resp.ok) { showStatus("采集出错：" + (data.error || resp.status), "error"); return; }
    lastData = data;
    render(data);
    showStatus(`关键词「${data.keyword}」共采集 ${data.total} 条 · 数据源：${data.source_mode} · ${data.collected_at}`, "ok");
  } catch (err) {
    showStatus("请求失败：" + err.message, "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "开始采集";
  }
}

/* ---------- 状态 ---------- */
function showStatus(msg, type) {
  const el = document.getElementById("status");
  const txt = document.getElementById("status-text");
  el.className = "status " + type;
  txt.textContent = msg;
  el.classList.remove("hidden");
}

/* ---------- 渲染分发 ---------- */
function render(data) {
  renderKpi(data);
  renderTrend(data);
  renderCompare(data);
  renderDist(data);
  renderRecommend(data);
  renderTable(data);
}

/* ---------- KPI ---------- */
const KPI_ICONS = {
  total: '<path d="M3 7l9-4 9 4-9 4-9-4z"></path><path d="M3 12l9 4 9-4M3 17l9 4 9-4"></path>',
  min: '<path d="M3 17l6-6 4 4 8-8"></path><path d="M21 7v6h-6"></path>',
  avg: '<path d="M12 3v18"></path><path d="M5 8h14M5 16h14"></path>',
  max: '<path d="M3 7l6 6 4-4 8 8"></path><path d="M21 17v-6h-6"></path>',
  source: '<path d="M4 7h16M4 12h16M4 17h10"></path>',
};
function renderKpi(data) {
  const el = document.getElementById("kpi");
  el.classList.remove("hidden");
  const products = data.products || [];
  let min = Infinity, max = -Infinity, sum = 0;
  products.forEach((p) => { if (p.price < min) min = p.price; if (p.price > max) max = p.price; sum += p.price; });
  const avg = products.length ? sum / products.length : 0;
  const items = [
    { key: "total", label: "采集商品数", value: data.total, accent: "var(--primary)" },
    { key: "min", label: "最低价 (¥)", value: products.length ? min.toFixed(2) : "-", accent: "var(--ok)" },
    { key: "avg", label: "均价 (¥)", value: products.length ? avg.toFixed(2) : "-", accent: "var(--gold)" },
    { key: "max", label: "最高价 (¥)", value: products.length ? max.toFixed(2) : "-", accent: "var(--jd)" },
    { key: "source", label: "数据源", value: data.source_mode, accent: "var(--bg-grad-b)" },
  ];
  el.innerHTML = items.map((it) => `
    <div class="kpi-card" style="--accent:${it.accent}">
      <div class="kpi-card__icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${KPI_ICONS[it.key]}</svg>
      </div>
      <div class="kpi-value">${it.value}</div>
      <div class="kpi-label">${it.label}</div>
    </div>`).join("");
}

/* ---------- 图表：价格趋势 ---------- */
function renderTrend(data) {
  const t = chartTheme();
  const pts = data.price_trend || [];
  const primary = t.dark ? "#2dd4bf" : "#0d9488";
  charts.trend.setOption({
    color: [primary],
    grid: { left: 56, right: 24, top: 24, bottom: 44 },
    tooltip: {
      trigger: "axis",
      backgroundColor: t.tooltipBg, borderColor: t.tooltipBorder, textStyle: { color: t.text },
      formatter: (params) => {
        const p = pts[params[0].dataIndex];
        return `<b>${PLATFORM_NAMES[p.platform] || p.platform}</b><br/>${escapeHtml(p.name)}<br/>¥${p.price.toFixed(2)}`;
      },
    },
    xAxis: { type: "value", name: "排名", minInterval: 1, nameTextStyle: { color: t.sub }, axisLine: { lineStyle: { color: t.axis } }, axisLabel: { color: t.sub }, splitLine: { show: false } },
    yAxis: { type: "value", name: "价格(¥)", nameTextStyle: { color: t.sub }, axisLine: { lineStyle: { color: t.axis } }, axisLabel: { color: t.sub }, splitLine: { lineStyle: { color: t.axis, type: "dashed" } } },
    series: [{
      type: "line", data: pts.map((p) => [p.rank, p.price]), smooth: true, symbolSize: 6,
      lineStyle: { width: 3 }, areaStyle: { opacity: 0.12 },
      markPoint: { data: [{ type: "min", name: "最低价" }], itemStyle: { color: t.dark ? "#4ade80" : "#16a34a" } },
    }],
  }, true);
}

/* ---------- 图表：平台对比 ---------- */
function renderCompare(data) {
  const t = chartTheme();
  const stats = data.platform_stats || [];
  const names = stats.map((s) => PLATFORM_NAMES[s.platform] || s.platform);
  charts.compare.setOption({
    color: [t.dark ? "#4ade80" : "#16a34a", primary2(t), t.dark ? "#f87171" : "#e1251b"],
    tooltip: { trigger: "axis", backgroundColor: t.tooltipBg, borderColor: t.tooltipBorder, textStyle: { color: t.text } },
    legend: { data: ["最低价", "均价", "最高价"], bottom: 0, textStyle: { color: t.text } },
    grid: { left: 56, right: 24, top: 28, bottom: 52 },
    xAxis: { type: "category", data: names, axisLine: { lineStyle: { color: t.axis } }, axisLabel: { color: t.sub } },
    yAxis: { type: "value", name: "价格(¥)", nameTextStyle: { color: t.sub }, axisLine: { lineStyle: { color: t.axis } }, axisLabel: { color: t.sub }, splitLine: { lineStyle: { color: t.axis, type: "dashed" } } },
    series: [
      { name: "最低价", type: "bar", data: stats.map((s) => s.min_price), barMaxWidth: 26 },
      { name: "均价", type: "bar", data: stats.map((s) => s.avg_price), barMaxWidth: 26 },
      { name: "最高价", type: "bar", data: stats.map((s) => s.max_price), barMaxWidth: 26 },
    ],
  }, true);
}
function primary2(t) { return t.dark ? "#5eead4" : "#0d9488"; }

/* ---------- 图表：价格分布 ---------- */
function renderDist(data) {
  const t = chartTheme();
  const dist = data.price_distribution || [];
  charts.dist.setOption({
    color: [t.dark ? "#fbbf24" : "#f59e0b"],
    tooltip: { trigger: "axis", backgroundColor: t.tooltipBg, borderColor: t.tooltipBorder, textStyle: { color: t.text } },
    grid: { left: 56, right: 24, top: 24, bottom: 64 },
    xAxis: { type: "category", data: dist.map((d) => d.range), axisLine: { lineStyle: { color: t.axis } }, axisLabel: { color: t.sub, rotate: 32, interval: 0 } },
    yAxis: { type: "value", name: "商品数", minInterval: 1, nameTextStyle: { color: t.sub }, axisLine: { lineStyle: { color: t.axis } }, axisLabel: { color: t.sub }, splitLine: { lineStyle: { color: t.axis, type: "dashed" } } },
    series: [{ type: "bar", data: dist.map((d) => d.count), barMaxWidth: 44, itemStyle: { borderRadius: [6, 6, 0, 0] } }],
  }, true);
}

/* ---------- 性价比推荐 ---------- */
function buildScoreMap(data) {
  const map = {};
  (data.recommendations || []).forEach((r) => {
    map[`${r.name}__${r.price}`] = { score: r.score, label: r.label };
  });
  return map;
}

function renderRecommend(data) {
  const el = document.getElementById("recommend");
  const recs = (data.recommendations || []).slice(0, 8);
  if (!recs.length) { el.innerHTML = '<p class="cell-empty" style="padding:12px">暂无推荐数据</p>'; return; }
  el.innerHTML = recs.map((r) => {
    const top = r.rank <= 3 ? "top" : "";
    const badge = r.label === "性价比之王" ? "rec-king" : r.label === "高性价比推荐" ? "rec-good" : "rec-normal";
    return `
      <div class="rec-item">
        <div class="rec-rank ${top}">${r.rank}</div>
        <div class="rec-info">
          <div class="rec-name" title="${escapeHtml(r.name)}">${escapeHtml(r.name)}</div>
          <div class="rec-meta">${PLATFORM_NAMES[r.platform] || r.platform} · 评分 ${r.shop_rating >= 0 ? r.shop_rating : "-"} · 销量 ${r.sales.toLocaleString()}</div>
        </div>
        <div class="rec-right">
          <span class="badge ${badge}">${r.label}</span>
          <div class="rec-price">¥${r.price.toFixed(2)}</div>
          <div class="rec-score">性价比 ${r.score}</div>
        </div>
      </div>`;
  }).join("");
}

/* ---------- 商品对比表 ---------- */
function renderTable(data) {
  const tbody = document.getElementById("product-body");
  const products = data.products || [];
  const scoreMap = buildScoreMap(data);
  if (!products.length) {
    tbody.innerHTML = '<tr><td colspan="11" class="cell-empty" style="text-align:center;padding:20px">无数据</td></tr>';
    return;
  }
  tbody.innerHTML = products.map((p, i) => {
    const s = scoreMap[`${p.name}__${p.price}`];
    const rating = p.shop_rating >= 0 ? p.shop_rating.toFixed(1) : "-";
    const sales = p.sales_text || p.sales.toLocaleString();
    const url = p.url
      ? `<a class="p-link" href="${p.url}" target="_blank" rel="noopener">查看</a>`
      : '<span class="cell-empty">-</span>';
    const img = p.image
      ? `<img class="p-thumb" src="${escapeHtml(p.image)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.classList.add('p-thumb--broken');this.removeAttribute('src')" />`
      : '<span class="p-thumb p-thumb--empty" aria-hidden="true"></span>';
    const badgeCls = s && s.label === "性价比之王" ? "rec-king" : s && s.label === "高性价比推荐" ? "rec-good" : "rec-normal";
    const scoreBadge = s
      ? `<span class="badge ${badgeCls}">${s.label} ${s.score}</span>`
      : '<span class="badge rec-normal">一般</span>';
    return `
      <tr>
        <td>${i + 1}</td>
        <td><span class="badge ${p.platform}">${PLATFORM_NAMES[p.platform] || p.platform}</span></td>
        <td>${img}</td>
        <td class="p-name" title="${escapeHtml(p.name)}">${escapeHtml(p.name)}</td>
        <td class="num">${p.price.toFixed(2)}</td>
        <td class="num">${p.original_price > 0 ? p.original_price.toFixed(2) : '<span class="cell-empty">-</span>'}</td>
        <td class="num">${sales}</td>
        <td class="num">${rating}</td>
        <td>${escapeHtml(p.shop_name || "-")}</td>
        <td>${scoreBadge}</td>
        <td>${url}</td>
      </tr>`;
  }).join("");
}

function escapeHtml(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
