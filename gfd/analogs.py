"""現在最像哪幾次事件：把「今天」的市場狀態和 88 個歷史事件發生時的狀態比對，找出最像的幾次，
看它們在「見報之後」兩週／一個月／兩個月錢往哪流。

狀態＝事件前一天收盤時的市場環境（股市漲跌、回檔深度、波動、利率、殖利率曲線、美元、黃金、原油、高收益債）
＋事件第一天的反應幅度（以各自事前 60 日波動為單位）。今天的狀態：把最新一個收盤當成「第一天」。
結果從第一天收盤起算——也就是看到新聞之後才進場，才是做得到的報酬。

這個方法有沒有用不能假設，要驗：對每個歷史事件，假裝不知道它的結果，用「最像的其他事件」預測它
事後比平常漲多還跌多，和「同類型事件」「隨機挑的事件」比命中率。沒有比較好就照實寫。
"""
import bisect
import datetime as dt
import hashlib
import json
import pathlib

import numpy as np

from . import config as C

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"

# 今天的狀態要用每天更新的 detail.json 補上 daily_cascade.json（一週才全量重抓一次）之後的收盤
DETAIL_IDS = {"^GSPC": "eq_spx", "^TNX": "b_us10y", "^IRX": "b_us3m", "DX-Y.NYB": "fx_dxy", "GC=F": "c_gold",
              "CL=F": "c_wti", "HYG": "b_hyg", "^NDX": "eq_ndx", "^SOX": "eq_sox", "^TWII": "eq_twii",
              "^N225": "eq_n225", "^HSI": "eq_hsi", "TLT": "b_ust_long", "^VIX": "v_vix"}

# (代碼, 標籤, 種類, 參數, 單位)。種類：chg＝n 日變動、dd＝距一年高點、vol＝20 日年化波動、
# curve＝10 年減 3 個月、z1＝第一天反應（事前 60 日波動的倍數）
FEATURES = [
    ("spx20", "S&P 500 近 20 日", "chg", ("^GSPC", 20), "%"),
    ("spx60", "S&P 500 近 60 日", "chg", ("^GSPC", 60), "%"),
    ("spxdd", "S&P 500 距一年高點", "dd", ("^GSPC",), "%"),
    ("spxvol", "S&P 500 20 日波動（年化）", "vol", ("^GSPC",), "%"),
    ("tnx20", "美 10 年殖利率近 20 日", "chg", ("^TNX", 20), "bp"),
    ("tnx60", "美 10 年殖利率近 60 日", "chg", ("^TNX", 60), "bp"),
    ("curve", "殖利率曲線（10 年減 3 個月）", "curve", (), "pp"),
    ("dxy20", "美元指數近 20 日", "chg", ("DX-Y.NYB", 20), "%"),
    ("gold20", "黃金近 20 日", "chg", ("GC=F", 20), "%"),
    ("wti20", "WTI 原油近 20 日", "chg", ("CL=F", 20), "%"),
    ("hy20", "高收益債近 20 日", "chg", ("HYG", 20), "%"),
    ("spx_z1", "第一天 S&P 500 反應", "z1", ("^GSPC",), "σ"),
    ("tnx_z1", "第一天 10 年殖利率反應", "z1", ("^TNX",), "σ"),
    ("dxy_z1", "第一天美元反應", "z1", ("DX-Y.NYB",), "σ"),
    ("gold_z1", "第一天黃金反應", "z1", ("GC=F",), "σ"),
    ("wti_z1", "第一天原油反應", "z1", ("CL=F",), "σ"),
    ("hy_z1", "第一天高收益債反應", "z1", ("HYG",), "σ"),
]
K = 5                 # 取最像的幾次
MIN_SHARED = 0.6      # 兩個狀態至少要有六成特徵都有資料才比
GAP_DAYS = 60         # 回測時排除相隔 60 天內的事件（視窗重疊會洩漏答案）
RANDOM_ROUNDS = 300


def _is_rate(sym):
    return sym in ("^TNX", "^IRX")


def _load():
    daily = json.loads((RAW / "daily_cascade.json").read_text(encoding="utf-8"))["series"]
    p = RAW / "detail.json"
    items = json.loads(p.read_text(encoding="utf-8")).get("items", {}) if p.exists() else {}
    out = {}
    for sym, rec in daily.items():
        dates, closes = list(rec["dates"]), list(rec["closes"])
        det = items.get(DETAIL_IDS.get(sym, ""), {}).get("d")
        if det and dates:
            # detail 的 d＝[距 1970-01-01 天數, 收盤]；只接在歷史最後一天之後，接點以同一天的價位對齊
            ep = dt.date(1970, 1, 1)
            ddates = [(ep + dt.timedelta(days=int(x))).isoformat() for x in det[0]]
            m = dict(zip(ddates, det[1]))
            k = (closes[-1] / m[dates[-1]]) if m.get(dates[-1]) and not _is_rate(sym) else 1.0
            for d, v in zip(ddates, det[1]):
                if d > dates[-1] and v is not None:
                    dates.append(d)
                    closes.append(v * k)
        out[sym] = dict(name=rec["name"], dates=dates, closes=np.asarray(closes, dtype=float))
    return out


def _chg(c, a, b, sym):
    if a < 0 or b >= len(c) or not (np.isfinite(c[a]) and np.isfinite(c[b])):
        return None
    if _is_rate(sym):
        return (c[b] - c[a]) * 100
    if c[a] <= 0 or c[b] <= 0:
        return None
    return 100 * np.log(c[b] / c[a])


def _sigma(c, i, sym):
    seg = c[max(0, i - 60):i + 1]
    with np.errstate(all="ignore"):
        d = np.diff(seg) * 100 if _is_rate(sym) else 100 * np.diff(np.log(seg))
    d = d[np.isfinite(d)]
    return float(np.std(d)) if len(d) >= 30 else None


def _base_index(s, date):
    """事件前最後一個收盤的位置（事件日當天及之後的不算）。"""
    return bisect.bisect_left(s["dates"], date) - 1


def state(data, date):
    """date＝事件日（第一天）。回傳 {特徵: 值}，缺資料的特徵不列。"""
    out = {}
    for key, _label, kind, args, _unit in FEATURES:
        v = None
        if kind == "curve":
            t, i3 = data.get("^TNX"), data.get("^IRX")
            if t and i3:
                a, b = _base_index(t, date), _base_index(i3, date)
                if a >= 0 and b >= 0:
                    v = t["closes"][a] - i3["closes"][b]
        else:
            sym = args[0]
            s = data.get(sym)
            if not s:
                continue
            i = _base_index(s, date)
            c = s["closes"]
            if i < 252:
                continue
            if kind == "chg":
                v = _chg(c, i - args[1], i, sym)
            elif kind == "dd":
                v = 100 * np.log(c[i] / np.nanmax(c[i - 251:i + 1]))
            elif kind == "vol":
                with np.errstate(all="ignore"):
                    v = float(np.nanstd(np.diff(np.log(c[i - 20:i + 1])))) * np.sqrt(252) * 100
            elif kind == "z1":
                sg = _sigma(c, i, sym)
                d1 = _chg(c, i, i + 1, sym)
                # 第一天必須真的在事件日當天或之後（停市時順延），而且在 5 天內
                if sg and d1 is not None and s["dates"][i + 1] >= date and \
                        (dt.date.fromisoformat(s["dates"][i + 1]) - dt.date.fromisoformat(date)).days <= 7:
                    v = d1 / sg
        if v is not None and np.isfinite(v):
            out[key] = float(v)
    return out


def outcome(data, date, sym, w):
    """見報之後才進場：第一天收盤起算 w 個交易日的變動。"""
    s = data.get(sym)
    if not s:
        return None
    i = _base_index(s, date) + 1
    if i < 1 or i + w >= len(s["closes"]):
        return None
    return _chg(s["closes"], i, i + w, sym)


def _norm(data):
    """每個特徵在全部歷史中的平均與標準差（每 5 天取一次樣），用來把不同單位放到同一把尺上。"""
    spx = data["^GSPC"]["dates"]
    vals = {k: [] for k, *_ in FEATURES}
    for d in spx[300:-1:5]:                       # 把每個取樣日都當成「第一天」
        for k, v in state(data, d).items():
            vals[k].append(v)
    out = {}
    for k, v in vals.items():
        a = np.asarray(v)
        if len(a) > 100:
            out[k] = (float(np.mean(a)), float(np.std(a)) or 1.0, a)
    return out


def _z(st, norm):
    return {k: float(np.clip((v - norm[k][0]) / norm[k][1], -4, 4)) for k, v in st.items() if k in norm}


def distance(za, zb):
    keys = [k for k in za if k in zb]
    if len(keys) < MIN_SHARED * len(FEATURES):
        return None
    return float(np.sqrt(np.mean([(za[k] - zb[k]) ** 2 for k in keys])))


def _backtest(states, outs, targets, wins, predict, excess, ev):
    """對每個歷史事件，假裝不知道結果：用最像的 K 個其他事件、同類型事件、隨機 K 個事件，
    分別預測它事後「比平常漲多還跌多」，比命中率。"""
    rng = np.random.default_rng(20260929)
    hits = {m: {w: [0, 0] for w in wins} for m in ("analog", "category", "random")}
    # 隨機組每一輪各自的命中數：相似事件法要比「大多數隨機輪」好，才算有用
    per_round = {w: np.zeros((RANDOM_ROUNDS, 2)) for w in wins}
    for e in C.SHOCK_EVENTS:
        eid, d0 = e["id"], dt.date.fromisoformat(e["date"])
        cands = [o["id"] for o in C.SHOCK_EVENTS if o["id"] != eid
                 and abs((dt.date.fromisoformat(o["date"]) - d0).days) > GAP_DAYS]
        dists = sorted((dd, o) for o in cands if (dd := distance(states[eid], states[o])) is not None)
        near = [o for _, o in dists[:K]]
        same = [o for o in cands if ev[o]["cat"] == e["cat"]]
        rnd = [list(rng.choice(cands, size=min(K, len(cands)), replace=False)) for _ in range(RANDOM_ROUNDS)]
        for s in targets:
            for w in wins:
                act = excess(outs[eid][s][w], s, w)
                if act is None or act == 0:
                    continue
                for m, pool in (("analog", near), ("category", same)):
                    if len(pool) < 3:
                        continue
                    p = predict(pool, s, w)
                    if p is not None and p != 0:
                        hits[m][w][0] += int((p > 0) == (act > 0))
                        hits[m][w][1] += 1
                ok = n = 0
                for ri, pool in enumerate(rnd):
                    p = predict(pool, s, w)
                    if p is not None and p != 0:
                        hit = int((p > 0) == (act > 0))
                        ok += hit
                        n += 1
                        per_round[w][ri] += (hit, 1)
                if n:
                    hits["random"][w][0] += ok / n
                    hits["random"][w][1] += 1
    backtest = {m: {str(w): dict(hit=round(100 * a / b, 1) if b else None, n=b) for w, (a, b) in hw.items()}
                for m, hw in hits.items()}
    for w in wins:
        rates = 100 * per_round[w][:, 0] / np.maximum(per_round[w][:, 1], 1)
        for m in ("analog", "category"):
            h = backtest[m][str(w)]["hit"]
            # 隨機挑 5 次事件的 300 輪中，有幾成命中率不輸這個方法（＝這個方法純靠運氣的機率）
            backtest[m][str(w)]["p_vs_random"] = round(float(np.mean(rates >= h)), 3) if h is not None else None
        backtest["random"][str(w)].update(p5=round(float(np.percentile(rates, 5)), 1),
                                          p95=round(float(np.percentile(rates, 95)), 1))

    return backtest


def build(cascade, log=print):
    if not cascade or not (RAW / "daily_cascade.json").exists():
        return None
    data = _load()
    norm = _norm(data)
    ev = {e["id"]: e for e in C.SHOCK_EVENTS}
    base = {u["id"]: u["base"] for u in cascade["universe"]}
    targets = [s for s in cascade["compare"] if s in data]
    wins = C.CASCADE_WINDOWS

    states = {e["id"]: _z(state(data, e["date"]), norm) for e in C.SHOCK_EVENTS}
    raw_states = {e["id"]: state(data, e["date"]) for e in C.SHOCK_EVENTS}
    outs = {e["id"]: {s: {w: outcome(data, e["date"], s, w) for w in wins} for s in targets} for e in C.SHOCK_EVENTS}

    def excess(v, s, w):
        b = base.get(s, {}).get(f"w{w}")
        return None if v is None or b is None else v - b

    def predict(pool, s, w):
        xs = [excess(outs[p][s][w], s, w) for p in pool]
        xs = [x for x in xs if x is not None]
        return float(np.median(xs)) if len(xs) >= 3 else None

    # ── 回測：留一法（只取決於歷史日線與事件清單，快取起來，排程每天只重算「今天」）──
    key = hashlib.sha1(json.dumps([json.loads((RAW / "daily_cascade.json").read_text(encoding="utf-8")).get("fetched_at"),
                                   C.SHOCK_EVENTS, FEATURES, K, MIN_SHARED, GAP_DAYS, RANDOM_ROUNDS, targets, wins,
                                   base], ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()
    cache_p = RAW / "analogs_backtest.json"
    cached = json.loads(cache_p.read_text(encoding="utf-8")) if cache_p.exists() else {}
    backtest = cached.get("backtest") if cached.get("key") == key else None
    if backtest is None:
        backtest = _backtest(states, outs, targets, wins, predict, excess, ev)
        cache_p.write_text(json.dumps(dict(key=key, backtest=backtest), ensure_ascii=False), encoding="utf-8")

    # ── 今天 ──
    spx = data["^GSPC"]["dates"]
    today = spx[-1]                                  # 把最新一個收盤當成「第一天」
    now_raw = state(data, today)
    now_z = _z(now_raw, norm)
    ranked = sorted((dd, e["id"]) for e in C.SHOCK_EVENTS if (dd := distance(now_z, states[e["id"]])) is not None)
    near = [eid for _, eid in ranked[:K]]
    pct = {k: round(float(100 * np.mean(norm[k][2] <= v)), 0) for k, v in now_raw.items() if k in norm}

    rows = []
    for s in targets:
        u = next(x for x in cascade["universe"] if x["id"] == s)
        row = dict(id=s, name=u["name"], unit="bp" if _is_rate(s) else ("pt" if s == "^VIX" else "%"))
        for w in wins:
            vals = [outs[e][s][w] for e in near]
            ok = [v for v in vals if v is not None]
            row[f"w{w}"] = [None if v is None else round(v, 2) for v in vals]
            row[f"med{w}"] = round(float(np.median(ok)), 2) if len(ok) >= 3 else None
            row[f"base{w}"] = base.get(s, {}).get(f"w{w}")
            row[f"n{w}"] = len(ok)
            row[f"up{w}"] = round(100 * float(np.mean(np.array(ok) > 0)), 0) if ok else None
        rows.append(row)

    feats = [dict(id=k, label=lab, unit=unit) for k, lab, _kind, _a, unit in FEATURES]
    analogs = [dict(id=eid, name=ev[eid]["name"], date=ev[eid]["date"], cat=ev[eid]["cat"], dist=round(dd, 2),
                    state={k: round(v, 2) for k, v in raw_states[eid].items()})
               for dd, eid in ranked[:K]]
    far = [dict(id=eid, name=ev[eid]["name"], date=ev[eid]["date"], dist=round(dd, 2)) for dd, eid in ranked[-3:]]
    b21 = backtest["analog"]["21"]
    log(f"[analogs] 今天（{today}）最像：{'、'.join(ev[e]['name'] for e in near)}；"
        f"回測一個月超額方向命中率 相似事件 {b21['hit']}%／同類型 {backtest['category']['21']['hit']}%"
        f"／隨機 {backtest['random']['21']['hit']}%")
    return dict(today=today, now={k: round(v, 2) for k, v in now_raw.items()}, pct=pct, features=feats,
                analogs=analogs, farthest=far, assets=rows, backtest=backtest, k=K, windows=wins,
                last_dates={s: data[s]["dates"][-1] for s in ("^GSPC", "^TNX", "DX-Y.NYB", "GC=F", "CL=F", "HYG")
                            if s in data})
