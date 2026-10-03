/* 可信度計分板（2026-10-03）：這個分頁每一種「推論」過去回頭對答案的結果，一題一列。
   傳導鏈的部分來自 2005 年起每個月的走步對答案（scenario.reliability.chain，幾百次），不是只看 12 個案例；
   排行來自走步回測（backtest），避險來自日線的置換檢定（hedge.daily）。全部由資料組出來，沒有寫死。 */

function reliabilityCard(S, hz) {
  const rc = S.reliability && S.reliability.chain;
  const rows = [];
  const pill = (word, tone) => h("span", { class: `pill pill-${tone}` }, word);
  if (rc && rc.more) {
    const m = rc.more, l = rc.less;
    const good = m.consistent && m.realized - m.base >= 3;
    rows.push(["哪件事比平常更可能（傳導鏈下一步）",
      `${m.n} 次提示，實際發生 ${fmtNum(m.realized, 0)}%、平常 ${fmtNum(m.base, 0)}%；前半 ${m.halves[0].realized ?? "—"}% 對 ${m.halves[0].base ?? "—"}%、後半 ${m.halves[1].realized ?? "—"}% 對 ${m.halves[1].base ?? "—"}%`,
      pill(good ? "方向有參考價值" : "參考價值低", good ? "ok" : "bad")]);
    if (l && l.n >= 20) rows.push(["哪件事比平常更不可能",
      `${l.n} 次提示，實際發生 ${fmtNum(l.realized, 0)}%、平常 ${fmtNum(l.base, 0)}%；前後半${l.consistent ? "都成立" : "方向相反"}`,
      pill(l.consistent ? "有參考價值" : "沒有參考價值", l.consistent ? "ok" : "bad")]);
    if (rc.bins && rc.bins.length) {
      const off = Math.max(...rc.bins.map((b) => Math.abs(b.realized - (b.lo + b.hi) / 2)));
      rows.push(["機率數字本身（校準後）",
        `${rc.n} 次預測分箱：` + rc.bins.map((b) => `${fmtNum(b.lo, 0)}～${fmtNum(b.hi, 0)}% 的實際 ${fmtNum(b.realized, 0)}%`).join("、")
          + `。原始數字的誤差（Brier）${rc.brier_raw} 比直接用平常 ${rc.brier_base} 還差，收縮後 ${rc.brier_adj}`,
        pill(off <= 15 ? "數字大致對得上" : "數字偏差大", off <= 15 ? "meh" : "bad")]);
    }
  }
  for (const x of S.horizons) {
    const B = S.backtest[String(x)]; const E = B.ensemble || B.ridge; const hv = B.halves && B.halves.ensemble;
    rows.push([`哪個標的接下來 ${x} 個月漲最多（排行）`,
      `${B.periods} 期走步回測，前 ${S.model.topk} 名平均多 ${fmtSigned(E.mean, 2)} 個百分點（各起點 ${scRange(E.offsets)}）${hv ? `；前半 ${fmtSigned(hv[0].mean, 2)}、後半 ${fmtSigned(hv[1].mean, 2)}` : ""}`,
      pill(E.verdict === "樣本外有效" ? "可以參考" : E.verdict === "時好時壞" ? "時好時壞" : "無效", SC_VERDICT_TONE[E.verdict] || "bad")]);
  }
  const E3 = S.backtest[String(hz)].ensemble;
  if (E3 && fin(E3.dir_hit)) rows.push([`單一標的會漲還是跌（${hz} 個月）`,
    `排行說會漲（或跌）的 ${E3.dir_n} 次裡，方向對的只有 ${fmtNum(E3.dir_hit, 0)}%——接近擲銅板`,
    pill(E3.dir_hit >= 58 ? "有一點參考價值" : "沒有參考價值", E3.dir_hit >= 58 ? "meh" : "bad")]);
  const HG = S.hedge, D = HG && HG.daily && HG.daily.targets;
  if (D && D.length) {
    const tests = D.flatMap((T) => T.hedges.map((x) => ({ T, x }))).filter(({ x }) => fin(x.p));
    const sig = tests.filter(({ x }) => x.p <= 0.01);
    const names = sig.slice(0, 3).map(({ T, x }) => `${scPlain(T.id, T.label).replace(/下跌$/, "")}跌時的${hgName(x)}`);
    rows.push(["如果跌了，什麼擋得住（避險）",
      `日線 ${tests.length} 次檢定裡 p ≤ 0.01 的有 ${sig.length} 個（純運氣約 ${fmtNum(tests.length * 0.01, 1)} 個）${names.length ? `：${names.join("、")}` : ""}；對台股下跌，美元（對新台幣）2004 年起 24/25 次一起漲`,
      pill(sig.length >= 3 ? "有參考價值" : "沒有參考價值", sig.length >= 3 ? "ok" : "bad")]);
  }
  const wv = (S.case_summary || {}).wave;
  if (wv && wv.n) rows.push(["下一波可能亮起的訊號", `${wv.n} 個提示亮起 ${wv.hits} 個（${fmtNum(100 * wv.hits / wv.n, 0)}%），平常約 ${fmtNum(wv.base, 0)}%（${scP(wv.p)}）`,
    pill(scSig(wv.p) ? "有參考價值" : "沒有參考價值", scSig(wv.p) ? "ok" : "bad")]);
  const c = card({ title: "可信度計分板：這一頁的每種推論，過去對答案的結果", span: 12,
    sub: `每一列是一種推論，右邊是它回頭對答案的成績：傳導鏈的「更可能／更不可能」是 2005 年起每個月都重推一次再對答案（${rc ? rc.n : "—"} 次）；排行是走步回測；避險是日線的置換檢定。有參考價值的只有少數幾種，其餘照實標示。` });
  c.body.append(h("div", { class: "tbl-wrap" }, h("table", { class: "data" },
    h("thead", {}, h("tr", {}, h("th", {}, "推論"), h("th", {}, "對答案的成績"), h("th", {}, "可信度"))),
    h("tbody", {}, rows.map(([q, ev, p]) => h("tr", {}, h("td", {}, h("b", {}, q)), h("td", {}, ev), h("td", {}, p)))))),
    h("p", { class: "note" }, "「校準」＝小樣本的機率照段數往平常收縮，收縮後各段的實際發生率對得上。前後半＝2005～2015 與 2016 起各算一次，兩半都成立才算站得住。全部是歷史統計，不是投資建議。"));
  return c;
}
