/* 啟動：分頁切換、報價帶、資料時間戳 */

(function boot() {
  const tabBtns = [...document.querySelectorAll('.tabs [role="tab"]')];
  const ids = tabBtns.map((b) => b.dataset.tab);
  let current = null;

  function render(id) {
    const root = document.getElementById("tab-" + id);
    hideTip();
    const redo = () => { const y = window.scrollY; render(id); window.scrollTo(0, y); };
    try {
      TABS[id](root, redo);
    } catch (err) {
      root.replaceChildren(h("p", { class: "empty" }, `這個分頁繪製失敗：${err.message}`));
      console.error(err);
    }
    root.dataset.range = state.range;
  }

  function show(id) {
    if (!ids.includes(id)) id = "overview";
    current = id;
    for (const b of tabBtns) {
      const on = b.dataset.tab === id;
      b.setAttribute("aria-selected", String(on));
      b.tabIndex = on ? 0 : -1;
    }
    for (const sec of document.querySelectorAll(".tab")) sec.hidden = sec.id !== "tab-" + id;
    const root = document.getElementById("tab-" + id);
    if (root.dataset.range !== state.range || !root.childElementCount) render(id);
    store.set("tab", id);
    if (location.hash.slice(1) !== id) {
      try { history.replaceState(null, "", "#" + id); } catch (e) { /* 沙箱 iframe 可能不允許改網址 */ }
    }
  }

  tabBtns.forEach((b, i) => {
    b.addEventListener("click", () => show(b.dataset.tab));
    b.addEventListener("keydown", (e) => {
      const d = { ArrowRight: 1, ArrowLeft: -1 }[e.key];
      if (!d) return;
      e.preventDefault();
      const next = tabBtns[(i + d + tabBtns.length) % tabBtns.length];
      next.focus();
      show(next.dataset.tab);
    });
  });
  window.addEventListener("hashchange", () => { const id = location.hash.slice(1); if (id && id !== current) show(id); });

  // 報頭時間戳
  const latest = (GFD.daily || [])[0];
  const stamp = (dt, dd) => [h("dt", {}, dt), h("dd", {}, dd)];
  document.getElementById("span-range").textContent = `${MONTHS[0]} → ${A.complete_end}`;
  document.getElementById("stamps").append(
    ...stamp("歷史資料", (A.fetched_at || "—").replace("T", " ").slice(0, 16)),
    ...stamp("鉅亨每日", latest ? latest.date : "尚未匯入"),
    ...stamp("頁面產出", GFD.built_at.replace("T", " ").slice(0, 16)));

  // 報價跑馬燈：最新一天的全部非個股報價＋台積電；內容複製一份接在後面做無縫循環
  const tape = document.getElementById("tape");
  if (latest) {
    const quotes = latest.quotes.filter((q) => !/^(美股|台股|港股)龍頭$/.test(q.group) || q.symbol === "TWS:2330:STOCK");
    const item = (q) => {
      const isBp = q.unit === "bp";
      return h("span", { class: "tape-item" },
        h("span", { class: "t-name" }, q.name),
        h("span", { class: "t-val" }, isBp ? q.close.toFixed(3) + "%" : fmtNum(q.close)),
        h("span", { class: dirClass(q.chg) }, `${arrow(q.chg)}${fmtSigned(q.chg, isBp ? 1 : 2, isBp ? "bp" : "%")}`),
        q.flag ? h("span", { class: "t-flag" }, `${Math.abs(q.z).toFixed(1)}σ`) : null);
    };
    const seq = () => h("div", { class: "tape-seq" }, quotes.map(item));
    const clone = seq();
    clone.setAttribute("aria-hidden", "true");
    const track = h("div", { class: "tape-track" }, seq(), clone);
    let paused = store.get("tapePaused", false);
    const btn = h("button", { class: "tape-btn", type: "button" });
    const setPaused = (p) => {
      paused = p;
      tape.classList.toggle("is-paused", p);
      btn.textContent = p ? "▶ 播放" : "❚❚ 暫停";
      btn.setAttribute("aria-label", p ? "播放報價跑馬燈" : "暫停報價跑馬燈");
      store.set("tapePaused", p);
    };
    btn.addEventListener("click", () => setPaused(!paused));
    tape.append(h("span", { class: "tape-date" }, `${latest.date} 收盤`), h("div", { class: "tape-view" }, track), btn);
    setPaused(paused);
    requestAnimationFrame(() => {
      const w = track.firstChild.getBoundingClientRect().width;
      tape.style.setProperty("--tape-dur", `${Math.max(30, Math.round(w / 55))}s`);  // 約每秒 55px
    });
    if (latest.news.some((n) => n.highlight)) document.getElementById("daily-dot").hidden = false;
  } else {
    tape.hidden = true;
  }

  document.getElementById("foot").append(
    GFD.public ? h("span", {}, "公開示範版：新聞只列標題與原文連結（摘要請看鉅亨網原文）；資料每天自動更新。") : null,
    h("span", {}, "資料來源：Yahoo Finance、台灣中央銀行、世界銀行（API 與 Pink Sheet）、日本財務省、美國財政部 TIC、SEC EDGAR、FinMind、鉅亨網。"),
    h("span", {}, "紅漲綠跌為台灣行情慣例。所有統計皆為歷史樣本內描述，僅供研究參考，不構成投資建議。"),
    h("span", {}, "更新：在專案資料夾執行 python3 gfd.py all（歷史資料超過 7 天才會重抓）。"));

  show(location.hash.slice(1) || store.get("tab", "overview"));
})();
