/* 沙盤推演的「避險」檢視（2026-10-02）：如果真的跌了，手上什麼會漲、能補回多少、平常要付出多少。
   資料在 gfd/hedge.py 算好，和沙盤推演同一包延後下載。先給數字與圖（風險、每次跌段一點、配置試算），
   文字說明收在點開才看到的地方。2026-10-03 加日線版（波段高點 → 低點），和月資料版（最深的 3 個月）切換；預設日線。 */

// 判定用中性的可信度色，不用漲跌色（本站紅漲綠跌，紅綠在這裡會被讀成好壞）
const HG_TONE = { "穩定避險": "ok", "有點幫助": "meh", "沒幫助": "bad", "跟著跌": "bad", "樣本不足": "bad" };
const HG_RANK = { "穩定避險": 0, "有點幫助": 1, "沒幫助": 2, "樣本不足": 3, "跟著跌": 4 };
const HG_ROWS = 8;            // 預設列出幾項，其餘按「顯示全部」
const hgName = (x) => (x.custom ? x.name : shortName(x.sid));
const hgPct = (v, d = 1) => (fin(v) ? fmtSigned(v, d, "%") : "—");
const hgPP = (v) => `${Math.abs(v).toFixed(1)} 個百分點`;
// 英文或數字結尾的名稱（S&P 500、DXY）後面接中文時空一格
const hgSp = (t) => (/[A-Za-z0-9]$/.test(t) ? t + " " : t);
function hgMedian(vals) {
  const s = vals.filter(fin).sort((a, b) => a - b);
  const n = s.length;
  return n ? (n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2) : null;
}
// 環境：all＝全部跌段；regime＝設定的環境訊號；其他＝現在亮著的某個訊號，跌段開始時也亮著
function hgSubset(T, env) {
  const keep = (e) => env === "all" || (env === "regime" ? e.regime : e.lit.includes(env));
  return T.episodes.map((e, i) => (keep(e) ? i : -1)).filter((i) => i >= 0);
}
function hgStats(x, idx) {
  const v = idx.map((i) => x.rets[i]).filter(fin);
  return { n: v.length, up: v.filter((r) => r > 0).length, med: hgMedian(v), worst: v.length ? Math.min(...v) : null };
}
function hgEnvName(H, env) {
  if (env === "all") return "全部跌段";
  if (env === "regime") return H.regime.short;
  const s = H.lit.find((l) => l.id === env);
  return s ? `「${s.label}」時` : env;
}
// 全部跌段裡最可靠的一項：先看判定，再看中位數
const hgBest = (T) => [...T.hedges].sort((a, b) => HG_RANK[a.verdict] - HG_RANK[b.verdict] || b.med - a.med)[0];
const hgDaily = (H) => (H && H.daily && H.daily.targets && H.daily.targets.length ? H.daily : null);
// 日線版的目標（同一個觸發 id）；沒有就用月資料版
const hgPrefer = (H, id) => { const D = hgDaily(H); return (D && D.targets.find((x) => x.id === id)) || H.targets.find((x) => x.id === id); };
// 「同樣長度的對照視窗」的說法：日線是同樣交易日數、月資料是 3 個月
const hgWin = (T) => (T.L ? `同樣 ${T.L} 個交易日` : "3 個月");

/* 開頭結論（全部由資料組出來；換目標時重寫） */
function hedgeLead(H, T) {
  const M = H.targets.find((x) => x.id === T.id) || T;      // 機率是月資料版的事件（傳導鏈推算）
  const o = M.odds || {};
  const risk = o.ongoing ? `「${M.label}」現在就成立（${o.current_at} 近 3 個月 ${hgPct(o.current)}）。`
    : fin(o.prob) ? `「${M.label}」接下來 ${H.W} 個月內發生的機率 ${fmtNum(o.prob, 0)}%（平常 ${fmtNum(o.base, 0)}%）。`
    : `「${M.label}」：傳導鏈的上游還沒成立，平常 ${H.W} 個月內發生的比例是 ${fmtNum(o.base, 0)}%。`;
  const b = hgBest(T);
  if (!b) return risk;
  const sAll = hgStats(b, hgSubset(T, "all"));
  const nm = hgSp(hgName(b));
  const head = T.L ? `日線看 ${T.first.slice(0, 4)} 年以來「${T.label}」的 ${T.n} 段下跌` : `過去「${T.label}」的 ${T.n} 段下跌`;
  let txt = `${head}，${nm}${sAll.n < T.n ? `有資料的 ${sAll.n} 段裡` : ""}有 ${sAll.up} 段同時上漲（中位 ${hgPct(sAll.med)}，${b.verdict}${fin(b.p) ? `，${scP(b.p)}` : ""}）`;
  const R = H.regime;
  const idx = R ? hgSubset(T, "regime") : [];
  if (R && R.lit && idx.length >= 3) {
    // 環境分組只有個位數段：只講「同一項」在這幾段怎麼樣，不在這麼少的段裡另外挑贏家（挑出來的多半是運氣）
    const s = hgStats(b, idx);
    const worse = s.n && s.up / s.n < sAll.up / sAll.n - 0.1;
    txt += `；${worse ? "但" : ""}現在是${R.short}，這種環境下開始的只有 ${s.n} 段，它${worse ? "只有" : "有"} ${s.up} 段上漲（中位 ${hgPct(s.med)}）`
      + `——段數太少只能參考，其他資產在這幾段的表現按下方「${R.short}」看`;
  }
  return `${risk}${txt}。下面每個點就是一段。`;
}

// 多重檢定：這一版做了幾次檢定、p 夠小的有幾個、純運氣期望幾個
function hgMulti(targets, R, label) {
  const ps = targets.flatMap((T) => T.hedges).map((x) => x.p).filter(fin);
  const k = ps.filter((p) => p <= R.stable_p).length, k2 = ps.filter((p) => p <= 0.01).length;
  return `${label}做了 ${ps.length} 次檢定，p ≤ ${R.stable_p} 的有 ${k} 個（全是運氣也會有約 ${Math.round(ps.length * R.stable_p)} 個）、`
    + `p ≤ 0.01 的有 ${k2} 個（運氣約 ${Math.round(ps.length * 0.01)} 個）`;
}

const HEDGE_VIEW = lazyTab("scenario", (root) => {
  const H = A.scenario && A.scenario.hedge;
  const R = H && H.rules;
  const DL = hgDaily(H);
  root.replaceChildren(tabHead("避險：如果真的跌了，什麼會漲、能補回多少",
    R ? (DL ? `日線版（預設）：從波段高點跌超過門檻（${DL.targets.map((T) => `${T.label.replace(/從波段高點跌.*/, "")} ${T.thr}%`).join("、")}）算一段下跌，`
      + "之後從低點反彈超過同一門檻才確認見底（zigzag，一段只算一次）；每個資產看同一段高點到低點的報酬（當天或之前最近一天的收盤，台股比美國早收半天，對幾週以上的下跌影響很小）。"
      + "債券基金用含配息的日線；公用事業、必需消費股只有價格（不含股息）。p 值把每一段換成同樣長度、隨機起點的視窗比。日線每週更新。" : "")
      + `月資料版：跌段用傳導鏈同一個條件（例：台股 3 個月跌 ≥ 5%），亮燈的月份間隔 ≤ 3 個月算同一段，每段取最深的那 3 個月——一段只算一次，`
      + "2008 年這種長跌段不會重複算十幾次。每個資產看同一個 3 個月（月底收盤到月底收盤）的報酬：上漲次數就是「保護率」，另看中位數與最差一次。"
      + `判定只看全部跌段：穩定避險＝中位數 > 0、上漲 ≥ ${R.stable_up}%，而且跌段中的中位數明顯高於隨機挑同樣多個 3 個月（p ≤ ${R.stable_p}，跌的時候特別會漲，不只是平常就在漲）；`
      + `有點幫助＝中位數 > 0、上漲 ≥ ${R.help_up}%；跟著跌＝中位數 ≤ ${R.fall_med}%、上漲 ≤ ${R.fall_up}%；跌段少於 ${R.min_n} 段不判定。`
      + `${[DL ? hgMulti(DL.targets, R, "日線版四個情境") : null, hgMulti(H.targets, R, "月資料版四個情境")].filter(Boolean).join("；")}。`
      + "沒有做多重檢定校正，所以只有 p 很小的那幾個比較可信，單一個「穩定避險」要和段數、其他情境一起看。"
      + "環境分組（例：利率上行時開始的跌段）通常只有個位數段，只畫出來對照、不下判定。"
      + "報酬是各資產的原幣報酬，沒有換算成新台幣、沒有交易成本；黃金、原油、匯率用月線收盤（不是月均價），才不會和指數錯開時間。全部是歷史統計，不是投資建議。" : "",
    false, null, H && H.targets.length ? " " : null));
  if (!H || !H.targets || !H.targets.length) { root.append(h_empty("尚未產生避險資料，請執行 python3 gfd.py analyze")); return; }
  const leadEl = root.querySelector(".tab-lead");
  const g = h("div", { class: "grid" });
  root.append(g);

  const st = { t: store.get("hgT", null), env: store.get("hgEnv", "all"), pick: store.get("hgPick", null), w: store.get("hgW", 20), all: false,
    mode: store.get("hgMode", "daily") };
  if (!H.targets.some((T) => T.id === st.t)) st.t = H.targets[0].id;
  if (st.mode !== "daily" || !DL) st.mode = DL && st.mode === "daily" ? "daily" : "monthly";
  const envOk = (env) => env === "all" || (env === "regime" && H.regime) || H.lit.some((l) => l.id === env);
  if (!envOk(st.env)) st.env = "all";
  const tset = () => (st.mode === "daily" && DL ? DL.targets : H.targets);       // 目前看的版本
  const cur = () => tset().find((T) => T.id === st.t) || tset()[0];

  // ── 1. 下跌風險：四個情境，點一個就換下面的目標 ──
  const c1 = card({ title: "下跌風險", span: 12,
    sub: `大字＝接下來 ${H.W} 個月內發生的機率（傳導鏈推算），細線標記＝平常的比例。點一格，下面兩張卡就換成那個情境。` });
  const tiles = h("div", { class: "hg-tiles", role: "group", "aria-label": "選擇要避險的下跌情境" });
  const why = h("details", { class: "hg-why" }, h("summary", {}, "這些機率怎麼來的"));
  c1.body.append(tiles, why);
  g.append(c1.el);

  // ── 2. 跌的時候，誰會漲 ──
  const c2 = card({ title: "跌的時候，誰會漲", span: 12,
    sub: "每一列一項資產，每個點是一次跌段裡它的 3 個月報酬（紅＝漲、綠＝跌，台灣慣例）；直線是中位數；右邊是上漲次數。點一列看每一段的細節。" });
  const envBar = h("div", { class: "chips", role: "group", "aria-label": "跌段的環境" });
  const envSel = h("select", { class: "hg-sel", "aria-label": "依其他現在亮著的訊號分組" });
  const axis = h("div", { class: "hg-axis", "aria-hidden": "true" });
  const rows = h("div", { class: "hg-rows" });
  const more = h("button", { class: "tool hg-more-btn", type: "button" });
  const modeBar = h("div", { class: "chips", role: "group", "aria-label": "下跌段的算法" });
  c2.body.append(DL ? h("div", { class: "hg-ctl hg-env hg-moderow" }, h("span", { class: "muted" }, "下跌段："), modeBar) : null,
    h("div", { class: "hg-ctl hg-env hg-envrow" }, h("span", { class: "muted" }, "開始時："), envBar, envSel), axis, rows, more);
  c2.el.append(h("p", { class: "note" }, "判定（右邊標籤）與排列順序一律看全部跌段；換成某種環境時，只有亮著的點、上漲次數與中位數改算那幾段。"
    + "持有美元資產的台灣投資人，還要再加上「美元（對新台幣）」那一列的變化。"));
  g.append(c2.el);

  // ── 3. 配置試算 ──
  const c3 = card({ title: "配置試算：拿一部分換成避險資產", span: 12,
    sub: "假設原本全部放在目標指數，把其中一部分換成選的資產，看跌的時候少跌多少、其他時候少賺多少（原幣計、沒有交易成本）。" });
  const pickSel = h("select", { class: "hg-sel", "aria-label": "避險資產" });
  const range = h("input", { type: "range", min: "0", max: String(Math.max(...H.mix_w)), step: "5", value: String(st.w), "aria-label": "避險部位比例", class: "hg-range" });
  const wLab = h("b", { class: "hg-wlab" });
  const stats = h("div", { class: "hg-stats" });
  const perEp = h("details", { class: "hg-why" }, h("summary", {}, "每一段的結果"));
  c3.body.append(h("div", { class: "hg-ctl" }, h("label", {}, "換成 ", pickSel), h("label", { class: "hg-wrap" }, "比例 ", range, wLab)), stats, perEp);
  g.append(c3.el);

  function set(patch) {
    Object.assign(st, patch);
    if ("t" in patch) { store.set("hgT", st.t); st.all = false; }
    if ("env" in patch) store.set("hgEnv", st.env);
    if ("pick" in patch) store.set("hgPick", st.pick);
    if ("mode" in patch) { store.set("hgMode", st.mode); st.all = false; }
    draw();
  }

  function drawTiles() {
    tiles.replaceChildren(...H.targets.map((T) => {
      const o = T.odds || {};
      const lift = fin(o.prob) && fin(o.base) ? o.prob - o.base : null;
      const big = o.ongoing ? "進行中" : fin(o.prob) ? `${fmtNum(o.prob, 0)}%` : "—";
      const cap = o.ongoing ? `${o.current_at} 近 3 個月 ${hgPct(o.current)}`
        : fin(o.prob) ? `${H.W} 個月內・平常 ${fmtNum(o.base, 0)}%` : `上游未成立・平常 ${fmtNum(o.base, 0)}%`;
      return h("button", { class: `hg-tile${o.ongoing ? " now" : lift >= 10 ? " likely" : ""}`, type: "button",
        "aria-pressed": String(T.id === st.t), onclick: () => { if (T.id !== st.t) set({ t: T.id }); } },
        h("span", { class: "hg-tile-l" }, T.label),
        h("span", { class: "hg-tile-big" }, big),
        h("span", { class: "hg-gauge", "aria-hidden": "true" },
          o.ongoing ? h("i", { class: "fill", style: "width:100%" }) : fin(o.prob) ? h("i", { class: "fill", style: `width:${o.prob}%` }) : null,
          !o.ongoing && fin(o.base) ? h("i", { class: "base", style: `left:${o.base}%` }) : null),
        h("span", { class: "hg-tile-s" }, cap),
        (() => { const V = st.mode === "daily" && DL ? (DL.targets.find((x) => x.id === T.id) || T) : T;
          return h("span", { class: "hg-tile-s muted" }, `${V.L ? "日線" : "過去"} ${V.n} 段・中位 ${hgPct(V.med)}・最深 ${hgPct(V.worst)}`); })());
    }));
    why.replaceChildren(h("summary", {}, "這些機率怎麼來的"), h("ul", { class: "hg-list" }, H.targets.map((T) => {
      const o = T.odds || {};
      if (o.ongoing) return h("li", {}, h("b", {}, T.label), `：${o.current_at} 已成立（${o.chain}的一層），所以沒有「會不會發生」的機率；下面看的是它跌的時候什麼會漲。`);
      if (!o.chains || !o.chains.length) return h("li", {}, h("b", {}, T.label), `：所在的傳導鏈上游都還沒成立，只有平常比例（任何一個月之後 ${H.W} 個月內發生的比例 ${fmtNum(o.base, 0)}%）。`);
      return h("li", {}, h("b", {}, T.label), "：", o.chains.map((c, k) => h("span", {}, k ? "；" : "",
        `${c.chain}——上游「${c.after}」亮著時，歷史 ${c.n_episodes} 段裡 ${H.W} 個月內跟著發生 ${fmtNum(c.prob, 0)}%（平常 ${fmtNum(c.base, 0)}%），`
        + `12 個月內 ${fmtNum(c.prob12, 0)}%（平常 ${fmtNum(c.base12, 0)}%）`)),
        o.chains.length > 1 ? "。大字取最高的那條（避險照較壞的情況準備）。" : "。");
    })));
  }

  function drawEnv(T) {
    const opts = [["all", `全部 ${T.episodes.length} 段`]];
    if (H.regime) opts.push(["regime", `${H.regime.short} ${hgSubset(T, "regime").length} 段${H.regime.lit ? "・現在就是" : ""}`]);
    envBar.replaceChildren(...opts.map(([k, label]) => h("button", { class: "chip", type: "button", "aria-pressed": String(st.env === k),
      onclick: () => set({ env: k }) }, label)));
    const others = H.lit.filter((l) => l.id !== (H.regime && H.regime.id) && l.id !== T.id);
    envSel.replaceChildren(h("option", { value: "" }, "其他現在亮著的訊號…"),
      ...others.map((l) => h("option", { value: l.id }, `${l.label}（${hgSubset(T, l.id).length} 段）`)));
    envSel.value = others.some((l) => l.id === st.env) ? st.env : "";
    envSel.onchange = () => set({ env: envSel.value || "all" });
    envSel.hidden = !others.length;
  }

  function hedgeRow(T, x, idx, D) {
    const s = hgStats(x, idx);
    const inSet = new Set(idx);
    const pos = (v) => 50 + 50 * Math.max(-1, Math.min(1, v / D));
    const nm = hgName(x), tn = shortName(T.sid);
    const dots = x.rets.map((v, i) => {
      if (!fin(v)) return null;
      const e = T.episodes[i];
      return h("span", { class: `hg-dot ${v > 0 ? "up" : "down"}${inSet.has(i) ? "" : " off"}${Math.abs(v) > D ? " clip" : ""}`, style: `left:${pos(v)}%`,
        title: `${e.m0}→${e.m1}：${tn} ${hgPct(e.ret)}，${nm} ${hgPct(v)}${e.regime && H.regime ? `（${H.regime.short}）` : ""}` });
    });
    const sum = h("summary", { class: "hg-sum" },
      h("span", { class: "hg-name" }, nm),
      h("span", { class: "hg-strip", role: "img", "aria-label": `${nm}：${s.n} 段中 ${s.up} 段上漲，中位 ${hgPct(s.med)}` },
        h("i", { class: "hg-zero" }), ...dots, fin(s.med) ? h("i", { class: "hg-med", style: `left:${pos(s.med)}%` }) : null),
      h("span", { class: "hg-cnt", title: "上漲次數／有資料的段數" }, h("b", {}, String(s.up)), `/${s.n}`),
      h("span", { class: `hg-medv ${dirClass(s.med)}` }, hgPct(s.med)),
      h("span", { class: `pill pill-${HG_TONE[x.verdict]}`, title: "全部跌段的判定" }, x.verdict));
    const det = h("details", { class: "hg-row" }, sum);
    // 細節用到才畫（展開時）
    det.addEventListener("toggle", () => { if (det.open && det.childElementCount === 1) det.append(hedgeMore(T, x)); });
    return det;
  }

  function hedgeMore(T, x) {
    const nm = hgName(x), tn = shortName(T.sid);
    const k = hgStats(x, hgSubset(T, "all")).up;
    const worstI = x.rets.indexOf(x.worst);
    const rnd = T.L ? "同樣長度、隨機起點的視窗" : "隨便挑的 3 個月";
    const pTxt = !fin(x.p) ? "" : x.p <= 0.05 ? `跌段中的表現明顯好於${rnd}（${scP(x.p)}）——跌的時候特別會漲，不只是平常就在漲。`
      : x.p <= 0.10 ? `跌段中的表現略好於${rnd}（${scP(x.p)}，邊際）。`
      : `和${rnd}分不太出來（${scP(x.p)}）——${x.med > 0 ? "上漲多半是它平常就在漲，不是因為跌段。" : "跌段沒有讓它特別會漲。"}`;
    const envs = [["all", "全部跌段"]];
    if (H.regime) envs.push(["regime", `${H.regime.short}（${H.regime.label}）`]);
    for (const l of H.lit) if (l.id !== (H.regime && H.regime.id) && l.id !== T.id) envs.push([l.id, l.label]);
    const envRows = envs.map(([env, label]) => [label, hgStats(x, hgSubset(T, env))]).filter(([, s]) => s.n);
    return h("div", { class: "hg-more" },
      h("p", {}, `${hgSp(tn)}的 ${x.n} 段下跌裡，${hgSp(nm)}有 ${k} 段上漲（${fmtNum(x.up, 0)}%），中位數 ${hgPct(x.med)}，`
        + `最好 ${hgPct(x.best)}、最差 ${hgPct(x.worst)}${worstI >= 0 ? `（${T.episodes[worstI].m0}→${T.episodes[worstI].m1}）` : ""}。${pTxt}`
        + `其他時候（不在跌段、${hgWin(T)}）中位 ${hgPct(x.calm)}。`),
      h("h4", { class: "sub-h" }, "依跌段開始時的環境"),
      h("div", { class: "tbl-wrap" }, h("table", { class: "data" },
        h("thead", {}, h("tr", {}, h("th", {}, "跌段開始時"), h("th", { class: "n" }, "段數"), h("th", { class: "n" }, "上漲"), h("th", { class: "n" }, "中位"), h("th", { class: "n" }, "最差"))),
        h("tbody", {}, envRows.map(([label, s]) => h("tr", {}, h("td", {}, label), h("td", { class: "n" }, String(s.n)),
          h("td", { class: "n" }, `${s.up}/${s.n}`), h("td", { class: "n" }, chg(s.med, 1, "%")), h("td", { class: "n" }, chg(s.worst, 1, "%"))))))),
      h("h4", { class: "sub-h" }, "每一段"),
      h("div", { class: "tbl-wrap" }, h("table", { class: "data" },
        h("thead", {}, h("tr", {}, h("th", {}, "期間"), h("th", { class: "n" }, tn), h("th", { class: "n" }, nm), h("th", {}, "環境"))),
        h("tbody", {}, T.episodes.map((e, i) => h("tr", {}, h("td", { class: "n" }, `${e.m0}→${e.m1}`, T.L ? h("span", { class: "sub" }, `${e.days} 個交易日`) : null),
          h("td", { class: "n" }, chg(e.ret, 1, "%")),
          h("td", { class: "n" }, fin(x.rets[i]) ? chg(x.rets[i], 1, "%") : "—"),
          h("td", { class: "muted" }, [e.regime && H.regime ? H.regime.short : "", e.recent ? "最近一段（可能還沒結束）" : ""].filter(Boolean).join("・"))))))));
  }

  function drawRows(T) {
    const idx = hgSubset(T, st.env);
    const all = T.hedges.flatMap((x) => x.rets.filter(fin).map(Math.abs)).sort((a, b) => a - b);
    const p95 = all.length ? all[Math.floor(all.length * 0.95)] : 20;
    const D = Math.min(40, Math.max(10, Math.ceil(p95 / 5) * 5));     // 同一張卡共用刻度，才能上下比
    axis.replaceChildren(h("span", { class: "a-name" }, "資產"),
      h("span", { class: "a-strip" }, h("span", {}, `−${D}%`), h("span", {}, "0"), h("span", {}, `+${D}%`)),
      h("span", { class: "a-cnt" }, "上漲"), h("span", { class: "a-med" }, "中位"), h("span", { class: "a-pill" }, "判定"));
    // 順序固定用全部跌段的中位數（後端排好的）：換環境時列不跳動，直接看同一列的點怎麼變
    const list = T.hedges.map((x) => ({ x, s: hgStats(x, idx) }));
    const shown = st.all ? list : list.slice(0, HG_ROWS);
    rows.replaceChildren(...shown.map(({ x }) => hedgeRow(T, x, idx, D)));
    more.hidden = list.length <= HG_ROWS;
    more.textContent = st.all ? `只看前 ${HG_ROWS} 項` : `顯示全部 ${list.length} 項（含跟著跌的）`;
    more.onclick = () => { st.all = !st.all; drawRows(T); };
    if (st.env !== "all" && idx.length < 5) rows.prepend(h("p", { class: "sc-banner" }, `${hgEnvName(H, st.env)}開始的跌段只有 ${idx.length} 段——只能當紀錄看，不能當規律。`));
    return list;
  }

  function drawSim(T, list) {
    const usable = list.filter(({ x }) => x.calm_mix);
    if (!usable.some(({ x }) => x.key === st.pick)) st.pick = (usable.find(({ x }) => HG_RANK[x.verdict] <= 1) || usable[0] || {}).x?.key;
    pickSel.replaceChildren(...usable.map(({ x }) => h("option", { value: x.key }, `${hgName(x)}（${x.verdict}）`)));
    pickSel.value = st.pick || "";
    pickSel.onchange = () => set({ pick: pickSel.value });
    const x = T.hedges.find((r) => r.key === st.pick);
    const upd = () => {
      const w = Number(range.value) / 100;
      st.w = Number(range.value);
      store.set("hgW", st.w);
      wLab.textContent = `${range.value}%`;
      if (!x) { stats.replaceChildren(h_empty("沒有可以試算的資產")); return; }
      const idx = hgSubset(T, st.env).filter((i) => fin(x.rets[i]) && fin(T.episodes[i].ret));
      const before = idx.map((i) => T.episodes[i].ret), after = idx.map((i) => (1 - w) * T.episodes[i].ret + w * x.rets[i]);
      const tn = shortName(T.sid);
      const stat = (label, a, b, good, note) => h("div", { class: "hg-stat" },
        h("div", { class: "hg-stat-l" }, label),
        h("div", { class: "hg-stat-v" }, h("span", { class: `was ${dirClass(a)}` }, hgPct(a)), h("span", { class: "muted" }, " → "), h("b", { class: dirClass(b) }, hgPct(b))),
        h("div", { class: "hg-stat-d" }, !fin(a) || !fin(b) || Math.abs(b - a) < 0.05 ? "沒有差別" : good(b - a)),
        note ? h("div", { class: "hg-stat-n muted" }, note) : null);
      const mi = H.mix_w.indexOf(st.w);
      stats.replaceChildren(
        stat(`${hgSp(tn)}跌的時候（中位）`, hgMedian(before), hgMedian(after), (d) => (d > 0 ? `少跌 ${hgPP(d)}` : `多跌 ${hgPP(d)}`),
          `${hgEnvName(H, st.env)}・${idx.length} 段`),
        stat("最慘的一次", before.length ? Math.min(...before) : null, after.length ? Math.min(...after) : null, (d) => (d > 0 ? `少跌 ${hgPP(d)}` : `多跌 ${hgPP(d)}`)),
        stat(`其他時候 ${hgWin(T)}（中位）`, x.calm_mix[0], mi >= 0 ? x.calm_mix[mi] : null, (d) => (d < 0 ? `少賺 ${hgPP(d)}` : `多賺 ${hgPP(d)}`),
          T.L ? "不在下跌段的視窗" : `${x.calm_n} 個月`));
      perEp.replaceChildren(h("summary", {}, "每一段的結果"), h("div", { class: "tbl-wrap" }, h("table", { class: "data" },
        h("thead", {}, h("tr", {}, h("th", {}, "期間"), h("th", { class: "n" }, tn), h("th", { class: "n" }, `換 ${range.value}%：${hgName(x)}`))),
        h("tbody", {}, idx.map((i, k) => h("tr", {}, h("td", { class: "n" }, `${T.episodes[i].m0}→${T.episodes[i].m1}`),
          h("td", { class: "n" }, chg(before[k], 1, "%")), h("td", { class: "n" }, chg(after[k], 1, "%"))))))));
    };
    range.oninput = upd;
    upd();
  }

  function drawMode(T) {
    if (!DL) return;
    const n = (set) => { const x = set.find((y) => y.id === T.id); return x ? x.n : 0; };
    modeBar.replaceChildren(...[["daily", `日線・高點到低點 ${n(DL.targets)} 段`], ["monthly", `月資料・最深的 3 個月 ${n(H.targets)} 段`]]
      .map(([k, label]) => h("button", { class: "chip", type: "button", "aria-pressed": String(st.mode === k), onclick: () => { if (st.mode !== k) set({ mode: k }); } }, label)));
  }

  function draw() {
    const T = cur();
    if (leadEl) leadEl.textContent = hedgeLead(H, T);
    drawMode(T);
    c2.el.querySelector(".card-sub").textContent = `每一列一項資產，每個點是一段下跌裡它的報酬（${T.L ? "日線：從波段高點到低點" : "月資料：那一段最深的 3 個月"}；紅＝漲、綠＝跌，台灣慣例）；`
      + "直線是中位數；右邊是上漲次數。點一列看每一段的細節。";
    drawTiles();
    drawEnv(T);
    const list = drawRows(T);
    c2.el.querySelector("h3").textContent = `跌的時候，誰會漲：${T.label}`;
    drawSim(T, list);
  }
  draw();
});
