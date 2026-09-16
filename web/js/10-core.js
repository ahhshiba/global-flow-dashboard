"use strict";
/* 資金流向觀測台：共用工具與圖表（純 SVG，無外部函式庫） */

const GFD = JSON.parse(document.getElementById("gfd-data").textContent);
const A = GFD.analysis;
const MONTHS = A.months;
const XS = MONTHS.map((m) => { const [y, mo] = m.split("-").map(Number); return y + (mo - 1) / 12; });
const SVGNS = "http://www.w3.org/2000/svg";
const EVENT_BANDS = (A.events_cfg || []).map((e) => ({ start: e.start, end: e.end, name: e.name }));
const RANGES = [["all", "全期"], ["20", "20 年"], ["10", "10 年"], ["5", "5 年"], ["3", "3 年"], ["1", "1 年"]];

const store = {
  get(k, d) { try { const v = localStorage.getItem("gfd:" + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem("gfd:" + k, JSON.stringify(v)); } catch (e) { /* 無痕視窗等情況直接略過 */ } },
};
const state = { range: store.get("range", "all"), hidden: store.get("hidden", {}) };

/* ── DOM ── */
function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "html") el.innerHTML = v;
    else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) {
    if (kid == null || kid === false) continue;
    el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
  return el;
}
function sv(tag, attrs, text) {
  const el = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(attrs || {})) if (v != null) el.setAttribute(k, v);
  if (text != null) el.textContent = text;
  return el;
}
const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fin = (v) => typeof v === "number" && isFinite(v);

/* ── 格式 ── */
function fmtNum(v, d) {
  if (!fin(v)) return "—";
  const a = Math.abs(v);
  if (d == null) d = a >= 1000 ? 0 : a >= 100 ? 1 : a >= 10 ? 2 : a >= 1 ? 3 : 4;
  return v.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
}
function fmtSigned(v, d = 1, suf = "") {
  if (!fin(v)) return "—";
  const t = Math.abs(v).toFixed(d);
  return (Number(t) === 0 ? "±" : v > 0 ? "+" : "−") + t + suf;
}
const dirClass = (v) => (!fin(v) || v === 0 ? "flat" : v > 0 ? "up" : "down");
const arrow = (v) => (!fin(v) || v === 0 ? "" : v > 0 ? "▲" : "▼");
function chg(v, d = 1, suf = "%") { return h("span", { class: dirClass(v) }, `${arrow(v)} ${fmtSigned(v, d, suf)}`.trim()); }
function chgHTML(v, d = 1, suf = "%") { return `<span class="${dirClass(v)}">${arrow(v)} ${fmtSigned(v, d, suf)}</span>`; }
function fmtAxis(v) {
  const a = Math.abs(v);
  if (a >= 1e6) return (v / 1e6).toFixed(a >= 1e7 ? 0 : 1) + "M";
  if (a >= 1e4) return (v / 1e3).toFixed(0) + "k";
  if (a >= 100) return v.toFixed(0);
  if (a >= 10) return v.toFixed(a % 1 ? 1 : 0);
  return String(+v.toFixed(2));
}
function seriesFmt(sid) {
  const s = A.series[sid];
  if (!s) return (v) => fmtNum(v);
  if (s.kind === "yield") return (v) => (fin(v) ? v.toFixed(2) + "%" : "—");
  const unit = s.unit && !["點", "指數", "比值"].includes(s.unit) ? " " + s.unit : "";
  return (v) => (fin(v) ? fmtNum(v) + unit : "—");
}
function ser(sid, slot, extra) {
  const s = A.series[sid];
  return Object.assign({ key: sid, name: s ? s.name : sid, color: `var(--s${slot})`, values: s ? s.values : [], fmt: seriesFmt(sid) }, extra || {});
}
const has = (sid) => !!(A.series[sid] && A.series[sid].stats);

/* ── 期間 ── */
function rangeStart() {
  if (state.range === "all") return 0;
  return Math.max(0, MONTHS.length - 1 - Number(state.range) * 12);
}
function rangeChips(onChange) {
  const wrap = h("div", { class: "chips", role: "group", "aria-label": "期間" }, h("span", { class: "lab" }, "期間"));
  for (const [k, label] of RANGES) {
    wrap.append(h("button", {
      class: "chip", type: "button", "aria-pressed": String(state.range === k),
      onclick: () => { state.range = k; store.set("range", k); onChange(); },
    }, label));
  }
  return wrap;
}

/* ── 尺寸變化重繪 ── */
const mounted = new Set();
const ro = new ResizeObserver((entries) => {
  for (const e of entries) {
    const host = e.target;
    const w = Math.round(e.contentRect.width);
    if (w && host._w !== w && host._render) { host._w = w; requestAnimationFrame(() => host.isConnected && host._render()); }
  }
});
function mount(host, render) {
  host._render = render;
  mounted.add(host);
  ro.observe(host);
  if (host.clientWidth) { host._w = host.clientWidth; render(); } else requestAnimationFrame(() => { host._w = host.clientWidth; render(); });
}
function redrawVisible() {
  for (const host of mounted) {
    if (!host.isConnected) { mounted.delete(host); ro.unobserve(host); continue; }
    if (host.offsetParent !== null && host._render) host._render();
  }
}

/* ── 提示框 ── */
const tipEl = document.getElementById("tip");
function showTip(html, x, y) {
  tipEl.innerHTML = html;
  tipEl.hidden = false;
  const r = tipEl.getBoundingClientRect();
  let left = x + 14, top = y + 14;
  if (left + r.width > innerWidth - 8) left = x - r.width - 14;
  if (top + r.height > innerHeight - 8) top = y - r.height - 14;
  tipEl.style.left = Math.max(8, left) + "px";
  tipEl.style.top = Math.max(8, top) + "px";
}
function hideTip() { tipEl.hidden = true; }
const tipRow = (color, name, val) => `<div class="tip-r"><i style="background:${color}"></i><span>${esc(name)}</span><b>${val}</b></div>`;

/* ── 刻度 ── */
function linTicks(lo, hi, count) {
  if (lo === hi) { lo -= 1; hi += 1; }
  const raw = (hi - lo) / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const err = raw / mag;
  const step = (err >= 7.5 ? 10 : err >= 3.5 ? 5 : err >= 1.5 ? 2 : 1) * mag;
  const min = Math.floor(lo / step) * step, max = Math.ceil(hi / step) * step;
  const ticks = [];
  for (let v = min; v <= max + step * 1e-6; v += step) ticks.push(+v.toFixed(10));
  return { min, max, ticks };
}
function logTicks(lo, hi) {
  const out = [];
  for (let e = Math.floor(Math.log10(lo)); e <= Math.ceil(Math.log10(hi)); e++) {
    for (const m of [1, 2, 5]) { const v = m * 10 ** e; if (v >= lo && v <= hi) out.push(v); }
  }
  if (out.length < 3) return linTicks(lo, hi, 4).ticks.filter((v) => v > 0 && v >= lo && v <= hi);
  if (out.length > 9) return out.filter((v) => /^1/.test(String(v)) || /^5/.test(String(v)));
  return out;
}
function bandsAt(label) { return EVENT_BANDS.filter((b) => label >= b.start && label <= b.end).map((b) => b.name); }

/* ── 折線圖（單一 Y 軸；指數化或原始值） ── */
function lineChart(host, o) {
  const xs = o.xs || XS, labels = o.labels || MONTHS;
  const i0 = Math.min(o.start ?? 0, xs.length - 1), i1 = xs.length - 1;
  const hidden = o.hidden || new Set();
  const data = o.series.filter((s) => !hidden.has(s.key)).map((s) => {
    let base = null;
    const plot = s.values.map((v, i) => {
      if (i < i0 || !fin(v)) return null;
      if (o.mode !== "index") return v;
      if (base == null) base = v;
      return base > 0 ? (v / base) * 100 : null;
    });
    return Object.assign({}, s, { plot });
  });
  let lo = Infinity, hi = -Infinity;
  for (const d of data) for (let i = i0; i <= i1; i++) { const v = d.plot[i]; if (v != null) { lo = Math.min(lo, v); hi = Math.max(hi, v); } }
  if (!isFinite(lo)) { host.replaceChildren(h("p", { class: "empty" }, "這個期間沒有資料（或所有序列都被隱藏）")); return; }
  for (const r of o.refs || []) { lo = Math.min(lo, r.y); hi = Math.max(hi, r.y); }
  const W = Math.max(260, host.clientWidth || 600), H = o.height || 260;
  const useLog = !!o.log && lo > 0;
  let y0, y1, ticks;
  if (o.yDomain) { [y0, y1] = o.yDomain; ticks = linTicks(y0, y1, 4).ticks.filter((t) => t >= y0 - 1e-9 && t <= y1 + 1e-9); }
  else if (useLog) { y0 = lo / 1.06; y1 = hi * 1.06; ticks = logTicks(y0, y1); }
  else { const t = linTicks(lo, hi, H < 200 ? 3 : 5); y0 = t.min; y1 = t.max; ticks = t.ticks; }
  const yFmt = o.yFmt || fmtAxis;
  const ml = Math.max(...ticks.map((t) => yFmt(t).length)) * 6.9 + 12;
  const direct = o.direct !== false && data.length <= 4 && W > 560;
  const mr = direct ? Math.min(170, Math.max(...data.map((d) => d.name.length)) * 11.5 + 18) : 12;
  const mt = 10, mb = 24, pw = W - ml - mr, ph = H - mt - mb;
  const X = (x) => ml + ((x - xs[i0]) / ((xs[i1] - xs[i0]) || 1)) * pw;
  const Y = (v) => (useLog
    ? mt + (1 - (Math.log(v) - Math.log(y0)) / (Math.log(y1) - Math.log(y0))) * ph
    : mt + (1 - (v - y0) / (y1 - y0 || 1)) * ph);
  const svg = sv("svg", { viewBox: `0 0 ${W} ${H}`, height: H, role: "img", "aria-label": o.label || "折線圖" });

  for (const t of ticks) {
    const y = Y(t);
    if (y < mt - 1 || y > mt + ph + 1) continue;
    svg.append(sv("line", { x1: ml, x2: ml + pw, y1: y, y2: y, style: "stroke:var(--grid);stroke-width:1" }));
    svg.append(sv("text", { x: ml - 8, y: y + 3.5, "text-anchor": "end" }, yFmt(t)));
  }
  // X 軸：年份或月份
  const span = xs[i1] - xs[i0];
  const byDay = String(labels[i1] || "").length >= 10;  // 日期精度到日（日線、週線）
  const maxTicks = Math.max(2, Math.floor(pw / 72));
  if (byDay && span < 0.3) {
    const step = Math.max(1, Math.ceil((i1 - i0) / maxTicks));
    for (let i = i0; i <= i1; i += step) svg.append(sv("text", { x: X(xs[i]), y: H - 6, "text-anchor": "middle" }, labels[i].slice(5)));
  } else if (span < 2.5 && String(labels[i1] || "").length >= 7) {
    const every = [1, 2, 3, 6].find((e) => (span * 12) / e <= maxTicks) || 6;
    let prev = null;
    for (let i = i0; i <= i1; i++) {
      const ym = labels[i].slice(0, 7);
      if (ym === prev) continue;
      const isFirst = prev === null;
      prev = ym;
      if (isFirst && byDay) continue;  // 區間第一個月通常不是從月初開始
      if ((Number(ym.slice(5, 7)) - 1) % every) continue;
      svg.append(sv("text", { x: X(xs[i]), y: H - 6, "text-anchor": "middle" }, ym));
    }
  } else {
    const maxT = Math.max(2, Math.floor(pw / 62));
    const step = [1, 2, 5, 10].find((s) => span / s <= maxT) || 10;
    for (let y = Math.ceil(xs[i0]); y <= xs[i1]; y++) {
      if (y % step) continue;
      const x = X(y);
      svg.append(sv("line", { x1: x, x2: x, y1: mt + ph, y2: mt + ph + 4, style: "stroke:var(--line-strong)" }));
      svg.append(sv("text", { x, y: H - 6, "text-anchor": "middle" }, String(y)));
    }
  }
  svg.append(sv("line", { x1: ml, x2: ml + pw, y1: mt + ph, y2: mt + ph, style: "stroke:var(--line-strong);stroke-width:1" }));

  for (const b of o.bands || []) {
    const a = MONTHS.indexOf(b.start), z = MONTHS.indexOf(b.end);
    if (a < 0 || z < i0) continue;
    const xa = X(xs[Math.max(a, i0)]), xz = X(xs[Math.min(z, i1)]);
    svg.append(sv("rect", { x: xa, y: mt, width: Math.max(2, xz - xa), height: ph, style: "fill:var(--band)" }));
    if (xz - xa > 44) svg.append(sv("text", { x: xa + 4, y: mt + 11, style: "font-size:10px" }, b.name.length > 6 ? b.name.slice(0, 6) + "…" : b.name));
  }
  for (const r of o.refs || []) {
    const y = Y(r.y);
    svg.append(sv("line", { x1: ml, x2: ml + pw, y1: y, y2: y, style: "stroke:var(--line-strong);stroke-width:1" }));
    if (r.label) svg.append(sv("text", { x: ml + 6, y: y - 4 }, r.label));
  }

  for (const d of data) {
    let path = "", pen = false, segs = 0, firstX = null, lastX = null;
    for (let i = i0; i <= i1; i++) {
      const v = d.plot[i];
      if (v == null || (useLog && v <= 0)) { pen = false; continue; }
      const x = X(xs[i]).toFixed(1), y = Y(v).toFixed(1);
      if (!pen) segs++;
      path += `${pen ? "L" : "M"}${x},${y}`;
      pen = true;
      if (firstX == null) firstX = x;
      lastX = x;
    }
    if (o.area && data.length === 1 && segs === 1) {
      const base = !useLog && y0 < 0 && y1 > 0 ? Y(0) : mt + ph;
      svg.append(sv("path", { d: `${path}L${lastX},${base}L${firstX},${base}Z`, style: `fill:color-mix(in srgb, ${d.color} 12%, transparent);stroke:none` }));
    }
    svg.append(sv("path", { d: path, style: `fill:none;stroke:${d.color};stroke-width:${d.width || 1.8};stroke-linejoin:round;stroke-linecap:round` }));
  }

  if (direct) {
    const ends = data.map((d) => {
      for (let i = i1; i >= i0; i--) if (d.plot[i] != null && !(useLog && d.plot[i] <= 0)) return { d, x: X(xs[i]), y: Y(d.plot[i]), y0: Y(d.plot[i]) };
      return null;
    }).filter(Boolean).sort((a, b) => a.y - b.y);
    for (let k = 1; k < ends.length; k++) if (ends[k].y - ends[k - 1].y < 14) ends[k].y = ends[k - 1].y + 14;
    const over = ends.length ? ends[ends.length - 1].y - (mt + ph) : 0;
    if (over > 0) ends.forEach((e) => { e.y -= over; });
    for (const e of ends) {
      svg.append(sv("circle", { cx: e.x, cy: e.y0, r: 3, style: `fill:${e.d.color};stroke:var(--surface);stroke-width:2` }));
      svg.append(sv("text", { x: ml + pw + 8, y: e.y + 4, class: "lbl" }, e.d.name));
    }
  }

  // 十字準線與提示
  const cross = sv("line", { y1: mt, y2: mt + ph, style: "stroke:var(--ink-2);stroke-width:1;opacity:.45", visibility: "hidden" });
  const dots = data.map((d) => sv("circle", { r: 4, style: `fill:${d.color};stroke:var(--surface);stroke-width:2`, visibility: "hidden" }));
  const hit = sv("rect", { x: ml, y: mt, width: Math.max(1, pw), height: ph, class: "hit", tabindex: 0, "aria-label": `${o.label || "圖表"}：用左右方向鍵查看各月數值` });
  svg.append(cross, ...dots, hit);
  let cur = null;
  const tipFmt = o.tipFmt || ((r) => (r.d.fmt ? r.d.fmt(r.raw) : fmtNum(r.raw)) + (o.mode === "index" ? ` <span class="muted">· ${fmtNum(r.v, 0)}</span>` : ""));
  function at(i) {
    i = Math.max(i0, Math.min(i1, i));
    cur = i;
    const x = X(xs[i]);
    cross.setAttribute("x1", x); cross.setAttribute("x2", x); cross.setAttribute("visibility", "visible");
    const rows = [];
    data.forEach((d, k) => {
      const v = d.plot[i];
      if (v == null || (useLog && v <= 0)) { dots[k].setAttribute("visibility", "hidden"); return; }
      dots[k].setAttribute("cx", x); dots[k].setAttribute("cy", Y(v)); dots[k].setAttribute("visibility", "visible");
      rows.push({ d, v, raw: d.values[i] });
    });
    rows.sort((a, b) => b.v - a.v);
    const ev = o.bands ? bandsAt(labels[i]) : [];
    const extra = o.tipNote ? o.tipNote(i) : "";
    const html = `<div class="tip-h">${esc(labels[i])}${o.mode === "index" ? "　指數化" : ""}</div>`
      + (rows.length ? rows.map((r) => tipRow(r.d.color, r.d.name, tipFmt(r))).join("") : '<div class="muted">無資料</div>')
      + (ev.length ? `<div class="tip-note">危機區間：${esc(ev.join("、"))}</div>` : "")
      + (extra ? `<div class="tip-note">${extra}</div>` : "");
    return { x, html };
  }
  function nearest(clientX) {
    const r = svg.getBoundingClientRect();
    const px = (clientX - r.left) * (W / r.width);
    const xv = xs[i0] + ((px - ml) / pw) * (xs[i1] - xs[i0]);
    let a = i0, b = i1;
    while (b - a > 1) { const m = (a + b) >> 1; if (xs[m] < xv) a = m; else b = m; }
    return xv - xs[a] < xs[b] - xv ? a : b;
  }
  function clear() { cross.setAttribute("visibility", "hidden"); dots.forEach((d) => d.setAttribute("visibility", "hidden")); hideTip(); }
  hit.addEventListener("pointermove", (e) => { const r = at(nearest(e.clientX)); showTip(r.html, e.clientX, e.clientY); });
  hit.addEventListener("pointerleave", clear);
  hit.addEventListener("blur", clear);
  hit.addEventListener("keydown", (e) => {
    const keys = { ArrowLeft: -1, ArrowRight: 1, Home: -1e9, End: 1e9 };
    if (!(e.key in keys)) return;
    e.preventDefault();
    const r = at((cur ?? i1) + keys[e.key]);
    const b = svg.getBoundingClientRect();
    showTip(r.html, b.left + r.x * (b.width / W), b.top + mt + 24);
  });
  host.replaceChildren(svg);
}

/* ── 表格替代視圖 ── */
function seriesTable(series, i0, mode) {
  const idx = [];
  for (let i = MONTHS.length - 1; i >= i0; i--) if (i === MONTHS.length - 1 || MONTHS[i].endsWith("-12")) idx.push(i);
  const head = h("tr", {}, h("th", {}, "月份"), series.map((s) => h("th", { class: "n" }, s.name)));
  const rows = idx.map((i) => h("tr", {}, h("td", { class: "n" }, MONTHS[i]), series.map((s) => h("td", { class: "n" }, s.fmt ? s.fmt(s.values[i]) : fmtNum(s.values[i])))));
  return h("table", { class: "data" }, h("thead", {}, head), h("tbody", {}, rows));
}

/* ── 卡片、圖例 ── */
function card({ title, sub, span = 12, note }) {
  const tools = h("div", { class: "tools" });
  const body = h("div");
  const el = h("article", { class: `card span-${span}` },
    h("div", { class: "card-h" }, h("div", {}, h("h3", {}, title), sub ? h("p", { class: "card-sub" }, sub) : null), tools),
    body, note ? h("p", { class: "note" }, note) : null);
  return { el, body, tools };
}
function toolButton(label, pressed, onclick) {
  const b = h("button", { class: "tool", type: "button", "aria-pressed": String(pressed) }, label);
  b.addEventListener("click", () => { const now = b.getAttribute("aria-pressed") !== "true"; b.setAttribute("aria-pressed", String(now)); onclick(now); });
  return b;
}
function legend(series, key, onToggle) {
  const hid = new Set(state.hidden[key] || []);
  const el = h("div", { class: "legend" });
  for (const s of series) {
    const b = h("button", { class: "lg", type: "button", "aria-pressed": String(!hid.has(s.key)), title: "點一下顯示／隱藏" },
      h("i", { style: `background:${s.color}` }), h("span", {}, s.name));
    b.addEventListener("click", () => {
      if (hid.has(s.key)) hid.delete(s.key); else hid.add(s.key);
      state.hidden[key] = [...hid];
      store.set("hidden", state.hidden);
      b.setAttribute("aria-pressed", String(!hid.has(s.key)));
      onToggle();
    });
    el.append(b);
  }
  return { el, hid };
}

/* ── 單一標的線圖（日／週／月／年） ── */
const DETAIL = GFD.detail || {};
const DAY_MS = 86400000;
const RES_LABEL = { d: "日", w: "週", m: "月", y: "年" };
// [鍵, 標籤, 年數]
const RES_RANGES = {
  d: [["1m", "1 個月", 1 / 12], ["3m", "3 個月", 0.25], ["6m", "6 個月", 0.5], ["1y", "1 年", 1], ["3y", "3 年", 3]],
  w: [["1y", "1 年", 1], ["3y", "3 年", 3], ["5y", "5 年", 5], ["10y", "10 年", 10], ["15y", "15 年", 15]],
  m: [["5y", "5 年", 5], ["10y", "10 年", 10], ["20y", "20 年", 20], ["all", "全期", 99]],
  y: [["all", "全期", 99]],
};
const RES_DEFAULT = { d: "6m", w: "3y", m: "all", y: "all" };
const isoDay = (n) => new Date(n * DAY_MS).toISOString().slice(0, 10);
function dayToX(n) {
  const d = new Date(n * DAY_MS), y = d.getUTCFullYear(), a = Date.UTC(y, 0, 1);
  return y + (d - a) / (Date.UTC(y + 1, 0, 1) - a);
}
const LEADER_BY_ID = {};
for (const L of Object.values(A.leaders || {})) for (const it of L.items) LEADER_BY_ID[it.id] = it;
const isRate = (unit) => unit === "%" || unit === "個百分點";
function fmtUnit(v, unit) {
  if (!fin(v)) return "—";
  if (unit === "%") return v.toFixed(3) + "%";
  if (unit === "個百分點") return fmtSigned(v, 2) + " 個百分點";
  if (!unit || ["點", "指數", "比值", "2010=100"].includes(unit)) return fmtNum(v);
  return `${fmtNum(v)} ${unit}`;
}

/* 有日線來源的用日線彙整出週／月／年；只有月資料的（央行、世界銀行、比值）只提供月／年 */
const INSTR_CACHE = {};
function instrument(sid) {
  if (sid in INSTR_CACHE) return INSTR_CACHE[sid];
  const meta = A.series[sid] || LEADER_BY_ID[sid];
  let out = null;
  const D = DETAIL[sid];
  if (meta && D) {
    const note = { d: "日收盤", w: "週收盤（該週最後交易日）", m: "月收盤（該月最後交易日）", y: "年收盤" };
    const res = {};
    for (const r of ["d", "w", "m", "y"]) {
      const blk = D[r];
      if (!blk || blk[0].length < 2) continue;
      res[r] = { xs: blk[0].map(dayToX), labels: blk[0].map((n) => (r === "y" ? isoDay(n).slice(0, 4) : r === "m" ? isoDay(n).slice(0, 7) : isoDay(n))),
        values: blk[1], unit: D.unit, src: `${D.src}・${note[r]}${D.stale ? "・本次抓取失敗，沿用上次資料" : ""}` };
    }
    out = { name: meta.name, res };
  } else if (meta) {
    const unit = A.series[sid] ? A.series[sid].unit : "";
    const note = A.series[sid] ? A.series[sid].note : "還原權息月報酬";
    const xs = [], labels = [], values = [];
    meta.values.forEach((v, i) => { if (fin(v)) { xs.push(XS[i]); labels.push(MONTHS[i]); values.push(v); } });
    if (values.length >= 2) {
      const yx = [], yl = [], yv = [];
      labels.forEach((l, i) => {
        if (i === labels.length - 1 || labels[i + 1].slice(0, 4) !== l.slice(0, 4)) { yx.push(xs[i]); yl.push(l.slice(0, 4)); yv.push(values[i]); }
      });
      out = { name: meta.name, res: {
        m: { xs, labels, values, unit, src: `${note}・月資料（這個標的沒有日線來源）` },
        y: { xs: yx, labels: yl, values: yv, unit, src: `${note}・年底值` } } };
    }
  }
  INSTR_CACHE[sid] = out;
  return out;
}

function singleEngine(key, getSeries, redraw) {
  const ctl = h("div", { class: "viewer-ctl" });
  ctl.hidden = true;
  let pick = store.get("pick:" + key, null);
  let res = store.get("res:" + key, "d");
  let rng = store.get("rng:" + key, null);
  const save = () => { store.set("pick:" + key, pick); store.set("res:" + key, res); store.set("rng:" + key, rng); };
  const seg = (label, items, current, onPick) => h("div", { class: "seg", role: "group", "aria-label": label }, items.map(([k, text, disabled]) => {
    const b = h("button", { type: "button", "aria-pressed": String(k === current), disabled: disabled || null,
      title: disabled ? "這個標的沒有這個週期的資料" : null }, text);
    b.addEventListener("click", () => onPick(k));
    return b;
  }));

  function render(host, tbl, table, useLog) {
    const series = getSeries();
    if (!series.length) { ctl.replaceChildren(); host.replaceChildren(h("p", { class: "empty" }, "沒有可單獨檢視的標的")); return; }
    if (!series.some((s) => s.key === pick)) pick = series[0].key;
    const ins = instrument(pick);
    const avail = ["d", "w", "m", "y"].filter((r) => ins.res[r]);
    if (!avail.includes(res)) res = avail[0];
    const ranges = RES_RANGES[res];
    if (!ranges.some((x) => x[0] === rng)) rng = RES_DEFAULT[res];
    const R = ins.res[res];
    const i1 = R.xs.length - 1;
    const years = ranges.find((x) => x[0] === rng)[2];
    let i0 = R.xs.findIndex((x) => x >= R.xs[i1] - years - 1e-9);
    if (i0 < 0 || i0 >= i1) i0 = Math.max(0, i1 - 1);
    const color = (series.find((s) => s.key === pick) || {}).color || "var(--s1)";
    const first = R.values[i0], last = R.values[i1];
    let hiI = i0, loI = i0;
    for (let i = i0; i <= i1; i++) {
      if (R.values[i] > R.values[hiI]) hiI = i;
      if (R.values[i] < R.values[loI]) loI = i;
    }
    const rate = isRate(R.unit);
    const change = rate ? chg((last - first) * 100, 0, "bp") : chg((last / first - 1) * 100, 2, "%");

    const rows = [];
    if (series.length > 1) {
      rows.push(h("div", { class: "viewer-row", role: "group", "aria-label": "選擇標的" }, series.map((s) => {
        const b = h("button", { class: "lg pick", type: "button", "aria-pressed": String(s.key === pick) }, h("i", { style: `background:${s.color}` }), h("span", {}, s.name));
        b.addEventListener("click", () => { pick = s.key; save(); redraw(); });
        return b;
      })));
    }
    rows.push(h("div", { class: "viewer-row" },
      seg("週期", ["d", "w", "m", "y"].map((r) => [r, RES_LABEL[r] + "線", !ins.res[r]]), res, (k) => { res = k; rng = null; save(); redraw(); }),
      ranges.length > 1 ? seg("期間", ranges.map(([k, t]) => [k, t, false]), rng, (k) => { rng = k; save(); redraw(); }) : null));
    rows.push(h("div", { class: "viewer-sum" },
      h("span", { class: "v-name" }, ins.name),
      h("span", { class: "v-last" }, fmtUnit(last, R.unit)),
      h("span", { class: "muted" }, R.labels[i1]),
      h("span", {}, "區間 ", change),
      h("span", {}, "高 ", h("b", { class: "mono" }, fmtUnit(R.values[hiI], R.unit)), h("span", { class: "muted" }, ` ${R.labels[hiI]}`)),
      h("span", {}, "低 ", h("b", { class: "mono" }, fmtUnit(R.values[loI], R.unit)), h("span", { class: "muted" }, ` ${R.labels[loI]}`))));
    rows.push(h("p", { class: "note", style: "margin:0" }, `資料：${R.src}`));
    ctl.replaceChildren(...rows);

    if (table) {
      const tr = [];
      for (let i = i1; i >= i0 && tr.length < 400; i--) {
        const prev = i > 0 ? R.values[i - 1] : null;
        const d = prev == null ? null : rate ? (R.values[i] - prev) * 100 : (R.values[i] / prev - 1) * 100;
        tr.push(h("tr", {}, h("td", { class: "n" }, R.labels[i]), h("td", { class: "n" }, fmtUnit(R.values[i], R.unit)),
          h("td", { class: "n" }, d == null ? "—" : chg(d, rate ? 1 : 2, rate ? "bp" : "%"))));
      }
      tbl.replaceChildren(h("table", { class: "data" },
        h("thead", {}, h("tr", {}, h("th", {}, RES_LABEL[res] + "期"), h("th", { class: "n" }, "收盤"), h("th", { class: "n" }, `較前一${RES_LABEL[res]}`))),
        h("tbody", {}, tr)));
      return;
    }
    lineChart(host, {
      series: [{ key: pick, name: ins.name, color, values: R.values, fmt: (v) => fmtUnit(v, R.unit) }],
      xs: R.xs, labels: R.labels, start: i0, log: useLog, area: true, height: 280, direct: false,
      label: `${ins.name} ${RES_LABEL[res]}線`, tipFmt: (r) => fmtUnit(r.raw, R.unit),
    });
  }
  return { ctl, render, setPick(k) { pick = k; save(); } };
}

/* 標準圖表卡：比較模式（圖例＋折線）與單一標的模式（日／週／月／年線） */
function chartCard(o) {
  const series = o.series.filter((s) => s.values && s.values.some(fin));
  const c = card({ title: o.title, sub: o.sub, span: o.span, note: o.note });
  const host = h("div", { class: "chart" });
  const tbl = h("div", { class: "tbl-wrap" });
  tbl.hidden = true;
  let useLog = store.get("log:" + o.key, o.log ?? false);
  let table = false;
  const lg = series.length > 1 ? legend(series, o.key, () => draw()) : null;
  const viewable = () => series.filter((s) => instrument(s.key));
  const eng = o.single !== false && viewable().length ? singleEngine(o.key, viewable, () => draw()) : null;
  let single = !!eng && store.get("single:" + o.key, false);
  if (eng) c.tools.append(toolButton(series.length > 1 ? "單一標的" : "日／週／月／年", single, (v) => { single = v; store.set("single:" + o.key, v); draw(); }));
  if (o.logToggle) c.tools.append(toolButton("對數刻度", useLog, (v) => { useLog = v; store.set("log:" + o.key, v); draw(); }));
  c.tools.append(toolButton("表格", false, (v) => { table = v; host.hidden = v; tbl.hidden = !v; draw(); }));
  function draw() {
    if (lg) lg.el.hidden = single;
    if (eng) eng.ctl.hidden = !single;
    if (single) { eng.render(host, tbl, table, useLog); return; }
    const start = o.fixedStart ?? rangeStart();
    if (table) {
      const vis = series.filter((s) => !(lg && lg.hid.has(s.key)));
      tbl.replaceChildren(seriesTable(vis, start, o.mode));
      return;
    }
    lineChart(host, Object.assign({}, o, { series, start, log: useLog, hidden: lg ? lg.hid : null, label: o.title }));
  }
  if (lg) c.body.append(lg.el);
  if (eng) c.body.append(eng.ctl);
  c.body.append(host, tbl);
  mount(host, draw);
  return c.el;
}

/* ── 走勢小圖 ── */
function sparkline(values, { w = 160, h: hh = 26, color = "var(--accent)" } = {}) {
  const pts = values.map((v, i) => [i, v]).filter((p) => fin(p[1]));
  const svg = sv("svg", { viewBox: `0 0 ${w} ${hh}`, preserveAspectRatio: "none", "aria-hidden": "true" });
  if (pts.length < 2) return svg;
  const lo = Math.min(...pts.map((p) => p[1])), hi = Math.max(...pts.map((p) => p[1]));
  const n = values.length - 1 || 1;
  const X = (i) => 1 + (i / n) * (w - 4), Y = (v) => 2 + (1 - (v - lo) / (hi - lo || 1)) * (hh - 4);
  const d = pts.map((p, k) => `${k ? "L" : "M"}${X(p[0]).toFixed(1)},${Y(p[1]).toFixed(1)}`).join("");
  svg.append(sv("path", { d: `${d}L${X(pts[pts.length - 1][0])},${hh}L${X(pts[0][0])},${hh}Z`, style: `fill:color-mix(in srgb, ${color} 13%, transparent)` }));
  svg.append(sv("path", { d, style: `fill:none;stroke:${color};stroke-width:1.5;vector-effect:non-scaling-stroke` }));
  return svg;
}

/* ── KPI 磚 ── */
/* 大數字一律是「最新已收盤價＋日漲跌」，和鉅亨每日頁同一份數字；研究用月資料只用來算 30 年位階。
   研究序列 → 每日報價代碼（沒列到的改用單一標的日線，再沒有才退回月資料並明講是月資料）。 */
const KPI_QUOTE = {
  fx_dxy: "GI:DXY:INDEX", fx_usdtwd: "FX:USDTWD:FOREX", fx_usdjpy: "FX:USDJPY:FOREX", fx_usdcny: "FX:USDCNY:FOREX",
  fx_eurusd: "FX:EURUSD:FOREX", b_us3m: "^IRX", b_us5y: "^FVX", b_us10y: "^TNX", b_us30y: "^TYX", b_jp10y: "JGB10Y",
  b_lqd: "LQD", b_hyg: "HYG", eq_spx: "GI:INX:INDEX", eq_dji: "GI:DJI:INDEX", eq_sox: "GI:SOX:INDEX", eq_hsi: "GI:HSI:INDEX",
  eq_twii: "TWS:TSE01:INDEX", eq_sse: "GI:SSEC:INDEX", c_gold: "GC=F", c_silver: "SI=F", c_copper: "HG=F", c_brent: "BZ=F",
  c_wti: "CL=F", c_natgas: "NG=F", c_maize: "ZC=F", c_soy: "ZS=F", v_vix: "^VIX",
};
const LATEST_QUOTES = Object.fromEntries((((GFD.daily || [])[0]) || { quotes: [] }).quotes.map((q) => [q.symbol, q]));

function latestClose(sid) {
  const D = (GFD.detail || {})[sid];
  const q = LATEST_QUOTES[KPI_QUOTE[sid]];
  const unit = D ? D.unit : (A.series[sid] || {}).unit;
  if (q) return { value: q.close, date: q.asof, dayChg: q.chg, rate: q.unit === "bp", unit, note: q.note, src: q.source };
  if (D && D.d && D.d[1].length >= 2) {
    const [t, v] = D.d;
    const n = v.length - 1;
    const rate = unit === "%" || unit === "個百分點";
    return { value: v[n], date: new Date(t[n] * 86400000).toISOString().slice(0, 10),
      dayChg: rate ? (v[n] - v[n - 1]) * 100 : (v[n] / v[n - 1] - 1) * 100, rate, unit, src: D.src };
  }
  return null;
}
function yearChange(sid, L) {
  const D = (GFD.detail || {})[sid];
  if (!D || !D.w) return null;
  const [t, v] = D.w;
  const target = Math.round(Date.parse(L.date) / 86400000) - 365;
  let j = -1;
  for (let i = 0; i < t.length; i++) if (t[i] <= target) j = i;
  if (j < 0 || !fin(v[j]) || v[j] === 0) return null;
  return L.rate ? (L.value - v[j]) * 100 : (L.value / v[j] - 1) * 100;
}

function kpi(sid, name) {
  const s = A.series[sid];
  if (!s || !s.stats) return h("div", { class: "kpi" }, h("div", { class: "k-name" }, name || sid), h("div", { class: "k-val muted" }, "—"));
  const st = s.stats;
  const pct = `30 年位階 ${fin(st.pct) ? st.pct.toFixed(0) : "—"}%`;
  const L = latestClose(sid);
  if (!L) {  // 沒有日資料來源（例：央行重貼現率）：明講是月資料
    const isY = s.kind === "yield";
    const unit = isY ? "%" : ["點", "指數", "比值"].includes(s.unit) ? "" : s.unit;
    const d = (v) => (isY ? chg(v, 0, "bp") : chg(v, 1, "%"));
    return h("div", { class: "kpi" },
      h("div", { class: "k-name", title: s.note }, name || s.name),
      h("div", { class: "k-val" }, isY ? fmtNum(st.value, 2) : fmtNum(st.value), unit ? h("span", { class: "k-unit" }, unit) : null),
      h("div", { class: "k-d" }, h("span", {}, h("span", { class: "muted" }, "1月 "), d(st.c1)), h("span", {}, h("span", { class: "muted" }, "12月 "), d(st.c12))),
      sparkline(s.values.slice(-37), { color: "var(--accent)" }),
      h("div", { class: "k-asof" }, `${st.last} 月資料・${pct}`));
  }
  const D = (GFD.detail || {})[sid];
  const rate = L.rate || L.unit === "%" || L.unit === "個百分點";
  const valText = L.unit === "%" ? fmtNum(L.value, 3) : L.unit === "個百分點" ? fmtSigned(L.value, 2) : fmtNum(L.value);
  const unitText = ["點", "指數", "比值", "2010=100"].includes(L.unit) ? "" : L.unit;
  const yc = yearChange(sid, L);
  return h("div", { class: "kpi" },
    h("div", { class: "k-name", title: `${s.note}；最新收盤來源：${L.src}` }, name || s.name),
    h("div", { class: "k-val" }, valText, unitText ? h("span", { class: "k-unit" }, unitText) : null),
    h("div", { class: "k-d" },
      h("span", {}, h("span", { class: "muted" }, "日 "), rate ? chg(L.dayChg, 1, "bp") : chg(L.dayChg, 2, "%")),
      h("span", {}, h("span", { class: "muted" }, "12月 "), fin(yc) ? (rate ? chg(yc, 0, "bp") : chg(yc, 1, "%")) : (rate ? chg(st.c12, 0, "bp") : chg(st.c12, 1, "%")))),
    sparkline(D && D.d ? D.d[1].slice(-120) : s.values.slice(-37), { color: "var(--accent)" }),
    h("div", { class: "k-asof" }, `${L.date.slice(5)} 收盤${L.note ? "・" + L.note : ""}・${pct}`));
}
function kpiRow(items) { return h("div", { class: "kpis span-12" }, items.filter(([sid]) => A.series[sid]).map(([sid, name]) => kpi(sid, name))); }

/* ── 中心對稱橫條 ── */
function divBars(rows, { suffix = "%", digits = 1 } = {}) {
  const max = Math.max(1, ...rows.map((r) => Math.abs(r.v || 0)));
  return h("div", { class: "bars" }, rows.map((r) => {
    const pct = fin(r.v) ? (Math.abs(r.v) / max) * 50 : 0;
    return h("div", { class: "bar-row" },
      h("span", {}, r.label),
      h("div", { class: "bar-track", role: "img", "aria-label": `${r.label} ${fmtSigned(r.v, digits, suffix)}` },
        fin(r.v) ? h("div", { class: `bar-fill ${r.v >= 0 ? "pos" : "neg"}`, style: `width:${pct}%` }) : null),
      h("span", { class: `n ${dirClass(r.v)}` }, fin(r.v) ? `${arrow(r.v)}${fmtSigned(r.v, digits, suffix)}` : "—"));
  }));
}

/* ── 關聯熱圖 ── */
function corrFill(r) {
  if (!fin(r)) return "var(--surface-2)";
  const p = Math.round(Math.min(1, Math.abs(r)) ** 0.8 * 100);
  return `color-mix(in oklab, ${r >= 0 ? "var(--div-pos)" : "var(--div-neg)"} ${p}%, var(--div-mid))`;
}
function heatmap(host, o) {
  const n = o.ids.length;
  const W = host.clientWidth || 800;
  const labW = 128;
  const cell = Math.max(20, Math.min(34, Math.floor((W - labW - 8) / n)));
  const topH = 104;
  const Wt = labW + n * cell + 6, Ht = topH + n * cell + 4;
  const svg = sv("svg", { viewBox: `0 0 ${Wt} ${Ht}`, width: Wt, height: Ht, role: "img", "aria-label": o.label || "關聯熱圖" });
  svg.style.width = Wt + "px";
  o.names.forEach((name, i) => {
    svg.append(sv("text", { x: labW - 8, y: topH + i * cell + cell / 2 + 4, "text-anchor": "end" }, name));
    const cx = labW + i * cell + cell / 2;
    svg.append(sv("text", { x: 0, y: 0, transform: `translate(${cx + 4},${topH - 8}) rotate(-55)` }, name));
  });
  for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) {
    const r = o.matrix[i][j];
    svg.append(sv("rect", { x: labW + j * cell + 1, y: topH + i * cell + 1, width: cell - 2, height: cell - 2, rx: 2, style: `fill:${corrFill(r)}` }));
    if (i !== j && fin(r) && Math.abs(r) >= 0.5 && cell >= 26) {
      svg.append(sv("text", { x: labW + j * cell + cell / 2, y: topH + i * cell + cell / 2 + 4, "text-anchor": "middle",
        style: `font:500 10px var(--f-mono);fill:${Math.abs(r) >= 0.65 ? "#fff" : "var(--ink)"}` }, r.toFixed(2).replace("0.", ".")));
    }
  }
  const mark = sv("rect", { width: cell, height: cell, rx: 3, style: "fill:none;stroke:var(--ink);stroke-width:1.5", visibility: "hidden" });
  const hit = sv("rect", { x: labW, y: topH, width: n * cell, height: n * cell, class: "hit", tabindex: 0, "aria-label": "關聯熱圖：用方向鍵移動格子" });
  svg.append(mark, hit);
  let ci = 0, cj = 1;
  function tipFor(i, j) {
    mark.setAttribute("x", labW + j * cell); mark.setAttribute("y", topH + i * cell); mark.setAttribute("visibility", "visible");
    return o.tip(i, j);
  }
  hit.addEventListener("pointermove", (e) => {
    const b = svg.getBoundingClientRect();
    const j = Math.floor(((e.clientX - b.left) * (Wt / b.width) - labW) / cell), i = Math.floor(((e.clientY - b.top) * (Ht / b.height) - topH) / cell);
    if (i < 0 || j < 0 || i >= n || j >= n) return;
    ci = i; cj = j;
    showTip(tipFor(i, j), e.clientX, e.clientY);
  });
  const clear = () => { mark.setAttribute("visibility", "hidden"); hideTip(); };
  hit.addEventListener("pointerleave", clear);
  hit.addEventListener("blur", clear);
  hit.addEventListener("keydown", (e) => {
    const mv = { ArrowLeft: [0, -1], ArrowRight: [0, 1], ArrowUp: [-1, 0], ArrowDown: [1, 0] }[e.key];
    if (!mv) return;
    e.preventDefault();
    ci = Math.max(0, Math.min(n - 1, ci + mv[0])); cj = Math.max(0, Math.min(n - 1, cj + mv[1]));
    const b = svg.getBoundingClientRect();
    showTip(tipFor(ci, cj), b.left + (labW + cj * cell + cell) * (b.width / Wt), b.top + (topH + ci * cell + cell) * (b.height / Ht));
  });
  host.replaceChildren(svg);
}

/* ── 領先落後柱狀圖 ── */
function lagChart(host, p) {
  const W = Math.max(260, host.clientWidth || 400), H = 170;
  const ml = 34, mr = 8, mt = 8, mb = 38, pw = W - ml - mr, ph = H - mt - mb;
  const vals = p.leadlag;
  const m = Math.max(0.3, p.sig || 0, ...vals.map((v) => Math.abs(v.r || 0))) * 1.15;
  const X = (k) => ml + ((k + 6.5) / 13) * pw, Y = (r) => mt + (1 - (r + m) / (2 * m)) * ph;
  const svg = sv("svg", { viewBox: `0 0 ${W} ${H}`, height: H, role: "img", "aria-label": `${p.label} 領先落後相關` });
  for (const t of [-m, 0, m].map((x) => +x.toFixed(2))) {
    svg.append(sv("line", { x1: ml, x2: ml + pw, y1: Y(t), y2: Y(t), style: `stroke:${t === 0 ? "var(--line-strong)" : "var(--grid)"}` }));
    svg.append(sv("text", { x: ml - 6, y: Y(t) + 3.5, "text-anchor": "end" }, t.toFixed(2)));
  }
  if (p.sig) for (const s of [p.sig, -p.sig]) svg.append(sv("line", { x1: ml, x2: ml + pw, y1: Y(s), y2: Y(s), style: "stroke:var(--warn);stroke-width:1;opacity:.8" }));
  const bw = Math.max(6, (pw / 13) * 0.56);
  for (const v of vals) {
    if (!fin(v.r)) continue;
    const y = Y(Math.max(0, v.r)), hgt = Math.abs(Y(v.r) - Y(0));
    const rect = sv("rect", { x: X(v.k) - bw / 2, y, width: bw, height: Math.max(1, hgt), rx: 2, style: `fill:${v.r >= 0 ? "var(--div-pos)" : "var(--div-neg)"}` });
    svg.append(rect);
    svg.append(sv("text", { x: X(v.k), y: H - mb + 14, "text-anchor": "middle" }, String(v.k)));
    const hitR = sv("rect", { x: X(v.k) - pw / 26, y: mt, width: pw / 13, height: ph, class: "hit" });
    hitR.addEventListener("pointermove", (e) => showTip(`<div class="tip-h">k = ${v.k}</div>`
      + `<div>r = <b class="mono">${fmtSigned(v.r, 2)}</b>　n = ${v.n}</div>`
      + `<div class="tip-note">${v.k === 0 ? "同月" : v.k > 0 ? `${esc(A.series[p.a].name)} 領先 ${v.k} 個月` : `${esc(A.series[p.b].name)} 領先 ${-v.k} 個月`}</div>`, e.clientX, e.clientY));
    hitR.addEventListener("pointerleave", hideTip);
    svg.append(hitR);
  }
  svg.append(sv("text", { x: ml, y: H - 4, class: "lbl", style: "font-size:11px" }, `← ${A.series[p.b].name} 領先`));
  svg.append(sv("text", { x: ml + pw, y: H - 4, class: "lbl", "text-anchor": "end", style: "font-size:11px" }, `${A.series[p.a].name} 領先 →`));
  host.replaceChildren(svg);
}

/* ── 分頁頭 ── */
function tabHead(title, desc, withRange, onRange) {
  return h("div", { class: "tab-head" },
    h("div", {}, h("h2", {}, title), desc ? h("p", {}, desc) : null),
    withRange ? rangeChips(onRange) : null);
}
function findingsList(tab) {
  const items = (A.findings || []).filter((f) => !tab || f.tab === tab);
  if (!items.length) return null;
  const toneLabel = { up: "偏多", down: "偏空", alert: "注意", neutral: "觀察" };
  return h("ul", { class: "finds" }, items.map((f) => h("li", { class: `t-${f.tone}` },
    h("b", {}, f.title, " ", h("span", { class: `pill pill-${f.tone === "alert" ? "warn" : f.tone === "up" ? "up" : f.tone === "down" ? "down" : "neutral"}` }, toneLabel[f.tone] || "")),
    h("span", {}, f.text))));
}
