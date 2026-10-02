/* 沙盤推演的「推演總結」檢視（資料在 gfd/scenario.py 算好；公開版用到才下載）。分頁本身與檢視切換在 75-sandbox.js */

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

// 訊號的年齡：這一段亮了多久，和歷史上各段比（間隔 ≤ 3 個月的中斷算同一段）
function scAgeText(g) {
  const base = `這一段從 ${g.since} 起已 ${g.age} 個月（短暫中斷算同一段）；歷史上 ${g.n_done} 段中位數 ${fmtNum(g.median, 0)} 個月、最長 ${g.longest} 個月`;
  if (g.age <= 1) return base + "。";
  if (g.share_longer === 0) return base + "——沒有一段撐到這麼久，現在是最久的一次。";
  return base + `，撐到這麼久的有 ${fmtNum(g.share_longer, 0)}%。`;
}

/* 開頭結論：一兩句就好（2026-10-02 起細節數字移到下面的「重點數字」小卡；全部由資料組出來，隨上方期間切換重寫） */
function scenarioLead(S, hz) {
  if (!S.active.length) return "目前沒有任何訊號亮著，模型的期望超額全部是 0，沒有可以推演的方向。";
  const B = S.backtest[String(hz)];
  const v = B.ridge.verdict;
  const head = `${S.active.length} 個訊號亮著。`;
  if (v === "樣本外無效") return `${head}${hz} 個月的排名在樣本外沒有比亂選好，這個期間不列推薦；下面的推演只當描述。`;
  if (v === "樣本外有效") return `${head}${hz} 個月的排名在樣本外有效，但訊號與門檻是事後設計的，實際效果可能更差。`;
  return `${head}${hz} 個月的排名在樣本外時好時壞，不能當買賣依據，只是研究線索。先看下面的重點數字，點各卡片看原因。`;
}

/* 重點數字（2026-10-02）：開頭幾個最重要的數字，一格一個；隨期間切換重畫 */
function scenarioTiles(S, hz) {
  const B = S.backtest[String(hz)];
  const v = B.ridge.verdict;
  const rows = S.assets[String(hz)] || [];
  const top = rows[0];
  const val = (r) => (fin(r.cal) ? r.cal : r.ev);
  const oldest = S.active.filter((a) => a.age && a.age.n_done).sort((a, b) => b.age.age - a.age.age)[0];
  const nodes = S.paths.flatMap((p) => p.nodes.filter((n) => !n.triggered && fin(n.prob) && fin(n.base)).map((n) => ({ p, n })));
  const likely = nodes.sort((a, b) => (b.n.prob - b.n.base) - (a.n.prob - a.n.base))[0];
  const cs = S.case_summary && S.case_summary.model && S.case_summary.model[String(hz)];
  const HG = S.hedge && S.hedge.targets && S.hedge.targets[0];
  const hb = HG ? hgBest(HG) : null;
  const hs = hb ? hgStats(hb, hgSubset(HG, "all")) : null;
  const hr = hb && S.hedge.regime && S.hedge.regime.lit ? hgStats(hb, hgSubset(HG, "regime")) : null;
  return statTiles([
    { label: "亮著的訊號", value: `${S.active.length} 個`, tone: oldest && oldest.age.age > oldest.age.longest ? "warn" : null,
      sub: oldest ? `亮最久：${oldest.label}，已 ${oldest.age.age} 個月（歷史最長 ${oldest.age.longest}）` : null },
    v === "樣本外無效" ? { label: `${hz} 個月期望值最高`, value: "不列推薦", tone: "bad", sub: "這個期間的排名在樣本外沒有比亂選好" }
      : top ? { label: `${hz} 個月期望值最高`, value: h("span", {}, `${top.name} `, chg(val(top), 1, "%")),
        sub: fin(top.cal) ? `已依樣本外校準（模型值 ${scPct(top.ev)}）` : "模型值（沒有校準值）" } : null,
    { label: "這套排名可信嗎", value: v, tone: SC_VERDICT_TONE[v] || null,
      sub: `樣本外前 ${S.model.topk} 名平均每期多 ${fmtSigned(B.ridge.mean, 2)} 個百分點（不同起始月 ${scRange(B.ridge.offsets)}）` },
    cs && cs.n ? { label: `對答案：類似時點的 ${hz} 個月`, value: `${cs.hit}/${cs.n}`, tone: scSig(cs.p) ? "ok" : "meh",
      sub: `當時的模型跑贏全體的次數（${scP(cs.p)}，${scPWord(cs.p)}）` } : null,
    likely ? { label: "接下來最可能跟著成立", value: `${fmtNum(likely.n.prob, 0)}%`, tone: likely.n.prob - likely.n.base >= 10 ? "warn" : null,
      sub: `${likely.n.label}：${S.within} 個月內（平常 ${fmtNum(likely.n.base, 0)}%，${likely.p.name}）` } : null,
    hs && hs.n ? { label: `${HG.label}時最常一起漲`, value: `${hgName(hb)} ${hs.up}/${hs.n}`,
      sub: hr && hr.n ? `但${S.hedge.regime.short}開始的跌段只有 ${hr.up}/${hr.n}；看避險檢視` : "看避險檢視" } : null,
  ]);
}

const SCENARIO_SUMMARY = lazyTab("scenario", (root) => {
  const S = A.scenario;
  let hz = store.get("scH", 3);
  if (S && !S.horizons.includes(hz)) hz = S.horizons[0];
  root.replaceChildren(tabHead("沙盤推演：現在亮著的訊號，接下來可能怎麼走、哪些標的期望值較好",
    "把事件衝擊、傳導鏈、訊號劇本三個檢視接起來：訊號劇本告訴我們現在哪些訊號亮著；傳導鏈從亮著的層往下推，看下一層有多可能跟著成立；"
    + "期望值把所有亮著的訊號一起放進模型（每個標的之後 3／6／12 個月的報酬減掉它平常的平均，對全部訊號做收縮迴歸），"
    + "同時亮著、彼此重疊的訊號會分攤效果、不重複計算。模型值再乘上「樣本外校準斜率」（過去樣本外實際超額大約是模型值的幾倍），"
    + "得到比較實際的數字。最後附上事件衝擊（日線）裡相關事件類型的短期反應。全部是歷史統計，不是投資建議，也沒有計入交易成本。",
    false, null, S ? scenarioLead(S, hz) : null));
  if (!S || !S.active) { root.append(h_empty("尚未產生沙盤推演，請執行 python3 gfd.py analyze")); return; }
  const g = h("div", { class: "grid" });
  root.append(g);
  let pick = store.get("scPick", null);

  // ── 0. 重點數字（隨期間切換重畫，在 draw() 裡） ──
  const c0 = card({ title: "重點數字", span: 12 });
  g.append(c0.el);

  // ── 1. 現在亮著的訊號：每個訊號一列，原因點開才有 ──
  const circ = (i) => (i < 20 ? String.fromCharCode(0x2460 + i) : `(${i + 1})`);
  const c1 = card({ title: "現在亮著的訊號", span: 12,
    sub: `資料截至 ${S.asof}，和「訊號劇本」檢視同一套判定。長條＝這一段已經亮了幾個月（細線＝歷史各段的中位數、粗線＝最長的一段）；右邊是單獨看這個訊號，之後 6 個月最好與最差的標的（p ≤ 0.10）。點一列看原因。` });
  const sigRow = (a, i) => {
    const ag = a.age || {};
    const scale = Math.max(ag.age || 0, ag.longest || 0, 1);
    const pos = (v) => `${Math.min(100, (100 * v) / scale)}%`;
    const over = ag.n_done && ag.age > ag.longest;
    const pick = (list) => list.map((b) => h("span", { class: "sig-pick" }, `${b.name} `, chg(b.lift, 1, "%")));
    const det = h("details", { class: "sig-row" },
      h("summary", { class: "sig-sum" },
        h("span", { class: "sig-no" }, circ(i)),
        h("span", { class: "sig-name" }, h("b", {}, a.label), h("span", { class: "sub" }, `${a.source}・${a.current_at} 數值 ${fin(a.current) ? fmtNum(a.current, 2) : "—"}`)),
        h("span", { class: "sig-age", title: ag.n_done ? scAgeText(ag) : "" },
          h("span", { class: `sig-bar${over ? " over" : ""}` }, h("i", { class: "fill", style: `width:${pos(ag.age || 0)}` }),
            ag.n_done ? h("i", { class: "med", style: `left:${pos(ag.median)}` }) : null,
            ag.n_done ? h("i", { class: "max", style: `left:${pos(ag.longest)}` }) : null),
          h("span", { class: "sig-age-t" }, h("b", {}, `${ag.age ?? a.run} 個月`),
            ag.n_done ? h("span", { class: "muted" }, `　中位 ${fmtNum(ag.median, 0)}・最長 ${ag.longest}${over ? "・最久的一次" : ""}`) : null)),
        h("span", { class: "sig-picks" },
          a.best6.length ? h("span", {}, h("span", { class: "muted" }, "最好 "), ...pick(a.best6.slice(0, 2))) : null,
          a.worst6.length ? h("span", {}, h("span", { class: "muted" }, "最差 "), ...pick(a.worst6.slice(0, 2))) : null,
          !a.best6.length && !a.worst6.length ? h("span", { class: "muted" }, "沒有 p ≤ 0.10 的標的") : null)));
    det.addEventListener("toggle", () => {
      if (!det.open || det.childElementCount > 1) return;
      det.append(h("div", { class: "sig-more" },
        h("p", {}, h("b", {}, "為什麼看它："), a.why),
        ag.n_done ? h("p", {}, ...emNums(scAgeText(ag))) : null,
        h("p", {}, `歷史上出現過 ${a.episodes} 次；目前已連續 ${a.run} 個月。`),
        a.best6.length || a.worst6.length ? h("p", {}, "單獨看這個訊號，之後 6 個月（訊號劇本口徑，p ≤ 0.10）：",
          ...[...a.best6.map((b) => ["最好", b]), ...a.worst6.map((b) => ["最差", b])].map(([k, b], j) =>
            h("span", {}, j ? "；" : "", `${k} ${b.name} `, chg(b.lift, 1, "%"), h("span", { class: "muted" }, `（${b.n} 次、${scP(b.p)}）`)))) : null));
    });
    return det;
  };
  c1.body.append(h("div", { class: "sig-head", "aria-hidden": "true" }, h("span", {}), h("span", {}, "訊號"), h("span", {}, "這一段已亮"), h("span", {}, "單獨看之後 6 個月")),
    ...S.active.map(sigRow));
  if (S.similar && S.similar.length) {
    c1.body.append(h("h4", { class: "sub-h" }, "最像現在的歷史時點：當時也亮著的訊號打 ●（編號對照上面各列）"),
      h("div", { class: "tbl-wrap" }, h("table", { class: "data sim-mx" },
        h("thead", {}, h("tr", {}, h("th", {}, "時點"), h("th", { class: "n" }, "相似度"),
          ...S.active.map((a, i) => h("th", { class: "c", title: a.label }, circ(i))))),
        h("tbody", {}, S.similar.map((sm) => h("tr", {}, h("td", { class: "n" }, sm.m), h("td", { class: "n" }, fmtNum(sm.jaccard, 2)),
          ...S.active.map((a) => h("td", { class: "c", title: a.label }, sm.shared.includes(a.label) ? h("span", { class: "mx-on" }, "●") : h("span", { class: "mx-off" }, "·")))))))),
      h("p", { class: "note" }, `相似度 1＝亮著的訊號完全相同。現在這組最多只和歷史上 ${fmtNum(S.similar[0].jaccard, 2)} 的程度重疊——完全相同的組合沒有出現過，`
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
      const tip = n.triggered ? `${n.current_at} 數值 ${fmtNum(n.current, 2)}`
        : (n.after ? `接在「${n.after}」之後；歷史 ${n.n_episodes} 次` : "") + (fin(n.wait) ? `；成立的話中位數第 ${fmtNum(n.wait, 0)} 個月` : "");
      steps.push(h("div", { class: `sc-node ${tone}`, title: tip },
        h("div", { class: "sc-node-l" }, n.label),
        n.triggered || !fin(n.prob) ? h("div", { class: "sc-node-s" }, state) : [
          h("div", { class: "sc-gauge", "aria-hidden": "true" }, h("i", { class: "fill", style: `width:${n.prob}%` }),
            fin(n.base) ? h("i", { class: "base", style: `left:${n.base}%` }) : null),
          h("div", { class: "sc-node-s" }, h("b", { class: "sc-node-p" }, `${fmtNum(n.prob, 0)}%`), `　${S.within} 個月內・平常 ${fmtNum(n.base, 0)}%`),
          fin(n.prob12) ? h("div", { class: "sc-node-s muted" }, `12 個月 ${fmtNum(n.prob12, 0)}%（平常 ${fmtNum(n.base12, 0)}%）`) : null]));
    });
    const ifs = p.nodes.filter((n) => !n.triggered && fin(n.prob) && n.if_then && n.if_then.length);
    const st = p.state;
    const stTxt = !st ? null : st.n_episodes === 0 ? "照這條鏈現在的狀態（亮著的層都亮、其餘都沒亮），歷史上沒有出現過，推不到更下層。"
      : `照這條鏈現在的狀態（亮著的層都亮、其餘都沒亮），歷史上有 ${st.n_episodes} 段、${st.n_months} 個月：剩下的層在 12 個月內全部走完的比例 ${fmtNum(st.all, 0)}%`
        + `${st.n_episodes < 3 ? "——樣本太少，只是紀錄" : ""}。`;
    const fr = p.frontier;
    let frTxt = null;
    if (fr && fr.n_months) {
      const depth = Object.entries(fr.depth).map(([d, pct]) => `再亮 ${d} 層 ${fmtNum(pct, 0)}%`).join("、");
      frTxt = h("p", { class: "sc-state" },
        `從目前最深的「${fr.deepest_label}」往下看（它下面的層：${fr.below.join("、")}）：歷史上這一層亮著、下面的層都還沒亮的有 ${fr.n_episodes} 段（${fr.n_months} 個月），12 個月內${depth}；`
        + `緊接的下一層「${fr.next_label}」6 個月內亮起 ${fmtNum(fr.prop, 0)}%；這一層熄掉（連續熄超過 3 個月）又沒傳到下一層（斷鏈）${fmtNum(fr.broke, 0)}%。`,
        fr.circular ? h("span", { class: "muted" }, `　下一層就是末端「${fr.term_name}」，末端的報酬不另外分組（分了會變成同義反覆）。`)
          : fr.term_if.n && fr.term_else.n ? h("span", {}, `末端「${fr.term_name}」6 個月：下一層 6 個月內有亮時中位 `, chg(fr.term_if.median, 1, "%"), `（${fr.term_if.n} 次），沒有時 `, chg(fr.term_else.median, 1, "%"), `（${fr.term_else.n} 次）。`) : null,
        fr.n_episodes < 5 ? h("span", { class: "muted" }, "　樣本很少，只是紀錄。") : null);
    }
    // 關鍵數字（2026-10-02）：從最深一層往下的傳導、斷鏈、照現在狀態全部走完；完整句子在「推演細節」
    const kchip = (label, value, sub) => h("span", { class: "kchip" }, h("span", { class: "k-l" }, label), h("b", {}, value), sub ? h("span", { class: "k-s" }, sub) : null);
    const kc = [];
    if (fr && fr.n_months) {
      kc.push(kchip("12 個月內再往下亮 ≥ 1 層", `${fmtNum(100 - (fr.depth["0"] || 0), 0)}%`, `從「${fr.deepest_label}」往下・${fr.n_episodes} 段`),
        kchip("斷鏈", `${fmtNum(fr.broke, 0)}%`, "這層熄掉、沒傳到下一層"));
      if (!fr.circular && fr.term_if.n && fr.term_else.n) {
        kc.push(kchip(`末端「${fr.term_name}」6 個月`, h("span", {}, chg(fr.term_if.median, 1, "%"), h("span", { class: "muted" }, " vs "), chg(fr.term_else.median, 1, "%")),
          `下一層有亮（${fr.term_if.n} 次）vs 沒亮（${fr.term_else.n} 次）`));
      }
    }
    if (st && st.n_episodes) kc.push(kchip("照現在狀態，剩下的層 12 個月內全部走完", `${fmtNum(st.all, 0)}%`, `${st.n_episodes} 段${st.n_episodes < 3 ? "・樣本太少" : ""}`));
    else if (st) kc.push(kchip("照現在狀態", "沒出現過", "歷史上沒有一模一樣的狀態"));
    const more = stTxt || frTxt || ifs.length ? moreBox("推演細節",
      stTxt ? h("p", { class: "sc-state" }, ...emNums(stTxt)) : null,
      frTxt,
      ifs.length ? h("ul", { class: "sc-ifs" }, ifs.map((n) => h("li", {}, `如果「${n.label}」也成立：訊號劇本裡通過三道檢驗的是 `,
        n.if_then.map((r, k) => h("span", {}, k ? "、" : "", `${r.name} ${r.horizon} 個月超額 `, chg(r.lift, 1, "%"))), "。"))) : null) : null;
    c2.body.append(h("div", { class: "sc-path" },
      h("div", { class: "sc-path-h" }, h("b", {}, p.name), h("span", { class: "muted" }, `　${p.active}/${p.of} 層成立`)),
      h("div", { class: "sc-steps" }, steps),
      kc.length ? h("div", { class: "kchips" }, kc) : null,
      more));
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

  // ── 2c. 避險摘要（細節在「避險」檢視，66-hedge.js）──
  const HG = S.hedge;
  if (HG && HG.targets && HG.targets.length) {
    const R = HG.regime;
    const cH = card({ title: "避險：如果真的跌了", span: 12,
      sub: `每個下跌情境：${HG.W} 個月內發生的機率、全部跌段裡最穩的避險資產（上漲次數／段數）`
        + (R && R.lit ? `，以及同一項在和現在一樣「${R.short}」開始的跌段裡的表現（只有個位數段，只能參考）。` : "。") });
    const btn = h("button", { class: "tool", type: "button", onclick: () => window.gotoTab("scenario", () => { window.scView = "hedge"; }) }, "看避險檢視 →");
    cH.tools.append(btn);
    const cell = (x, s) => (x && s && s.n ? h("span", {}, `${hgName(x)} `, h("b", { class: "mono" }, `${s.up}/${s.n}`), h("span", { class: "muted" }, `　中位 ${hgPct(s.med)}`)) : h("span", { class: "muted" }, "—"));
    cH.body.append(h("div", { class: "tbl-wrap" }, h("table", { class: "data" },
      h("thead", {}, h("tr", {}, h("th", {}, "下跌情境"), h("th", { class: "n" }, `${HG.W} 個月內`), h("th", {}, "全部跌段最穩"),
        R && R.lit ? h("th", {}, `${R.short}開始的跌段`) : null)),
      h("tbody", {}, HG.targets.map((T) => {
        const o = T.odds || {};
        const b = hgBest(T);
        const idx = R ? hgSubset(T, "regime") : [];
        return h("tr", {},
          h("td", {}, T.label, h("span", { class: "sub" }, `過去 ${T.n} 段・中位 ${hgPct(T.med)}`)),
          h("td", { class: "n" }, o.ongoing ? h("b", {}, "進行中") : fin(o.prob) ? h("span", {}, h("b", {}, `${fmtNum(o.prob, 0)}%`), h("span", { class: "muted" }, `（平常 ${fmtNum(o.base, 0)}%）`)) : h("span", { class: "muted" }, `—（平常 ${fmtNum(o.base, 0)}%）`)),
          h("td", {}, cell(b, b && hgStats(b, hgSubset(T, "all")))),
          R && R.lit ? h("td", {}, idx.length ? cell(b, b && hgStats(b, idx)) : h("span", { class: "muted" }, "沒有這樣的跌段")) : null);
      })))),
      h("p", { class: "note" }, "段數都只有個位數到二十幾段；每一段的報酬、配置試算（換多少比例能少跌多少、平常少賺多少）在避險檢視。"));
    g.append(cH.el);
  }

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
    const mt = (x) => (mm[x] && mm[x].n ? { label: `公平的考試：當時的模型・${x} 個月`, value: `${mm[x].hit}/${mm[x].n}`, tone: scSig(mm[x].p) ? "ok" : "meh",
      sub: `前 ${S.model.topk} 名跑贏全體的次數；平均每次 ${fmtSigned(mm[x].spread_mean, 2)} 個百分點（${scP(mm[x].p)}，${scPWord(mm[x].p)}）` } : null);
    cA.body.append(statTiles([mt("3"), mt("6"),
      ly.n ? { label: "傳導鏈的下一層（Brier，越小越準）", value: fmtNum(ly.brier, 3), tone: ly.skill > 0 ? "ok" : "bad",
        sub: `直接用平常比例是 ${fmtNum(ly.brier_base, 3)}——${ly.skill > 0 ? "比平常比例準" : "比平常比例還不準"}（${ly.n} 次預測）` } : null,
      wv.n ? { label: "下一波訊號", value: `${wv.hits}/${wv.n}`, tone: scSig(wv.p) ? "ok" : "meh",
        sub: `實際亮起 ${fmtNum(100 * wv.hits / wv.n, 0)}%，平常約 ${fmtNum(wv.base, 0)}%：${scWaveWord(wv)}（${scP(wv.p)}）` } : null,
      td["3"] && td["3"].n ? { label: "今天的前 5 名放回這些時點・3 個月", value: `${td["3"].hit}/${td["3"].n}`,
        sub: "樣本內（今天的模型就是從這些歷史學來的），不是公平的考試" } : null]));
    cA.body.append(moreBox("這些數字怎麼讀", h("ul", { class: "finds" },
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
          + "。今天的模型就是從這些歷史學來的，對得上是應該的，只能看出「在哪幾次會錯、錯多少」。")))));
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
          ...c.wave.map((w, k) => h("span", {}, k ? "、" : "", ok(w.actual), ` ${w.label}（${fmtNum(w.prob, 0)}% vs 平常 ${fmtNum(w.base, 0)}%）`))) : null,
        h("p", { class: "sc-case-p" }, h("b", {}, "後來實際發生（事後資料，只做對照）："),
          Array.isArray(c.events_after) ? (c.events_after.length ? `之後一年內的事件：${c.events_after.map((e) => `${e.date.slice(0, 7)} ${e.name}`).join("、")}。` : "之後一年內沒有收錄的重大事件。") : null,
          c.chains_after && c.chains_after.length ? h("span", {}, h("br"), "各鏈走到：", c.chains_after.map((x, k) => h("span", {}, k ? "；" : "", `${x.chain} ${x.on}/${x.of} 層亮著`,
            x.rest ? `，之後一年再亮 ${x.lit.length}/${x.rest} 層${x.lit.length ? `（${x.lit.join("、")}）` : ""}` : "，已是最末層")), "。") : null,
          c.actual6 ? h("span", {}, h("br"), "6 個月實際比全體多最多：", ...c.actual6.best.map((x, k) => h("span", {}, k ? "、" : "", `${x.name} `, chg(x.v, 1, ""))),
            "；最少：", ...c.actual6.worst.map((x, k) => h("span", {}, k ? "、" : "", `${x.name} `, chg(x.v, 1, "")))) : null)));
    }
  }
  g.append(cA.el);

  // ── 5. 事件衝擊 ──
  const c5 = card({ title: "相關事件類型的短期反應（事件衝擊・日線）", span: 12,
    sub: "亮著的訊號對應到事件衝擊檢視裡的事件類型，看這類事件發生後一個月、兩個月，各標的比平常多或少多少。這是「事件一爆發」的短期反應，月資料的訊號比較像慢慢累積的狀態，只能當參考。" });
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
  if (fin(S.event_luck)) c5.body.append(h("p", { class: "note" }, `事件衝擊整體估計約 ${fmtNum(S.event_luck, 0)}% 的顯著結果是運氣（見事件衝擊檢視），單一類型的數字請保守看待。`));
  g.append(c5.el);

  // ── 6. 這套推演可信嗎 ──
  const c6 = card({ title: "這套推演可信嗎：走步樣本外回測", span: 12,
    sub: `從 ${S.model.eval_start} 起每個月只用「當時已經知道結果」的資料重估模型，買期望值最高的 ${S.model.topk} 個標的，和全體平均比。` });
  c6.body.append(moreBox("方法細節",
    h("p", {}, `全體＝當期有資料的標的（${(S.backtest[String(S.horizons[0])].n_assets || []).join("～")} 個）。`
      + "世界銀行商品價格與央行匯率是月均價，月底時已經包含過去半個月，所以這些標的的報酬一律從下個月的均價算起，估計時也多退一個月（不這樣做回測會偷看未來，3 個月的差距會被灌大好幾倍）。"
      + "期間互相重疊不能當獨立樣本，所以每隔 h 個月取一期、每個起點各算一次，列出範圍。")));
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
    parts.push(statTiles([
      { label: "校準後期望超額", value: fin(r.cal) ? chg(r.cal, 1, "%") : "—", sub: fin(r.cal) ? "模型值乘上樣本外校準斜率，比較實際的數字" : "這個期間樣本外無效，不給校準值" },
      { label: "模型值", value: chg(r.ev, 1, "%"), sub: `80% 區間 ${scPct(r.lo)}～${scPct(r.hi)}` },
      { label: "樣本內重抽同方向", value: fin(scStable(r)) ? `${fmtNum(scStable(r), 0)}%` : "—", sub: "重抽 200 次和現在同方向的比例；只代表模型穩不穩，不是賺錢的機率" },
      { label: `它平常 ${hz} 個月`, value: scPct(r.base), sub: "超額＝之後報酬減掉這個平常值" },
    ]));
    if (!valid) parts.push(h("p", { class: "sc-banner t-bad" }, h("b", {}, "注意："), `${hz} 個月的排名在樣本外沒有比亂選好，下面的原因只是描述，不能當依據。`));
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
      parts.push(h("h4", { class: "sub-h" }, "相關事件類型發生後（事件衝擊・日線）：比平常多或少"),
        h("div", { class: "tbl-wrap" }, h("table", { class: "data" },
          h("thead", {}, h("tr", {}, ["事件類型", "一個月", "兩個月", "走完一半", "事件數"].map((t, i) => h("th", { class: i ? "n" : null }, t)))),
          h("tbody", {}, r.events.map((e) => h("tr", {},
            h("td", {}, e.cat_name),
            h("td", { class: "n" }, chg(e.excess21, 1, "%"), h("span", { class: "sub" }, scP(e.p21))),
            h("td", { class: "n" }, chg(e.excess42, 1, "%"), h("span", { class: "sub" }, scP(e.p42))),
            h("td", { class: "n" }, fin(e.half_day) ? `第 ${fmtNum(e.half_day, 0)} 天` : "—"),
            h("td", { class: "n" }, String(e.n))))))));
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
    c0.body.replaceChildren(scenarioTiles(S, hz));
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
