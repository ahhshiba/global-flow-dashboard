"""沙盤推演：把傳導鏈、訊號劇本、事件衝擊接起來，回答「現在這些訊號亮著，接下來可能怎麼走、哪些標的期望值較好」。

四步：
1. 現況：訊號劇本的觸發條件中，哪些現在亮著（同一套定義與「最新一筆資料」口徑，數字和訊號劇本分頁一致）。
2. 推演：每條傳導鏈從目前成立的層往下看，還沒成立的下一層在 6 個月內跟著成立的歷史機率（對照平常）。
3. 期望值：每個可投資標的的「之後 h 個月報酬減掉自己平常的平均」，對全部訊號的 0/1 指標做 ridge 迴歸
   （λ 事先設定，不看樣本外結果挑）。同時亮著、彼此重疊的訊號會分攤效果，不重複計算；目前亮燈訊號的係數加總＝模型期望超額。
   區間用 12 個月一塊的區塊自助法。
4. 樣本外檢查：走步回測，每個月只用當時已經知道結果的資料估計，買期望值最高的幾個，和全體平均比；
   同時量「校準斜率」＝樣本外實際超額大約是模型值的幾倍，頁面上的「校準後」就是模型值乘上它。

原因說明不用 ridge 係數（同時亮著的訊號會互相分攤，單看係數會出現「日圓升值讓原油漲」這種看不出道理的拆法），
改列每個亮燈訊號「單獨」的歷史：用訊號劇本同一套口徑（獨立事件起點、事件後中位數減平常中位數、位移檢定 p），
兩個分頁的數字可以互相對照。

限制（頁面上照實寫）：訊號與門檻是事後設計的，回測只排除了「估計」上的偷看，排除不了「設計」上的後見之明；
另外比較過不只一種組合方式，挑選本身也是偷看，實際效果可能比回測差。報酬是對數報酬、沒有交易成本與稅；
全部是歷史統計，不是投資建議。
"""
import numpy as np

from . import chains as CH
from . import config as C
from . import playbook as PB

BLOCK = 12          # 區塊自助法的區塊長度（月）
PERM = 500          # 置換檢定次數
SIMILAR_TOP = 5     # 列出最像現在的幾個歷史時點
SEED = 20261002


def _key(nd):
    return (nd["sid"], nd["op"], nd["cmp"], nd["thr"])


def _masks(g, series, trig, end):
    out = []
    for t in trig:
        vals = CH.transform(g, t["sid"], t["op"], series[t["sid"]]["kind"])
        out.append(CH.trigger_mask(vals, t["cmp"], t["thr"], end))
    return np.array(out).T            # (months, K) bool


def _run_length(mask, cur):
    """目前這一段已經連續亮了幾個月（含當月）。"""
    n = 0
    while cur - n >= 0 and mask[cur - n]:
        n += 1
    return n


def _ridge(Xr, yr, lam):
    mu = float(yr.mean())
    K = Xr.shape[1]
    beta = np.linalg.solve(Xr.T @ Xr + lam * np.eye(K), Xr.T @ (yr - mu))
    return mu, beta


def _spread(preds, real, k):
    top = np.argsort(-preds)[:k]
    return float(real[top].mean() - real.mean())


def _walk_forward(X, F, Mom, h, end, start, lam, k):
    """每個決策月 T 只用 t ≤ T−h（結果已知）的資料；用累加和，不必每期重算。

    同時算三種排名做對照：ridge（本頁採用）、單一訊號平均（每個亮燈訊號單獨的條件超額、收縮後取平均）、6 個月動能。
    """
    n, A = F.shape
    K = X.shape[1]
    Xf = X.astype(float)
    pr = np.full((n, A), np.nan)
    pa = np.full((n, A), np.nan)
    mus = np.full((n, A), np.nan)
    for a in range(A):
        y = F[:, a]
        v = np.isfinite(y)
        v[end - h + 1:] = False
        yz = np.where(v, y, 0.0)
        xv = Xf * v[:, None]
        Sxx = np.cumsum(xv[:, :, None] * Xf[:, None, :], axis=0)
        Sxy = np.cumsum(xv * yz[:, None], axis=0)
        Sx = np.cumsum(xv, axis=0)
        Sy = np.cumsum(yz)
        Sn = np.cumsum(v.astype(float))
        for T in range(start, end - h + 1):
            i = T - h
            if Sn[i] < 60 or not np.isfinite(F[T, a]):
                continue
            mu = Sy[i] / Sn[i]
            b = Sxy[i] - mu * Sx[i]                     # Σ x·(y − μ)
            pr[T, a] = Xf[T] @ np.linalg.solve(Sxx[i] + lam * np.eye(K), b)
            act = Xf[T] > 0
            pa[T, a] = float(np.mean(b[act] / (Sx[i][act] + lam))) if act.any() else 0.0
            mus[T, a] = mu
    periods = []
    for T in range(start, end - h + 1):
        ok = np.isfinite(pr[T]) & np.isfinite(F[T])
        if ok.sum() < 10:
            continue
        r = F[T, ok]
        mom = np.where(np.isfinite(Mom[T, ok]), Mom[T, ok], 0.0)
        periods.append(dict(T=T, real=r, pr=pr[T, ok], pa=pa[T, ok], own=r - mus[T, ok],
                            ridge=_spread(pr[T, ok], r, k), avg=_spread(pa[T, ok], r, k), mom=_spread(mom, r, k)))
    return periods


def _offsets(periods, h, key, rng, with_p=True):
    """重疊的期間不能當獨立樣本：每 h 個月取一期（不重疊），每個起點各算一次，再看範圍。"""
    rows = []
    for off in range(h):
        sub = periods[off::h]
        if len(sub) < 8:
            continue
        s = np.array([p[key] for p in sub])
        pval = None
        if with_p:
            k = C.SCENARIO_TOPK
            null = [np.mean([float(p["real"][rng.permutation(len(p["real"]))[:k]].mean() - p["real"].mean()) for p in sub])
                    for _ in range(PERM)]
            pval = float((np.sum(np.array(null) >= s.mean()) + 1) / (PERM + 1))
        rows.append(dict(offset=off, n=len(sub), mean=CH.r(s.mean()), hit=CH.r(100 * (s > 0).mean(), 0), p=CH.r(pval, 3)))
    return rows


def _verdict(rows):
    if not rows:
        return "樣本不足"
    means = [r["mean"] for r in rows if r["mean"] is not None]
    ps = [r["p"] for r in rows if r["p"] is not None]
    if all(m > 0 for m in means) and ps and max(ps) <= 0.10:
        return "樣本外有效"
    if np.mean(means) > 0 and sum(m > 0 for m in means) > len(means) / 2:
        return "時好時壞"
    return "樣本外無效"


def _summ(periods, key):
    s = np.array([p[key] for p in periods])
    return dict(mean=CH.r(s.mean()) if s.size else None, hit=CH.r(100 * (s > 0).mean(), 0) if s.size else None)


def build(g, series, months, play, chain_block, cascade, log=print):
    end = g.end
    lam = C.SCENARIO_LAMBDA
    trig = PB._triggers(series)
    ids = [t["id"] for t in trig]
    pmap = {t["id"]: t for t in play["triggers"]}
    X = _masks(g, series, trig, end)
    K = len(trig)
    # 目前亮燈：直接用訊號劇本的判定（各序列最新一筆），兩個分頁的數字才會一致
    x_now = np.array([1.0 if pmap.get(i, {}).get("active") else 0.0 for i in ids])
    act_k = [k for k in range(K) if x_now[k]]
    active = []
    for k in act_k:
        t, p = trig[k], pmap[trig[k]["id"]]
        cur = months.index(p["current_at"]) if p.get("current_at") in months else end
        active.append(dict(id=t["id"], label=t["label"], source=t["source"], why=t["why"], sid=t["sid"],
                           current=p.get("current"), current_at=p.get("current_at"),
                           run=_run_length(X[:, k], cur), episodes=p.get("episodes")))
    active_ids = {a["id"] for a in active}
    assets = [s for s in C.PLAYBOOK_UNIVERSE if s in g.arr and s in series and s not in C.PLAYBOOK_OBSERVE_ONLY]
    start = months.index(C.SCENARIO_EVAL_START) if C.SCENARIO_EVAL_START in months else 120
    rng = np.random.default_rng(SEED)
    robust = play.get("robust", [])

    # 最像現在的歷史時點：亮燈組合的 Jaccard 相似度（每段只取最像的一個月，前後至少隔 6 個月）
    Xa = X.astype(float)
    inter = Xa @ x_now
    union = Xa.sum(axis=1) + x_now.sum() - inter
    with np.errstate(invalid="ignore", divide="ignore"):
        jac = np.where(union > 0, inter / union, 0.0)
    jac[end - max(C.PLAYBOOK_HORIZONS) + 1:] = 0     # 只列結果已經知道的時點（排除最近一年，那就是「現在」本身）
    similar, taken = [], []
    for t in np.argsort(-jac):
        if jac[t] <= 0 or len(similar) >= SIMILAR_TOP:
            break
        if any(abs(int(t) - u) < 6 for u in taken):
            continue
        taken.append(int(t))
        similar.append(dict(m=months[t], t=int(t), jaccard=CH.r(jac[t]),
                            shared=[trig[k]["label"] for k in act_k if X[t, k]]))

    # 事件衝擊：亮燈訊號 → 事件類型 → 各標的短期反應（日線事件研究）
    cats = {c["id"]: c for c in (cascade or {}).get("categories", [])}
    ev_types, by_sid_events = [], {}
    pmin = lambda r: min(r["p21"] if r["p21"] is not None else 1, r["p42"] if r["p42"] is not None else 1)
    for cat_id in sorted({c for a in active for c in C.SCENARIO_EVENT_TYPES.get(a["id"], [])}):
        cat = cats.get(cat_id)
        if not cat:
            continue
        rows = []
        for a in cat.get("assets", []):
            sid = C.SCENARIO_CASCADE_SID.get(a["id"])
            if not sid:
                continue
            row = dict(sid=sid, name=series.get(sid, {}).get("name", a["name"]), n=a.get("n"), half_day=a.get("half_day"),
                       excess21=a.get("excess21"), p21=a.get("p21"), agree21=a.get("agree21"),
                       excess42=a.get("excess42"), p42=a.get("p42"), agree42=a.get("agree42"), resp_rate=a.get("resp_rate"))
            rows.append(row)
            by_sid_events.setdefault(sid, []).append(dict(cat=cat_id, cat_name=cat["name"], **row))
        sig = sorted([r for r in rows if pmin(r) <= 0.10], key=pmin)
        recent = sorted([e for e in cascade["events"] if e["cat"] == cat_id], key=lambda e: e["date"])[-3:]
        ev_types.append(dict(id=cat_id, name=cat["name"], n=cat.get("n"),
                             from_=[a["label"] for a in active if cat_id in C.SCENARIO_EVENT_TYPES.get(a["id"], [])],
                             rows=sig[:8], recent=[dict(id=e["id"], name=e["name"], date=e["date"]) for e in recent]))

    # 期望值、原因、樣本外回測
    out_h, backtest = {}, {}
    for h in C.PLAYBOOK_HORIZONS:
        F = np.vstack([CH.forward(g, s, h, series[s]["kind"]) for s in assets]).T
        Mom = np.vstack([CH.transform(g, s, "chg6", series[s]["kind"]) for s in assets]).T
        periods = _walk_forward(X, F, Mom, h, end, start, lam, C.SCENARIO_TOPK)
        offs = _offsets(periods, h, "ridge", rng)
        verdict = _verdict(offs)
        cal = np.array([(p_, o_) for p in periods for p_, o_ in zip(p["pr"], p["own"])])
        slope = float(cal[:, 0] @ cal[:, 1] / (cal[:, 0] @ cal[:, 0])) if cal.size else None
        corr = float(np.corrcoef(cal[:, 0], cal[:, 1])[0, 1]) if cal.size else None
        use_cal = slope is not None and slope > 0 and verdict != "樣本外無效"
        backtest[str(h)] = dict(
            periods=len(periods), start=months[periods[0]["T"]] if periods else None,
            end=months[periods[-1]["T"]] if periods else None,
            ridge=dict(**_summ(periods, "ridge"), offsets=offs, verdict=verdict),
            avg=dict(**_summ(periods, "avg"), offsets=_offsets(periods, h, "avg", rng)),
            momentum=dict(**_summ(periods, "mom"), offsets=_offsets(periods, h, "mom", rng)),
            calibration=dict(slope=CH.r(slope), corr=CH.r(corr, 3), used=bool(use_cal)),
            series=[dict(m=months[p["T"]], v=CH.r(p["ridge"])) for p in periods])
        b_avg = backtest[str(h)]["avg"]
        b_avg["verdict"] = _verdict(b_avg["offsets"])
        backtest[str(h)]["momentum"]["verdict"] = _verdict(backtest[str(h)]["momentum"]["offsets"])

        # 每個亮燈訊號單獨的歷史（訊號劇本同一套口徑），給「原因」用
        rows_all = np.arange(0, end - h + 1)
        uni = {}
        for k in act_k:
            starts = CH.episodes(X[:, k])
            ep_mask = np.zeros(len(months), bool)
            ep_mask[starts] = True
            pv = PB._shift_pvalues(ep_mask, F, end)
            uni[k] = (starts, pv)

        recs = []
        for a, sid in enumerate(assets):
            y = F[rows_all, a]
            ok = np.isfinite(y)
            if ok.sum() < 60:
                continue
            Xr = X[rows_all][ok].astype(float)
            yr = y[ok]
            mu, beta = _ridge(Xr, yr, lam)
            ev = float(x_now @ beta)
            # 區塊自助法：整塊 12 個月一起抽，保留報酬的自相關
            N = len(yr)
            nb = int(np.ceil(N / BLOCK))
            boots = []
            for _ in range(C.SCENARIO_BOOT):
                st = rng.integers(0, max(1, N - BLOCK), size=nb)
                pos = np.concatenate([np.arange(b0, b0 + BLOCK) for b0 in st])[:N]
                boots.append(float(x_now @ _ridge(Xr[pos], yr[pos], lam)[1]))
            boots = np.array(boots)
            base_med = float(np.median(yr))
            evidence = []
            for k in act_k:
                starts, pv = uni[k]
                vals = [F[t, a] for t in starts if t <= end - h and np.isfinite(F[t, a])]
                if not vals:
                    continue
                lift = float(np.median(vals)) - base_med
                evidence.append(dict(id=ids[k], label=trig[k]["label"], source=trig[k]["source"], why=trig[k]["why"],
                                     n=len(vals), lift=CH.r(lift), hit=CH.r(100 * np.mean(np.array(vals) > base_med), 0),
                                     p=CH.r(float(pv[a]), 3) if np.isfinite(pv[a]) else None, beta=CH.r(beta[k])))
            evidence.sort(key=lambda e: abs(e["lift"] or 0), reverse=True)
            refs = [dict(trigger=r["trigger"], label=r["trigger_label"], lift=r["lift"], p=r["p"], n=r["n"],
                         conflict=bool(r.get("conflict")))
                    for r in robust if r["sid"] == sid and r["horizon"] == h and r["trigger"] in active_ids]
            past = [dict(m=s["m"], jaccard=s["jaccard"], own=CH.r(F[s["t"], a] - mu) if s["t"] <= end - h and np.isfinite(F[s["t"], a]) else None)
                    for s in similar]
            recs.append(dict(sid=sid, name=series[sid]["name"], ev=CH.r(ev), cal=CH.r(ev * slope) if use_cal else None,
                             base=CH.r(mu), lo=CH.r(np.percentile(boots, 10)), hi=CH.r(np.percentile(boots, 90)),
                             prob_pos=CH.r(100 * (boots > 0).mean(), 0), evidence=evidence, robust=refs,
                             events=by_sid_events.get(sid, []), past=past))
        recs.sort(key=lambda r: r["ev"], reverse=True)
        out_h[str(h)] = recs
        log(f"[scenario] {h} 個月：樣本外 {len(periods)} 期，前 {C.SCENARIO_TOPK} 名平均多 "
            f"{backtest[str(h)]['ridge']['mean']:+.2f}%（各起點 {[o['mean'] for o in offs]}，p {[o['p'] for o in offs]}）"
            f"→ {verdict}；校準斜率 {slope:.2f}；對照 單一訊號平均 {b_avg['mean']:+.2f}%、動能 {backtest[str(h)]['momentum']['mean']:+.2f}%")

    # 傳導鏈推演：從目前成立的層往下，還沒成立的層在 W 個月內跟著成立的機率
    W = C.CHAIN_WITHIN
    key_to_id = {_key(t): t["id"] for t in trig}
    items = {c["id"]: c for c in chain_block.get("items", [])}
    paths = []
    for chain in C.CHAINS:
        it = items.get(chain["id"])
        if not it or not it["active"]["count"]:
            continue
        cmasks, finite = [], []
        for nd in chain["nodes"]:
            vals = CH.transform(g, nd["sid"], nd["op"], series[nd["sid"]]["kind"])
            cmasks.append(CH.trigger_mask(vals, nd["cmp"], nd["thr"], end))
            finite.append(np.isfinite(vals))
        nodes = []
        for j, (nd, info) in enumerate(zip(chain["nodes"], it["nodes"])):
            tid = key_to_id.get(_key(nd))
            row = dict(id=nd["id"], sid=nd["sid"], label=nd["label"], name=info["name"], triggered=bool(info["triggered"]),
                       current=info["current"], current_at=info["current_at"], trigger=tid)
            ups = [i for i in range(j) if it["nodes"][i]["triggered"]]
            if not info["triggered"] and ups:
                i = ups[-1]
                up_t = [t for t in range(end - W + 1) if cmasks[i][t]]
                hits = [bool(cmasks[j][t + 1:t + 1 + W].any()) for t in up_t]
                base = [bool(cmasks[j][t + 1:t + 1 + W].any()) for t in range(end - W + 1) if finite[j][t]]
                waits = [int(np.argmax(cmasks[j][t + 1:t + 1 + W])) + 1 for t, hh in zip(up_t, hits) if hh]
                row.update(after=it["nodes"][i]["label"], prob=CH.r(100 * np.mean(hits), 0) if hits else None,
                           base=CH.r(100 * np.mean(base), 0) if base else None,
                           wait=CH.r(float(np.median(waits)), 1) if waits else None, n_months=len(hits),
                           n_episodes=len(CH.episodes(cmasks[i][:end - W + 1])))
                # 如果這一層也成立：訊號劇本裡這個訊號的穩健組合（可投資標的）
                row["if_then"] = [dict(name=r["name"], sid=r["sid"], lift=r["lift"], horizon=r["horizon"], p=r["p"])
                                  for r in robust if r["trigger"] == tid][:4]
            nodes.append(row)
        paths.append(dict(id=chain["id"], name=chain["name"], thesis=chain["thesis"], nodes=nodes,
                          active=it["active"]["count"], of=it["active"]["of"]))

    asof = max((a["current_at"] for a in active if a.get("current_at")), default=months[end])
    log(f"[scenario] 亮燈 {len(active)} 個訊號；最像現在的歷史時點 {[(s['m'], s['jaccard']) for s in similar]}；"
        f"{len(paths)} 條鏈有成立的層；{len(ev_types)} 個相關事件類型")
    return dict(asof=asof, active=active, horizons=C.PLAYBOOK_HORIZONS, assets=out_h, backtest=backtest,
                similar=[{k: v for k, v in s.items() if k != "t"} for s in similar],
                paths=paths, events=ev_types, within=W, event_luck=((cascade or {}).get("stats") or {}).get("fdr05"),
                model=dict(lam=lam, topk=C.SCENARIO_TOPK, eval_start=C.SCENARIO_EVAL_START, boot=C.SCENARIO_BOOT,
                           block=BLOCK, perm=PERM, triggers=K, assets=len(assets)))
