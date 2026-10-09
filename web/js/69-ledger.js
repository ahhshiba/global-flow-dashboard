/* 沙盤推演的「預測帳本」檢視（v2，2026-10-10）：日線、六個期間（短線 5／10、中線 21／63、長線 126／252 個交易日）的預測，
   短線每週、中線每月第一週、長線每季第一週建一批，只增不改、到期自動對答案。
   資料在 gfd/forecast.py 算好，存在 scenario.forecast（跟著沙盤推演那包延後下載）；欄位意義與規格見該檔與 forecast_columns.csv。
   版面（數字先、說明點開；會改變結論的限制常駐，不收進點開）：
   開頭一行重點 → 常駐可信度（橫幅＋每期間一列的回測表）→ 期間切換與本週預測表（每列點開：判斷條件表、原因、回測、起始價與查價）
   → 系統自動對答案成績（即時與補登分開）→ 最近到期 → 判斷條件（規則表）收合卡 → 下載與試算表。
   試算表的實際結果由人工填寫（第三方驗證），系統自己對的答案只在網站上，不進 CSV。
   回測補登是事後用同一套程式重跑，只供看格式，不是證據，標題就寫出來。 */

// 給第三方人工填寫驗證的 Google 試算表（v2；用 IMPORTDATA 讀公開 CSV）；空字串＝不顯示按鈕
const FC_SHEET_URL = "https://docs.google.com/spreadsheets/d/1p-5VhmfO9gDPwpbapXTr07dsEDofkM5AFaJzlzCUEEw/edit";
const FC_LOCAL_DIR = "data/forecast/";                  // 本機單檔版旁邊沒有這些檔，只顯示路徑文字
const FC_VERDICT_CLASS = { "偏漲": "pill-up", "偏跌": "pill-down", "跳過": "pill-warn" };   // 不確定＝灰色 fc-flat（台股慣例：漲紅跌綠）
const FC_WIDE = 63;                                     // 這個期間（含）以上，區間落入率逐年擺盪大，要加註
const FC_CSV_COLS = 51;                                 // CSV 欄數（A～AY），forecast_columns.csv 讀不到時用這個

const fcData = (S) => (S && S.forecast && Array.isArray(S.forecast.batch) && S.forecast.batch.length && Array.isArray(S.forecast.horizons) && S.forecast.horizons.length ? S.forecast : null);
const fcHs = (F) => F.horizons.map((x) => x.h);
const fcInfo = (F, hz) => F.horizons.find((x) => x.h === hz) || { h: hz, tier: "", label: "" };
const fcHName = (x) => `${x.h} 日${x.label ? `・${x.label}` : ""}`;
const fcLive = (F, hz) => (F.score && F.score.live && F.score.live[String(hz)]) || {};
const fcLiveDue = (F) => fcHs(F).reduce((a, hz) => a + (fcLive(F, hz).due || 0), 0);
const fcPct = (v, d = 1) => (fin(v) ? `${fmtNum(v, d)}%` : "—");
const fcBuy = (r) => (r.tw_buy && !/^[（(]?無[）)]?$/.test(r.tw_buy) && r.tw_buy !== r.symbol ? r.tw_buy : "");
const fcSub = (r) => [r.symbol, fcBuy(r) ? `台股可買 ${fcBuy(r)}` : null].filter(Boolean).join("・");
const fcMaj = (b) => (b && fin(b.maj) ? b.maj : b && fin(b.up) ? Math.max(b.up, 100 - b.up) : null);   // 多數方向（舊資料沒有 maj 時由永遠猜漲推）

// 本週這一批裡，某個期間最早的預計到期日（各資產交易日不同；只看本週批，更早的批次不在這裡）
function fcEarliest(F, hz) {
  const ds = F.batch.filter((r) => r.horizon === hz && r.due_est).map((r) => r.due_est).sort();
  return ds.length ? ds[0] : null;
}
// 本週各層級（短線／中線／長線）有幾筆，依帳本的期間順序；沒建的層級（例如不是月初那一週）不列
function fcTiers(F) {
  const out = [];
  for (const x of F.horizons) {
    const n = F.batch.filter((r) => r.horizon === x.h).length;
    if (!n) continue;
    let t = out.find((o) => o.tier === x.tier);
    if (!t) out.push(t = { tier: x.tier, n: 0, labels: [] });
    t.n += n;
    t.labels.push(x.label || `${x.h} 日`);
  }
  return out;
}

/* ── 常駐可信度：數字全取自 forecast.backtest（2008 年起的走步回測） ── */
function fcCred(F) {
  const per = F.horizons.map((x) => ({ x, b: F.backtest && F.backtest[String(x.h)] })).filter((p) => p.b && fin(p.b.dir));
  if (!per.length) return null;
  per.forEach((p) => { p.maj = fcMaj(p.b); p.worse = fin(p.maj) && p.b.dir < p.maj; p.wide = p.x.h >= FC_WIDE; });
  const worse = per.filter((p) => p.worse), bands = per.map((p) => p.b.band).filter(fin);
  const all = worse.length === per.length;
  const dirText = all ? `在每個期間（${per.map((p) => p.x.label || p.x.h + " 日").join("、")}）都沒有贏過「永遠猜多數方向」`
    : worse.length ? `在 ${worse.map((p) => p.x.label || p.x.h + " 日").join("、")} 沒有贏過「永遠猜多數方向」，其餘期間只略高於它（差距要對照隨機誤差）`
      : "各期間只略高於「永遠猜多數方向」（差距要對照隨機誤差）";
  const bandText = bands.length ? `${fcPct(Math.min(...bands))}～${fcPct(Math.max(...bands))}` : "—";
  const text = `方向判斷（偏漲／偏跌）${dirText}，主要反映資產的長期傾向，不是當下訊號。`
    + `落在 25%～75% 區間的比例整體 ${bandText}（理想 50%）；但 ${FC_WIDE} 日以上的期間逐年擺盪大、個別資產仍會失準，單一批次不一定接近 50%。`
    + "回測補登是事後重跑，不是證據。";
  const brief = all ? "方向判斷在每個期間都沒有贏過永遠猜多數方向，區間落入率約 50%" : "方向判斷沒有明顯贏過永遠猜多數方向";
  return { per, text, brief, all, bandText, start: F.backtest.start, assets: per[0].b.assets };
}

function fcCredTable(cred) {
  const th = (t, n, title) => h("th", { class: n ? "n" : null, title: title || null }, t);
  return h("div", { class: "tbl-wrap" }, h("table", { class: "data fc-cred-tbl" },
    h("thead", {}, h("tr", {}, th("期間"),
      th("回測方向命中", 1, "只算偏漲／偏跌的判定；「不確定」不算"),
      th("永遠猜漲", 1, "這些判定中，實際上漲的比例"),
      th("多數方向", 1, "max(猜漲, 猜跌)：方向命中要贏過它才算有本事"),
      th("落在區間", 1, "實際漲跌落在 25%～75% 區間的比例，理想約 50%"))),
    h("tbody", {}, cred.per.map((p) => h("tr", { "data-h": p.x.h },
      h("td", {}, h("b", {}, `${p.x.tier}・${fcHName(p.x)}`),
        p.worse ? h("span", { class: "fc-flag" }, "方向沒有比猜多數準") : null,
        p.wide ? h("span", { class: "fc-flag soft" }, "區間逐年擺盪大") : null),
      h("td", { class: "n fc-v-dir" }, fcPct(p.b.dir), p.b.nj ? h("span", { class: "sub" }, `判定 ${fmtNum(p.b.nj, 0)}`) : null),
      h("td", { class: "n fc-v-up" }, fcPct(p.b.up)),
      h("td", { class: "n fc-v-maj" }, fcPct(p.maj)),
      h("td", { class: "n fc-v-band" }, fcPct(p.b.band)))))));
}

function fcCredCard(F) {
  const cred = fcCred(F);
  if (!cred) return null;
  const since = cred.start ? `${String(cred.start).slice(0, 4)} 年起` : "";
  const c = card({ title: "系統回測可信度（常駐）", span: 12,
    sub: `走步回測：${since}${since && cred.assets ? "、" : ""}${cred.assets ? `${cred.assets} 個資產` : ""}，每週用當時已知的資料做一次決策、到期後對答案，只算起始日以前已到期的。每一列的判定，下面預測表點開都有。` });
  c.body.append(h("p", { class: "sc-banner t-meh fc-banner" }, h("b", {}, "先看這個："), cred.text), fcCredTable(cred));
  return c;
}

// 推演總結裡的入口（64-story.js 的故事卡呼叫）：一行，點了切到預測帳本
function fcEntry(S) {
  const F = fcData(S);
  if (!F) return null;
  const cred = fcCred(F);
  const tiers = fcTiers(F).map((t) => `${t.tier} ${t.n}`).join("／");
  return h("div", { class: "fc-entry-row" },
    h("button", { class: "fc-entry", type: "button", onclick: () => window.gotoTab("scenario", () => { window.scView = "ledger"; }) },
      h("span", { class: "fc-entry-t" }, `預測帳本：${tiers} 筆，系統已對答案 ${fcLiveDue(F)} 筆 →`),
      h("span", { class: "sub" }, `從 ${F.horizons[0].label || F.horizons[0].h + " 日"}到 ${F.horizons[F.horizons.length - 1].label || F.horizons[F.horizons.length - 1].h + " 日"}共 ${F.horizons.length} 個期間，每筆列出判斷條件與回測可信度${cred ? `；${cred.brief}` : ""}`)));
}

/* ── 系統自動對答案的成績（網站自己的，不在試算表）。sc＝{ "5": {due, pending, skipped, band, dir, dir_n, up, maj}, ... } ── */
function fcScoreTable(F, sc, live) {
  const th = (t, n, title) => h("th", { class: n ? "n" : null, title: title || null }, t);
  return h("div", { class: "tbl-wrap" }, h("table", { class: "data fc-score-tbl" },
    h("thead", {}, h("tr", {}, th("期間"), th("已到期／待到期", 1), th("落在區間", 1),
      th("方向命中", 1, "n＝有做方向判斷的筆數（判定「不確定」的不算）"), th("永遠猜漲", 1), th("多數方向", 1, "max(猜漲, 猜跌)：方向命中要贏過它才算有本事"))),
    h("tbody", {}, F.horizons.map((x) => {
      const s = (sc && sc[String(x.h)]) || {}, first = live && !s.due ? fcEarliest(F, x.h) : null;
      return h("tr", { "data-h": x.h },
        h("td", {}, h("span", { class: "fc-tier" }, `${x.tier} `), `${x.h} 日`, first ? h("span", { class: "sub fc-first" }, `最早約 ${first.slice(5)} 到期`) : null),
        h("td", { class: "n" }, `${s.due ?? 0}／${s.pending ?? 0}`, s.skipped ? h("span", { class: "sub" }, `跳過 ${s.skipped}`) : null),
        h("td", { class: "n" }, fcPct(s.band)),
        h("td", { class: "n" }, fcPct(s.dir), s.dir_n ? h("span", { class: "sub" }, `n=${s.dir_n}`) : null),
        h("td", { class: "n" }, fcPct(s.up)),
        h("td", { class: "n" }, fcPct(s.maj)));
    }))));
}

function fcLiveCard(F) {
  const due = fcLiveDue(F);
  const c = card({ title: "即時成績：建立當下寫下的預測，到期後系統對答案", span: 6,
    sub: "這是網站自己對的答案，不在 Google 試算表（試算表的結果由人工填寫）。只算「即時」那一批；落在區間的理想值約 50%，方向命中要贏過「多數方向」才算有本事。" });
  if (!due) {
    const firsts = F.horizons.map((x) => fcEarliest(F, x.h)).filter(Boolean).sort();
    c.body.append(h("p", { class: "sc-banner t-neutral fc-wait" }, h("b", {}, "目前還沒有到期的即時預測。"),
      firsts.length ? `最早 ${firsts[0]} 到期（${F.horizons.map((x) => `${x.h} 日約 ${(fcEarliest(F, x.h) || "—").slice(5)}`).join("、")}），到期後這裡會自動出現成績。` : ""));
  }
  c.body.append(fcScoreTable(F, F.score && F.score.live, true));
  return c;
}

function fcBackfillCard(F) {
  const c = card({ title: "回測補登（事後用同一套方法重跑，只供看格式，不是證據）", span: 6,
    sub: "帳本第一次建立時，用截至當時的資料補了過去的批次（每週期間 12 週、每月期間 12 個月、每季期間 8 季）。程式只用起始日以前的資料，防得了偷看；但設計時已經看過這段歷史，所以不能當成當時公布過的預測。補登只在網站上，不進 CSV 與試算表。" });
  c.body.append(fcScoreTable(F, F.score && F.score.backfill, false),
    h("p", { class: "note" }, "即時與補登的成績分開統計，不會混在一起。"));
  return c;
}

/* ── 本週預測：一列一筆，點開看判斷條件表、原因、回測、起始價與查價網址 ── */
function fcCondTable(steps) {
  const th = (t) => h("th", {}, t);
  return h("div", { class: "tbl-wrap fc-cond-wrap" }, h("table", { class: "data fc-cond fc-stack" },
    h("thead", {}, h("tr", {}, ["步驟", "條件", "實際數值", "門檻／規則", "結果", "是否參與預測"].map(th))),
    h("tbody", {}, steps.map((s) => {
      const used = !!s.used_in_prediction;
      return h("tr", { class: used ? "use" : "rec", "data-s": s.s },
        h("td", { class: "fc-s", "data-l": "步驟" }, s.s),
        h("td", { class: "fc-nm", "data-l": "條件" }, s.name),
        h("td", { class: "fc-val", "data-l": "實際數值" }, s.value ?? "—"),
        h("td", { class: "fc-thr", "data-l": "門檻／規則" }, s.threshold ?? "—"),
        h("td", { class: "fc-res", "data-l": "結果" }, h("b", {}, s.result ?? "—")),
        h("td", { class: "fc-use", "data-l": "是否參與預測" }, h("span", { class: `fc-part ${used ? "use" : "rec"}` }, used ? "參與預測" : "只記錄")));
    }))));
}

// 回測成績（同資產、同期間）：基準是「永遠猜多數方向」，偏跌的資產贏「永遠猜漲」太容易
function fcBt(r) {
  const gap = fin(r.bt_dir) && fin(r.bt_maj) ? r.bt_dir - r.bt_maj : null;
  const kv = (l, v, extra) => h("div", { class: "fc-kv" }, h("span", { class: "fc-kl" }, l), h("b", {}, v), extra || null);
  const claim = gap == null ? "這個資產與期間的回測判定太少，沒有可比的成績。"
    : gap < 0 ? `方向沒有比猜多數準（低 ${fmtNum(-gap, 1)} 個百分點）。`
      : gap < 0.05 ? "方向和猜多數一樣準，沒有比較準。"
        : gap < 2 ? `只比多數方向高 ${fmtNum(gap, 1)} 個百分點，在隨機誤差內，不能算比較準。` : `比多數方向高 ${fmtNum(gap, 1)} 個百分點；每週決策的報酬互相重疊，等效獨立次數遠少於判定次數，隨機誤差仍要放寬看。`;
  return [
    h("div", { class: "fc-kvs" },
      kv("判定次數", fin(r.bt_n) ? fmtNum(r.bt_n, 0) : "—", fin(r.bt_nall) ? h("span", { class: "sub" }, `全部決策 ${fmtNum(r.bt_nall, 0)}`) : null),
      kv("方向命中", fcPct(r.bt_dir)), kv("永遠猜漲", fcPct(r.bt_up)), kv("多數方向", fcPct(r.bt_maj)), kv("落在區間", fcPct(r.bt_band), h("span", { class: "sub" }, "理想 50%"))),
    h("p", { class: "fc-bt" }, claim),
  ];
}

function fcStart(r) {
  const same = fin(r.start_raw) && fin(r.start_adj) && r.start_raw === r.start_adj;
  const num = (v) => (fin(v) ? String(v) : "—");
  return [
    h("div", { class: "fc-kvs" },
      h("div", { class: "fc-kv" }, h("span", { class: "fc-kl" }, "起始日"), h("b", { class: "fc-start-date" }, r.start_date || "—")),
      h("div", { class: "fc-kv" }, h("span", { class: "fc-kl" }, "起始收盤（未還原）"), h("b", { class: "fc-start-raw" }, num(r.start_raw)), h("span", { class: "sub" }, "查價網站看到的數字")),
      h("div", { class: "fc-kv" }, h("span", { class: "fc-kl" }, "起始收盤（還原權息）"), h("b", { class: "fc-start-adj" }, num(r.start_adj)), h("span", { class: "sub" }, same ? "與未還原相同" : "模型用，查價網站通常看不到"))),
    h("p", { class: "fc-verify" }, h("b", {}, "人工驗證請用未還原收盤。"), "到期收盤也查未還原價，期間內有配息再另外填配息。",
      r.url ? h("span", { class: "fc-urlrow" }, "查價網址：", h("a", { class: "fc-url", href: r.url, target: "_blank", rel: "noopener" }, r.url)) : null),
  ];
}

function fcDetail(r) {
  const months = r.horizon / 21;
  const monthly = r.horizon >= 63 && Number.isInteger(months)
    ? [h("h5", {}, `月度沙盤推演同期間看法（${months} 個月）`),
      h("p", { class: "fc-monthly" }, fin(r.monthly)
        ? `${months} 個月期望超額 ${fmtSigned(r.monthly, 2, "%")}；月度回測判定：${r.monthly_verdict || "—"}。月資料的另一個角度，只是並排放，不參與這筆預測。`
        : "沒有對應的月度標的。")]
    : [];
  const out = [
    h("h5", {}, "判斷條件"),
    h("p", { class: "fc-legend" }, h("span", { class: "fc-part use" }, "參與預測"), "＝實線，真的進了預測；", h("span", { class: "fc-part rec" }, "只記錄"), "＝虛線、灰字，只留紀錄、不改預測，供之後用真實結果檢驗。"),
    fcCondTable(r.steps || []),
    h("h5", {}, "判斷原因"),
    h("p", { class: "fc-reason" }, r.reason),
    h("p", { class: "fc-flowline" }, h("b", {}, "判斷流程："), r.flow),
    h("h5", {}, "回測成績（同資產、同期間的走步回測）"),
    ...fcBt(r),
    ...monthly,
    h("h5", {}, "起始價與人工查價"),
    ...fcStart(r),
  ];
  if (r.status === "已到期") out.push(h("h5", {}, "系統對答案"),
    h("p", {}, `${r.settled} 到期，實際 ${fmtSigned(r.actual, 2, "%")}（還原權息價）；落在區間：${r.in_band || "—"}；方向：${r.dir_ok || "—"}。`));
  out.push(h("p", { class: "muted fc-meta" }, `預測編號 ${r.id}・${r.source}・模型 ${r.version}・建立 ${r.created}`));
  return h("div", { class: "fc-detail" }, out);
}

function fcRow(r) {
  const cell = (cls, label, ...kids) => h("span", { class: `fc-c fc-c-${cls}${cls === "name" || cls === "verdict" || cls === "code" ? "" : " fc-n"}`, "data-l": label }, ...kids);
  const x = { h: r.horizon, label: r.h_label };
  const det = h("details", { class: "fc-item fc-row", "data-id": r.id },
    h("summary", { class: "fc-sum" },
      h("span", { class: "fc-c fc-c-name" }, h("span", { class: "fc-asset" }, r.asset), h("span", { class: "sub" }, fcSub(r))),
      cell("hz", "期間", fcHName(x)),
      cell("pred", "預測", fin(r.pred) ? chg(r.pred, 2) : "—"),
      cell("band", "區間", fin(r.lo) && fin(r.hi) ? `${fmtSigned(r.lo, 2, "%")}～${fmtSigned(r.hi, 2, "%")}` : "—"),
      cell("pup", "上漲機率", fcPct(r.p_up)),
      h("span", { class: "fc-c fc-c-verdict" }, h("span", { class: `pill ${FC_VERDICT_CLASS[r.verdict] || "fc-flat"}` }, r.verdict)),
      h("span", { class: "fc-br", "aria-hidden": "true" }),
      cell("due", "到期", r.due_est || "—", r.status === "已到期" ? h("span", { class: "sub" }, `${r.settled} 已到期`) : null),
      r.code ? h("span", { class: "fc-c fc-c-code", title: "狀態代碼（機器可讀）" }, r.code) : null));
  det.addEventListener("toggle", () => {
    if (!det.open || det.childElementCount > 1) return;
    det.append(fcDetail(r));
  });
  return det;
}

// 一個期間一組：標題列寫這個期間本批的偏漲／偏跌／不確定各幾筆與最早到期日
function fcGroup(F, x, rows) {
  const cnt = {};
  rows.forEach((r) => { cnt[r.verdict] = (cnt[r.verdict] || 0) + 1; });
  const first = fcEarliest(F, x.h);
  return h("div", { class: "fc-grp", "data-h": x.h },
    h("b", {}, `${x.tier}・${fcHName(x)}`),
    h("span", { class: "sub" }, `${rows.length} 筆：偏漲 ${cnt["偏漲"] || 0}・偏跌 ${cnt["偏跌"] || 0}・不確定 ${cnt["不確定"] || 0}${cnt["跳過"] ? `・跳過 ${cnt["跳過"]}` : ""}${first ? `・最早約 ${first} 到期` : ""}`));
}

function fcBatchCard(F) {
  const infos = F.horizons.filter((x) => F.batch.some((r) => r.horizon === x.h));
  const tiers = fcTiers(F);
  const c = card({ title: `本週預測：${F.week}（${F.batch.length} 筆）`, span: 12,
    sub: "數字先看：預測漲跌是同一個波動狀態下，歷史上同樣天數的中位數報酬；區間是 25%～75%；方向判定主要反映資產的長期傾向，不是當下訊號。點一列看「判斷條件」：每一步用了什麼數值、對照什麼門檻、結果是什麼、有沒有參與預測。" });
  let sel = "all";
  const host = h("div", { class: "fc-list" });
  const count = h("p", { class: "fc-count", role: "status" });
  const chips = h("div", { class: "chips fc-chips", role: "group", "aria-label": "期間" });
  const head = h("div", { class: "fc-cols", "aria-hidden": "true" },
    ...[["name", "資產（代號・台股可買）"], ["hz", "期間"], ["pred", "預測漲跌"], ["band", "區間（25%～75%）"], ["pup", "上漲機率"], ["verdict", "方向判定"], ["due", "預計到期日"]]
      .map(([k, t]) => h("span", { class: `fc-c fc-c-${k}${k === "name" || k === "verdict" ? "" : " fc-n"}` }, t)));
  const match = (r) => sel === "all" || r.tier === sel || r.horizon === sel;
  const draw = () => {
    const chip = ([k, label]) => h("button", { class: "chip", type: "button", "data-k": String(k), "aria-pressed": String(k === sel), onclick: () => { sel = k; draw(); } }, label);
    chips.replaceChildren(chip(["all", "全部"]), h("span", { class: "lab" }, "層級"), ...tiers.map((t) => chip([t.tier, t.tier])),
      h("span", { class: "lab" }, "期間"), ...infos.map((x) => chip([x.h, x.label || `${x.h} 日`])));
    const shown = F.batch.filter(match);
    count.textContent = `顯示 ${shown.length}／${F.batch.length} 筆`;
    host.replaceChildren(head, ...infos.flatMap((x) => {
      const rows = shown.filter((r) => r.horizon === x.h);
      return rows.length ? [fcGroup(F, x, rows), ...rows.map(fcRow)] : [];
    }));
  };
  c.tools.append(chips);
  c.body.append(count, host);
  draw();
  return c;
}

/* ── 最近到期（系統對答案）：預測 vs 實際 ── */
function fcRecentCard(F) {
  const rec = F.recent || [];
  const c = card({ title: `最近到期（${rec.length} 筆）：預測 vs 實際`, span: 12,
    sub: "系統對的答案，不在試算表。落在區間＝實際漲跌落在 25%～75% 區間內（理想約一半）。方向：偏漲且實際 > 0、偏跌且實際 < 0 算對，反過來算錯，「不確定」不判。「補登」是事後重跑的、不是證據，「即時」才是當時寫下的。" });
  if (!rec.length) { c.body.append(h("p", { class: "empty" }, "還沒有到期的紀錄。")); return c; }
  const th = (t, n) => h("th", { class: n ? "n" : null }, t);
  const tone = { "是": "ok", "對": "ok", "否": "meh", "錯": "meh" };
  const pill = (w) => (w ? h("span", { class: `pill pill-${tone[w] || "bad"}` }, w) : h("span", { class: "muted" }, "—"));
  c.body.append(h("div", { class: "tbl-wrap" }, h("table", { class: "data fc-recent" },
    h("thead", {}, h("tr", {}, th("資產"), th("期間", 1), th("起始日 → 到期日", 1), th("預測", 1), th("區間", 1), th("實際", 1), th("落在區間", 1), th("方向", 1))),
    h("tbody", {}, rec.map((r) => h("tr", { "data-id": r.id },
      h("td", {}, h("span", { class: "fc-asset" }, r.asset, h("span", { class: `fc-src ${r.source === "即時" ? "live" : "bf"}` }, r.source === "即時" ? "即時" : "補登")), h("span", { class: "sub" }, fcSub(r))),
      h("td", { class: "n" }, `${r.horizon} 日`, h("span", { class: "sub" }, r.h_label || "")),
      h("td", { class: "n" }, `${r.start_date} → ${r.settled || "—"}`),
      h("td", { class: "n" }, fin(r.pred) ? chg(r.pred, 2) : "—", h("span", { class: "sub" }, r.verdict)),
      h("td", { class: "n" }, `${fmtSigned(r.lo, 2, "%")}～${fmtSigned(r.hi, 2, "%")}`),
      h("td", { class: "n" }, fin(r.actual) ? chg(r.actual, 2) : "—"),
      h("td", { class: "n" }, pill(r.in_band)),
      h("td", { class: "n" }, pill(r.dir_ok))))))));
  return c;
}

/* ── 判斷條件（規則表）：收合卡。每一條都能照著算，輸出到 CSV 的哪一欄 ── */
function fcRulesCard(F) {
  const rules = F.rules || [];
  return foldCard({ title: `判斷條件（規則表，${rules.length} 條）`, span: 12, key: "fcRules",
    sub: "每一筆預測都照這些規則走，定義寫到可以照著算，門檻與參數就是程式裡用的數字；「是否參與預測」寫「否」的只是記錄或參考，不改預測。同一份內容也輸出成 forecast_rules.csv，試算表會自動讀入。",
    render: (body) => {
      const th = (t) => h("th", {}, t);
      const usedYes = (v) => /^是/.test(v || "");
      const cls = ["fc-rc", "fc-rs", "fc-rn", "fc-rd", "fc-rt", "fc-rp", "fc-ro", "fc-rb"];
      body.append(
        h("div", { class: "tbl-wrap" }, h("table", { class: "data fc-rules fc-stack" },
          h("thead", {}, h("tr", {}, ["規則代碼", "步驟", "名稱", "定義", "門檻或參數", "是否參與預測", "輸出欄位", "研究依據"].map(th))),
          h("tbody", {}, rules.map((q) => {
            const v = [q["規則代碼"], q["步驟"], q["名稱"], q["定義"], q["門檻或參數"], q["是否參與預測"], q["輸出到哪一欄"], q["研究依據"]];
            const lab = ["規則代碼", "步驟", "名稱", "定義", "門檻或參數", "是否參與預測", "輸出欄位", "研究依據"];
            return h("tr", { class: usedYes(q["是否參與預測"]) ? "use" : "rec", "data-code": q["規則代碼"] },
              v.map((t, i) => h("td", { class: cls[i], "data-l": lab[i] }, t ?? "—")));
          })))),
        (F.method || []).length ? moreBox("方法與誠實聲明（逐條文字版）", h("ol", { class: "fc-method" }, F.method.map((m) => h("li", {}, m)))) : null);
    } });
}

/* ── 下載與試算表 ── */
function fcLinksCard(F) {
  const c = card({ title: "下載與試算表", span: 12 });
  const files = [[F.csv || "data/forecast.csv", "預測"], [F.rules_csv || "data/forecast_rules.csv", "判斷條件"], [F.columns_csv || "data/forecast_columns.csv", "欄位說明"]];
  const base = (p) => String(p).split("/").pop();
  const csvs = GFD.public
    ? files.map(([p, label]) => h("a", { class: "tool fc-csv", href: p, download: base(p), "data-kind": label }, `下載 CSV：${label}`))
    : [h("span", { class: "fc-localcsv" }, "本機檔案（在專案資料夾，公開版才有下載連結）：",
      ...files.map(([p]) => h("code", {}, FC_LOCAL_DIR + base(p))))];
  const sheet = FC_SHEET_URL ? [h("a", { class: "tool fc-sheet", href: FC_SHEET_URL, target: "_blank", rel: "noopener" }, "Google 試算表"),
    h("span", { class: "fc-sheet-note" }, "試算表的實際結果由人工填寫（第三方驗證），系統答案不會進試算表")] : [];
  const nCols = (F.columns || []).filter((q) => q["誰填"] === "系統").length || FC_CSV_COLS;
  c.body.append(h("div", { class: "fc-links" }, ...csvs, ...sheet),
    h("p", { class: "note" }, `預測 CSV 共 ${F.live_rows ?? "—"} 列（只有即時列；帳本另有 ${F.rows != null && F.live_rows != null ? F.rows - F.live_rows : "—"} 列補登，只在網站上）、固定 ${nCols} 欄，`
      + "只會在最後面新增列，舊列的位置與內容不會改；請不要排序或刪列，試算表的手填欄靠列位置對齊。判斷條件與欄位說明兩份由程式常數產生，試算表用 IMPORTDATA 自動讀入。"));
  return c;
}

const LEDGER_VIEW = lazyTab("scenario", (root) => {
  const S = A.scenario, F = fcData(S);
  if (!F) {
    root.replaceChildren(tabHead("預測帳本", null));
    root.append(h("p", { class: "empty" }, "尚未產生預測帳本，請執行 python3 gfd.py analyze"));
    return;
  }
  const tiers = fcTiers(F);
  const lead = `本週（${F.week}）建立 ${F.batch.length} 筆：`
    + tiers.map((t) => `${t.tier} ${t.n}（${t.labels.join("、")}）`).join("、")
    + "。節奏：短線每週、中線每月第一週、長線每季第一週；到期後系統自動對答案。";
  root.replaceChildren(tabHead("預測帳本：從 1 週到 12 個月，每筆都寫出判斷條件",
    "沙盤推演的結果是月資料、看 3～12 個月，要很久才能對答案；這裡另外用日線做預測，從短線（1、2 週）到中線（1、3 個月）到長線（6、12 個月）都有：每個資產各寫一筆，"
    + "把每一步的判斷條件（波動、均線、動能、VIX、樣本數）連同實際數值與門檻拆開記下，並附上同期間的走步回測成績，方便之後量化與檢驗。預測欄位一旦寫入就不再修改。"
    + "系統到期後自己對答案（只顯示在網站）；另外有一份 Google 試算表，實際結果由人工查價填寫，是獨立的第三方驗證。全部是歷史統計，不是投資建議。", false, null, lead));
  const g = h("div", { class: "grid" });
  root.append(g);
  const cred = fcCredCard(F);
  g.append(...[cred && cred.el, fcBatchCard(F).el, fcLiveCard(F).el, fcBackfillCard(F).el, fcRecentCard(F).el, fcRulesCard(F).el, fcLinksCard(F).el].filter(Boolean));
});
