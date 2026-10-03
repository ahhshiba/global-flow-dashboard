"""確切標的、低基期、更詳細的推演（2026-10-03）。

回答三件事：
1. 確切標的：每個抽象資產（美長債、美元、半導體…）對應到可以買的 ETF／股票／現金部位（config.TARGETS），
   每檔現在在哪裡：最新價、1 年變動、離歷史高點與 3 年高點多遠、10 年位階、離 200 日均線多遠；
   還有它是不是真的在追蹤那個資產（月報酬相關，低於門檻就標出來）。
2. 低基期：位階低、離高點遠就算低基期（config.LOWBASE）。但低基期有沒有用不能用講的——
   把底層序列「當時往前 10 年的位階」分五段，看各段之後 6／12 個月的報酬；現在在哪一段、那一段過去怎樣。
3. 更詳細的推演：每個資產三個角度各自看 3／6／12 個月——
   模型（沙盤推演的 ridge，已校準）、相似時點（亮燈組合和現在重疊 ≥ SIM_THR 的月份之後實際怎樣：中位、10～90% 範圍、上漲比例、段數）、
   低基期（上面那段的歷史）；三個角度一致才算方向明確。另外每個「可能會發生的事」真的發生時通常多深、多久
   （幅度分布、等幾個月的分布）。

全部是歷史統計，不是投資建議。相似時點與低基期的段數通常只有十幾段。
"""
import datetime as dt

import numpy as np

from . import chains as CH
from . import config as C
from . import playbook as PB
from . import scenario as SC

EPOCH = dt.date(1970, 1, 1)
HORIZONS = [3, 6, 12]
MIN_TRACK = 0.5          # 月報酬相關低於這個就標「追蹤不佳」
VIEW_GAP = 2.0           # 相似時點／位階：典型值要比平常差 2 個百分點以上才算有方向
BUCKETS = ["最低 20%", "20～40%", "40～60%", "60～80%", "最高 20%"]


def _r(v, nd=1):
    return CH.r(v, nd)


def _pct_rank(x, v):
    x = x[np.isfinite(x)]
    return float(100 * (x < v).mean() + 50 * (x == v).mean()) if len(x) else None


def _ticker_status(d, g):
    """一檔標的現在在哪裡（用它自己的含息日線）。"""
    dates = np.array(d["dates"], dtype="datetime64[D]")
    px = np.array(d["closes"], float)
    ok = np.isfinite(px) & (px > 0)
    dates, px = dates[ok], px[ok]
    if len(px) < 250:
        return None
    last = px[-1]
    day = dates[-1]
    ago = lambda days: px[dates <= day - np.timedelta64(days, "D")]        # noqa: E731
    chg = lambda days: (last / ago(days)[-1] - 1) * 100 if len(ago(days)) else None      # noqa: E731
    w10 = px[dates > day - np.timedelta64(3652, "D")]
    w3 = px[dates > day - np.timedelta64(1096, "D")]
    ma200 = px[-200:].mean()
    return dict(last=_r(last, 2 if last < 100 else 1), date=str(day), first=str(dates[0]),
                c1y=_r(chg(365)), c3y=_r(chg(1096)),
                dd_ath=_r((last / px.max() - 1) * 100), ath_at=str(dates[int(np.argmax(px))]),
                dd_3y=_r((last / w3.max() - 1) * 100), pct10=_r(_pct_rank(w10, last), 0),
                years10=_r((dates[-1] - dates[dates > day - np.timedelta64(3652, "D")][0]).astype(int) / 365.25, 1),
                ma200=_r((last / ma200 - 1) * 100))


def _monthly(d, g):
    """標的日線 → 和 g.months 對齊的月底收盤（≤ g.end）。"""
    a = np.full(len(g.months), np.nan)
    for ds, v in zip(d["dates"], d["closes"]):
        i = g.pos.get(ds[:7])
        if i is not None and i <= g.end and v and v > 0:
            a[i] = v
    return a


def _track(tm, under, inverse, months=60):
    """標的和底層序列的月報酬相關（最近 months 個月有資料的部分）。"""
    with np.errstate(all="ignore"):
        r1 = np.diff(np.log(tm))
        r2 = np.diff(np.log(under))
        if inverse:
            r2 = -r2
    ok = np.isfinite(r1) & np.isfinite(r2)
    idx = np.where(ok)[0][-months:]
    if len(idx) < 12:
        return None, int(len(idx))
    return float(np.corrcoef(r1[idx], r2[idx])[0, 1]), int(len(idx))


def _lowbase_flag(st):
    L = C.LOWBASE
    if st is None:
        return None, ""
    pct, dd = st["pct10"], st["dd_3y"]
    low = pct is not None and pct <= L["pct_low"]
    pull = not low and dd is not None and dd <= L["dd_pull"]
    high = pct is not None and pct >= L["pct_high"] and dd is not None and dd > L["dd_high"]
    why = []
    if pct is not None:
        why.append(f"10 年位階 {pct:.0f}%")
    if dd is not None:
        why.append(f"離 3 年高點 {dd:+.0f}%")
    return ("低基期" if low else "高檔回落" if pull else "高基期" if high else "中間"), "、".join(why)


def _fwd(g, sid, h, kind, inverse):
    f = CH.forward(g, sid, h, kind)
    return -f if inverse else f


def _dist(v):
    v = v[np.isfinite(v)]
    if not len(v):
        return None
    return dict(n=int(len(v)), median=_r(float(np.median(v))), p10=_r(float(np.percentile(v, 10))), p90=_r(float(np.percentile(v, 90))),
                hit=_r(100 * float(np.mean(v > 0)), 0))


def _lowbase_hist(g, sid, kind, inverse):
    """底層序列「當時往前 10 年的位階」分五段 → 各段之後 6／12 個月的報酬。回 (現在的段, 各段統計)。"""
    a = g.arr[sid]
    n = len(a)
    W = C.LOWBASE_WINDOW
    pct = np.full(n, np.nan)
    for t in range(n):
        if not np.isfinite(a[t]):
            continue
        w = a[max(0, t - W + 1):t + 1]
        w = w[np.isfinite(w)]
        if len(w) >= 36:
            pct[t] = 100 * (w < a[t]).mean() + 50 * (w == a[t]).mean()
    if inverse:
        pct = 100 - pct
    cur = pct[g.end] if np.isfinite(pct[g.end]) else None
    bucket = lambda p: min(4, int(p // 20))          # noqa: E731
    out = {}
    for h in (6, 12):
        f = _fwd(g, sid, h, kind, inverse)
        rows = []
        for b in range(5):
            m = np.isfinite(pct) & (np.floor(np.minimum(np.nan_to_num(pct, nan=-1), 99.9) / 20).astype(int) == b) & np.isfinite(f)
            d = _dist(f[m])
            rows.append(dict(bucket=BUCKETS[b], n_episodes=len(CH.episodes(m)), **(d or dict(n=0, median=None, p10=None, p90=None, hit=None))))
        out[str(h)] = dict(buckets=rows, all=_dist(f))
    return (dict(pct=_r(cur, 0), bucket=BUCKETS[bucket(cur)] if cur is not None else None, hist=out) if cur is not None else None)


def _similar_hist(g, sid, kind, inverse, jac, end):
    out = {}
    for h in HORIZONS:
        f = _fwd(g, sid, h, kind, inverse)
        m = (jac >= SC.SIM_THR) & np.isfinite(f)
        m[end - h + 1:] = False
        d = _dist(f[m])
        out[str(h)] = dict(n_episodes=len(CH.episodes(m)), **(d or dict(n=0, median=None, p10=None, p90=None, hit=None)), all=_dist(f))
    return out


def _model(scen, sid, inverse):
    out = {}
    for h in HORIZONS:
        row = next((r for r in (scen.get("assets") or {}).get(str(h), []) if r["sid"] == sid), None)
        if not row:
            out[str(h)] = None
            continue
        s = -1 if inverse else 1
        out[str(h)] = dict(ev=_r(s * row["ev"]) if row["ev"] is not None else None, cal=_r(s * row["cal"]) if row.get("cal") is not None else None,
                           lo=_r(s * (row["hi"] if inverse else row["lo"])) if row.get("lo") is not None else None,
                           hi=_r(s * (row["lo"] if inverse else row["hi"])) if row.get("hi") is not None else None,
                           prob_pos=_r(100 - row["prob_pos"] if inverse else row["prob_pos"], 0) if row.get("prob_pos") is not None else None,
                           verdict=scen["backtest"][str(h)]["ridge"]["verdict"])
    return out


def _verdict(model, sim, low, h):
    """三個角度的方向：+1／−1／0；一致的個數。"""
    views = []
    m = model.get(str(h)) if model else None
    if m and m["verdict"] != "樣本外無效" and (m["cal"] is not None or m["ev"] is not None):
        v = m["cal"] if m["cal"] is not None else m["ev"]
        clear = m["lo"] is not None and m["hi"] is not None and (m["lo"] > 0 or m["hi"] < 0)     # 80% 區間不跨 0 才算有方向
        views.append(("模型", int(np.sign(v)) if clear and abs(v) >= 0.5 else 0))
    s = sim.get(str(h)) if sim else None
    if s and s["n_episodes"] >= 3 and s["median"] is not None and s["all"]:
        d = s["median"] - s["all"]["median"]
        views.append(("相似時點", int(np.sign(d)) if abs(d) >= VIEW_GAP else 0))
    hh = "6" if h == 3 else str(h)
    if low and low["hist"].get(hh):
        row = next((b for b in low["hist"][hh]["buckets"] if b["bucket"] == low["bucket"]), None)
        if row and row["n_episodes"] >= 3 and row["median"] is not None and low["hist"][hh]["all"]:
            d = row["median"] - low["hist"][hh]["all"]["median"]
            views.append(("位階", int(np.sign(d)) if abs(d) >= VIEW_GAP else 0))
    pos = sum(1 for _, v in views if v > 0)
    neg = sum(1 for _, v in views if v < 0)
    word = "沒有足夠的角度" if len(views) < 2 else "三個角度都偏多" if pos == 3 else "三個角度都偏空" if neg == 3 \
        else "偏多" if pos >= 2 and not neg else "偏空" if neg >= 2 and not pos else "方向不一致"
    return dict(views=[dict(name=n, dir=v) for n, v in views], word=word)


def _outcome_detail(g, series, trig, X, scen, W):
    """每個「可能會發生的事」（鏈的未成立節點）真的發生時：幅度分布（觸發那個月的變動、之後 3 個月內最深）、等幾個月的分布。"""
    ids = [t["id"] for t in trig]
    tmap = {t["id"]: t for t in trig}
    end = g.end
    out = {}
    for p in scen.get("paths", []):
        for i, n in enumerate(p["nodes"]):
            if n.get("triggered") or n.get("prob") is None or not n.get("after") or n["trigger"] not in ids:
                continue
            up = next((m for m in p["nodes"] if m["label"] == n["after"]), None)
            if not up or up.get("trigger") not in ids:
                continue
            j, k = ids.index(n["trigger"]), ids.index(up["trigger"])
            t = tmap[n["trigger"]]
            vals = CH.transform(g, t["sid"], t["op"], series[t["sid"]]["kind"])
            cm_j, cm_i = X[:, j], X[:, k]
            m = np.zeros(len(cm_i), bool)
            m[:end - W + 1] = cm_i[:end - W + 1] & ~cm_j[:end - W + 1] & np.isfinite(vals[:end - W + 1])
            starts = CH.episodes(m)                       # 和 _node_prob 同一種分段：上游亮、這一層沒亮，間隔 ≤ GAP 算同一段
            sizes, deep, waits = [], [], []
            for s0 in starts:
                seg = cm_j[s0 + 1:s0 + 1 + W]
                if not seg.any():
                    continue
                f = s0 + 1 + int(np.argmax(seg))
                waits.append(f - s0)
                sizes.append(vals[f])
                win = vals[f:min(f + 4, end + 1)]
                win = win[np.isfinite(win)]
                if len(win):
                    deep.append(float(win.max() if t["cmp"] == ">=" else win.min()))
            if len(sizes) < 3:
                continue
            key = n["trigger"]
            if key in out and out[key]["n"] >= len(sizes):
                continue
            out[key] = dict(n=len(sizes), n_episodes=len(starts), unit="bp" if series[t["sid"]]["kind"] == "yield" else "%", op=t["op"], thr=t["thr"], cmp=t["cmp"],
                            size=_dist(np.array(sizes)), deep=_dist(np.array(deep)) if deep else None,
                            wait=[int(sum(1 for w in waits if w == mm)) for mm in range(1, W + 1)])
    return out


def build(g, series, scen, raw, log=print):
    raw_s = (raw or {}).get("series", {})
    trig = PB._triggers(series)
    ids = [t["id"] for t in trig]
    X = SC._masks(g, series, trig, g.end)
    lit = {a["id"] for a in scen.get("active", []) if a["id"] in ids}
    x_now = np.array([1.0 if i in lit else 0.0 for i in ids])
    Xa = X.astype(float)
    inter = Xa @ x_now
    union = Xa.sum(axis=1) + x_now.sum() - inter
    with np.errstate(invalid="ignore", divide="ignore"):
        jac = np.where(union > 0, inter / union, 0.0)

    assets = {}
    for sid_key, sym, name, market, note in C.TARGETS:
        inverse = sid_key.endswith("~inv")
        sid = sid_key.replace("~inv", "")
        if sid not in series or sid not in g.arr:
            log(f"[targets] 序列 {sid} 不存在，略過 {sym}")
            continue
        kind = series[sid]["kind"]
        if sid_key not in assets:
            assets[sid_key] = dict(sid=sid, inverse=inverse, name=series[sid]["name"], kind=kind,
                                   pct30=series[sid]["stats"].get("pct") if series[sid].get("stats") else None,
                                   model=_model(scen, sid, inverse) if kind == "price" else None,
                                   similar=_similar_hist(g, sid, kind, inverse, jac, g.end) if kind == "price" else None,
                                   lowbase=_lowbase_hist(g, sid, kind, inverse) if kind == "price" else None, tickers=[])
            if inverse and assets[sid_key]["pct30"] is not None:
                assets[sid_key]["pct30"] = 100 - assets[sid_key]["pct30"]
            A = assets[sid_key]
            A["verdict"] = {str(h): _verdict(A["model"], A["similar"], A["lowbase"], h) for h in HORIZONS} if kind == "price" else None
        A = assets[sid_key]
        if market == "cash":
            a = g.arr[sid]
            st = dict(last=_r(a[g.end], 2), date=g.months[g.end], first=g.months[0], c1y=series[sid]["stats"].get("c12"), c3y=None,
                      dd_ath=None, ath_at=None, dd_3y=_r((a[g.end] / np.nanmax(a[max(0, g.end - 36):g.end + 1]) - 1) * 100),
                      pct10=_r(_pct_rank(a[max(0, g.end - 120):g.end + 1], a[g.end]), 0), years10=10.0, ma200=None)
            flag, why = _lowbase_flag(st)
            A["tickers"].append(dict(sym=sym, name=name, market=market, note=note, status=st, base=flag, base_why=why, track=None, track_n=0, track_ok=None, stale=False))
            continue
        d = raw_s.get(sym)
        if not d:
            log(f"[targets] 沒有 {sym} 的日線，略過")
            continue
        st = _ticker_status(d, g)
        if not st:
            continue
        tm = _monthly(d, g)
        corr, nn = _track(tm, g.arr[sid], inverse) if kind == "price" else (None, 0)       # 殖利率不是價格，不比追蹤
        flag, why = _lowbase_flag(st)
        A["tickers"].append(dict(sym=sym, name=name, market=market, note=note, status=st, base=flag, base_why=why,
                                 track=_r(corr, 2), track_n=nn, track_ok=(None if corr is None else corr >= MIN_TRACK), stale=bool(d.get("stale")),
                                 currency=d.get("currency")))
        if corr is not None and corr < MIN_TRACK:
            log(f"[targets] {sym}（{name}）和 {series[sid]['name']} 的月報酬相關只有 {corr:.2f}（{nn} 個月）")
    outcomes = _outcome_detail(g, series, trig, X, scen, scen.get("within", 6))
    n_t = sum(len(a["tickers"]) for a in assets.values())
    lows = [t["sym"] for a in assets.values() for t in a["tickers"] if t["base"] == "低基期"]
    pulls = [t["sym"] for a in assets.values() for t in a["tickers"] if t["base"] == "高檔回落"]
    log(f"[targets] {len(assets)} 個資產、{n_t} 檔標的；低基期：{'、'.join(lows) if lows else '沒有'}；高檔回落：{'、'.join(pulls) if pulls else '沒有'}；情境幅度 {len(outcomes)} 個")
    return dict(assets=assets, outcomes=outcomes, rules=dict(C.LOWBASE, window=C.LOWBASE_WINDOW, min_track=MIN_TRACK, sim_thr=SC.SIM_THR),
                fetched=(raw or {}).get("fetched_at"), horizons=HORIZONS)
