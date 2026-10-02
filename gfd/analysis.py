"""30 年關聯研究：讀 data/raw → 寫 data/analysis.json。純本地計算、零網路。"""
import bisect
import datetime as dt
import json
import math
import pathlib

import numpy as np

from . import analogs as AN
from . import cascade as CA
from . import chains as CH
from . import config as C
from . import playbook as PB
from . import scenario as SC

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "analysis.json"
TPE = dt.timezone(dt.timedelta(hours=8))
ROLL = 36


def _load(name, default=None):
    p = RAW / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def month_range(a, b):
    y, m = map(int, a.split("-"))
    out = []
    while f"{y:04d}-{m:02d}" <= b:
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def num(x, nd=2):
    if x is None:
        return None
    x = float(x)
    return round(x, nd) if math.isfinite(x) else None


def compact(v):
    if v is None or not math.isfinite(v):
        return None
    a = abs(v)
    return round(v, 4) if a < 10 else round(v, 3) if a < 1000 else round(v, 1)


def changes(a, kind, k=1):
    out = np.full(len(a), np.nan)
    with np.errstate(all="ignore"):
        if kind == "yield":
            out[k:] = (a[k:] - a[:-k]) * 100
        else:
            out[k:] = 100 * np.log(a[k:] / a[:-k])
    return out


def pcorr(x, y, min_n=24):
    m = np.isfinite(x) & np.isfinite(y)
    n = int(m.sum())
    if n < min_n:
        return None, n
    xs, ys = x[m], y[m]
    if xs.std() == 0 or ys.std() == 0:
        return None, n
    return float(np.corrcoef(xs, ys)[0, 1]), n


def lagcorr(x, y, k):
    """k>0：x 領先 y k 個月（x_t 對 y_{t+k}）。"""
    if k > 0:
        return pcorr(x[:-k], y[k:])
    if k < 0:
        return pcorr(x[-k:], y[:k])
    return pcorr(x, y)


class Grid:
    def __init__(self, values):
        ends = [max(v) for v in values.values() if v]
        self.months = month_range(C.START_MONTH, max(ends))
        now = dt.datetime.now(TPE)
        cur = f"{now.year:04d}-{now.month:02d}"
        complete = [i for i, m in enumerate(self.months) if m < cur]
        self.end = complete[-1] if complete else len(self.months) - 1  # 最後一個完整月
        self.pos = {m: i for i, m in enumerate(self.months)}
        self.arr = {}
        for sid, vals in values.items():
            a = np.full(len(self.months), np.nan)
            for m, v in vals.items():
                if m in self.pos and v is not None:
                    a[self.pos[m]] = v
            self.arr[sid] = a

    def done(self, a):
        """只保留完整月份（研究用，避免當月未收完的資料）。"""
        return a[: self.end + 1]


def series_stats(a, kind, months):
    idx = np.where(np.isfinite(a))[0]
    if not len(idx):
        return None
    first, last = idx[0], idx[-1]
    v = a[last]

    def chg(k):
        j = last - k
        if j < 0 or not np.isfinite(a[j]):
            return None
        return (v - a[j]) * 100 if kind == "yield" else (v / a[j] - 1) * 100

    seg = a[first:last + 1]
    fin = seg[np.isfinite(seg)]
    st = dict(first=months[first], last=months[last], value=compact(v),
              c1=num(chg(1)), c3=num(chg(3)), c12=num(chg(12)), c60=num(chg(60)),
              min=compact(fin.min()), min_at=months[first + int(np.nanargmin(seg))],
              max=compact(fin.max()), max_at=months[first + int(np.nanargmax(seg))],
              pct=num(100 * (fin < v).mean() + 50 * (fin == v).mean(), 0))
    ch = changes(a, kind)
    st["vol"] = num(np.nanstd(ch) * math.sqrt(12)) if np.isfinite(ch).sum() > 12 else None
    years = (last - first) / 12
    if kind != "yield" and years >= 1 and a[first] > 0:
        st["cagr"] = num(((v / a[first]) ** (1 / years) - 1) * 100)
    if kind == "price":
        peak = np.fmax.accumulate(np.where(np.isfinite(seg), seg, -np.inf))
        dd = np.where(np.isfinite(seg), (seg / peak - 1) * 100, np.nan)
        st["mdd"] = num(np.nanmin(dd))
        st["mdd_at"] = months[first + int(np.nanargmin(dd))]
        st["dd_now"] = num(dd[-1])
    return st


def build_series(g, raw_values):
    meta = {s["id"]: s for s in C.SERIES}
    out = {}
    for sid, s in meta.items():
        if sid not in g.arr:
            continue
        a = g.arr[sid]
        source = {"yahoo": "Yahoo Finance", "cbc": "台灣中央銀行", "wb_pink": "世界銀行 Pink Sheet",
                  "mof_jgb": "日本財務省"}.get(s["src"][0], s["src"][0])
        out[sid] = dict(name=s["name"], group=s["group"], kind=s["kind"], unit=s["unit"], note=s["note"], source=source,
                        values=[compact(x) for x in a], stats=series_stats(a, s["kind"], g.months))
    # 衍生序列
    derived = []
    if "b_us10y" in g.arr and "b_us3m" in g.arr:
        derived.append(("d_curve", "美債 10 年 − 3 個月利差", "yield", "%", g.arr["b_us10y"] - g.arr["b_us3m"],
                        "負值＝殖利率曲線倒掛，歷史上常領先景氣衰退"))
    if "c_copper" in g.arr and "c_gold" in g.arr:
        derived.append(("d_cu_au", "銅/黃金 比值", "price", "比值", g.arr["c_copper"] / g.arr["c_gold"],
                        "上升＝景氣實需強於避險需求"))
    if "c_brent" in g.arr and "c_gold" in g.arr:
        derived.append(("d_oil_au", "原油/黃金 比值", "price", "比值", g.arr["c_brent"] / g.arr["c_gold"],
                        "上升＝通膨與景氣動能強於避險"))
    for sid, name, kind, unit, a, note in derived:
        g.arr[sid] = a
        out[sid] = dict(name=name, group="derived", kind=kind, unit=unit, note=note,
                        values=[compact(x) for x in a], stats=series_stats(a, kind, g.months))
    return out


def correlations(g, series):
    ids = [i for i in C.CORE_IDS if i in series]
    ch = {i: g.done(changes(g.arr[i], series[i]["kind"])) for i in ids}
    n = len(ids)
    full = [[None] * n for _ in range(n)]
    full_n = [[0] * n for _ in range(n)]
    recent = [[None] * n for _ in range(n)]
    for i in range(n):
        for j in range(i, n):
            r, k = pcorr(ch[ids[i]], ch[ids[j]], 36)
            rr, _ = pcorr(ch[ids[i]][-ROLL:], ch[ids[j]][-ROLL:], 30)
            full[i][j] = full[j][i] = num(r)
            full_n[i][j] = full_n[j][i] = k
            recent[i][j] = recent[j][i] = num(rr)
    return dict(ids=ids, full=full, full_n=full_n, recent=recent, window=ROLL,
                recent_start=g.months[max(0, g.end - ROLL + 1)], recent_end=g.months[g.end])


def pairs(g, series):
    out = []
    for a, b, label, why in C.PAIRS:
        if a not in series or b not in series:
            continue
        x = g.done(changes(g.arr[a], series[a]["kind"]))
        y = g.done(changes(g.arr[b], series[b]["kind"]))
        r_full, n_full = pcorr(x, y, 36)
        r_rec, n_rec = pcorr(x[-ROLL:], y[-ROLL:], 30)
        rolling = [None] * len(g.months)
        for t in range(ROLL - 1, len(x)):
            r, _ = pcorr(x[t - ROLL + 1:t + 1], y[t - ROLL + 1:t + 1], 30)
            rolling[t] = num(r)
        ll = []
        for k in range(-6, 7):
            r, nn = lagcorr(x, y, k)
            ll.append(dict(k=k, r=num(r), n=nn))
        valid = [e for e in ll if e["r"] is not None]
        best = max(valid, key=lambda e: abs(e["r"])) if valid else None
        r0 = next((e["r"] for e in ll if e["k"] == 0), None)
        sig = num(2 / math.sqrt(n_full), 3) if n_full else None
        lead = None
        if best and best["k"] != 0 and sig and abs(best["r"]) > sig and abs(best["r"]) > abs(r0 or 0) + 0.05:
            lead = best
        out.append(dict(a=a, b=b, label=label, why=why, r_full=num(r_full), n_full=n_full,
                        r_recent=num(r_rec), n_recent=n_rec, rolling=rolling, leadlag=ll,
                        best=best, lead=lead, sig=sig))
    return out


def events(g, series):
    ids = [i for i in dict.fromkeys(C.CORE_IDS + [f for f, _ in C.FLOWMAP]) if i in series]
    out = []
    for eid, name, start, end in C.EVENTS:
        if start not in g.pos or end not in g.pos or g.pos[start] == 0:
            continue
        s, e = g.pos[start] - 1, g.pos[end]
        moves = {}
        for i in ids:
            a, kind = g.arr[i], series[i]["kind"]
            if not (np.isfinite(a[s]) and np.isfinite(a[e])):
                continue
            if kind == "yield":
                moves[i] = dict(v=num((a[e] - a[s]) * 100, 0), unit="bp")
            elif kind == "level":
                moves[i] = dict(v=num(a[e] - a[s], 1), unit="pt")
            else:
                moves[i] = dict(v=num((a[e] / a[s] - 1) * 100, 1), unit="%")
        out.append(dict(id=eid, name=name, start=start, end=end, moves=moves))
    return dict(ids=ids, items=out)


def rolling_z(a, window, min_n):
    z = np.full(len(a), np.nan)
    for t in range(len(a)):
        if not np.isfinite(a[t]):
            continue
        w = a[max(0, t - window + 1):t + 1]
        w = w[np.isfinite(w)]
        if len(w) >= min_n and w.std() > 0:
            z[t] = (a[t] - w.mean()) / w.std()
    return np.clip(z, -3, 3)


def _bucket_stats(vals):
    v = np.array([x for x in vals if np.isfinite(x)])
    if not len(v):
        return dict(n=0)
    return dict(n=int(len(v)), mean=num(v.mean()), median=num(np.median(v)), hit=num(100 * (v > 0).mean(), 0))


def forward_returns(g, sid, k):
    a = g.done(g.arr[sid])
    f = np.full(len(g.months), np.nan)
    with np.errstate(all="ignore"):
        f[:len(a) - k] = 100 * np.log(a[k:] / a[:-k])
    return f


def composite(g):
    A = g.arr
    need = ["fx_dxy", "v_vix", "fx_usdjpy", "c_copper", "c_gold", "b_hy", "b_ig", "fx_usdtwd"]
    if any(k not in A for k in need):
        return None
    raw = {
        "dollar": changes(A["fx_dxy"], "price", 6),
        "fear": A["v_vix"].copy(),
        "carry": changes(A["fx_usdjpy"], "price", 3),
        "growth": changes(A["c_copper"] / A["c_gold"], "price", 6),
        "credit": changes(A["b_hy"], "price", 6) - changes(A["b_ig"], "price", 6),
        "asia": changes(A["fx_usdtwd"], "price", 3),
    }
    comps, stack = [], []
    for key, name, how, sign, why in C.COMPOSITE:
        z = sign * rolling_z(raw[key], C.COMPOSITE_Z_WINDOW, C.COMPOSITE_Z_MIN)
        stack.append(z)
        li = np.where(np.isfinite(z))[0]
        comps.append(dict(key=key, name=name, how=how, sign=sign, why=why, z=[num(x) for x in z],
                          latest=num(z[li[-1]]) if len(li) else None,
                          latest_at=g.months[li[-1]] if len(li) else None))
    S = np.vstack(stack)
    cnt = np.isfinite(S).sum(axis=0)
    total = np.where(np.isfinite(S), S, 0).sum(axis=0)
    with np.errstate(all="ignore"):
        comp = np.where(cnt >= 4, total / np.maximum(cnt, 1), np.nan)
    li = np.where(np.isfinite(comp))[0]
    latest = comp[li[-1]] if len(li) else None
    hist = comp[np.isfinite(comp)]
    state = None if latest is None else ("風險偏好" if latest > 0.5 else "避險" if latest < -0.5 else "中性")

    # 狀態 × 未來 3 個月報酬（樣本內回顧，非回測）
    targets = [t for t in ["eq_spx", "eq_twii", "eq_hsi", "c_gold", "b_ust_long", "fx_dxy"] if t in A]
    buckets = [("避險 < −0.5", -9, -0.5), ("中性", -0.5, 0.5), ("風險偏好 > 0.5", 0.5, 9)]
    fwd = []
    for t in targets:
        f3 = forward_returns(g, t, 3)
        row = dict(id=t, buckets=[])
        for label, lo, hi in buckets:
            m = np.isfinite(comp) & (comp >= lo) & (comp < hi)
            row["buckets"].append(dict(label=label, **_bucket_stats(f3[m])))
        fwd.append(row)
    return dict(values=[num(x) for x in comp], components=comps, latest=num(latest),
                latest_at=g.months[li[-1]] if len(li) else None, state=state,
                percentile=num(100 * (hist < latest).mean(), 0) if latest is not None else None,
                forward=fwd, bucket_labels=[b[0] for b in buckets])


def vix_regimes(g):
    if "v_vix" not in g.arr:
        return None
    vix = g.arr["v_vix"]
    bands = [("平靜 < 15", 0, 15), ("正常 15–20", 15, 20), ("緊張 20–30", 20, 30), ("恐慌 ≥ 30", 30, 999)]
    rows = []
    for t in [x for x in ["eq_spx", "eq_twii", "eq_hsi", "c_gold", "b_ust_long"] if x in g.arr]:
        f1, f3 = forward_returns(g, t, 1), forward_returns(g, t, 3)
        row = dict(id=t, bands=[])
        for label, lo, hi in bands:
            m = np.isfinite(vix) & (vix >= lo) & (vix < hi)
            row["bands"].append(dict(label=label, f1=_bucket_stats(f1[m]), f3=_bucket_stats(f3[m])))
        rows.append(row)
    fin = vix[np.isfinite(vix)]
    li = np.where(np.isfinite(vix))[0][-1]
    cur = next(label for label, lo, hi in bands if lo <= vix[li] < hi)
    share = [dict(label=label, pct=num(100 * ((fin >= lo) & (fin < hi)).mean(), 0)) for label, lo, hi in bands]
    return dict(bands=[b[0] for b in bands], rows=rows, current=cur, latest=num(vix[li]),
                latest_at=g.months[li], share=share)


def flowmap(g, series):
    """Legacy payload key: relative price performance, never measured fund flows."""
    out = []
    for sid, label in C.FLOWMAP:
        st = (series.get(sid) or {}).get("stats")
        if st:
            meta = series[sid]
            out.append(dict(id=sid, label=label, r1=st["c1"], r3=st["c3"], r12=st["c12"], asof=st["last"],
                            measure="relative_price_change", source=meta.get("source", "未標示"),
                            basis=meta.get("note", "")))
    return out


def leaders(g):
    out = {}
    for mkt, cfg in C.LEADERS.items():
        idx = g.done(changes(g.arr[cfg["index"]], "price")) if cfg["index"] in g.arr else None
        rows = []
        for ticker, name, cnyes, _ in cfg["items"]:
            sid = f"lead_{mkt}_{ticker}"
            if sid not in g.arr:
                rows.append(dict(id=sid, ticker=ticker, name=name, cnyes=cnyes, missing=True))
                continue
            a = g.arr[sid]
            st = series_stats(a, "price", g.months)
            beta = corr = None
            if idx is not None:
                x = g.done(changes(a, "price"))[-60:]
                y = idx[-60:]
                corr, n = pcorr(x, y, 24)
                m = np.isfinite(x) & np.isfinite(y)
                if n >= 24 and y[m].var() > 0:
                    beta = float(np.cov(x[m], y[m])[0, 1] / y[m].var(ddof=1))
            rows.append(dict(id=sid, ticker=ticker, name=name, cnyes=cnyes, stats=st, beta=num(beta),
                             corr=num(corr), values=[compact(v) for v in a]))
        out[mkt] = dict(title=cfg["title"], index=cfg["index"], items=rows)
    return out


def reserves_ca(g, annual):
    if not annual:
        return None, None
    years = list(range(1995, dt.date.today().year + 1))

    def block(key):
        data = annual.get(key) or {}
        rows = []
        for code, name in C.RESERVE_COUNTRIES:
            vals = data.get(code) or {}
            rows.append(dict(code=code, name=name, values=[num(vals[str(y)] / 1e9, 1) if str(y) in vals else None
                                                           for y in years]))
        return rows

    res = dict(years=years, countries=block("reserves"), note="世界銀行年資料（含黃金），十億美元")
    tw = annual.get("tw_reserves") or {}
    tw_arr = [num(tw[m] / 1000, 1) if m in tw else None for m in g.months]  # 百萬美元 → 十億美元
    res["tw_monthly"] = tw_arr
    res["tw_annual"] = [num(tw[f"{y}-12"] / 1000, 1) if f"{y}-12" in tw else None for y in years]
    if tw:
        last = max(tw)
        prev = f"{int(last[:4]) - 1}{last[4:]}"
        res["tw_latest"] = dict(month=last, value=num(tw[last] / 1000, 1),
                                c12=num((tw[last] - tw[prev]) / 1000, 1) if prev in tw else None)
    ca = dict(years=years, countries=block("current_account"), note="世界銀行經常帳餘額，十億美元")
    return res, ca


def strength_block(annual, series):
    """國力面板：GDP、成長、CPI、政策利率（與扣掉通膨的實質利率）、經常帳／GDP、外匯存底。
    課堂：貨幣長期反映國力，利率只決定短期套利；費雪方程式把名目利率拆成實質利率＋預期通膨，這裡用最近一年 CPI 近似。"""
    if not annual:
        return None
    blocks = {k: annual.get(k) or {} for k in ("gdp", "gdp_growth", "cpi", "ca_gdp", "reserves", "policy")}

    def latest(d):
        return (max(d), d[max(d)]) if d else (None, None)

    rows = []
    for rank, (code, name) in enumerate(C.RESERVE_COUNTRIES, start=1):
        gy, gv = latest(blocks["gdp"].get(code))
        gry, grv = latest(blocks["gdp_growth"].get(code))
        cy, cv = latest(blocks["cpi"].get(code))
        cay, cav = latest(blocks["ca_gdp"].get(code))
        ry, rv = latest(blocks["reserves"].get(code))
        py, pv = latest(blocks["policy"].get(C.BIS_POLICY_AREA.get(code)))
        rows.append(dict(code=code, name=name, rank=rank, gdp=num(gv / 1e9, 0) if gv else None, gdp_year=gy,
                         growth=num(grv, 1), growth_year=gry, cpi=num(cv, 1), cpi_year=cy,
                         policy=num(pv, 2), policy_at=py, policy_src="ECB" if C.BIS_POLICY_AREA.get(code) == "XM" else None,
                         real=num(pv - cv, 1) if pv is not None and cv is not None else None,
                         ca_gdp=num(cav, 1), ca_year=cay, reserves=num(rv / 1e9, 0) if rv else None))
    tw_disc = (series.get("b_tw_disc") or {}).get("stats") or {}
    tw = annual.get("tw_reserves") or {}
    rows.append(dict(code="TWN", name="台灣", rank=None, gdp=None, gdp_year=None, growth=None, growth_year=None,
                     cpi=None, cpi_year=None, policy=tw_disc.get("value"), policy_at=tw_disc.get("last"), policy_src="央行重貼現率",
                     real=None, ca_gdp=None, ca_year=None, reserves=num(tw[max(tw)] / 1000, 0) if tw else None))
    return dict(rows=rows, note="GDP、成長率、CPI 年增率、經常帳／GDP：世界銀行年資料；政策利率：國際清算銀行月底值（德、法、義為歐洲央行存款機制利率）；"
                                "台灣：央行重貼現率，其餘欄位世界銀行沒有台灣。實質利率＝政策利率 − 最近一年 CPI 年增率，是費雪方程式的粗略版。")


def curve_block(g, detail):
    """殖利率曲線的形狀（今天 vs 1／3／10／20 年前）與 1995 年以來的倒掛期間，附倒掛後股市與衰退怎麼走。"""
    items = (detail or {}).get("items") or {}
    if not all(sid in items for sid, _t, _l in C.CURVE_TENORS):
        return None
    epoch = dt.date(1970, 1, 1)
    today_days = (dt.date.today() - epoch).days

    def value_at(part, day):
        """part＝[天數[], 值[]]：取 ≤ day 的最後一筆。"""
        days, vals = part
        i = bisect.bisect_right(days, day) - 1
        return (vals[i], days[i]) if i >= 0 else (None, None)

    snapshots = []
    for years, label in C.CURVE_SNAPSHOTS:
        target = today_days - round(365.25 * years)
        vals, dates = [], []
        for sid, _tenor, _l in C.CURVE_TENORS:
            it = items[sid]
            part = it["d"] if years == 0 else it["w"] if years <= 12 else it["m"]
            v, d = value_at(part, target)
            vals.append(num(v, 2))
            dates.append((epoch + dt.timedelta(days=d)).isoformat() if d is not None else None)
        snapshots.append(dict(key=f"y{years}", label=label, values=vals, as_of=max(x for x in dates if x) if any(dates) else None))

    # 倒掛期間：月資料（1995 起），連續 <0 的月份算一段
    curve = g.arr.get("d_curve")
    spx = g.arr.get("eq_spx")
    episodes = []
    if curve is not None:
        i = 0
        n = g.end + 1
        while i < n:
            if np.isfinite(curve[i]) and curve[i] < 0:
                j = i
                while j + 1 < n:
                    # 連續 <0 就延伸；中間最多 3 個月回正（例：2007-05～06）仍算同一段，和傳導鏈的事件合併規則一致
                    nxt = next((k for k in range(j + 1, min(j + 4, n)) if np.isfinite(curve[k]) and curve[k] < 0), None)
                    if nxt is None:
                        break
                    j = nxt
                seg = curve[i:j + 1]
                k = int(np.nanargmin(seg))
                rec = next((r for r in C.NBER_RECESSION_STARTS if g.months[i] <= r <= g.months[min(j + 24, n - 1)]), None)
                rec_lag = (int(rec[:4]) * 12 + int(rec[5:7])) - (int(g.months[i][:4]) * 12 + int(g.months[i][5:7])) if rec else None

                def fwd(m):
                    if spx is None or i + m >= n or not (np.isfinite(spx[i]) and np.isfinite(spx[i + m])) or spx[i] <= 0:
                        return None
                    return num(100 * (spx[i + m] / spx[i] - 1), 1)
                # 只倒掛 1 個月且很淺（例：2020-02 −0.10、2025-04 −0.01）視為雜訊，不歸因衰退
                noise = (j - i + 1) == 1 and float(seg[k]) > -0.25
                episodes.append(dict(start=g.months[i], end=g.months[j], months=j - i + 1, min=num(float(seg[k]), 2), noise=noise,
                                     min_at=g.months[i + k], ongoing=j == n - 1, spx12=fwd(12), spx24=fwd(24),
                                     recession=rec, recession_lag=rec_lag))
                i = j + 1
            else:
                i += 1
    latest_curve, latest_day = value_at(items["d_curve"]["d"], today_days) if "d_curve" in items else (None, None)
    return dict(tenors=[dict(sid=s, x=t, label=l) for s, t, l in C.CURVE_TENORS], snapshots=snapshots, episodes=episodes,
                latest=num(latest_curve, 2), latest_at=(epoch + dt.timedelta(days=latest_day)).isoformat() if latest_day else None,
                recessions=C.NBER_RECESSION_STARTS,
                note="短天期（3 個月）貼著政策利率；長天期（10、30 年）反映長期成長與通膨預期加期限溢酬。"
                     "正常是往上斜；倒掛＝短率高於長率，市場預期未來降息。倒掛期間用月底值判定（10 年 − 3 個月 < 0），"
                     "「之後」欄是從倒掛起算月的 S&P 500 價格變動與 NBER 認定的下一次衰退起點。"
                     "資料是月底值。")


def reserves_table(annual, tic_blk):
    """GDP 前十大國家＋台灣：外匯存底、可支應進口月數、存底／GDP、持有美債與其占存底比例。
    1997 年的教訓：存底不足（常用門檻＝三個月進口）又釘住匯率的國家最容易被攻擊；
    浮動匯率的準備貨幣國（美、英、加）存底本來就少，門檻對它們意義不大，表上照列但註明。"""
    if not annual:
        return None
    res, months, gdp = (annual.get(k) or {} for k in ("reserves", "reserves_months", "gdp"))
    holders = {h["key"]: h for h in (tic_blk or {}).get("holders", [])}

    def latest(d):
        if not d:
            return None, None
        y = max(d)
        return y, d[y]

    rows = []
    for rank, (code, name) in enumerate(C.RESERVE_COUNTRIES, start=1):
        ry, rv = latest(res.get(code))
        prev = (res.get(code) or {}).get(str(int(ry) - 1)) if ry else None
        my, mv = latest(months.get(code))
        gy, gv = latest(gdp.get(code))
        same_year = (gdp.get(code) or {}).get(ry) if ry else None
        h = holders.get(C.RESERVE_TIC_KEY.get(code))
        rows.append(dict(code=code, name=name, rank=rank,
                         reserves=num(rv / 1e9, 1) if rv else None, reserves_year=ry,
                         c12=num((rv - prev) / 1e9, 1) if rv and prev else None,
                         c12_pct=num(100 * (rv - prev) / prev, 1) if rv and prev else None,
                         months=num(mv, 1) if mv is not None else None, months_year=my,
                         gdp=num(gv / 1e9, 0) if gv else None, gdp_year=gy,
                         res_gdp=num(100 * rv / same_year, 1) if rv and same_year else None,
                         ust=h["latest"] if h else None, ust_at=h["latest_at"] if h else None,
                         ust_pct=num(100 * h["latest"] / (rv / 1e9), 0) if h and h.get("latest") and rv else None,
                         low_cover=bool(mv is not None and mv < C.RESERVE_IMPORT_MONTHS_MIN),
                         reserve_currency=code in ("USA", "GBR", "CAN")))
    tw = annual.get("tw_reserves") or {}
    if tw:
        last = max(tw)
        prev = f"{int(last[:4]) - 1}{last[4:]}"
        h = holders.get("taiwan")
        rv = tw[last] / 1000
        rows.append(dict(code="TWN", name="台灣", rank=None, reserves=num(rv, 1), reserves_year=last,
                         c12=num((tw[last] - tw[prev]) / 1000, 1) if prev in tw else None,
                         c12_pct=num(100 * (tw[last] - tw[prev]) / tw[prev], 1) if prev in tw else None,
                         months=None, months_year=None, gdp=None, gdp_year=None, res_gdp=None,
                         ust=h["latest"] if h else None, ust_at=h["latest_at"] if h else None,
                         ust_pct=num(100 * h["latest"] / rv, 0) if h and h.get("latest") else None,
                         low_cover=False, reserve_currency=False))
    return dict(rows=rows, months_min=C.RESERVE_IMPORT_MONTHS_MIN,
                note="存底與 GDP：世界銀行年資料（存底含黃金），十億美元；台灣存底：央行月資料（不含黃金）。"
                     "進口月數＝存底可支付幾個月的商品與服務進口（世界銀行）。美債持有：美國財政部 TIC 月底數，"
                     "含該國官方與民間所有持有者，英國等託管中心的數字含替他國保管的部位，所以「占存底」可能超過 100%。")


def tic(annual):
    data = (annual or {}).get("tic") or {}
    allm = sorted({m for v in data.values() for m in v})
    if not allm:
        return None
    months = month_range(allm[0], allm[-1])
    rows = []
    total = data.get("grand total") or {}
    for key, name in C.TIC_HOLDERS:
        vals = data.get(key) or {}
        last = max(vals) if vals else None
        prev = f"{int(last[:4]) - 1}{last[4:]}" if last else None
        rows.append(dict(key=key, name=name, values=[vals.get(m) for m in months],
                         latest=vals.get(last), latest_at=last,
                         c12=num(vals[last] - vals[prev], 1) if last and prev in vals else None,
                         share=num(100 * vals[last] / total[last], 1) if last and total.get(last) and key != "grand total" else None))
    return dict(months=months, holders=rows, note="十億美元，月底持有量")


def company_cf(cf):
    if not cf:
        return None
    out = {}
    for mkt, scale, unit in (("us", 1e9, "十億美元"), ("tw", 1e8, "億元")):
        rows = []
        for r in cf.get(mkt, []):
            years = [dict(end=y["end"], ocf=num(y["ocf"] / scale, 2),
                          capex=num(y["capex"] / scale, 2) if y.get("capex") is not None else None,
                          fcf=num(y["fcf"] / scale, 2) if y.get("fcf") is not None else None)
                     for y in r["years"]]
            last = years[-1] if years else {}
            cagr = None
            if len(years) >= 6 and years[-6].get("ocf") and years[-6]["ocf"] > 0 and last.get("ocf", 0) > 0:
                cagr = num(((last["ocf"] / years[-6]["ocf"]) ** (1 / 5) - 1) * 100, 1)
            rows.append(dict(ticker=r["ticker"], name=r["name"], entity=r.get("entity"), years=years[-20:],
                             latest=last, ocf_cagr5=cagr))
        out[mkt] = dict(unit=unit, items=rows)
    out["note"] = "美股：SEC EDGAR 10-K 年度營業現金流與資本支出；台股：FinMind 年度現金流量表。自由現金流＝營業現金流－資本支出；金融股的自由現金流不具比較意義。"
    return out


def findings(series, comp, pr, flow, vix, tic_blk, res):
    out = []

    def add(tab, tone, title, text):
        out.append(dict(tab=tab, tone=tone, title=title, text=text))

    if comp and comp["latest"] is not None:
        cs = [c for c in comp["components"] if c["latest"] is not None]
        lo = min(cs, key=lambda c: c["latest"])
        hi = max(cs, key=lambda c: c["latest"])
        add("overview", "up" if comp["latest"] > 0.5 else "down" if comp["latest"] < -0.5 else "neutral",
            f"風險偏好代理指數 {comp['latest']:+.2f}（{comp['state']}）",
            f"截至 {comp['latest_at']}，位於 1995 年以來第 {comp['percentile']:.0f} 百分位。"
            f"最推升的是「{hi['name']}」（z {hi['latest']:+.2f}），最拖累的是「{lo['name']}」（z {lo['latest']:+.2f}）。")
    if flow:
        rank = sorted([f for f in flow if f["r3"] is not None], key=lambda f: f["r3"], reverse=True)
        if len(rank) >= 4:
            top = "、".join(f"{f['label']} {f['r3']:+.1f}%" for f in rank[:3])
            bot = "、".join(f"{f['label']} {f['r3']:+.1f}%" for f in rank[-3:][::-1])
            add("overview", "neutral", "近 3 個月跨資產相對強弱", f"最強：{top}；最弱：{bot}。依價格變動排序，未量測資金淨流入或淨流出。")
    for p in pr:
        if p["r_full"] is None or p["r_recent"] is None:
            continue
        d = p["r_recent"] - p["r_full"]
        flip = p["r_recent"] * p["r_full"] < 0 and min(abs(p["r_recent"]), abs(p["r_full"])) > 0.15
        if abs(d) >= 0.3 or flip:
            kind = "翻轉" if flip else ("增強" if abs(p["r_recent"]) > abs(p["r_full"]) else "減弱")
            add("research", "alert", f"關係{kind}：{p['label']}",
                f"近 {ROLL} 個月 r = {p['r_recent']:+.2f}，1995 年以來 r = {p['r_full']:+.2f}（n={p['n_full']}）。{p['why']}")
        if p["lead"]:
            k = p["lead"]["k"]
            who, whom = (series[p["a"]]["name"], series[p["b"]]["name"]) if k > 0 else (series[p["b"]]["name"], series[p["a"]]["name"])
            add("research", "neutral", f"領先落後：{who} → {whom}",
                f"{who}的月變動與 {abs(k)} 個月後的{whom}相關 r = {p['lead']['r']:+.2f}（n={p['lead']['n']}，"
                f"顯著門檻 ±{p['sig']:.2f}），高於同期相關。樣本內統計，不代表可交易訊號。")
    if vix:
        spx = next((r for r in vix["rows"] if r["id"] == "eq_spx"), None)
        band = next((b for b in spx["bands"] if b["label"] == vix["current"]), None) if spx else None
        if band and band["f3"].get("n"):
            add("vol", "alert" if vix["latest"] >= 30 else "neutral", f"VIX {vix['latest']:.1f}：{vix['current']}",
                f"1995 年以來 VIX 處於此區間的月份，S&P 500 之後 3 個月報酬中位數 {band['f3']['median']:+.1f}%、"
                f"上漲機率 {band['f3']['hit']:.0f}%（n={band['f3']['n']}）。")
    cur = (series.get("d_curve") or {}).get("stats")
    if cur:
        add("bond", "alert" if cur["value"] < 0 else "neutral",
            f"美債 10 年 − 3 個月利差 {cur['value']:+.2f} 個百分點",
            ("殖利率曲線倒掛中，" if cur["value"] < 0 else "曲線維持正斜率，")
            + f"近 12 個月變動 {cur['c12']:+.0f}bp。" if cur.get("c12") is not None else "")
    dxy = (series.get("fx_dxy") or {}).get("stats")
    if dxy and dxy.get("c3") is not None:
        add("fx", "neutral", f"美元指數近 3 個月 {dxy['c3']:+.1f}%",
            f"近 12 個月 {dxy['c12']:+.1f}%，目前位於 1995 年以來第 {dxy['pct']:.0f} 百分位。"
            + "匯率變化本身不足以判定跨境資金淨流量。")
    if tic_blk:
        parts = [f"{h['name']} {h['c12']:+.0f}" for h in tic_blk["holders"] if h["c12"] is not None and h["key"] != "grand total"]
        if parts:
            last = tic_blk["holders"][0]["latest_at"]
            add("flow", "neutral", f"外國持有美債 12 個月變化（至 {last}，十億美元）", "、".join(parts) + "。")
    if res and res.get("tw_latest"):
        t = res["tw_latest"]
        add("fx", "neutral", f"台灣外匯存底 {t['value']:.1f} 十億美元（{t['month']}）",
            f"較一年前 {t['c12']:+.1f} 十億美元。" if t.get("c12") is not None else "")
    return out


def run(log=print):
    sraw = _load("series.json")
    if not sraw or not sraw.get("values"):
        raise SystemExit("找不到 data/raw/series.json，請先執行：python3 gfd.py history")
    g = Grid(sraw["values"])
    series = build_series(g, sraw["values"])
    comp = composite(g)
    pr = pairs(g, series)
    flow = flowmap(g, series)
    vix = vix_regimes(g)
    annual = _load("annual.json", {})
    res, ca = reserves_ca(g, annual)
    tic_blk = tic(annual)
    if res:
        res["table"] = reserves_table(annual, tic_blk)
    curve = curve_block(g, _load("detail.json"))
    strength = strength_block(annual, series)
    chain_block, chain_findings = CH.build(g, series, g.months, log=log)
    play = PB.build(g, series, g.months, log=log)
    for t in [x for x in play["triggers"] if x["active"]][:6]:
        best = [r for h in play["horizons"] for r in t["assets"][str(h)]["robust"]]
        best.sort(key=lambda r: r["lift"], reverse=True)
        txt = (f"歷史上出現過 {t['episodes']} 次。" +
               (f"通過三道檢驗的資產：{'、'.join(f'{r['name']}（超額 {r['lift']:+.1f}{r['unit']}）' for r in best[:3])}。"
                if best else "事件後沒有任何資產通過穩健檢驗（事件數、前後半期一致、位移檢定）。"))
        chain_findings.append(dict(tab="playbook", tone="alert" if best else "neutral",
                                   title=f"訊號成立中：{t['label']}", text=txt))
    cas = CA.build(log=log)
    if cas:
        cas["analogs"] = AN.build(cas, log=log)
    # 沙盤推演是在其他分析之上的推估：它出錯不能拖垮每日更新（排程會跑這裡），記錄錯誤、分頁顯示「尚未產生」
    try:
        scen = SC.build(g, series, g.months, play, chain_block, cas, log=log)
    except Exception as exc:          # noqa: BLE001
        import traceback
        log(f"[scenario] 失敗，這次略過沙盤推演：{exc!r}\n{traceback.format_exc()}")
        scen = None
    out = dict(
        generated_at=dt.datetime.now(TPE).isoformat(timespec="seconds"),
        fetched_at=sraw.get("fetched_at"),
        months=g.months, complete_end=g.months[g.end],
        observe=C.OBSERVE_REASONS, curve=curve, strength=strength,
        series=series, corr=correlations(g, series), pairs=pr, events=events(g, series),
        composite=comp, vix=vix, flowmap=flow, leaders=leaders(g),
        reserves=res, current_account=ca, tic=tic_blk, company_cf=company_cf(_load("company_cf.json")),
        chains=chain_block, playbook=play, cascade=cas, scenario=scen,
        findings=findings(series, comp, pr, flow, vix, tic_blk, res) + chain_findings,
        coverage=(_load("coverage.json") or {}).get("items", []),
        gaps=[dict(item=a, reason=b, proxy=c) for a, b, c in C.GAPS],
        events_cfg=[dict(id=a, name=b, start=c, end=d) for a, b, c, d in C.EVENTS],
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"[analysis] {len(series)} 條序列、{len(pr)} 組配對、{len(out['findings'])} 則重點 → {OUT} "
        f"({OUT.stat().st_size / 1024:.0f} KB)")
    return out
