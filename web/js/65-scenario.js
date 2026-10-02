/* 分頁：沙盤推演（資料在 gfd/scenario.py 算好；公開版用到才下載） */

// 判定用中性的「可信度」色，不用漲跌色（本站紅漲綠跌，紅綠在這裡會被讀成好壞）
const SC_VERDICT_TONE = { "樣本外有效": "ok", "時好時壞": "meh", "樣本外無效": "bad", "樣本不足": "bad" };
const scPct = (v, d = 1) => (fin(v) ? fmtSigned(v, d, "%") : "—");
const scP = (p) => (fin(p) ? (p < 0.001 ? "p<0.001" : `p=${p.toFixed(3)}`) : "");
// p 值白話：≤ 0.05 顯著、≤ 0.10 邊際、其餘分不出和亂挑（或運氣）的差別
const scPWord = (p, vsWhat = "亂挑") => (!fin(p) ? "" : p <= 0.05 ? "統計上顯著" : p <= 0.10 ? "邊際，未達 0.05" : `分不出和${vsWhat}的差別`);
// 「下一波」命中率對照平常比例的說法：依 p 與命中率決定，不寫死
const scSig = (p) => fin(p) && p <= 0.05;      // null 不能當成顯著（JS 會把 null <= 0.05 判成 true）
const scWaveWord = (w) => (!w || !w.n ? "" : scSig(w.p) ? "明顯高於平常"
  : 100 * w.hits / w.n > w.base ? "略高於平常，但還在運氣範圍內" : "沒有比平常好");
const scRange = (rows, key = "mean") => {
  const v = rows.map((r) => r[key]).filter(fin);
  if (!v.length) return "—";
  return key === "hit" ? `${Math.min(...v).toFixed(0)}～${Math.max(...v).toFixed(0)}%` : `${fmtSigned(Math.min(...v), 2)}～${fmtSigned(Math.max(...v), 2)}`;
};
// 樣本內穩定度：重抽後和現在「同方向」的比例（期望值為負的標的要看「為負」的比例）
const scStable = (r) => (fin(r.prob_pos) && fin(r.ev) && r.ev !== 0 ? (r.ev > 0 ? r.prob_pos : 100 - r.prob_pos) : null);   // 沒有方向（0）就不給
// 訊號劇本通過三道檢驗的組合：和模型同方向＝支持，反方向＝相反（不能只標「通過檢驗」，會被讀成支持）
const scRefs = (r) => {
  const refs = r.robust || [];
  return { agree: refs.filter((x) => Math.sign(x.lift) === Math.sign(r.ev)), oppose: refs.filter((x) => Math.sign(x.lift) === -Math.sign(r.ev)) };
};

/* 開頭結論：亮燈數、目前排名前後、樣本外可信度（全部由資料組出來；隨上方期間切換重寫） */
function scenarioLead(S, hz) {
  if (!S.active.length) return "目前沒有任何訊號亮著，模型的期望超額全部是 0，沒有可以推演的方向。";
  const rows = S.assets[String(hz)] || [];
  const B = S.backtest[String(hz)];
  const v = B.ridge.verdict;
  const val = (r) => (fin(r.cal) ? r.cal : r.ev);
  const top = rows.slice(0, 3), bot = rows.slice(-2).reverse();
  const head = `${S.active.length} 個訊號亮著。`;
  const bt = `這套排名在 ${B.start} 起的樣本外回測，${hz} 個月前 ${S.model.topk} 名平均每期只比全體多 ${fmtSigned(B.ridge.mean, 2)} 個百分點`
    + `（不同起始月 ${scRange(B.ridge.offsets)}）`;
  if (v === "樣本外無效") return `${head}${hz} 個月的排名在樣本外沒有比亂選好（${fmtSigned(B.ridge.mean, 2)}），這個期間不列推薦。`;
  const picks = `依模型，未來 ${hz} 個月期望超額較高的是${top.map((r) => `${r.name}（${scPct(val(r))}）`).join("、")}，`
    + `較弱的是${bot.map((r) => `${r.name}（${scPct(val(r))}）`).join("、")}${fin(top[0] && top[0].cal) ? "（已依樣本外校準）" : "（模型值）"}。`;
  const cs = S.case_summary && S.case_summary.model && S.case_summary.model[String(hz)];
  const check = cs && cs.n ? `對照過去 ${S.case_summary.n} 個類似時點，當時的模型 ${hz} 個月前 ${S.model.topk} 名跑贏全體 ${cs.hit}/${cs.n} 次（${scP(cs.p)}，${scPWord(cs.p)}）。` : "";
  if (v === "樣本外有效") return `${head}${picks}${bt}，各起始月都顯著。${check}訊號門檻是事後設計的，實際效果可能更差。`;
  return `${head}${picks}但${bt}，時好時壞。${check}不能當買賣依據，只是研究線索。`;
}

TABS.scenario = lazyTab("scenario", (root) => {
  const S = A.scenario;
  let hz = store.get("scH", 3);
  if (S && !S.horizons.includes(hz)) hz = S.horizons[0];
  root.replaceChildren(tabHead("沙盤推演：現在亮著的訊號，接下來可能怎麼走、哪些標的期望值較好",
    "把三個分頁接起來：訊號劇本告訴我們現在哪些訊號亮著；傳導鏈從亮著的層往下推，看下一層有多可能跟著成立；"
    + "期望值把所有亮著的訊號一起放進模型（每個標的之後 3／6／12 個月的報酬減掉它平常的平均，對全部訊號做收縮迴歸），"
    + "同時亮著、彼此重疊的訊號會分攤效果、不重複計算。模型值再乘上「樣本外校準斜率」（過去樣本外實際超額大約是模型值的幾倍），"
    + "得到比較實際的數字。最後附上事件衝擊（日線）裡相關事件類型的短期反應。全部是歷史統計，不是投資建議，也沒有計入交易成本。",
    false, null, S ? scenarioLead(S, hz) : null));
  if (!S || !S.active) { root.append(h_empty("尚未產生沙盤推演，請執行 python3 gfd.py analyze")); return; }
  const g = h("div", { class: "grid" });
  root.append(g);
  let pick = store.get("scPick", null);

  // ── 1. 現在亮著的訊號 ──
  const c1 = card({ title: "現在亮著的訊號", span: 12,
    sub: `資料截至 ${S.asof}（各序列最新一筆）。和「訊號劇本」分頁同一套判定。` });
  const bySource = new Map();
  for (const a of S.active) { if (!bySource.has(a.source)) bySource.set(a.source, []); bySource.get(a.source).push(a); }
  c1.body.append(h("div", { class: "sc-active" }, [...bySource].map(([src, list]) => h("div", { class: "sc-src" },
    h("div", { class: "sc-src-h" }, src),
    h("ul", { class: "sc-sig" }, list.map((a) => h("li", {},
      h("b", {}, a.label),
      h("span", { class: "muted" }, `　${a.current_at} 數值 ${fin(a.current) ? fmtNum(a.current, 2) : "—"}・已連續 ${a.run} 個月・歷史上 ${a.episodes} 次`),
      h("div", { class: "sc-why" }, a.why))))))));
  if (S.similar && S.similar.length) {
    c1.body.append(h("h4", { class: "sub-h" }, "最像現在的歷史時點（亮著的訊號重疊程度，1＝完全相同）"),
      h("div", { class: "tbl-wrap" }, h("table", { class: "data" },
        h("thead", {}, h("tr", {}, h("th", {}, "時點"), h("th", { class: "n" }, "相似度"), h("th", {}, "當時也亮著的訊號"))),
        h("tbody", {}, S.similar.map((s) => h("tr", {}, h("td", { class: "n" }, s.m), h("td", { class: "n" }, fmtNum(s.jaccard, 2)),
          h("td", {}, s.shared.join("、"))))))),
      h("p", { class: "note" }, `現在這組訊號最多只和歷史上 ${fmtNum(S.similar[0].jaccard, 2)} 的程度重疊——完全相同的組合沒有出現過，`
        + "期望值是把各訊號的歷史效果組合起來推估的，不是「上次一模一樣時發生了什麼」。"));
  }
  g.append(c1.el);

  // ── 2. 傳導鏈推演 ──
  const c2 = card({ title: "推演：傳導鏈的下一層", span: 12,
    sub: `從每條鏈目前成立的層往下看：還沒成立的層，歷史上在上游成立後 ${S.within} 個月內跟著成立的比例，和「隨便哪個月」的平常比例對照。` });
  if (!S.paths.length) c2.body.append(h("p", { class: "empty" }, "目前沒有任何一條鏈有成立的層"));
  for (const p of S.paths) {
    const steps = [];
    p.nodes.forEach((n, i) => {
      if (i) steps.push(h("span", { class: "sc-arrow", "aria-hidden": "true" }, "→"));
      let state = null, tone = "";
      if (n.triggered) { state = "已成立"; tone = "on"; }
      else if (fin(n.prob)) {
        const lift = n.prob - (n.base ?? n.prob);
        tone = lift >= 10 ? "likely" : lift <= -5 ? "unlikely" : "";
        state = `${S.within} 個月內 ${fmtNum(n.prob, 0)}%（平常 ${fmtNum(n.base, 0)}%）`;
      } else state = "上游未成立";
      steps.push(h("div", { class: `sc-node ${tone}`, title: n.triggered ? `${n.current_at} 數值 ${fmtNum(n.current, 2)}` : (n.after ? `接在「${n.after}」之後；歷史 ${n.n_episodes} 次` : "") },
        h("div", { class: "sc-node-l" }, n.label), h("div", { class: "sc-node-s" }, state),
        !n.triggered && fin(n.prob12) ? h("div", { class: "sc-node-s" }, `12 個月內 ${fmtNum(n.prob12, 0)}%（平常 ${fmtNum(n.base12, 0)}%）`) : null,
        fin(n.wait) && !n.triggered ? h("div", { class: "sc-node-s muted" }, `成立的話中位數第 ${fmtNum(n.wait, 0)} 個月`) : null));
    });
    const ifs = p.nodes.filter((n) => !n.triggered && fin(n.prob) && n.if_then && n.if_then.length);
    const st = p.state;
    const stTxt = !st ? null : st.n_episodes === 0 ? "照這條鏈現在的狀態（亮著的層都亮、其餘都沒亮），歷史上沒有出現過，推不到更下層。"
      : `照這條鏈現在的狀態（亮著的層都亮、其餘都沒亮），歷史上有 ${st.n_episodes} 段、${st.n_months} 個月：剩下的層在 12 個月內全部走完的比例 ${fmtNum(st.all, 0)}%`
        + `${st.n_episodes < 3 ? "——樣本太少，只是紀錄" : ""}。`;
    c2.body.append(h("div", { class: "sc-path" },
      h("div", { class: "sc-path-h" }, h("b", {}, p.name), h("span", { class: "muted" }, `　${p.active}/${p.of} 層成立`)),
      h("div", { class: "sc-steps" }, steps),
      stTxt ? h("p", { class: "sc-state" }, stTxt) : null,
      ifs.length ? h("ul", { class: "sc-ifs" }, ifs.map((n) => h("li", {}, `如果「${n.label}」也成立：訊號劇本裡通過三道檢驗的是 `,
        n.if_then.map((r, k) => h("span", {}, k ? "、" : "", `${r.name} ${r.horizon} 個月超額 `, chg(r.lift, 1, "%"))), "。"))) : null));
  }
  c2.body.append(h("p", { class: "note" }, "「比平常更可能」（紅框）＝高出平常 10 個百分點以上；「比平常更不可能」（虛線）＝低於平常 5 個百分點以上。"
    + "傳導鏈的層是事後挑的假說，歷史上多數段落「跟著發生」，但事件後報酬站得住的很少，請搭配下面的期望值與樣本外檢查一起看。"));
  g.append(c2.el);

  // ── 2b. 下一波可能亮起的訊號（跨鏈） ──
  const CS = S.case_summary || {};
  const cW = card({ title: "下一波可能亮起的訊號（跨鏈）", span: 12,
    sub: `不限同一條鏈：歷史上和現在狀態相似的月份（亮著的訊號重疊 ≥ ${fmtNum((CS.threshold || 0.25) * 100, 0)}%），之後 ${S.within} 個月哪些「現在沒亮」的訊號比平常更常亮起。` });
  if (!S.wave || !S.wave.length) cW.body.append(h("p", { class: "empty" }, "沒有比平常明顯更常亮起的訊號"));
  else cW.body.append(h("div", { class: "tbl-wrap" }, h("table", { class: "data" },
    h("thead", {}, h("tr", {}, ["訊號", `${S.within} 個月內亮起`, "平常", "相似月份（段）", "如果亮起：訊號劇本通過檢驗的組合"].map((t, i) => h("th", { class: i && i < 4 ? "n" : null }, t)))),
    h("tbody", {}, S.wave.map((w) => h("tr", {},
      h("td", {}, w.label, h("span", { class: "sub" }, `${w.source}：${w.why}`)),
      h("td", { class: "n" }, `${fmtNum(w.prob, 0)}%`), h("td", { class: "n" }, `${fmtNum(w.base, 0)}%`),
      h("td", { class: "n" }, `${w.n_months}（${w.n_episodes}）`),
      h("td", {}, w.if_then && w.if_then.length ? w.if_then.map((r, k) => h("span", {}, k ? "、" : "", `${r.name} ${r.horizon} 個月 `, chg(r.lift, 1, "%"))) : h("span", { class: "muted" }, "—"))))))));
  if (CS.wave && CS.wave.n) {
    cW.body.append(h("p", { class: "note" }, `對答案：在過去 ${CS.n} 個類似時點用同樣方法（只用當時的資料）挑出的「下一波」訊號，${CS.wave.n} 個裡實際亮起 ${CS.wave.hits} 個`
      + `（${fmtNum(100 * CS.wave.hits / CS.wave.n, 0)}%），平常比例約 ${fmtNum(CS.wave.base, 0)}%：${scWaveWord(CS.wave)}（${scP(CS.wave.p)}）。`));
  }
  g.append(cW.el);

  // ── 3. 期望值排行 ──
  const c3 = card({ title: "期望值排行", span: 12 });
  const hChips = h("div", { class: "chips" });
  c3.tools.append(hChips);
  const c3body = h("div");
  c3.body.append(c3body);
  g.append(c3.el);

  // ── 4. 為什麼 ──
  const c4 = card({ title: "為什麼", span: 12 });
  g.append(c4.el);

  // ── 4b. 對答案：過去類似的時點 ──
  const cA = card({ title: "對答案：過去類似的時點，推演說了什麼、後來實際怎樣", span: 12,
    sub: `挑出亮著的訊號和現在重疊最多的歷史時點（重疊 ≥ ${fmtNum((CS.threshold || 0.25) * 100, 0)}%、彼此至少隔一年、之後一年的結果已經知道），`
      + "在每個時點只用「當時已經知道」的資料重跑整套推演，再對照之後實際發生的事。案例只有十來個，運氣成分很大。" });
  if (!S.cases || !S.cases.length) cA.body.append(h("p", { class: "empty" }, "沒有夠相似的歷史時點"));
  else {
    const mm = CS.model || {}, td = CS.today || {}, ly = CS.layers || {}, wv = CS.wave || {};
    const fair = (x) => (mm[x] && mm[x].n ? `${x} 個月前 ${S.model.topk} 名跑贏全體 ${mm[x].hit}/${mm[x].n} 次、平均每次 ${fmtSigned(mm[x].spread_mean, 2)} 個百分點（${scP(mm[x].p)}，${scPWord(mm[x].p)}）` : null);
    cA.body.append(h("ul", { class: "finds" },
      h("li", { class: (mm["3"] && scSig(mm["3"].p)) || (mm["6"] && scSig(mm["6"].p)) ? "t-up" : "t-alert" },
        h("b", {}, "公平的考試：當時的模型"),
        h("span", {}, [fair("3"), fair("6")].filter(Boolean).join("；") + "。p 值是和「每次隨機挑 5 個」比。"
          + "這裡只排除了估計上的偷看；訊號、門檻與傳導鏈本身是事後設計的，真實情況通常更差。")),
      ly.n ? h("li", { class: ly.skill > 0 ? "t-up" : "t-alert" },
        h("b", {}, "傳導鏈的下一層"),
        h("span", {}, `${ly.n} 次預測中實際發生 ${ly.happened} 次。預測機率的準確度（Brier，越小越好）${fmtNum(ly.brier, 3)}，`
          + `直接用「平常比例」是 ${fmtNum(ly.brier_base, 3)}——${ly.skill > 0 ? `比平常比例準 ${fmtNum(ly.skill * 100, 0)}%。` : `比直接用平常比例還不準（${fmtNum(ly.skill * 100, 0)}%）。`}`
          + (ly.skill > 0 ? "在類似時點，「上游亮了，下一層比平常更可能」有一點參考價值，但案例不多。" : "也就是說，「上游亮了，下一層比平常更可能」這件事在類似時點沒有幫上忙。"))) : null,
      wv.n ? h("li", { class: scSig(wv.p) ? "t-up" : "t-neutral" },
        h("b", {}, "下一波訊號"),
        h("span", {}, `挑出的 ${wv.n} 個「可能亮起」的訊號實際亮起 ${wv.hits} 個（${fmtNum(100 * wv.hits / wv.n, 0)}%），平常比例約 ${fmtNum(wv.base, 0)}%：${scWaveWord(wv)}（${scP(wv.p)}）。`)) : null,
      h("li", { class: "t-neutral" },
        h("b", {}, "今天的答案放回這些時點（不是公平的考試）"),
        h("span", {}, ["3", "6"].filter((x) => td[x] && td[x].n).map((x) => `今天 ${x} 個月的前 ${S.model.topk} 名在這些時點之後 ${x} 個月跑贏全體 ${td[x].hit}/${td[x].n} 次、平均 ${fmtSigned(td[x].mean, 2)} 個百分點`).join("；")
          + "。今天的模型就是從這些歷史學來的，對得上是應該的，只能看出「在哪幾次會錯、錯多少」。"))));
    const ok = (v) => (v ? h("span", { class: "sc-ok" }, "✓") : h("span", { class: "sc-ng" }, "✗"));
    const modelCell = (m) => (!m || !m.ok ? h("td", { class: "n muted" }, m && m.reason ? "資料不足" : "—")
      : h("td", { class: "n" }, chg(m.spread, 1, ""), " ", ok(m.hit), h("span", { class: "sub" }, m.top.slice(0, 3).map((x) => x.name).join("、"))));
    cA.body.append(h("div", { class: "tbl-wrap" }, h("table", { class: "data" },
      h("thead", {}, h("tr", {}, ["時點", "相似度", "當時模型 3 個月：前 5 名比全體", "6 個月", "今天的前 5 名放在當時（樣本內，3 個月）", "鏈的下一層猜對", "下一波亮起"]
        .map((t, i) => h("th", { class: i ? "n" : null }, t)))),
      h("tbody", {}, S.cases.map((c) => {
        const lr = c.layers || [];
        const right = lr.filter((l) => (l.prob >= 50) === l.actual).length;
        const wvc = c.wave || [];
        return h("tr", {},
          h("td", {}, c.m, h("span", { class: "sub" }, `${c.shared.length} 個訊號和現在相同`)),
          h("td", { class: "n" }, fmtNum(c.jaccard, 2)),
          modelCell(c.model["3"]), modelCell(c.model["6"]),
          h("td", { class: "n" }, c.today["3"] ? chg(c.today["3"].top, 1, "") : "—"),
          h("td", { class: "n" }, lr.length ? `${right}/${lr.length}` : "—"),
          h("td", { class: "n" }, wvc.length ? `${wvc.filter((w) => w.actual).length}/${wvc.length}` : "—"));
      })))));
    cA.body.append(h("p", { class: "note" }, "數字是之後 h 個月的報酬比當時全體標的平均多幾個百分點（對數報酬；月均價標的從下個月起算）。"
      + "「鏈的下一層猜對」＝預測機率 ≥ 50% 而且真的發生、或 < 50% 而且沒發生。點下面各時點看細節。"));
    for (const c of S.cases) {
      const m3 = c.model["3"];
      cA.body.append(h("details", { class: "sc-case" },
        h("summary", {}, `${c.m}　相似度 ${fmtNum(c.jaccard, 2)}　當時亮著 ${c.active.length} 個訊號`),
        h("p", { class: "sc-case-p" }, h("b", {}, "當時亮著："), c.active.join("、"), "。", h("br"), h("b", {}, "和現在相同："), c.shared.join("、") || "—", "。"),
        m3 && m3.ok ? h("p", { class: "sc-case-p" }, h("b", {}, "當時模型 3 個月看好："),
          ...m3.top.map((x, k) => h("span", {}, k ? "、" : "", `${x.name} `, chg(x.real, 1, ""))),
          h("br"), h("b", {}, "當時模型 3 個月看壞："),
          ...m3.bottom.map((x, k) => h("span", {}, k ? "、" : "", `${x.name} `, chg(x.real, 1, ""))),
          h("span", { class: "muted" }, "（數字是實際比全體多幾個百分點）")) : null,
        c.layers && c.layers.length ? h("ul", { class: "sc-case-l" }, c.layers.map((l) => h("li", {}, ok(l.actual), ` ${l.chain}：${l.label}　當時推估 ${fmtNum(l.prob, 0)}%（平常 ${fmtNum(l.base, 0)}%）`))) : null,
        c.wave && c.wave.length ? h("p", { class: "sc-case-p" }, h("b", {}, "當時挑的下一波："),
          ...c.wave.map((w, k) => h("span", {}, k ? "、" : "", ok(w.actual), ` ${w.label}（${fmtNum(w.prob, 0)}% vs 平常 ${fmtNum(w.base, 0)}%）`))) : null));
    }
  }
  g.append(cA.el);

  // ── 5. 事件衝擊 ──
  const c5 = card({ title: "相關事件類型的短期反應（事件衝擊・日線）", span: 12,
    sub: "亮著的訊號對應到事件衝擊分頁裡的事件類型，看這類事件發生後一個月、兩個月，各標的比平常多或少多少。這是「事件一爆發」的短期反應，月資料的訊號比較像慢慢累積的狀態，只能當參考。" });
  if (!S.events.length) c5.body.append(h("p", { class: "empty" }, "亮著的訊號沒有對應到明確的事件類型"));
  for (const e of S.events) {
    c5.body.append(h("div", { class: "sc-ev" },
      h("div", { class: "sc-path-h" }, h("b", {}, e.name), h("span", { class: "muted" }, `　${e.n} 個事件・因為亮著：${e.from_.join("、")}`)),
      e.rows.length ? h("div", { class: "tbl-wrap" }, h("table", { class: "data" },
        h("thead", {}, h("tr", {}, ["標的", "一個月比平常", "兩個月比平常", "走完一半", "有反應的比例"].map((t, i) => h("th", { class: i ? "n" : null }, t)))),
        h("tbody", {}, e.rows.map((r) => h("tr", {},
          h("td", {}, r.name),
          h("td", { class: "n" }, chg(r.excess21, 1, "%"), h("span", { class: "sub" }, scP(r.p21))),
          h("td", { class: "n" }, chg(r.excess42, 1, "%"), h("span", { class: "sub" }, scP(r.p42))),
          h("td", { class: "n" }, fin(r.half_day) ? `第 ${fmtNum(r.half_day, 0)} 天` : "—"),
          h("td", { class: "n" }, fin(r.resp_rate) ? `${fmtNum(r.resp_rate, 0)}%` : "—")))))) : h("p", { class: "empty" }, "這類事件後沒有 p ≤ 0.10 的標的"),
      e.recent.length ? h("p", { class: "note" }, `最近的同類事件：${e.recent.map((x) => `${x.date.slice(0, 7)} ${x.name}`).join("、")}`) : null));
  }
  if (fin(S.event_luck)) c5.body.append(h("p", { class: "note" }, `事件衝擊整體估計約 ${fmtNum(S.event_luck, 0)}% 的顯著結果是運氣（見事件衝擊分頁），單一類型的數字請保守看待。`));
  g.append(c5.el);

  // ── 6. 這套推演可信嗎 ──
  const c6 = card({ title: "這套推演可信嗎：走步樣本外回測", span: 12,
    sub: `從 ${S.model.eval_start} 起每個月只用「當時已經知道結果」的資料重估模型，買期望值最高的 ${S.model.topk} 個標的，和當期有資料的全體標的（${(S.backtest[String(S.horizons[0])].n_assets || []).join("～")} 個）平均比。`
      + "世界銀行商品價格與央行匯率是月均價，月底時已經包含過去半個月，所以這些標的的報酬一律從下個月的均價算起，估計時也多退一個月（不這樣做回測會偷看未來，3 個月的差距會被灌大好幾倍）。"
      + "期間互相重疊不能當獨立樣本，所以每隔 h 個月取一期、每個起點各算一次，列出範圍。" });
  const methods = [["ridge", "本頁的模型"], ["avg", "對照：單一訊號平均"], ["momentum", "對照：過去 6 個月漲最多"]];
  c6.body.append(h("div", { class: "tbl-wrap" }, h("table", { class: "data" },
    h("thead", {}, h("tr", {}, ["方法", "期間", "前 5 名平均每期多", "各起點範圍", "各起點勝率", "置換檢定 p", "判定"].map((t, i) => h("th", { class: i > 1 ? "n" : null }, t)))),
    h("tbody", {}, methods.flatMap(([k, name]) => S.horizons.map((x) => {
      const b = S.backtest[String(x)][k];
      const ps = b.offsets.map((o) => o.p).filter(fin);
      return h("tr", { class: k === "ridge" && x === hz ? "sel" : null },
        h("td", {}, name), h("td", {}, `${x} 個月`),
        h("td", { class: "n" }, chg(b.mean, 2, "")),
        h("td", { class: "n" }, scRange(b.offsets)),
        h("td", { class: "n" }, scRange(b.offsets, "hit")),
        h("td", { class: "n" }, ps.length ? `${Math.min(...ps).toFixed(3)}～${Math.max(...ps).toFixed(3)}` : "—"),
        h("td", { class: "n" }, h("span", { class: `pill pill-${SC_VERDICT_TONE[b.verdict] || "neutral"}` }, b.verdict)));
    }))))));
  const cal = S.horizons.map((x) => `${x} 個月 ${fmtNum(S.backtest[String(x)].calibration.slope, 2)}`).join("、");
  c6.body.append(h("p", { class: "note" }, `校準斜率（樣本外實際超額 ÷ 模型值）：${cal}。模型值通常高估好幾倍，所以排行榜上的「校準後」才是比較實際的數字；`
    + "斜率不是正的或回測判定無效的期間，不給校準後數字。"));
  const chartHost = h("div", { class: "chart" });
  c6.body.append(h("h4", { class: "sub-h" }, "累積差距：每 h 個月換一次前 5 名，比全體平均多（對數報酬加總，示意；每條線是不同的起始月，最多畫 6 條）"), chartHost);
  c6.body.append(h("ul", { class: "finds", style: "margin-top:12px" },
    h("li", { class: "t-alert" }, h("b", {}, "後見之明"), h("span", {}, "訊號和門檻是 2026 年回頭設計的，回測只排除了「估計」上的偷看，排除不了「設計」上的後見之明。")),
    h("li", { class: "t-alert" }, h("b", {}, "比較過不只一種方法"), h("span", {}, "上表的兩種對照也是挑選過程的一部分；挑選本身就是一種偷看，實際效果可能比表上差。")),
    h("li", { class: "t-neutral" }, h("b", {}, "沒有成本"), h("span", {}, "報酬是對數報酬，沒有交易成本、滑價、稅與期貨轉倉成本；指數與商品要用 ETF 或期貨才能實際持有。"))));
  g.append(c6.el);

  function drawChart() {
    const B = S.backtest[String(hz)];
    const ms = B.series.map((p) => p.m);
    const xs = ms.map((m) => { const [y, mo] = m.split("-").map(Number); return y + (mo - 1) / 12; });
    const colors = ["var(--s1)", "var(--s2)", "var(--s3)", "var(--s4)", "var(--s5)", "var(--s6)"];
    const series = [];
    for (let off = 0; off < Math.min(hz, 6); off++) {
      let acc = 0, last = null;
      const values = B.series.map((p, i) => {
        if ((i - off) % hz === 0 && i >= off && fin(p.v)) { acc += p.v; last = acc; }
        return i >= off ? last ?? 0 : null;
      });
      series.push({ key: `o${off}`, name: `起點 ${ms[off]}`, color: colors[off], values, fmt: (v) => fmtSigned(v, 1) });
    }
    lineChart(chartHost, { series, xs, labels: ms, height: 220, direct: false, refs: [{ y: 0 }], label: "樣本外累積差距",
      yFmt: (v) => fmtSigned(v, 0), tipFmt: (r) => fmtSigned(r.raw, 1) });
  }

  function why(r) {
    const B = S.backtest[String(hz)];
    const valid = B.ridge.verdict !== "樣本外無效";
    c4.el.querySelector("h3").textContent = `為什麼：${r.name}（未來 ${hz} 個月）`;
    const ev = r.evidence || [];
    const up = ev.filter((e) => (e.lift || 0) > 0).length, dn = ev.filter((e) => (e.lift || 0) < 0).length;
    const dir = Math.sign(r.ev);
    const agreeN = ev.filter((e) => Math.sign(e.lift || 0) === dir).length;
    const past = (r.past || []).filter((p) => fin(p.own));
    const pastWin = past.filter((p) => Math.sign(p.own) === dir).length;
    const parts = [];
    parts.push(h("p", { class: "sc-sum" },
      `模型期望超額 ${scPct(r.ev)}（80% 區間 ${scPct(r.lo)}～${scPct(r.hi)}；${fin(scStable(r)) ? `樣本內重抽 200 次有 ${fmtNum(scStable(r), 0)}% 和現在同方向，這只代表模型在樣本內穩不穩，不是賺錢的機率` : "目前沒有方向"}）`,
      fin(r.cal) ? `，依樣本外校準約 ${scPct(r.cal)}` : "，這個期間樣本外無效，不給校準值",
      `；它平常 ${hz} 個月平均 ${scPct(r.base)}。`,
      valid ? "" : h("b", { class: "down" }, `　注意：${hz} 個月的排名在樣本外沒有比亂選好，下面的原因只是描述，不能當依據。`)));
    // 最像的歷史時點
    if (past.length) {
      parts.push(h("h4", { class: "sub-h" }, `最像現在的歷史時點，之後 ${hz} 個月比它平常多或少（${past.length} 次中 ${pastWin} 次和模型同方向）`),
        h("div", { class: "sc-past" }, past.map((p) => h("span", { class: "sc-chip" }, h("span", { class: "muted" }, `${p.m}（相似 ${fmtNum(p.jaccard, 2)}）`), " ", chg(p.own, 1, "%")))));
    }
    // 各訊號單獨的歷史
    if (ev.length) {
      parts.push(h("h4", { class: "sub-h" }, `各訊號單獨的歷史（訊號劇本口徑：每次事件後 ${hz} 個月中位數比平常多多少）：偏多 ${up}、偏空 ${dn}；和模型同方向的 ${agreeN} 個`),
        h("div", { class: "tbl-wrap" }, h("table", { class: "data" },
          h("thead", {}, h("tr", {}, ["訊號", "單獨看", "事件數", "跑贏平常", "p", "模型分攤"].map((t, i) => h("th", { class: i ? "n" : null }, t)))),
          h("tbody", {}, ev.map((e) => h("tr", {},
            h("td", {}, e.label, h("span", { class: "sub" }, `${e.source}：${e.why}`)),
            h("td", { class: "n" }, chg(e.lift, 1, "%")),
            h("td", { class: "n" }, String(e.n)),
            h("td", { class: "n" }, fin(e.hit) ? `${fmtNum(e.hit, 0)}%` : "—"),
            h("td", { class: "n" }, fin(e.p) ? e.p.toFixed(3) : "—"),
            h("td", { class: "n" }, chg(e.beta, 1, "%"))))))));
      if (agreeN * 2 < ev.length) {
        parts.push(h("p", { class: "note" }, "單獨看，多數訊號的方向和模型相反：模型的結論主要來自「這幾個訊號同時亮著」的組合（例如殖利率上升＋商品上漲＋銅比金強的再通膨組合），"
          + "不是任何一個訊號自己的效果。組合效果的樣本比單一訊號更少，請多看上面「最像的歷史時點」那幾次的實際結果。"));
      }
    }
    // 傳導鏈裡的位置
    const inChains = S.paths.flatMap((p) => p.nodes.filter((n) => n.sid === r.sid).map((n) => ({ p, n })));
    if (inChains.length) {
      parts.push(h("h4", { class: "sub-h" }, "它在傳導鏈裡的位置"),
        h("ul", { class: "finds" }, inChains.map(({ p, n }) => h("li", { class: n.triggered ? "t-alert" : fin(n.prob) && n.prob - (n.base ?? n.prob) >= 10 ? "t-up" : "t-neutral" },
          h("b", {}, `${p.name}：${n.label}`),
          h("span", {}, n.triggered ? "這一層已經成立。"
            : fin(n.prob) ? `接在「${n.after}」之後，歷史上 ${S.within} 個月內成立的比例 ${fmtNum(n.prob, 0)}%（平常 ${fmtNum(n.base, 0)}%），成立的話中位數第 ${fmtNum(n.wait, 0)} 個月。`
            : "上游還沒成立，暫時推不到這一層。")))));
    }
    // 事件衝擊
    if (r.events && r.events.length) {
      parts.push(h("h4", { class: "sub-h" }, "相關事件類型發生後（事件衝擊・日線）"),
        h("ul", { class: "finds" }, r.events.map((e) => h("li", { class: "t-neutral" },
          h("b", {}, e.cat_name),
          h("span", {}, `一個月比平常 ${scPct(e.excess21)}（${scP(e.p21)}）、兩個月 ${scPct(e.excess42)}（${scP(e.p42)}）`
            + `${fin(e.half_day) ? `，有反應時中位數第 ${fmtNum(e.half_day, 0)} 天走完一半` : ""}；${e.n} 個事件。`)))));
    }
    // 訊號劇本的穩健組合
    if (r.robust && r.robust.length) {
      parts.push(h("h4", { class: "sub-h" }, "訊號劇本裡通過三道檢驗的組合"),
        h("ul", { class: "finds" }, r.robust.map((x) => {
          const same = Math.sign(x.lift) === Math.sign(r.ev);
          return h("li", { class: same && !x.conflict ? "t-up" : "t-alert" },
            h("b", {}, `${x.label}：${hz} 個月超額 ${scPct(x.lift)}${same ? "（和模型同方向）" : "（和模型方向相反）"}`),
            h("span", {}, `${x.n} 次事件、${scP(x.p)}${x.conflict ? "；方向和傳導鏈當初的假說相反，別直接照用" : ""}`
              + `${same ? "" : "；單看這個訊號，歷史上是反方向——模型的結論來自其他訊號的組合"}。`));
        })));
    }
    c4.body.replaceChildren(...parts);
  }

  function draw() {
    store.set("scH", hz);
    const lead = root.querySelector(":scope > .tab-head .tab-lead");
    if (lead) lead.textContent = scenarioLead(S, hz);
    hChips.replaceChildren(...S.horizons.map((x) => h("button", { class: "chip", type: "button", "aria-pressed": String(x === hz),
      onclick: () => { hz = x; draw(); } }, `${x} 個月`)));
    const B = S.backtest[String(hz)];
    const rows = S.assets[String(hz)];
    const valid = B.ridge.verdict;
    c3.el.querySelector("h3").textContent = `期望值排行：未來 ${hz} 個月`;
    const banner = h("p", { class: `sc-banner t-${SC_VERDICT_TONE[valid] || "neutral"}` },
      h("b", {}, `${hz} 個月：${valid}。`),
      valid === "樣本外有效" ? `樣本外每期前 ${S.model.topk} 名比全體多 ${fmtSigned(B.ridge.mean, 2)} 個百分點（各起點 ${scRange(B.ridge.offsets)}）。`
        : valid === "時好時壞" ? `樣本外平均有正的差距（${fmtSigned(B.ridge.mean, 2)}），但不同起始月差很多（${scRange(B.ridge.offsets)}），參考就好。`
        : `樣本外沒有比亂選好（平均 ${fmtSigned(B.ridge.mean, 2)}），這個期間的排名不要當依據。`);
    const showAll = store.get("scAll", false);
    const list = showAll ? rows : [...rows.slice(0, 8), null, ...rows.slice(-5)];
    if (!pick || !rows.some((r) => r.sid === pick)) pick = rows[0].sid;
    const tr = (r, i) => {
      if (!r) return h("tr", { class: "sc-gap" }, h("td", { colspan: 8 }, "⋯"));
      const ev = r.evidence || [];
      const up = ev.filter((e) => (e.lift || 0) > 0).length, dn = ev.filter((e) => (e.lift || 0) < 0).length;
      const past = (r.past || []).filter((p) => fin(p.own));
      const win = past.filter((p) => Math.sign(p.own) === Math.sign(r.ev)).length;
      const rank = rows.indexOf(r) + 1;
      return h("tr", { class: r.sid === pick ? "sel" : null, tabindex: 0, style: "cursor:pointer", "aria-label": `${r.name}，看原因`,
        onclick: () => { pick = r.sid; store.set("scPick", pick); draw(); jumpTo(c4.el); },
        onkeydown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick = r.sid; store.set("scPick", pick); draw(); jumpTo(c4.el);
          const t = c4.el.querySelector("h3"); t.tabIndex = -1; t.focus({ preventScroll: true }); } } },
        h("td", { class: "rank" }, `#${rank}`),
        h("td", {}, r.name, ...(() => { const { agree, oppose } = scRefs(r); return [
          agree.length ? h("span", { class: "pill pill-ok", style: "margin-left:6px", title: agree.map((x) => x.label).join("、") }, "檢驗支持") : null,
          oppose.length ? h("span", { class: "pill pill-meh", style: "margin-left:6px", title: oppose.map((x) => x.label).join("、") }, "檢驗相反") : null]; })()),
        h("td", { class: "n" }, fin(r.cal) ? chg(r.cal, 1, "%") : h("span", { class: "muted" }, "—")),
        h("td", { class: "n" }, chg(r.ev, 1, "%"), h("span", { class: "sub" }, `${scPct(r.lo)}～${scPct(r.hi)}`)),
        h("td", { class: "n" }, fin(scStable(r)) ? `${fmtNum(scStable(r), 0)}%` : "—"),
        h("td", { class: "n" }, past.length ? `${win}/${past.length}` : "—"),
        h("td", { class: "n" }, `${up} 多／${dn} 空`),
        h("td", { class: "n" }, scPct(r.base)));
    };
    c3body.replaceChildren(banner,
      h("div", { class: `tbl-wrap${valid === "樣本外無效" ? " sc-void" : ""}` }, h("table", { class: "data sc-rank" },
        h("thead", {}, h("tr", {}, ["排名", "標的", "校準後期望超額", "模型值（80% 區間）", "樣本內穩定度", "最像時點同方向", "單一訊號", `平常 ${hz} 個月`]
          .map((t, i) => h("th", { class: i === 0 ? "rank" : i > 1 ? "n" : null,
            title: i === 4 ? "樣本內重抽 200 次（12 個月一塊），模型值和現在同方向的比例；只代表模型在樣本內穩不穩，不是賺錢的機率" : null }, t)))),
        h("tbody", {}, list.map(tr)))),
      h("div", { class: "chips", style: "margin-top:10px" },
        h("button", { class: "chip", type: "button", "aria-pressed": String(showAll), onclick: () => { store.set("scAll", !showAll); draw(); } },
          showAll ? "只看前 8 與後 5" : `顯示全部 ${rows.length} 個`),
        h("span", { class: "muted", style: "font-size:12.5px" }, "點一列看原因。超額＝之後報酬減掉該標的平常的平均（對數報酬）；可投資標的才排名，殖利率、VIX 等觀察指標不列入。")));
    why(rows.find((r) => r.sid === pick));
    drawChart();
  }
  mount(chartHost, drawChart);
  draw();
});

function h_empty(text) { return h("p", { class: "empty" }, text); }
