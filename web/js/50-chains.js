/* 分頁：傳導鏈（事件 → 第二層 → 第三層…） */

const CH_HORIZON_LABEL = { 1: "1 個月", 3: "3 個月", 6: "6 個月", 12: "12 個月" };

function chUnit(v, unit, digits) {
  if (!fin(v)) return "—";
  return fmtSigned(v, digits ?? (unit === "bp" ? 0 : 1), unit === "bp" ? "bp" : "%");
}
function chChg(v, unit) {
  return h("span", { class: dirClass(v) }, `${arrow(v)} ${chUnit(v, unit)}`.trim());
}
const chVerdictTone = (v) => (v.includes("都顯著") ? "up" : v.includes("報酬顯著") ? "up" : v.includes("只有傳導") ? "warn" : "neutral");

/* 事件後第 1～12 個月的平均月變動 */
function profileChart(host, profile, unit) {
  const W = Math.max(260, host.clientWidth || 400), H = 150;
  const ml = 38, mr = 8, mt = 10, mb = 26, pw = W - ml - mr, ph = H - mt - mb;
  const vals = profile.map((p) => p.mean).filter(fin);
  if (!vals.length) { host.replaceChildren(h("p", { class: "empty" }, "樣本不足")); return; }
  const m = Math.max(...vals.map(Math.abs)) * 1.2 || 1;
  const X = (i) => ml + ((i + 0.5) / profile.length) * pw;
  const Y = (v) => mt + (1 - (v + m) / (2 * m)) * ph;
  const svg = sv("svg", { viewBox: `0 0 ${W} ${H}`, height: H, role: "img", "aria-label": "事件後各月平均變動" });
  for (const t of [-m, 0, m]) {
    svg.append(sv("line", { x1: ml, x2: ml + pw, y1: Y(t), y2: Y(t), style: `stroke:${t === 0 ? "var(--line-strong)" : "var(--grid)"}` }));
    svg.append(sv("text", { x: ml - 6, y: Y(t) + 3.5, "text-anchor": "end" }, chUnit(t, unit, unit === "bp" ? 0 : 1)));
  }
  const bw = Math.max(6, (pw / profile.length) * 0.6);
  profile.forEach((p, i) => {
    if (!fin(p.mean)) return;
    const y = Y(Math.max(0, p.mean));
    svg.append(sv("rect", { x: X(i) - bw / 2, y, width: bw, height: Math.max(1, Math.abs(Y(p.mean) - Y(0))), rx: 2,
      style: `fill:${p.mean >= 0 ? "var(--up)" : "var(--down)"}` }));
    if (i % 2 === 0) svg.append(sv("text", { x: X(i), y: H - 8, "text-anchor": "middle" }, String(p.m)));
    const hit = sv("rect", { x: X(i) - pw / (profile.length * 2), y: mt, width: pw / profile.length, height: ph, class: "hit" });
    hit.addEventListener("pointermove", (e) => showTip(
      `<div class="tip-h">事件後第 ${p.m} 個月</div><div>平均 <b class="mono">${chUnit(p.mean, unit)}</b>　n = ${p.n}</div>`, e.clientX, e.clientY));
    hit.addEventListener("pointerleave", hideTip);
    svg.append(hit);
  });
  svg.append(sv("text", { x: ml + pw, y: H - 8, "text-anchor": "end", class: "lbl" }, "事件後第 N 個月"));
  host.replaceChildren(svg);
}

function chainLinkDetail(chain, link) {
  const up = chain.nodes.find((n) => n.id === link.from_);
  const dn = chain.nodes.find((n) => n.id === link.to);
  const c = card({ title: `${up.name} → ${dn.name}`, span: 12,
    sub: `上游：${up.label}；下游：${dn.label}。下面的統計以「上游成立的那個月」為起點。`,
    note: `事件數為合併後的獨立事件（間隔 ≤ ${A.chains.gap} 個月視為同一次）；p 值為觸發序列循環位移 2000 次的雙尾比例，只說明隨機挑同樣多時點有多容易得到同樣結果。` });

  c.body.append(h("div", { class: "viewer-sum", style: "margin-bottom:10px" },
    h("span", {}, "傳導機率 ", h("b", { class: "mono" }, fin(link.prob) ? `${link.prob.toFixed(0)}%` : "—"),
      h("span", { class: "muted" }, `（平常 ${fin(link.prob_base) ? link.prob_base.toFixed(0) + "%" : "—"}、${link.prob_n} 次事件）`)),
    h("span", {}, "等待中位數 ", h("b", { class: "mono" }, fin(link.wait_median) ? `${link.wait_median} 個月` : "—")),
    h("span", { class: `pill pill-${chVerdictTone(link.verdict)}` }, link.verdict)));

  const head = ["期間", "事件後中位數", "平常（無條件）", "差", "上漲比例", "最糟一次", "期間內最大逆行", "p", "n"];
  const rows = A.chains.horizons.map((hh) => {
    const x = link.horizons[String(hh)];
    if (!x) return null;
    const e = x.event, b = x.base;
    return h("tr", {},
      h("td", {}, CH_HORIZON_LABEL[hh] || `${hh} 個月`),
      h("td", { class: "n" }, chChg(e.median, link.unit)),
      h("td", { class: "n muted" }, chUnit(b.median, link.unit)),
      h("td", { class: "n" }, chChg(x.lift, link.unit)),
      h("td", { class: "n" }, fin(e.hit) ? `${e.hit.toFixed(0)}%` : "—"),
      h("td", { class: "n down" }, chUnit(e.worst, link.unit)),
      h("td", { class: "n" }, chUnit(x.mae && x.mae.median, link.unit)),
      h("td", { class: "n" }, fin(x.p) ? (x.p <= 0.05 ? h("b", {}, x.p.toFixed(3)) : x.p.toFixed(3)) : "—"),
      h("td", { class: "n muted" }, e.n || 0));
  }).filter(Boolean);
  c.body.append(h("div", { class: "tbl-wrap" }, h("table", { class: "data" },
    h("thead", {}, h("tr", {}, head.map((t, i) => h("th", { class: i ? "n" : null }, t)))), h("tbody", {}, rows))));

  const t = link.timing;
  const dirWord = t.direction === "down" ? "下跌" : "上漲";
  const tile = (title, d, note) => h("div", { class: "kpi" },
    h("div", { class: "k-name" }, title),
    h("div", { class: "k-val" }, fin(d.median) ? chUnit(d.median, link.unit) : "—"),
    h("div", { class: "k-d" }, h("span", {}, h("span", { class: "muted" }, "上漲比例 "), fin(d.hit) ? `${d.hit.toFixed(0)}%` : "—"),
      h("span", {}, h("span", { class: "muted" }, "n "), d.n || 0)),
    h("div", { class: "k-asof" }, note));
  c.body.append(h("h4", { class: "sub-h" }, `先行 vs 追價：事件當下，下游自己前 3 個月${dirWord}了沒（比較之後 3 個月）`),
    h("div", { class: "kpis" },
      tile("下游還沒反應時進場", t.not_yet, `前 3 個月還沒${dirWord}`),
      tile("下游已經反應後進場", t.already, `前 3 個月已經${dirWord}`)));

  const host = h("div", { class: "chart" });
  c.body.append(h("h4", { class: "sub-h" }, "反應時程：事件後每個月的平均變動"), host);
  mount(host, () => profileChart(host, link.profile, link.unit));
  return c.el;
}

function chainCard(chain, selLink, onPick) {
  const c = card({ title: chain.name, span: 12, sub: chain.thesis,
    note: `目前 ${chain.active.count}/${chain.active.of} 層成立。點箭頭看該段的完整統計。` });
  const flow = h("div", { class: "chain-flow" });
  chain.nodes.forEach((n, i) => {
    flow.append(h("div", { class: `chain-node${n.triggered ? " on" : ""}`, title: n.why },
      h("div", { class: "cn-step" }, `第 ${i + 1} 層${n.triggered ? "・成立中" : ""}`),
      h("div", { class: "cn-name" }, n.name),
      h("div", { class: "cn-cond" }, n.label),
      h("div", { class: "cn-now" }, `目前 ${fin(n.current) ? fmtNum(n.current, 2) : "—"}${n.kind === "yield" && n.op !== "level" ? " bp" : n.op === "level" ? "" : "%"}`,
        h("span", { class: "muted" }, `・${n.current_at || "—"}`)),
      h("div", { class: "cn-hist muted" }, `歷史 ${n.episodes} 次事件`)));
    const link = chain.links[i];
    if (link) {
      const b = h("button", { class: `chain-arrow${selLink === i ? " sel" : ""}`, type: "button", "aria-pressed": String(selLink === i),
        title: `${link.verdict}：機率 ${link.prob}% vs 平常 ${link.prob_base}%` },
        h("div", { class: "ca-prob" }, fin(link.prob) ? `${link.prob.toFixed(0)}%` : "—"),
        h("div", { class: "ca-base muted" }, `平常 ${fin(link.prob_base) ? link.prob_base.toFixed(0) + "%" : "—"}`),
        h("div", { class: `ca-verdict ${chVerdictTone(link.verdict)}` }, link.verdict.replace("與平常沒有明顯差別", "無差別").replace("傳導與報酬都顯著", "傳導＋報酬")),
        h("div", { class: "ca-wait muted" }, fin(link.wait_median) ? `約 ${link.wait_median} 個月` : ""));
      b.addEventListener("click", () => onPick(i));
      flow.append(b);
    }
  });
  c.body.append(flow);

  const f = chain.full;
  const fh = f.horizons[String(A.chains.horizons[2] || 6)];
  c.body.append(h("h4", { class: "sub-h" }, "全鏈同時成立"),
    h("p", { class: "note", style: "margin:0" },
      f.episodes
        ? `1995 年以來只有 ${f.months} 個月、合併為 ${f.episodes} 次（${f.dates.join("、")}）。末端標的其後 6 個月中位數 ${chUnit(fh.event.median, "%")}，平常 ${chUnit(fh.base.median, "%")}。${f.episodes < 5 ? "樣本太少，只能當歷史紀錄看，不足以推論。" : ""}`
        : "1995 年以來沒有出現過所有層同時成立。"));
  if (chain.recent.length) {
    c.body.append(h("h4", { class: "sub-h" }, "第一層最近幾次事件與末端標的其後 6 個月"),
      h("div", { class: "chips" }, chain.recent.map((r) => h("span", { class: `pill pill-${r.outcome >= 0 ? "up" : "down"}` },
        `${r.at}　${chUnit(r.outcome, "%")}`))));
  }
  return c.el;
}

TABS.chains = (root) => {
  const CH = A.chains;
  root.replaceChildren(tabHead("傳導鏈：一個事件推到第三、四層",
    "先寫下經濟學上的假說（例如「日債殖利率上行 → 日圓升值 → 美股下跌 → 費半 → 台股」），再用 1995 年以來的月資料逐段檢定：下游條件多久跟著成立、機率比平常高多少、下游標的之後的報酬分布與最大逆行。這些是歷史統計，不是預測，也沒有做樣本外交易驗證。", false));
  if (!CH || !CH.items.length) { root.append(h("p", { class: "empty" }, "尚未產生傳導鏈分析，請執行 python3 gfd.py analyze")); return; }
  const g = h("div", { class: "grid" });
  root.append(g);

  const f = findingsCard("chains", "目前成立中的層");
  if (f) g.append(f);

  // 整體結論：由資料統計出來，不是寫死的
  const links = CH.items.flatMap((c) => c.links.map((l) => ({ chain: c, l })));
  const transmit = links.filter((x) => (x.l.prob_lift || 0) >= 10);
  const sig = links.filter((x) => x.l.verdict.includes("報酬") && x.l.verdict.includes("顯著"));
  const timing = CH.items.flatMap((c) => c.summary.timing.map((t) => ({ chain: c.name, ...t })));
  const early = timing.filter((t) => t.better === "尚未反應時進場");
  const sc = card({ title: "整段研究的結論", span: 12, sub: "以下數字每次重算分析時更新。" });
  sc.body.append(h("ul", { class: "finds" },
    h("li", { class: "t-neutral" }, h("b", {}, `傳導本身大多成立：${links.length} 段裡有 ${transmit.length} 段，下游條件跟著出現的機率比平常高 10 個百分點以上`),
      h("span", {}, "最強的幾段：" + transmit.slice().sort((a, b) => b.l.prob_lift - a.l.prob_lift).slice(0, 4)
        .map((x) => `${x.chain.nodes.find((n) => n.id === x.l.from_).name}→${x.chain.nodes.find((n) => n.id === x.l.to).name} ${x.l.prob}%（平常 ${x.l.prob_base}%）`).join("；") + "。")),
    h("li", { class: sig.length ? "t-up" : "t-alert" }, h("b", {}, `但「跟著發生」不等於「能賺錢」：只有 ${sig.length} 段的報酬在統計上站得住（p ≤ 0.05 且事件數 ≥ 10）`),
      h("span", {}, sig.length
        ? sig.map((x) => `${x.chain.name}：${x.chain.nodes.find((n) => n.id === x.l.from_).name}→${x.chain.nodes.find((n) => n.id === x.l.to).name}`).join("；") + "。其餘各段的事件後報酬與平常沒有明顯差別。"
        : "其餘各段都與平常沒有明顯差別。")),
    h("li", { class: "t-alert" }, h("b", {}, `「見報就是出場點」不是普世規則：${timing.length} 段可比較的連結中，${early.length} 段是「下游還沒反應時進場」較好`),
      h("span", {}, "方向大致是：恐慌與下跌鏈偏反轉（要趁下游還沒跌時進場），景氣與上漲鏈偏動能（等下游確認了再進場反而較好）。兩邊的事件數都不多，請看各段的 n。"))));
  g.append(sc.el);

  let sel = store.get("chainSel", CH.items[0].id);
  let selLink = 0;
  const chips = h("div", { class: "chips" });
  const body = h("div", { class: "grid", style: "margin-top:16px" });
  const draw = () => {
    if (!CH.items.some((c) => c.id === sel)) sel = CH.items[0].id;
    chips.replaceChildren(h("span", { class: "lab" }, "選鏈"), ...CH.items.map((c) => h("button", {
      class: "chip", type: "button", "aria-pressed": String(c.id === sel),
      onclick: () => { sel = c.id; selLink = 0; store.set("chainSel", sel); draw(); },
    }, `${c.name}（${c.active.count}/${c.active.of}）`)));
    const chain = CH.items.find((c) => c.id === sel);
    selLink = Math.min(selLink, Math.max(0, chain.links.length - 1));
    body.replaceChildren(chainCard(chain, selLink, (i) => { selLink = i; draw(); }),
      chain.links[selLink] ? chainLinkDetail(chain, chain.links[selLink]) : null);
  };
  const holder = card({ title: "逐鏈檢視", span: 12, sub: "每條鏈是一個假說；箭頭上的數字是下游條件在 " + CH.within + " 個月內跟著成立的機率。" });
  holder.tools.append(chips);
  g.append(holder.el);
  root.append(body);
  draw();
};
