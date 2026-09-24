"""訊號劇本：每個事件的前兆，以及事件後全資產的期望值排行。

期望值＝事件後報酬中位數「減掉該資產自己的無條件基準」。黃金、美股這種長期上漲的資產，
不扣掉基準會一路排在前面，那不是訊號帶來的，是本來就會漲。

要被標成「穩健」必須同時通過三關：獨立事件數 ≥ 8、2012 年前後兩段同方向、
循環位移檢定 p ≤ 0.10。通不過就照實標示，不排進建議名單。全部是樣本內歷史統計，
沒有計入交易成本、滑價與稅，也不是投資建議。
"""
import numpy as np

from . import chains as CH
from . import config as C

ITERS = 1000
SEED = 20260924
PRE_ASSETS = ["eq_spx", "eq_sox", "eq_twii", "eq_hsi", "b_hy", "b_ust_long",
              "c_gold", "c_copper", "c_brent", "fx_dxy", "v_vix"]


def _triggers(series):
    seen, out = set(), []
    for chain in C.CHAINS:
        for nd in chain["nodes"]:
            key = (nd["sid"], nd["op"], nd["cmp"], nd["thr"])
            if key in seen or nd["sid"] not in series:
                continue
            seen.add(key)
            out.append(dict(id=f"{chain['id']}_{nd['id']}", sid=nd["sid"], op=nd["op"], cmp=nd["cmp"],
                            thr=nd["thr"], label=nd["label"], why=nd["why"], source=chain["name"]))
    for nd in C.PLAYBOOK_EXTRA_TRIGGERS:
        key = (nd["sid"], nd["op"], nd["cmp"], nd["thr"])
        if key in seen or nd["sid"] not in series:
            continue
        seen.add(key)
        out.append(dict(id=nd["id"], sid=nd["sid"], op=nd["op"], cmp=nd["cmp"], thr=nd["thr"],
                        label=nd["label"], why=nd["why"], source="補充訊號"))
    return out


def _forward_matrix(g, series, assets, h):
    cols = []
    for sid in assets:
        kind = series[sid]["kind"]
        cols.append(CH.forward(g, sid, h, kind))
    return np.vstack(cols).T          # (months, assets)


def _shift_pvalues(mask, F, end, iters=ITERS, seed=SEED):
    """整段事件序列循環位移，一次算出所有資產的雙尾 p 值。"""
    n = end + 1
    m = mask[:n]
    F = F[:n]
    valid = np.isfinite(F)
    Fz = np.where(valid, F, 0.0)
    obs_cnt = (m[:, None] & valid).sum(axis=0)
    obs_sum = (m[:, None] * Fz).sum(axis=0)
    obs = np.where(obs_cnt >= 3, obs_sum / np.maximum(obs_cnt, 1), np.nan)
    rng = np.random.default_rng(seed)
    shifts = rng.integers(1, n, size=iters)
    M = np.stack([np.roll(m, int(s)) for s in shifts]).astype(float)   # (iters, months)
    cnt = M @ valid.astype(float)
    tot = M @ Fz
    means = np.where(cnt >= 3, tot / np.maximum(cnt, 1), np.nan)
    with np.errstate(invalid="ignore"):
        ge = np.nansum(means >= obs, axis=0)
        le = np.nansum(means <= obs, axis=0)
        usable = np.sum(np.isfinite(means), axis=0)
    p = 2 * np.minimum((ge + 1) / (usable + 1), (le + 1) / (usable + 1))
    return np.where(np.isfinite(obs) & (usable > 50), np.minimum(p, 1.0), np.nan)


def _asset_row(sid, series, starts, F, col, end, split_idx, p):
    kind = series[sid]["kind"]
    unit = "bp" if kind == "yield" else "%"
    ev = CH.dist([F[t, col] for t in starts])
    base = CH.dist(F[:end + 1, col])
    if not ev.get("n") or not base.get("n"):
        return None
    early = [F[t, col] for t in starts if t < split_idx and np.isfinite(F[t, col])]
    late = [F[t, col] for t in starts if t >= split_idx and np.isfinite(F[t, col])]
    med_early = float(np.median(early)) if early else None
    med_late = float(np.median(late)) if late else None
    lift = ev["median"] - base["median"]
    agree = (med_early is not None and med_late is not None
             and len(early) >= 2 and len(late) >= 2 and np.sign(med_early) == np.sign(med_late)
             and np.sign(med_early) == np.sign(lift))
    big = abs(lift) >= (10.0 if unit == "bp" else 1.0)
    return dict(sid=sid, name=series[sid]["name"], unit=unit, n=ev["n"], big=bool(big), robust=False,
                investable=sid not in C.PLAYBOOK_OBSERVE_ONLY,
                median=ev["median"], base=base["median"], lift=CH.r(lift), hit=ev["hit"],
                worst=ev["worst"], p10=ev["p10"], p=CH.r(float(p), 3) if p is not None and np.isfinite(p) else None,
                early=CH.r(med_early), late=CH.r(med_late), agree=bool(agree))


def build(g, series, months, log=print):
    end = g.end
    split_idx = next((i for i, m in enumerate(months) if m >= C.PLAYBOOK_SPLIT), len(months) // 2)
    assets = [sid for sid in C.PLAYBOOK_UNIVERSE if sid in series and sid in g.arr]
    trig = _triggers(series)

    # 先把每個事件的觸發遮罩與獨立事件起點算好
    info = []
    for t in trig:
        kind = series[t["sid"]]["kind"]
        vals = CH.transform(g, t["sid"], t["op"], kind)
        mask = CH.trigger_mask(vals, t["cmp"], t["thr"], end)
        starts = CH.episodes(mask)
        fin = np.where(np.isfinite(vals[:end + 1]))[0]
        cur = int(fin[-1]) if fin.size else None
        info.append(dict(t=t, mask=mask, starts=starts, vals=vals, kind=kind,
                         current=CH.r(vals[cur]) if cur is not None else None,
                         current_at=months[cur] if cur is not None else None,
                         active=bool(mask[cur]) if cur is not None else False))

    # 事件後全資產表現
    fmats = {h: _forward_matrix(g, series, assets, h) for h in C.PLAYBOOK_HORIZONS}
    out, robust_all, all_cells = [], [], []
    for rec in info:
        t, starts = rec["t"], rec["starts"]
        if len(starts) < 3:
            continue
        ep_mask = np.zeros(len(months), bool)
        ep_mask[starts] = True
        per_h = {}
        for h in C.PLAYBOOK_HORIZONS:
            F = fmats[h]
            pvals = _shift_pvalues(ep_mask, F, end)
            rows = []
            for col, sid in enumerate(assets):
                row = _asset_row(sid, series, starts, F, col, end, split_idx, pvals[col])
                if row:
                    rows.append(row)
            for r in rows:
                r["horizon"] = h
            rows.sort(key=lambda r: (r["lift"] if r["lift"] is not None else -999), reverse=True)
            per_h[str(h)] = dict(top=rows[:C.PLAYBOOK_TOP], bottom=rows[-3:][::-1], robust=[])
            for r in rows:
                all_cells.append((t, h, r))

        # 事件前 3 個月，哪些資產已經先動了
        pre = []
        for sid in PRE_ASSETS:
            if sid not in g.arr:
                continue
            kind = series[sid]["kind"]
            ch3 = CH.transform(g, sid, "chg3", kind)
            ev = CH.dist([ch3[t2] for t2 in starts])
            base = CH.dist(ch3[:end + 1])
            if ev.get("n") and base.get("n"):
                pre.append(dict(sid=sid, name=series[sid]["name"], unit="bp" if kind == "yield" else "%",
                                event=ev["median"], base=base["median"],
                                diff=CH.r(ev["median"] - base["median"]), n=ev["n"]))
        pre.sort(key=lambda x: abs(x["diff"] or 0), reverse=True)

        # 前兆：哪些訊號常在這個事件之前出現（要同時看命中率與誤報）
        W = C.CHAIN_WITHIN
        target = rec["mask"]
        base_rate = float(np.mean([target[i + 1:i + 1 + W].any() for i in range(end - W + 1)])) * 100
        precursors = []
        for other in info:
            if other["t"]["id"] == t["id"] or not other["starts"]:
                continue
            hits = [target[i + 1:i + 1 + W].any() for i in other["starts"] if i + W <= end]
            if len(hits) < 5:
                continue
            precision = float(np.mean(hits)) * 100
            covered = 0
            leads = []
            for s in starts:
                back = other["mask"][max(0, s - W):s]
                if back.any():
                    covered += 1
                    leads.append(s - (max(0, s - W) + int(np.where(back)[0][-1])))
            recall = 100.0 * covered / len(starts) if starts else 0
            precursors.append(dict(id=other["t"]["id"], label=other["t"]["label"], source=other["t"]["source"],
                                   precision=CH.r(precision, 0), base=CH.r(base_rate, 0),
                                   lift=CH.r(precision - base_rate, 0), recall=CH.r(recall, 0),
                                   lead=CH.r(float(np.median(leads)), 1) if leads else None, n=len(hits)))
        precursors = [p for p in precursors if (p["lift"] or 0) >= 10 and (p["recall"] or 0) >= 20]
        precursors.sort(key=lambda x: (x["lift"], x["recall"]), reverse=True)

        out.append(dict(id=t["id"], label=t["label"], why=t["why"], source=t["source"], sid=t["sid"],
                        name=series[t["sid"]]["name"], op=t["op"], cmp=t["cmp"], thr=t["thr"],
                        episodes=len(starts), dates=[months[s] for s in starts][-8:],
                        active=rec["active"], current=rec["current"], current_at=rec["current_at"],
                        base_rate=CH.r(base_rate, 0), precursors=precursors[:6], pre=pre[:8],
                        assets=per_h, robust_count=sum(len(per_h[str(h)]["robust"]) for h in C.PLAYBOOK_HORIZONS)))

    # ── 多重檢定：估計偽發現率，而不是用 BH ──
    # 循環位移最多只有 n 種位移（這裡約 381），p 值有下限（約 0.005），
    # BH 在 3,500 次檢定下會要求 p < 0.00003，那是這個檢定做不到的精度，
    # 用 BH 會把「精度不足」誤報成「完全沒訊號」。改成直接估偽發現率：
    # 在完全沒有訊號時，p ≤ 閾值的比例就等於閾值，乘上檢定數即為運氣預期值。
    tested = [(t, h, r) for t, h, r in all_cells
              if r["p"] is not None and r["n"] >= C.PLAYBOOK_MIN_EPISODES]
    M = len(tested)
    buckets = []
    for thr in (0.10, 0.05, 0.02):
        obs = sum(1 for _t, _h, r in tested if r["p"] <= thr)
        obs_agree = sum(1 for _t, _h, r in tested if r["p"] <= thr and r["agree"] and r["big"])
        exp = M * thr
        buckets.append(dict(p=thr, observed=obs, expected=round(exp),
                            fdr=CH.r(min(1.0, exp / obs) * 100, 0) if obs else None,
                            with_filters=obs_agree,
                            fdr_filtered=CH.r(min(1.0, exp * 0.5 / obs_agree) * 100, 0) if obs_agree else None))
    strict = C.PLAYBOOK_STRICT_P
    for _t, _h, r in tested:
        r["robust"] = bool(r["p"] <= strict and r["agree"] and r["big"])
    for rec in out:
        for h in C.PLAYBOOK_HORIZONS:
            blk = rec["assets"][str(h)]
            blk["robust"] = [r for r in blk["top"] + blk["bottom"] if r.get("robust")]
        rec["robust_count"] = sum(len(rec["assets"][str(h)]["robust"]) for h in C.PLAYBOOK_HORIZONS)
    for t, h, r in tested:
        if r["robust"]:
            robust_all.append(dict(trigger=t["id"], trigger_label=t["label"], **r))
    robust_all.sort(key=lambda r: abs(r["lift"]), reverse=True)
    strict_bucket = next(b for b in buckets if b["p"] == strict)
    stats = dict(tested=M, buckets=buckets, strict_p=strict, p_floor=CH.r(2 / (end + 2), 4),
                 robust=len(robust_all), robust_investable=sum(1 for r in robust_all if r["investable"]),
                 expected_by_chance=strict_bucket["expected"],
                 fdr_estimate=strict_bucket["fdr_filtered"],
                 note=(f"共檢定 {M} 組（訊號×資產×期間）。位移檢定的 p 值有下限（約 {2 / (end + 2):.3f}），"
                       f"因此不用 BH（會因精度不足把一切判成無效），改以「運氣預期值 ÷ 實際通過數」估偽發現率。"
                       f"最嚴格一格 p ≤ {strict}：實際 {strict_bucket['observed']} 組、運氣預期約 "
                       f"{strict_bucket['expected']} 組；再加上前後半期同方向與幅度門檻後剩 "
                       f"{strict_bucket['with_filters']} 組，估計仍有約 {strict_bucket['fdr_filtered']}% 是運氣。"))
    log(f"[playbook] 可投資標的中穩健 {sum(1 for r in robust_all if r['investable'])} 組、"
        f"觀察指標 {sum(1 for r in robust_all if not r['investable'])} 組")
    log(f"[playbook] {len(out)} 個訊號、{len(assets)} 個資產；檢定 {M} 組；"
        + "；".join(f"p≤{b['p']} 實際 {b['observed']}／運氣 {b['expected']}" for b in buckets)
        + f"；最終穩健 {len(robust_all)} 組（估計偽發現率 {strict_bucket['fdr_filtered']}%）")
    inv = [r for r in robust_all if r["investable"]]
    obs = [r for r in robust_all if not r["investable"]]
    return dict(triggers=out, assets=assets,
                robust=inv[:60], robust_observe=obs[:30], split=C.PLAYBOOK_SPLIT,
                min_episodes=C.PLAYBOOK_MIN_EPISODES, max_p=C.PLAYBOOK_MAX_P, horizons=C.PLAYBOOK_HORIZONS,
                iters=ITERS, stats=stats, max_p_strict_label=str(C.PLAYBOOK_STRICT_P),
                note="期望值為相對該資產無條件基準的超額中位數；穩健＝事件數 ≥ 8、2012 年前後同方向、"
                     f"超額幅度夠大、且位移檢定 p ≤ {C.PLAYBOOK_STRICT_P}。即使如此仍有估計比例是運氣，"
                     "資產之間彼此相關會讓實際偽發現率更高。")
