/* 分頁：鉅亨每日 */

TABS.daily = (root) => {
  const days = GFD.daily || [];
  root.replaceChildren(tabHead("鉅亨每日：各市場重點",
    "每天從鉅亨網匯入頭條與各市場新聞，以及指數、匯率、龍頭股收盤；鉅亨沒有提供的期貨、VIX、公債殖利率改用 Yahoo Finance 與日本財務省，逐列標註來源。「重點」由規則自動標註，不是人工編輯。", false));
  if (!days.length) {
    root.append(h("p", { class: "empty" }, "還沒有每日資料。在專案資料夾執行：python3 gfd.py daily"));
    return;
  }
  const secLabel = Object.fromEntries(GFD.sections.map((s) => [s.id, s.label]));
  let dayIdx = 0;
  let sec = store.get("dailySec", "all");
  let onlyHl = store.get("dailyHl", true);
  let query = "";

  const bar = h("div", { class: "daily-bar" });
  const tiles = h("div", { class: "sec-tiles", style: "margin:14px 0 16px" });
  const g = h("div", { class: "grid" });
  root.append(bar, tiles, g);

  const select = h("select", { id: "daily-date", "aria-label": "選擇日期" },
    days.map((d, i) => h("option", { value: String(i) }, `${d.date}（重點 ${d.news.filter((n) => n.highlight).length} 則）`)));
  select.addEventListener("change", () => { dayIdx = Number(select.value); renderDay(); });
  const meta = h("span", { class: "muted", style: "font-size:12.5px" });
  bar.append(h("label", { for: "daily-date", class: "muted", style: "font-size:12.5px" }, "日期"), select, meta);

  function quoteRow(q) {
    const isBp = q.unit === "bp";
    return h("div", { class: `qrow${q.flag ? " flagged" : ""}` },
      h("div", { class: "q-name", title: `${q.symbol}・${q.source}・${q.asof}` }, q.name,
        q.flag ? h("span", { class: "zflag", title: "當日變動相對近 60 個交易日的標準差" }, `${Math.abs(q.z).toFixed(1)}σ`) : null,
        q.note ? h("span", { class: "qnote", title: "漲跌以證交所除權息後的開盤競價基準計算" }, q.note) : null,
        h("small", {}, `${q.source === "鉅亨網" ? "" : q.source + " "}${q.asof.slice(5)}${q.stale ? " 休市" : ""}`)),
      h("span", { class: "n" }, isBp ? q.close.toFixed(3) + "%" : fmtNum(q.close)),
      h("span", { class: `n ${dirClass(q.chg)}` }, `${arrow(q.chg)}${fmtSigned(q.chg, isBp ? 1 : 2, isBp ? "bp" : "%")}`),
      sparkline(q.spark, { w: 64, h: 20, color: q.chg >= 0 ? "var(--up)" : "var(--down)" }));
  }

  function newsItem(n) {
    return h("li", { class: n.highlight ? "hl" : null },
      h("span", { class: "n-time" }, n.time),
      h("div", {},
        h("a", { class: "n-title", href: n.url, target: "_blank", rel: "noopener" }, n.title),
        n.highlight ? h("div", { class: "n-meta" }, h("span", { class: "hl-mark" }, "★ 重點"), n.reasons.map((r) => h("span", { class: "tag" }, r))) : null,
        n.summary ? h("p", { class: "n-sum" }, n.summary) : null,
        h("div", { class: "n-meta" },
          Object.keys(n.sections).map((s) => h("span", { class: "tag sec" }, secLabel[s] || s)),
          n.cats.map((c) => h("span", { class: "tag" }, c)),
          n.stocks.slice(0, 4).map((s) => h("span", { class: "tag" }, s)))));
  }

  function renderDay() {
    const D = days[dayIdx];
    meta.textContent = `匯入時間 ${D.generated_at.replace("T", " ").slice(0, 16)}・重點門檻 分數 ≥ ${D.rules.highlight_score}・異常波動 |z| ≥ ${D.rules.mover_z}`;

    tiles.replaceChildren(
      h("button", { class: "sec-tile", type: "button", "aria-pressed": String(sec === "all"), onclick: () => { sec = "all"; store.set("dailySec", sec); renderDay(); } },
        h("div", { class: "st-name" }, "全部"),
        h("div", { class: "st-num" }, `新聞 ${D.news.length}・重點 ${D.news.filter((n) => n.highlight).length}`),
        h("div", { class: "st-mv" }, `異常波動 ${D.quotes.filter((q) => q.flag).length} 檔`)),
      ...GFD.sections.map((s) => {
        const S = D.sections[s.id] || { news: 0, highlights: 0, movers: [] };
        return h("button", { class: "sec-tile", type: "button", "aria-pressed": String(sec === s.id), onclick: () => { sec = s.id; store.set("dailySec", sec); renderDay(); } },
          h("div", { class: "st-name" }, s.label),
          h("div", { class: "st-num" }, `新聞 ${S.news}・重點 ${S.highlights}`),
          S.movers.length ? h("div", { class: "st-mv" }, `⚑ ${S.movers.slice(0, 2).join("、")}${S.movers.length > 2 ? "…" : ""}`) : h("div", { class: "st-mv muted" }, "無異常波動"));
      }));

    const inSec = (n) => sec === "all" || n.sections[sec];
    const quotes = D.quotes.filter((q) => sec === "all" || q.section === sec || (sec === "flow" && q.section === "fx"));
    const hlNews = D.news.filter((n) => n.highlight && inSec(n));
    const movers = quotes.filter((q) => q.flag);
    g.replaceChildren();

    const sc = card({ title: `${D.date} ${sec === "all" ? "" : secLabel[sec] + " "}重點摘要`, span: 12,
      sub: "依規則分數排序：標題命中觀察關鍵字、鉅亨頭條、提及龍頭股、對應當日異常波動的標的會加分。" });
    sc.body.append(
      movers.length
        ? h("div", { class: "chips", style: "margin-bottom:10px" }, h("span", { class: "lab" }, "異常波動"),
          movers.map((q) => h("span", { class: `pill ${q.chg >= 0 ? "pill-up" : "pill-down"}` }, `${q.name} ${fmtSigned(q.chg, q.unit === "bp" ? 1 : 2, q.unit === "bp" ? "bp" : "%")}・${Math.abs(q.z).toFixed(1)}σ`)))
        : h("p", { class: "muted", style: "margin:0 0 8px" }, "今天這個分類沒有超過 2 倍標準差的價格變動。"),
      hlNews.length
        ? h("ol", { class: "finds" }, hlNews.slice(0, 8).map((n) => h("li", { class: "t-alert" },
          h("b", {}, h("a", { href: n.url, target: "_blank", rel: "noopener", style: "text-decoration:none" }, n.title)),
          h("span", {}, `${n.time}・${Object.keys(n.sections).map((s) => secLabel[s]).join("、")}・${n.reasons.join("；")}`))))
        : h("p", { class: "empty" }, "這個分類今天沒有達到門檻的新聞。"));
    g.append(sc.el);

    const qc = card({ title: "收盤與異常波動", span: 5, sub: "數值為當地最後收盤；σ＝當日變動相對近 60 個交易日標準差的倍數。" });
    const groups = new Map();
    for (const q of quotes) {
      const key = `${secLabel[q.section]}・${q.group}`;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(q);
    }
    if (!quotes.length) qc.body.append(h("p", { class: "empty" }, "這個分類沒有對應的報價。"));
    for (const [name, rows] of groups) qc.body.append(h("div", { class: "qgroup" }, h("h4", {}, name), rows.map(quoteRow)));
    if (D.errors && D.errors.length) qc.body.append(h("p", { class: "note" }, `匯入時有 ${D.errors.length} 個錯誤：${D.errors.slice(0, 3).join("；")}`));
    g.append(qc.el);

    const nc = card({ title: "新聞", span: 7, sub: "來源：鉅亨網；點標題開啟原文。" });
    const search = h("input", { type: "search", id: "news-q", placeholder: "搜尋標題、摘要、關鍵字", value: query, "aria-label": "搜尋新聞" });
    const hlBox = h("input", { type: "checkbox", id: "news-hl" });
    hlBox.checked = onlyHl;
    const list = h("ul", { class: "news" });
    const count = h("span", { class: "muted", style: "font-size:12.5px" });
    const drawList = () => {
      const ql = query.trim().toLowerCase();
      const items = D.news.filter((n) => inSec(n) && (!onlyHl || n.highlight)
        && (!ql || `${n.title} ${n.summary} ${n.keywords.join(" ")} ${n.stocks.join(" ")}`.toLowerCase().includes(ql)));
      count.textContent = `${items.length} 則`;
      list.replaceChildren(...(items.length ? items.slice(0, 150).map(newsItem) : [h("li", {}, h("span"), h("p", { class: "empty" }, "沒有符合條件的新聞"))]));
    };
    search.addEventListener("input", () => { query = search.value; drawList(); });
    hlBox.addEventListener("change", () => { onlyHl = hlBox.checked; store.set("dailyHl", onlyHl); drawList(); });
    nc.body.append(h("div", { class: "news-tools" }, search, h("label", { for: "news-hl" }, hlBox, "只看重點"), count), list);
    drawList();
    g.append(nc.el);
  }

  renderDay();
};
