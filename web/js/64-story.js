/* 沙盤推演的「一頁看懂」（2026-10-03）：使用者說推演總結「看不懂」——原本照研究步驟排（訊號、鏈、模型、回測），
   名稱是門檻（「日本 10 年殖利率 6 個月上升 ≥ 20bp」），標題講期望值、內文又說期望值不能用。
   同日使用者再要求「先寫可能會發生什麼，點開再寫原因跟判斷過程」：卡片只列「可能會發生的事」（一行一件、機率對照平常），
   點開才有為什麼（哪條鏈、走到哪一步）、怎麼判斷的（過去幾次、12 個月對照）、可信度、真的發生怎麼準備；
   現在的局面收在最後的「根據什麼」。原本的卡片原封不動放在下面的「研究細節」。全部由資料組出來。 */

// 訊號的白話名稱與主題（門檻原文放在小字）
const SC_PLAIN = {
  dollar_dxy: ["美元走強", "匯率"], dollar_hsi: ["港股下跌", "股市"], dollar_copper: ["銅價下跌", "原物料"],
  dollar_agri: ["農產品下跌", "原物料"], dollar_ust: ["美國長債上漲（利率下降）", "利率"],
  carry_jgb: ["日本利率上升", "利率"], carry_jpy: ["日圓轉強", "匯率"], carry_spx: ["美股下跌", "股市"],
  carry_sox: ["半導體股下跌", "股市"], carry_twii: ["台股下跌", "股市"],
  inflation_oil: ["油價大漲", "原物料"], inflation_ust10: ["美國長期利率上升", "利率"], inflation_ndx: ["科技股下跌", "股市"],
  inflation_curve: ["美國長短期利率差距很小（0.5 個百分點以下）", "利率"], inflation_gold: ["黃金上漲", "原物料"],
  fertilizer_gas: ["歐洲天然氣大漲", "原物料"], fertilizer_urea: ["肥料（尿素）大漲", "原物料"],
  fertilizer_agri: ["農產品上漲", "原物料"], fertilizer_ust3m: ["美國短期利率上升（升息）", "利率"],
  cycle_cuau: ["銅比黃金強（實體需求回溫）", "原物料"], cycle_sox: ["半導體股大漲", "股市"], cycle_twii: ["台股上漲", "股市"],
  cycle_twd: ["新台幣轉強", "匯率"], cycle_hy: ["高收益債上漲（市場敢冒險）", "信用與恐慌"],
  panic_vix: ["市場恐慌（VIX 30 以上）", "信用與恐慌"], panic_hy: ["高收益債下跌（信用緊張）", "信用與恐慌"],
  panic_spx: ["美股大跌", "股市"], panic_twii: ["台股大跌", "股市"],
  china_cny: ["人民幣走弱", "匯率"], china_hsi: ["港股下跌", "股市"], china_metals: ["金屬價格下跌", "原物料"],
  curve_inv: ["美國殖利率曲線倒掛", "利率"], vix_25: ["市場緊張（VIX 25 以上）", "信用與恐慌"],
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
  carry: "日圓是低利借錢的貨幣：日本利率上升讓借日圓變貴，借日圓去投資別的資產的人（套利交易）被迫賣掉資產還錢，先賣美股，再擴散到半導體和台股。",
  inflation: "油價是通膨最直接的來源：油價急漲推高長期利率，利率高會壓低成長股的股價，資金轉向黃金避險。",
  fertilizer: "氮肥是用天然氣做的：天然氣漲 → 肥料漲 → 糧價漲 → 通膨 → 可能升息（課堂上提到的連鎖反應）。",
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
    const lift = stPA(n) - n.base;                      // 2026-10-03 起用校準後（往平常收縮）的機率
    if (!by.has(key) || Math.abs(lift) > Math.abs(by.get(key).lift)) by.set(key, { p, n, lift });
  }
  return [...by.values()];
}
// 校準後的機率（往平常收縮；沒有就用原始）
const stPA = (n) => (fin(n.prob_adj) ? n.prob_adj : n.prob);
const stPA12 = (n) => (fin(n.prob12_adj) ? n.prob12_adj : n.prob12);
const ST_GAP = 5;            // 校準後和平常差 ≥ 5 個百分點才算「更可能」（和 config.SCENARIO_LIFT_GAP 一致）
// 「比平常更可能」這類提示回頭對答案的結果：2005 年起每個月走步對答案（幾百次），不是只看 12 個案例。卡片上要常駐。
function storyReliab(S) {
  const rc = S.reliability && S.reliability.chain;
  if (rc && rc.more && rc.more.n >= 30) {
    const m = rc.more, l = rc.less;
    const good = m.consistent && m.realized - m.base >= 3;
    return { word: good ? "方向有參考價值" : "參考價值低", tone: good ? "ok" : "bad",
      text: `2005 年起每個月回頭對答案（${rc.n} 次）：「比平常更可能」的提示有 ${m.n} 次，實際發生 ${fmtNum(m.realized, 0)}%、平常 ${fmtNum(m.base, 0)}%${m.consistent ? "，前後半都成立" : "，但前後半不一致"}。`
        + `機率數字已照段數往平常收縮（校準後各段的實際發生率對得上，原始數字會高估）。「更不可能」的提示過去${l && l.consistent ? "也成立" : "沒有參考價值"}。`,
      lessOk: !!(l && l.consistent) };
  }
  const ly = (S.case_summary || {}).layers || {};
  if (!ly.n) return null;
  return ly.skill > 0 ? { word: "有一點參考價值", tone: "meh", text: `拿過去 ${ly.n} 次類似時點回頭對答案，這類比例比直接用「平常」準一點。`, lessOk: false }
    : { word: "參考價值低", tone: "bad", text: `拿過去 ${ly.n} 次類似時點回頭對答案，這類比例沒有比直接用「平常」準。`, lessOk: false };
}
const storyDiff = (x) => (x >= 0 ? `多 ${fmtNum(x, 2)}` : `少 ${fmtNum(-x, 2)}`);

/* 開頭一句：先講可能發生什麼（附可信度），再講下跌時什麼擋得住，最後講排行 */
function storyLead(S, hz) {
  if (!S.active.length) return "目前沒有任何訊號亮著，沒有可以推演的方向。";
  const ups = storyNext(S).filter((x) => x.lift >= ST_GAP).sort((a, b) => b.lift - a.lift).slice(0, 3);
  const R = storyReliab(S);
  const H = S.hedge && S.hedge.targets && S.hedge.targets.length ? S.hedge : null;
  const prep = (() => {
    if (!H) return "";
    const tgt = storyHedgeTarget(H);
    const T = tgt && hgPrefer(H, tgt.id), b = T && hgBest(T);
    if (!b) return "";
    const st = hgStats(b, hgSubset(T, "all")), since = st.n < T.n ? hgSince(T, b) : null;
    return `過去${scPlain(tgt.id, tgt.label)}時，最常一起漲的是${hgName(b)}（${since ? `${since} 年起、` : ""}回頭看）。`;
  })();
  const v = S.backtest[String(hz)].ridge.verdict;
  return (ups.length ? `接下來 ${S.within} 個月比平常更可能：${ups.map((u) => `${scPlain(u.n.trigger, u.n.label)}（${fmtNum(stPA(u.n), 0)}%，平常 ${fmtNum(u.n.base, 0)}%）`).join("、")}。`
    + (R ? (R.word === "方向有參考價值" ? `這類「更可能」的提示過去實際發生率比平常高，方向有參考價值；機率數字已校準。` : `不過這類比例回頭對答案${R.word === "參考價值低" ? "參考價值低" : "只有一點參考價值"}。`) : "")
    : `接下來 ${S.within} 個月沒有哪件事明顯比平常更可能。`)
    + prep + (v === "樣本外有效" ? "" : "「哪個標的會漲最多」沒有可靠的答案。");
}

// 要準備的下跌情境：機率比平常高最多的那個（正在發生的跳過，因為已經發生了）
function storyHedgeTarget(H) {
  const c = H.targets.filter((T) => T.odds && !T.odds.ongoing && fin(T.odds.prob) && fin(T.odds.base));
  return c.sort((a, b) => (b.odds.prob - b.odds.base) - (a.odds.prob - a.odds.base))[0] || H.targets[0];
}

// 下跌情境：過去這種下跌時什麼一起漲、換 20% 的回頭試算、利率上行時美長債的提醒（描述，不是建議）
function storyHedge(S, tid) {
  const HG = S.hedge && S.hedge.targets && S.hedge.targets.length ? S.hedge : null;
  const M = HG && HG.targets.find((T) => T.id === tid);
  if (!M) return null;
  const T = hgPrefer(HG, tid), b = hgBest(T);
  if (!b) return null;
  const st = hgStats(b, hgSubset(T, "all"));
  const since = st.n < T.n ? hgSince(T, b) : null;
  const what = T.L ? `${scPlain(tid, M.label).replace(/下跌$/, "")}從高點跌 ${T.thr}% 以上` : scPlain(tid, M.label);
  const pairs = T.episodes.map((e, i) => [e.ret, b.rets[i]]).filter(([a, r]) => fin(a) && fin(r));
  const k = HG.mix_w.indexOf(20);
  const r1 = (v) => Math.round(v * 10) / 10;            // 和畫面上的一位小數一致，差距才不會差 0.1
  const m0 = r1(hgMedian(pairs.map(([a]) => a))), m1 = r1(hgMedian(pairs.map(([a, r]) => 0.8 * a + 0.2 * r)));
  const c0 = b.calm_mix && fin(b.calm_mix[0]) ? r1(b.calm_mix[0]) : null, c1 = b.calm_mix && k >= 0 && fin(b.calm_mix[k]) ? r1(b.calm_mix[k]) : null;
  const out = { b, st, short: `過去${what}時，${hgName(b)} ${st.n} 次裡 ${st.up} 次一起漲${since ? `（${since} 年起）` : ""}`, nodes: [] };
  out.nodes.push(h("p", {}, `用每天的價格，看過去每一次${what}（從高點到低點）：`, h("b", {}, hgName(b)),
    `${since ? ` ${since} 年以來` : ""}的 ${st.n} 次裡，有 ${st.up} 次同時上漲。`));
  if (fin(m0) && fin(m1)) {
    out.nodes.push(h("div", { class: "st-mix" },
      h("div", {}, h("span", { class: "st-tl" }, `回頭試算：如果原本把 20% 放在${hgName(b)}（不是建議）`)),
      h("div", { class: "st-mixv" }, h("span", {}, "跌的時候，典型的一次"), h("b", {}, chg(m0, 1, "%"), " → ", chg(m1, 1, "%")),
        h("span", { class: "muted" }, `少跌約 ${fmtNum(Math.abs(m1 - m0), 1)} 個百分點`)),
      fin(c0) && fin(c1) ? h("div", { class: "st-mixv" }, h("span", {}, `沒在跌的時候，典型的一段（${T.L ? `${T.L} 個交易日` : "3 個月"}）`),
        h("b", {}, chg(c0, 1, "%"), " → ", chg(c1, 1, "%")), h("span", { class: "muted" }, `少賺約 ${fmtNum(Math.abs(c0 - c1), 1)} 個百分點（這是代價）`)) : null));
  }
  const bond = T.hedges.find((x) => x.key === "VUSTX" || x.key === "b_ust_long");
  const R = HG.regime;
  if (bond && bond !== b && R && R.lit) {
    const a1 = hgStats(bond, hgSubset(T, "all")), a2 = hgStats(bond, hgSubset(T, "regime"));
    if (a2.n && a2.up / a2.n < a1.up / a1.n - 0.1) {
      out.nodes.push(h("p", {}, `很多人會想到美國長債：在這 ${a1.n} 次下跌裡它有 ${a1.up} 次上漲；但像現在這樣「${R.short}」開始的 ${a2.n} 次，只有 ${a2.up} 次上漲、${a2.n - a2.up} 次跟著跌——利率上升時，長債比較擋不住。`));
    }
  }
  out.nodes.push(h("p", { class: "muted" }, `${T.L ? "高點和低點是事後才知道的，這是回頭描述，不是進出場訊號。" : ""}完整的比較在「避險」檢視。`));
  return out;
}

function storyCard(S, hz) {
  const R = storyReliab(S);
  const c = card({ title: "可能會發生什麼", span: 12,
    sub: `接下來 ${S.within} 個月，和「平常」比起來比較可能、或比較不可能發生的事。「平常」＝不看任何訊號、隨便挑一個月，之後 ${S.within} 個月內發生的比例（長條裡的細線）。點一行看原因和判斷過程。` });
  if (R) c.body.append(h("p", { class: `sc-banner t-${R.tone}` }, h("b", {}, `可信度：${R.word}。`), `${R.text}這些是過去類似情況的比例，不是預測。`));
  const nameOf = (p, label) => scPlain((p.nodes.find((m) => m.label === label) || {}).trigger, label);

  const item = (x) => {
    const { p, n } = x;
    const more = x.lift > 0;
    const hedge = more ? storyHedge(S, n.trigger) : null;
    const after = nameOf(p, n.after);
    const sum = h("summary", { class: "st-sum" },
      h("span", { class: "st-name" }, scPlain(n.trigger, n.label),
        h("span", { class: "sub" }, `接在「${after}」之後${fin(n.prob12) ? `・12 個月內 ${fmtNum(stPA12(n), 0)}%（平常 ${fmtNum(n.base12, 0)}%）` : ""}`)),
      h("span", { class: "st-bar", role: "img", "aria-label": `${S.within} 個月內 ${stPA(n)}%（校準後），平常 ${n.base}%` },
        h("i", { class: `fill${more ? " more" : ""}`, style: `width:${stPA(n)}%` }), h("i", { class: "base", style: `left:${n.base}%` })),
      h("span", { class: "st-pct", title: fin(n.prob_adj) ? `校準後；原始 ${fmtNum(n.prob, 0)}%（${n.n_episodes} 段，往平常收縮）` : "" }, h("b", {}, `${fmtNum(stPA(n), 0)}%`), h("span", { class: "muted" }, ` 平常 ${fmtNum(n.base, 0)}%`)),
      hedge ? h("span", { class: "st-prep" }, `${hedge.short}・回頭看`) : null);
    const det = h("details", { class: "st-item" }, sum);
    det.addEventListener("toggle", () => {
      if (!det.open || det.childElementCount > 1) return;
      const idx = p.nodes.indexOf(n);
      const steps = p.nodes.slice(0, idx + 1).map((m, i) => h("span", { class: `st-step-pill${m.triggered ? " on" : i === idx ? " here" : ""}` },
        scPlain(m.trigger, m.label), h("small", {}, m.triggered ? "已發生" : i === idx ? "這一步" : "還沒")));
      const others = S.paths.filter((q) => q !== p && q.nodes.some((m) => m.trigger === n.trigger && !m.triggered && fin(m.prob)));
      const me = scPlain(n.trigger, n.label);
      const near12 = fin(n.prob12) && fin(n.base12) && Math.abs(stPA12(n) - n.base12) < 5;
      const read12 = !near12 ? "。" : more ? "——時間拉長就和平常差不多，比較像「比較早發生」，不是「比較會發生」。"
        : "——時間拉長就和平常差不多，比較像「比較晚發生」，不是「比較不會發生」。";
      det.append(h("div", { class: "st-detail" },
        h("h5", {}, "為什麼"),
        h("div", { class: "st-chain" }, h("span", { class: "st-tl" }, `「${SC_CHAIN_PLAIN[p.id] || p.name}」這條連鎖反應`),
          ...steps.flatMap((el, i) => (i ? [h("span", { class: "st-arrow", "aria-hidden": "true" }, "→"), el] : [el]))),
        h("p", {}, SC_CHAIN_WHY[p.id] || p.thesis),
        others.length ? h("p", { class: "muted" }, `它也出現在${others.map((q) => { const m = q.nodes.find((y) => y.trigger === n.trigger);
          return `「${SC_CHAIN_PLAIN[q.id] || q.name}」（${fmtNum(m.prob, 0)}%，平常 ${fmtNum(m.base, 0)}%）`; }).join("、")}；上面的數字取和平常差最多的那條。`) : null,
        h("h5", {}, "怎麼判斷的"),
        h("ul", { class: "st-ul" },
          h("li", {}, `過去有 ${n.n_episodes} 段（${n.n_months} 個月），「${after}」已經發生、「${me}」還沒發生。`),
          h("li", {}, `這些月份裡，${S.within} 個月內「${me}」真的發生的有 ${fmtNum(n.prob, 0)}%。`),
          fin(n.prob_adj) ? h("li", {}, `只有 ${n.n_episodes} 段，把它往平常拉一點（校準）：${fmtNum(n.prob_adj, 0)}%——頁面上用這個數字。校準後的數字過去對得上實際發生率，原始數字會高估。`) : null,
          h("li", {}, `隨便挑一個月來看是 ${fmtNum(n.base, 0)}%——這就是「平常」。`),
          fin(n.wait) ? h("li", {}, `真的發生的話，通常在第 ${fmtNum(n.wait, 0)} 個月。`) : null,
          fin(n.prob12) ? h("li", {}, `拉長到 12 個月：${fmtNum(stPA12(n), 0)}%（校準後），平常 ${fmtNum(n.base12, 0)}%${read12}`) : null),
        h("h5", {}, "可信度"),
        h("p", {}, `${n.n_episodes} 次不算多（通常要幾十次以上才比較穩）。${R ? `${R.text.replace(/。$/, "")}——${R.word}。` : ""}`),
        hedge ? [h("h5", {}, "如果真的發生，過去什麼擋得住"), ...hedge.nodes] : null,
        ...tgOutcomeExtra(S, n, hedge)));
    });
    return det;
  };

  const nx = storyNext(S);
  const more = nx.filter((x) => x.lift >= ST_GAP).sort((a, b) => b.lift - a.lift).slice(0, 4);
  const less = nx.filter((x) => x.lift <= -ST_GAP).sort((a, b) => a.lift - b.lift).slice(0, 2);
  const B = S.backtest[String(hz)].ridge, v = B.verdict;
  const rank = h("details", { class: "st-item" },
    h("summary", { class: "st-sum st-sum-rank" }, h("span", { class: "st-name" }, `哪個標的接下來 ${hz} 個月漲最多？`),
      h("span", { class: "st-ans" }, v === "樣本外有效" ? "有一點參考價值" : "沒有可靠的答案"),
      h("span", { class: `pill pill-${SC_VERDICT_TONE[v] || "bad"}` }, v === "樣本外有效" ? "可以參考" : v === "時好時壞" ? "時好時壞" : "無效")),
    h("div", { class: "st-detail" },
      h("h5", {}, "怎麼判斷的"),
      h("ul", { class: "st-ul" },
        h("li", {}, `從 ${S.backtest[String(hz)].start} 起，每個月只用當時已經知道的資料，重算一次「接下來 ${hz} 個月誰漲最多」的排行。`),
        h("li", {}, `每次買排行前 ${S.model.topk} 名，${hz} 個月後和全部標的的平均比。`),
        h("li", {}, `結果平均每次只${storyDiff(B.mean)} 個百分點，而且換不同的起始月份，從 ${scRange(B.offsets)} 都有。`)),
      h("p", {}, v === "樣本外有效" ? "回測裡有效，但訊號和門檻是事後設計的，實際效果可能比較差。" : "所以排行只能當研究線索，不要照著買。"),
      h("p", { class: "muted" }, "完整的排行和每個標的的原因在下面「研究細節」的期望值排行。")));

  // 根據什麼：現在正在發生的事
  const lit = storyLit(S);
  const groups = SC_THEMES.map((t) => [t, lit.filter((a) => (SC_PLAIN[a.id] || [, "其他"])[1] === t)]).filter(([, xs]) => xs.length);
  const other = lit.filter((a) => !SC_PLAIN[a.id]);
  if (other.length) groups.push(["其他", other]);
  const basis = moreBox(`根據什麼：現在正在發生的 ${lit.length} 件事`,
    h("div", { class: "st-themes" }, groups.map(([t, xs]) => h("div", { class: "st-theme" }, h("span", { class: "st-tl" }, t),
      ...xs.map((a) => h("span", { class: "st-chip", title: `${a.label}（${a.current_at}）` }, scPlain(a.id, a.label),
        a.age && a.age.n_done && a.age.age > a.age.longest ? h("span", { class: "st-flag" }, `已 ${a.age.age} 個月，比過去都久`) : null))))),
    S.similar && S.similar.length ? h("p", {}, `過去最像現在的是 ${S.similar[0].m}，但正在發生的事只有約 ${fmtNum(S.similar[0].jaccard * 100, 0)}% 相同——沒有一模一樣的前例，上面的比例是把每件事各自的歷史拼起來的。`) : null);

  c.body.append(
    more.length ? h("div", { class: "st-group" }, h("div", { class: "st-cap" }, "比平常更可能"), ...more.map(item)) : h("p", { class: "st-note" }, "沒有哪件事明顯比平常更可能。"),
    less.length ? h("div", { class: "st-group" }, h("div", { class: "st-cap" }, R && !R.lessOk ? "比平常更不可能（這個方向回頭對答案沒有參考價值，只是列出來）" : "比平常更不可能"), ...less.map(item)) : null,
    h("div", { class: "st-group" }, h("div", { class: "st-cap" }, "其他問題"), rank),
    h("p", { class: "st-note" }, "全部是歷史統計，不是投資建議。"),
    basis);
  return c;
}
