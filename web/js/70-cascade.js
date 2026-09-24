/* 分頁：事件衝擊鏈（真實事件 → 兩週／一個月／兩個月的逐層傳導） */

function csUnit(v, unit, d) {
  if (!fin(v)) return "—";
  return fmtSigned(v, d ?? (unit === "bp" ? 0 : unit === "pt" ? 1 : 1), unit === "%" ? "%" : unit === "bp" ? "bp" : " pt");
}
const csLayerName = (id) => (A.cascade.layers.find((l) => l.id === id) || {}).name || id;

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
  for (const d of [1, 5, 10, 21, 42].filter((d) => d <= maxDays)) {
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
  const head = isCat
    ? ["標的", "傳導速度（半程）", "有反應次數", "事件前 10 天", "兩週", "一個月", "兩個月"]
    : ["標的", "傳導速度（半程）", "最大反應", "事件前 10 天", "兩週", "一個月", "兩個月"];
  const body = [];
  for (const l of A.cascade.layers) {
    const inLayer = rows.filter((r) => r.layer === l.id);
    if (!inLayer.length) continue;
    body.push(h("tr", {}, h("td", { colspan: head.length, style: "background:var(--surface-2);font-weight:600" }, l.name)));
    for (const r of inLayer) {
      body.push(h("tr", {},
        h("td", {}, r.name, !fin(r.half_day) ? h("span", { class: "sub" }, "無實質反應") : null),
        h("td", { class: "n" }, fin(r.half_day) ? `第 ${r.half_day} 天` : "—"),
        isCat
          ? h("td", { class: "n" }, `${r.half_n}/${r.n}`, h("span", { class: "sub" }, fin(r.resp_rate) ? `${r.resp_rate}%` : ""))
          : h("td", { class: "n" }, fin(r.peak_move) ? h("span", { class: dirClass(r.peak_move) }, csUnit(r.peak_move, r.unit)) : "—",
            fin(r.peak_day) ? h("span", { class: "sub" }, `第 ${r.peak_day} 天`) : null),
        h("td", { class: "n muted" }, csUnit(r.pre, r.unit)),
        ...A.cascade.windows.map((w) => h("td", { class: "n" },
          h("span", { class: dirClass(r[`w${w}`]) }, csUnit(r[`w${w}`], r.unit)),
          isCat && fin(r[`agree${w}`]) ? h("span", { class: "sub" }, `同向 ${r[`agree${w}`]}%`) : null))));
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

TABS.cascade = (root) => {
  const CA = A.cascade;
  root.replaceChildren(tabHead("事件衝擊鏈：一個事件，兩週到兩個月內怎麼一層一層傳下去",
    "用日線做事件研究。事件是真的發生過的事（戰爭、管線中斷、破產），不是價格門檻。"
    + "傳導順序不是假設的，是量出來的：每個標的先判斷有沒有實質反應（期間內最大累積變動超過自身 2σ×√天數），"
    + "有反應的再算「走完一半」是第幾天——上游通常幾天就走完，下游會拖。", false));
  if (!CA || !CA.events.length) { root.append(h("p", { class: "empty" }, "尚未產生事件衝擊分析，請執行 python3 gfd.py history 後再 analyze")); return; }
  const g = h("div", { class: "grid" });
  root.append(g);

  let mode = store.get("csMode", "event");
  let sel = store.get("csSel", "ukraine22");
  const chips = h("div", { class: "chips" });
  const body = h("div", { class: "grid", style: "margin-top:16px" });

  const draw = () => {
    const modeChips = [["event", "單一事件"], ["cat", "分類彙總"]].map(([k, l]) =>
      h("button", { class: "chip", type: "button", "aria-pressed": String(k === mode),
        onclick: () => { mode = k; store.set("csMode", k); sel = k === "cat" ? CA.categories[0].id : "ukraine22"; draw(); } }, l));
    const list = mode === "event"
      ? CA.events.map((e) => [e.id, `${e.date.slice(0, 7)}　${e.name}`])
      : CA.categories.map((c) => [c.id, `${c.name}（${c.n} 次）`]);
    if (!list.some(([k]) => k === sel)) sel = list[0][0];
    chips.replaceChildren(...modeChips, h("span", { class: "lab", style: "margin-left:10px" }, mode === "event" ? "選事件" : "選分類"),
      ...list.map(([k, l]) => h("button", { class: "chip", type: "button", "aria-pressed": String(k === sel),
        onclick: () => { sel = k; store.set("csSel", k); draw(); } }, l)));

    body.replaceChildren();
    if (mode === "event") {
      const ev = CA.events.find((e) => e.id === sel);
      const responded = ev.assets.filter((a) => a.responded).length;
      const c = card({ title: `${ev.name}（${ev.date}${ev.approx ? " 概略日" : ""}）`, span: 12,
        sub: `${ev.note}　｜　${responded}/${ev.assets.length} 個標的出現實質反應`,
        note: CA.note });
      const host = h("div", { class: "chart" });
      c.body.append(h("h4", { class: "sub-h" }, "傳導時間軸：點的位置＝走完一半反應的那一天，大小＝反應幅度"), host);
      mount(host, () => cascadeTimeline(host, ev.assets.filter((a) => a.responded), CA.max_days));
      const pathHost = h("div", { class: "chart" });
      c.body.append(h("h4", { class: "sub-h" }, "反應最大的四個標的：事件後累積變動"), pathHost);
      mount(pathHost, () => cascadePaths(pathHost, ev.assets));
      c.body.append(h("h4", { class: "sub-h" }, "逐層明細"), cascadeTable(
        ev.assets.slice().sort((a, b) => (a.half_day === null) - (b.half_day === null) || (a.half_day || 99) - (b.half_day || 99)), false));
      body.append(c.el);
    } else {
      const cat = CA.categories.find((c) => c.id === sel);
      const evNames = cat.events.map((id) => (CA.events.find((e) => e.id === id) || {}).name).filter(Boolean);
      const c = card({ title: `${cat.name}：${cat.n} 次事件的共同模式`, span: 12,
        sub: `包含：${evNames.join("、")}`,
        note: "中位數與同向比例；每類事件次數不多（4～8 次），只能當參考。「有反應次數」代表這個標的在幾次事件中真的動了。" + CA.note });
      const host = h("div", { class: "chart" });
      c.body.append(h("h4", { class: "sub-h" }, "傳導時間軸（各標的的中位數）"), host);
      mount(host, () => cascadeTimeline(host, cat.assets.filter((r) => fin(r.half_day) && r.half_n >= 2)
        .map((r) => Object.assign({}, r, { peak_move: r.w21 })), CA.max_days));
      c.body.append(h("h4", { class: "sub-h" }, "逐層明細"), cascadeTable(cat.assets, true));
      body.append(c.el);
    }
  };

  const holder = card({ title: "選擇事件", span: 12,
    sub: `收錄 ${CA.events.length} 個真實事件，分 ${CA.categories.length} 類。事件清單可在 gfd/config.py 的 SHOCK_EVENTS 增刪。` });
  holder.tools.append(chips);
  g.append(holder.el);
  root.append(body);
  draw();
};
