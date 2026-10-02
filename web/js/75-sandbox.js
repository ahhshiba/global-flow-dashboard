/* 分頁：沙盤推演（2026-10-02 起事件衝擊、傳導鏈、訊號劇本併進這個分頁，上方切換四個檢視）
   推演總結＝原本的沙盤推演（65-scenario.js）；另外三個檢視的畫法不變（TABS.cascade／chains／playbook 仍是各檢視的繪製函式，
   只是不再是獨立分頁）。舊網址 #cascade、#chains、#playbook 由 90-boot.js 轉到這裡的對應檢視，網址也跟著檢視走。 */
const SC_VIEWS = [["summary", "推演總結"], ["cascade", "事件衝擊"], ["chains", "傳導鏈"], ["playbook", "訊號劇本"]];
const SC_VIEW_LABEL = Object.fromEntries(SC_VIEWS);
// 只認自己定義的檢視（#toString 之類的網址會查到 Object.prototype，不能當成檢視）
const isScView = (v) => typeof v === "string" && Object.prototype.hasOwnProperty.call(SC_VIEW_LABEL, v);
const SC_VIEW_NEEDS = { summary: "scenario", cascade: "cascade", playbook: "playbook" };   // 公開版要另外下載的資料
const scViewHash = (v) => (v === "summary" ? "scenario" : v);

TABS.scenario = (root, redo) => {
  // localStorage 被封（沙箱 iframe）時，沿用這次瀏覽裡最後的檢視，不要每次重畫都跳回推演總結
  let view = window.scView || store.get("scView", window.scCurrentView || "summary");
  window.scView = null;
  if (!isScView(view)) view = "summary";
  const bar = h("div", { class: "chips sc-views", role: "group", "aria-label": "沙盤推演的檢視" });
  const draw = (v, scroll) => {
    // 每次換檢視都用新的容器：前一個檢視若還在等資料，資料到了只會畫進已經拿掉的舊容器，不會蓋掉現在的檢視
    const host = h("div", { class: "view-root" });
    root.replaceChildren(bar, host);
    view = v;
    window.scCurrentView = v;
    store.set("scView", v);
    bar.replaceChildren(...SC_VIEWS.map(([k, label]) => h("button", {
      class: "chip", type: "button", "aria-pressed": String(k === v),
      onpointerenter: () => { if (SC_VIEW_NEEDS[k]) prefetch([SC_VIEW_NEEDS[k]]); },   // 滑過就先下載
      onclick: () => { if (k !== view) draw(k, true); },
    }, label)));
    const render = v === "summary" ? SCENARIO_SUMMARY : TABS[v];
    try {
      render(host, redo);
      addToc(host);
    } catch (err) {
      host.replaceChildren(h("p", { class: "empty" }, `這個檢視繪製失敗：${err.message}`));
      console.error(err);
    }
    // 網址跟著檢視走：舊連結與分享出去的 #cascade 等都能直接打開對應檢視
    const hash = scViewHash(v);
    if (location.hash.slice(1) !== hash) {
      try { history.replaceState(null, "", "#" + hash); } catch (e) { /* 沙箱 iframe 可能不允許改網址 */ }
    }
    if (scroll && root.getBoundingClientRect().top < 0) jumpTo(root, false);
  };
  draw(view, false);
};
