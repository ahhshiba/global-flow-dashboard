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
          isCat && fin(r[`agree${w}`]) ? h("span", { class: "sub" }, `同向 ${r[`agree${w}`]}%｜平常 ${csUnit(r[`base${w}`], r.unit)}`) : null))));
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

TABS.cascade = (root) => {
  const CA = A.cascade;
  root.replaceChildren(tabHead("事件衝擊鏈：一個事件，兩週到兩個月內怎麼一層一層傳下去",
    "用日線做事件研究。事件是真的發生過的事（戰爭、央行轉向、匯率危機、崩盤、疫情、天災…），不是價格門檻。"
    + "傳導順序不是假設的，是量出來的：每個標的先判斷有沒有實質反應（期間內最大累積變動超過自身 2σ×√天數），"
    + "有反應的再算「走完一半」是第幾天——上游通常幾天就走完，下游會拖。", false));
  if (!CA || !CA.events.length) { root.append(h("p", { class: "empty" }, "尚未產生事件衝擊分析，請執行 python3 gfd.py history 後再 analyze")); return; }
  const g = h("div", { class: "grid" });
  root.append(g);

  const catName = (id) => (CA.categories.find((c) => c.id === id) || {}).name || id;
  let mode = store.get("csMode", "event");
  let sel = store.get("csSel", "ukraine22");
  let fcat = store.get("csCat", "all");
  let win = store.get("csWin", 21);
  const chips = h("div", { class: "chips" });
  const chips2 = h("div", { class: "chips", style: "margin-top:8px" });
  const body = h("div", { class: "grid", style: "margin-top:16px" });
  const btn = (label, on, fn) => h("button", { class: "chip", type: "button", "aria-pressed": String(on), onclick: fn }, label);

  const draw = () => {
    const modeChips = [["event", "單一事件"], ["cat", "分類彙總"], ["compare", "類型比較"]].map(([k, l]) =>
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
      chips2.replaceChildren(h("span", { class: "lab" }, "選事件"),
        ...evs.map((e) => btn(`${e.date.slice(0, 7)}　${e.name}`, e.id === sel, () => { sel = e.id; store.set("csSel", sel); draw(); })));
    } else if (mode === "cat") {
      if (!CA.categories.some((c) => c.id === fcat)) fcat = CA.categories[0].id;
      chips.replaceChildren(...modeChips, h("span", { class: "lab", style: "margin-left:10px" }, "選分類"),
        ...CA.categories.map((c) => btn(`${c.name}（${c.n} 次）`, c.id === fcat, () => { fcat = c.id; store.set("csCat", fcat); draw(); })));
    } else {
      chips.replaceChildren(...modeChips, h("span", { class: "lab", style: "margin-left:10px" }, "期間"),
        ...CA.windows.map((w) => btn(w === 10 ? "兩週" : w === 21 ? "一個月" : "兩個月", w === win,
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
      const host = h("div", { class: "chart" });
      c.body.append(h("h4", { class: "sub-h" }, "傳導時間軸（各標的的中位數）"), host);
      mount(host, () => cascadeTimeline(host, cat.assets.filter((r) => fin(r.half_day) && r.half_n >= 2)
        .map((r) => Object.assign({}, r, { peak_move: r.w21 })), CA.max_days));
      c.body.append(h("h4", { class: "sub-h" }, "逐層明細"), cascadeTable(cat.assets, true));
      body.append(c.el);
    } else {
      const c = card({ title: `不同類型的事件，錢往哪裡流（事件後${win === 10 ? "兩週" : win === 21 ? "一個月" : "兩個月"}）`, span: 12,
        sub: "每格是該類事件後的中位數變動，下方小字是該標的「平常」同樣天數的中位數。"
          + "只有上漲比例和平常明顯不同（二項檢定 p≤0.10）的格子才上色：紅＝比平常漲得多、綠＝比平常跌得多；● ＝p≤0.05。",
        note: "每類事件只有 4～14 次，且早期事件很多標的沒有資料（格內標示次數）。這是歷史上的中位數，不是預測；"
          + "同一類事件的起因不同（例：1990 年伊拉克入侵科威特與 2023 年哈瑪斯攻擊以色列都是地緣衝突，對油價的衝擊差很多），"
          + "看同向比例比看中位數重要。" + CA.note });
      c.body.append(...cascadeCompare(win));
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
};
