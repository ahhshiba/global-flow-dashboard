/* 分頁「FAQ」：兩塊、兩種顏色，沒有說明文字、沒有查詢列（2026-10-07）。
   第一塊＝老師的提問加答案（gfd/faq.py，主色底）；第二塊＝原有的名詞解釋（gfd/glossary.py，青綠底）。build 時內嵌。 */

function glossaryGo(link) {
  const [tab, event] = link.split(":");
  if (event) {
    window.gotoTab("cascade", () => {
      // 記憶體直接交給事件衝擊檢視；localStorage 在沙箱 iframe 可能被封鎖，只當作「下次打開」的記憶
      window.csPending = { mode: "event", cat: "all", sel: event };
      store.set("csMode", "event");
      store.set("csCat", "all");
      store.set("csSel", event);
    });
  } else {
    // 連到沙盤推演本身（例：走步回測、校準斜率）要打開推演總結，不是上次停留的檢視
    window.gotoTab(tab, tab === "scenario" ? () => { window.scView = "summary"; } : null);
  }
}

function glossaryLinkLabel(link, events) {
  const [tab, event] = link.split(":");
  if (event) return `事件衝擊：${events[event] || event}`;
  const btn = document.getElementById("t-" + tab);
  if (btn) return btn.textContent.trim();
  if (tab === "research") return "總覽・關聯熱圖";
  return isScView(tab) ? `沙盤推演・${SC_VIEW_LABEL[tab]}` : tab;
}

TABS.glossary = (outer) => {
  const G = GFD.glossary, F = GFD.faq;
  const pendingTerm = window.glPending; window.glPending = null;
  outer.replaceChildren(tabHead("FAQ", "", false));
  if (!G || !G.entries.length) { outer.append(h("p", { class: "empty" }, "沒有名詞資料")); return; }
  const items = F ? F.items : [];
  const byId = Object.fromEntries(G.entries.map((e) => [e.id, e]));

  // 點「相關名詞」或題目裡的名詞連結：捲到那一條並閃一下
  const jump = (id) => {
    const el = document.getElementById("gl-" + id);
    if (!el) return;
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    el.classList.remove("gl-flash"); void el.offsetWidth; el.classList.add("gl-flash");
  };

  const entryCard = (e) => h("article", { class: "card span-6 gl-entry gl-term", id: "gl-" + e.id },
    h("div", { class: "gl-title" }, h("h3", {}, e.term), h("span", { class: "gl-en" }, e.en)),
    h("p", { class: "gl-short" }, e.short),
    h("p", { class: "gl-read" }, e.read),
    e.links.length ? h("div", { class: "gl-row" }, h("span", { class: "gl-lab" }, "本站哪裡看"),
      ...e.links.map((l) => h("button", { class: "chip gl-link", type: "button", onclick: () => glossaryGo(l) }, glossaryLinkLabel(l, G.events) + " →"))) : null,
    e.related.length ? h("div", { class: "gl-row" }, h("span", { class: "gl-lab" }, "相關"),
      ...e.related.filter((r) => byId[r]).map((r) => h("button", { class: "gl-rel", type: "button", onclick: () => jump(r) }, byId[r].term))) : null);

  if (items.length) outer.append(h("div", { class: "grid gl-block" }, items.map((i) => faqCard(i, jump))));
  outer.append(h("div", { class: "grid gl-block" }, G.entries.map(entryCard)));
  if (pendingTerm) setTimeout(() => jump(pendingTerm), 0);
};
