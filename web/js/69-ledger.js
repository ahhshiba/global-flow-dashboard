/* 沙盤推演的「預測帳本」檢視（2026-10-09）：日線、10／21 個交易日的短期預測，每週一建一批、只增不改、到期自動對答案。
   資料在 gfd/forecast.py 算好，存在 scenario.forecast（跟著沙盤推演那包延後下載）；規格與欄位意義見該檔。
   版面：開頭一行重點 → 常駐的可信度（會改變結論的限制，不收進點開）→ 成績（即時、回測補登分開）→ 本週預測表（每列點開看判斷流程與原因）
   → 最近到期 → 判斷流程（state machine）收合卡 → 下載與試算表。
   回測補登是事後用同一套程式重跑，只供看格式，不是證據，標題就寫出來。 */

// Google 試算表連結（用 IMPORTDATA 讀公開 CSV 的那份）；空字串＝不顯示按鈕
const FC_SHEET_URL = "https://docs.google.com/spreadsheets/d/15Y7w4O7Bu9sOVB7vue_9GPZNzoQi8bG6gU1a1XVOzV8/edit";
const FC_LOCAL_CSV = "data/forecast/forecast.csv";      // 本機單檔版旁邊沒有這個檔，只顯示路徑文字
const FC_USE_STEPS = ["S1", "S5", "S6"];                // 真正參與預測與判定的步驟；S2～S4 只記錄
const FC_VERDICT_CLASS = { "偏漲": "pill-up", "偏跌": "pill-down", "跳過": "pill-warn" };   // 不確定＝灰色 fc-flat（台股慣例：漲紅跌綠）

const fcData = (S) => (S && S.forecast && Array.isArray(S.forecast.batch) && S.forecast.batch.length ? S.forecast : null);
const fcLive = (F, hz) => (F.score && F.score.live && F.score.live[String(hz)]) || {};
const fcLiveDue = (F) => F.horizons.reduce((a, x) => a + (fcLive(F, x).due || 0), 0);
const fcPct = (v, d = 1) => (fin(v) ? `${fmtNum(v, d)}%` : "—");
const fcBuy = (r) => (r.tw_buy && !/^[（(]?無[）)]?$/.test(r.tw_buy) && r.tw_buy !== r.symbol ? r.tw_buy : "");
const fcSub = (r) => [r.symbol, fcBuy(r) ? `台股可買 ${fcBuy(r)}` : null].filter(Boolean).join("・");

// 走步回測的可信度（數字都來自 forecast.backtest）：方向有沒有比「永遠猜漲」準、區間落入率離理想 50% 多遠
function fcCred(F) {
  const per = F.horizons.map((x) => ({ hz: x, b: F.backtest && F.backtest[String(x)] })).filter((p) => p.b && fin(p.b.dir) && fin(p.b.up) && fin(p.b.band));
  if (!per.length) return null;
  const gap = Math.max(...per.map((p) => p.b.dir - p.b.up));            // 方向命中比永遠猜漲高幾個百分點（取各期間最高的）
  const noBetter = gap < 2;
  const band = per.reduce((a, p) => a + p.b.band, 0) / per.length;
  const assets = per[0].b.assets;
  const start = F.backtest.start ? `${String(F.backtest.start).slice(0, 4)} 年起` : "";
  const text = `走步回測（${start}${start && assets ? "、" : ""}${assets ? `${assets} 個資產` : ""}）：`
    + per.map((p) => `${p.hz} 個交易日方向命中 ${fcPct(p.b.dir)}、永遠猜漲 ${fcPct(p.b.up)}`).join("；")
    + `——${noBetter ? "方向沒有比猜漲準" : `方向只比猜漲準 ${fmtNum(gap, 1)} 個百分點`}；`
    + `區間（25%～75%）落入 ${per.map((p) => fcPct(p.b.band)).join("／")}（理想 50%）。`;
  const brief = `${noBetter ? "方向判斷沒有比永遠猜漲準" : "方向判斷只比永遠猜漲準一點"}，區間落入率約 ${fmtNum(band, 0)}%（理想 50%）`;
  return { text, brief, noBetter };
}

// 第一批各期間約幾號到期（各資產的交易日不同，取最早～最晚）
function fcDueRange(F) {
  const out = {};
  for (const x of F.horizons) {
    const ds = F.batch.filter((r) => r.horizon === x && r.due_est).map((r) => r.due_est).sort();
    if (!ds.length) continue;
    const a = ds[0].slice(5), b = ds[ds.length - 1].slice(5);
    out[x] = a === b ? a : `${a}～${b}`;
  }
  return out;
}
const fcDueText = (F) => { const d = fcDueRange(F); return F.horizons.filter((x) => d[x]).map((x) => `${x} 日約 ${d[x]}`).join("、"); };

// 推演總結裡的入口（64-story.js 的故事卡呼叫）：一行，點了切到預測帳本
function fcEntry(S) {
  const F = fcData(S);
  if (!F) return null;
  const cred = fcCred(F);
  return h("div", { class: "fc-entry-row" },
    h("button", { class: "fc-entry", type: "button", onclick: () => window.gotoTab("scenario", () => { window.scView = "ledger"; }) },
      h("span", { class: "fc-entry-t" }, `短期預測帳本：本週 ${F.batch.length} 筆，已到期 ${fcLiveDue(F)} 筆 →`),
      h("span", { class: "sub" }, `${F.horizons.join("／")} 個交易日（約 2 週與 1 個月）就能對答案${cred ? `；${cred.brief}` : ""}`)));
}

// 一個期間一列的成績表。sc＝{ "10": {due, pending, skipped, band, dir, dir_n, up}, ... }
function fcScoreTable(F, sc) {
  const th = (t, n) => h("th", { class: n ? "n" : null }, t);
  return h("div", { class: "tbl-wrap" }, h("table", { class: "data fc-score-tbl" },
    h("thead", {}, h("tr", {}, th("期間"), th("已到期／待到期", 1), th("落在區間", 1), h("th", { class: "n", title: "n＝有做方向判斷的筆數（判定「不確定」的不算）" }, "方向命中"), th("同列永遠猜漲", 1))),
    h("tbody", {}, F.horizons.map((x) => {
      const s = (sc && sc[String(x)]) || {};
      return h("tr", {},
        h("td", {}, `${x} 個交易日`),
        h("td", { class: "n" }, `${s.due ?? 0}／${s.pending ?? 0}`, s.skipped ? h("span", { class: "sub" }, `跳過 ${s.skipped}`) : null),
        h("td", { class: "n" }, fcPct(s.band)),
        h("td", { class: "n" }, fcPct(s.dir), s.dir_n ? h("span", { class: "sub" }, `n=${s.dir_n}`) : null),
        h("td", { class: "n" }, fcPct(s.up)));
    }))));
}

function fcLiveCard(F) {
  const due = fcLiveDue(F);
  const c = card({ title: "即時成績：每週一建的預測，到期後對答案", span: 6,
    sub: "只算「即時」那一批（建立當下才寫下的預測）。落在區間的理想值約 50%；方向命中要贏過「同列永遠猜漲」才算有本事。" });
  if (!due) c.body.append(h("p", { class: "sc-banner t-neutral fc-wait" },
    h("b", {}, "目前還沒有到期的即時預測。"), `第一批 ${fcDueText(F)} 到期，到期後這裡會自動出現成績。`));
  c.body.append(fcScoreTable(F, F.score && F.score.live));
  return c;
}

function fcBackfillCard(F) {
  const c = card({ title: "回測補登（事後用同一套方法重跑，只供看格式，不是證據）", span: 6,
    sub: "帳本第一次建立時，用截至當時的資料補了過去 12 週。程式只用起始日以前的資料，防得了偷看；但設計時已經看過這段歷史，所以不能當成當時公布過的預測。" });
  c.body.append(fcScoreTable(F, F.score && F.score.backfill),
    h("p", { class: "note" }, "即時與補登的成績分開統計，不會混在一起。"));
  return c;
}

/* 本週預測：一列一筆，點開看判斷流程（一步一格）、原因、回測成績、月度沙盤推演 */
function fcStep(s) {
  const rec = /只記錄/.test(s.name || "");
  return h("div", { class: `fc-step${FC_USE_STEPS.includes(s.s) ? " use" : ""}${rec ? " rec" : ""}` },
    h("div", { class: "fc-sh" }, h("small", {}, s.s), h("b", {}, s.name)),
    h("div", { class: "fc-sv" }, s.value),
    s.detail ? h("div", { class: "fc-sd" }, s.detail) : null);
}
function fcFlow(steps, mini) {
  return h("div", { class: `fc-flow${mini ? " mini" : ""}` }, steps.flatMap((s, i) => [i ? h("span", { class: "fc-arrow", "aria-hidden": "true" }, "→") : null, fcStep(s)]));
}
function fcDetail(r) {
  // 基準＝永遠猜多數方向（偏跌的資產贏「永遠猜漲」太容易）
  const maj = fin(r.bt_up) ? Math.max(r.bt_up, 100 - r.bt_up) : null, majName = fin(r.bt_up) && r.bt_up < 50 ? "永遠猜跌" : "永遠猜漲";
  const gap = fin(r.bt_dir) && fin(maj) ? r.bt_dir - maj : null;
  const out = [
    h("h5", {}, "判斷流程（實線＝參與預測，虛線＝只記錄、不參與）"),
    fcFlow(r.steps || []),
    h("h5", {}, "判斷原因"),
    h("p", { class: "fc-reason" }, r.reason),
    h("h5", {}, "回測成績（同資產、同期間的走步回測）"),
    h("p", { class: "fc-bt" }, `方向命中 ${fcPct(r.bt_dir)}，${majName} ${fcPct(maj)}${gap != null && gap < 2 ? `（沒有比${majName}準）` : ""}；預測區間實際落入 ${fcPct(r.bt_band)}（理想 50%）。`),
    h("h5", {}, "月度沙盤推演（3 個月）"),
    h("p", { class: "fc-monthly" }, fin(r.monthly) ? `3 個月期望超額 ${fmtSigned(r.monthly, 2, "%")}（月資料的另一個角度，不參與這筆預測）。` : "沒有對應的月度標的。"),
  ];
  if (r.status === "已到期") out.push(h("h5", {}, "對答案"),
    h("p", {}, `${r.settled} 到期，實際 ${fmtSigned(r.actual, 2, "%")}；落在區間：${r.in_band || "—"}；方向：${r.dir_ok || "—"}。`));
  out.push(h("p", { class: "muted fc-meta" }, `預測編號 ${r.id}・起始日 ${r.start_date || "—"}・起始價 ${fin(r.start_price) ? fmtNum(r.start_price) : "—"}・模型 ${r.version}・${r.source}`));
  return h("div", { class: "fc-detail" }, out);
}
function fcRow(r) {
  const cell = (cls, label, ...kids) => h("span", { class: `fc-c fc-c-${cls}${cls === "name" || cls === "verdict" ? "" : " fc-n"}`, "data-l": label }, ...kids);
  const due = r.status === "已到期" ? `${r.settled} 已到期` : r.due_est || "—";
  const det = h("details", { class: "fc-item fc-row", "data-id": r.id },
    h("summary", { class: "fc-sum" },
      h("span", { class: "fc-c fc-c-name" }, h("span", { class: "fc-asset" }, r.asset), h("span", { class: "sub" }, fcSub(r))),
      cell("hz", "期間", `${r.horizon} 日`),
      cell("pred", "預測", fin(r.pred) ? chg(r.pred, 2) : "—"),
      cell("band", "區間", fin(r.lo) && fin(r.hi) ? `${fmtSigned(r.lo, 2, "%")}～${fmtSigned(r.hi, 2, "%")}` : "—"),
      cell("pup", "上漲機率", fcPct(r.p_up)),
      h("span", { class: "fc-c fc-c-verdict" }, h("span", { class: `pill ${FC_VERDICT_CLASS[r.verdict] || "fc-flat"}` }, r.verdict)),
      h("span", { class: "fc-br", "aria-hidden": "true" }),
      cell("due", "到期", due)));
  det.addEventListener("toggle", () => {
    if (!det.open || det.childElementCount > 1) return;
    det.append(fcDetail(r));
  });
  return det;
}

function fcBatchCard(F) {
  const c = card({ title: `本週預測：${F.week}（${F.batch.length} 筆）`, span: 12,
    sub: "每個資產各預測 10、21 個交易日後的漲跌：預測值是同一個波動狀態下歷史上同樣天數的中位數報酬，區間是 25%～75%。方向判定主要反映資產的長期傾向，不是當下訊號。點一列看判斷流程與原因。" });
  let sel = "all";
  const host = h("div", { class: "fc-list" });
  const chips = h("div", { class: "chips", role: "group", "aria-label": "期間" });
  const head = h("div", { class: "fc-cols", "aria-hidden": "true" },
    ...[["name", "資產（代號・台股可買）"], ["hz", "期間"], ["pred", "預測漲跌"], ["band", "區間（25%～75%）"], ["pup", "上漲機率"], ["verdict", "方向判定"], ["due", "預計到期日"]]
      .map(([k, t]) => h("span", { class: `fc-c fc-c-${k}${k === "name" || k === "verdict" ? "" : " fc-n"}` }, t)));
  const draw = () => {
    chips.replaceChildren(...[["all", "全部"], ...F.horizons.map((x) => [x, `${x} 日`])].map(([k, label]) => h("button", {
      class: "chip", type: "button", "aria-pressed": String(k === sel), onclick: () => { sel = k; draw(); } }, label)));
    host.replaceChildren(head, ...F.batch.filter((r) => sel === "all" || r.horizon === sel).map(fcRow));
  };
  c.tools.append(chips);
  c.body.append(host);
  draw();
  return c;
}

/* 最近到期：預測 vs 實際 */
function fcRecentCard(F) {
  const rec = F.recent || [];
  const c = card({ title: `最近到期（${rec.length} 筆）：預測 vs 實際`, span: 12,
    sub: "落在區間＝實際漲跌落在 25%～75% 區間內（理想約一半）。方向：偏漲且實際 > 0、偏跌且實際 < 0 算對，反過來算錯，「不確定」不判。「補登」是事後重跑的，「即時」才是當時寫下的。" });
  if (!rec.length) { c.body.append(h("p", { class: "empty" }, "還沒有到期的紀錄。")); return c; }
  const th = (t, n) => h("th", { class: n ? "n" : null }, t);
  const tone = { "是": "ok", "對": "ok", "否": "meh", "錯": "meh" };
  const pill = (w) => (w ? h("span", { class: `pill pill-${tone[w] || "bad"}` }, w) : h("span", { class: "muted" }, "—"));
  c.body.append(h("div", { class: "tbl-wrap" }, h("table", { class: "data fc-recent" },
    h("thead", {}, h("tr", {}, th("資產"), th("期間", 1), th("起始日 → 到期日", 1), th("預測", 1), th("區間", 1), th("實際", 1), th("落在區間", 1), th("方向", 1))),
    h("tbody", {}, rec.map((r) => h("tr", { "data-id": r.id },
      h("td", {}, h("span", { class: "fc-asset" }, r.asset, h("span", { class: `fc-src ${r.source === "即時" ? "live" : "bf"}` }, r.source === "即時" ? "即時" : "補登")), h("span", { class: "sub" }, fcSub(r))),
      h("td", { class: "n" }, `${r.horizon} 日`),
      h("td", { class: "n" }, `${r.start_date} → ${r.settled || "—"}`),
      h("td", { class: "n" }, fin(r.pred) ? chg(r.pred, 2) : "—", h("span", { class: "sub" }, r.verdict)),
      h("td", { class: "n" }, `${fmtSigned(r.lo, 2, "%")}～${fmtSigned(r.hi, 2, "%")}`),
      h("td", { class: "n" }, fin(r.actual) ? chg(r.actual, 2) : "—"),
      h("td", { class: "n" }, pill(r.in_band)),
      h("td", { class: "n" }, pill(r.dir_ok))))))));
  return c;
}

/* 判斷流程（state machine）：收合卡 */
function fcMethodCard(F) {
  return foldCard({ title: "判斷流程（state machine）", span: 12, key: "fcMethod",
    sub: "每一筆預測都照 S0 → S7 走一遍，走過的狀態與數值逐步記在帳本裡。展開看每一步做什麼。",
    render: (body) => {
      const steps = (F.batch[0] && F.batch[0].steps) || [];
      body.append(
        h("p", { class: "sc-banner t-meh fc-rec-note" }, h("b", {}, "S2 趨勢、S3 動能、S4 VIX 只記錄，不參與預測。"),
          "2008 年起的走步研究裡，它們對漲跌都沒有預測力；先記下來，留給未來用真實帳本檢驗。"),
        steps.length ? fcFlow(steps.map((s) => ({ s: s.s, name: s.name, value: "", detail: "" })), true) : null,
        h("ol", { class: "fc-method" }, (F.method || []).map((m) => h("li", {}, m))));
    } });
}

/* 下載與試算表 */
function fcLinksCard(F) {
  const c = card({ title: "下載與試算表", span: 12 });
  const csv = GFD.public
    ? h("a", { class: "tool fc-csv", href: F.csv || "data/forecast.csv", download: "forecast.csv" }, "下載 CSV")
    : h("span", { class: "fc-localcsv" }, "本機檔案（在專案資料夾，公開版才有下載連結）：", h("code", {}, FC_LOCAL_CSV));
  const sheet = FC_SHEET_URL ? h("a", { class: "tool fc-sheet", href: FC_SHEET_URL, target: "_blank", rel: "noopener" }, "Google 試算表") : null;
  c.body.append(h("div", { class: "fc-links" }, csv, sheet),
    h("p", { class: "note" }, `帳本目前共 ${F.rows ?? "—"} 列（一列＝一個資產 × 一個期間），只會在最後面新增，舊列的位置與預測欄位不會改。`
      + "Google 試算表用 IMPORTDATA 讀這個 CSV：請不要排序或刪列，手填欄靠列位置對齊。"));
  return c;
}

const LEDGER_VIEW = lazyTab("scenario", (root) => {
  const S = A.scenario, F = fcData(S);
  if (!F) {
    root.replaceChildren(tabHead("短期預測帳本", null));
    root.append(h("p", { class: "empty" }, "尚未產生預測帳本，請執行 python3 gfd.py analyze"));
    return;
  }
  const assets = new Set(F.batch.map((r) => r.asset_id || r.symbol)).size;
  const live0 = fcLiveDue(F) === 0;
  const lead = `本週（${F.week}）${assets} 個資產 × ${F.horizons.join("／")} 個交易日的預測，共 ${F.batch.length} 筆；每週一建一批，到期自動對答案`
    + (live0 ? `；第一批 ${fcDueText(F)} 到期。` : "。");
  root.replaceChildren(tabHead("短期預測帳本：約 2 週與 1 個月後就能對答案",
    "沙盤推演的結果是月資料、看 3～12 個月，要很久才能對答案；這裡另外用日線做短期預測：每週一為每個資產各寫一筆 10 與 21 個交易日的預測，"
    + "附上判斷流程（state machine）、原因與同期間的走步回測成績。預測欄位一旦寫入就不再修改，到期後系統自動填實際漲跌、是否落在區間、方向對錯，所以之後可以拿真實結果檢驗與改進。"
    + "全部是歷史統計，不是投資建議。", false, null, lead));
  const g = h("div", { class: "grid" });
  root.append(g);
  const cred = fcCred(F);
  if (cred) g.append(h("p", { class: "sc-banner t-meh fc-banner span-12" }, h("b", {}, "可信度："), cred.text,
    "目前能宣稱的只有區間；偏漲／偏跌主要是資產的長期上漲傾向，不是當下訊號。"));
  g.append(fcLiveCard(F).el, fcBackfillCard(F).el, fcBatchCard(F).el, fcRecentCard(F).el, fcMethodCard(F).el, fcLinksCard(F).el);
});
