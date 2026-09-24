"""事件衝擊鏈：真實事件發生後兩週／一個月／兩個月，資金從上游流到下游的實際路徑。

和其他分頁的差別：這裡用日線，而且事件是「真的發生過的事」（戰爭、管線中斷、破產），
不是價格門檻。傳導順序不是我假設的，是量出來的——先判定「有沒有實質反應」（42 個交易日內
最大累積變動 ≥ 2σ×√該天數，σ 取事件前 60 個交易日的日波動），有反應的才算「走完一半」是第幾天。

限制：每類事件只有 4～14 次，中位數只能當參考；事件常同時伴隨其他事件，無法分離因果。
1999 年以前的事件，ETF／期貨還不存在，改用代理序列（產業基金、現貨價、證交所指數），逐筆標註。
"""
import bisect
import datetime as dt
import hashlib
import json
import math
import pathlib

import numpy as np

from . import config as C

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"


def r(v, nd=2):
    if v is None:
        return None
    v = float(v)
    return round(v, nd) if np.isfinite(v) else None


def _unit(sym):
    if sym in ("^TNX", "^IRX"):
        return "bp"
    if sym == "^VIX":
        return "pt"
    return "%"


def _change(closes, i0, j, unit):
    a, b = closes[i0], closes[i0 + j]
    if not (np.isfinite(a) and np.isfinite(b)):
        return None
    if unit == "%" and (a <= 0 or b <= 0):     # 2020-04-20 WTI 期貨結算 −37.63，對數報酬無定義
        return None
    if unit == "bp":
        return (b - a) * 100
    if unit == "pt":
        return b - a
    return 100 * np.log(b / a)


def event_response(rec, sym, event_date):
    dates, closes = rec["dates"], np.asarray(rec["closes"], dtype=float)
    i0 = bisect.bisect_left(dates, event_date) - 1      # 事件前最後一個收盤
    if i0 < 61 or i0 + C.CASCADE_MAX_DAYS >= len(dates):
        return None
    unit = _unit(sym)
    seg = closes[i0 - 60:i0 + 1]
    with np.errstate(all="ignore"):
        if unit == "%":
            rets = 100 * np.diff(np.log(seg))
        elif unit == "bp":
            rets = 100 * np.diff(seg)
        else:
            rets = np.diff(seg)
    sigma = float(np.nanstd(rets))
    path = [_change(closes, i0, j, unit) for j in range(1, C.CASCADE_MAX_DAYS + 1)]
    react = react_move = None
    if sigma > 0:
        for j, v in enumerate(path, start=1):
            if v is not None and abs(v) >= C.CASCADE_REACT_SIGMA * sigma * (j ** 0.5):
                react, react_move = j, v
                break
    pre = None
    if i0 - C.CASCADE_PRE >= 0:
        pre = _change(closes, i0 - C.CASCADE_PRE, C.CASCADE_PRE, unit)
    # 傳導速度：先判斷這個標的到底有沒有實質反應（期間內最大累積變動要超過 2σ×√天數），
    # 有反應的才算「達到最大反應一半」是第幾天。沒有這道前置判斷的話，兩個月幾乎沒動的標的
    # 會因為「一半」的門檻很低而排在最前面，順序就失去意義。
    vals = [(abs(v), j) for j, v in enumerate(path, start=1) if v is not None]
    peak_abs, peak_day = max(vals) if vals else (None, None)
    responded = bool(peak_abs is not None and sigma > 0
                     and peak_abs >= C.CASCADE_REACT_SIGMA * sigma * (peak_day ** 0.5))
    peak_move = path[peak_day - 1] if peak_day else None
    half_day = None
    if responded:
        for j, v in enumerate(path, start=1):
            if v is not None and abs(v) >= peak_abs / 2 and (v > 0) == (peak_move > 0):
                half_day = j
                break
    z1 = r(path[0] / sigma, 2) if path and path[0] is not None and sigma > 0 else None
    # 事件視窗（含事前 60 天的波動估計）有任何一段落在代理序列上，就標出代理名稱
    px = rec.get("proxy")
    proxy = px["name"] if px and dates[i0 - 60] <= px["until"] else None
    out = dict(id=sym, name=rec["name"], layer=rec["layer"], unit=unit, base_date=dates[i0], proxy=proxy,
               sigma=r(sigma, 3), react=react, react_move=r(react_move), half_day=half_day,
               peak_day=peak_day if responded else None, peak_move=r(peak_move) if responded else None,
               responded=responded, z1=z1, pre=r(pre), path=[r(v, 2) for v in path])
    for w in C.CASCADE_WINDOWS:
        out[f"w{w}"] = r(path[w - 1]) if len(path) >= w else None
    return out


def binom_p(k, n, p0, upper):
    """單尾二項檢定：n 次事件裡 k 次上漲，平常上漲機率 p0。upper=True 算 P(X≥k)，否則 P(X≤k)。
    事件彼此相隔夠遠（同類事件已去重），所以視為獨立；次數少時 p 值下限很高（5 次全漲也只有 0.6^5≈0.08）。"""
    rng = range(k, n + 1) if upper else range(0, k + 1)
    return sum(math.comb(n, i) * p0 ** i * (1 - p0) ** (n - i) for i in rng)


def baseline(rec, sym):
    """無條件基準：這個標的在全部歷史中，任意一天起算 w 個交易日的變動中位數與上漲比例。
    事件後的中位數要跟這個比，否則長期上漲的資產（科技股）在任何事件後看起來都像「錢流入」。"""
    c = np.asarray(rec["closes"], dtype=float)
    unit = _unit(sym)
    out = {}
    for w in C.CASCADE_WINDOWS:
        a, b = c[:-w], c[w:]
        with np.errstate(all="ignore"):
            if unit == "%":
                ok = (a > 0) & (b > 0)
                d = 100 * np.log(b[ok] / a[ok])
            elif unit == "bp":
                d = (b - a) * 100
            else:
                d = b - a
        d = d[np.isfinite(d)]
        out[f"w{w}"] = r(float(np.median(d))) if len(d) else None
        out[f"up{w}"] = r(100 * float(np.mean(d > 0)), 0) if len(d) else None
    return out


def _categories(events, universe, base):
    """分類彙總：同一類事件的中位數、方向一致度，以及和無條件基準比較的超額與二項檢定。"""
    cats = []
    for cid, cname in C.SHOCK_CATS:
        evs, skipped = [], []
        for e in sorted((e for e in events if e["cat"] == cid), key=lambda e: e["date"]):
            gap = (dt.date.fromisoformat(e["date"]) - dt.date.fromisoformat(evs[-1]["date"])).days if evs else None
            if gap is not None and gap < C.CASCADE_DEDUP_DAYS:
                skipped.append(dict(id=e["id"], name=e["name"], after=evs[-1]["name"], days=gap))
                continue
            evs.append(e)
        if not evs:
            continue
        rows = []
        for u in universe:
            vals = {w: [] for w in C.CASCADE_WINDOWS}
            reacts, pres, halves = [], [], []
            for e in evs:
                a = next((x for x in e["assets"] if x["id"] == u["id"]), None)
                if not a:
                    continue
                for w in C.CASCADE_WINDOWS:
                    if a[f"w{w}"] is not None:
                        vals[w].append(a[f"w{w}"])
                if a["react"]:
                    reacts.append(a["react"])
                if a["half_day"]:
                    halves.append(a["half_day"])
                if a["pre"] is not None:
                    pres.append(a["pre"])
            n = len(vals[C.CASCADE_WINDOWS[1]])
            if n < 2:
                continue
            row = dict(id=u["id"], name=u["name"], layer=u["layer"], unit=_unit(u["id"]), n=n,
                       react=r(float(np.median(reacts)), 1) if reacts else None, react_n=len(reacts),
                       half_day=r(float(np.median(halves)), 1) if halves else None, half_n=len(halves),
                       pre=r(float(np.median(pres))) if pres else None)
            for w in C.CASCADE_WINDOWS:
                v = vals[w]
                row[f"w{w}"] = r(float(np.median(v))) if v else None
                row[f"agree{w}"] = r(100 * max(np.mean(np.array(v) > 0), np.mean(np.array(v) < 0)), 0) if v else None
                bw = base[u["id"]][f"w{w}"]
                row[f"base{w}"] = bw
                row[f"up{w}"] = r(100 * float(np.mean(np.array(v) > 0)), 0) if v else None
                row[f"base_up{w}"] = base[u["id"]][f"up{w}"]
                row[f"excess{w}"] = r(row[f"w{w}"] - bw) if v and bw is not None else None
                bu = base[u["id"]][f"up{w}"]
                if v and bu is not None and row[f"excess{w}"] is not None:
                    k = int(np.sum(np.array(v) > 0))
                    row[f"p{w}"] = r(binom_p(k, len(v), bu / 100, row[f"excess{w}"] > 0), 3)
                else:
                    row[f"p{w}"] = None
            rows.append(row)
        # 先把「多數事件都有反應」的排前面，再依傳導速度；只反應過一次的不該排在最前面
        for x in rows:
            x["resp_rate"] = r(100 * x["half_n"] / x["n"], 0) if x["n"] else None
        rows.sort(key=lambda x: (x["half_n"] < 2, x["half_day"] is None, x["half_day"] or 99, -(x["half_n"] or 0)))
        cats.append(dict(id=cid, name=cname, n=len(evs), events=[e["id"] for e in evs], skipped=skipped,
                         first=evs[0]["date"], last=evs[-1]["date"], assets=rows))

    return cats


def _count(cats, alpha):
    return sum(1 for c in cats for x in c["assets"] for w in C.CASCADE_WINDOWS
               if x.get(f"p{w}") is not None and (alpha is None or x[f"p{w}"] <= alpha))


def _null_calibration(daily, universe, base, rounds=C.CASCADE_NULL_ROUNDS, span=C.CASCADE_NULL_SPAN):
    """每個事件保留分類，日期隨機移到原日期前後 span 天內（涵蓋的標的與年代大致相同），重跑分類統計。"""
    rng = np.random.default_rng(20260924)
    lo = dt.date.fromisoformat(C.CASCADE_START) + dt.timedelta(days=120)
    hi = dt.date.today() - dt.timedelta(days=90)
    out = []
    for _ in range(rounds):
        fake = []
        for ev in C.SHOCK_EVENTS:
            d = dt.date.fromisoformat(ev["date"]) + dt.timedelta(days=int(rng.integers(-span, span + 1)))
            d = min(max(d, lo), hi).isoformat()
            assets = [x for x in (event_response(daily[s], s, d) for s, _n, _l in C.CASCADE_UNIVERSE if s in daily) if x]
            if assets:
                fake.append(dict(id=ev["id"], name=ev["name"], date=d, cat=ev["cat"], assets=assets))
        out.append(_count(_categories(fake, universe, base), 0.05))
    return out


def build(log=print):
    path = RAW / "daily_cascade.json"
    if not path.exists():
        log("[cascade] 找不到 data/raw/daily_cascade.json，略過（執行 gfd.py history 會抓）")
        return None
    raw_meta = json.loads(path.read_text(encoding="utf-8"))
    daily = raw_meta["series"]
    layers = [dict(id=a, name=b) for a, b in C.CASCADE_LAYERS]
    universe = [dict(id=s, name=n, layer=l, start=daily[s]["dates"][0], base=baseline(daily[s], s))
                for s, n, l in C.CASCADE_UNIVERSE if s in daily]
    base = {u["id"]: u["base"] for u in universe}

    events = []
    evdate = {e["id"]: dt.date.fromisoformat(e["date"]) for e in C.SHOCK_EVENTS}
    for ev in C.SHOCK_EVENTS:
        assets = []
        for sym, _n, _l in C.CASCADE_UNIVERSE:
            rec = daily.get(sym)
            if not rec:
                continue
            resp = event_response(rec, sym, ev["date"])
            if resp:
                assets.append(resp)
        if not assets:
            continue
        # 反應順序：先動的排前面；沒有明顯反應的排最後
        # 排序＝傳導順序：先看「走完一半」是第幾天，再看反應強度
        order = sorted(assets, key=lambda a: (a["half_day"] is None, a["half_day"] or 99, -abs(a["z1"] or 0)))
        # 網頁只畫反應最大的四條累積路徑（與 70-cascade.js 的 cascadePaths 同一規則），其餘不輸出以控制頁面大小
        keep = {a["id"] for a in sorted((a for a in assets if a["responded"] and a["unit"] == "%"),
                                        key=lambda a: -abs(a["peak_move"]))[:4]}
        for a in assets:
            if a["id"] not in keep:
                a["path"] = None
        # 兩個月視窗內還有別的事件 → 這次量到的變動混了那個事件的效果
        overlaps = sorted((dict(id=o["id"], name=o["name"], days=(evdate[o["id"]] - evdate[ev["id"]]).days)
                           for o in C.SHOCK_EVENTS if o["id"] != ev["id"]
                           and abs((evdate[o["id"]] - evdate[ev["id"]]).days) <= C.CASCADE_OVERLAP_DAYS),
                          key=lambda x: x["days"])
        events.append(dict(id=ev["id"], name=ev["name"], date=ev["date"], cat=ev["cat"], note=ev.get("note", ""),
                           approx=bool(ev.get("approx")), assets=assets, coverage=len(assets),
                           proxies=sorted({a["proxy"] for a in assets if a["proxy"]}), overlaps=overlaps,
                           order=[a["id"] for a in order],
                           first_movers=[dict(id=a["id"], name=a["name"], layer=a["layer"], react=a["react"],
                                              half_day=a["half_day"], move=a["react_move"], unit=a["unit"])
                                         for a in order[:6]]))

    cats = _categories(events, universe, base)

    # 多重檢定的現實：分類 × 標的 × 期間 做了幾百次檢定，有一部分過關純屬運氣。
    # 二項檢定是離散的、格子之間又高度相關，名目 5% 不能直接用 → 把每個事件日隨機移到前後三年內，
    # 重跑整套分類統計，數「假事件」也有幾格過關，當作運氣預期。
    stats = dict(tests=_count(cats, None), p05=_count(cats, 0.05), p10=_count(cats, 0.10))
    # 結果只取決於日線與事件清單，排程每天 analyze 不必重跑（約 40 秒）
    key = hashlib.sha1(json.dumps([raw_meta.get("fetched_at"), C.SHOCK_EVENTS, C.SHOCK_CATS, C.CASCADE_UNIVERSE,
                                   C.CASCADE_WINDOWS, C.CASCADE_DEDUP_DAYS, C.CASCADE_NULL_ROUNDS, C.CASCADE_NULL_SPAN,
                                   C.CASCADE_REACT_SIGMA, C.CASCADE_PRE, C.CASCADE_MAX_DAYS, C.CASCADE_START],
                                  ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    cache_p = RAW / "cascade_null.json"
    cached = json.loads(cache_p.read_text(encoding="utf-8")) if cache_p.exists() else {}
    if cached.get("key") == key:
        null = cached["null05"]
    else:
        null = _null_calibration(daily, universe, base)
        cache_p.write_text(json.dumps(dict(key=key, null05=null)), encoding="utf-8")
    stats.update(null05=null, null05_mean=r(float(np.mean(null)), 1),
                 fdr05=r(min(100.0, 100 * float(np.mean(null)) / stats["p05"]), 0) if stats["p05"] else None)
    log(f"[cascade] 分類檢定 {stats['tests']} 格；p≤0.05 實際 {stats['p05']} 格、隨機事件日平均 {stats['null05_mean']} 格"
        f"（估計偽發現率 {stats['fdr05']}%）")
    missing = [e["id"] for e in C.SHOCK_EVENTS if e["id"] not in {x["id"] for x in events}]
    log(f"[cascade] {len(events)} 個事件、{len(universe)} 個標的、{len(cats)} 個分類"
        + (f"；資料不足略過：{', '.join(missing)}" if missing else ""))
    return dict(events=events, categories=cats, layers=layers, universe=universe, compare=C.CASCADE_COMPARE, stats=stats,
                windows=C.CASCADE_WINDOWS, pre=C.CASCADE_PRE, max_days=C.CASCADE_MAX_DAYS,
                sigma_mult=C.CASCADE_REACT_SIGMA, fetched_at=raw_meta.get("fetched_at"),
                note=("傳導順序以「走完一半」的天數排序＝累積變動第一次達到兩個月總變動一半的那天；"
                      "「有實質反應」＝期間內最大累積變動超過該標的自身 2σ×√天數（σ 取事件前 60 個交易日的日波動）；"
                      "沒有實質反應的標的不給傳導速度，列在最後。"
                      "1999 年以前的事件，ETF 與期貨尚未存在，改用代理序列（產業基金還原淨值、現貨價、證交所指數），"
                      "在明細中逐筆標註；代理與原標的並非完全相同的資產。"
                      "殖利率以 bp、VIX 以點數、其餘以對數報酬 % 表示。每類事件次數少，中位數僅供參考；"
                      "事件期間常伴隨其他事件，無法分離因果。"))
