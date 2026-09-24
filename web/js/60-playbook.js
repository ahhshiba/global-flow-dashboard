/* 分頁：訊號劇本（事件前兆 × 事件後全資產期望值） */

function pbNum(v, unit, d) {
  return fin(v) ? fmtSigned(v, d ?? (unit === "bp" ? 0 : 1), unit === "bp" ? "bp" : "%") : "—";
}
function pbRows(rows, showFlag) {
  const head = ["資產", "期間", "事件後中位數", "平常", "超額", "上漲比例", "最糟一次", "前半／後半", "p", "n"];
  return h("div", { class: "tbl-wrap" }, h("table", { class: "data" },
    h("thead", {}, h("tr", {}, head.map((t, i) => h("th", { class: i ? "n" : null }, t)))),
    h("tbody", {}, rows.map((r) => h("tr", { class: r.robust ? "sel" : null },
      h("td", {}, r.name, r.robust && showFlag ? h("span", { class: "qnote" }, "通過檢驗") : null,
        !r.investable ? h("span", { class: "sub" }, "觀察指標，不能直接買") : null),
      h("td", { class: "n" }, `${r.horizon} 個月`),
      h("td", { class: "n" }, h("span", { class: dirClass(r.median) }, pbNum(r.median, r.unit))),
      h("td", { class: "n muted" }, pbNum(r.base, r.unit)),
      h("td", { class: "n" }, h("b", { class: dirClass(r.lift) }, pbNum(r.lift, r.unit))),
      h("td", { class: "n" }, fin(r.hit) ? `${r.hit.toFixed(0)}%` : "—"),
      h("td", { class: "n down" }, pbNum(r.worst, r.unit)),
      h("td", { class: "n muted" }, `${pbNum(r.early, r.unit, 0)}／${pbNum(r.late, r.unit, 0)}`),
      h("td", { class: "n" }, fin(r.p) ? r.p.toFixed(3) : "—"),
      h("td", { class: "n muted" }, r.n))))));
}

function pbTriggerCard(t, P) {
  const c = card({ title: t.label, span: 12,
    sub: `${t.why}　｜　來自：${t.source}　｜　歷史 ${t.episodes} 次事件${t.active ? "　｜　目前成立中" : ""}`,
    note: `最近幾次：${t.dates.join("、")}。目前值 ${fin(t.current) ? fmtNum(t.current, 2) : "—"}（${t.current_at || "—"}）。` });

  if (t.precursors.length) {
    c.body.append(h("h4", { class: "sub-h" }, "前兆：這個事件發生前，通常先看到什麼"));
    c.body.append(h("div", { class: "tbl-wrap" }, h("table", { class: "data" },
      h("thead", {}, h("tr", {}, ["前兆訊號", "出現後 6 個月內本事件發生率", "平常發生率", "多出", "涵蓋本事件比例", "領先月數", "n"]
        .map((x, i) => h("th", { class: i ? "n" : null }, x)))),
      h("tbody", {}, t.precursors.map((p) => h("tr", {},
        h("td", {}, p.label, h("span", { class: "sub" }, p.source)),
        h("td", { class: "n" }, `${p.precision}%`),
        h("td", { class: "n muted" }, `${p.base}%`),
        h("td", { class: "n" }, h("b", {}, `+${p.lift}pp`)),
        h("td", { class: "n" }, `${p.recall}%`),
        h("td", { class: "n" }, fin(p.lead) ? `${p.lead} 個月` : "—"),
        h("td", { class: "n muted" }, p.n)))))));
    c.body.append(h("p", { class: "note", style: "margin-top:4px" },
      "「發生率」是前兆出現後事件跟著來的比例（精確率），「涵蓋」是本事件有多少次事前看得到這個前兆（召回率）。兩個都要看：只有精確率高但涵蓋低，代表大多數事件沒有預警。"));
  }
  if (t.pre.length) {
    c.body.append(h("h4", { class: "sub-h" }, "事件當下，各資產自己前 3 個月已經走了多少"),
      h("div", { class: "tbl-wrap" }, h("table", { class: "data" },
        h("thead", {}, h("tr", {}, ["資產", "事件前 3 個月中位數", "平常", "差"].map((x, i) => h("th", { class: i ? "n" : null }, x)))),
        h("tbody", {}, t.pre.map((x) => h("tr", {}, h("td", {}, x.name),
          h("td", { class: "n" }, h("span", { class: dirClass(x.event) }, pbNum(x.event, x.unit))),
          h("td", { class: "n muted" }, pbNum(x.base, x.unit)),
          h("td", { class: "n" }, h("b", { class: dirClass(x.diff) }, pbNum(x.diff, x.unit)))))))));
  }

  let horizon = store.get("pbHorizon", P.horizons[1]);
  let onlyInv = store.get("pbInvestable", true);
  const chips = h("div", { class: "chips", style: "margin-top:12px" });
  const tbl = h("div");
  const drawRows = () => {
    chips.replaceChildren(h("span", { class: "lab" }, "期間"),
      ...P.horizons.map((hh) => h("button", { class: "chip", type: "button", "aria-pressed": String(hh === horizon),
        onclick: () => { horizon = hh; store.set("pbHorizon", hh); drawRows(); } }, `${hh} 個月`)),
      h("span", { class: "lab", style: "margin-left:8px" }, "範圍"),
      h("button", { class: "chip", type: "button", "aria-pressed": String(onlyInv),
        onclick: () => { onlyInv = !onlyInv; store.set("pbInvestable", onlyInv); drawRows(); } }, onlyInv ? "只看可投資標的" : "含觀察指標"));
    const blk = t.assets[String(horizon)];
    const pick = (arr) => arr.filter((r) => !onlyInv || r.investable);
    const top = pick(blk.top), bottom = pick(blk.bottom);
    tbl.replaceChildren(
      h("h4", { class: "sub-h" }, `事件後 ${horizon} 個月：超額最高的標的（超額＝事件後中位數 − 該資產自己的平常水準）`),
      top.length ? pbRows(top, true) : h("p", { class: "empty" }, "沒有資料"),
      h("h4", { class: "sub-h" }, "同期最差的標的"),
      bottom.length ? pbRows(bottom, true) : h("p", { class: "empty" }, "沒有資料"));
  };
  drawRows();
  c.body.append(chips, tbl);
  return c.el;
}

TABS.playbook = (root) => {
  const P = A.playbook;
  root.replaceChildren(tabHead("訊號劇本：事件的前兆與之後該看哪些資產",
    "每個事件先找前兆（哪些訊號常在它之前出現，含誤報率），再把 37 個資產在事件後 3／6／12 個月的表現全部排名。排名看的是「超額」＝事件後表現減掉該資產自己的平常水準，否則長期上漲的資產會一路排在前面。這些是歷史統計，不是建議，也沒有計入交易成本。", false));
  if (!P || !P.triggers.length) { root.append(h("p", { class: "empty" }, "尚未產生訊號劇本，請執行 python3 gfd.py analyze")); return; }
  const g = h("div", { class: "grid" });
  root.append(g);

  // 可信度：多重檢定的誠實交代
  const s = P.stats;
  const mc = card({ title: "先看這個：這些數字有多可信", span: 12,
    sub: "一次檢定這麼多組合，光靠運氣就會撈到一批「有效」的結果。下面是實際通過數與運氣預期值的對照。",
    note: `位移檢定的 p 值下限約 ${s.p_floor}（只有 ${A.months.length} 種位移），所以不用 Benjamini-Hochberg（會因精度不足把全部判成無效），改用運氣預期值估偽發現率。資產彼此相關，實際偽發現率可能更高。` });
  mc.body.append(h("div", { class: "tbl-wrap" }, h("table", { class: "data" },
    h("thead", {}, h("tr", {}, ["p 值門檻", "實際通過", "純靠運氣預期", "估計偽發現率", "再加前後半期一致＋幅度門檻", "估計偽發現率"]
      .map((x, i) => h("th", { class: i ? "n" : null }, x)))),
    h("tbody", {}, s.buckets.map((b) => h("tr", { class: b.p === s.strict_p ? "sel" : null },
      h("td", {}, `p ≤ ${b.p}${b.p === s.strict_p ? "（採用）" : ""}`),
      h("td", { class: "n" }, b.observed), h("td", { class: "n muted" }, b.expected),
      h("td", { class: "n" }, `${b.fdr}%`),
      h("td", { class: "n" }, b.with_filters), h("td", { class: "n" }, h("b", {}, `${b.fdr_filtered}%`))))))));
  mc.body.append(h("p", { class: "note" },
    `共檢定 ${s.tested} 組（訊號 × 資產 × 期間）。最後留下 ${s.robust} 組，其中可投資標的 ${s.robust_investable} 組；`
    + `估計仍有約 ${s.fdr_estimate}% 是運氣。換句話說：這張清單是「候選」，不是「結論」，三組裡大概有一組是雜訊。`));
  g.append(mc.el);

  const fc = findingsCard("playbook", "目前成立中的訊號");
  if (fc) g.append(fc);

  // 全域通過檢驗清單
  const up = P.robust.filter((r) => r.lift > 0).slice(0, 15);
  const down = P.robust.filter((r) => r.lift < 0).slice(0, 10);
  const rc = card({ title: "通過檢驗的組合（可投資標的）", span: 12,
    sub: "事件數 ≥ 8、2012 年前後兩段同方向、超額幅度夠大、位移檢定 p ≤ " + P.max_p_strict_label,
    note: "「前半／後半」是 2012 年前後各自的事件後中位數；兩邊同號才列入。最糟一次是該事件後最差的一次結果，決定停損要放多寬。" });
  const mkList = (rows) => h("div", { class: "tbl-wrap" }, h("table", { class: "data" },
    h("thead", {}, h("tr", {}, ["訊號", "資產", "期間", "超額", "事件後", "上漲比例", "最糟", "前半／後半", "p", "n"]
      .map((x, i) => h("th", { class: i ? "n" : null }, x)))),
    h("tbody", {}, rows.map((r) => h("tr", {},
      h("td", {}, r.trigger_label),
      h("td", {}, r.name),
      h("td", { class: "n" }, `${r.horizon} 個月`),
      h("td", { class: "n" }, h("b", { class: dirClass(r.lift) }, pbNum(r.lift, r.unit))),
      h("td", { class: "n" }, pbNum(r.median, r.unit)),
      h("td", { class: "n" }, fin(r.hit) ? `${r.hit.toFixed(0)}%` : "—"),
      h("td", { class: "n down" }, pbNum(r.worst, r.unit)),
      h("td", { class: "n muted" }, `${pbNum(r.early, r.unit, 0)}／${pbNum(r.late, r.unit, 0)}`),
      h("td", { class: "n" }, fin(r.p) ? r.p.toFixed(3) : "—"),
      h("td", { class: "n muted" }, r.n))))));
  rc.body.append(h("h4", { class: "sub-h" }, "事件後表現優於自己平常（超額為正）"), mkList(up),
    h("h4", { class: "sub-h" }, "事件後表現劣於自己平常（超額為負，通常是該避開或反手的方向）"), mkList(down));
  if (P.robust_observe && P.robust_observe.length) {
    rc.body.append(h("details", { style: "margin-top:10px" }, h("summary", {}, `另有 ${P.robust_observe.length} 組落在觀察指標（VIX、殖利率、利差）——反應多半是機械性的，不能直接當部位`),
      mkList(P.robust_observe.slice(0, 10))));
  }
  g.append(rc.el);

  // 逐訊號檢視
  const actives = P.triggers.filter((t) => t.active);
  let sel = store.get("pbSel", (actives[0] || P.triggers[0]).id);
  const chips = h("div", { class: "chips" });
  const body = h("div", { class: "grid", style: "margin-top:16px" });
  const draw = () => {
    if (!P.triggers.some((t) => t.id === sel)) sel = P.triggers[0].id;
    chips.replaceChildren(h("span", { class: "lab" }, "選訊號"),
      ...P.triggers.slice().sort((a, b) => (b.active - a.active) || (b.robust_count - a.robust_count)).map((t) =>
        h("button", { class: "chip", type: "button", "aria-pressed": String(t.id === sel),
          onclick: () => { sel = t.id; store.set("pbSel", sel); draw(); } },
        `${t.active ? "● " : ""}${t.label.length > 18 ? t.label.slice(0, 18) + "…" : t.label}`)));
    body.replaceChildren(pbTriggerCard(P.triggers.find((t) => t.id === sel), P));
  };
  const holder = card({ title: "逐訊號檢視", span: 12, sub: "「●」代表目前成立中。清單依成立中、通過檢驗的組合數排序。" });
  holder.tools.append(chips);
  g.append(holder.el);
  root.append(body);
  draw();
};
