/* 分頁：現金流、VIX、30 年關聯 */

const SHORT = {
  fx_dxy: "美元指數", fx_usdtwd: "美元/台幣", fx_usdjpy: "美元/日圓", fx_usdcny: "美元/人民幣", fx_eurusd: "歐元/美元",
  b_us3m: "美 3 月殖利率", b_us10y: "美 10 年殖利率", b_jp10y: "日 10 年殖利率", b_ust_long: "美長債基金", b_ig: "投資級債",
  b_hy: "高收益債", b_brk: "波克夏", eq_spx: "S&P 500", eq_ndx: "那斯達克 100", eq_sox: "費城半導體", eq_hsi: "恆生指數",
  eq_twii: "台灣加權", eq_n225: "日經 225", eq_sse: "上證", c_gold: "黃金", c_copper: "銅", c_brent: "布蘭特原油",
  c_maize: "玉米", c_soy: "大豆", ci_agri: "農產品指數", v_vix: "VIX",
};
const shortName = (sid) => SHORT[sid] || (A.series[sid] ? A.series[sid].name : sid);

function pairCard(p, span) {
  const c = card({ title: p.label, sub: p.why, span: span || 6 });
  const strong = (v) => h("b", { class: `mono ${fin(v) ? (v >= 0 ? "up" : "down") : ""}` }, fin(v) ? fmtSigned(v, 2) : "—");
  c.body.append(h("div", { class: "pair-stats" },
    h("span", {}, "1995 年以來 r ", strong(p.r_full)),
    h("span", {}, `近 ${A.corr ? A.corr.window : 36} 個月 r `, strong(p.r_recent)),
    h("span", { class: "muted" }, `n = ${p.n_full}`),
    p.lead ? h("span", { class: "pill pill-warn" }, `領先 ${Math.abs(p.lead.k)} 個月`) : null));
  const host = h("div", { class: "chart" });
  const lagHost = h("div", { class: "chart" });
  c.body.append(h("h4", { class: "sub-h" }, "36 個月滾動相關"), host,
    h("h4", { class: "sub-h" }, "領先落後相關（k 個月；橘線為 95% 顯著門檻）"), lagHost);
  mount(host, () => lineChart(host, {
    series: [{ key: "r", name: "滾動相關", color: "var(--s1)", values: p.rolling, fmt: (v) => (fin(v) ? fmtSigned(v, 2) : "—") }],
    start: rangeStart(), yDomain: [-1, 1], refs: [{ y: 0 }], bands: EVENT_BANDS, height: 170, direct: false, label: p.label,
  }));
  mount(lagHost, () => lagChart(lagHost, p));
  return c.el;
}

/* ── 現金流 ── */
function cfCard(CF) {
  const c = card({ title: "龍頭企業現金流", span: 12, note: CF.note,
    sub: "點公司名稱就能在上方畫出該公司的營業現金流、資本支出與自由現金流。" });
  let mkt = store.get("cfMkt", "tw");
  let sel = null;
  const chips = h("div", { class: "chips" });
  const host = h("div", { class: "chart" });
  const tblWrap = h("div", { class: "tbl-wrap", style: "margin-top:12px" });
  const dig = () => (mkt === "us" ? 1 : 0);
  function build() {
    const M = CF[mkt];
    if (!sel || !M.items.some((x) => x.ticker === sel)) sel = (M.items[0] || {}).ticker;
    chips.replaceChildren(...[["tw", "台股"], ["us", "美股"]].map(([k, l]) => h("button", { class: "chip", type: "button", "aria-pressed": String(k === mkt),
      onclick: () => { mkt = k; store.set("cfMkt", k); sel = null; build(); draw(); } }, l)));
    const head = ["公司", "最近年度", `營業現金流（${M.unit}）`, "資本支出", "自由現金流", "營業現金流 5 年年化", "營業現金流走勢"];
    const rows = M.items.map((it) => {
      const L = it.latest || {};
      const btn = h("button", { class: "rowbtn", type: "button", "aria-pressed": String(it.ticker === sel) }, it.name);
      btn.addEventListener("click", () => { sel = it.ticker; build(); draw(); });
      return h("tr", { class: it.ticker === sel ? "sel" : null },
        h("td", {}, btn, h("span", { class: "sub" }, it.ticker)),
        h("td", { class: "n" }, L.end || "—"),
        h("td", { class: "n" }, fmtNum(L.ocf, dig())),
        h("td", { class: "n" }, fmtNum(L.capex, dig())),
        h("td", { class: `n ${dirClass(L.fcf)}` }, fmtNum(L.fcf, dig())),
        h("td", { class: "n" }, fin(it.ocf_cagr5) ? fmtSigned(it.ocf_cagr5, 1, "%") : "—"),
        h("td", {}, sparkline(it.years.map((y) => y.ocf), { w: 110, h: 24, color: "var(--s1)" })));
    });
    tblWrap.replaceChildren(h("table", { class: "data" }, h("thead", {}, h("tr", {}, head.map((t, i) => h("th", { class: i ? "n" : null }, t)))), h("tbody", {}, rows)));
  }
  function draw() {
    const M = CF[mkt];
    const it = M.items.find((x) => x.ticker === sel);
    if (!it || !it.years.length) { host.replaceChildren(h("p", { class: "empty" }, "沒有現金流資料")); return; }
    const xs = it.years.map((y) => Number(y.end.slice(0, 4)) + (Number(y.end.slice(5, 7)) - 1) / 12);
    const f = (v) => (fin(v) ? `${fmtNum(v, dig())} ${M.unit}` : "—");
    lineChart(host, { xs, labels: it.years.map((y) => `${y.end.slice(0, 7)} 年度`), start: 0, height: 240, label: `${it.name} 現金流`,
      series: [
        { key: "ocf", name: "營業現金流", color: "var(--s1)", values: it.years.map((y) => y.ocf), fmt: f },
        { key: "capex", name: "資本支出", color: "var(--s2)", values: it.years.map((y) => y.capex), fmt: f },
        { key: "fcf", name: "自由現金流", color: "var(--s3)", values: it.years.map((y) => y.fcf), fmt: f },
      ], refs: [{ y: 0 }] });
  }
  build();
  c.tools.append(chips);
  c.body.append(host, tblWrap);
  mount(host, draw);
  return c.el;
}

TABS.flow = (root, redo) => {
  root.replaceChildren(tabHead("現金流：國家與公司",
    "分開閱讀三種口徑：TIC 是月底美債持有量存量、經常帳是期間收支餘額、公司現金流是財報期間現金收支。它們與價格相對強弱不可互換。", true, redo));
  const g = h("div", { class: "grid" });
  root.append(g);
  const f = findingsCard("flow");
  if (f) g.append(f);
  const T = A.tic;
  if (T) {
    const xs = T.months.map((m) => { const [y, mo] = m.split("-").map(Number); return y + (mo - 1) / 12; });
    const holders = T.holders.filter((x) => x.key !== "grand total");
    g.append(xCard({ key: "flow-tic", title: "主要外國持有美債（十億美元）", span: 7, xs, labels: T.months, rangeAware: true, xName: "月份", height: 280,
      sub: "月底持有量存量及其變化；存量變動可能包含估值等影響，不能直接視為跨境淨買賣流量。", note: `資料：美國財政部 TIC，2000 年起，月底持有量（含官方與民間）；資料期間至 ${T.months[T.months.length - 1] || "未提供"}。`,
      series: holders.map((x, i) => ({ key: x.key, name: x.name, color: `var(--s${i + 1})`, values: x.values, fmt: (v) => (fin(v) ? fmtNum(v, 1) + " B" : "—") })) }));
    const tc = card({ title: "持有量與 12 個月變化", span: 5, sub: `截至 ${T.holders[0].latest_at}（十億美元）` });
    tc.body.append(h("div", { class: "tbl-wrap" }, h("table", { class: "data" },
      h("thead", {}, h("tr", {}, h("th", {}, "國家/地區"), h("th", { class: "n" }, "持有"), h("th", { class: "n" }, "12 個月"), h("th", { class: "n" }, "占外國合計"))),
      h("tbody", {}, T.holders.map((x) => h("tr", {}, h("td", {}, x.name), h("td", { class: "n" }, fmtNum(x.latest, 1)),
        h("td", { class: "n" }, chg(x.c12, 1, "")), h("td", { class: "n" }, fin(x.share) ? x.share.toFixed(1) + "%" : "—")))))));
    const bars = holders.filter((x) => fin(x.c12)).map((x) => ({ label: x.name, v: x.c12 })).sort((a, b) => b.v - a.v);
    tc.body.append(h("h4", { class: "sub-h" }, "12 個月增減"), divBars(bars, { suffix: "", digits: 0 }));
    g.append(tc.el);
  }
  const CA = A.current_account;
  if (CA) {
    g.append(xCard({ key: "flow-ca", title: "經常帳餘額（十億美元）", span: 12, xs: CA.years, labels: CA.years.map(String), rangeAware: true, xName: "年度", height: 260,
      sub: "期間內商品、服務、初次所得與二次所得的收支餘額；不是金融帳或證券投資淨流量。", note: "世界銀行年資料；各國最新非空年份見圖表，缺值不等於零。台灣不在世界銀行資料庫中，見總覽的資料缺口。",
      refs: [{ y: 0 }], series: CA.countries.map((c, i) => ({ key: c.code, name: c.name, color: `var(--s${i + 1})`, values: c.values, fmt: (v) => (fin(v) ? fmtNum(v, 0) + " B" : "—") })) }));
  }
  if (A.company_cf) g.append(cfCard(A.company_cf));
};

/* ── VIX ── */
TABS.vol = (root, redo) => {
  root.replaceChildren(tabHead("VIX：恐慌指數與之後的報酬",
    "VIX 是 S&P 500 選擇權隱含的 30 天波動。這裡把 1995 年以來的月底 VIX 分成四個區間，統計各資產之後 1 個月、3 個月的表現。", true, redo));
  const g = h("div", { class: "grid" });
  root.append(g);
  const V = A.vix;
  const f = findingsCard("vol");
  if (f) g.append(f);
  if (!V) return;
  const tone = V.latest >= 30 ? "warn" : V.latest >= 20 ? "down" : "neutral";
  const gc = card({ title: "目前位置", span: 4, sub: `月底值，截至 ${V.latest_at}` });
  gc.body.append(h("div", { class: "gauge" }, h("span", { class: "g-val" }, fmtNum(V.latest, 1)), h("span", { class: `pill pill-${tone}` }, V.current)),
    h("h4", { class: "sub-h" }, "1995 年以來各區間占比"),
    h("div", { class: "bars" }, V.share.map((s) => h("div", { class: "bar-row" }, h("span", {}, s.label.split(" ")[0]),
      h("div", { class: "bar-track", role: "img", "aria-label": `${s.label} ${s.pct}%` },
        h("div", { class: "bar-fill", style: `left:0;width:${s.pct}%;background:${s.label === V.current ? "var(--accent)" : "var(--line-strong)"}` })),
      h("span", { class: "n" }, `${s.pct}%`)))));
  g.append(gc.el);
  g.append(chartCard({ key: "vol-vix", title: "VIX 月底值", span: 8, height: 280, bands: EVENT_BANDS, area: true,
    series: [ser("v_vix", 1, { fmt: (v) => fmtNum(v, 1) })], refs: [{ y: 15, label: "15" }, { y: 20, label: "20" }, { y: 30, label: "30 恐慌" }] }));
  const tc = card({ title: "VIX 區間 × 之後的報酬", span: 12, sub: "各格為對數報酬中位數；小字為上漲機率與樣本月數。", note: "樣本內統計；月份重疊、恐慌區間樣本少，不能當成交易規則。" });
  let horizon = store.get("vixH", "f3");
  const chips = h("div", { class: "chips" });
  const body = h("div", { class: "tbl-wrap" });
  const draw = () => {
    chips.replaceChildren(...[["f1", "之後 1 個月"], ["f3", "之後 3 個月"]].map(([k, l]) => h("button", { class: "chip", type: "button", "aria-pressed": String(k === horizon),
      onclick: () => { horizon = k; store.set("vixH", k); draw(); } }, l)));
    body.replaceChildren(h("table", { class: "data" },
      h("thead", {}, h("tr", {}, h("th", {}, "資產"), V.bands.map((b) => h("th", { class: "n" }, b)))),
      h("tbody", {}, V.rows.map((r) => h("tr", {}, h("td", {}, shortName(r.id)), r.bands.map((b) => {
        const s = b[horizon];
        return h("td", { class: "n" }, s.n ? chg(s.median, 1) : "—", s.n ? h("span", { class: "sub" }, `${fmtNum(s.hit, 0)}%・n=${s.n}`) : null);
      }))))));
  };
  draw();
  tc.tools.append(chips);
  tc.body.append(body);
  g.append(tc.el);
  for (const p of (A.pairs || []).filter((x) => x.a === "v_vix" || x.b === "v_vix")) g.append(pairCard(p, 12));
};

/* ── 30 年關聯 ── */
TABS.research = (root, redo) => {
  root.replaceChildren(tabHead("30 年關聯研究",
    "月資料：價格類用月對數報酬、殖利率用月變動（bp）、VIX 用對數變動。全期為 1995 年以來，近期為最近 36 個完整月。相關不等於因果；領先落後為樣本內統計。", true, redo));
  const g = h("div", { class: "grid" });
  root.append(g);
  const f = findingsCard("research", "關係變化與領先落後");
  if (f) g.append(f);

  const C = A.corr;
  if (C) {
    let mode = store.get("heatMode", "full");
    const hc = card({ title: "資產關聯熱圖", span: 12, sub: `紅＝同向、藍＝反向；只標出 |r| ≥ 0.5 的數字，其餘移到格子上看。近期區間：${C.recent_start} → ${C.recent_end}。` });
    const chips = h("div", { class: "chips" });
    const host = h("div", { class: "heat-wrap heat" });
    const names = C.ids.map(shortName);
    const draw = () => {
      chips.replaceChildren(...[["full", "1995 年以來"], ["recent", "近 36 個月"]].map(([k, l]) => h("button", { class: "chip", type: "button", "aria-pressed": String(k === mode),
        onclick: () => { mode = k; store.set("heatMode", k); draw(); } }, l)));
      heatmap(host, { ids: C.ids, names, matrix: mode === "full" ? C.full : C.recent, label: "資產關聯熱圖",
        tip: (i, j) => `<div class="tip-h">${esc(names[i])} × ${esc(names[j])}</div>`
          + `<div>1995 年以來 r = <b class="mono">${fin(C.full[i][j]) ? fmtSigned(C.full[i][j], 2) : "—"}</b>（n=${C.full_n[i][j]}）</div>`
          + `<div>近 36 個月 r = <b class="mono">${fin(C.recent[i][j]) ? fmtSigned(C.recent[i][j], 2) : "—"}</b></div>` });
    };
    hc.tools.append(chips);
    hc.body.append(host);
    mount(host, draw);
    g.append(hc.el);
  }

  for (const p of A.pairs || []) g.append(pairCard(p, 6));

  const E = A.events;
  if (E && E.items.length) {
    const ec = card({ title: "歷史危機期間各資產表現", span: 12,
      sub: "區間起點前一個月底到終點月底的變化；價格類為 %、殖利率為 bp、VIX 為點數。紅＝上升、綠＝下跌（台灣行情慣例）。",
      note: "商品與匯率為月均值，短區間（如新冠 2020-02→03）的跌幅會比日線看到的小。" });
    const scale = { "%": 45, bp: 250, pt: 30 };
    const head = h("tr", {}, h("th", {}, "資產"), E.items.map((e) => h("th", { class: "n" }, e.name, h("span", { class: "sub" }, `${e.start}→${e.end}`))));
    const rows = E.ids.map((sid) => h("tr", {}, h("td", {}, shortName(sid)), E.items.map((e) => {
      const m = e.moves[sid];
      if (!m) return h("td", { class: "n muted" }, "—");
      const p = Math.round(Math.min(1, Math.abs(m.v) / scale[m.unit]) * 42);
      const col = m.v >= 0 ? "var(--up)" : "var(--down)";
      return h("td", { class: "n heatcell", style: `background:color-mix(in srgb, ${col} ${p}%, transparent)` },
        `${fmtSigned(m.v, m.unit === "%" ? 1 : 0)}${m.unit === "%" ? "%" : m.unit === "bp" ? "bp" : ""}`);
    })));
    ec.body.append(h("div", { class: "tbl-wrap" }, h("table", { class: "data" }, h("thead", {}, head), h("tbody", {}, rows))));
    g.append(ec.el);
  }
};
