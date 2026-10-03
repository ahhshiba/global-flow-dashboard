/* 沙盤推演的「一頁看懂」（2026-10-03）：使用者說推演總結「看不懂」——原本照研究步驟排（訊號、鏈、模型、回測），
   名稱是門檻（「日本 10 年殖利率 6 個月上升 ≥ 20bp」），標題講期望值、內文又說期望值不能用。
   這裡改照讀者的問題排四步：現在的局面 → 接下來可能發生什麼 → 該怎麼準備 → 這些推論有多可靠，
   每一步用白話、一兩個數字；原本的卡片原封不動放在下面的「研究細節」。全部由資料組出來。 */

// 訊號的白話名稱與主題（門檻原文放在小字）
const SC_PLAIN = {
  dollar_dxy: ["美元走強", "匯率"], dollar_hsi: ["港股下跌", "股市"], dollar_copper: ["銅價下跌", "原物料"],
  dollar_agri: ["農產品下跌", "原物料"], dollar_ust: ["美國長債上漲（利率下降）", "利率"],
  carry_jgb: ["日本利率上升", "利率"], carry_jpy: ["日圓轉強", "匯率"], carry_spx: ["美股下跌", "股市"],
  carry_sox: ["半導體股下跌", "股市"], carry_twii: ["台股下跌", "股市"],
  inflation_oil: ["油價大漲", "原物料"], inflation_ust10: ["美國長期利率上升", "利率"], inflation_ndx: ["科技股下跌", "股市"],
  inflation_curve: ["美國長短利差變窄", "利率"], inflation_gold: ["黃金上漲", "原物料"],
  fertilizer_gas: ["歐洲天然氣大漲", "原物料"], fertilizer_urea: ["肥料（尿素）大漲", "原物料"],
  fertilizer_agri: ["農產品上漲", "原物料"], fertilizer_ust3m: ["美國短期利率上升（升息）", "利率"],
  cycle_cuau: ["銅比黃金強（實體需求回溫）", "原物料"], cycle_sox: ["半導體股大漲", "股市"], cycle_twii: ["台股上漲", "股市"],
  cycle_twd: ["新台幣轉強", "匯率"], cycle_hy: ["高收益債上漲（市場敢冒險）", "信用與恐慌"],
  panic_vix: ["市場恐慌（VIX ≥ 30）", "信用與恐慌"], panic_hy: ["高收益債下跌（信用緊張）", "信用與恐慌"],
  panic_spx: ["美股大跌", "股市"], panic_twii: ["台股大跌", "股市"],
  china_cny: ["人民幣走弱", "匯率"], china_hsi: ["港股下跌", "股市"], china_metals: ["金屬價格下跌", "原物料"],
  curve_inv: ["美國殖利率曲線倒掛", "利率"], vix_25: ["市場緊張（VIX ≥ 25）", "信用與恐慌"],
  dxy_down: ["美元走弱", "匯率"], twd_weak: ["新台幣轉弱", "匯率"], spx_dd: ["美股一年跌 1 成以上", "股市"],
  gold_run: ["黃金大漲", "原物料"], rates_up: ["美國長期利率急升", "利率"], rates_down: ["美國長期利率急降", "利率"],
};
// 同一件事的強弱兩個門檻都亮時，只講強的那個
const SC_SUPERSEDE = { rates_up: "inflation_ust10", panic_spx: "carry_spx", panic_twii: "carry_twii", china_hsi: "dollar_hsi",
  gold_run: "inflation_gold", panic_vix: "vix_25" };
const SC_THEMES = ["利率", "匯率", "股市", "原物料", "信用與恐慌"];
const SC_CHAIN_PLAIN = { carry: "日圓套利平倉", inflation: "通膨", fertilizer: "肥料到糧價", cycle: "景氣擴張", china: "中國轉弱",
  dollar: "美元緊縮", panic: "恐慌" };
// 每條鏈為什麼會這樣傳（白話一句；改寫自 config.CHAINS 的 thesis，意思不變）
const SC_CHAIN_WHY = {
  carry: "日圓是低利借錢的貨幣：日本利率上升讓借日圓變貴，借日圓去買股票的人被迫賣股還錢，先賣美股，再擴散到半導體和台股。",
  inflation: "油價是通膨最直接的來源：油價急漲推高長期利率，利率高讓成長股變便宜，資金轉向黃金避險。",
  fertilizer: "氮肥是用天然氣做的：天然氣漲 → 肥料漲 → 糧價漲 → 通膨 → 可能升息（2026-10-01 課堂提到的鏈）。",
  cycle: "銅比黃金強代表工廠真的在用料：半導體先漲，接著台股，外資匯進來讓台幣變強，最後連高收益債也漲。",
  china: "人民幣走弱通常代表中國內需轉弱：先反映在港股，再到金屬，最後透過供應鏈影響台灣、韓國的電子股。",
  dollar: "美元是全世界借錢用的貨幣：美元變貴先壓美國以外的股市，再壓用美元計價的原物料，最後美債反而上漲。",
  panic: "恐慌時高收益債先跌、股市補跌；這條鏈在看「恐慌時買進」過去值多少、要先忍受多深的下跌。",
};
const scPlain = (id, label) => (SC_PLAIN[id] ? SC_PLAIN[id][0] : label);

// 現在亮著、去掉被更強門檻蓋過的
function storyLit(S) {
  const ids = new Set(S.active.map((a) => a.id));
  const hidden = new Set(Object.entries(SC_SUPERSEDE).filter(([strong]) => ids.has(strong)).map(([, weak]) => weak));
  return S.active.filter((a) => !hidden.has(a.id));
}
// 還沒成立、比平常更可能（或更不可能）的下一層；同一個訊號出現在幾條鏈就取差距最大的那條
function storyNext(S) {
  const by = new Map();
  for (const p of S.paths) for (const n of p.nodes) {
    if (n.triggered || !fin(n.prob) || !fin(n.base)) continue;
    const key = n.trigger || n.label;
    const lift = n.prob - n.base;
    if (!by.has(key) || Math.abs(lift) > Math.abs(by.get(key).lift)) by.set(key, { p, n, lift });
  }
  return [...by.values()];
}
// 進行中的鏈：成立兩層以上，從亮著的層講到下一個沒亮的層
function storyChains(S) {
  return S.paths.filter((p) => p.active >= 2).sort((a, b) => b.active / b.of - a.active / a.of).slice(0, 2).map((p) => {
    const lit = p.nodes.filter((n) => n.triggered);
    const last = p.nodes.reduce((k, n, i) => (n.triggered ? i : k), -1);
    const next = p.nodes.slice(last + 1).find((n) => !n.triggered && fin(n.prob));
    return { p, lit, next };
  });
}

/* 開頭一句：三步各一句（局面、下一步、準備） */
function storyLead(S, hz) {
  if (!S.active.length) return "目前沒有任何訊號亮著，沒有可以推演的方向。";
  const lit = storyLit(S).map((a) => scPlain(a.id, a.label));
  const ups = storyNext(S).filter((x) => x.lift >= 10).sort((a, b) => b.lift - a.lift).slice(0, 2);
  const H = S.hedge && S.hedge.targets && S.hedge.targets.length ? S.hedge : null;
  const prep = (() => {
    if (!H) return "";
    const tgt = storyHedgeTarget(H);
    const T = tgt && hgPrefer(H, tgt.id), b = T && hgBest(T);
    return b ? `準備：${scPlain(tgt.id, tgt.label)}時，過去最常一起漲的是${hgName(b)}。` : "";
  })();
  const v = S.backtest[String(hz)].ridge.verdict;
  return `現在：${lit.slice(0, 4).join("、")}${lit.length > 4 ? ` 等 ${lit.length} 件事` : ""}。`
    + (ups.length ? `接下來比平常更可能的是${ups.map((u) => `「${scPlain(u.n.trigger, u.n.label)}」（${S.within} 個月內 ${fmtNum(u.n.prob, 0)}%，平常 ${fmtNum(u.n.base, 0)}%）`).join("、")}。` : "")
    + prep + (v === "樣本外有效" ? "" : "「哪個標的會漲最多」的排行過去不穩定，不要照著買。");
}

// 要準備的下跌情境：機率比平常高最多的那個（正在發生的跳過，因為已經發生了）
function storyHedgeTarget(H) {
  const c = H.targets.filter((T) => T.odds && !T.odds.ongoing && fin(T.odds.prob) && fin(T.odds.base));
  return c.sort((a, b) => (b.odds.prob - b.odds.base) - (a.odds.prob - a.odds.base))[0] || H.targets[0];
}

function storyCard(S, hz) {
  const c = card({ title: "一頁看懂", span: 12, sub: "照四個問題排：現在怎樣、接下來可能怎樣、該怎麼準備、這些推論有多可靠。每一步怎麼算的，在下面的「研究細節」。" });
  const step = (no, title, ...kids) => h("section", { class: "st-step" }, h("div", { class: "st-no", "aria-hidden": "true" }, no), h("div", { class: "st-body" }, h("h4", { class: "st-h" }, title), ...kids));

  // ① 現在的局面
  const lit = storyLit(S);
  const groups = SC_THEMES.map((t) => [t, lit.filter((a) => (SC_PLAIN[a.id] || [, "其他"])[1] === t)]).filter(([, xs]) => xs.length);
  const other = lit.filter((a) => !SC_PLAIN[a.id]);
  if (other.length) groups.push(["其他", other]);
  const chains = storyChains(S);
  const s1 = step("1", "現在的局面",
    h("div", { class: "st-themes" }, groups.map(([t, xs]) => h("div", { class: "st-theme" }, h("span", { class: "st-tl" }, t),
      ...xs.map((a) => h("span", { class: "st-chip", title: `${a.label}（${a.current_at}）` }, scPlain(a.id, a.label),
        a.age && a.age.n_done && a.age.age > a.age.longest ? h("span", { class: "st-flag" }, `已 ${a.age.age} 個月，比過去都久`) : null))))),
    chains.length ? h("ul", { class: "st-list" }, chains.map(({ p, lit: L, next }) => h("li", {},
      h("b", {}, `「${SC_CHAIN_PLAIN[p.id] || p.name}」走到第 ${p.active}/${p.of} 步：`),
      L.map((n) => scPlain(n.trigger, n.label)).join(" → "),
      next ? h("span", {}, " → 下一步通常是", h("b", {}, `「${scPlain(next.trigger, next.label)}」`)) : null,
      h("div", { class: "st-why" }, SC_CHAIN_WHY[p.id] || p.thesis)))) : null,
    S.similar && S.similar.length ? h("p", { class: "st-note" },
      `過去最像現在的是 ${S.similar[0].m}，但亮著的訊號只有約 ${fmtNum(S.similar[0].jaccard * 100, 0)}% 相同——沒有一模一樣的前例，下面的數字都是把各訊號的歷史拼起來推估的。`) : null);

  // ② 接下來可能發生什麼
  const nx = storyNext(S);
  const more = nx.filter((x) => x.lift >= 10).sort((a, b) => b.lift - a.lift).slice(0, 3);
  const less = nx.filter((x) => x.lift <= -10).sort((a, b) => a.lift - b.lift).slice(0, 2);
  const bar = (x) => h("div", { class: "st-row" },
    h("span", { class: "st-name" }, scPlain(x.n.trigger, x.n.label), h("span", { class: "sub" }, `接在「${scPlain((x.p.nodes.find((m) => m.label === x.n.after) || {}).trigger, x.n.after)}」之後`)),
    h("span", { class: "st-bar", role: "img", "aria-label": `${S.within} 個月內 ${x.n.prob}%，平常 ${x.n.base}%` },
      h("i", { class: `fill${x.lift > 0 ? " more" : ""}`, style: `width:${x.n.prob}%` }), h("i", { class: "base", style: `left:${x.n.base}%` })),
    h("span", { class: "st-pct" }, h("b", {}, `${fmtNum(x.n.prob, 0)}%`), h("span", { class: "muted" }, ` 平常 ${fmtNum(x.n.base, 0)}%`)));
  const s2 = step("2", `接下來 ${S.within} 個月可能發生什麼`,
    more.length ? h("div", { class: "st-bars" }, h("div", { class: "st-cap" }, "比平常更可能"), ...more.map(bar)) : h("p", { class: "st-note" }, "沒有哪一步明顯比平常更可能。"),
    less.length ? h("div", { class: "st-bars" }, h("div", { class: "st-cap" }, "比平常更不可能"), ...less.map(bar)) : null,
    h("p", { class: "st-note" }, `「平常」＝不看任何訊號，隨便哪個月之後 ${S.within} 個月內發生的比例；長條裡的細線就是平常。這些比例來自過去幾十次類似的情況，不是預測。`));

  // ③ 該怎麼準備
  const HG = S.hedge && S.hedge.targets && S.hedge.targets.length ? S.hedge : null;
  let s3kids = [];
  if (HG) {
    const tgt = storyHedgeTarget(HG);
    const T = hgPrefer(HG, tgt.id), b = T && hgBest(T);
    if (b) {
      const st = hgStats(b, hgSubset(T, "all"));
      const since = st.n < T.n ? hgSince(T, b) : null;
      const pairs = T.episodes.map((e, i) => [e.ret, b.rets[i]]).filter(([a, r]) => fin(a) && fin(r));
      const w = 0.2, k = HG.mix_w.indexOf(20);
      const m0 = hgMedian(pairs.map(([a]) => a)), m1 = hgMedian(pairs.map(([a, r]) => (1 - w) * a + w * r));
      const c0 = b.calm_mix && b.calm_mix[0], c1 = b.calm_mix && k >= 0 ? b.calm_mix[k] : null;
      const o = tgt.odds || {};
      s3kids.push(h("p", { class: "st-big" },
        `如果「${scPlain(tgt.id, tgt.label)}」真的發生${fin(o.prob) ? `（${S.within} 個月內 ${fmtNum(o.prob, 0)}%）` : ""}，過去最常同時上漲的是 `,
        h("b", {}, hgName(b)), `：${since ? `${since} 年以來` : ""} ${st.n} 次裡 ${st.up} 次。`),
        fin(m0) && fin(m1) ? h("div", { class: "st-mix" },
          h("div", {}, h("span", { class: "st-tl" }, `把 20% 換成${hgName(b)}`)),
          h("div", { class: "st-mixv" }, h("span", {}, "跌的時候（中位）"), h("b", {}, chg(m0, 1, "%"), " → ", chg(m1, 1, "%")),
            h("span", { class: "muted" }, `少跌約 ${fmtNum(Math.abs(m1 - m0), 1)} 個百分點`)),
          fin(c0) && fin(c1) ? h("div", { class: "st-mixv" }, h("span", {}, "平常（中位）"), h("b", {}, chg(c0, 1, "%"), " → ", chg(c1, 1, "%")),
            h("span", { class: "muted" }, `少賺約 ${fmtNum(Math.abs(c0 - c1), 1)} 個百分點`)) : null) : null);
      const bond = T.hedges.find((x) => x.key === "VUSTX" || x.key === "b_ust_long");
      const R = HG.regime;
      if (bond && bond !== b && R && R.lit) {
        const a1 = hgStats(bond, hgSubset(T, "all")), a2 = hgStats(bond, hgSubset(T, "regime"));
        if (a2.n && a2.up / a2.n < a1.up / a1.n - 0.1) {
          s3kids.push(h("p", { class: "st-note" }, `很多人會想到美國長債：平常 ${a1.up}/${a1.n} 次會漲，但像現在這樣「${R.short}」開始的下跌只有 ${a2.up}/${a2.n} 次——利率上升時股債常一起跌。`));
        }
      }
    }
  }
  const v = S.backtest[String(hz)].ridge.verdict;
  s3kids.push(h("p", { class: "st-note" }, h("b", {}, "要不要照「期望值排行」去買？"),
    v === "樣本外有效" ? `${hz} 個月的排行過去在回測裡有效，可以參考，但訊號是事後設計的，實際效果可能比較差。`
      : `不要。${hz} 個月的排行在過去的回測裡${v === "時好時壞" ? "時好時壞" : "沒有比亂選好"}，只能當研究線索。`));
  const s3 = step("3", "該怎麼準備", ...s3kids);

  // ④ 這些推論有多可靠
  const CS = S.case_summary || {}, ly = CS.layers || {};
  const B = S.backtest[String(hz)].ridge;
  const rows = [];
  if (ly.n) rows.push(["第 2 步的機率（接下來可能發生什麼）", ly.skill > 0 ? ["有一點用", "meh"] : ["參考價值低", "bad"],
    `拿過去 ${ly.n} 次類似時點來對答案，${ly.skill > 0 ? "比直接用「平常」的比例準一點" : "沒有比直接用「平常」的比例準"}。`]);
  if (HG) {
    const tgt = storyHedgeTarget(HG), T = hgPrefer(HG, tgt.id), b = T && hgBest(T);
    const sb = b && hgStats(b, hgSubset(T, "all"));
    if (b) rows.push([`第 3 步的避險（${hgName(b)}）`, fin(b.p) && b.p <= 0.01 ? ["過去最一致", "ok"] : fin(b.p) && b.p <= 0.05 ? ["還算一致", "meh"] : ["看不出來", "bad"],
      `${sb.n} 次下跌裡 ${sb.up} 次上漲；隨便挑同樣長的期間很少這麼一致（${scP(b.p)}）。${T.L ? "高點低點是事後才知道的，這是描述不是訊號。" : ""}`]);
  }
  rows.push([`期望值排行（${hz} 個月）`, [v === "樣本外有效" ? "可以參考" : v === "時好時壞" ? "時好時壞" : "無效", SC_VERDICT_TONE[v] || "bad"],
    `從 ${S.backtest[String(hz)].start} 起每個月只用當時的資料重算，前 ${S.model.topk} 名平均每期多 ${fmtSigned(B.mean, 2)} 個百分點，不同起始月 ${scRange(B.offsets)}。`]);
  const s4 = step("4", "這些推論有多可靠",
    h("div", { class: "st-rel" }, rows.map(([what, [word, tone], why]) => h("div", { class: "st-relrow" },
      h("span", { class: "st-relw" }, what), h("span", { class: `pill pill-${tone}` }, word), h("span", { class: "st-relwhy" }, why)))),
    h("p", { class: "st-note" }, "全部是歷史統計，不是投資建議，也沒有算交易成本。"));

  c.body.append(h("div", { class: "st-steps" }, s1, s2, s3, s4));
  return c;
}
