/* 分頁：總覽、匯市、債市、股市、商品 */
const TABS = {};

function statsTable(ids, title, sub) {
  const c = card({ title: title || "統計摘要", sub: sub || "截至各序列最新月份；殖利率的變動以 bp 表示，位階＝目前水準在 1995 年以來的百分位。", span: 12 });
  const rows = ids.filter(has).map((sid) => {
    const s = A.series[sid], st = s.stats, y = s.kind === "yield";
    const pc = (v) => (y ? chg(v, 0, "bp") : chg(v, 1, "%"));
    return h("tr", {},
      h("td", {}, s.name, h("span", { class: "sub" }, s.note)),
      h("td", { class: "n" }, y ? fmtNum(st.value, 2) + "%" : fmtNum(st.value), h("span", { class: "sub" }, st.last)),
      h("td", { class: "n" }, pc(st.c1)), h("td", { class: "n" }, pc(st.c3)), h("td", { class: "n" }, pc(st.c12)), h("td", { class: "n" }, pc(st.c60)),
      h("td", { class: "n" }, s.kind === "price" && fin(st.cagr) ? fmtSigned(st.cagr, 1, "%") : "—"),
      h("td", { class: "n" }, fin(st.mdd) ? `${st.mdd.toFixed(1)}%` : "—", st.mdd_at ? h("span", { class: "sub" }, st.mdd_at) : null),
      h("td", { class: "n" }, fin(st.pct) ? st.pct.toFixed(0) + "%" : "—"),
      h("td", { class: "n" }, `${fmtNum(st.min, y ? 2 : undefined)} – ${fmtNum(st.max, y ? 2 : undefined)}`, h("span", { class: "sub" }, `${st.min_at}／${st.max_at}`)));
  });
  const head = ["標的", "最新", "1 個月", "3 個月", "12 個月", "5 年", "年化報酬", "最大回撤", "30 年位階", "區間低 – 高"];
  c.body.append(h("div", { class: "tbl-wrap" }, h("table", { class: "data" },
    h("thead", {}, h("tr", {}, head.map((t, i) => h("th", { class: i ? "n" : null }, t)))), h("tbody", {}, rows))));
  return c.el;
}

/* 非月份 X 軸（年度、TIC 月份）的圖表卡 */
function xCard(o) {
  const c = card({ title: o.title, sub: o.sub, span: o.span, note: o.note });
  const host = h("div", { class: "chart" });
  const tbl = h("div", { class: "tbl-wrap" });
  tbl.hidden = true;
  let table = false;
  const series = o.series.filter((s) => s.values.some(fin));
  const lg = series.length > 1 ? legend(series, o.key, () => draw()) : null;
  c.tools.append(toolButton("表格", false, (v) => { table = v; host.hidden = v; tbl.hidden = !v; draw(); }));
  function startIdx() {
    if (!o.rangeAware || state.range === "all") return 0;
    const yr = new Date().getFullYear() - Number(state.range);
    const i = o.xs.findIndex((x) => x >= yr);
    return i < 0 ? 0 : i;
  }
  function draw() {
    const vis = series.filter((s) => !(lg && lg.hid.has(s.key)));
    const i0 = startIdx();
    if (table) {
      const rows = [];
      for (let i = o.labels.length - 1; i >= i0; i--) {
        rows.push(h("tr", {}, h("td", { class: "n" }, o.labels[i]), vis.map((s) => h("td", { class: "n" }, s.fmt ? s.fmt(s.values[i]) : fmtNum(s.values[i])))));
      }
      tbl.replaceChildren(h("table", { class: "data" },
        h("thead", {}, h("tr", {}, h("th", {}, o.xName || "期間"), vis.map((s) => h("th", { class: "n" }, s.name)))), h("tbody", {}, rows)));
      return;
    }
    lineChart(host, { series, hidden: lg ? lg.hid : null, xs: o.xs, labels: o.labels, start: i0, height: o.height || 240,
      yFmt: o.yFmt, label: o.title, refs: o.refs, direct: o.direct });
  }
  if (lg) c.body.append(lg.el);
  c.body.append(host, tbl);
  mount(host, draw);
  return c.el;
}

function findingsCard(tab, title) {
  const list = findingsList(tab);
  if (!list) return null;
  const c = card({ title: title || "本頁重點", span: 12, sub: "由資料自動產生的敘述，每次重算分析時更新。" });
  c.body.append(list);
  return c.el;
}

/* ── 總覽 ── */
TABS.overview = (root, redo) => {
  root.replaceChildren(tabHead("跨資產相對強弱與風險偏好",
    "六個市場訊號合成風險偏好代理指數，搭配近期價格變動排行。持有量、經常帳與公司現金流在「現金流」分頁各依原始口徑呈現。", true, redo));
  const g = h("div", { class: "grid" });
  root.append(g);
  const C = A.composite;

  if (C) {
    const tone = C.latest > 0.5 ? "up" : C.latest < -0.5 ? "down" : "neutral";
    const gc = card({ title: "風險偏好代理指數", span: 5, sub: "六個市場訊號對過去 60 個月做 z 分數後，取當月可用訊號平均（至少四項）；正值表示風險偏好代理訊號偏強。", note: "描述性代理指標；不是實際資金流量，也未完成樣本外交易驗證。" });
    gc.body.append(
      h("div", { class: "gauge" },
        h("span", { class: `g-val ${tone === "neutral" ? "" : tone}` }, fmtSigned(C.latest, 2)),
        h("span", { class: `pill pill-${tone}` }, C.state),
        h("span", { class: "g-meta" }, `截至 ${C.latest_at}・1995 年以來第 ${fmtNum(C.percentile, 0)} 百分位`)),
      h("h4", { class: "sub-h" }, "組成訊號（z 分數，已調整方向）"),
      divBars(C.components.map((x) => ({ label: x.name, v: x.latest })), { suffix: "", digits: 2 }),
      h("ul", { class: "gaps", style: "margin-top:12px" }, C.components.map((x) => h("li", {}, h("b", {}, x.name), " ", h("span", {}, `${x.how}：${x.why}；截至 ${x.latest_at || "未提供"}`)))));
    g.append(gc.el);
    g.append(chartCard({
      key: "ov-composite", title: "指數走勢與歷史危機", span: 7, height: 330, area: true,
      sub: "陰影為歷史危機區間；±0.5 為狀態分界。",
      series: [{ key: "composite", name: "風險偏好代理指數", color: "var(--s1)", values: C.values, fmt: (v) => (fin(v) ? fmtSigned(v, 2) : "—") }],
      refs: [{ y: 0.5, label: "風險偏好 +0.5" }, { y: -0.5, label: "避險 −0.5" }], bands: EVENT_BANDS,
    }));
  }

  const fc = card({ title: "跨資產相對強弱", span: 6, sub: "各資產月序列的價格變動百分比排行；基金採還原權息資料。", note: "價格上漲不等於資金淨流入。各列截至月份與採樣口徑可能不同；此排行為歷史描述。" });
  let period = store.get("flowPeriod", "r3");
  const fchips = h("div", { class: "chips" });
  const fbody = h("div");
  const drawFlow = () => {
    fchips.replaceChildren(...[["r1", "1 個月"], ["r3", "3 個月"], ["r12", "12 個月"]].map(([k, l]) =>
      h("button", { class: "chip", type: "button", "aria-pressed": String(k === period), onclick: () => { period = k; store.set("flowPeriod", k); drawFlow(); } }, l)));
    const ranked = (A.flowmap || []).filter((r) => fin(r[period])).sort((a, b) => b[period] - a[period]);
    const rows = ranked.map((r) => ({ label: r.label, v: r[period] }));
    const provenanceRows = ranked.map((r) => h("tr", {},
      h("td", {}, r.label), h("td", {}, r.asof || "未提供"),
      h("td", {}, r.source || (A.series[r.id] || {}).source || "請參閱資料來源",
        h("span", { class: "sub" }, r.basis || (A.series[r.id] || {}).note || "未標示"))));
    const provenanceTable = h("table", { class: "data" },
      h("thead", {}, h("tr", {}, ["資產", "截至月份", "來源／口徑"].map((label) => h("th", {}, label)))),
      h("tbody", {}, provenanceRows));
    const provenance = h("details", {}, h("summary", {}, "查看來源、截至月份與口徑"),
      h("div", { class: "tbl-wrap" }, provenanceTable));
    fbody.replaceChildren(divBars(rows), provenance);
  };
  drawFlow();
  fc.tools.append(fchips);
  fc.body.append(fbody);
  g.append(fc.el);

  if (C) {
    const tc = card({ title: "指數分區之後 3 個月的報酬", span: 6,
      sub: "1995 年以來，指數處於各區間的月份，之後 3 個月對數報酬的中位數；小字為上漲機率與樣本月數。",
      note: "樣本內回顧，不是回測；各月份的未來 3 個月彼此重疊，樣本並不獨立。" });
    const head = h("tr", {}, h("th", {}, "資產"), C.bucket_labels.map((l) => h("th", { class: "n" }, l)));
    const rows = C.forward.map((r) => h("tr", {}, h("td", {}, A.series[r.id] ? A.series[r.id].name : r.id),
      r.buckets.map((b) => h("td", { class: "n" }, b.n ? chg(b.median, 1) : "—", b.n ? h("span", { class: "sub" }, `${fmtNum(b.hit, 0)}%・n=${b.n}`) : null))));
    tc.body.append(h("div", { class: "tbl-wrap" }, h("table", { class: "data" }, h("thead", {}, head), h("tbody", {}, rows))));
    g.append(tc.el);
  }

  g.append(kpiRow([["fx_dxy", "美元指數"], ["fx_usdtwd", "美元/新台幣"], ["b_us10y", "美 10 年殖利率"], ["v_vix", "VIX"],
    ["eq_spx", "S&P 500"], ["eq_twii", "台灣加權"], ["c_gold", "黃金期貨"], ["c_brent", "布蘭特原油"]]));

  const others = (A.findings || []).filter((f) => f.tab !== "overview");
  const oc = card({ title: "各市場重點", span: 7, sub: "來自各分頁的自動敘述。" });
  const own = findingsList("overview");
  if (own) oc.body.append(own);
  if (others.length) {
    const tabName = { fx: "匯市", bond: "債市", equity: "股市", commodity: "商品", flow: "現金流", vol: "VIX", cascade: "事件衝擊", chains: "傳導鏈", playbook: "訊號劇本", research: "30 年關聯" };
    oc.body.append(h("ul", { class: "finds", style: "margin-top:12px" }, others.map((f) => h("li", { class: `t-${f.tone}` },
      h("b", {}, `【${tabName[f.tab] || f.tab}】${f.title}`), h("span", {}, f.text)))));
  }
  g.append(oc.el);

  const gap = card({ title: "資料來源與缺口", span: 5, sub: "手寫清單裡有些項目沒有免費的長歷史來源，這裡列出替代做法。" });
  gap.body.append(h("ul", { class: "gaps" }, (A.gaps || []).map((x) => h("li", {}, h("b", {}, x.item), h("br"), h("span", {}, `${x.reason}。替代：${x.proxy}。`)))));
  const bad = (A.coverage || []).filter((c) => c.status !== "ok");
  if (bad.length) gap.body.append(h("p", { class: "note" }, `本次更新有 ${bad.length} 項抓取失敗或沿用舊資料：${bad.map((b) => b.name).join("、")}`));
  g.append(gap.el);
};

/* ── 匯市 ── */
TABS.fx = (root, redo) => {
  root.replaceChildren(tabHead("匯市：美元、人民幣、日圓、新台幣、歐元",
    "以「美元/該貨幣」報價時，線往上代表該貨幣貶值；歐元/美元相反。匯率不是資金流量。30 年匯率取自台灣央行月均值，美元指數為月底值。", true, redo));
  const g = h("div", { class: "grid" });
  root.append(g);
  const f = findingsCard("fx");
  if (f) g.append(f);
  g.append(kpiRow([["fx_dxy", "美元指數"], ["fx_usdtwd", "美元/新台幣"], ["fx_usdjpy", "美元/日圓"], ["fx_usdcny", "美元/人民幣"], ["fx_eurusd", "歐元/美元"]]));
  g.append(chartCard({
    key: "fx-index", title: "主要匯率（期間起點＝100）", span: 12, mode: "index", height: 300, bands: EVENT_BANDS,
    series: [ser("fx_dxy", 1), ser("fx_usdtwd", 2), ser("fx_usdjpy", 3), ser("fx_usdcny", 4), ser("fx_eurusd", 5)],
    note: "歐元 1999 年才誕生，全期檢視時以它自己的第一筆為 100。",
  }));
  const R = A.reserves;
  if (R) {
    const fmtB = (v) => (fin(v) ? fmtNum(v, 0) + " B" : "—");
    const series = R.countries.map((c, i) => ({ key: c.code, name: c.name, color: `var(--s${i + 1})`, values: c.values, fmt: fmtB }));
    series.push({ key: "TWN", name: "台灣", color: "var(--s6)", values: R.tw_annual, fmt: fmtB });
    g.append(xCard({ key: "fx-reserves", title: "各國外匯存底（十億美元）", span: 7, xs: R.years, labels: R.years.map(String), rangeAware: true, series, xName: "年度",
      sub: "年底值。", note: "中、日、美、歐元區、香港：世界銀行（含黃金）；台灣：中央銀行（不含黃金）。口徑不同，請比較趨勢而非絕對值。" }));
    const tw = R.tw_latest;
    g.append(chartCard({
      key: "fx-tw-reserves", title: "台灣外匯存底（月資料）", span: 5, height: 240, area: true,
      sub: tw ? `${tw.month}：${fmtNum(tw.value, 1)} 十億美元，較一年前 ${fmtSigned(tw.c12, 1)}` : "",
      series: [{ key: "twres", name: "台灣外匯存底", color: "var(--s6)", values: R.tw_monthly, fmt: (v) => (fin(v) ? fmtNum(v, 1) + " B" : "—") }],
    }));
  }
  for (const p of (A.pairs || []).filter((x) => [x.a, x.b].some((s) => s.startsWith("fx_")))) g.append(pairCard(p, 6));
  g.append(statsTable(["fx_dxy", "fx_usdtwd", "fx_usdjpy", "fx_usdcny", "fx_eurusd"]));
};

/* ── 債市 ── */
TABS.bond = (root, redo) => {
  root.replaceChildren(tabHead("債市：美國、日本、台灣利率與公司債",
    "殖利率畫原始水準；公司債與長債基金以還原息總報酬指數化。前 10 大公司債與台灣 10 年公債沒有免費長歷史，改用基金與政策利率代理（見總覽的資料缺口）。", true, redo));
  const g = h("div", { class: "grid" });
  root.append(g);
  const f = findingsCard("bond");
  if (f) g.append(f);
  g.append(kpiRow([["b_us3m", "美 3 個月"], ["b_us10y", "美 10 年"], ["b_us30y", "美 30 年"], ["b_jp10y", "日 10 年"], ["b_tw_disc", "台灣重貼現率"], ["d_curve", "美 10Y−3M 利差"]]));
  g.append(chartCard({
    key: "bond-yields", title: "殖利率與政策利率（%）", span: 12, height: 300, bands: EVENT_BANDS,
    series: [ser("b_us3m", 1), ser("b_us10y", 2), ser("b_us30y", 3), ser("b_jp10y", 4), ser("b_tw_disc", 5)],
    yFmt: (v) => `${+v.toFixed(2)}%`,
  }));
  g.append(chartCard({
    key: "bond-curve", title: "美債殖利率曲線：10 年 − 3 個月", span: 6, height: 240, area: true, bands: EVENT_BANDS,
    series: [ser("d_curve", 1, { fmt: (v) => (fin(v) ? fmtSigned(v, 2) + " 個百分點" : "—") })],
    refs: [{ y: 0, label: "倒掛線" }], yFmt: (v) => `${+v.toFixed(1)}`,
    note: "跌破 0＝曲線倒掛；1995 年以來數次都領先美國衰退，但領先時間長短不一。",
  }));
  g.append(chartCard({
    key: "bond-credit", title: "公債與公司債（總報酬，期間起點＝100）", span: 6, height: 240, mode: "index", logToggle: true,
    series: [ser("b_ust_long", 1), ser("b_ig", 2), ser("b_hy", 3), ser("b_lqd", 4), ser("b_hyg", 5)],
    note: "LQD 2002 年、HYG 2007 年才上市，以各自第一筆為 100。",
  }));
  g.append(chartCard({
    key: "bond-brk", title: "波克夏 vs S&P 500（期間起點＝100）", span: 6, height: 260, mode: "index", log: true, logToggle: true, bands: EVENT_BANDS,
    series: [ser("b_brk", 1), ser("eq_spx", 2)],
    sub: "波克夏握有大量美國短期國庫券；利率高時現金部位收益高，但與大盤的連動會下降。",
  }));
  const brk = (A.pairs || []).find((p) => p.a === "b_brk");
  if (brk) g.append(pairCard(brk, 6));
  for (const p of (A.pairs || []).filter((x) => (x.a.startsWith("b_") || x.b.startsWith("b_")) && x.a !== "b_brk" && x.a !== "v_vix")) g.append(pairCard(p, 6));
  g.append(statsTable(["b_us3m", "b_us5y", "b_us10y", "b_us30y", "b_jp10y", "b_tw_disc", "d_curve", "b_ust_long", "b_ig", "b_hy", "b_lqd", "b_hyg", "b_brk"]));
};

/* ── 股市 ── */
function leadersCard() {
  const c = card({ title: "龍頭股觀察", span: 12,
    sub: "最新收盤與日漲跌取自鉅亨每日（台股除權息日以證交所基準價計算）；1 個月以後的報酬為還原權息月資料；β 與相關係數以近 60 個月對所屬指數計算。點公司名稱就能在上方圖表比較個股與指數。",
    note: "名單為大型權值股，不是即時市值排名；要換股請改 gfd/config.py 的 LEADERS。" });
  let mkt = store.get("leadersMkt", "tw");
  let sel = null;
  const chips = h("div", { class: "chips" });
  const host = h("div", { class: "chart" });
  const tblWrap = h("div", { class: "tbl-wrap", style: "margin-top:12px" });
  const valid = (L, id) => L.items.some((x) => x.id === id && !x.missing);
  function build() {
    const L = A.leaders[mkt];
    if (!valid(L, sel)) sel = store.get("leadersSel:" + mkt, null);
    if (!valid(L, sel)) sel = (L.items.find((x) => !x.missing) || {}).id;
    chips.replaceChildren(...["tw", "us", "hk"].map((k) => h("button", { class: "chip", type: "button", "aria-pressed": String(k === mkt),
      onclick: () => { mkt = k; store.set("leadersMkt", k); sel = null; build(); draw(); } }, A.leaders[k].title)));
    const head = ["公司", "最新收盤", "日漲跌", "1 個月", "12 個月", "5 年", "年化報酬", "最大回撤", "β", "相關", "近 3 年走勢"];
    const rows = L.items.map((it) => {
      if (it.missing) return h("tr", {}, h("td", {}, it.name, h("span", { class: "sub" }, it.ticker)), h("td", { class: "n muted", colspan: 10 }, "無資料"));
      const st = it.stats;
      const q = LATEST_QUOTES[it.cnyes];
      const btn = h("button", { class: "rowbtn", type: "button", "aria-pressed": String(it.id === sel) }, it.name);
      btn.addEventListener("click", () => { sel = it.id; store.set("leadersSel:" + mkt, sel); build(); draw(); });
      return h("tr", { class: it.id === sel ? "sel" : null },
        h("td", {}, btn, h("span", { class: "sub" }, `${it.ticker}・${st.first} 起`)),
        q ? h("td", { class: "n" }, fmtNum(q.close), h("span", { class: "sub" }, `${q.asof.slice(5)}${q.note ? "・" + q.note : ""}`))
          : h("td", { class: "n" }, fmtNum(st.value), h("span", { class: "sub" }, `${st.last} 月資料`)),
        h("td", { class: "n" }, q ? chg(q.chg, 2) : "—"),
        h("td", { class: "n" }, chg(st.c1)), h("td", { class: "n" }, chg(st.c12)), h("td", { class: "n" }, chg(st.c60)),
        h("td", { class: "n" }, fin(st.cagr) ? fmtSigned(st.cagr, 1, "%") : "—"),
        h("td", { class: "n" }, fin(st.mdd) ? `${st.mdd.toFixed(0)}%` : "—"),
        h("td", { class: "n" }, fmtNum(it.beta, 2)), h("td", { class: "n" }, fmtNum(it.corr, 2)),
        h("td", {}, sparkline(it.values.slice(-37), { w: 110, h: 24, color: "var(--s1)" })));
    });
    tblWrap.replaceChildren(h("table", { class: "data" }, h("thead", {}, h("tr", {}, head.map((t, i) => h("th", { class: i ? "n" : null }, t)))), h("tbody", {}, rows)));
  }
  const pairSeries = () => {
    const L = A.leaders[mkt];
    const it = L.items.find((x) => x.id === sel);
    return it ? [{ key: it.id, name: it.name, color: "var(--s1)", values: it.values, fmt: (v) => fmtNum(v) }, ser(L.index, 2)] : [];
  };
  const eng = singleEngine("leaders", () => pairSeries().filter((s) => instrument(s.key)), () => draw());
  let single = store.get("single:leaders", false);
  let pickedFor = null;
  function draw() {
    eng.ctl.hidden = !single;
    const L = A.leaders[mkt];
    const it = L.items.find((x) => x.id === sel);
    if (!it) { host.replaceChildren(h("p", { class: "empty" }, "沒有可比較的個股")); return; }
    if (single) {
      if (pickedFor !== sel) { eng.setPick(sel); pickedFor = sel; }  // 點了新的一列 → 線圖跟著換成那檔
      eng.render(host, h("div"), false, false);
      return;
    }
    const first = it.values.findIndex(fin);
    lineChart(host, { series: pairSeries(), mode: "index", log: true, start: Math.max(rangeStart(), first), height: 260, bands: EVENT_BANDS, label: `${it.name} 與指數` });
  }
  build();
  c.tools.append(chips, toolButton("單一標的", single, (v) => { single = v; store.set("single:leaders", v); draw(); }));
  c.body.append(eng.ctl, host, tblWrap);
  mount(host, draw);
  return c.el;
}

TABS.equity = (root, redo) => {
  root.replaceChildren(tabHead("股市：美國、香港、台灣",
    "指數為價格指數（不含息）；台灣加權 1997-07 以前以中央銀行月資料接續。日經與上證列為參考，用來觀察亞洲資金輪動。", true, redo));
  const g = h("div", { class: "grid" });
  root.append(g);
  const f = findingsCard("equity");
  if (f) g.append(f);
  g.append(kpiRow([["eq_spx", "S&P 500"], ["eq_ndx", "那斯達克 100"], ["eq_sox", "費城半導體"], ["eq_hsi", "恆生指數"], ["eq_twii", "台灣加權"], ["eq_n225", "日經 225"]]));
  g.append(chartCard({
    key: "eq-index", title: "主要股價指數（期間起點＝100）", span: 12, height: 320, mode: "index", log: true, logToggle: true, bands: EVENT_BANDS,
    series: [ser("eq_spx", 1), ser("eq_ndx", 2), ser("eq_sox", 3), ser("eq_hsi", 4), ser("eq_twii", 5), ser("eq_n225", 6), ser("eq_sse", 7), ser("eq_dji", 8)],
  }));
  g.append(leadersCard());
  for (const p of (A.pairs || []).filter((x) => x.a.startsWith("eq_") && !x.b.startsWith("fx_"))) g.append(pairCard(p, 6));
  g.append(statsTable(["eq_spx", "eq_ndx", "eq_dji", "eq_sox", "eq_hsi", "eq_twii", "eq_n225", "eq_sse"]));
};

/* ── 商品 ── */
TABS.commodity = (root, redo) => {
  root.replaceChildren(tabHead("商品：農產品、金屬、能源",
    "30 年商品價格取自世界銀行 Pink Sheet 月均價（每月初更新上月）；每日變動請看「鉅亨每日」分頁的期貨報價。", true, redo));
  const g = h("div", { class: "grid" });
  root.append(g);
  const f = findingsCard("commodity");
  if (f) g.append(f);
  g.append(kpiRow([["c_gold", "黃金"], ["c_silver", "白銀"], ["c_copper", "銅"], ["c_brent", "布蘭特原油"], ["c_maize", "玉米"], ["c_soy", "大豆"]]));
  const idx = (key, title, ids) => chartCard({ key, title, span: 6, height: 260, mode: "index", log: true, logToggle: true, bands: EVENT_BANDS,
    series: ids.map((id, i) => ser(id, i + 1)) });
  g.append(idx("cm-metal", "貴金屬與工業金屬（起點＝100）", ["c_gold", "c_silver", "c_platinum", "c_copper", "c_alu", "c_iron"]));
  g.append(idx("cm-energy", "能源（起點＝100）", ["c_brent", "c_wti", "c_natgas"]));
  g.append(idx("cm-agri", "農產品（起點＝100）", ["c_maize", "c_soy", "c_wheat"]));
  g.append(idx("cm-wbidx", "世界銀行商品指數（起點＝100）", ["ci_energy", "ci_nonenergy", "ci_agri", "ci_metals", "ci_precious"]));
  g.append(chartCard({ key: "cm-cuau", title: "銅/黃金 比值", span: 6, height: 230, area: true, bands: EVENT_BANDS, series: [ser("d_cu_au", 1, { fmt: (v) => fmtNum(v, 3) })],
    sub: "銅代表景氣實需、黃金代表避險，比值上升＝資金偏向景氣循環。" }));
  g.append(chartCard({ key: "cm-oilau", title: "原油/黃金 比值", span: 6, height: 230, area: true, bands: EVENT_BANDS, series: [ser("d_oil_au", 1, { fmt: (v) => fmtNum(v, 4) })],
    sub: "比值上升＝通膨與景氣動能強於避險需求。" }));
  for (const p of (A.pairs || []).filter((x) => x.a.startsWith("c_"))) g.append(pairCard(p, 6));
  g.append(statsTable(["c_gold", "c_silver", "c_platinum", "c_copper", "c_alu", "c_iron", "c_brent", "c_wti", "c_natgas", "c_maize", "c_soy", "c_wheat",
    "ci_energy", "ci_nonenergy", "ci_agri", "ci_metals", "ci_precious"]));
};
