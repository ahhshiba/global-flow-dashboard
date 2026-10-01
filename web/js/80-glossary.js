/* 分頁：名詞解釋（內容在 gfd/glossary.py，build 時內嵌） */

function glossaryGo(link) {
  const [tab, event] = link.split(":");
  if (event) {
    window.gotoTab("cascade", () => {
      // 記憶體直接交給事件衝擊分頁；localStorage 在沙箱 iframe 可能被封鎖，只當作「下次打開」的記憶
      window.csPending = { mode: "event", cat: "all", sel: event };
      store.set("csMode", "event");
      store.set("csCat", "all");
      store.set("csSel", event);
    });
  } else {
    window.gotoTab(tab);
  }
}

function glossaryLinkLabel(link, events) {
  const [tab, event] = link.split(":");
  if (event) return `事件衝擊：${events[event] || event}`;
  const btn = document.getElementById("t-" + tab);
  return btn ? btn.textContent.trim() : tab;
}

TABS.glossary = (outer) => {
  const G = GFD.glossary, F = GFD.faq;
  const pendingTerm = window.glPending; window.glPending = null;
  // 從舊的 #faq 連結或其他地方指定要看哪個檢視（記憶體優先，用過即清）
  let view = pendingTerm ? "terms" : (window.glView || store.get("glView", "terms"));
  window.glView = null;
  if (view !== "faq") view = "terms";
  outer.replaceChildren(tabHead("名詞解釋與 FAQ",
    "本站與課堂用到的專有名詞（一句話定義、怎麼看、在本站哪裡看），以及老師的提問與交辦。標「10/1 課堂」的是 2026-10-01 討論提到的。"
    + "標「約」的數字是量級，不是精確統計。", false));
  if (!G || !G.entries.length) { outer.append(h("p", { class: "empty" }, "沒有名詞資料")); return; }
  const faqOpen = F ? F.items.filter((i) => i.status === "open").length : 0;
  const viewChips = h("div", { class: "chips gl-views" });
  const root = h("div", {});              // 名詞檢視
  const faqRoot = h("div", {});           // FAQ 檢視
  outer.append(viewChips, root, faqRoot);
  let faqDrawn = false;
  const setView = (v) => {
    view = v; store.set("glView", v);
    viewChips.replaceChildren(
      h("button", { class: "chip", type: "button", "aria-pressed": String(v === "terms"), onclick: () => setView("terms") }, `名詞解釋（${G.entries.length}）`),
      F ? h("button", { class: "chip", type: "button", "aria-pressed": String(v === "faq"), onclick: () => setView("faq") },
        `老師的提問 FAQ（${F.items.length}，未答 ${faqOpen}）`) : null);
    root.hidden = v !== "terms";
    faqRoot.hidden = v !== "faq";
    if (v === "faq" && !faqDrawn) { faqDrawn = true; faqView(faqRoot, (id) => { setView("terms"); jump(id); }); }
  };

  const byId = Object.fromEntries(G.entries.map((e) => [e.id, e]));
  let q = "";
  let cat = store.get("glCat", "all");
  let onlyClass = store.get("glClass", false);
  if (cat !== "all" && !G.cats.some((c) => c.id === cat)) cat = "all";

  const input = h("input", { class: "gl-search", type: "search", placeholder: "搜尋名詞、英文或內容，例：殖利率、Fisher、稀土",
    "aria-label": "搜尋名詞" });
  const chips = h("div", { class: "chips" });
  const count = h("span", { class: "muted gl-count" });
  const body = h("div", {});

  const matches = (e) => {
    if (cat !== "all" && e.cat !== cat) return false;
    if (onlyClass && !e.class_note) return false;
    if (!q) return true;
    const needle = q.toLowerCase();
    return [e.term, e.en, e.short, e.read].some((s) => (s || "").toLowerCase().includes(needle));
  };

  // 點「相關名詞」：清掉會把它濾掉的條件，再捲到那一條
  const jump = (id) => {
    const target = byId[id];
    if (!target) return;
    if (!matches(target)) {
      q = ""; input.value = ""; cat = "all"; onlyClass = false;
      store.set("glCat", cat); store.set("glClass", onlyClass);
      draw();
    }
    const el = document.getElementById("gl-" + id);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      el.classList.remove("gl-flash"); void el.offsetWidth; el.classList.add("gl-flash");
    }
  };

  const entryCard = (e) => h("article", { class: "card span-6 gl-entry", id: "gl-" + e.id },
    h("div", { class: "gl-title" },
      h("h3", {}, e.term), h("span", { class: "gl-en" }, e.en),
      e.class_note ? h("span", { class: "pill pill-warn gl-badge" }, "10/1 課堂") : null),
    h("p", { class: "gl-short" }, e.short),
    h("p", { class: "gl-read" }, e.read),
    e.links.length ? h("div", { class: "gl-row" }, h("span", { class: "gl-lab" }, "本站哪裡看"),
      ...e.links.map((l) => h("button", { class: "chip gl-link", type: "button", onclick: () => glossaryGo(l) }, glossaryLinkLabel(l, G.events) + " →"))) : null,
    e.related.length ? h("div", { class: "gl-row" }, h("span", { class: "gl-lab" }, "相關"),
      ...e.related.filter((r) => byId[r]).map((r) => h("button", { class: "gl-rel", type: "button", onclick: () => jump(r) }, byId[r].term))) : null);

  function draw() {
    chips.replaceChildren(
      h("button", { class: "chip", type: "button", "aria-pressed": String(cat === "all"),
        onclick: () => { cat = "all"; store.set("glCat", cat); draw(); } }, `全部（${G.entries.length}）`),
      ...G.cats.map((c) => h("button", { class: "chip", type: "button", "aria-pressed": String(cat === c.id),
        onclick: () => { cat = c.id; store.set("glCat", cat); draw(); } },
        `${c.name}（${G.entries.filter((e) => e.cat === c.id).length}）`)),
      h("button", { class: "chip", type: "button", "aria-pressed": String(onlyClass), style: "margin-left:8px",
        onclick: () => { onlyClass = !onlyClass; store.set("glClass", onlyClass); draw(); } }, "只看 10/1 課堂提到的"));
    const shown = G.entries.filter(matches);
    count.textContent = `顯示 ${shown.length} / ${G.entries.length} 條`;
    body.replaceChildren();
    if (!shown.length) { body.append(h("p", { class: "empty" }, "沒有符合的名詞")); return; }
    for (const c of G.cats) {
      const items = shown.filter((e) => e.cat === c.id);
      if (!items.length) continue;
      body.append(h("h3", { class: "gl-cat" }, `${c.name}`, h("span", { class: "muted" }, `　${items.length} 條`)),
        h("div", { class: "grid" }, items.map(entryCard)));
    }
  }

  let timer = null;
  input.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(() => { q = input.value.trim(); draw(); }, 120);
  });

  const controls = card({ title: "查詢", span: 12 });
  controls.body.append(h("div", { class: "gl-controls" }, input, count), chips);
  root.append(h("div", { class: "grid" }, controls.el), body);
  draw();
  setView(view);
  if (pendingTerm) setTimeout(() => jump(pendingTerm), 0);
};
