/* 名詞解釋分頁裡的「老師的提問（FAQ）」檢視（內容在 gfd/faq.py）。
   名詞連結在同一個分頁內切回名詞檢視並捲到那一條（jumpTerm），其他連結照常換分頁。 */

function faqGo(link, jumpTerm) {
  const [kind, target] = link.split(":");
  if (kind === "cascade") return glossaryGo(link);
  if (kind === "glossary") return jumpTerm(target);
  window.gotoTab(kind);
}

function faqView(root, jumpTerm) {
  const F = GFD.faq;
  if (!F || !F.items.length) { root.append(h("p", { class: "empty" }, "沒有 FAQ 資料")); return; }
  let cat = store.get("faqCat", "all");
  let only = store.get("faqOpen", false);
  if (cat !== "all" && !F.cats.some((c) => c.id === cat)) cat = "all";
  const open = F.items.filter((i) => i.status === "open").length;
  const chips = h("div", { class: "chips" });
  const body = h("div", {});
  const label = (link) => {
    const [kind, target] = link.split(":");
    if (kind === "cascade" && target) return `事件衝擊：${F.events[target] || target}`;
    if (kind === "glossary" && target) return `名詞：${F.terms[target] || target}`;
    const btn = document.getElementById("t-" + kind);
    return btn ? btn.textContent.trim() : kind;
  };
  const item = (i) => h("article", { class: `card span-12 faq-item ${i.status}` },
    h("div", { class: "faq-q" },
      h("span", { class: `pill ${i.status === "open" ? "pill-warn" : "pill-up"}` }, i.status === "open" ? "未答" : "已答"),
      h("h3", {}, i.q), h("span", { class: "muted faq-asked" }, `${i.asked} 課堂`)),
    i.answer ? h("p", { class: "faq-a" }, i.answer) : h("p", { class: "faq-a muted" }, "尚未回答。回答寫在 gfd/faq.py 的 answer 欄。"),
    i.links.length ? h("div", { class: "gl-row" }, h("span", { class: "gl-lab" }, "本站哪裡看"),
      ...i.links.map((l) => h("button", { class: "chip gl-link", type: "button", onclick: () => faqGo(l, jumpTerm) }, label(l) + " →"))) : null);
  const draw = () => {
    chips.replaceChildren(
      h("button", { class: "chip", type: "button", "aria-pressed": String(cat === "all"), onclick: () => { cat = "all"; store.set("faqCat", cat); draw(); } }, `全部（${F.items.length}）`),
      ...F.cats.map((c) => h("button", { class: "chip", type: "button", "aria-pressed": String(cat === c.id), onclick: () => { cat = c.id; store.set("faqCat", cat); draw(); } },
        `${c.name}（${F.items.filter((i) => i.cat === c.id).length}）`)),
      h("button", { class: "chip", type: "button", "aria-pressed": String(only), style: "margin-left:8px", onclick: () => { only = !only; store.set("faqOpen", only); draw(); } }, `只看未答（${open}）`));
    const shown = F.items.filter((i) => (cat === "all" || i.cat === cat) && (!only || i.status === "open"));
    body.replaceChildren();
    if (!shown.length) { body.append(h("p", { class: "empty" }, "沒有符合的題目")); return; }
    for (const c of F.cats) {
      const items = shown.filter((i) => i.cat === c.id);
      if (!items.length) continue;
      body.append(h("h3", { class: "gl-cat" }, c.name, h("span", { class: "muted" }, `　${items.length} 題`)), h("div", { class: "grid" }, items.map(item)));
    }
  };
  const holder = card({ title: "老師的提問與交辦", span: 12,
    sub: `${F.items.length} 題，未答 ${open} 題。每一題是課堂上老師要求搞懂或做到的事，回答後在 gfd/faq.py 更新；每題附本站可以查的地方。` });
  holder.tools.append(chips);
  root.append(h("div", { class: "grid" }, holder.el), body);
  draw();
}
