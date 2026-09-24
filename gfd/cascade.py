"""事件衝擊鏈：真實事件發生後兩週／一個月／兩個月，資金從上游流到下游的實際路徑。

和其他分頁的差別：這裡用日線，而且事件是「真的發生過的事」（戰爭、管線中斷、破產），
不是價格門檻。傳導順序不是我假設的，是量出來的——先判定「有沒有實質反應」（42 個交易日內
最大累積變動 ≥ 2σ×√該天數，σ 取事件前 60 個交易日的日波動），有反應的才算「走完一半」是第幾天。

限制：每類事件只有 4～8 次，中位數只能當參考；事件常同時伴隨其他事件，無法分離因果。
"""
import bisect
import datetime as dt
import json
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
    if not (np.isfinite(a) and np.isfinite(b)) or a <= 0:
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
    out = dict(id=sym, name=rec["name"], layer=rec["layer"], unit=unit, base_date=dates[i0],
               sigma=r(sigma, 3), react=react, react_move=r(react_move), half_day=half_day,
               peak_day=peak_day if responded else None, peak_move=r(peak_move) if responded else None,
               responded=responded, z1=z1, pre=r(pre), path=[r(v, 2) for v in path])
    for w in C.CASCADE_WINDOWS:
        out[f"w{w}"] = r(path[w - 1]) if len(path) >= w else None
    return out


def build(log=print):
    path = RAW / "daily_cascade.json"
    if not path.exists():
        log("[cascade] 找不到 data/raw/daily_cascade.json，略過（執行 gfd.py history 會抓）")
        return None
    daily = json.loads(path.read_text(encoding="utf-8"))["series"]
    layers = [dict(id=a, name=b) for a, b in C.CASCADE_LAYERS]
    universe = [dict(id=s, name=n, layer=l) for s, n, l in C.CASCADE_UNIVERSE if s in daily]

    events = []
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
        events.append(dict(id=ev["id"], name=ev["name"], date=ev["date"], cat=ev["cat"], note=ev.get("note", ""),
                           approx=bool(ev.get("approx")), assets=assets,
                           order=[a["id"] for a in order],
                           first_movers=[dict(id=a["id"], name=a["name"], layer=a["layer"], react=a["react"],
                                              half_day=a["half_day"], move=a["react_move"], unit=a["unit"])
                                         for a in order[:6]]))

    # 分類彙總：同一類事件的中位數與方向一致度
    cats = []
    for cid, cname in C.SHOCK_CATS:
        evs = [e for e in events if e["cat"] == cid]
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
            rows.append(row)
        # 先把「多數事件都有反應」的排前面，再依傳導速度；只反應過一次的不該排在最前面
        for x in rows:
            x["resp_rate"] = r(100 * x["half_n"] / x["n"], 0) if x["n"] else None
        rows.sort(key=lambda x: (x["half_n"] < 2, x["half_day"] is None, x["half_day"] or 99, -(x["half_n"] or 0)))
        cats.append(dict(id=cid, name=cname, n=len(evs), events=[e["id"] for e in evs], assets=rows))

    log(f"[cascade] {len(events)} 個事件、{len(universe)} 個標的、{len(cats)} 個分類")
    return dict(events=events, categories=cats, layers=layers, universe=universe,
                windows=C.CASCADE_WINDOWS, pre=C.CASCADE_PRE, max_days=C.CASCADE_MAX_DAYS,
                sigma_mult=C.CASCADE_REACT_SIGMA, fetched_at=json.loads(path.read_text(encoding="utf-8")).get("fetched_at"),
                note=("傳導順序以「走完一半」的天數排序＝累積變動第一次達到兩個月總變動一半的那天；"
                      "「有實質反應」＝期間內最大累積變動超過該標的自身 2σ×√天數（σ 取事件前 60 個交易日的日波動）；"
                      "沒有實質反應的標的不給傳導速度，列在最後。"
                      "殖利率以 bp、VIX 以點數、其餘以對數報酬 % 表示。每類事件次數少，中位數僅供參考；"
                      "事件期間常伴隨其他事件，無法分離因果。"))
