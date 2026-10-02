/* 沙盤推演的「事件衝擊」檢視（真實事件 → 兩週／一個月／兩個月的逐層傳導）；2026-10-02 前是獨立分頁 */

function csUnit(v, unit, d) {
  if (!fin(v)) return "—";
  return fmtSigned(v, d ?? (unit === "bp" ? 0 : unit === "pt" ? 1 : 1), unit === "%" ? "%" : unit === "bp" ? "bp" : " pt");
}
const csLayerName = (id) => (A.cascade.layers.find((l) => l.id === id) || {}).name || id;
const CS_WIN = { 10: "兩週", 21: "一個月", 42: "兩個月", 126: "半年", 252: "一年" };
const csWin = (w) => CS_WIN[w] || `${w} 日`;
const csPersist = (k) => (A.cascade.persist_labels || {})[k] || k;
/* 隨機日期的持續性分布：沒有事件也會有不少標的被判成「一年以上」（長期漂移＋長視窗波動較大） */
function persistBaseNote() {
  const B = A.cascade.persist_base;
  if (!B || !B.pct) return null;
  return h("span", { class: "muted" }, `對照：隨機挑 ${B.n_dates} 個日期當假事件，有反應的標的中 短暫 ${B.pct.transient}%、長期 ${B.pct.persistent}%、一年以上 ${B.pct.lasting}%。`
    + "真實事件要比這個高才算特別持久。");
}
/* 持續性分布：短暫／長期／一年以上 的小橫條（有反應的標的數） */
function persistBar(dist, n) {
  const keys = ["transient", "persistent", "lasting", "unknown"];
  const total = keys.reduce((s, k) => s + (dist[k] || 0), 0);
  if (!total) return h("span", { class: "muted" }, "沒有標的出現實質反應");
  return h("div", { class: "pbar" }, keys.filter((k) => dist[k]).map((k) =>
    h("div", { class: `pbar-seg pb-${k}`, style: `flex:${dist[k]}`, title: `${csPersist(k)} ${dist[k]}` },
      `${csPersist(k)} ${dist[k]}`)));
}

/* 傳導時間軸：每個有反應的標的，點在「走完一半」的那一天 */
function cascadeTimeline(host, rows, maxDays) {
  const items = rows.filter((r) => fin(r.half_day));
  if (!items.length) { host.replaceChildren(h("p", { class: "empty" }, "這次事件沒有標的出現實質反應")); return; }
  const W = Math.max(320, host.clientWidth || 600);
  const ml = 132, mr = 56, mt = 26, rowH = 20;
  const layers = A.cascade.layers.filter((l) => items.some((r) => r.layer === l.id));
  const H = mt + layers.reduce((n, l) => n + items.filter((r) => r.layer === l.id).length, 0) * rowH + layers.length * 16 + 14;
  const pw = W - ml - mr;
  const X = (d) => ml + ((d - 1) / Math.max(1, maxDays - 1)) * pw;
  const svg = sv("svg", { viewBox: `0 0 ${W} ${H}`, height: H, role: "img", "aria-label": "事件後傳導時間軸" });
  // 刻度彼此至少隔 44px，窄螢幕上自動略過擠在一起的（例：手機上「第 5 天」和「2 週」會疊在一起）
  let lastX = -Infinity;
  for (const d of [1, 5, 10, 21, 42].filter((d) => d <= maxDays)) {
    if (X(d) - lastX < 44 && d !== maxDays) continue;
    lastX = X(d);
    svg.append(sv("line", { x1: X(d), x2: X(d), y1: mt - 8, y2: H - 12, style: "stroke:var(--grid)" }));
    svg.append(sv("text", { x: X(d), y: mt - 12, "text-anchor": "middle" },
      d === 10 ? "2 週" : d === 21 ? "1 個月" : d === 42 ? "2 個月" : `第 ${d} 天`));
  }
  let y = mt + 8;
  for (const l of layers) {
    svg.append(sv("text", { x: 0, y: y + 4, class: "lbl", style: "font-weight:600" }, l.name));
    y += 16;
    for (const r of items.filter((x) => x.layer === l.id).sort((a, b) => a.half_day - b.half_day)) {
      const v = fin(r.peak_move) ? r.peak_move : (r.w21 || 0);
      const color = v >= 0 ? "var(--up)" : "var(--down)";
      svg.append(sv("text", { x: ml - 10, y: y + 4, "text-anchor": "end", class: "lbl" }, r.name));
      svg.append(sv("line", { x1: ml, x2: ml + pw, y1: y, y2: y, style: "stroke:var(--grid)" }));
      const cx = X(r.half_day);
      svg.append(sv("circle", { cx, cy: y, r: Math.min(9, 3.5 + Math.abs(v) / 6), style: `fill:${color};opacity:.85` }));
      const t = sv("text", { x: ml + pw + 6, y: y + 4, class: "lbl", style: `fill:${color}` }, csUnit(v, r.unit));
      svg.append(t);
      const hit = sv("rect", { x: ml, y: y - rowH / 2, width: pw, height: rowH, class: "hit" });
      hit.addEventListener("pointermove", (e) => showTip(
        `<div class="tip-h">${esc(r.name)}　${esc(csLayerName(r.layer))}</div>`
        + `<div>走完一半：第 <b>${r.half_day}</b> 天${fin(r.peak_day) ? `，最大反應第 ${r.peak_day} 天 <b>${csUnit(r.peak_move, r.unit)}</b>` : ""}</div>`
        + `<div>兩週 <b>${csUnit(r.w10, r.unit)}</b>　一個月 <b>${csUnit(r.w21, r.unit)}</b>　兩個月 <b>${csUnit(r.w42, r.unit)}</b></div>`
        + (fin(r.pre) ? `<div class="tip-note">事件前 10 天已經走了 ${csUnit(r.pre, r.unit)}</div>` : ""), e.clientX, e.clientY));
      hit.addEventListener("pointerleave", hideTip);
      svg.append(hit);
      y += rowH;
    }
  }
  host.replaceChildren(svg);
}

function cascadeTable(rows, isCat) {
  const head = (isCat
    ? ["標的", "傳導速度（半程）", "有反應次數", "事件前 10 天"]
    : ["標的", "傳導速度（半程）", "最大反應", "事件前 10 天"]).concat(A.cascade.windows.map(csWin), isCat ? [] : ["持續性"]);
  const body = [];
  for (const l of A.cascade.layers) {
    const inLayer = rows.filter((r) => r.layer === l.id);
    if (!inLayer.length) continue;
    body.push(h("tr", {}, h("td", { colspan: head.length, style: "background:var(--surface-2);font-weight:600" }, h("span", { class: "grp-name" }, l.name))));
    for (const r of inLayer) {
      body.push(h("tr", {},
        h("td", {}, r.name, !fin(r.half_day) ? h("span", { class: "sub" }, "無實質反應") : null,
          r.proxy ? h("span", { class: "sub" }, `代理：${r.proxy}`) : null),
        h("td", { class: "n" }, fin(r.half_day) ? `第 ${r.half_day} 天` : "—"),
        isCat
          ? h("td", { class: "n" }, `${r.half_n}/${r.n}`, h("span", { class: "sub" }, fin(r.resp_rate) ? `${r.resp_rate}%` : ""))
          : h("td", { class: "n" }, fin(r.peak_move) ? h("span", { class: dirClass(r.peak_move) }, csUnit(r.peak_move, r.unit)) : "—",
            fin(r.peak_day) ? h("span", { class: "sub" }, `第 ${r.peak_day} 天`) : null),
        h("td", { class: "n muted" }, csUnit(r.pre, r.unit)),
        ...A.cascade.windows.map((w) => h("td", { class: "n" },
          h("span", { class: dirClass(r[`w${w}`]) }, csUnit(r[`w${w}`], r.unit)),
          isCat && fin(r[`p${w}`]) && r[`p${w}`] <= 0.05 ? h("b", { class: "cs-sig", "aria-label": "p≤0.05" }, " ●") : null,
          isCat && fin(r[`agree${w}`]) ? h("span", { class: "sub" }, `同向 ${r[`agree${w}`]}%｜平常 ${csUnit(r[`base${w}`], r.unit)}`) : null)),
        isCat ? null : h("td", { class: "n" }, r.responded ? h("span", { class: `pb-tag pb-${r.persist}` }, csPersist(r.persist)) : h("span", { class: "muted" }, "—"),
          r.still_growing ? h("span", { class: "sub" }, "半年後比兩個月的峰值更大") : null)));
    }
  }
  return h("div", { class: "tbl-wrap" }, h("table", { class: "data" },
    h("thead", {}, h("tr", {}, head.map((t, i) => h("th", { class: i ? "n" : null }, t)))), h("tbody", {}, body)));
}

/* 累積路徑：反應最大的幾個標的，事件後 42 個交易日怎麼走 */
function cascadePaths(host, assets) {
  const pick = assets.filter((a) => a.responded && a.unit === "%")
    .sort((a, b) => Math.abs(b.peak_move) - Math.abs(a.peak_move)).slice(0, 4);  // 最多 4 條，名稱才標得進去
  if (!pick.length) { host.replaceChildren(h("p", { class: "empty" }, "沒有足夠的反應可畫路徑")); return; }
  const days = A.cascade.max_days;
  lineChart(host, {
    xs: Array.from({ length: days }, (_, i) => i + 1),
    labels: Array.from({ length: days }, (_, i) => `第 ${i + 1} 個交易日`),
    series: pick.map((a, i) => ({ key: a.id, name: a.name, color: `var(--s${i + 1})`, values: a.path,
      fmt: (v) => csUnit(v, a.unit) })),
    start: 0, height: 260, refs: [{ y: 0 }], label: "事件後累積變動", direct: true,
  });
}

/* 類型比較：不同類型的事件，錢往哪裡流。列＝事件類型，欄＝各層代表標的。
   顏色看「超額」＝事件後中位數減該標的平常同樣天數的中位數；只有二項檢定 p≤0.10 的格子上色 */
const csP = (p) => (fin(p) ? (p < 0.001 ? "p<0.001" : `p=${p.toFixed(3)}`) : "");
function cascadeCompare(win) {
  const CA = A.cascade;
  const cols = CA.compare.map((id) => CA.universe.find((u) => u.id === id)).filter(Boolean);
  const cell = (cat, id) => cat.assets.find((x) => x.id === id);
  // 每欄各自縮放顏色：% / bp / 點數不能放在同一把尺上
  const scale = {};
  for (const c of cols) {
    const vs = CA.categories.map((cat) => (cell(cat, c.id) || {})[`excess${win}`]).filter(fin).map(Math.abs);
    scale[c.id] = Math.max(1e-9, ...vs);
  }
  const rows = CA.categories.map((cat) => h("tr", {},
    h("th", { scope: "row", style: "text-align:left;white-space:nowrap" }, cat.name,
      h("span", { class: "sub" }, `${cat.n} 次｜${cat.first.slice(0, 4)}–${cat.last.slice(0, 4)}`)),
    ...cols.map((c) => {
      const x = cell(cat, c.id);
      const v = x ? x[`w${win}`] : null;
      if (!fin(v)) return h("td", { class: "n muted" }, "—");
      const ex = x[`excess${win}`], p = x[`p${win}`];
      const k = fin(p) && p <= 0.10 ? Math.round(18 + Math.min(1, Math.abs(ex) / scale[c.id]) * (p <= 0.05 ? 45 : 22)) : 0;
      const tone = ex >= 0 ? "var(--up)" : "var(--down)";
      return h("td", { class: "n", style: k ? `background:color-mix(in srgb, ${tone} ${k}%, transparent)` : null,
        title: `${cat.name} → ${c.name}：事件後中位數 ${csUnit(v, x.unit)}（平常 ${csUnit(x[`base${win}`], x.unit)}），`
          + `${x.n} 次中上漲 ${x[`up${win}`]}%（平常 ${x[`base_up${win}`]}%），${csP(p)}` },
        csUnit(v, x.unit), fin(p) && p <= 0.05 ? h("b", { class: "cs-sig", "aria-label": "p≤0.05" }, " ●") : null,
        h("span", { class: "sub" }, `平常 ${csUnit(x[`base${win}`], x.unit)}｜${x.n} 次`));
    })));
  const table = h("div", { class: "tbl-wrap" }, h("table", { class: "data" },
    h("thead", {}, h("tr", {}, h("th", {}, "事件類型"), ...cols.map((c) => h("th", { class: "n" }, c.name)))),
    h("tbody", {}, rows)));

  // 錢往哪流：超額方向與事件後中位數同向、且上漲比例和平常的差異 p≤0.10，依超額大小各取三個
  const flows = CA.categories.map((cat) => {
    const ok = cat.assets.filter((x) => x.n >= 3 && fin(x[`excess${win}`]) && fin(x[`p${win}`]) && x[`p${win}`] <= 0.10
      && Math.sign(x[`excess${win}`]) === Math.sign(x[`w${win}`]));
    const up = ok.filter((x) => x[`excess${win}`] > 0).sort((a, b) => b[`excess${win}`] / scaleOf(b) - a[`excess${win}`] / scaleOf(a)).slice(0, 3);
    const dn = ok.filter((x) => x[`excess${win}`] < 0).sort((a, b) => a[`excess${win}`] / scaleOf(a) - b[`excess${win}`] / scaleOf(b)).slice(0, 3);
    const fmt = (x) => h("span", { class: "flow-item" }, x.name, " ",
      h("b", { class: dirClass(x[`w${win}`]) }, csUnit(x[`w${win}`], x.unit)),
      h("span", { class: "muted" }, `（平常 ${csUnit(x[`base${win}`], x.unit)}；${x.n} 次、${csP(x[`p${win}`])}）`),
      x[`p${win}`] <= 0.05 ? h("b", { class: "cs-sig" }, " ●") : null);
    const list = (xs) => xs.length ? xs.flatMap((x, i) => (i ? ["、", fmt(x)] : [fmt(x)])) : [h("span", { class: "muted" }, "沒有和平常明顯不同的標的")];
    return h("tr", {}, h("th", { scope: "row", style: "text-align:left;white-space:nowrap" }, cat.name),
      h("td", {}, ...list(up)), h("td", {}, ...list(dn)));
  });
  const flowTable = h("div", { class: "tbl-wrap" }, h("table", { class: "data" },
    h("thead", {}, h("tr", {}, h("th", {}, "事件類型"), h("th", {}, "錢流入（比平常漲得多）"), h("th", {}, "錢流出（比平常跌得多）"))),
    h("tbody", {}, flows)));
  const st = CA.stats;
  const warn = h("p", { class: "cs-warn" },
    `多重檢定：${st.tests.toLocaleString()} 格比較中有 ${st.p05} 格 p≤0.05（標 ●）；但把每個事件日隨機移到前後三年內重跑 ${st.null05.length} 次，`
    + `假事件平均也有 ${st.null05_mean} 格過關——估計約 ${st.fdr05}% 的 ● 是運氣。次數多（≥ 8 次）且 p 很小的格子比較可信；`
    + "只有 4～5 次的類型，即使全部同方向也可能是巧合。");
  return [warn, table, h("h4", { class: "sub-h" }, "錢往哪流：比平常漲得多／跌得多的標的（至少 3 次、p≤0.10，依超額相對該欄的大小排序）"), flowTable];
}
// 不同單位的超額要排在一起比較時，以該標的「平常」變動幅度的尺度做粗略標準化（至少 1）
function scaleOf(x) { return x.unit === "%" ? 1 : x.unit === "bp" ? 10 : 2; }

/* 現在像哪次：今天的市場狀態 vs 88 個事件發生時的狀態，最像的 5 次，見報之後錢往哪流 */
const csFmtFeat = (v, unit) => (!fin(v) ? "—" : unit === "σ" ? fmtSigned(v, 1, "σ") : unit === "pp" ? `${v.toFixed(2)}`
  : unit === "bp" ? fmtSigned(v, 0, "bp") : fmtSigned(v, 1, "%"));
function cascadeNow(win) {
  const AN = A.cascade.analogs;
  if (!AN) return [h("p", { class: "empty" }, "尚未產生相似事件分析")];
  const bt = AN.backtest, wl = csWin;
  const cells = (m) => AN.windows.map((w) => `${wl(w)} ${bt[m][w].hit}%`).join("、");
  const verdict = h("div", { class: "cs-warn" },
    h("b", {}, "先講結論：相似的歷史不能拿來預測接下來。"),
    ` 回測方法：對每個歷史事件假裝不知道結果，用「狀態最像的 ${AN.k} 次其他事件」預測它事後比平常漲多還跌多。`
    + `命中率 ${cells("analog")}；隨機挑 ${AN.k} 次事件 ${cells("random")}`
    + `（隨機 300 輪的 90% 區間 ${AN.windows.map((w) => `${bt.random[w].p5}–${bt.random[w].p95}%`).join("、")}）；`
    + `用同類型事件預測 ${cells("category")}。`
    + `隨機 300 輪中，命中率不輸相似事件法的輪次占 ${AN.windows.map((w) => `${wl(w)} ${Math.round(100 * bt.analog[w].p_vs_random)}%`).join("、")}`
    + "（要低於 5% 才能說相似事件法比運氣好）。"
    + "所以下面只是「歷史上狀態像現在的時候，事後發生過什麼」的對照，不是買賣訊號。");

  // 狀態比較
  const an = AN.analogs;
  const fhead = h("tr", {}, h("th", {}, "狀態"), h("th", { class: "n" }, `現在（${AN.today}）`),
    ...an.map((a) => h("th", { class: "n" }, `${a.date.slice(0, 7)}`, h("span", { class: "sub" }, a.name))));
  const frows = AN.features.map((f) => {
    const v = AN.now[f.id], p = AN.pct[f.id];
    const extreme = fin(p) && (p <= 10 || p >= 90);
    return h("tr", {}, h("th", { scope: "row", style: "text-align:left;white-space:nowrap" }, f.label),
      h("td", { class: "n", style: extreme ? "background:var(--warn-soft)" : null },
        csFmtFeat(v, f.unit), fin(p) ? h("span", { class: "sub" }, `歷史第 ${p} 百分位`) : h("span", { class: "sub" }, "今天無資料")),
      ...an.map((a) => h("td", { class: "n" }, csFmtFeat(a.state[f.id], f.unit))));
  });
  const ftable = h("div", { class: "tbl-wrap" }, h("table", { class: "data" }, h("thead", {}, fhead), h("tbody", {}, frows)));

  // 見報之後的結果
  const ohead = h("tr", {}, h("th", {}, "標的"),
    ...an.map((a) => h("th", { class: "n" }, a.date.slice(0, 7), h("span", { class: "sub" }, `距離 ${a.dist}`))),
    h("th", { class: "n" }, "中位數"), h("th", { class: "n" }, "平常"));
  const orows = AN.assets.map((r) => h("tr", {}, h("th", { scope: "row", style: "text-align:left;white-space:nowrap" }, r.name),
    ...r[`w${win}`].map((v) => h("td", { class: "n" }, h("span", { class: dirClass(v) }, csUnit(v, r.unit)))),
    h("td", { class: "n" }, h("b", { class: dirClass(r[`med${win}`]) }, csUnit(r[`med${win}`], r.unit)),
      fin(r[`up${win}`]) ? h("span", { class: "sub" }, `${r[`n${win}`]} 次中上漲 ${r[`up${win}`]}%`) : null),
    h("td", { class: "n muted" }, csUnit(r[`base${win}`], r.unit))));
  const otable = h("div", { class: "tbl-wrap" }, h("table", { class: "data" }, h("thead", {}, ohead), h("tbody", {}, orows)));

  return [verdict,
    h("h4", { class: "sub-h" }, `狀態比較：把最新一個收盤（${AN.today}）當成「事件第一天」。黃底＝現在處於歷史前後 10% 的極端`), ftable,
    h("h4", { class: "sub-h" }, `這 ${an.length} 次事件「見報之後」${wl(win)}的變動（從事件第一天收盤起算，看到新聞才進場也做得到）`), otable,
    h("p", { class: "note" }, `最不像現在的事件：${AN.farthest.map((a) => `${a.date.slice(0, 7)} ${a.name}`).join("、")}。`
      + "距離＝各項狀態換成標準分數後的均方根差，越小越像；兩個狀態至少要有六成項目都有資料才比。"
      + `今天的資料：${Object.entries(AN.last_dates).map(([k, d]) => `${k} ${d}`).join("、")}（期貨與美元在台北早上還沒收盤，會停在前一個交易日）。`)];
}

/* 開頭結論：全部事件合起來的傳導節奏、持續性與可信度（由資料算，不寫死） */
function cascadeLead(CA) {
  const byLayer = {}, pc = { transient: 0, persistent: 0, lasting: 0 };
  for (const e of CA.events) for (const r of e.assets) {
    if (!r.responded) continue;
    if (fin(r.half_day)) (byLayer[r.layer] = byLayer[r.layer] || []).push(r.half_day);
    if (r.persist in pc) pc[r.persist]++;
  }
  const med = (a) => { const s = a.slice().sort((x, y) => x - y), m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
  const layers = CA.layers.filter((l) => byLayer[l.id]).map((l) => ({ name: l.name.split("：")[0], short: (l.name.split("：")[1] || l.name), d: Math.round(med(byLayer[l.id])) }));
  if (!layers.length) return null;
  const lo = Math.min(...layers.map((l) => l.d)), hi = Math.max(...layers.map((l) => l.d));
  let text = hi - lo <= 3
    ? `${CA.events.length} 個事件合起來看，各層「走完一半反應」的中位數都在第 ${lo}～${hi} 天，差距不大，誰先誰後要看個別事件。`
    : `${CA.events.length} 個事件合起來看，「走完一半反應」的中位數：${layers.map((l) => `${l.short}第 ${l.d} 天`).join("、")}。`;
  const tot = pc.transient + pc.persistent + pc.lasting;
  const B = CA.persist_base && CA.persist_base.pct;
  if (tot) text += `有反應的標的中 ${Math.round((pc.transient * 100) / tot)}% 半年後已退掉一半以上${B && fin(B.transient) ? `（隨機日期是 ${Math.round(B.transient)}%）` : ""}。`;
  if (CA.stats && fin(CA.stats.fdr05)) text += `統計上顯著的結果估計約 ${Math.round(CA.stats.fdr05)}% 是運氣，單一類型的結論只能當參考。`;
  return text;
}

TABS.cascade = lazyTab("cascade", (root) => {
  const CA = A.cascade;
  root.replaceChildren(tabHead("事件衝擊鏈：一個事件，兩週到兩個月內怎麼一層一層傳下去",
    "用日線做事件研究。事件是真的發生過的事（戰爭、央行轉向、匯率危機、崩盤、疫情、天災…），不是價格門檻。"
    + "傳導順序不是假設的，是量出來的：每個標的先判斷有沒有實質反應（期間內最大累積變動超過自身 2σ×√天數），"
    + "有反應的再算「走完一半」是第幾天。", false, null, CA && CA.events.length ? cascadeLead(CA) : null));
  if (!CA || !CA.events.length) { root.append(h("p", { class: "empty" }, "尚未產生事件衝擊分析，請執行 python3 gfd.py history 後再 analyze")); return; }
  const g = h("div", { class: "grid" });
  root.append(g);

  const catName = (id) => (CA.categories.find((c) => c.id === id) || {}).name || id;
  // 從其他分頁指定要打開的事件（名詞解釋的連結）：記憶體優先，用過即清
  const pending = window.csPending;
  window.csPending = null;
  let mode = pending ? pending.mode : store.get("csMode", "event");
  let sel = pending ? pending.sel : store.get("csSel", "ukraine22");
  let fcat = pending ? pending.cat : store.get("csCat", "all");
  let win = store.get("csWin", 21);
  const chips = h("div", { class: "chips" });
  const chips2 = h("div", { class: "chips", style: "margin-top:8px" });
  let evQ = "";       // 事件搜尋字（不記住：每次打開都從完整清單開始）
  const body = h("div", { class: "grid", style: "margin-top:16px" });
  const btn = (label, on, fn) => h("button", { class: "chip", type: "button", "aria-pressed": String(on), onclick: fn }, label);

  const draw = () => {
    const modeChips = [["event", "單一事件"], ["cat", "分類彙總"], ["compare", "類型比較"], ["now", "現在像哪次"]].map(([k, l]) =>
      btn(l, k === mode, () => { mode = k; store.set("csMode", k); draw(); }));
    chips2.replaceChildren();
    if (mode === "event") {
      if (fcat !== "all" && !CA.categories.some((c) => c.id === fcat)) fcat = "all";   // 存的分類已不存在
      const evs = CA.events.filter((e) => fcat === "all" || e.cat === fcat).slice().sort((a, b) => a.date.localeCompare(b.date));
      if (!evs.some((e) => e.id === sel)) sel = evs[0].id;
      chips.replaceChildren(...modeChips, h("span", { class: "lab", style: "margin-left:10px" }, "類型"),
        btn(`全部（${CA.events.length}）`, fcat === "all", () => { fcat = "all"; store.set("csCat", fcat); draw(); }),
        ...CA.categories.map((c) => btn(`${c.name}（${CA.events.filter((e) => e.cat === c.id).length}）`, fcat === c.id,
          () => { fcat = c.id; store.set("csCat", fcat); draw(); })));
      // 88 個事件的按鈕牆改成：搜尋框＋固定高度可捲動的清單，選中的捲到看得見的位置
      const list = h("div", { class: "ev-list" });
      const count = h("span", { class: "muted gl-count" });
      const fill = () => {
        const needle = evQ.trim().toLowerCase();
        const shown = evs.filter((e) => !needle || `${e.date} ${e.name} ${e.note || ""}`.toLowerCase().includes(needle));
        count.textContent = `${shown.length} / ${evs.length}`;
        list.replaceChildren(...(shown.length ? shown.map((e) => btn(`${e.date.slice(0, 7)}　${e.name}`, e.id === sel,
          () => { sel = e.id; store.set("csSel", sel); draw(); })) : [h("span", { class: "muted" }, "沒有符合的事件")]));
        // 清單換了內容（第一次畫、清掉搜尋字）就把選中的事件捲回看得見的位置
        requestAnimationFrame(() => {
          const on = list.querySelector('[aria-pressed="true"]');
          if (on) list.scrollTop = Math.max(0, on.offsetTop - list.clientHeight / 2 + on.offsetHeight / 2);
        });
      };
      const input = h("input", { class: "gl-search ev-search", type: "search", placeholder: "搜尋事件，例：雷曼、1997、關稅", "aria-label": "搜尋事件" });
      input.value = evQ;
      input.addEventListener("input", () => { evQ = input.value; fill(); });
      chips2.replaceChildren(h("div", { class: "ev-bar" }, h("span", { class: "lab" }, "選事件"), input, count), list);
      fill();
    } else if (mode === "cat") {
      if (!CA.categories.some((c) => c.id === fcat)) fcat = CA.categories[0].id;
      chips.replaceChildren(...modeChips, h("span", { class: "lab", style: "margin-left:10px" }, "選分類"),
        ...CA.categories.map((c) => btn(`${c.name}（${c.n} 次）`, c.id === fcat, () => { fcat = c.id; store.set("csCat", fcat); draw(); })));
    } else {   // compare 與 now 都用期間切換
      chips.replaceChildren(...modeChips, h("span", { class: "lab", style: "margin-left:10px" }, "期間"),
        ...CA.windows.map((w) => btn(csWin(w), w === win,
          () => { win = w; store.set("csWin", w); draw(); })));
    }

    body.replaceChildren();
    if (mode === "event") {
      const ev = CA.events.find((e) => e.id === sel);
      const responded = ev.assets.filter((a) => a.responded).length;
      const c = card({ title: `${ev.name}（${ev.date}${ev.approx ? " 概略日" : ""}）`, span: 12,
        sub: `${catName(ev.cat)}　｜　${ev.note}　｜　${responded}/${ev.assets.length} 個標的出現實質反應`
          + (ev.coverage < CA.universe.length ? `（${CA.universe.length} 個標的中只有 ${ev.coverage} 個在當時有資料）` : ""),
        note: CA.note });
      if (ev.overlaps.length) {
        c.body.append(h("p", { class: "cs-warn" }, "⚠ 兩個月視窗內還有其他事件，下面的變動混有它們的效果：",
          ev.overlaps.map((o) => `${o.name}（${o.days > 0 ? "後" : "前"} ${Math.abs(o.days)} 天）`).join("、")));
      }
      if (ev.proxies.length) {
        c.body.append(h("p", { class: "cs-info" }, "當時 ETF／期貨尚未上市，部分標的改用代理序列：", ev.proxies.join("、"),
          "。代理與原標的並非完全相同的資產，明細中逐筆標註。"));
      }
      const P = ev.persist;
      c.body.append(h("div", { class: "cs-persist" },
        h("b", {}, "持續性："), P.verdict ? `多數有反應的標的屬於「${csPersist(P.verdict)}」衝擊` : "無法判定",
        h("span", { class: "muted" }, "　尺＝兩個月內的最大反應：半年後還保有一半以上才算長期，一年後還保有一半以上才算一年以上"),
        persistBar(P.dist, P.n), persistBaseNote(),
        fin(ev.growing_share) ? h("span", { class: "muted" }, `有反應的標的中 ${ev.growing_share}% 在半年後比兩個月的峰值更大（事件過了兩個月還在擴大）${ev.region === "cn" ? "；這是中國事件" : ""}`) : null));
      const host = h("div", { class: "chart" });
      c.body.append(h("h4", { class: "sub-h" }, "傳導時間軸：點的位置＝走完一半反應的那一天，大小＝反應幅度"), host);
      mount(host, () => cascadeTimeline(host, ev.assets.filter((a) => a.responded), CA.max_days));
      const pathHost = h("div", { class: "chart" });
      c.body.append(h("h4", { class: "sub-h" }, "反應最大的四個標的：事件後累積變動"), pathHost);
      mount(pathHost, () => cascadePaths(pathHost, ev.assets));
      c.body.append(h("h4", { class: "sub-h" }, "逐層明細"), cascadeTable(
        ev.assets.slice().sort((a, b) => (a.half_day === null) - (b.half_day === null) || (a.half_day || 99) - (b.half_day || 99)), false));
      body.append(c.el);
    } else if (mode === "cat") {
      const cat = CA.categories.find((c) => c.id === fcat);
      const evNames = cat.events.map((id) => CA.events.find((e) => e.id === id)).filter(Boolean)
        .map((e) => `${e.date.slice(0, 4)} ${e.name}`);
      const c = card({ title: `${cat.name}：${cat.n} 次事件的共同模式`, span: 12,
        sub: `包含：${evNames.join("、")}`,
        note: "中位數與同向比例；「平常」＝該標的全部歷史中任意一天起算同樣天數的中位數，事件後的數字要跟它比；"
          + "● ＝事件後上漲比例和平常的差異通過二項檢定 p≤0.05（但約三分之二這種格子是運氣，見類型比較頁）。"
          + "每類事件次數不多，只能當參考。「有反應次數」代表這個標的在幾次事件中真的動了；"
          + "早期事件很多標的還沒有資料，所以每一列的次數不同。" + CA.note });
      if (cat.skipped.length) {
        c.body.append(h("p", { class: "cs-warn" }, "以下事件與同類前一個事件相隔太近，彙總時不重複計算：",
          cat.skipped.map((s) => `${s.name}（${s.after}後 ${s.days} 天）`).join("、")));
      }
      c.body.append(h("div", { class: "cs-persist" }, h("b", {}, "這類事件的持續性（所有事件、有反應的標的合計）："), persistBar(cat.persist, 0), persistBaseNote()));
      const host = h("div", { class: "chart" });
      c.body.append(h("h4", { class: "sub-h" }, "傳導時間軸（各標的的中位數）"), host);
      mount(host, () => cascadeTimeline(host, cat.assets.filter((r) => fin(r.half_day) && r.half_n >= 2)
        .map((r) => Object.assign({}, r, { peak_move: r.w21 })), CA.max_days));
      c.body.append(h("h4", { class: "sub-h" }, "逐層明細"), cascadeTable(cat.assets, true));
      body.append(c.el);
    } else if (mode === "now") {
      const AN = CA.analogs;
      const c = card({ title: AN ? `現在最像哪幾次事件：${AN.analogs.map((a) => a.name).join("、")}` : "現在最像哪幾次事件", span: 12,
        sub: "今天的市場環境（股市、回檔、波動、利率、殖利率曲線、美元、黃金、原油、高收益債）加上最新一天的反應幅度，"
          + "和 88 個歷史事件發生時比對。",
        note: "回測是留一法：預測某個事件時，把它前後 60 天內的事件排除，避免視窗重疊洩漏答案。"
          + "命中＝預測「比平常漲多／跌多」的方向對了；平常＝該標的全部歷史中任意一天起算同樣天數的中位數。" });
      c.body.append(...cascadeNow(win));
      body.append(c.el);
    } else {
      const c = card({ title: `不同類型的事件，錢往哪裡流（事件後${csWin(win)}）`, span: 12,
        sub: "每格是該類事件後的中位數變動，下方小字是該標的「平常」同樣天數的中位數。"
          + "只有上漲比例和平常明顯不同（二項檢定 p≤0.10）的格子才上色：紅＝比平常漲得多、綠＝比平常跌得多；● ＝p≤0.05。",
        note: "每類事件只有 4～14 次，且早期事件很多標的沒有資料（格內標示次數）。這是歷史上的中位數，不是預測；"
          + "同一類事件的起因不同（例：1990 年伊拉克入侵科威特與 2023 年哈瑪斯攻擊以色列都是地緣衝突，對油價的衝擊差很多），"
          + "看同向比例比看中位數重要。" + CA.note });
      c.body.append(...cascadeCompare(win));
      const L = CA.cn_lag;
      if (L && L.cn_n) {
        const sig = fin(L.p) && L.p <= 0.05;
        const B = CA.persist_base;
        c.body.append(h("h4", { class: "sub-h" }, "課堂假說檢驗：中國事件是不是「半年後才浮現」"),
          h("p", { class: "cs-info" },
            `量法：事件後兩個月內有實質反應的標的中，半年後的變動比兩個月的峰值更大（＝事件過了兩個月還在擴大）的比例。`
            + `中國事件（${L.cn_n} 次）中位數 ${L.cn_median}%、平均 ${L.cn_mean}%；其他事件（${L.other_n} 次）中位數 ${L.other_median}%、平均 ${L.other_mean}%`
            + (B && fin(B.growing_median) ? `；隨機日期 ${B.growing_median}%` : "") + "。"
            + (sig ? `中國事件明顯較高（重排檢定 p=${L.p}），但次數少，仍只能當參考。`
                   : `差異在隨機範圍內（重排檢定 p≈${fin(L.p) ? L.p : "—"}），資料不能證明中國事件比較晚浮現，也不能否定——次數太少。`)
            + `　逐一：${L.cn_events.map((e) => `${e.name} ${fin(e.share) ? e.share + "%" : "—"}`).join("、")}`));
      }
      body.append(c.el);
    }
  };

  const holder = card({ title: "選擇事件", span: 12,
    sub: `收錄 1980 年以來 ${CA.events.length} 個真實事件，分 ${CA.categories.length} 類。事件清單可在 gfd/config.py 的 SHOCK_EVENTS 增刪。` });
  holder.tools.append(chips);
  holder.body.append(chips2);
  g.append(holder.el);
  root.append(body);
  draw();
  const cc = crisisCard();                  // 原「30 年關聯」分頁的歷史危機表（月資料），收合卡
  if (cc) root.append(h("div", { class: "grid", style: "margin-top:16px" }, cc.el));
});
