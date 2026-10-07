/* FAQ 分頁裡「問題加答案」的卡（內容在 gfd/faq.py；版面在 80-glossary.js）。
   名詞連結在同一個分頁內捲到那一條（jumpTerm），其他連結照常換分頁。 */

function faqGo(link, jumpTerm) {
  const [kind, target] = link.split(":");
  if (kind === "cascade") return glossaryGo(link);
  if (kind === "glossary") return jumpTerm(target);
  window.gotoTab(kind, kind === "scenario" ? () => { window.scView = "summary"; } : null);   // 連到沙盤推演本身開推演總結
}

function faqLabel(link) {
  const F = GFD.faq;
  const [kind, target] = link.split(":");
  if (kind === "cascade" && target) return `事件衝擊：${F.events[target] || target}`;
  if (kind === "glossary" && target) return `名詞：${F.terms[target] || target}`;
  const btn = document.getElementById("t-" + kind);
  if (btn) return btn.textContent.trim();
  if (kind === "research") return "總覽・關聯熱圖";
  return isScView(kind) ? `沙盤推演・${SC_VIEW_LABEL[kind]}` : kind;
}

function faqCard(i, jumpTerm) {
  return h("article", { class: "card span-12 faq-item gl-class", id: "faq-" + i.id },
    h("div", { class: "faq-q" },
      i.status === "open" ? h("span", { class: "pill pill-warn" }, "未答") : null,
      h("h3", {}, i.q)),
    i.answer ? h("p", { class: "faq-a" }, i.answer) : h("p", { class: "faq-a muted" }, "還沒有答案。"),
    i.links.length ? h("div", { class: "gl-row" }, h("span", { class: "gl-lab" }, "本站哪裡看"),
      ...i.links.map((l) => h("button", { class: "chip gl-link", type: "button", onclick: () => faqGo(l, jumpTerm) }, faqLabel(l) + " →"))) : null);
}
