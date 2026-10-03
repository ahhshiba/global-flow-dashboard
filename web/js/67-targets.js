/* 確切標的、低基期、更詳細的推演（2026-10-03）。資料在 gfd/targets.py（scenario.targets）。
   1. 每個「可能會發生的事」點開後多兩段：通常多深、多久（幅度與等待的分布）；確切標的（會跟著動的、過去擋得住的）。
   2. 「確切標的」卡片：每個資產對應的 ETF／股票現在在哪裡（10 年位階、離高點、低基期標籤），
      三個角度各自看 3／6／12 個月（模型、相似時點、低基期的歷史），一致才算方向明確。
   全部是歷史統計，不是投資建議。 */

const TG_BASE_TONE = { "低基期": "ok", "高檔回落": "meh", "高基期": "warn", "中間": null };
const TG_VERDICT_TONE = { "三個角度都偏多": "ok", "三個角度都偏空": "ok", "偏多": "meh", "偏空": "meh", "方向不一致": "bad", "沒有足夠的角度": "bad" };
const TG_MARKET = { us: "美國", tw: "台灣", cash: "現金" };
const tgData = (S) => (S && S.targets && S.targets.assets ? S.targets : null);
const tgKey = (x) => (x.inverse ? `${x.sid}~inv` : x.sid);        // 避險資料列 → 資產鍵
const tgPct = (v, d = 1) => (fin(v) ? fmtSigned(v, d, "%") : "—");
const tgArrow = (d) => (d > 0 ? "↑" : d < 0 ? "↓" : "→");
const TG_GAP = 2;                 // 相似時點／位階：典型值要比平常差 2 個百分點以上才算有方向（和 gfd/targets.py 一致）
const tgGloss = (id, label) => h("button", { class: "gl-rel", type: "button", onclick: () => window.gotoTab("glossary", () => { window.glPending = id; }) }, label);

// 標的的小籤：代碼＋位置標籤
function tgChip(t) {
  const tone = TG_BASE_TONE[t.base];
  return h("span", { class: "tg-chip", title: `${t.name}${t.note ? "：" + t.note : ""}（${t.base_why}）` },
    h("b", {}, t.sym), h("span", { class: "muted" }, ` ${t.name}`),
    tone ? h("span", { class: `pill pill-${tone}` }, t.base) : null,
    t.track_ok === false ? h("span", { class: "pill pill-bad", title: `和底層資產的月報酬相關只有 ${t.track}，不是同一件事` }, "追蹤不佳") : null);
}

// 一個資產在某個期間，三個角度各一句（白話）
function tgViews(A, hz) {
  const out = [];
  const m = A.model && A.model[String(hz)];
  if (m && (m.cal != null || m.ev != null)) {
    const v = m.cal != null ? m.cal : m.ev;
    const invalid = m.verdict === "樣本外無效";
    const clear = fin(m.lo) && fin(m.hi) && (m.lo > 0 || m.hi < 0);
    out.push({ name: "模型", dir: !invalid && clear && Math.abs(v) >= 0.5 ? Math.sign(v) : 0, value: invalid ? "無效" : tgPct(v), base: null,
      text: invalid ? `這個期間的模型在回測裡沒有比亂選好，不給數字`
        : `模型估計之後 ${hz} 個月比它平常${v < 0 ? "少" : "多"} ${fmtNum(Math.abs(v), 1)} 個百分點${m.cal != null ? `（已依過去的實際表現打折；打折前 ${tgPct(m.ev)}）` : ""}。打折前的可能範圍 ${tgPct(m.lo)}～${tgPct(m.hi)}${clear ? "" : "，跨過 0，算不出方向"}。這個模型在回測裡${m.verdict}`,
      weak: m.verdict !== "樣本外有效" });
  }
  const s = A.similar && A.similar[String(hz)];
  if (s && s.n_episodes) {
    const d = s.all ? s.median - s.all.median : null;
    out.push({ name: "相似時點", dir: fin(d) && Math.abs(d) >= TG_GAP ? Math.sign(d) : 0, value: tgPct(s.median), base: tgPct(s.all && s.all.median),
      text: `過去和現在最像的 ${s.n_episodes} 段（${s.n} 個月），之後 ${hz} 個月典型 ${tgPct(s.median)}（10～90%：${tgPct(s.p10)}～${tgPct(s.p90)}），${fmtNum(s.hit, 0)}% 的時候上漲；平常典型 ${tgPct(s.all && s.all.median)}、${fmtNum(s.all && s.all.hit, 0)}% 上漲`,
      weak: s.n_episodes < 5 });
  }
  const L = A.lowbase, hh = hz === 3 ? "6" : String(hz);
  if (L && L.hist[hh]) {
    const row = L.hist[hh].buckets.find((b) => b.bucket === L.bucket), all = L.hist[hh].all;
    if (row && row.n) {
      const d = all ? row.median - all.median : null;
      out.push({ name: hz === 3 ? "位階（6 個月）" : "位階", dir: fin(d) && Math.abs(d) >= TG_GAP ? Math.sign(d) : 0, value: tgPct(row.median), base: tgPct(all && all.median),
        text: `現在的 10 年位階 ${fmtNum(L.pct, 0)}%（${L.bucket}）；過去在這一段的 ${row.n_episodes} 段，之後 ${hh} 個月典型 ${tgPct(row.median)}、${fmtNum(row.hit, 0)}% 上漲；平常 ${tgPct(all && all.median)}${hz === 3 ? "（位階只看 6 與 12 個月）" : ""}`,
        weak: row.n_episodes < 5 });
    }
  }
  return out;
}

/* 可能會發生的事 → 點開多兩段：通常多深、多久；確切標的 */
function tgOutcomeExtra(S, n, hedge) {
  const T = tgData(S);
  if (!T) return [];
  const out = [];
  const o = T.outcomes[n.trigger];
  const me = scPlain(n.trigger, n.label);
  if (o && o.size) {
    const u = o.unit === "bp" ? "bp" : "%";
    const f = (v) => (fin(v) ? fmtSigned(v, u === "bp" ? 0 : 1, u) : "—");
    const W = o.wait.length, tot = o.wait.reduce((a, b) => a + b, 0);
    const soon = tot ? Math.round(100 * (o.wait[0] + (o.wait[1] || 0)) / tot) : null;
    const ext = o.cmp === ">=" ? "最高" : "最深";
    out.push(h("h5", {}, "真的發生的話，通常多深、多久"),
      h("ul", { class: "st-ul" },
        h("li", {}, `上面 ${o.n_episodes} 段裡真的發生的 ${o.n} 段：剛跨過門檻那個月的變動典型是 ${f(o.size.median)}（10～90%：${f(o.size.p10)}～${f(o.size.p90)}）。`),
        o.deep ? h("li", {}, `之後 3 個月內${ext}典型 ${f(o.deep.median)}（${f(o.deep.p10)}～${f(o.deep.p90)}）。`) : null,
        tot ? h("li", {}, `什麼時候發生（只算真的發生的那 ${o.n} 段）：`, h("span", { class: "tg-wait", role: "img", "aria-label": o.wait.map((c, i) => `第 ${i + 1} 個月 ${c} 段`).join("，") },
          ...o.wait.map((c, i) => h("span", { class: "tg-wbar" }, h("i", { style: `height:${Math.max(2, Math.round(28 * c / Math.max(...o.wait)))}px` }), h("small", {}, `${i + 1}月`), h("small", { class: "muted" }, String(c))))),
          soon != null ? ` 前兩個月就發生的佔 ${soon}%。` : "") : null));
  }
  const D = S.hedge && S.hedge.daily && S.hedge.daily.targets && S.hedge.daily.targets.find((x) => x.id === n.trigger);
  if (D && D.episodes && D.episodes.length >= 5) {
    const rets = D.episodes.map((e) => e.ret).filter(fin).sort((a, b) => a - b), days = D.episodes.map((e) => e.days).filter(fin).sort((a, b) => a - b);
    const q = (v, p) => v[Math.min(v.length - 1, Math.floor(v.length * p))];
    const li = h("li", {}, `用每天的價格看，${D.first.slice(0, 4)} 年以來從高點跌超過 ${D.thr}% 的有 ${D.n} 次：從高點到低點典型 ${tgPct(q(rets, 0.5))}（10～90%：${tgPct(q(rets, 0.1))}～${tgPct(q(rets, 0.9))}），`
      + `走 ${q(days, 0.5)} 個交易日（${q(days, 0.1)}～${q(days, 0.9)} 天）。`);
    const ul = out.length ? out[out.length - 1] : null;
    if (ul && ul.tagName === "UL") ul.append(li); else out.push(h("h5", {}, "真的發生的話，通常多深、多久"), h("ul", { class: "st-ul" }, li));
  }
  const A = T.assets[n.sid];
  const list = (title, a, note) => (a && a.tickers.length ? h("div", { class: "tg-list" }, h("span", { class: "st-tl" }, title), ...a.tickers.map(tgChip), note ? h("span", { class: "muted tg-note" }, note) : null) : null);
  const bad = A && A.tickers.some((t) => t.track_ok === false);
  const allBad = A && A.tickers.length && A.tickers.every((t) => t.track_ok === false);
  const lists = [];
  const isDown = /跌|貶|走弱|轉弱|下降/.test(me);
  if (A) lists.push(list(allBad ? "題材相近的（不是同一件事）" : isDown ? "會跟著跌的" : "會跟著動的", A, bad ? "標著「追蹤不佳」的和這件事不是同一個東西，只是題材相近；位置標籤是它自己的位置，不是這件事的訊號。" : null));
  if (hedge && hedge.b) {
    const HA = T.assets[tgKey(hedge.b)];
    if (HA) lists.push(list("過去擋得住的", HA, null));
  }
  if (lists.some(Boolean)) out.push(h("h5", {}, "確切標的"), ...lists.filter(Boolean),
    h("p", { class: "muted" }, "位置標籤：低基期＝10 年位階 25% 以下；高檔回落＝漲過又跌下來（離 3 年高點 20% 以上）；高基期＝位階 80% 以上且貼近高點。每檔的細節在下面「確切標的」卡片。"));
  return out;
}

/* 確切標的卡片 */
function targetsCard(S, hz) {
  const T = tgData(S);
  if (!T) return null;
  const c = card({ title: "確切標的：現在在哪裡、三個角度怎麼看", span: 12,
    sub: "每個資產對應到可以買的 ETF／股票／現金部位（美國與台灣）。位置＝它自己的 10 年位階與離 3 年高點多遠。"
      + "三個角度＝模型（沙盤推演的期望值，乘上樣本外的校準斜率）、相似時點（過去和現在最像的月份之後實際怎樣）、位階（它過去在同樣位階之後怎樣）；三個角度一致才算方向明確。期間跟上面的 3／6／12 個月切換。" });
  const bt = S.backtest[String(hz)].ridge.verdict;
  c.body.append(h("p", { class: "sc-banner t-bad" }, h("b", {}, "可信度："),
    `模型的排行在回測裡${bt}；相似時點只有十來段；位階每一段也只有幾段到十幾段。三個角度一致，也只是「過去類似情況多半這樣」，不是預測。標著「追蹤不佳」的標的，三個角度說的是原料或指數本身，不是那檔標的。`));
  const keys = Object.keys(T.assets);
  const pct = (k) => (T.assets[k].lowbase && fin(T.assets[k].lowbase.pct) ? T.assets[k].lowbase.pct : 999);
  keys.sort((a, b) => pct(a) - pct(b) || a.localeCompare(b));      // 只照位階排，不照判定排（不是排行榜）
  const lowKeys = keys.filter((k) => T.assets[k].tickers.some((t) => t.base === "低基期"));
  const pullKeys = keys.filter((k) => !lowKeys.includes(k) && T.assets[k].tickers.some((t) => t.base === "高檔回落"));
  const restKeys = keys.filter((k) => !lowKeys.includes(k) && !pullKeys.includes(k));
  const row = (k) => {
    const A = T.assets[k];
    const V = A.verdict && A.verdict[String(hz)];
    const views = A.kind === "price" ? tgViews(A, hz) : [];
    const sum = h("summary", { class: "tg-sum" },
      h("span", { class: "tg-name" }, A.inverse ? `日圓（對美元）` : A.name, h("span", { class: "sub" }, `10 年位階 ${A.lowbase && fin(A.lowbase.pct) ? fmtNum(A.lowbase.pct, 0) + "%" : "—"}（30 年 ${fin(A.pct30) ? fmtNum(A.pct30, 0) + "%" : "—"}）`
        + (() => { const t = A.tickers.find((t) => fin(t.status && t.status.pct10) && A.lowbase && fin(A.lowbase.pct) && Math.abs(t.status.pct10 - A.lowbase.pct) >= 20);
          return t ? `・${t.sym} 本身 ${fmtNum(t.status.pct10, 0)}%` : ""; })())),
      h("span", { class: "tg-chips" }, ...A.tickers.map(tgChip)),
      h("span", { class: "tg-views" }, views.map((v) => h("span", { class: `tg-v${v.weak ? " weak" : ""}`, title: v.text }, h("span", { class: "muted" }, v.name), ` ${tgArrow(v.dir)} ${v.value}`,
        v.base != null ? h("span", { class: "muted" }, `（平常 ${v.base}）`) : null))),
      V ? h("span", { class: "tg-verdict" }, h("span", { class: `pill pill-${TG_VERDICT_TONE[V.word] || "bad"}` }, V.word),
        A.tickers.length && A.tickers.every((t) => t.track_ok === false) ? h("span", { class: "sub" }, `只對${A.name}本身；標的不追蹤`) : null)
        : h("span", { class: "pill pill-bad" }, "殖利率，不排名"));
    const det = h("details", { class: "tg-item" }, sum);
    det.addEventListener("toggle", () => {
      if (!det.open || det.childElementCount > 1) return;
      const L = A.lowbase, hh = hz === 3 ? "6" : String(hz);
      det.append(h("div", { class: "st-detail" },
        h("h5", {}, "現在在哪裡"),
        h("div", { class: "tbl-wrap" }, h("table", { class: "data" },
          h("thead", {}, h("tr", {}, ["代碼", "名稱", "市場", "最新", "1 年", "離 3 年高點", "離歷史高點", "10 年位階", "離 200 日線", "位置", "追蹤"].map((t, i) => h("th", { class: i >= 3 && i <= 8 ? "n" : null }, t)))),
          h("tbody", {}, A.tickers.map((t) => { const s = t.status; return h("tr", {},
            h("td", {}, h("b", {}, t.sym), t.stale ? h("span", { class: "sub" }, "資料沿用上次") : null),
            h("td", {}, t.name, t.note ? h("span", { class: "sub" }, t.note) : null),
            h("td", {}, TG_MARKET[t.market] || t.market),
            h("td", { class: "n" }, fin(s.last) ? `${fmtNum(s.last, s.last < 100 ? 2 : 1)}${t.currency ? " " + t.currency : ""}` : "—", h("span", { class: "sub" }, s.date)),
            h("td", { class: "n" }, chg(s.c1y, 1, "%")), h("td", { class: "n" }, chg(s.dd_3y, 1, "%")),
            h("td", { class: "n" }, fin(s.dd_ath) ? [chg(s.dd_ath, 1, "%"), h("span", { class: "sub" }, s.ath_at)] : "—"),
            h("td", { class: "n" }, fin(s.pct10) ? `${fmtNum(s.pct10, 0)}%` : "—"), h("td", { class: "n" }, chg(s.ma200, 1, "%")),
            h("td", {}, TG_BASE_TONE[t.base] ? h("span", { class: `pill pill-${TG_BASE_TONE[t.base]}` }, t.base) : t.base),
            h("td", {}, t.track == null ? h("span", { class: "muted" }, t.market === "cash" ? "就是匯率本身" : "—")
              : h("span", { class: t.track_ok ? null : "down", title: `和「${A.name}」的月報酬相關（最近 ${t.track_n} 個月）` }, fmtNum(t.track, 2)))); })))),
        views.length ? [h("h5", {}, `三個角度（${hz} 個月）`), h("ul", { class: "st-ul" }, views.map((v) => h("li", {}, h("b", {}, `${v.name} ${tgArrow(v.dir)}`), `　${v.text}。`))),
          A.tickers.length && A.tickers.every((t) => t.track_ok === false) ? h("p", { class: "sc-banner t-bad" }, `上面三個角度看的是「${A.name}」本身；這裡的標的和它的月報酬相關都不到 0.5，只是題材相近，不能直接套用。`) : null] : null,
        L ? [h("h5", {}, "位階有沒有用：它過去在各個位階之後怎樣"),
          h("div", { class: "tbl-wrap" }, h("table", { class: "data" },
            h("thead", {}, h("tr", {}, ["10 年位階（當時）", "段數", `${hh} 個月典型`, "10～90%", "上漲比例"].map((t, i) => h("th", { class: i ? "n" : null }, t)))),
            h("tbody", {}, L.hist[hh].buckets.map((b) => h("tr", { class: b.bucket === L.bucket ? "sel" : null },
              h("td", {}, b.bucket, b.bucket === L.bucket ? h("span", { class: "sub" }, "現在在這裡") : null),
              h("td", { class: "n" }, String(b.n_episodes)), h("td", { class: "n" }, b.n ? chg(b.median, 1, "%") : "—"),
              h("td", { class: "n" }, b.n ? `${tgPct(b.p10)}～${tgPct(b.p90)}` : "—"), h("td", { class: "n" }, b.n ? `${fmtNum(b.hit, 0)}%` : "—"))),
              L.hist[hh].all ? h("tr", {}, h("td", {}, "平常（全部月份）"), h("td", { class: "n" }, "—"), h("td", { class: "n" }, chg(L.hist[hh].all.median, 1, "%")),
                h("td", { class: "n" }, `${tgPct(L.hist[hh].all.p10)}～${tgPct(L.hist[hh].all.p90)}`), h("td", { class: "n" }, `${fmtNum(L.hist[hh].all.hit, 0)}%`)) : null))),
          h("p", { class: "muted" }, "位階用當時往前 10 年算，不偷看之後的資料；台股、美股這類長期上漲的資產，低位階多半是大跌之後，段數很少。")] : null,
        A.kind !== "price" ? h("p", {}, "這是殖利率，不是價格：短期利率上升時，這些標的的配息會跟著升，但價格本身幾乎不動；不列三個角度。") : null));
    });
    return det;
  };
  c.body.append(...[
    lowKeys.length ? h("div", { class: "st-group" }, h("div", { class: "st-cap" }, "有標的在低基期的（位置低不代表會漲，看「位階」那個角度）"), ...lowKeys.map(row)) : null,
    pullKeys.length ? h("div", { class: "st-group" }, h("div", { class: "st-cap" }, "有標的漲過又跌下來的（高檔回落，位階還是高）"), ...pullKeys.map(row)) : null,
    restKeys.length ? h("div", { class: "st-group" }, h("div", { class: "st-cap" }, lowKeys.length || pullKeys.length ? "其他" : "全部"), ...restKeys.map(row)) : null,
    h("p", { class: "st-note" }, `標的的價格每天更新（${(T.fetched || "").slice(0, 10)}），含配息；台灣掛牌的美元資產是台幣計價，多了匯率變動。期貨型 ETF（石油、天然氣、銅、農產品）有轉倉成本，長期持有會和原物料價格脫節。全部是歷史統計，不是投資建議。　`,
      tgGloss("lowbase", "低基期是什麼？"), " ", tgGloss("tracking", "追蹤程度是什麼？")),
  ].filter(Boolean));
  return c;
}
