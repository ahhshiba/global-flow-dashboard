/* 分頁：名詞解釋＋課堂提到的題目併成一份清單（名詞在 gfd/glossary.py、題目在 gfd/faq.py，build 時內嵌）。
   有色底的卡片＝課堂提到的（老師的提問，全部都在 FAQ）；沒有色底的是名詞解釋。 */

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
  const faqItems = F ? F.items : [];
  const faqOpen = faqItems.filter((i) => i.status === "open").length;
  // 舊的 #faq 連結（window.glView = "faq"）打開時只看課堂提到的；記憶體優先，用過即清
  let kind = pendingTerm ? "all" : (window.glView === "faq" ? "class" : store.get("glKind", "all"));
  window.glView = null;
  if (!["all", "class", "term"].includes(kind) || (kind === "class" && !faqItems.length)) kind = "all";
  outer.replaceChildren(tabHead("名詞解釋與 FAQ",
    "本站用到的專有名詞（一句話定義、怎麼看、在本站哪裡看），以及老師的提問與交辦。有色底的卡片是課堂提到的，其餘是名詞解釋。"
    + "標「約」的數字是量級，不是精確統計。", false));
  if (!G || !G.entries.length) { outer.append(h("p", { class: "empty" }, "沒有名詞資料")); return; }

  const cats = [...G.cats, ...(F ? F.cats : []).filter((c) => !G.cats.some((g) => g.id === c.id))];
  const catCount = (id) => G.entries.filter((e) => e.cat === id).length + faqItems.filter((i) => i.cat === id).length;
  const total = G.entries.length + faqItems.length;
  const byId = Object.fromEntries(G.entries.map((e) => [e.id, e]));
  let q = "";
  let cat = store.get("glCat", "all");
  let onlyOpen = store.get("glOpen", false);
  if (cat !== "all" && !cats.some((c) => c.id === cat)) cat = "all";

  const input = h("input", { class: "gl-search", type: "search", placeholder: "搜尋名詞、英文或老師的提問，例：殖利率、Fisher、稀土",
    "aria-label": "搜尋名詞與提問" });
  const kinds = h("div", { class: "chips gl-kinds" });
  const chips = h("div", { class: "chips" });
  const count = h("span", { class: "muted gl-count" });
  const body = h("div", {});

  const hit = (parts) => { if (!q) return true; const needle = q.toLowerCase(); return parts.some((s) => (s || "").toLowerCase().includes(needle)); };
  // 「只看未答」只對題目有意義：名詞沒有答不答的狀態，所以開著時名詞整批收起
  const matchesTerm = (e) => kind !== "class" && !(onlyOpen && kind === "all") && (cat === "all" || e.cat === cat) && hit([e.term, e.en, e.short, e.read]);
  const matchesFaq = (i) => kind !== "term" && (!onlyOpen || i.status === "open") && (cat === "all" || i.cat === cat) && hit([i.q, i.answer]);

  // 點「相關名詞」或題目裡的名詞連結：清掉會把它濾掉的條件，再捲到那一條
  const jump = (id) => {
    const target = byId[id];
    if (!target) return;
    if (!matchesTerm(target)) {
      q = ""; input.value = ""; cat = "all"; kind = "all"; onlyOpen = false;
      store.set("glCat", cat); store.set("glKind", kind); store.set("glOpen", onlyOpen);
      draw();
    }
    const el = document.getElementById("gl-" + id);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      el.classList.remove("gl-flash"); void el.offsetWidth; el.classList.add("gl-flash");
    }
  };

  const entryCard = (e) => h("article", { class: "card span-6 gl-entry", id: "gl-" + e.id },
    h("div", { class: "gl-title" }, h("h3", {}, e.term), h("span", { class: "gl-en" }, e.en)),
    h("p", { class: "gl-short" }, e.short),
    h("p", { class: "gl-read" }, e.read),
    e.links.length ? h("div", { class: "gl-row" }, h("span", { class: "gl-lab" }, "本站哪裡看"),
      ...e.links.map((l) => h("button", { class: "chip gl-link", type: "button", onclick: () => glossaryGo(l) }, glossaryLinkLabel(l, G.events) + " →"))) : null,
    e.related.length ? h("div", { class: "gl-row" }, h("span", { class: "gl-lab" }, "相關"),
      ...e.related.filter((r) => byId[r]).map((r) => h("button", { class: "gl-rel", type: "button", onclick: () => jump(r) }, byId[r].term))) : null);

  function draw() {
    const kindBtn = (k, label) => h("button", { class: `chip${k === "class" ? " gl-kind-class" : ""}`, type: "button", "aria-pressed": String(kind === k),
      onclick: () => { kind = k; store.set("glKind", kind); draw(); } }, label);
    kinds.replaceChildren(kindBtn("all", `全部（${total}）`),
      faqItems.length ? kindBtn("class", `課堂提到（${faqItems.length}）`) : null,
      kindBtn("term", `名詞解釋（${G.entries.length}）`),
      faqItems.length && kind !== "term" ? h("button", { class: "chip", type: "button", "aria-pressed": String(onlyOpen), style: "margin-left:8px",
        onclick: () => { onlyOpen = !onlyOpen; store.set("glOpen", onlyOpen); draw(); } }, `只看未答（${faqOpen}）`) : null);
    chips.replaceChildren(
      h("button", { class: "chip", type: "button", "aria-pressed": String(cat === "all"),
        onclick: () => { cat = "all"; store.set("glCat", cat); draw(); } }, "所有分類"),
      ...cats.filter((c) => catCount(c.id)).map((c) => h("button", { class: "chip", type: "button", "aria-pressed": String(cat === c.id),
        onclick: () => { cat = c.id; store.set("glCat", cat); draw(); } }, `${c.name}（${catCount(c.id)}）`)));
    const shownTerms = G.entries.filter(matchesTerm), shownFaq = faqItems.filter(matchesFaq);
    count.textContent = `顯示 ${shownTerms.length + shownFaq.length} / ${total} 條`;
    body.replaceChildren();
    if (!shownTerms.length && !shownFaq.length) { body.append(h("p", { class: "empty" }, "沒有符合的名詞或題目")); return; }
    for (const c of cats) {
      const qs = shownFaq.filter((i) => i.cat === c.id), ts = shownTerms.filter((e) => e.cat === c.id);
      if (!qs.length && !ts.length) continue;
      body.append(h("h3", { class: "gl-cat" }, c.name, h("span", { class: "muted" }, `　${qs.length + ts.length} 條`)),
        h("div", { class: "grid" }, [...qs.map((i) => faqCard(i, jump)), ...ts.map(entryCard)]));   // 課堂提到的題目排在該分類最前面
    }
  }

  let timer = null;
  input.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(() => { q = input.value.trim(); draw(); }, 120);
  });

  const controls = card({ title: "查詢", span: 12 });
  controls.body.append(h("div", { class: "gl-controls" }, input, count), kinds, chips);
  outer.append(h("div", { class: "grid" }, controls.el), body);
  draw();
  if (pendingTerm) setTimeout(() => jump(pendingTerm), 0);
};
