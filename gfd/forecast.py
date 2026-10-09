"""短期預測帳本 v1（2026-10-09）：日線、10／21 個交易日，每個 ISO 週一批，只增不改，到期自動對答案。

為什麼這樣做（研究結論，不要在這裡重做）：2008 年起每週走步、22 個資產，趨勢／動能／離年線／短期反轉／VIX 查表
對「比平常強或弱」的多空命中都約 50%，IC 約 0；方向命中 55～57% 只是資產本來偏漲，永遠猜漲一樣準。
「同一波動三分位」的歷史 p25–p75 區間實際落入率 48～52%（校準良好）——這是 v1 唯一敢宣稱的東西。
所以 v1 的預測值＝同波動狀態下歷史的中位報酬；方向只在歷史上漲機率 ≥55% 或 ≤45% 時標偏漲／偏跌，並明寫
「主要是長期傾向」；趨勢、動能、VIX 只記錄，留給未來用真實帳本檢驗。

狀態機：S0 資料檢查 → S1 波動 → S2 趨勢（記錄）→ S3 動能（記錄）→ S4 VIX（記錄）→ S5 查表 → S6 判定 → S7 輸出。

四條底線（遇到岔路的優先序）：
  1. 不偷看未來：每一列只用「起始日（含）以前」的資料；查表樣本的到期日也 ≤ 起始日；走步回測成績只算「到期日 ≤ 起始日」的決策。
  2. 帳本只增不改：預測欄位（A～AA）寫入後不再動，只有 AB～AF（到期對答案）會從「待到期」變成「已到期」；
     列的順序永遠不變，新列只加在最後面（Google 試算表靠列位置對齊手填欄）。
  3. 失敗不拖垮既有分析：build() 由呼叫端包 try/except；寫檔都是先寫暫存檔再 os.replace，寫前留一份 ledger.prev.json。
  4. 誠實：輸出不宣稱比回測更強的預測力；補登的列是「事後用同一套程式補算」，只防資料偷看，防不了設計偷看。

檔案（data/forecast/）：ledger.json（帳本）、forecast.csv（32 欄，試算表 IMPORTDATA 用）、backtest.json（走步回測快取）。
自我測試：python3 -m gfd.forecast --selftest
"""
import csv
import datetime as dt
import fcntl
import io
import json
import math
import os
import pathlib
import shutil
import sys
import tempfile
import time
from bisect import bisect_left, bisect_right
from contextlib import contextmanager

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view as _swv

from . import config as C

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
FDIR = ROOT / "data" / "forecast"
TPE = dt.timezone(dt.timedelta(hours=8))

LIVE, FILL = "即時", "回測補登"
PENDING, DONE, SKIPPED = "待到期", "已到期", "跳過"

# CSV 欄位（A～AF，共 32 欄；順序與表頭就是規格，改動要同步改試算表）
COLS = [
    ("id", "預測編號"), ("source", "來源"), ("created", "建立日期"), ("version", "模型版本"), ("asset", "資產"),
    ("symbol", "代號"), ("tw_buy", "台股可買"), ("horizon", "期間（交易日）"), ("start_date", "起始日"),
    ("start_price", "起始價"), ("due_est", "預計到期日"), ("flow", "判斷流程"), ("vol_state", "波動狀態"),
    ("trend_state", "趨勢狀態"), ("mom_state", "動能狀態"), ("vix", "VIX"), ("n_eff", "樣本數（獨立段）"),
    ("pred", "預測漲跌%"), ("lo", "區間下緣%"), ("hi", "區間上緣%"), ("p_up", "歷史上漲機率%"),
    ("verdict", "方向判定"), ("reason", "判斷原因"), ("bt_dir", "回測方向命中%"), ("bt_up", "回測永遠猜漲%"),
    ("bt_band", "回測落在區間%"), ("monthly", "月度沙盤推演（3個月期望超額%）"),
    ("status", "狀態"), ("settled", "到期日"), ("actual", "實際漲跌%（系統）"), ("in_band", "落在區間"),
    ("dir_ok", "方向對錯"),
]
N_PRED_COLS = 27                       # A～AA：預測欄位，寫入後永不修改
SETTLE_KEYS = ("status", "settled", "actual", "in_band", "dir_ok")   # AB～AF：只有到期對答案會改
PCT_KEYS = {"pred", "lo", "hi", "p_up", "bt_dir", "bt_up", "bt_band", "monthly", "actual"}
EXTRA_KEYS = ("asset_id", "week", "vix_pct", "steps")   # 帳本裡有、CSV 沒有的欄位（同樣寫入後不改）


def _params():
    return dict(
        version=C.FORECAST_VERSION, horizons=tuple(C.FORECAST_HORIZONS), bt_start=C.FORECAST_BACKTEST_START,
        backfill=C.FORECAST_BACKFILL_WEEKS, min_hist=C.FORECAST_MIN_HISTORY, min_neff=C.FORECAST_MIN_NEFF,
        up=round(C.FORECAST_UP * 100, 6), down=round(C.FORECAST_DOWN * 100, 6), stale=C.FORECAST_STALE_DAYS)


# ───────────────────────── 序列與指標（全部是「只看過去」的滾動量） ─────────────────────────

class Ser:
    """一條日線：dates（升冪）、closes（還原權息收盤）。vol／sma／r20 在 index t 只用到 ≤ t 的資料。"""

    def __init__(self, dates, closes):
        d, c = [], []
        for x, y in zip(dates, closes):
            if y is None:
                continue
            y = float(y)
            if not math.isfinite(y) or y <= 0 or (d and x <= d[-1]):
                continue
            d.append(x)
            c.append(y)
        self.d = d
        self.c = np.asarray(c, float)
        n = self.n = len(d)
        lr = np.full(n, np.nan)
        if n > 1:
            lr[1:] = np.diff(np.log(self.c))
        self.vol = np.full(n, np.nan)            # 20 日對數報酬標準差（日）
        if n >= 21:
            self.vol[20:] = _swv(lr[1:], 20).std(axis=1)
        self.sma50 = np.full(n, np.nan)
        self.sma200 = np.full(n, np.nan)
        if n >= 50:
            self.sma50[49:] = _swv(self.c, 50).mean(axis=1)
        if n >= 200:
            self.sma200[199:] = _swv(self.c, 200).mean(axis=1)
        self.r20 = np.full(n, np.nan)            # 20 日報酬
        if n > 20:
            self.r20[20:] = self.c[20:] / self.c[:-20] - 1
        self._wk = None

    @property
    def wk(self):
        if self._wk is None:
            iso = [dt.date.fromisoformat(x).isocalendar() for x in self.d]
            self._wk = [i[0] * 100 + i[1] for i in iso]
        return self._wk


def _r2(x):
    r = round(float(x), 2)
    return r + 0.0 if r == 0 else r


def _lookup(s, T, h, p, full=True):
    """S1＋S5：起始日 index T、期間 h。只用 index ≤ T 的資料，樣本的到期也 ≤ T。回傳狀態與查表結果。"""
    v = s.vol[20:T + 1]
    q1, q2 = np.quantile(v, (1 / 3, 2 / 3))
    cur = s.vol[T]
    st = int(cur >= q1) + int(cur >= q2)                 # 0 低 1 中 2 高
    f = s.c[h:T + 1] / s.c[:T + 1 - h] - 1               # 起點 0..T-h 的 h 日報酬（到期日 ≤ T）
    vs = s.vol[:T + 1 - h]
    with np.errstate(invalid="ignore"):
        stv = (vs >= q1).astype(np.int8) + (vs >= q2).astype(np.int8)
    m = np.isfinite(vs) & (stv == st)
    n_same = int(m.sum())
    ne_same = n_same // h
    fb = ne_same < p["min_neff"]
    sub = f if fb else f[m]
    p25, med, p75 = np.percentile(sub, (25, 50, 75))
    out = dict(state=st, n_same=n_same, ne_same=ne_same, fallback=fb, n=len(sub), n_eff=len(sub) // h,
               med=float(med), p25=float(p25), p75=float(p75), p_up=float((sub > 0).mean()))
    if full:
        out.update(vol=float(cur), vpct=100.0 * float((v < cur).mean()), n_all=len(f), ne_all=len(f) // h)
    return out


def _decide(L, p):
    """把查表結果轉成帳本用的數字（百分比、兩位小數）與方向判定。"""
    pu = _r2(100 * L["p_up"])
    verdict = "偏漲" if pu >= p["up"] - 1e-9 else "偏跌" if pu <= p["down"] + 1e-9 else "不確定"
    return dict(pred=_r2(100 * L["med"]), lo=_r2(100 * L["p25"]), hi=_r2(100 * L["p75"]), p_up=pu, verdict=verdict)


def _grade(verdict, lo, hi, act):
    """到期對答案（百分比兩位小數的值，和 CSV 上看到的一致）：落在區間、方向對錯。"""
    inb = lo <= act <= hi
    ok = (act > 0) if verdict == "偏漲" else (act < 0) if verdict == "偏跌" else None
    return inb, ok


def _vix_asof(vix, date):
    """起始日（含）以前最後一筆 VIX 與它在 1990 起歷史的分位；沒有或超過 7 天前 → None。"""
    if vix is None:
        return None
    j = bisect_right(vix.d, date) - 1
    if j < 0 or (dt.date.fromisoformat(date) - dt.date.fromisoformat(vix.d[j])).days > 7:
        return None
    x = float(vix.c[j])
    return x, 100.0 * float((vix.c[:j + 1] < x).mean())


# ───────────────────────── 走步回測（快取） ─────────────────────────

def _walk(s, h, p):
    """每個 ISO 週的第一個交易日做一次決策（同 live 的查表），用實際 h 日後的漲跌對答案。
    欄位依決策順序（到期日遞增）：mat 到期日、v 方向(1 偏漲/-1 偏跌/0 不確定)、ok 方向對(0/1)、up 實際>0、inb 落在區間。"""
    i0 = max(p["min_hist"] - 1, bisect_left(s.d, p["bt_start"]), 1)
    wk = s.wk
    e = dict(mat=[], v=[], ok=[], up=[], inb=[])
    for T in range(i0, s.n - h):
        if wk[T] == wk[T - 1]:
            continue
        dd = _decide(_lookup(s, T, h, p, full=False), p)
        act = _r2(100 * (s.c[T + h] / s.c[T] - 1))
        inb, ok = _grade(dd["verdict"], dd["lo"], dd["hi"], act)
        e["mat"].append(s.d[T + h])
        e["v"].append(1 if dd["verdict"] == "偏漲" else -1 if dd["verdict"] == "偏跌" else 0)
        e["ok"].append(1 if ok else 0)
        e["up"].append(1 if act > 0 else 0)
        e["inb"].append(1 if inb else 0)
    return e


def _bt_asof(e, cutoff):
    """走步回測在 cutoff（含）以前已到期的決策的成績；沒有 → None。"""
    if not e:
        return None
    k = bisect_right(e["mat"], cutoff)
    if k == 0:
        return None
    v = e["v"][:k]
    nj = sum(1 for x in v if x)
    hit = sum(o for x, o in zip(v, e["ok"][:k]) if x)
    upj = sum(u for x, u in zip(v, e["up"][:k]) if x)
    band = sum(e["inb"][:k])
    return dict(n=k, nj=nj, hit=hit, upj=upj, bandn=band,
                dir=_r2(100 * hit / nj) if nj else None, up=_r2(100 * upj / nj) if nj else None, band=_r2(100 * band / k))


def _atomic_write(path, text):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _ensure_bt(path, series, assets, p, today, log):
    """走步回測成績快取：鍵＝模型版本＋ISO 週（＋參數）；鍵沒變就不重算，只補沒有的 (代號, 期間)。"""
    y, w, _ = today.isocalendar()
    key = f"{p['version']}|{y}-W{w:02d}"
    params = dict(up=p["up"], down=p["down"], min_neff=p["min_neff"], min_hist=p["min_hist"], start=p["bt_start"])
    cache = None
    if path.exists():
        try:
            cache = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            cache = None
    if not cache or cache.get("key") != key or cache.get("params") != params:
        cache = dict(key=key, params=params, assets={})
    t0, todo = time.time(), 0
    for a in assets:
        s = series.get(a[1])
        if s is None or s.n < p["min_hist"]:
            continue
        for h in p["horizons"]:
            k = f"{a[1]}|{h}"
            if k not in cache["assets"]:
                cache["assets"][k] = _walk(s, h, p)
                todo += 1
    if todo:
        cache["built"] = dt.datetime.now(TPE).isoformat(timespec="seconds")
        _atomic_write(path, json.dumps(cache, ensure_ascii=False, separators=(",", ":")))
        log(f"[forecast] 走步回測重算 {todo} 個 (資產,期間)，{time.time() - t0:.1f} 秒")
    return cache


# ───────────────────────── 列的組成（S0～S7、判斷流程、判斷原因） ─────────────────────────

def _sg(x, nd=1):
    s = f"{abs(x):.{nd}f}"
    return f"{0:.{nd}f}" if float(s) == 0 else ("+" if x > 0 else "−") + s


def _pt(x, p):
    """機率的顯示：整數百分比；剛好卡在 55／45 門檻附近時多顯示一位，避免「顯示 55% 卻判不確定」。"""
    s = f"{x:.0f}"
    return f"{x:.1f}" if int(s) in (round(p["up"]), round(p["down"])) else s


def _week_label(d):
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def _skip_row(base, why):
    base.update(
        status=SKIPPED, verdict=SKIPPED,
        flow=f"S0 資料不合格（{why}）→ 跳過",
        reason=f"{base['asset']}（{base['symbol']}）{why}，這一期不出預測。",
        steps=[dict(s="S0", name="資料檢查", value="不合格", detail=why)])
    return base


def _make_row(asset, h, s, vix, cut, created, source, monthly, bt, p):
    """組一列。cut＝資料截止日（含），created＝建立日。只用 ≤ cut 的資料。"""
    aid, sym, _src, name, tw = asset
    week = _week_label(created)
    base = {k: None for k, _ in COLS}
    base.update(id=f"{week}-{sym}-{h}", source=source, created=created.isoformat(), version=p["version"], asset=name,
                symbol=sym, tw_buy=tw or "無", horizon=h, status=PENDING, asset_id=aid, week=week, vix_pct=None)
    T = bisect_right(s.d, cut.isoformat()) - 1 if s is not None else -1
    if T < 0:
        return _skip_row(base, "沒有資料")
    n = T + 1
    last = dt.date.fromisoformat(s.d[T])
    age = (created - last).days
    if n < p["min_hist"]:
        return _skip_row(base, f"歷史只有 {n} 個交易日，不足 {p['min_hist']} 個")
    if age > p["stale"]:
        return _skip_row(base, f"最後收盤 {s.d[T]} 已是 {age} 天前，超過 {p['stale']} 天")

    L = _lookup(s, T, h, p)
    dd = _decide(L, p)
    sd, price = s.d[T], float(s.c[T])
    vs = ("低", "中", "高")[L["state"]]
    ann = 100 * L["vol"] * math.sqrt(252)
    c200, c50 = float(s.sma200[T]), float(s.sma50[T])
    up200, up50 = price > c200, c50 > c200
    trend = "多頭" if up200 and up50 else "空頭" if (not up200 and not up50) else "盤整"
    r20 = float(s.r20[T])
    hist = s.r20[20:T + 1]
    mpct = 100.0 * float((hist < r20).mean())
    mom = "弱" if mpct < 100 / 3 else "強" if mpct > 200 / 3 else "中"
    vx = _vix_asof(vix, sd)
    due = np.busday_offset(np.datetime64(sd), h, roll="forward")
    pu, v = dd["p_up"], dd["verdict"]
    ne = L["n_eff"]

    # ── 判斷流程（一行）──
    if L["fallback"]:
        s5 = f"S5 同波動樣本僅 {L['ne_same']} 段，樣本不足，改用全部歷史 {ne} 段"
    else:
        s5 = f"S5 同波動樣本 {ne} 段"
    vtxt = f"S4 VIX:{vx[0]:.1f}(第{vx[1]:.0f}分位)" if vx else "S4 VIX:無資料"
    flow = " → ".join(["S0 資料OK", f"S1 波動:{vs}(第{L['vpct']:.0f}分位)", f"S2 趨勢:{trend}",
                       f"S3 動能:{mom}(第{mpct:.0f}分位)", vtxt, s5, f"S6 {v}(上漲機率{_pt(pu, p)}%)"])

    # ── 判斷原因（一段白話）──
    who = f"{name}（{sym}）"
    if L["fallback"]:
        t1 = (f"過去{who}波動屬「{vs}」的樣本只有約 {L['ne_same']} 段獨立樣本，不足 {p['min_neff']} 段，改看全部歷史："
              f"{h} 個交易日後的漲跌中位數 {_sg(dd['pred'])}%，一半的情況落在 {_sg(dd['lo'])}%～{_sg(dd['hi'])}%，"
              f"上漲機率 {_pt(pu, p)}%（約 {ne} 段獨立樣本）。")
    else:
        t1 = (f"過去{who}波動屬「{vs}」時，{h} 個交易日後的漲跌中位數 {_sg(dd['pred'])}%，"
              f"一半的情況落在 {_sg(dd['lo'])}%～{_sg(dd['hi'])}%，上漲機率 {_pt(pu, p)}%（約 {ne} 段獨立樣本）。")
    if v == "偏漲":
        t2 = "判定偏漲，主要反映長期上漲傾向，不是當下訊號"
    elif v == "偏跌":
        t2 = "判定偏跌，只表示這個波動狀態下歷史上跌的次數比漲多，是歷史傾向，不是當下訊號"
    else:
        t2 = f"上漲機率介於 {p['down']:.0f}%～{p['up']:.0f}% 之間，不做方向判斷"
    if bt and bt["nj"]:
        # 基準用「永遠猜多數方向」：對本來偏跌的資產，贏「永遠猜漲」太容易，不能拿來說有預測力
        bmaj = max(bt["up"], 100 - bt["up"])
        bname = "永遠猜漲" if bt["up"] >= 50 else "永遠猜跌"
        gap = bt["dir"] - bmaj
        noise = 1.96 * 100 * math.sqrt(0.25 / bt["nj"])          # 單一比例的 95% 隨機誤差（保守）
        if abs(gap) < 0.5:
            cmp_ = f"和{bname}一樣準，沒有比較準"
        elif gap < 0:
            cmp_ = f"還不如{bname}（差 {-gap:.0f} 個百分點）"
        elif gap < noise:
            cmp_ = f"只比{bname}高 {gap:.0f} 個百分點，在隨機誤差內（±{noise:.0f}），不能說比較準"
        else:
            cmp_ = f"比{bname}高 {gap:.0f} 個百分點（超出隨機誤差 ±{noise:.0f}，但不保證延續）"
        t3 = (f"走步回測（只算起始日前已到期的決策）方向命中 {bt['dir']:.0f}%（{bt['nj']} 次判定）、永遠猜漲 {bt['up']:.0f}%、永遠猜跌 {100 - bt['up']:.0f}%，"
              f"{cmp_}；預測區間實際涵蓋 {bt['band']:.0f}%（理想約 50%）。")
    elif bt:
        t3 = f"走步回測（{bt['n']} 次決策）沒有方向判定可比；預測區間實際涵蓋 {bt['band']:.0f}%（理想約 50%）。"
    else:
        t3 = "沒有可用的走步回測成績。"
    t4 = (f"趨勢{trend}、動能{mom}"
          + (f"、VIX {vx[0]:.0f}（第 {vx[1]:.0f} 分位）" if vx else "、VIX 無資料")
          + "只記錄、不參與預測（2008 年起的走步研究裡它們對漲跌沒有預測力）。")
    reason = t1 + t2 + "。" + t3 + t4

    mon = None if monthly is None else _r2(monthly)
    steps = [
        dict(s="S0", name="資料檢查", value="OK", detail=f"歷史 {n} 個交易日，最後收盤 {sd}（{age} 天前）"),
        dict(s="S1", name="波動狀態", value=vs, detail=f"20 日波動在自己歷史的第 {L['vpct']:.0f} 分位，年化 {ann:.0f}%"),
        dict(s="S2", name="趨勢狀態（只記錄）", value=trend,
             detail=f"收盤{'高' if up200 else '低'}於 200 日線 {abs(100 * (price / c200 - 1)):.1f}%，"
                    f"50 日線{'高' if up50 else '低'}於 200 日線"),
        dict(s="S3", name="動能狀態（只記錄）", value=mom, detail=f"20 日報酬 {_sg(100 * r20)}%，在自己歷史的第 {mpct:.0f} 分位"),
        dict(s="S4", name="環境 VIX（只記錄）", value=f"{vx[0]:.1f}" if vx else "無資料",
             detail=f"在 1990 年以來歷史的第 {vx[1]:.0f} 分位" if vx else "起始日前 7 天內沒有 VIX 收盤"),
        dict(s="S5", name="查表", value=f"{ne} 段",
             detail=(f"同波動「{vs}」樣本只有 {L['ne_same']} 段（不足 {p['min_neff']} 段），改用全部歷史 {ne} 段；"
                     if L["fallback"] else f"同波動「{vs}」的歷史樣本 {ne} 段；")
                    + f"中位數 {_sg(dd['pred'])}%，p25 {_sg(dd['lo'])}%，p75 {_sg(dd['hi'])}%，上漲機率 {_pt(pu, p)}%"),
        dict(s="S6", name="判定", value=v, detail=f"上漲機率 {_pt(pu, p)}%（≥{p['up']:.0f}% 偏漲、≤{p['down']:.0f}% 偏跌，其餘不確定）"),
        dict(s="S7", name="輸出", value="寫入帳本",
             detail=(f"回測方向命中 {bt['dir']:.0f}%、永遠猜漲 {bt['up']:.0f}%、區間涵蓋 {bt['band']:.0f}%" if bt and bt["nj"]
                     else "沒有可用的回測成績")
                    + (f"；月度沙盤推演 3 個月期望超額 {_sg(mon, 2)}%" if mon is not None else "")),
    ]
    base.update(
        start_date=sd, start_price=round(price, 4), due_est=str(due), flow=flow, vol_state=vs, trend_state=trend,
        mom_state=mom, vix=_r2(vx[0]) if vx else None, vix_pct=round(vx[1], 1) if vx else None, n_eff=int(ne),
        pred=dd["pred"], lo=dd["lo"], hi=dd["hi"], p_up=pu, verdict=v, reason=reason,
        bt_dir=bt["dir"] if bt else None, bt_up=bt["up"] if bt else None, bt_band=bt["band"] if bt else None,
        monthly=mon, steps=steps)
    return base


def _settle_row(row, s):
    """到期對答案：起始日之後已有 h 根收盤 → 填實際漲跌%、落在區間、方向對錯。回傳是否有改。
    實際漲跌％用「同一份還原權息序列」的起始日收盤當分母（和預測用的樣本同口徑，除息不會讓分母錯位），
    不用帳本記的起始價（那是寫入當時的還原基準，之後除息會被往下調整）。"""
    if row["status"] != PENDING or s is None:
        return False
    i = bisect_left(s.d, row["start_date"])
    h = row["horizon"]
    if i >= s.n or s.d[i] != row["start_date"] or i + h > s.n - 1:
        return False                      # 序列裡找不到起始日，或還不到 h 根：維持待到期
    act = _r2(100 * (float(s.c[i + h]) / float(s.c[i]) - 1))
    inb, ok = _grade(row["verdict"], row["lo"], row["hi"], act)
    row.update(status=DONE, settled=s.d[i + h], actual=act, in_band="是" if inb else "否",
               dir_ok="不判" if ok is None else "對" if ok else "錯")
    return True


# ───────────────────────── 帳本與 CSV ─────────────────────────

def _cell(k, v):
    if v is None or v == "":
        return ""
    if k in PCT_KEYS or k == "vix":
        return f"{float(v):.2f}"
    if k == "start_price":
        return f"{float(v):.4f}".rstrip("0").rstrip(".")
    if k in ("horizon", "n_eff"):
        return str(int(v))
    return str(v)


def csv_text(rows):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow([h for _, h in COLS])
    for r in rows:
        w.writerow([_cell(k, r.get(k)) for k, _ in COLS])
    return buf.getvalue()


def _load_ledger(path):
    if not path.exists():
        # 帳本不見但備份還在＝有東西出錯了：不能默默重建（會換掉已公開的預測），要人工把 ledger.prev.json 改回來
        if path.with_name("ledger.prev.json").exists():
            raise FileNotFoundError(f"{path} 不見了但 ledger.prev.json 還在：請確認後把備份改名回 ledger.json，不自動重建")
        return dict(version=C.FORECAST_VERSION, rows=[])
    led = json.loads(path.read_text(encoding="utf-8"))   # 壞檔就讓它報錯：不能在壞檔上覆寫，ledger.prev.json 還在
    if not isinstance(led.get("rows"), list):
        raise ValueError(f"{path} 格式不對（沒有 rows）")
    return led


def _write_ledger(path, led):
    if path.exists():
        shutil.copy2(path, path.with_name("ledger.prev.json"))
    head = json.dumps({k: v for k, v in led.items() if k != "rows"}, ensure_ascii=False, separators=(",", ":"))
    body = ",\n".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in led["rows"])
    _atomic_write(path, head[:-1] + ',"rows":[\n' + body + "\n]}\n")


def _check_append_only(old, rows):
    """寫檔前的最後防線：舊列的預測欄位（A～AA 與附加欄位）一個字都不能變，列的位置也不能動。"""
    if len(rows) < len(old):
        raise RuntimeError("帳本列數變少，拒絕寫入")
    frozen = [k for k, _ in COLS[:N_PRED_COLS]] + list(EXTRA_KEYS)
    for i, o in enumerate(old):
        r = rows[i]
        for k in frozen:
            if o.get(k) != r.get(k):
                raise RuntimeError(f"帳本第 {i + 1} 列（{o.get('id')}）的 {k} 被改動，拒絕寫入")
        if o["status"] != PENDING and any(o.get(k) != r.get(k) for k in SETTLE_KEYS):
            raise RuntimeError(f"帳本第 {i + 1} 列（{o.get('id')}）已結案卻被改動，拒絕寫入")


@contextmanager
def _flock(path):
    with open(path, "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def update(series, vix, today, dirpath, monthly=None, p=None, assets=None, log=print):
    """主流程：回測快取 →（帳本第一次建立時）補登 → 本週即時批次 → 到期對答案 → 寫帳本與 CSV。
    series：{代號: Ser}；vix：Ser 或 None；today：台北時間的 date；monthly：{asset_id: 期望超額%}。"""
    p = p or _params()
    assets = list(assets if assets is not None else C.FORECAST_ASSETS)
    dirpath.mkdir(parents=True, exist_ok=True)
    with _flock(dirpath / ".lock"):
        lp = dirpath / "ledger.json"
        led = _load_ledger(lp)
        rows = led["rows"]
        old = [dict(r) for r in rows]
        bt = _ensure_bt(dirpath / "backtest.json", series, assets, p, today, log)
        have = {r["id"] for r in rows}

        def batch(cut, created, source, mon):
            out = []
            for a in assets:
                s = series.get(a[1])
                for h in p["horizons"]:
                    rid = f"{_week_label(created)}-{a[1]}-{h}"
                    if rid in have:
                        continue
                    T = bisect_right(s.d, cut.isoformat()) - 1 if s is not None else -1
                    b = _bt_asof(bt["assets"].get(f"{a[1]}|{h}"), s.d[T]) if T >= 0 else None
                    out.append(_make_row(a, h, s, vix, cut, created, source, (mon or {}).get(a[0]), b, p))
                    have.add(rid)
            return out

        new_fill = []
        if not rows and p["backfill"] > 0:
            mon = today - dt.timedelta(days=today.weekday())
            for k in range(p["backfill"], 0, -1):
                m = mon - dt.timedelta(days=7 * k)      # 補登：當週星期一建立，只用到星期日為止的資料
                new_fill += batch(m - dt.timedelta(days=1), m, FILL, None)
            rows.extend(new_fill)
        new_live = batch(today, today, LIVE, monthly)
        rows.extend(new_live)
        settled = sum(_settle_row(r, series.get(r["symbol"])) for r in rows)
        _check_append_only(old, rows)
        if new_fill or new_live or settled:
            led["version"] = p["version"]
            led["updated"] = dt.datetime.now(TPE).isoformat(timespec="seconds")
            _write_ledger(lp, led)
        text = csv_text(rows)
        cp = dirpath / "forecast.csv"
        if not cp.exists() or cp.read_text(encoding="utf-8") != text:
            _atomic_write(cp, text)
        log(f"[forecast] 帳本 {len(rows)} 列（新增補登 {len(new_fill)}、即時 {len(new_live)}，本次到期對答案 {settled}）")
    return dict(rows=rows, bt=bt, new_fill=len(new_fill), new_live=len(new_live), settled=settled)


# ───────────────────────── 給網頁用的摘要 ─────────────────────────

METHOD = [
    "S0 資料檢查：歷史至少 1000 個交易日、最後一筆收盤不超過 7 個日曆天前；不合格的列記「跳過」，不出預測。",
    "S1 波動狀態：20 日對數報酬標準差（年化顯示）；用到起始日為止的全部歷史算三分位門檻，分成低／中／高。",
    "S2 趨勢狀態（只記錄）：收盤與 200 日線、50 日線與 200 日線都在上面＝多頭，都在下面＝空頭，其餘盤整。",
    "S3 動能狀態（只記錄）：20 日報酬在自己歷史的分位，低於 1/3 為弱、高於 2/3 為強，其餘為中。",
    "S4 環境（只記錄）：起始日前最近一筆 VIX 收盤，與它在 1990 年以來歷史的分位。",
    "S5 查表：只用到期日不晚於起始日的歷史樣本（不偷看），取「同一波動三分位」的 h 日報酬；獨立段數＝樣本數÷h，"
    "不足 15 段就改用全部歷史。輸出中位數（預測漲跌）、p25～p75（區間）、上漲機率。",
    "S6 判定：上漲機率 ≥55% 偏漲、≤45% 偏跌，其餘不確定。這主要是資產的長期傾向，不是當下訊號。",
    "S7 輸出：寫入帳本（只增不改），附同資產同期間的走步回測成績（方向命中、永遠猜漲命中、落在區間比例，只算起始日前已到期的決策）。",
    "到期對答案：起始日之後有 h 根收盤就填實際漲跌%、是否落在區間、方向對錯（用同一份還原權息序列算，除息不會錯位）。預測欄位寫入後永不修改。",
    "補登：帳本第一次建立時，用截至當時的資料補 12 週；補登與即時的成績分開統計。補登是事後用同一套程式補算，"
    "只防得了資料偷看，防不了「設計看過這段歷史」，不能當成當時公布過的預測。",
    "誠實聲明：2008 年起的研究裡，趨勢、動能、離年線、短期反轉、VIX 對漲跌都沒有預測力（IC 約 0）；方向命中 55～57% 只是因為這些資產本來偏漲，"
    "永遠猜漲一樣準。v1 唯一驗證過的是區間校準（同波動三分位的 p25～p75 實際落入率約 50%）。",
]


def _rate(num, den):
    return _r2(100 * num / den) if den else None


def _score(rows, source):
    out = {}
    for h in sorted({r["horizon"] for r in rows}):
        rs = [r for r in rows if r["source"] == source and r["horizon"] == h and r["status"] != SKIPPED]
        due = [r for r in rs if r["status"] == DONE]
        jd = [r for r in due if r["dir_ok"] in ("對", "錯")]
        out[str(h)] = dict(
            due=len(due), pending=len(rs) - len(due), skipped=sum(1 for r in rows if r["source"] == source and r["horizon"] == h and r["status"] == SKIPPED),
            band=_rate(sum(1 for r in due if r["in_band"] == "是"), len(due)),
            dir=_rate(sum(1 for r in jd if r["dir_ok"] == "對"), len(jd)), dir_n=len(jd),
            up=_rate(sum(1 for r in jd if r["actual"] > 0), len(jd)))
    return out


def _bt_pooled(bt, assets, p):
    out = {}
    for h in p["horizons"]:
        n = nj = hit = upj = band = 0
        cnt = 0
        for a in assets:
            r = _bt_asof(bt["assets"].get(f"{a[1]}|{h}"), "9999-12-31")
            if r:
                n += r["n"]; nj += r["nj"]; hit += r["hit"]; upj += r["upj"]; band += r["bandn"]; cnt += 1
        out[str(h)] = dict(n=n, nj=nj, assets=cnt, dir=_rate(hit, nj), up=_rate(upj, nj), band=_rate(band, n))
    return out


def summarize(rows, bt, today, p, assets):
    wk = _week_label(today)
    batch = [dict(r) for r in rows if r["source"] == LIVE and r["week"] == wk]
    done = [(r["settled"], i) for i, r in enumerate(rows) if r["status"] == DONE]
    done.sort(reverse=True)
    out = dict(
        version=p["version"], horizons=list(p["horizons"]), asof=today.isoformat(), week=wk, batch=batch,
        score=dict(live=_score(rows, LIVE), backfill=_score(rows, FILL)),
        recent=[dict(rows[i]) for _, i in done[:30]],
        backtest=dict(_bt_pooled(bt, assets, p), start=p["bt_start"]),
        csv="data/forecast.csv", method=list(METHOD), rows=len(rows))
    return out


# ───────────────────────── 對外入口 ─────────────────────────

def _load_raw(name):
    p = RAW / name
    if not p.exists():
        raise FileNotFoundError(f"找不到 {p}，預測帳本沒有資料可用（不寫任何東西）")
    return json.loads(p.read_text(encoding="utf-8"))


def monthly_map(scen):
    """月度沙盤推演 3 個月的期望超額（ens_cal，沒有就 ens），對不到的資產就沒有。"""
    out = {}
    for r in ((scen or {}).get("assets") or {}).get("3") or []:
        sid = r.get("sid", r.get("id"))
        v = r.get("ens_cal")
        if v is None:
            v = r.get("ens")
        if sid is not None and v is not None:
            out[sid] = float(v)
    return out


def build(scen=None, log=print, today=None, dirpath=None):
    """analysis.run() 呼叫：更新帳本與 CSV，回傳給網頁用的摘要（可轉 JSON）。出錯就丟例外，由呼叫端記錄。"""
    today = today or dt.datetime.now(TPE).date()
    tg, cs = _load_raw("daily_targets.json").get("series", {}), _load_raw("daily_cascade.json").get("series", {})
    pools = dict(targets=tg, cascade=cs)
    series = {}
    for _aid, sym, src, _name, _tw in C.FORECAST_ASSETS:
        v = pools.get(src, {}).get(sym)
        if v and v.get("dates"):
            series[sym] = Ser(v["dates"], v["closes"])
    vv = cs.get("^VIX")
    vix = Ser(vv["dates"], vv["closes"]) if vv and vv.get("dates") else None
    p = _params()
    res = update(series, vix, today, dirpath or FDIR, monthly=monthly_map(scen), p=p, log=log)
    out = summarize(res["rows"], res["bt"], today, p, C.FORECAST_ASSETS)
    json.dumps(out, ensure_ascii=False)          # 確認可序列化（有 numpy 型別會在這裡報錯，而不是在寫 analysis.json 時）
    sc = out["score"]["backfill"]
    log("[forecast] 補登已到期 " + "、".join(f"{h} 日 {v['due']} 列 區間{v['band']}% 方向{v['dir']}%（{v['dir_n']} 判，永遠猜漲 {v['up']}%）"
                                          for h, v in sc.items()))
    return out


# ───────────────────────── 自我測試（合成資料） ─────────────────────────

SPEC_HEADER = ["預測編號", "來源", "建立日期", "模型版本", "資產", "代號", "台股可買", "期間（交易日）", "起始日", "起始價",
               "預計到期日", "判斷流程", "波動狀態", "趨勢狀態", "動能狀態", "VIX", "樣本數（獨立段）", "預測漲跌%",
               "區間下緣%", "區間上緣%", "歷史上漲機率%", "方向判定", "判斷原因", "回測方向命中%", "回測永遠猜漲%",
               "回測落在區間%", "月度沙盤推演（3個月期望超額%）", "狀態", "到期日", "實際漲跌%（系統）", "落在區間",
               "方向對錯"]


def _synth(n, seed, drift=0.0004, base_sig=0.010):
    rng = np.random.default_rng(seed)
    days = np.busday_offset(np.datetime64("2012-01-02"), np.arange(n), roll="forward")
    dates = [str(x) for x in days]
    sig = base_sig * (1 + 0.8 * np.sin(np.arange(n) / 150.0 + seed))
    c = 100 * np.exp(np.cumsum(drift + sig * rng.standard_normal(n)))
    return dates, c


def _cut(series, k):
    return {sym: Ser(s.d[:k + 1], s.c[:k + 1].tolist()) for sym, s in series.items()}


def _selftest():
    ok = []

    def check(name, cond, info=""):
        ok.append((name, bool(cond)))
        print(("  PASS " if cond else "  FAIL ") + name + (f"  {info}" if info and not cond else ""))

    N = 3000
    p = _params()
    assets = [("a_one", "AAA", "targets", "測試資產甲", "0050.TW"), ("a_two", "BBB", "targets", "測試資產乙", "")]
    full = {}
    for i, a in enumerate(assets):
        d, c = _synth(N, 7 + i)
        full[a[1]] = Ser(d, c.tolist())
    vd, vc = _synth(N, 99, drift=0.0, base_sig=0.03)
    vfull = Ser(vd, (15 * vc / vc[0]).tolist())
    K = 2900
    d0 = dt.date.fromisoformat(full["AAA"].d[K])
    today1 = d0                       # 資料截止日（含）＝第 K 根
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="fc_selftest_"))
    try:
        quiet = lambda *_a, **_k: None
        # (a) 冪等
        A = tmp / "a"
        r1 = update(_cut(full, K), vfull, today1, A, p=p, assets=assets, log=quiet)
        n1 = len(r1["rows"])
        b1 = (A / "ledger.json").read_bytes()
        c1 = (A / "forecast.csv").read_bytes()
        r2 = update(_cut(full, K), vfull, today1, A, p=p, assets=assets, log=quiet)
        per = len(assets) * len(p["horizons"])
        check("(a) 冪等：列數＝(補登週數+1)×資產×期間", n1 == (p["backfill"] + 1) * per, f"{n1}")
        check("(a) 冪等：同一週連跑第二次列數不變", len(r2["rows"]) == n1 and r2["new_live"] == 0 and r2["new_fill"] == 0)
        check("(a) 冪等：帳本與 CSV 位元組不變", (A / "ledger.json").read_bytes() == b1 and (A / "forecast.csv").read_bytes() == c1)
        ids = [r["id"] for r in r2["rows"]]
        check("(a) 預測編號不重複", len(set(ids)) == len(ids))

        # (b) 只增不改：下一週新增列，舊列的 A～AA 逐字相同、位置不動
        old_cells = [[_cell(k, r.get(k)) for k, _ in COLS[:N_PRED_COLS]] for r in r2["rows"]]
        K2 = K + 5
        r3 = update(_cut(full, K2), vfull, today1 + dt.timedelta(days=7), A, p=p, assets=assets, log=quiet)
        new_cells = [[_cell(k, r.get(k)) for k, _ in COLS[:N_PRED_COLS]] for r in r3["rows"]]
        check("(b) 只增不改：第二週新增 資產×期間 列", len(r3["rows"]) == n1 + per, f"{len(r3['rows'])}")
        check("(b) 只增不改：舊列 A～AA 逐字相同且位置不變", new_cells[:n1] == old_cells)
        check("(b) 新列在最後面且建立日期較晚", all(r["created"] > r2["rows"][-1]["created"] for r in r3["rows"][n1:]))
        check("(b) 備份檔 ledger.prev.json 存在", (A / "ledger.prev.json").exists())
        snap = [dict(r) for r in r3["rows"]]
        tampered = [dict(r) for r in r3["rows"]]
        tampered[0]["pred"] = 99.0
        try:
            _check_append_only(snap, tampered)
            guarded = False
        except RuntimeError:
            guarded = True
        check("(b) 防線：改舊列預測欄位會被拒絕寫入", guarded)

        # (c) 不偷看：把起始日之後的資料換成亂數，列的 A～AA 不能變
        fills = [r for r in r3["rows"] if r["source"] == FILL and r["status"] != SKIPPED]
        row = fills[len(fills) // 2]
        S = row["start_date"]
        a = next(x for x in assets if x[1] == row["symbol"])
        junk = {}
        for sym, s in full.items():
            j = bisect_right(s.d, S)
            rng = np.random.default_rng(1)
            c2 = s.c.copy()
            c2[j:] = c2[j:] * np.exp(np.cumsum(rng.standard_normal(len(c2) - j) * 0.05 + 0.01))   # 起始日之後全亂
            junk[sym] = Ser(s.d, c2.tolist())
        trunc = {sym: Ser(s.d[:bisect_right(s.d, S)], s.c[:bisect_right(s.d, S)].tolist()) for sym, s in full.items()}
        vj = Ser(vfull.d, np.concatenate([vfull.c[:bisect_right(vfull.d, S)],
                                          vfull.c[bisect_right(vfull.d, S):] * 3]).tolist())
        created = dt.date.fromisoformat(row["created"])
        cut = created - dt.timedelta(days=1)
        res_cells = []
        for label, ser_map, vx in (("完整序列", full, vfull), ("起始日截斷", trunc, vfull), ("起始日後亂數", junk, vj)):
            bt_c = _ensure_bt(tmp / ("bt_" + label), ser_map, assets, p, today1, quiet)
            s = ser_map[row["symbol"]]
            rr = _make_row(a, row["horizon"], s, vx, cut, created, FILL, None,
                           _bt_asof(bt_c["assets"].get(f"{row['symbol']}|{row['horizon']}"), S), p)
            res_cells.append([_cell(k, rr.get(k)) for k, _ in COLS[:N_PRED_COLS]])
        check("(c) 不偷看：完整序列算出的列＝帳本裡的列", res_cells[0] == [_cell(k, row.get(k)) for k, _ in COLS[:N_PRED_COLS]])
        check("(c) 不偷看：截在起始日的序列與完整序列的 A～AA 相同", res_cells[1] == res_cells[0])
        check("(c) 不偷看：起始日之後換成亂數，A～AA 仍相同", res_cells[2] == res_cells[0])

        # (d) 到期對答案：構造已知價格
        B = tmp / "b"
        ser0 = {sym: Ser(s.d[:K + 1], s.c[:K + 1].tolist()) for sym, s in full.items()}
        rb = update(ser0, vfull, today1, B, p=p, assets=assets, log=quiet)
        live = {(r["symbol"], r["horizon"]): r for r in rb["rows"] if r["source"] == LIVE}
        r10, r21 = live[("AAA", 10)], live[("AAA", 21)]
        base_px = float(ser0["AAA"].c[K])
        ext = full["AAA"]
        c_ext = ext.c.copy()
        c_ext[K + 10] = base_px * 1.05
        c_ext[K + 21] = base_px * 0.97
        fut = dict(full)
        fut["AAA"] = Ser(ext.d[:K + 22], c_ext[:K + 22].tolist())
        fut["BBB"] = Ser(full["BBB"].d[:K + 22], full["BBB"].c[:K + 22].tolist())
        # 只用 10 根：先給 K+12 根，21 日那列要還在「待到期」
        mid = {sym: Ser(s.d[:K + 12], s.c[:K + 12].tolist()) for sym, s in fut.items()}
        rm = update(mid, vfull, today1, B, p=p, assets=assets, log=quiet)
        lm = {(r["symbol"], r["horizon"]): r for r in rm["rows"] if r["source"] == LIVE}
        check("(d) 到期：10 日列到期、21 日列仍待到期", lm[("AAA", 10)]["status"] == DONE and lm[("AAA", 21)]["status"] == PENDING)
        x10 = lm[("AAA", 10)]
        check("(d) 到期：實際漲跌%＝+5.00、到期日＝起始後第 10 根", x10["actual"] == 5.0 and x10["settled"] == ext.d[K + 10],
              f"{x10['actual']} {x10['settled']}")
        exp_in = x10["lo"] <= 5.0 <= x10["hi"]
        exp_dir = None if x10["verdict"] == "不確定" else ((x10["verdict"] == "偏漲") == (5.0 > 0))
        check("(d) 到期：落在區間與方向對錯與獨立計算一致",
              x10["in_band"] == ("是" if exp_in else "否")
              and x10["dir_ok"] == ("不判" if exp_dir is None else "對" if exp_dir else "錯"), f"{x10['verdict']} {x10['in_band']} {x10['dir_ok']}")
        rf = update(fut, vfull, today1, B, p=p, assets=assets, log=quiet)
        lf = {(r["symbol"], r["horizon"]): r for r in rf["rows"] if r["source"] == LIVE}
        x21 = lf[("AAA", 21)]
        check("(d) 到期：21 日列實際漲跌%＝-3.00", x21["status"] == DONE and x21["actual"] == -3.0, f"{x21['actual']}")
        check("(d) 到期：已結案的 10 日列不再變動", lf[("AAA", 10)] == lm[("AAA", 10)])
        # 單元：三種判定 × 區間內外
        s_u = Ser([str(x) for x in np.busday_offset(np.datetime64("2020-01-01"), np.arange(40), roll="forward")],
                  [100.0] * 40)
        base_row = dict(status=PENDING, start_date=s_u.d[5], horizon=10, start_price=100.0, lo=-2.0, hi=2.0, verdict="偏漲")
        cases = [("偏漲", 103.0, "否", "對"), ("偏漲", 99.0, "是", "錯"), ("偏跌", 97.0, "否", "對"), ("偏跌", 101.0, "是", "錯"),
                 ("不確定", 101.0, "是", "不判"), ("偏漲", 98.0, "是", "錯"), ("偏跌", 102.0, "是", "錯")]
        good = True
        for v, px, e_in, e_dir in cases:
            cc = np.full(40, 100.0)
            cc[15] = px
            ss = Ser(s_u.d, cc.tolist())
            rw = dict(base_row, verdict=v)
            _settle_row(rw, ss)
            good &= (rw["status"] == DONE and rw["in_band"] == e_in and rw["dir_ok"] == e_dir
                     and rw["actual"] == _r2(px - 100.0) and rw["settled"] == ss.d[15])
        check("(d) 到期：偏漲／偏跌／不確定 × 區間內外 單元測試", good)
        sk = dict(base_row, status=SKIPPED)
        check("(d) 到期：跳過的列不碰", _settle_row(sk, s_u) is False and sk["status"] == SKIPPED)

        # (e) CSV 格式
        raw = (A / "forecast.csv").read_bytes()
        check("(e) CSV：無 BOM", not raw.startswith(b"\xef\xbb\xbf"))
        rd = list(csv.reader(io.StringIO(raw.decode("utf-8"))))
        check("(e) CSV：表頭 32 欄且順序與規格一致", len(rd[0]) == 32 and rd[0] == SPEC_HEADER, str(len(rd[0])))
        check("(e) CSV：每列都是 32 欄、列數＝帳本列數＋1", all(len(x) == 32 for x in rd) and len(rd) == len(r3["rows"]) + 1)
        check("(e) CSV：百分比欄是兩位小數數字", all(re_pct(x[17]) for x in rd[1:] if x[17]))

        # (f) 資料過舊 → 跳過
        stale = _cut(full, K)
        stale["BBB"] = Ser(full["BBB"].d[:K - 30], full["BBB"].c[:K - 30].tolist())
        rs = update(stale, vfull, today1, tmp / "c", p=p, assets=assets, log=quiet)
        sk_rows = [r for r in rs["rows"] if r["source"] == LIVE and r["symbol"] == "BBB"]
        check("(f) 資料過舊：該列記跳過且不出預測", len(sk_rows) == 2 and all(
            r["status"] == SKIPPED and r["verdict"] == SKIPPED and r["pred"] is None and "S0" in r["flow"] for r in sk_rows))
        check("(f) 資料過舊不影響其他資產", all(r["status"] == PENDING for r in rs["rows"] if r["source"] == LIVE and r["symbol"] == "AAA"))

        # (g) 回測快取：同一週不重算；摘要可轉 JSON
        t_before = (A / "backtest.json").stat().st_mtime_ns
        update(_cut(full, K2), vfull, today1 + dt.timedelta(days=7), A, p=p, assets=assets, log=quiet)
        check("(g) 回測快取：同一週不重算", (A / "backtest.json").stat().st_mtime_ns == t_before)
        sm = summarize(r3["rows"], r3["bt"], today1 + dt.timedelta(days=7), p, assets)
        json.dumps(sm, ensure_ascii=False)
        need = {"version", "horizons", "asof", "batch", "score", "recent", "backtest", "csv", "method"}
        check("(g) 摘要欄位齊全且可轉 JSON", need <= set(sm) and len(sm["batch"]) == per and "steps" in sm["batch"][0])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    bad = [n for n, c in ok if not c]
    if bad:
        print(f"FORECAST SELF-TEST FAILED：{len(bad)}/{len(ok)} 項失敗")
        return 1
    print(f"FORECAST SELF-TEST PASSED（{len(ok)} 項）")
    return 0


def re_pct(x):
    try:
        float(x)
    except ValueError:
        return False
    return len(x.split(".")[-1]) == 2


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    if "--run" in sys.argv:
        build()
        sys.exit(0)
    print("用法：python3 -m gfd.forecast --selftest | --run")
    sys.exit(2)
