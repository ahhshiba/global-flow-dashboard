"""預測帳本 v2（2026-10-10）：日線、5／10／21／63／126／252 個交易日（短線到長線），只增不改，到期自動對答案。

為什麼這樣做（研究結論，不要在這裡重做）：2008 年起每週走步、22 個資產，趨勢／動能／離年線／短期反轉／VIX 查表
對「比平常強或弱」的多空命中都約 50%，IC 約 0；方向命中 55～57% 只是資產本來偏漲，永遠猜漲一樣準。
「同一波動三分位」的歷史 p25–p75 區間實際落入率 48～52%（校準良好，5／10／21 日）——這是唯一敢宣稱的東西。
所以預測值＝同波動狀態下歷史的中位報酬；方向只在歷史上漲機率 ≥55% 或 ≤45% 時標偏漲／偏跌，並明寫
「主要是長期傾向」；趨勢、動能、VIX 只記錄，留給未來用真實帳本檢驗。63／126／252 日是 v2 新增，沒有 v1 級別的研究，
網頁與回報照實呈現它們的回測落入率。

v2 與 v1 的差別：期間從 2 個擴成 6 個；每個判斷條件拆成獨立的數字欄位（51 欄，A～AY）；CSV 只放「即時」列，
不放回測補登、不放系統自己對答案的欄位（第三方人工驗證不能被系統答案影響）；另外匯出判斷條件與欄位說明兩份 CSV
（由本檔常數產生，單一來源）。v1 帳本封存在 data/forecast/archive/。

狀態機：S0 資料檢查 → S1 波動 → S2 趨勢（記錄）→ S3 動能（記錄）→ S4 VIX（記錄）→ S5 查表 → S6 判定 → S7 輸出。

批次節奏（台北時間、ISO 週）：5、10 日每週第一次執行建一批；21、63 日每月「第一週」（該週週一落在當月 1～7 日）建一批；
126、252 日每季第一週（同上且月份 1、4、7、10）建一批。

五條底線（遇到岔路的優先序）：
  1. 不偷看未來：每一列只用「起始日（含）以前」的資料；查表樣本的到期日也 ≤ 起始日；走步回測成績只算「到期日 ≤ 起始日」的決策。
  2. 帳本只增不改：CSV 的 A～AY 與附加欄位寫入後不再動，舊列位置與內容永不改變（試算表手填欄靠列位置對齊）；
     只有 ledger.json 裡的到期對答案欄位（狀態／到期日／實際漲跌／落在區間／方向對錯）會從「待到期」變成「已到期」。
  3. 條件可被機器重算：每個數值都有獨立欄位與門檻；狀態用欄位上顯示的值（2 位小數）判定，第三方照規則表能重算出同一個狀態。
  4. 誠實：輸出不宣稱比回測更強的預測力；補登的列是「事後用同一套程式補算」，只防資料偷看，防不了設計偷看。
  5. 失敗不拖垮既有分析：build() 由呼叫端包 try/except；寫檔都是先寫暫存檔再 os.replace，寫前留一份 ledger.prev.json。

檔案（data/forecast/）：ledger.json（帳本）、forecast.csv（51 欄，只有即時列，試算表 IMPORTDATA 用）、
forecast_rules.csv（判斷條件）、forecast_columns.csv（欄位說明）、backtest.json（走步回測快取）、archive/（舊版封存）。
自我測試：python3 -m gfd.forecast --selftest
"""
import copy
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
SQRT252 = math.sqrt(252)

LIVE, FILL = "即時", "回測補登"
PENDING, DONE, SKIPPED = "待到期", "已到期", "跳過"
PASS = "通過"

# CSV 欄位（A～AY，共 51 欄；順序與表頭就是規格，改動要同步改試算表）。表頭＝SPEC_v2 的欄名；
# 規格裡只用來舉例或列舉選項的括號（例 2026-W41…、低／中／高）不放進表頭，單位與量尺的括號（年化%、0～100）保留。
COLS = [
    ("id", "預測編號"), ("source", "來源"), ("created", "建立日期"), ("version", "模型版本"), ("tier", "期間層級"),
    ("horizon", "期間（交易日）"), ("h_label", "期間（約略）"), ("asset", "資產"), ("symbol", "代號（預測用）"),
    ("tw_buy", "台股可買"), ("start_date", "起始日"), ("start_raw", "起始收盤（未還原，查價用）"),
    ("start_adj", "起始收盤（還原權息，模型用）"), ("due_est", "預計到期日"), ("url", "查價網址"),
    ("n_hist", "S0 歷史交易日數"), ("age", "S0 資料落後天數"), ("s0", "S0 結果"),
    ("vol_ann", "S1 20日波動（年化%）"), ("vol_q1", "S1 門檻低中（年化%）"), ("vol_q2", "S1 門檻中高（年化%）"),
    ("vol_pct", "S1 波動分位（0～100）"), ("vol_state", "S1 波動狀態"),
    ("sma50", "S2 50日均線（還原價）"), ("sma200", "S2 200日均線（還原價）"), ("dist200", "S2 收盤相對200日線%"),
    ("trend_state", "S2 趨勢狀態"),
    ("r20", "S3 20日報酬%"), ("mom_pct", "S3 動能分位（0～100）"), ("mom_state", "S3 動能狀態"),
    ("vix", "S4 VIX"), ("vix_pct", "S4 VIX分位（0～100）"),
    ("sample", "S5 查表樣本"), ("n_days", "S5 樣本數（日）"), ("n_eff", "S5 獨立段數（樣本數÷期間）"),
    ("pred", "S5 預測漲跌%（中位數）"), ("lo", "S5 區間下緣%（p25）"), ("hi", "S5 區間上緣%（p75）"),
    ("p_up", "S5 歷史上漲機率%"), ("rule", "S6 判定規則"), ("verdict", "S6 方向判定"),
    ("bt_n", "回測判定次數"), ("bt_dir", "回測方向命中%"), ("bt_up", "回測永遠猜漲%"), ("bt_maj", "回測多數方向%"),
    ("bt_band", "回測落在區間%"), ("monthly", "月度沙盤推演同期間期望超額%"),
    ("monthly_verdict", "月度沙盤推演同期間回測判定"), ("code", "狀態代碼"), ("flow", "判斷流程"), ("reason", "判斷原因"),
]
CSV_KEYS = [k for k, _ in COLS]
SETTLE_KEYS = ("status", "settled", "actual", "in_band", "dir_ok")   # 只在 ledger.json／網頁：系統自動對答案，不進 CSV
EXTRA_KEYS = ("asset_id", "week", "bt_nall", "steps")               # 帳本裡有、CSV 沒有的欄位（同樣寫入後不改）
ALL_KEYS = CSV_KEYS + list(SETTLE_KEYS) + list(EXTRA_KEYS)
F2_KEYS = {"vol_ann", "vol_q1", "vol_q2", "vol_pct", "dist200", "r20", "mom_pct", "vix", "vix_pct", "pred", "lo", "hi",
           "p_up", "bt_dir", "bt_up", "bt_maj", "bt_band", "monthly"}      # 數字、兩位小數
PX_KEYS = {"start_raw", "start_adj", "sma50", "sma200"}                   # 價格：最多 4 位小數
INT_KEYS = {"horizon", "n_hist", "age", "n_days", "n_eff", "bt_n"}


def _col(i):
    """0 起算的欄位序號 → 試算表欄名（0→A、26→AA、60→BI）。"""
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


LETTER = {k: _col(i) for i, (k, _) in enumerate(COLS)}
LAST_CSV_COL = _col(len(COLS) - 1)         # AY
SHEET_MANUAL = [("AZ", "到期收盤（未還原，手填）"), ("BA", "期間內每股配息（選填）"), ("BB", "查價來源（手填）"),
                ("BC", "驗證人（手填）"), ("BD", "驗證日期（手填）"), ("BE", "備註（手填）")]
SHEET_FORMULA = [("BF", "實際漲跌%（含配息）"), ("BG", "落在區間"), ("BH", "方向對錯"), ("BI", "預測誤差（百分點）")]


def _params():
    return dict(
        version=C.FORECAST_VERSION, horizons=tuple(C.FORECAST_HORIZONS), cadence=dict(C.FORECAST_CADENCE),
        info=dict(C.FORECAST_HORIZON_INFO), quarter_months=tuple(C.FORECAST_QUARTER_MONTHS),
        backfill=tuple(C.FORECAST_BACKFILL), monthly_months=dict(C.FORECAST_MONTHLY_MONTHS),
        no_div=tuple(C.FORECAST_NO_DIVIDEND), bt_start=C.FORECAST_BACKTEST_START,
        min_hist=C.FORECAST_MIN_HISTORY, min_neff=C.FORECAST_MIN_NEFF,
        up=round(C.FORECAST_UP * 100, 6), down=round(C.FORECAST_DOWN * 100, 6), stale=C.FORECAST_STALE_DAYS)


MOM_LO, MOM_HI = 33.33, 66.67          # S3 動能、S4 VIX 分位的三等分門檻（用欄位上的 2 位數比較）


# ───────────────────────── 序列與指標（全部是「只看過去」的滾動量） ─────────────────────────

class Ser:
    """一條日線：dates（升冪）、closes（還原權息收盤）、raw（未還原收盤，可沒有）。
    va／sma／r20 在 index t 只用到 ≤ t 的資料。va＝20 日年化波動（%），四捨五入到 2 位：
    波動狀態、分位、樣本分群全部用這個 2 位數，第三方用欄位上的值就能重算同一個狀態。"""

    def __init__(self, dates, closes, raw=None):
        d, c, rw = [], [], []
        for i, (x, y) in enumerate(zip(dates, closes)):
            if y is None:
                continue
            y = float(y)
            if not math.isfinite(y) or y <= 0 or (d and x <= d[-1]):
                continue
            r = raw[i] if raw is not None and i < len(raw) else None
            d.append(x)
            c.append(y)
            rw.append(float(r) if r is not None and math.isfinite(float(r)) and float(r) > 0 else math.nan)
        self.d = d
        self.c = np.asarray(c, float)
        self.raw = np.asarray(rw, float) if raw is not None else None
        n = self.n = len(d)
        lr = np.full(n, np.nan)
        if n > 1:
            lr[1:] = np.diff(np.log(self.c))
        self.va = np.full(n, np.nan)             # 20 日對數報酬標準差 × √252 × 100，兩位小數
        if n >= 21:
            self.va[20:] = np.round(100 * SQRT252 * _swv(lr[1:], 20).std(axis=1), 2)
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

    def raw_at(self, i):
        """index i 的未還原收盤；沒有（序列沒帶 raw 或該日缺值）→ None。"""
        if self.raw is None or not math.isfinite(self.raw[i]):
            return None
        return round(float(self.raw[i]), 4)


def _r2(x):
    r = round(float(x), 2)
    return r + 0.0 if r == 0 else r


def _vol_state(s, T):
    """S1：到 T（含）為止所有 20 日年化波動（2 位）的 1/3、2/3 分位數（2 位）與目前值、狀態（0 低 1 中 2 高）。"""
    v = s.va[20:T + 1]
    q1, q2 = (float(x) for x in np.round(np.quantile(v, (1 / 3, 2 / 3)), 2))
    cur = float(s.va[T])
    return q1, q2, cur, int(cur >= q1) + int(cur >= q2)


def _lookup(s, T, h, p, full=True, qq=None):
    """S1＋S5：起始日 index T、期間 h。只用 index ≤ T 的資料，樣本的到期也 ≤ T。回傳狀態與查表結果。"""
    q1, q2, cur, st = qq or _vol_state(s, T)
    f = s.c[h:T + 1] / s.c[:T + 1 - h] - 1               # 起點 0..T-h 的 h 日報酬（到期日 ≤ T）
    vs = s.va[:T + 1 - h]
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
        v = s.va[20:T + 1]
        out.update(vol=cur, q1=q1, q2=q2, vpct=float(np.round(100.0 * (v < cur).mean(), 2)),
                   n_all=len(f), ne_all=len(f) // h)
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
    """起始日（含）以前最後一筆 VIX 與它在 1990 起歷史的分位（2 位）；沒有或超過 7 天前 → None。"""
    if vix is None:
        return None
    j = bisect_right(vix.d, date) - 1
    if j < 0 or (dt.date.fromisoformat(date) - dt.date.fromisoformat(vix.d[j])).days > 7:
        return None
    x = float(vix.c[j])
    return _r2(x), _r2(100.0 * float((vix.c[:j + 1] < x).mean()))


def _tercile(pct):
    """分位（2 位）→ 0／1／2（<33.33、33.33～66.67、>66.67）。"""
    return 0 if pct < MOM_LO else 2 if pct > MOM_HI else 1


# ───────────────────────── 批次節奏 ─────────────────────────

def _monday(d):
    return d - dt.timedelta(days=d.weekday())


def _cadences(mon, p):
    """ISO 週（週一＝mon）要建哪幾種節奏：每週都有 week；週一落在當月 1～7 日加 month；再加上月份在季初月加 quarter。"""
    c = {"week"}
    if mon.day <= 7:
        c.add("month")
        if mon.month in p["quarter_months"]:
            c.add("quarter")
    return c


def _horizons_for(mon, p):
    cs = _cadences(mon, p)
    return [h for h in p["horizons"] if p["cadence"][h] in cs]


def _week_label(d):
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def _backfill_plan(today, p):
    """帳本第一次建立時的補登計畫：[(週一, [期間…])]，由舊到新。每種節奏各往回取 N 個（不含本週）。"""
    mon = _monday(today)
    by = {}
    for cad, n in p["backfill"]:
        m, got = mon, 0
        while got < n and (mon - m).days < 7 * 400:
            m -= dt.timedelta(days=7)
            if cad in _cadences(m, p):
                by.setdefault(m, set()).add(cad)
                got += 1
    return [(m, [h for h in p["horizons"] if p["cadence"][h] in cs]) for m, cs in sorted(by.items())]


# ───────────────────────── 走步回測（快取） ─────────────────────────

def _walk_multi(s, hs, p):
    """每個 ISO 週的第一個交易日做一次決策（同 live 的查表），用實際 h 日後的漲跌對答案；多個期間共用同一次波動分位計算。
    每個期間的欄位依決策順序（到期日遞增）：mat 到期日、v 方向(1 偏漲/-1 偏跌/0 不確定)、ok 方向對(0/1)、up 實際>0、inb 落在區間。"""
    i0 = max(p["min_hist"] - 1, bisect_left(s.d, p["bt_start"]), 1)
    wk = s.wk
    out = {h: dict(mat=[], v=[], ok=[], up=[], inb=[]) for h in hs}
    for T in range(i0, s.n - min(hs)):
        if wk[T] == wk[T - 1]:
            continue
        qq = _vol_state(s, T)
        for h in hs:
            if T + h >= s.n:
                continue
            e = out[h]
            dd = _decide(_lookup(s, T, h, p, full=False, qq=qq), p)
            act = _r2(100 * (s.c[T + h] / s.c[T] - 1))
            inb, ok = _grade(dd["verdict"], dd["lo"], dd["hi"], act)
            e["mat"].append(s.d[T + h])
            e["v"].append(1 if dd["verdict"] == "偏漲" else -1 if dd["verdict"] == "偏跌" else 0)
            e["ok"].append(1 if ok else 0)
            e["up"].append(1 if act > 0 else 0)
            e["inb"].append(1 if inb else 0)
    return out


def _bt_asof(e, cutoff):
    """走步回測在 cutoff（含）以前已到期的決策的成績；沒有 → None。
    maj＝多數方向基準＝max(永遠猜漲, 永遠猜跌)；majn＝多數方向猜對的次數（合併各資產時用，基準要逐資產取多數再加總）。"""
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
    up = _r2(100 * upj / nj) if nj else None
    return dict(n=k, nj=nj, hit=hit, upj=upj, bandn=band, majn=max(upj, nj - upj),
                dir=_r2(100 * hit / nj) if nj else None, up=up,
                maj=_r2(max(up, 100 - up)) if nj else None, band=_r2(100 * band / k))


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
        need = [h for h in p["horizons"] if f"{a[1]}|{h}" not in cache["assets"]]
        if not need:
            continue
        for h, e in _walk_multi(s, need, p).items():
            cache["assets"][f"{a[1]}|{h}"] = e
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


def _rule_text(p):
    return f"≥{p['up']:.0f}% 偏漲；≤{p['down']:.0f}% 偏跌；其餘不確定"


def _code(vol=None, trend=None, mom=None, vixq=None, sample=None, call=None):
    """AW 狀態代碼（機器可讀）。vixq：0／1／2 或 None（無 VIX 資料寫 NA）。"""
    return "|".join([f"VOL={vol}", f"TREND={trend}", f"MOM={mom}", f"VIXQ={'NA' if vixq is None else vixq}",
                     f"SAMPLE={sample}", f"CALL={call}"])


def parse_code(code):
    """AW 狀態代碼 → dict（鍵 VOL／TREND／MOM／VIXQ／SAMPLE／CALL；跳過的列是 S0／CALL）。"""
    return dict(x.split("=", 1) for x in str(code).split("|") if "=" in x)


def _skip_row(base, why, known=None):
    base.update(known or {})
    base.update(
        status=SKIPPED, s0=SKIPPED, verdict=SKIPPED, rule=None,
        code=f"S0={SKIPPED}|CALL={SKIPPED}",
        flow=f"S0 資料不合格（{why}）→ 跳過",
        reason=f"{base['asset']}（{base['symbol']}）{why}，這一期不出預測。",
        steps=[dict(s="S0", name="資料檢查", value="不合格", threshold="", result=SKIPPED, used_in_prediction=True)])
    return base


def _noise(bt, h):
    """回測方向命中率的 95% 隨機誤差（百分點）。每週決策的 h 日報酬互相重疊，等效獨立次數＝判定次數÷max(1, h/5)。"""
    ne = bt["nj"] / max(1.0, h / 5.0)
    return 1.96 * 100 * math.sqrt(0.25 / ne), ne


def _band_note(band):
    """回測區間涵蓋率明顯偏離 50% 時，直接在判斷原因裡講出來。"""
    if band < 40:
        return "，明顯偏低（這個資產的區間常常太窄，實際跑出區間的次數比預期多，區間不可信）"
    if band > 60:
        return "，明顯偏高（這個資產的區間常常太寬，區間資訊量很低）"
    return ""


def _swing(h):
    """長期間：相鄰決策高度重疊，涵蓋率在個別年份會大幅擺盪（2026-10-10 回測：63／126／252 日逐年可差三成以上）。"""
    return ("長期間的決策互相重疊，區間涵蓋率在個別年份會大幅擺盪（回測逐年可差三成以上），單一批次不一定接近 50%。"
            if h >= 63 else "")


def _make_row(asset, h, s, vix, cut, created, source, mon, bt, p):
    """組一列。cut＝資料截止日（含），created＝建立日。只用 ≤ cut 的資料。mon＝(月度期望超額, 月度回測判定) 或 None。"""
    aid, sym, _src, name, tw = asset
    week = _week_label(created)
    tier, hlabel = p["info"][h]
    base = {k: None for k in ALL_KEYS}
    base.update(id=f"{week}-{sym}-H{h}", source=source, created=created.isoformat(), version=p["version"], tier=tier,
                horizon=h, h_label=hlabel, asset=name, symbol=sym, tw_buy=tw or "無",
                url=f"https://finance.yahoo.com/quote/{sym}/history", status=PENDING, asset_id=aid, week=week)
    T = bisect_right(s.d, cut.isoformat()) - 1 if s is not None else -1
    if T < 0:
        return _skip_row(base, "沒有資料")
    n = T + 1
    sd = s.d[T]
    last = dt.date.fromisoformat(sd)
    age = (created - last).days
    known = dict(start_date=sd, n_hist=n, age=age, start_raw=s.raw_at(T), start_adj=round(float(s.c[T]), 4))
    if n < p["min_hist"]:
        return _skip_row(base, f"歷史只有 {n} 個交易日，不足 {p['min_hist']} 個", known)
    if age > p["stale"]:
        return _skip_row(base, f"最後收盤 {sd} 已是 {age} 天前，超過 {p['stale']} 天", known)

    L = _lookup(s, T, h, p)
    dd = _decide(L, p)
    vs = ("低", "中", "高")[L["state"]]
    price, c50, c200 = known["start_adj"], round(float(s.sma50[T]), 4), round(float(s.sma200[T]), 4)
    dist = _r2(100 * (price / c200 - 1))
    trend = "多頭" if price > c200 and c50 > c200 else "空頭" if price < c200 and c50 < c200 else "盤整"
    r20x = float(s.r20[T])
    r20 = _r2(100 * r20x)
    mpct = _r2(100.0 * float((s.r20[20:T + 1] < r20x).mean()))
    mom = "弱" if mpct < MOM_LO else "強" if mpct > MOM_HI else "中"
    vx = _vix_asof(vix, sd)
    vixq = _tercile(vx[1]) if vx else None
    due = np.busday_offset(np.datetime64(sd), h, roll="forward")
    pu, v = dd["p_up"], dd["verdict"]
    ne = L["n_eff"]
    sample = "全部歷史" if L["fallback"] else "同波動"
    ann = L["vol"]
    mval, mver = (mon if mon else (None, None))
    mval = None if mval is None else _r2(mval)

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
    hz = f"{h} 個交易日（約{hlabel}）"
    if L["fallback"]:
        t1 = (f"過去{who}波動屬「{vs}」的樣本只有約 {L['ne_same']} 段獨立樣本，不足 {p['min_neff']} 段，改看全部歷史："
              f"{hz}後的漲跌中位數 {_sg(dd['pred'])}%，一半的情況落在 {_sg(dd['lo'])}%～{_sg(dd['hi'])}%，"
              f"上漲機率 {_pt(pu, p)}%（約 {ne} 段獨立樣本）。")
    else:
        t1 = (f"過去{who}波動屬「{vs}」時，{hz}後的漲跌中位數 {_sg(dd['pred'])}%，"
              f"一半的情況落在 {_sg(dd['lo'])}%～{_sg(dd['hi'])}%，上漲機率 {_pt(pu, p)}%（約 {ne} 段獨立樣本）。")
    if ne < p["min_neff"]:
        t1 += f"全部歷史也只有約 {ne} 段獨立樣本（不足 {p['min_neff']} 段），區間與機率的可信度很低，只能當粗略參考。"
    if v == "偏漲":
        t2 = "判定偏漲，主要反映長期上漲傾向，不是當下訊號"
    elif v == "偏跌":
        t2 = "判定偏跌，只表示這個波動狀態下歷史上跌的次數比漲多，是歷史傾向，不是當下訊號"
    else:
        t2 = f"上漲機率介於 {p['down']:.0f}%～{p['up']:.0f}% 之間，不做方向判斷"
    if bt and bt["nj"]:
        # 基準用「永遠猜多數方向」：對本來偏跌的資產，贏「永遠猜漲」太容易，不能拿來說有預測力
        bmaj = bt["maj"]
        bname = "永遠猜漲" if bt["up"] >= 50 else "永遠猜跌"
        gap = bt["dir"] - bmaj
        noise, ne_bt = _noise(bt, h)
        if abs(gap) < 0.5:
            cmp_ = f"和{bname}一樣準，沒有比較準"
        elif gap < 0:
            cmp_ = f"還不如{bname}（差 {-gap:.0f} 個百分點）"
        elif gap < noise:
            cmp_ = f"只比{bname}高 {gap:.0f} 個百分點，在隨機誤差內（±{noise:.0f}），不能說比較準"
        else:
            cmp_ = f"比{bname}高 {gap:.0f} 個百分點（超出隨機誤差 ±{noise:.0f}，但不保證延續）"
        ov = f"，每週決策的 {h} 日報酬互相重疊，等效約 {ne_bt:.0f} 次獨立判定" if h > 5 else ""
        t3 = (f"走步回測（只算起始日前已到期的決策）方向命中 {bt['dir']:.0f}%（{bt['nj']} 次判定{ov}）、"
              f"永遠猜漲 {bt['up']:.0f}%、永遠猜跌 {100 - bt['up']:.0f}%，{cmp_}；"
              f"預測區間實際涵蓋 {bt['band']:.0f}%（理想約 50%）{_band_note(bt['band'])}。{_swing(h)}")
    elif bt:
        t3 = (f"走步回測（{bt['n']} 次決策）沒有方向判定可比；預測區間實際涵蓋 {bt['band']:.0f}%（理想約 50%）"
              f"{_band_note(bt['band'])}。{_swing(h)}")
    else:
        t3 = "沒有可用的走步回測成績。"
    t4 = (f"趨勢{trend}、動能{mom}"
          + (f"、VIX {vx[0]:.0f}（第 {vx[1]:.0f} 分位）" if vx else "、VIX 無資料")
          + "只記錄、不參與預測（2008 年起的走步研究裡它們對漲跌沒有預測力）。")
    reason = t1 + t2 + "。" + t3 + t4

    # ── 步驟明細（網頁用）：每個條件的數值、門檻、結果、有沒有參與預測 ──
    bt_val = (f"方向命中 {bt['dir']:.2f}%／永遠猜漲 {bt['up']:.2f}%／多數方向 {bt['maj']:.2f}%／區間 {bt['band']:.2f}%（{bt['nj']} 次判定）"
              if bt and bt["nj"] else (f"區間 {bt['band']:.2f}%（無方向判定）" if bt else "無"))
    bt_res = ("無方向判定" if not (bt and bt["nj"]) else
              "高於多數方向" if bt["dir"] - bt["maj"] >= _noise(bt, h)[0] else
              "沒有比多數方向準" if bt["dir"] - bt["maj"] < 0.5 else "高出多數方向但在隨機誤差內")
    steps = [
        dict(s="S0", name="資料檢查", value=f"歷史 {n} 個交易日；最後收盤 {sd}（落後 {age} 天）",
             threshold=f"歷史 ≥ {p['min_hist']} 日；落後 ≤ {p['stale']} 天", result=PASS, used_in_prediction=True),
        dict(s="S1", name="波動狀態", value=f"{ann:.2f}%（年化，第 {L['vpct']:.2f} 分位）",
             threshold=f"<{L['q1']:.2f} 低；{L['q1']:.2f}～{L['q2']:.2f} 中；≥{L['q2']:.2f} 高", result=vs, used_in_prediction=True),
        dict(s="S2", name="趨勢狀態", value=f"收盤 {price:g}；50 日線 {c50:g}；200 日線 {c200:g}（離 200 日線 {_sg(dist, 2)}%）",
             threshold="收盤與 50 日線都在 200 日線上＝多頭；都在下＝空頭；其餘盤整", result=trend, used_in_prediction=False),
        dict(s="S3", name="動能狀態", value=f"20 日報酬 {_sg(r20, 2)}%（第 {mpct:.2f} 分位）",
             threshold=f"<{MOM_LO} 弱；>{MOM_HI} 強；其餘中", result=mom, used_in_prediction=False),
        dict(s="S4", name="環境 VIX", value=(f"{vx[0]:.2f}（第 {vx[1]:.2f} 分位）" if vx else "無資料"),
             threshold=f"分位 <{MOM_LO} 低(0)；>{MOM_HI} 高(2)；其餘 1", result=(f"VIXQ={vixq}" if vx else "無資料"),
             used_in_prediction=False),
        dict(s="S5", name="查表", value=f"{sample}樣本 {L['n']} 日（{ne} 段獨立）；中位數 {_sg(dd['pred'], 2)}%；"
                                      f"p25～p75 {_sg(dd['lo'], 2)}%～{_sg(dd['hi'], 2)}%；上漲機率 {_pt(pu, p)}%",
             threshold=(f"同波動獨立段數 ≥ {p['min_neff']}，否則全部歷史"
                        + (f"（本列同波動僅 {L['ne_same']} 段，改用全部歷史）" if L["fallback"] else "")),
             result=f"{sample}，{ne} 段" + ("，可信度低" if ne < p["min_neff"] else ""), used_in_prediction=True),
        dict(s="S6", name="方向判定", value=f"上漲機率 {_pt(pu, p)}%", threshold=_rule_text(p), result=v, used_in_prediction=True),
        dict(s="S7", name="回測參考", value=bt_val,
             threshold="方向命中對照多數方向（高出隨機誤差才算有料）", result=bt_res, used_in_prediction=False),
    ]
    if mval is not None:
        steps.append(dict(s="M", name=f"月度沙盤推演 {p['monthly_months'][h]} 個月",
                          value=f"期望超額 {_sg(mval, 2)}%", threshold="月度模型的走步回測判定",
                          result=mver or "無判定", used_in_prediction=False))
    base.update(
        start_date=sd, start_raw=known["start_raw"], start_adj=price, due_est=str(due), n_hist=n, age=age, s0=PASS,
        vol_ann=ann, vol_q1=L["q1"], vol_q2=L["q2"], vol_pct=L["vpct"], vol_state=vs,
        sma50=c50, sma200=c200, dist200=dist, trend_state=trend,
        r20=r20, mom_pct=mpct, mom_state=mom, vix=vx[0] if vx else None, vix_pct=vx[1] if vx else None,
        sample=sample, n_days=int(L["n"]), n_eff=int(ne), pred=dd["pred"], lo=dd["lo"], hi=dd["hi"], p_up=pu,
        rule=_rule_text(p), verdict=v,
        bt_n=bt["nj"] if bt else None, bt_dir=bt["dir"] if bt else None, bt_up=bt["up"] if bt else None,
        bt_maj=bt["maj"] if bt else None, bt_band=bt["band"] if bt else None, bt_nall=bt["n"] if bt else None,
        monthly=mval, monthly_verdict=(mver if mval is not None else None),
        code=_code(vs, trend, mom, vixq, sample, v), flow=flow, reason=reason, steps=steps)
    return base


def _settle_row(row, s):
    """到期對答案（只記在 ledger.json／網頁，不進 CSV）：起始日之後已有 h 根收盤 → 填實際漲跌%、落在區間、方向對錯。
    回傳是否有改。實際漲跌％用「同一份還原權息序列」的起始日收盤當分母（和預測用的樣本同口徑，除息不會讓分母錯位），
    不用帳本記的起始收盤（那是寫入當時的還原基準，之後除息會被往下調整）。"""
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
    if k in F2_KEYS:
        return f"{float(v):.2f}"
    if k in PX_KEYS:
        return f"{float(v):.4f}".rstrip("0").rstrip(".")
    if k in INT_KEYS:
        return str(int(v))
    return str(v)


def _csv(header, body):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    for r in body:
        w.writerow(r)
    return buf.getvalue()


def csv_text(rows):
    """forecast.csv：只放「即時」列（回測補登與系統自動對答案的欄位都不放，第三方驗證不能被系統答案影響）。"""
    return _csv([h for _, h in COLS], ([_cell(k, r.get(k)) for k, _ in COLS] for r in rows if r["source"] == LIVE))


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
    """寫檔前的最後防線：舊列的預測欄位（CSV 的 A～AY 與附加欄位）一個字都不能變，列的位置也不能動；
    已結案的列連對答案欄位也不能變。"""
    if len(rows) < len(old):
        raise RuntimeError("帳本列數變少，拒絕寫入")
    frozen = CSV_KEYS + list(EXTRA_KEYS)
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


def _archive_old(dirpath, old_version, log):
    """舊版帳本封存到 archive/（ledger_<版>.json、forecast_<版>.csv、backtest_<版>.json），然後從主目錄移走。
    可重跑：封存檔已存在且內容相同就略過複製；內容不同就拒絕（不覆蓋封存）。ledger.json 最後才刪，
    中途當掉下次還認得出是舊版、會再做一次。"""
    arc = dirpath / "archive"
    arc.mkdir(exist_ok=True)
    for src, dst in (("ledger.json", f"ledger_{old_version}.json"), ("forecast.csv", f"forecast_{old_version}.csv"),
                     ("backtest.json", f"backtest_{old_version}.json")):
        sp, dp = dirpath / src, arc / dst
        if not sp.exists():
            continue
        if dp.exists():
            if dp.read_bytes() != sp.read_bytes():
                raise RuntimeError(f"封存檔 {dp} 已存在且和 {sp} 內容不同，拒絕覆蓋")
        else:
            tmp = dp.with_suffix(dp.suffix + ".tmp")
            shutil.copy2(sp, tmp)
            os.replace(tmp, dp)
            if dp.read_bytes() != sp.read_bytes():
                raise RuntimeError(f"封存 {sp} → {dp} 驗證失敗")
    for name in ("ledger.prev.json", "forecast.csv", "backtest.json", "ledger.json"):
        (dirpath / name).unlink(missing_ok=True)
    log(f"[forecast] 舊版 {old_version} 帳本已封存到 {arc}")


def update(series, vix, today, dirpath, monthly=None, p=None, assets=None, log=print):
    """主流程：（舊版封存）→ 回測快取 →（帳本第一次建立時）補登 → 本週即時批次 → 到期對答案 → 寫帳本與三份 CSV。
    series：{代號: Ser}；vix：Ser 或 None；today：台北時間的 date；
    monthly：{月數(3/6/12): dict(vals={asset_id: 期望超額%}, verdict=回測判定)}。"""
    p = p or _params()
    assets = list(assets if assets is not None else C.FORECAST_ASSETS)
    dirpath.mkdir(parents=True, exist_ok=True)
    with _flock(dirpath / ".lock"):
        lp = dirpath / "ledger.json"
        led = _load_ledger(lp)
        migrate = bool(led["rows"]) and led.get("version") != p["version"]
        if migrate or not led["rows"]:
            # 要建新帳本：先確認資料齊全，不齊就什麼都不動（舊版也不封存）。補登列的 L 欄寫了就永遠改不了
            miss = [a[1] for a in assets if series.get(a[1]) is not None and series[a[1]].raw is None
                    and a[1] not in p["no_div"]]
            if miss:
                raise RuntimeError(f"daily_targets.json 沒有未還原收盤 raw_closes（{'、'.join(miss[:5])}…）：先重抓日線再建帳本，"
                                   "否則補登列的起始收盤（L 欄）會永久留白")
        if migrate:
            _archive_old(dirpath, led.get("version") or "v1", log)
            led = dict(version=p["version"], rows=[])
        rows = led["rows"]
        old = copy.deepcopy(rows)
        bt = _ensure_bt(dirpath / "backtest.json", series, assets, p, today, log)
        have = {r["id"] for r in rows}
        deferred = []

        def batch(cut, created, source, hs):
            out = []
            for h in hs:
                for a in assets:
                    s = series.get(a[1])
                    rid = f"{_week_label(created)}-{a[1]}-H{h}"
                    if rid in have:
                        continue
                    T = bisect_right(s.d, cut.isoformat()) - 1 if s is not None else -1
                    b = _bt_asof(bt["assets"].get(f"{a[1]}|{h}"), s.d[T]) if T >= 0 else None
                    mon = None
                    if source == LIVE and h in p["monthly_months"]:
                        mm = (monthly or {}).get(p["monthly_months"][h]) or {}
                        val = (mm.get("vals") or {}).get(a[0])
                        mon = (val, mm.get("verdict")) if val is not None else None
                    row = _make_row(a, h, s, vix, cut, created, source, mon, b, p)
                    if source == LIVE and row["status"] != SKIPPED and row["start_raw"] is None:
                        deferred.append(rid)          # 沒有未還原收盤就不建（寫進去就永遠留白）：下次執行再試
                        continue
                    out.append(row)
                    have.add(rid)
            return out

        new_fill = []
        if not rows:
            for m, hs in _backfill_plan(today, p):    # 補登：當週星期一建立，只用到星期日為止的資料
                new_fill += batch(m - dt.timedelta(days=1), m, FILL, hs)
            rows.extend(new_fill)
        new_live = batch(today, today, LIVE, _horizons_for(_monday(today), p))
        rows.extend(new_live)
        settled = sum(_settle_row(r, series.get(r["symbol"])) for r in rows)
        _check_append_only(old, rows)
        text = csv_text(rows)
        cp = dirpath / "forecast.csv"
        prev = cp.read_text(encoding="utf-8") if cp.exists() else None
        if prev is not None and not text.startswith(prev):     # 寫帳本之前先檢查，免得帳本寫了、CSV 卡住
            raise RuntimeError("forecast.csv 的舊列會被改動（只能在最後新增），拒絕寫入；"
                               "若是帳本重建造成的，請人工確認 CSV 與帳本哪個才對")
        if new_fill or new_live or settled:
            led["version"] = p["version"]
            led["updated"] = dt.datetime.now(TPE).isoformat(timespec="seconds")
            _write_ledger(lp, led)
        if prev != text:
            _atomic_write(cp, text)
        for name, body in (("forecast_rules.csv", rules_csv_text(p)), ("forecast_columns.csv", columns_csv_text(p))):
            f = dirpath / name
            if not f.exists() or f.read_text(encoding="utf-8") != body:
                _atomic_write(f, body)
        if deferred:
            log(f"[forecast] 警告：{len(deferred)} 列即時預測因沒有未還原收盤而暫不建立（下次執行再試）：{'、'.join(deferred[:4])}…")
        log(f"[forecast] 帳本 {len(rows)} 列（新增補登 {len(new_fill)}、即時 {len(new_live)}，本次到期對答案 {settled}）")
    return dict(rows=rows, bt=bt, new_fill=len(new_fill), new_live=len(new_live), settled=settled, deferred=len(deferred))


# ───────────────────────── 判斷條件表與欄位說明表（單一來源：由本檔常數產生） ─────────────────────────

RULES_HEADER = ["規則代碼", "步驟", "名稱", "定義", "門檻或參數", "是否參與預測", "輸出到哪一欄", "研究依據", "模型版本"]
COLUMNS_HEADER = ["欄位代號", "欄位名稱", "定義", "單位／格式", "對應步驟", "誰填"]

# 試算表公式（每欄第 2 列放一格陣列公式；L／AJ／AK／AL／AO 是 CSV 的欄位）
SHEET_FORMULAS = {
    "BF": '=ARRAYFORMULA(IF((AZ2:AZ="")+(L2:L="")>0,"",ROUND((AZ2:AZ+IF(BA2:BA="",0,BA2:BA))/L2:L*100-100,2)))',
    "BG": '=ARRAYFORMULA(IF((BF2:BF="")+(AK2:AK="")>0,"",IF((BF2:BF>=AK2:AK)*(BF2:BF<=AL2:AL),"是","否")))',
    "BH": '=ARRAYFORMULA(IF(BF2:BF="","",IF(AO2:AO="偏漲",IF(BF2:BF>0,"對","錯"),IF(AO2:AO="偏跌",IF(BF2:BF<0,"對","錯"),"不判"))))',
    "BI": '=ARRAYFORMULA(IF((BF2:BF="")+(AJ2:AJ="")>0,"",ROUND(BF2:BF-AJ2:AJ,2)))',
}


def rules_rows(p):
    """判斷條件表。每一列＝一條可照著算的規則；欄位代號對應 forecast.csv。"""
    v = p["version"]
    ev_core = ("v1 研究（2008 起每週走步、22 資產、5／10／21 日）：同波動三分位的 p25–p75 區間實際落入率 48～52%，"
               "是唯一站得住的部分")
    ev_none = ("v1 研究（2008 起、22 資產）：趨勢／動能／離年線／短期反轉／VIX 對『比平常強或弱』的多空命中都約 50%，IC≈0，"
               "所以只記錄、不參與預測")
    hz = "、".join(f"{h}" for h in p["horizons"])
    return [
        ["S0-1", "S0", "歷史長度", "n＝到起始日（含）為止該代號的有效收盤筆數（交易日）；n ≥ 門檻才往下做，否則 R 欄＝跳過、不出預測",
         f"n ≥ {p['min_hist']}（交易日）", "是（把關：不合格就不出預測）", "P、R",
         f"設計值，不是研究結果：{p['min_hist']} 個交易日約 4 年，讓波動三分位門檻與查表至少有 4 年資料可用", v],
        ["S0-2", "S0", "資料新鮮度", "Q 欄＝建立日期 − 起始日（日曆天）；起始日＝建立日（含）以前最後一筆收盤的日期；Q ≤ 門檻才往下做，否則跳過",
         f"Q ≤ {p['stale']}（日曆天）", "是（把關：不合格就不出預測）", "K、Q、R",
         f"設計值：{p['stale']} 天涵蓋週末加連假，超過代表資料源停更", v],
        ["S1-1", "S1", "波動定義",
         "S 欄＝最近 20 筆還原收盤的日對數報酬（ln(今日收盤÷前日收盤)）的母體標準差（分母 20）×√252 ×100，四捨五入到 2 位（年化%）；"
         "之後的分群、分位、狀態一律用這個 2 位數",
         "窗口 20 日；年化係數 √252", "是（決定查哪個波動狀態的歷史樣本）", "S、V", ev_core, v],
        ["S1-2", "S1", "三分位門檻",
         "T、U 欄＝到起始日（含）為止所有 S 值（從第 21 筆起）的 1/3 與 2/3 分位數（線性內插，numpy 預設），四捨五入到 2 位。W 欄：S<T＝低；T≤S<U＝中；S≥U＝高（都是欄位上的值）。"
         "V 欄＝這些 S 值中小於目前 S 的比例×100（0～100，2 位）",
         "分位 33.33%／66.67%", "是", "T、U、V、W", ev_core, v],
        ["S2-1", "S2", "趨勢定義",
         "M 欄＝起始收盤（還原權息）；X 欄＝最近 50 筆還原收盤平均，Y 欄＝最近 200 筆平均（X、Y 取 4 位小數）；Z 欄＝(M÷Y−1)×100（2 位）。"
         "AA 欄：M>Y 且 X>Y＝多頭；M<Y 且 X<Y＝空頭；其餘＝盤整（用欄位上的值比較）",
         "均線 50 日、200 日", "否（只記錄）", "X、Y、Z、AA", ev_none, v],
        ["S3-1", "S3", "動能定義",
         "AB 欄＝(今日還原收盤÷20 筆前還原收盤−1)×100（2 位）。AC 欄＝到起始日（含）為止所有 20 日報酬（從第 21 筆起）中小於今日值的比例×100（2 位）。"
         f"AD 欄：AC<{MOM_LO}＝弱；AC>{MOM_HI}＝強；其餘＝中",
         f"窗口 20 日；分位 {MOM_LO}／{MOM_HI}", "否（只記錄）", "AB、AC、AD", ev_none, v],
        ["S4-1", "S4", "VIX 分位",
         "AE 欄＝起始日（含）以前最後一筆 ^VIX 收盤（超過 7 天前視為無資料，留空）。AF 欄＝1990 年起到該日為止的 VIX 收盤中小於 AE 的比例×100（2 位）。"
         f"AW 欄裡的 VIXQ：AF<{MOM_LO}＝0；AF>{MOM_HI}＝2；其餘＝1；無資料＝NA",
         f"分位 {MOM_LO}／{MOM_HI}", "否（只記錄）", "AE、AF、AW", ev_none, v],
        ["S5-1", "S5", "不偷看規則",
         "S1～S6 與回測的每個數字只用起始日（含）以前的資料；查表樣本的到期日（樣本起點＋期間 F 個交易日）必須 ≤ 起始日；"
         "走步回測只算到期日 ≤ 起始日的決策；補登列再多一層：只用建立日前一天（週日）以前的資料",
         "樣本到期日 ≤ 起始日", "是（約束所有步驟）", "S～AT",
         "selftest：把起始日之後的資料截掉或換成亂數，六個期間的整列 A～AY 都必須逐字相同", v],
        ["S5-2", "S5", "同波動樣本",
         "樣本＝起始日以前每個起點 t（t＋F 的收盤在起始日或之前）中，t 當天的波動狀態（用同一組 T、U）等於目前波動狀態者；"
         "每個樣本取 F（期間）個交易日的還原價報酬 c[t+F]÷c[t]−1。AG 欄＝同波動；AH 欄＝樣本數（日）",
         "同一波動三分位", "是", "AG、AH、AI", ev_core, v],
        ["S5-3", "S5", "樣本不足改用全部歷史",
         "AI 欄＝AH÷F（取整數，獨立段數）。同波動樣本的 AI<門檻 → 改用全部歷史（所有起點，AG 欄＝全部歷史）；"
         "全部歷史的 AI 也<門檻時照樣輸出，但判斷原因（AY）與網頁會註明可信度很低",
         f"獨立段數 < {p['min_neff']}", "是", "AG、AH、AI、AY",
         "設計值（v1 沿用）：期間越長獨立段數越少，63／126／252 日常常只剩個位數段，區間與機率只能當粗略參考", v],
        ["S5-4", "S5", "預測值與區間",
         "AJ 欄＝樣本報酬的中位數；AK 欄＝p25；AL 欄＝p75（分位數用線性內插，numpy 預設）；AM 欄＝樣本中報酬>0 的比例×100；都四捨五入到 2 位（單位 %）",
         "p25、p50、p75；報酬>0", "是", "AJ、AK、AL、AM",
         "5／10／21 日：p25–p75 實際落入率 48～52%（v1 研究）。63／126／252 日是 v2 新增，2026-10-10 走步回測（22 資產、2008 起）合併落入率 "
         "63 日 51.0%、126 日 50.7%、252 日 50.0%，但這三個期間逐年落入率差可達三成以上（約 24%～69%）、個別資產可低到 32%——"
         "平均接近 50%，單一批次不一定；最新數字見 AT 欄與網頁回測合併成績", v],
        ["S6-1", "S6", "方向規則",
         "AO 欄：AM ≥ 上限 → 偏漲；AM ≤ 下限 → 偏跌；其餘 → 不確定（用欄位上的 2 位數比較）。AN 欄逐列寫出這條規則",
         f"{p['up']:.0f}／{p['down']:.0f}（%）", "是", "AN、AO",
         "v1 研究：方向命中 55～57% 只是資產本來偏漲，永遠猜漲一樣準，所以偏漲主要反映長期傾向，不是當下訊號", v],
        ["S7-1", "S7", "走步回測（基準＝多數方向）",
         "2008-01-01 起，每個 ISO 週第一個交易日用同一套 S1～S6 做一次決策，到期後用實際報酬對答案；每一列只引用到期日 ≤ 起始日的決策。"
         "AP 欄＝偏漲／偏跌的決策數（AQ～AS 的分母）；AQ 欄＝方向命中率；AR 欄＝永遠猜漲（這些決策中實際>0 的比例）；"
         "AS 欄＝多數方向＝max(AR, 100−AR)；AT 欄＝實際落在 p25～p75 的比例（分母＝所有決策，含不確定）。比較基準用 AS，不用 AR",
         "隨機誤差 ±1.96×√(0.25÷等效判定數)；等效判定數＝AP÷max(1, F÷5)", "否（只是參考，不改預測）", "AP～AT",
         "偏跌資產贏『永遠猜漲』太容易，所以基準用多數方向（v1 修正）；每週決策的 F 日報酬互相重疊，期間越長等效獨立次數越少（252 日約為 AP÷50）。"
         "2026-10-10 合併回測：方向命中都沒有超過多數方向（5 日 57.1% 對 57.5%，252 日 66.0% 對 71.7%）", v],
        ["B-1", "批次", "批次節奏（短中長線）",
         f"每個 ISO 週（台北時間）第一次執行時建一批。{p['horizons'][0]}、{p['horizons'][1]} 日每週建；21、63 日只在該週週一落在當月 1～7 日的那一週建（每月一次）；"
         "126、252 日只在這種週且月份為 1、4、7、10 時建（每季一次）。同一週重跑不重複建（預測編號＝ISO 週-代號-H期間）",
         f"期間 {hz}（交易日）；週／月（週一 1～7 日）／季（月 {'、'.join(str(m) for m in p['quarter_months'])}）", "否", "A、C、E、F、G",
         "設計：長期間的相鄰樣本高度重疊，所以長期間每月／每季才建一列，避免用重疊樣本灌水", v],
        ["B-2", "批次", "回測補登",
         "帳本第一次建立時，往回補登 12 週（5、10 日）、12 個月（21、63 日）、8 季（126、252 日）；用當時（建立日前一天）的資料、同一套流程；"
         "補登列只在 ledger.json 與網頁，不進 forecast.csv",
         "週 12、月 12、季 8", "否", "B（即時／回測補登）",
         "補登是事後用同一套程式補算，只防得了資料偷看，防不了設計偷看，不能當成當時公布過的預測", v],
        ["M-1", "M", "月度沙盤推演銜接",
         "只有 63／126／252 日的即時列：AU 欄＝月度沙盤推演 3／6／12 個月的期望超額（ens_cal 優先，沒有用 ens；以資產 id 對應，對不上留空）；"
         "AV 欄＝該月度模型的走步回測判定（ensemble 優先，沒有用 ridge）",
         "63→3 個月；126→6 個月；252→12 個月", "否（並排放，不併入預測）", "AU、AV",
         "月度模型是否有效看沙盤推演頁的回測判定；這裡只並排放，不當作本帳本的依據", v],
        ["E-1", "對答案", "系統自動對答案",
         "不在 forecast.csv：起始日之後第 F 根收盤出現時，系統用同一份還原權息序列算實際漲跌%、是否落在 p25～p75、方向對錯，"
         "只記在 ledger.json 與網頁。第三方驗證請在試算表用 AZ～BI 人工查價，不看系統答案",
         "實際漲跌% = c[起始+F]÷c[起始]−1", "否", "（ledger.json／網頁）",
         "第三方驗證不能被系統答案影響，所以系統答案不進 CSV", v],
        ["V-1", "驗證", "第三方驗證公式（試算表）",
         "BF 欄＝(AZ+BA)÷L×100−100，四捨五入 2 位（AZ 空白則空白；BA 空白視為 0；L 空白則空白）；"
         "BG 欄＝BF 在 AK～AL 之間（含邊界）→ 是，否則 否；"
         "BH 欄＝AO 偏漲且 BF>0 或 偏跌且 BF<0 → 對，偏漲且 BF≤0 或 偏跌且 BF≥0 → 錯，不確定／跳過 → 不判；BI 欄＝BF−AJ（百分點）。"
         "公式放每欄第 2 列，一格陣列公式，見 forecast_columns.csv",
         "AZ 用未還原到期收盤；BA 補上期間內每股配息", "否", "BF、BG、BH、BI",
         "與系統自動對答案同一套判斷；差別是價格由人從外部查，且含配息（系統用還原權息價，兩者可能差一點）", v],
    ]


def columns_rows(p):
    """欄位說明表：A～AY（forecast.csv）＋ AZ～BI（試算表手填欄與公式欄）。"""
    L_ = LETTER
    d = {
        "id": ("ISO 週-代號-H期間，例 2026-W41-SPY-H10；整個帳本唯一，同一週重跑不重複建", "文字", "B-1"),
        "source": ("固定為「即時」（建立當週當下產生的預測）；回測補登的列不放進這份 CSV，保留此欄方便未來擴充", "文字", "B-2"),
        "created": ("這一批的建立日（台北時間）", "YYYY-MM-DD", "B-1"),
        "version": ("模型版本；規則改動就升版，舊版封存在 data/forecast/archive/", "文字", "—"),
        "tier": ("短線＝5、10 日；中線＝21、63 日；長線＝126、252 日", "文字", "B-1"),
        "horizon": ("預測期間，單位是該標的自己的交易日（不是日曆日）", "整數", "B-1"),
        "h_label": ("5→1週、10→2週、21→1個月、63→3個月、126→6個月、252→12個月（約略，供閱讀）", "文字", "B-1"),
        "asset": ("資產名稱（22 個資產之一）", "文字", "—"),
        "symbol": ("Yahoo Finance 代號，預測與查價都用這個", "文字", "—"),
        "tw_buy": ("台灣可買的對應標的；「無」＝沒有對應", "文字", "—"),
        "start_date": ("起始日＝建立日（含）以前該標的最後一筆收盤的日期；S1～S6 的數字只用到這天（含）為止的資料", "YYYY-MM-DD", "S0-2"),
        "start_raw": ("起始日當天的未還原收盤（Yahoo 歷史頁的 Close：只調整分割，不調整配息），人工查價與計算實際報酬的分母（試算表 L）。"
                      "TWD=X 沒有配息，與 M 相同", "價格，最多 4 位小數", "S0"),
        "start_adj": ("起始日當天的還原權息收盤（Yahoo Adj Close，寫入當時的值），模型用。之後除息時 Yahoo 會把歷史價往下調，帳本不回頭改", "價格，最多 4 位小數", "S0"),
        "due_est": ("起始日往後數 F 個工作日（週一～週五，未扣休市）估的到期日，只供查價參考；系統對答案用實際第 F 根收盤", "YYYY-MM-DD", "B-1"),
        "url": ("Yahoo Finance 該代號的歷史價格頁，人工查到期收盤用", "URL", "—"),
        "n_hist": (f"到起始日（含）為止的有效收盤筆數；需 ≥ {p['min_hist']}", "整數（交易日）", "S0-1"),
        "age": (f"建立日 − 起始日；需 ≤ {p['stale']}", "整數（日曆天）", "S0-2"),
        "s0": ("通過／跳過；跳過時 AO 也是跳過，S1～S6 欄位留空（起始日、收盤等已知值仍填）", "文字：通過／跳過", "S0"),
        "vol_ann": ("最近 20 筆還原收盤的日對數報酬標準差 ×√252 ×100", "%，2 位小數", "S1-1"),
        "vol_q1": ("到起始日（含）為止所有 20 日年化波動的第 1/3 分位數（低／中分界）", "%，2 位小數", "S1-2"),
        "vol_q2": ("同上的第 2/3 分位數（中／高分界）", "%，2 位小數", "S1-2"),
        "vol_pct": ("歷史上 20 日年化波動小於目前值的比例×100", "0～100，2 位小數", "S1-2"),
        "vol_state": (f"{L_['vol_ann']} 欄 < {L_['vol_q1']} 欄 → 低；{L_['vol_q1']} 欄 ≤ {L_['vol_ann']} 欄 < {L_['vol_q2']} 欄 → 中；{L_['vol_ann']} 欄 ≥ {L_['vol_q2']} 欄 → 高", "文字：低／中／高", "S1-2"),
        "sma50": ("最近 50 筆還原收盤平均", "價格，最多 4 位小數", "S2-1"),
        "sma200": ("最近 200 筆還原收盤平均", "價格，最多 4 位小數", "S2-1"),
        "dist200": (f"({L_['start_adj']}÷{L_['sma200']}−1)×100", "%，2 位小數", "S2-1"),
        "trend_state": (f"{L_['start_adj']}>{L_['sma200']} 且 {L_['sma50']}>{L_['sma200']} → 多頭；兩者都<→ 空頭；其餘盤整。只記錄、不參與預測", "文字：多頭／空頭／盤整", "S2-1"),
        "r20": ("(今日還原收盤÷20 筆前還原收盤−1)×100", "%，2 位小數", "S3-1"),
        "mom_pct": ("歷史上 20 日報酬小於目前值的比例×100", "0～100，2 位小數", "S3-1"),
        "mom_state": (f"{L_['mom_pct']}<{MOM_LO} → 弱；>{MOM_HI} → 強；其餘中。只記錄、不參與預測", "文字：弱／中／強", "S3-1"),
        "vix": ("起始日（含）以前最後一筆 ^VIX 收盤；超過 7 天前視為無資料（留空）。只記錄", "數字，2 位小數", "S4-1"),
        "vix_pct": ("1990 年起到該日為止的 VIX 收盤中小於目前值的比例×100", "0～100，2 位小數", "S4-1"),
        "sample": (f"S5 查表用的樣本：同波動三分位的歷史；若同波動獨立段數 < {p['min_neff']} 就改用全部歷史", "文字：同波動／全部歷史", "S5-2、S5-3"),
        "n_days": ("查表樣本的日數（每個起點算一個樣本）", "整數", "S5-2"),
        "n_eff": (f"{L_['n_days']}÷{L_['horizon']}，取整數；< {p['min_neff']} 代表樣本太少、可信度低", "整數", "S5-3"),
        "pred": ("查表樣本的 F 日報酬中位數（預測漲跌）", "%，2 位小數", "S5-4"),
        "lo": ("樣本報酬的 p25（區間下緣）", "%，2 位小數", "S5-4"),
        "hi": ("樣本報酬的 p75（區間上緣）", "%，2 位小數", "S5-4"),
        "p_up": ("樣本中報酬>0 的比例×100", "%，2 位小數", "S5-4"),
        "rule": (f"本列使用的方向規則：≥{p['up']:.0f}% 偏漲；≤{p['down']:.0f}% 偏跌；其餘不確定", "文字", "S6-1"),
        "verdict": (f"{L_['p_up']}≥{p['up']:.0f} → 偏漲；≤{p['down']:.0f} → 偏跌；其餘不確定；資料不合格 → 跳過。主要反映長期傾向，不是當下訊號", "文字：偏漲／偏跌／不確定／跳過", "S6-1"),
        "bt_n": ("走步回測中，到期日 ≤ 起始日的偏漲／偏跌決策數（回測方向命中、永遠猜漲、多數方向的分母）", "整數", "S7-1"),
        "bt_dir": ("這些決策的方向命中率", "%，2 位小數", "S7-1"),
        "bt_up": ("這些決策中實際報酬>0 的比例（永遠猜漲會對的比例）", "%，2 位小數", "S7-1"),
        "bt_maj": (f"max({L_['bt_up']}, 100−{L_['bt_up']})＝永遠猜多數方向的命中率；比較方向命中時的基準", "%，2 位小數", "S7-1"),
        "bt_band": ("所有回測決策（含不確定）的實際報酬落在 p25～p75 的比例；理想約 50%", "%，2 位小數", "S7-1"),
        "monthly": ("月度沙盤推演同期間（63→3 個月、126→6、252→12）的期望超額；只有這三個期間的即時列才有，對不上資產留空", "%，2 位小數", "M-1"),
        "monthly_verdict": ("該月度模型的走步回測判定（例 時好時壞、樣本外無效）；同上只有 63／126／252", "文字", "M-1"),
        "code": (f"機器可讀，以「|」分隔的 鍵=值：VOL（{L_['vol_state']}）|TREND（{L_['trend_state']}）|MOM（{L_['mom_state']}）|"
                 f"VIXQ（由 {L_['vix_pct']} 三等分：<{MOM_LO}→0、>{MOM_HI}→2、其餘 1；無資料 NA）|SAMPLE（{L_['sample']}）|CALL（{L_['verdict']}）。"
                 "跳過的列只有 S0=跳過|CALL=跳過", "文字，例 VOL=中|TREND=多頭|MOM=強|VIXQ=2|SAMPLE=同波動|CALL=偏漲", "彙總"),
        "flow": ("S0→S6 走過的狀態與數值，一行", "文字", "S0～S6"),
        "reason": ("白話的判斷原因，含回測與基準的比較（對照多數方向）與可信度提醒", "文字", "S0～S7"),
    }
    out = []
    for k, name in COLS:
        df, unit, step = d[k]
        out.append([LETTER[k], name, df, unit, step, "系統"])
    man = {
        "AZ": ("起始日後第 F 個交易日（N 欄只是估計；遇休市以實際第 F 個交易日為準）的未還原收盤，從 O 欄網址或券商查", "價格（未還原）", "V-1", "手填"),
        "BA": ("起始日之後到到期日（含）之間，每股實際配發的現金股利合計（未還原價口徑）；不知道就留空（留空視為 0，含息報酬會偏低）", "價格", "V-1", "手填"),
        "BB": ("AZ 的查價來源，例 Yahoo／券商", "文字", "V-1", "手填"),
        "BC": ("驗證人", "文字", "V-1", "手填"),
        "BD": ("驗證日期", "YYYY-MM-DD", "V-1", "手填"),
        "BE": ("備註", "文字", "V-1", "手填"),
        "BF": (f"實際漲跌（含配息）＝(AZ+BA)÷L×100−100，AZ 空白則空白。公式（放 BF2，勿手動輸入）：{SHEET_FORMULAS['BF']}", "%，2 位小數", "V-1", "公式"),
        "BG": (f"BF 在 AK～AL 之間（含邊界）→ 是，否則 否。公式（放 BG2）：{SHEET_FORMULAS['BG']}", "文字：是／否", "V-1", "公式"),
        "BH": (f"AO 偏漲且 BF>0 或 偏跌且 BF<0 → 對；相反 → 錯；不確定／跳過 → 不判。公式（放 BH2）：{SHEET_FORMULAS['BH']}", "文字：對／錯／不判", "V-1", "公式"),
        "BI": (f"預測誤差＝BF−AJ（實際減預測中位數）。公式（放 BI2）：{SHEET_FORMULAS['BI']}", "百分點，2 位小數", "V-1", "公式"),
    }
    for code, name in SHEET_MANUAL + SHEET_FORMULA:
        df, unit, step, who = man[code]
        out.append([code, name, df, unit, step, who])
    return out


def rules_csv_text(p):
    return _csv(RULES_HEADER, rules_rows(p))


def columns_csv_text(p):
    return _csv(COLUMNS_HEADER, columns_rows(p))


# ───────────────────────── 給網頁用的摘要 ─────────────────────────

METHOD = [
    "期間與節奏：5、10 日（短線）每週建一批；21、63 日（中線）每月第一週（該週週一落在當月 1～7 日）建一批；126、252 日（長線）每季第一週（1、4、7、10 月）建一批。同一週重跑不重複建。",
    "S0 資料檢查：歷史至少 1000 個交易日、最後一筆收盤不超過 7 個日曆天前；不合格的列記「跳過」，不出預測。",
    "S1 波動狀態：20 日對數報酬標準差年化（%，2 位小數）；用到起始日為止的全部歷史算 1/3、2/3 分位門檻，分成低／中／高。門檻與目前值都寫在欄位裡。",
    "S2 趨勢狀態（只記錄）：收盤與 200 日線、50 日線與 200 日線都在上面＝多頭，都在下面＝空頭，其餘盤整。",
    "S3 動能狀態（只記錄）：20 日報酬在自己歷史的分位，低於 33.33 為弱、高於 66.67 為強，其餘為中。",
    "S4 環境（只記錄）：起始日前最近一筆 VIX 收盤，與它在 1990 年以來歷史的分位。",
    "S5 查表：只用到期日不晚於起始日的歷史樣本（不偷看），取「同一波動三分位」的 h 日報酬；獨立段數＝樣本數÷h，"
    "不足 15 段就改用全部歷史；全部歷史也不足 15 段時照樣輸出，但標明可信度很低（期間越長越常發生）。輸出中位數（預測漲跌）、p25～p75（區間）、上漲機率。",
    "S6 判定：上漲機率 ≥55% 偏漲、≤45% 偏跌，其餘不確定。這主要是資產的長期傾向，不是當下訊號。",
    "S7 輸出：寫入帳本（只增不改），附同資產同期間的走步回測成績（方向命中、永遠猜漲、多數方向、落在區間比例，只算起始日前已到期的決策）。"
    "每週決策的 h 日報酬互相重疊，期間越長等效獨立次數越少，隨機誤差也越大。",
    "起始收盤有兩種：未還原（人工查價用，試算表 L 欄）與還原權息（模型用）。到期對答案用同一份還原權息序列，除息不會讓分母錯位。",
    "系統自動對答案：起始日之後有 h 根收盤就填實際漲跌%、是否落在區間、方向對錯，只記在帳本與網頁，不放進給試算表的 CSV；"
    "試算表的實際結果由人工查價填寫，是獨立的第三方驗證。",
    "補登：帳本第一次建立時，用截至當時的資料補 12 週（5、10 日）、12 個月（21、63 日）、8 季（126、252 日）；補登與即時的成績分開統計，補登列不進 CSV。"
    "補登是事後用同一套程式補算，只防得了資料偷看，防不了「設計看過這段歷史」，不能當成當時公布過的預測。",
    "月度沙盤推演銜接：63／126／252 日的即時列並排放月度模型 3／6／12 個月的期望超額與它的回測判定；只是並排，不併入預測。",
    "誠實聲明：2008 年起的研究裡，趨勢、動能、離年線、短期反轉、VIX 對漲跌都沒有預測力（IC 約 0）；方向命中 55～57% 只是因為這些資產本來偏漲，"
    "永遠猜漲一樣準。唯一驗證過的是 5／10／21 日的區間校準（同波動三分位的 p25～p75 實際落入率約 50%）；63／126／252 日是新增的，回測落入率看網頁的回測合併成績。",
]


def _rate(num, den):
    return _r2(100 * num / den) if den else None


def _score(rows, source, p):
    """系統自動對答案的成績（即時／補登分開）。maj＝已判定樣本合併後的多數方向（max(猜漲, 猜跌)）。"""
    out = {}
    for h in p["horizons"]:
        allr = [r for r in rows if r["source"] == source and r["horizon"] == h]
        rs = [r for r in allr if r["status"] != SKIPPED]
        due = [r for r in rs if r["status"] == DONE]
        jd = [r for r in due if r["dir_ok"] in ("對", "錯")]
        up = _rate(sum(1 for r in jd if r["actual"] > 0), len(jd))
        out[str(h)] = dict(
            due=len(due), pending=len(rs) - len(due), skipped=len(allr) - len(rs),
            band=_rate(sum(1 for r in due if r["in_band"] == "是"), len(due)),
            dir=_rate(sum(1 for r in jd if r["dir_ok"] == "對"), len(jd)), dir_n=len(jd),
            up=up, maj=None if up is None else _r2(max(up, 100 - up)))
    return out


def _bt_pooled(bt, assets, p):
    """走步回測各資產合併：方向命中、永遠猜漲、多數方向（逐資產取多數再加總）、落在區間。"""
    out = {}
    for h in p["horizons"]:
        n = nj = hit = upj = majn = band = cnt = 0
        for a in assets:
            r = _bt_asof(bt["assets"].get(f"{a[1]}|{h}"), "9999-12-31")
            if r:
                n += r["n"]; nj += r["nj"]; hit += r["hit"]; upj += r["upj"]; majn += r["majn"]; band += r["bandn"]; cnt += 1
        out[str(h)] = dict(n=n, nj=nj, assets=cnt, dir=_rate(hit, nj), up=_rate(upj, nj), maj=_rate(majn, nj),
                           band=_rate(band, n))
    return out


def _lean(r):
    return {k: v for k, v in r.items() if k != "steps"}


def summarize(rows, bt, today, p, assets):
    wk = _week_label(today)
    batch = [dict(r) for r in rows if r["source"] == LIVE and r["week"] == wk]
    done = sorted(((r["settled"], i) for i, r in enumerate(rows) if r["status"] == DONE), reverse=True)
    hs = _horizons_for(_monday(today), p)
    out = dict(
        version=p["version"], asof=today.isoformat(), week=wk,
        horizons=[dict(h=h, tier=p["info"][h][0], label=p["info"][h][1], cadence=p["cadence"][h]) for h in p["horizons"]],
        this_week_horizons=hs,
        batch=batch,
        score=dict(live=_score(rows, LIVE, p), backfill=_score(rows, FILL, p)),
        recent=[_lean(rows[i]) for _, i in done[:40]],
        backtest=dict(_bt_pooled(bt, assets, p), start=p["bt_start"]),
        csv="data/forecast.csv", rules_csv="data/forecast_rules.csv", columns_csv="data/forecast_columns.csv",
        method=list(METHOD),
        rules=[dict(zip(RULES_HEADER, r)) for r in rules_rows(p)],
        columns=[dict(zip(COLUMNS_HEADER, r)) for r in columns_rows(p)],
        rows=len(rows), live_rows=sum(1 for r in rows if r["source"] == LIVE))
    return out


# ───────────────────────── 對外入口 ─────────────────────────

def _load_raw(name):
    p = RAW / name
    if not p.exists():
        raise FileNotFoundError(f"找不到 {p}，預測帳本沒有資料可用（不寫任何東西）")
    return json.loads(p.read_text(encoding="utf-8"))


def monthly_map(scen):
    """月度沙盤推演 3／6／12 個月的期望超額（ens_cal，沒有就 ens；以資產 id 對應）與該月度模型的回測判定
    （ensemble 的 verdict，沒有就用 ridge 的）。回傳 {月數: dict(vals={asset_id: %}, verdict=文字或 None)}。"""
    out = {}
    sc = scen or {}
    for m in (3, 6, 12):
        vals = {}
        for r in (sc.get("assets") or {}).get(str(m)) or []:
            sid = r.get("sid", r.get("id"))
            v = r.get("ens_cal")
            if v is None:
                v = r.get("ens")
            if sid is not None and v is not None:
                vals[sid] = float(v)
        b = (sc.get("backtest") or {}).get(str(m)) or {}
        verdict = (b.get("ensemble") or {}).get("verdict") or (b.get("ridge") or {}).get("verdict")
        out[m] = dict(vals=vals, verdict=verdict)
    return out


def _mk_ser(v, sym, p):
    raw = v.get("raw_closes")
    if raw is not None and len(raw) != len(v["dates"]):
        raw = None
    if raw is None and sym in p["no_div"]:
        raw = v["closes"]                      # 沒有配息的代號：未還原＝還原
    return Ser(v["dates"], v["closes"], raw)


def build(scen=None, log=print, today=None, dirpath=None):
    """analysis.run() 呼叫：更新帳本與 CSV，回傳給網頁用的摘要（可轉 JSON）。出錯就丟例外，由呼叫端記錄。"""
    today = today or dt.datetime.now(TPE).date()
    p = _params()
    tg, cs = _load_raw("daily_targets.json").get("series", {}), _load_raw("daily_cascade.json").get("series", {})
    pools = dict(targets=tg, cascade=cs)
    series = {}
    for _aid, sym, src, _name, _tw in C.FORECAST_ASSETS:
        v = pools.get(src, {}).get(sym)
        if v and v.get("dates"):
            series[sym] = _mk_ser(v, sym, p)
    vv = cs.get("^VIX")
    vix = Ser(vv["dates"], vv["closes"]) if vv and vv.get("dates") else None
    res = update(series, vix, today, dirpath or FDIR, monthly=monthly_map(scen), p=p, log=log)
    out = summarize(res["rows"], res["bt"], today, p, C.FORECAST_ASSETS)
    json.dumps(out, ensure_ascii=False)          # 確認可序列化（有 numpy 型別會在這裡報錯，而不是在寫 analysis.json 時）
    sc = out["score"]["backfill"]
    log("[forecast] 補登已到期 " + "、".join(f"{h} 日 {v['due']} 列 區間{v['band']}% 方向{v['dir']}%（{v['dir_n']} 判，多數方向 {v['maj']}%）"
                                          for h, v in sc.items() if v["due"]))
    bp = out["backtest"]
    log("[forecast] 走步回測合併 " + "、".join(f"{h} 日 方向{bp[str(h)]['dir']}%／猜漲{bp[str(h)]['up']}%／多數{bp[str(h)]['maj']}%／"
                                          f"區間{bp[str(h)]['band']}%（n={bp[str(h)]['n']}）" for h in p["horizons"]))
    return out


# ───────────────────────── 自我測試（合成資料） ─────────────────────────

# 表頭：和 SPEC_v2 的 A～AY 欄名逐字對照（故意不從 COLS 產生，才測得到 COLS 被改壞）
SPEC_HEADER = [
    "預測編號", "來源", "建立日期", "模型版本", "期間層級", "期間（交易日）", "期間（約略）", "資產", "代號（預測用）", "台股可買",
    "起始日", "起始收盤（未還原，查價用）", "起始收盤（還原權息，模型用）", "預計到期日", "查價網址",
    "S0 歷史交易日數", "S0 資料落後天數", "S0 結果",
    "S1 20日波動（年化%）", "S1 門檻低中（年化%）", "S1 門檻中高（年化%）", "S1 波動分位（0～100）", "S1 波動狀態",
    "S2 50日均線（還原價）", "S2 200日均線（還原價）", "S2 收盤相對200日線%", "S2 趨勢狀態",
    "S3 20日報酬%", "S3 動能分位（0～100）", "S3 動能狀態", "S4 VIX", "S4 VIX分位（0～100）",
    "S5 查表樣本", "S5 樣本數（日）", "S5 獨立段數（樣本數÷期間）", "S5 預測漲跌%（中位數）", "S5 區間下緣%（p25）",
    "S5 區間上緣%（p75）", "S5 歷史上漲機率%", "S6 判定規則", "S6 方向判定",
    "回測判定次數", "回測方向命中%", "回測永遠猜漲%", "回測多數方向%", "回測落在區間%",
    "月度沙盤推演同期間期望超額%", "月度沙盤推演同期間回測判定", "狀態代碼", "判斷流程", "判斷原因"]
SHEET_HEADERS_REST = ["到期收盤（未還原，手填）", "期間內每股配息（選填）", "查價來源（手填）", "驗證人（手填）", "驗證日期（手填）",
                      "備註（手填）", "實際漲跌%（含配息）", "落在區間", "方向對錯", "預測誤差（百分點）"]


def _synth(n, seed, drift=0.0004, base_sig=0.010):
    rng = np.random.default_rng(seed)
    days = np.busday_offset(np.datetime64("2012-01-02"), np.arange(n), roll="forward")
    dates = [str(x) for x in days]
    sig = base_sig * (1 + 0.8 * np.sin(np.arange(n) / 150.0 + seed))
    c = 100 * np.exp(np.cumsum(drift + sig * rng.standard_normal(n)))
    return dates, c


def _cut_date(series, date):
    """每條序列截到 date（含）；raw 一起截。"""
    iso = date.isoformat()
    out = {}
    for sym, s in series.items():
        k = bisect_right(s.d, iso)
        out[sym] = Ser(s.d[:k], s.c[:k].tolist(), None if s.raw is None else s.raw[:k].tolist())
    return out


def _row_sig(r):
    """一列的 CSV 內容（逐欄字串）＋步驟明細，用來比對『逐字相同』。"""
    return [_cell(k, r.get(k)) for k in CSV_KEYS] + [json.dumps(r.get("steps"), ensure_ascii=False)]


def _expected_horizons(mon, p):
    """測試用的獨立實作：把規則直接寫死，不呼叫 _cadences。"""
    hs = [5, 10]
    if mon.day <= 7:
        hs += [21, 63]
        if mon.month in (1, 4, 7, 10):
            hs += [126, 252]
    return hs


def _selftest():
    ok = []

    def check(name, cond, info=""):
        ok.append((name, bool(cond)))
        print(("  PASS " if cond else "  FAIL ") + name + (f"  {info}" if info and not cond else ""))

    t_start = time.time()
    quiet = lambda *_a, **_k: None
    N = 3300
    p = dict(_params(), bt_start="2020-01-01")            # 合成資料的回測從 2020 開始，測試才跑得快
    assets = [("a_one", "AAA", "targets", "測試資產甲", "0050.TW"), ("a_two", "BBB", "targets", "測試資產乙", "")]
    full = {}
    for i, a in enumerate(assets):
        d, c = _synth(N, 7 + i)
        full[a[1]] = Ser(d, c.tolist(), (c * (1.1 if i == 0 else 1.0)).tolist())      # AAA：未還原 > 還原（有配息）；BBB：相同
    vd, vc = _synth(N, 99, drift=0.0, base_sig=0.03)
    vfull = Ser(vd, (15 * vc / vc[0]).tolist())
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="fc_selftest_"))
    try:
        # (a) 節奏
        mondays = [dt.date(2020, 1, 6) + dt.timedelta(days=7 * k) for k in range(52 * 12)]
        pure_ok = all(_horizons_for(m, p) == _expected_horizons(m, p) for m in mondays)
        check("(a) 節奏：2020～2031 每個週一，期間集合＝獨立寫死的規則", pure_ok)
        by_year = {}
        for m in mondays:
            if m.year in range(2020, 2032):
                e = by_year.setdefault(m.year, [0, 0])
                e[0] += 21 in _horizons_for(m, p)
                e[1] += 126 in _horizons_for(m, p)
        check("(a) 節奏：每年剛好 12 個月初週、4 個季初週", all(v == [12, 4] for k, v in by_year.items() if k in range(2020, 2032)), str(by_year))
        ex = {dt.date(2026, 10, 5): [5, 10, 21, 63, 126, 252], dt.date(2026, 10, 12): [5, 10], dt.date(2026, 11, 2): [5, 10, 21, 63],
              dt.date(2027, 1, 4): [5, 10, 21, 63, 126, 252], dt.date(2026, 12, 28): [5, 10], dt.date(2026, 9, 28): [5, 10]}
        check("(a) 節奏：2026-W41 全六個期間、10-12 只有 5／10、11-02 加 21／63、2027-01-04 全六個", all(_horizons_for(m, p) == v for m, v in ex.items()))

        A = tmp / "a"
        weeks = [dt.date(2023, 9, 25) + dt.timedelta(days=7 * k) for k in range(8)]
        per_h = len(assets)
        prev_sig, prev_csv, prev_n = None, "", 0
        cadence_ok, stable_ok, idem_ok, prefix_ok, ledger_bytes = True, True, True, True, None
        info_c = ""
        n_rows_by_week = []
        for k, mon in enumerate(weeks):
            today = mon + dt.timedelta(days=2)
            ser = _cut_date(full, today)
            r = update(ser, vfull, today, A, p=p, assets=assets, log=quiet)
            exp_h = _expected_horizons(mon, p)
            live_now = [x for x in r["rows"] if x["source"] == LIVE and x["week"] == _week_label(mon)]
            got_h = sorted({x["horizon"] for x in live_now})
            if got_h != sorted(exp_h) or len(live_now) != per_h * len(exp_h) or r["new_live"] != per_h * len(exp_h):
                cadence_ok = False
                info_c = f"{mon} 預期 {exp_h} 得到 {got_h} 新增 {r['new_live']}"
            sig = [_row_sig(x) for x in r["rows"]]
            if prev_sig is not None and sig[:len(prev_sig)] != prev_sig:
                stable_ok = False
            prev_sig = sig
            csv_now = (A / "forecast.csv").read_text(encoding="utf-8")
            if not csv_now.startswith(prev_csv):
                prefix_ok = False
            prev_csv = csv_now
            files1 = {n: (A / n).read_bytes() for n in ("ledger.json", "forecast.csv", "forecast_rules.csv", "forecast_columns.csv")}
            r2 = update(ser, vfull, today, A, p=p, assets=assets, log=quiet)
            if r2["new_live"] or r2["new_fill"] or len(r2["rows"]) != len(r["rows"]) or any((A / n).read_bytes() != b for n, b in files1.items()):
                idem_ok = False
            n_rows_by_week.append(len(r["rows"]))
        check("(a) 節奏：每週實際建立的列＝該週應有的期間 × 資產（含 10-02 季初週 6 個、11-06 月初週 4 個）", cadence_ok, info_c)
        rowsA = r["rows"]
        fill = [x for x in rowsA if x["source"] == FILL]
        exp_cnt = {5: 12, 10: 12, 21: 12, 63: 12, 126: 8, 252: 8}
        got_cnt = {h: sum(1 for x in fill if x["horizon"] == h) // per_h for h in exp_cnt}
        check("(a) 補登：每週期間 12 週、每月期間 12 個月、每季期間 8 季", got_cnt == exp_cnt, str(got_cnt))
        mon0 = weeks[0]
        exp_q, m = [], mon0
        while len(exp_q) < 8:
            m -= dt.timedelta(days=7)
            if m.day <= 7 and m.month in (1, 4, 7, 10):
                exp_q.append(m.isoformat())
        check("(a) 補登：126／252 日的建立日＝往回數 8 個季初週一", sorted({x["created"] for x in fill if x["horizon"] == 252}) == sorted(exp_q))
        check("(a) 補登：建立日＝週一、起始日在建立日前（只用前一天以前的資料）", all(
            dt.date.fromisoformat(x["created"]).weekday() == 0 and x["start_date"] < x["created"] for x in fill if x["status"] != SKIPPED))
        ids = [x["id"] for x in rowsA]
        check("(a) 預測編號不重複，格式 年-W週-代號-H期間", len(set(ids)) == len(ids) and all(x["id"] == f"{x['week']}-{x['symbol']}-H{x['horizon']}" for x in rowsA))

        # (c) 只增不改＋冪等（跨週、跨月、跨季）
        check("(c) 只增不改：每週新增後，舊列的 A～AY 與步驟逐字相同、位置不動（跨週／跨月／跨季）", stable_ok)
        check("(c) 只增不改：forecast.csv 每次都是上一版的延伸（舊列位元組不變）", prefix_ok)
        check("(c) 冪等：同一週重跑，列數與帳本／三份 CSV 位元組都不變", idem_ok)
        check("(c) 備份檔 ledger.prev.json 存在", (A / "ledger.prev.json").exists())
        snap = json.loads(json.dumps(rowsA))
        bad = 0
        for key, val in (("pred", 99.0), ("id", "x"), ("reason", "改"), ("start_raw", 1.0), ("monthly", 5.0), ("steps", []), ("code", "x"),
                         ("vol_ann", 1.0), ("asset_id", "z")):
            tampered = json.loads(json.dumps(snap))
            tampered[3][key] = val
            try:
                _check_append_only(snap, tampered)
            except RuntimeError:
                bad += 1
        check("(c) 防線：改舊列任何預測欄位（A～AY 與附加欄位）都會被拒絕寫入", bad == 9, str(bad))
        done_row = next(i for i, x in enumerate(snap) if x["status"] == DONE)
        t2 = json.loads(json.dumps(snap))
        t2[done_row]["actual"] = 123.0
        try:
            _check_append_only(snap, t2)
            g2 = False
        except RuntimeError:
            g2 = True
        try:
            _check_append_only(snap, snap[:-1])
            g3 = False
        except RuntimeError:
            g3 = True
        check("(c) 防線：已結案的列被改動、列數變少都會被拒絕", g2 and g3)

        # (d) CSV 格式：只有即時列、51 欄、沒有對答案欄位
        raw = (A / "forecast.csv").read_bytes()
        check("(d) CSV：無 BOM、UTF-8", not raw.startswith(b"\xef\xbb\xbf") and raw.decode("utf-8") is not None)
        rd = list(csv.reader(io.StringIO(raw.decode("utf-8"))))
        live_rows = [x for x in rowsA if x["source"] == LIVE]
        check("(d) CSV：表頭 51 欄（A～AY）且與 SPEC_v2 逐字一致", len(rd[0]) == 51 and rd[0] == SPEC_HEADER and LAST_CSV_COL == "AY", str(len(rd[0])))
        check("(d) CSV：每列 51 欄、列數＝即時列＋表頭，且順序＝帳本裡即時列的順序",
              all(len(x) == 51 for x in rd) and len(rd) == len(live_rows) + 1 and [x[0] for x in rd[1:]] == [x["id"] for x in live_rows])
        check("(d) CSV：只有「即時」列（沒有回測補登）", {x[1] for x in rd[1:]} == {LIVE} and len(fill) > 0 and not any(x["id"] in {y[0] for y in rd[1:]} for x in fill))
        settle_names = {"狀態", "到期日", "實際漲跌%（系統）", "落在區間", "方向對錯", "實際漲跌%"}
        check("(d) CSV：沒有任何系統對答案欄位（狀態／到期日／實際漲跌／落在區間／方向對錯）", not (settle_names & set(rd[0])) and all(k not in CSV_KEYS for k in SETTLE_KEYS))
        check("(d) 帳本裡有已到期的即時列（系統照常對答案），但 CSV 位元組沒有因此改變（見 (c) 的延伸檢查）",
              any(x["source"] == LIVE and x["status"] == DONE for x in rowsA))
        import re as _re
        pat2 = _re.compile(r"^-?\d+\.\d{2}$")
        fmt_ok = True
        for k in CSV_KEYS:
            j = CSV_KEYS.index(k)
            for x in rd[1:]:
                c_ = x[j]
                if not c_:
                    continue
                if k in F2_KEYS and not pat2.match(c_):
                    fmt_ok = False
                if k in INT_KEYS and not c_.isdigit():
                    fmt_ok = False
                if k in PX_KEYS and not _re.match(r"^\d+(\.\d{1,4})?$", c_):
                    fmt_ok = False
        check("(d) CSV：百分比欄是兩位小數數字、整數欄是整數、價格欄最多 4 位小數", fmt_ok)
        j = {k: CSV_KEYS.index(k) for k in CSV_KEYS}
        aa = [x for x in rd[1:] if x[j["symbol"]] == "AAA" and x[j["s0"]] == PASS]
        bb = [x for x in rd[1:] if x[j["symbol"]] == "BBB" and x[j["s0"]] == PASS]
        check("(d) 起始收盤：未還原（L）＝1.1 倍還原價（M，有配息的 AAA）；沒有配息的 BBB 兩者相同",
              all(abs(float(x[j["start_raw"]]) - 1.1 * float(x[j["start_adj"]])) < 6e-4 for x in aa) and
              all(x[j["start_raw"]] == x[j["start_adj"]] for x in bb))
        check("(d) 查價網址、期間層級與約略名稱",
              all(x[j["url"]] == f"https://finance.yahoo.com/quote/{x[j['symbol']]}/history" for x in rd[1:]) and
              all((x[j["tier"]], x[j["h_label"]]) == tuple(p["info"][int(x[j["horizon"]])]) for x in rd[1:]))
        check("(d) 欄位字母：判定規則＝AN、方向判定＝AO、狀態代碼＝AW、判斷原因＝AY",
              LETTER["rule"] == "AN" and LETTER["verdict"] == "AO" and LETTER["code"] == "AW" and LETTER["reason"] == "AY" and
              LETTER["start_raw"] == "L" and LETTER["pred"] == "AJ" and LETTER["lo"] == "AK" and LETTER["hi"] == "AL")

        # (e) 判斷條件表與欄位說明表
        rr = list(csv.reader(io.StringIO((A / "forecast_rules.csv").read_text(encoding="utf-8"))))
        need_codes = {"S0-1", "S0-2", "S1-1", "S1-2", "S2-1", "S3-1", "S4-1", "S5-1", "S5-2", "S5-3", "S5-4", "S6-1", "S7-1", "B-1", "V-1"}
        need_cols = ["規則代碼", "步驟", "名稱", "定義", "門檻或參數", "是否參與預測", "輸出到哪一欄", "研究依據", "模型版本"]
        check("(e) 規則 CSV：欄位齊全、每列欄數一致、規則代碼涵蓋規格列出的 15 條",
              rr[0] == need_cols and all(len(x) == len(need_cols) for x in rr) and need_codes <= {x[0] for x in rr[1:]} and
              all(all(c_.strip() for c_ in x) for x in rr[1:]))
        cr = list(csv.reader(io.StringIO((A / "forecast_columns.csv").read_text(encoding="utf-8"))))
        letters = [x[0] for x in cr[1:]]
        check("(e) 欄位說明 CSV：表頭 6 欄、涵蓋 A～BI 共 61 列且依序", cr[0] == ["欄位代號", "欄位名稱", "定義", "單位／格式", "對應步驟", "誰填"]
              and len(cr) == 62 and letters == [_col(i) for i in range(61)] and letters[0] == "A" and letters[-1] == "BI", f"{len(cr)}")
        check("(e) 欄位說明 CSV：A～AY 的欄名＝forecast.csv 表頭，AZ～BI 的欄名與誰填（手填／公式）",
              [x[1] for x in cr[1:52]] == SPEC_HEADER and [x[1] for x in cr[52:]] == SHEET_HEADERS_REST and
              [x[5] for x in cr[1:52]] == ["系統"] * 51 and [x[5] for x in cr[52:58]] == ["手填"] * 6 and [x[5] for x in cr[58:]] == ["公式"] * 4 and
              all(all(c_.strip() for c_ in x) for x in cr[1:]))
        check("(e) 欄位說明：BF～BI 的公式文字放在定義裡且引用的欄位字母正確",
              cr[58][0] == "BF" and "AZ2:AZ" in cr[58][2] and "L2:L" in cr[58][2] and "BA2:BA" in cr[58][2]
              and cr[59][0] == "BG" and "AK2:AK" in cr[59][2] and "AL2:AL" in cr[59][2] and "BF2:BF" in cr[59][2]
              and cr[60][0] == "BH" and "AO2:AO" in cr[60][2] and "BF2:BF" in cr[60][2]
              and cr[61][0] == "BI" and "AJ2:AJ" in cr[61][2] and "BF2:BF" in cr[61][2])
        check("(e) 兩份定義檔由程式常數產生：重新產生的內容與檔案逐字相同",
              rules_csv_text(p) == (A / "forecast_rules.csv").read_text(encoding="utf-8") and columns_csv_text(p) == (A / "forecast_columns.csv").read_text(encoding="utf-8"))

        # (f) 狀態代碼可解析回 W／AA／AD／AF／AG／AO
        f_ok, f_info = True, ""
        for x in rowsA:
            pc = parse_code(x["code"])
            if x["status"] == SKIPPED:
                if pc != {"S0": SKIPPED, "CALL": SKIPPED} or x["verdict"] != SKIPPED:
                    f_ok = False
                continue
            vq = pc.get("VIXQ")
            exp_vq = "NA" if x["vix_pct"] is None else str(0 if x["vix_pct"] < 33.33 else 2 if x["vix_pct"] > 66.67 else 1)
            if not (pc.get("VOL") == x["vol_state"] and pc.get("TREND") == x["trend_state"] and pc.get("MOM") == x["mom_state"]
                    and vq == exp_vq and pc.get("SAMPLE") == x["sample"] and pc.get("CALL") == x["verdict"]):
                f_ok, f_info = False, str(x["code"])
        check("(f) 狀態代碼（AW）可解析回 W／AA／AD／AF／AG／AO 的值（含 VIXQ 由 AF 三等分）", f_ok, f_info)
        ex_code = parse_code("VOL=中|TREND=多頭|MOM=強|VIXQ=2|SAMPLE=同波動|CALL=偏漲")
        check("(f) 規格範例代碼可解析", ex_code == dict(VOL="中", TREND="多頭", MOM="強", VIXQ="2", SAMPLE="同波動", CALL="偏漲"))
        # 狀態可由欄位上的值重算（機器可重算）
        rc_ok = True
        for x in rowsA:
            if x["status"] == SKIPPED:
                continue
            w = "低" if x["vol_ann"] < x["vol_q1"] else "中" if x["vol_ann"] < x["vol_q2"] else "高"
            aa_ = "多頭" if x["start_adj"] > x["sma200"] and x["sma50"] > x["sma200"] else "空頭" if x["start_adj"] < x["sma200"] and x["sma50"] < x["sma200"] else "盤整"
            ad = "弱" if x["mom_pct"] < 33.33 else "強" if x["mom_pct"] > 66.67 else "中"
            ao = "偏漲" if x["p_up"] >= 55 else "偏跌" if x["p_up"] <= 45 else "不確定"
            if (w, aa_, ad, ao) != (x["vol_state"], x["trend_state"], x["mom_state"], x["verdict"]) or (x["dist200"] > 0) != (x["start_adj"] > x["sma200"]):
                rc_ok = False
            if x["bt_up"] is not None and abs(x["bt_maj"] - max(x["bt_up"], 100 - x["bt_up"])) > 0.011:
                rc_ok = False
            if x["n_eff"] != x["n_days"] // x["horizon"] or x["sample"] not in ("同波動", "全部歷史"):
                rc_ok = False
        check("(f) 條件可重算：用欄位上顯示的值重算 W／AA／AD／AO、多數方向、獨立段數，全部列一致", rc_ok)

        # (b) 不偷看：六個期間各取一列補登，截斷與換成亂數後整列相同
        full_end = _cut_date(full, weeks[-1] + dt.timedelta(days=2))
        peek_ok, peek_info = True, ""
        for h in p["horizons"]:
            cand = [x for x in rowsA if x["source"] == FILL and x["horizon"] == h and x["status"] != SKIPPED and x["symbol"] == "AAA"]
            row = cand[len(cand) // 2]
            S = row["start_date"]
            a = assets[0]
            j0 = bisect_right(full_end["AAA"].d, S)
            rng = np.random.default_rng(h)
            junk, trunc = {}, {}
            for sym, s in full_end.items():
                j_ = bisect_right(s.d, S)
                c2 = s.c.copy()
                c2[j_:] = c2[j_:] * np.exp(np.cumsum(rng.standard_normal(len(c2) - j_) * 0.05 + 0.01))
                r2_ = s.raw.copy()
                r2_[j_:] = r2_[j_:] * 7
                junk[sym] = Ser(s.d, c2.tolist(), r2_.tolist())
                trunc[sym] = Ser(s.d[:j_], s.c[:j_].tolist(), s.raw[:j_].tolist())
            vj = Ser(vfull.d, np.concatenate([vfull.c[:bisect_right(vfull.d, S)], vfull.c[bisect_right(vfull.d, S):] * 3]).tolist())
            vt = Ser(vfull.d[:bisect_right(vfull.d, S)], vfull.c[:bisect_right(vfull.d, S)].tolist())
            created = dt.date.fromisoformat(row["created"])
            cut = created - dt.timedelta(days=1)
            sigs = []
            for label, ser_map, vx in (("完整序列", full_end, vfull), ("起始日截斷", trunc, vt), ("起始日後亂數", junk, vj)):
                bt_c = _ensure_bt(tmp / f"bt_{h}_{label}", ser_map, assets, p, weeks[-1], quiet)
                s = ser_map["AAA"]
                T = bisect_right(s.d, cut.isoformat()) - 1
                rr_ = _make_row(a, h, s, vx, cut, created, FILL, None, _bt_asof(bt_c["assets"].get(f"AAA|{h}"), s.d[T]), p)
                sigs.append(_row_sig(rr_))
            same = sigs[0] == sigs[1] == sigs[2]
            from_ledger = sigs[0] == _row_sig(row)
            if not (same and from_ledger):
                peek_ok = False
                peek_info += f" h={h}: 相同={same} 與帳本一致={from_ledger}"
        check("(b) 不偷看：六個期間各一列，完整序列＝起始日截斷＝起始日後換成亂數（A～AY＋步驟逐字相同），且與帳本一致", peek_ok, peek_info)

        # 月度沙盤推演銜接：只有 63／126／252
        B = tmp / "b"
        mon_in = {3: dict(vals={"a_one": 1.23}, verdict="時好時壞"), 6: dict(vals={"a_one": -2.5}, verdict="樣本外無效"),
                  12: dict(vals={}, verdict="時好時壞")}
        tday = dt.date(2023, 10, 4)                    # 2023-10-02 那週：季初週，全六個期間
        rb = update(_cut_date(full, tday), vfull, tday, B, monthly=mon_in, p=p, assets=assets, log=quiet)
        lv = {(x["symbol"], x["horizon"]): x for x in rb["rows"] if x["source"] == LIVE}
        check("(M) 月度銜接：63／126 日有期望超額與回測判定，其餘期間空白；對不上的資產／期間（252、BBB）留空",
              lv[("AAA", 63)]["monthly"] == 1.23 and lv[("AAA", 63)]["monthly_verdict"] == "時好時壞" and
              lv[("AAA", 126)]["monthly"] == -2.5 and lv[("AAA", 126)]["monthly_verdict"] == "樣本外無效" and
              lv[("AAA", 252)]["monthly"] is None and lv[("AAA", 252)]["monthly_verdict"] is None and
              lv[("BBB", 63)]["monthly"] is None and all(lv[("AAA", h)]["monthly"] is None for h in (5, 10, 21)) and
              any(s_["s"] == "M" for s_ in lv[("AAA", 63)]["steps"]))
        ms = monthly_map({"assets": {"3": [{"sid": "x", "ens_cal": 1.5, "ens": 9.0}, {"sid": "y", "ens_cal": None, "ens": 2.0}], "6": [], "12": []},
                          "backtest": {"3": {"ensemble": {"verdict": "甲"}, "ridge": {"verdict": "乙"}}, "6": {"ridge": {"verdict": "乙"}}, "12": {}}})
        check("(M) monthly_map：ens_cal 優先、否則 ens；回測判定 ensemble 優先、否則 ridge",
              ms[3] == dict(vals={"x": 1.5, "y": 2.0}, verdict="甲") and ms[6]["verdict"] == "乙" and ms[12]["verdict"] is None)

        # (g) 到期對答案：構造已知價格（5 日與 10 日）
        Cd = tmp / "c"
        K = bisect_right(full["AAA"].d, "2023-10-04") - 1
        ser0 = _cut_date(full, dt.date(2023, 10, 4))
        rc = update(ser0, vfull, dt.date(2023, 10, 4), Cd, p=p, assets=assets, log=quiet)
        csv_c0 = (Cd / "forecast.csv").read_bytes()
        live = {(x["symbol"], x["horizon"]): x for x in rc["rows"] if x["source"] == LIVE}
        base_px = float(ser0["AAA"].c[K])
        ext = full["AAA"]
        c_ext = ext.c.copy()
        c_ext[K + 5] = base_px * 1.05
        c_ext[K + 10] = base_px * 0.97
        fut = dict(full)
        fut["AAA"] = Ser(ext.d[:K + 11], c_ext[:K + 11].tolist(), ext.raw[:K + 11].tolist())
        fut["BBB"] = Ser(full["BBB"].d[:K + 11], full["BBB"].c[:K + 11].tolist(), full["BBB"].raw[:K + 11].tolist())
        mid = {sym: Ser(s.d[:K + 7], s.c[:K + 7].tolist(), s.raw[:K + 7].tolist()) for sym, s in fut.items()}
        rm = update(mid, vfull, dt.date(2023, 10, 4), Cd, p=p, assets=assets, log=quiet)
        csv_c1 = (Cd / "forecast.csv").read_bytes()
        lm = {(x["symbol"], x["horizon"]): x for x in rm["rows"] if x["source"] == LIVE}
        check("(g) 到期：5 日列到期、10 日列仍待到期", lm[("AAA", 5)]["status"] == DONE and lm[("AAA", 10)]["status"] == PENDING)
        x5 = lm[("AAA", 5)]
        check("(g) 到期：實際漲跌%＝+5.00、到期日＝起始後第 5 根", x5["actual"] == 5.0 and x5["settled"] == ext.d[K + 5], f"{x5['actual']} {x5['settled']}")
        exp_in = x5["lo"] <= 5.0 <= x5["hi"]
        exp_dir = None if x5["verdict"] == "不確定" else ((x5["verdict"] == "偏漲") == (5.0 > 0))
        check("(g) 到期：落在區間與方向對錯與獨立計算一致",
              x5["in_band"] == ("是" if exp_in else "否") and x5["dir_ok"] == ("不判" if exp_dir is None else "對" if exp_dir else "錯"))
        rf = update(fut, vfull, dt.date(2023, 10, 4), Cd, p=p, assets=assets, log=quiet)
        lf = {(x["symbol"], x["horizon"]): x for x in rf["rows"] if x["source"] == LIVE}
        check("(g) 到期：10 日列實際漲跌%＝-3.00；已結案的 5 日列不再變動", lf[("AAA", 10)]["status"] == DONE and lf[("AAA", 10)]["actual"] == -3.0 and lf[("AAA", 5)] == lm[("AAA", 5)])
        csv_c2 = (Cd / "forecast.csv").read_bytes()
        check("(g) 到期對答案不影響 CSV：對答案前後三次執行的 forecast.csv 位元組相同（且帳本確實有列已到期）",
              csv_c0 == csv_c1 == csv_c2 and rf["settled"] >= 0 and any(x["status"] == DONE for x in rf["rows"]))
        s_u = Ser([str(x) for x in np.busday_offset(np.datetime64("2020-01-01"), np.arange(40), roll="forward")], [100.0] * 40)
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
            good &= (rw["status"] == DONE and rw["in_band"] == e_in and rw["dir_ok"] == e_dir and rw["actual"] == _r2(px - 100.0) and rw["settled"] == ss.d[15])
        check("(g) 到期：偏漲／偏跌／不確定 × 區間內外 單元測試", good)
        sk = dict(base_row, status=SKIPPED)
        check("(g) 到期：跳過的列不碰", _settle_row(sk, s_u) is False and sk["status"] == SKIPPED)

        # (h) 資料過舊 → 跳過；沒有未還原收盤 → 暫不建立（同週補建）；缺 raw 不能建新帳本
        stale = _cut_date(full, dt.date(2023, 10, 4))
        stale["BBB"] = _cut_date({"BBB": full["BBB"]}, dt.date(2023, 8, 1))["BBB"]
        rs = update(stale, vfull, dt.date(2023, 10, 4), tmp / "d", p=p, assets=assets, log=quiet)
        sk_rows = [x for x in rs["rows"] if x["source"] == LIVE and x["symbol"] == "BBB"]
        check("(h) 資料過舊：該資產所有期間的列記跳過、不出預測、AW 只有 S0／CALL", len(sk_rows) == 6 and all(
            x["status"] == SKIPPED and x["verdict"] == SKIPPED and x["pred"] is None and x["s0"] == SKIPPED and "S0" in x["flow"]
            and x["code"] == "S0=跳過|CALL=跳過" for x in sk_rows))
        check("(h) 資料過舊不影響其他資產", all(x["status"] in (PENDING, DONE) for x in rs["rows"] if x["source"] == LIVE and x["symbol"] == "AAA"))
        a3 = assets + [("a_three", "CCC", "targets", "測試資產丙", "")]
        d3, c3 = _synth(N, 31)
        full3 = dict(full, CCC=Ser(d3, c3.tolist(), (c3 * 1.2).tolist()))
        no_raw = lambda ser: dict(ser, CCC=Ser(ser["CCC"].d, ser["CCC"].c.tolist()))
        try:
            update(no_raw(_cut_date(full3, dt.date(2023, 10, 4))), vfull, dt.date(2023, 10, 4), tmp / "e0", p=p, assets=a3, log=quiet)
            g1 = False
        except RuntimeError:
            g1 = not (tmp / "e0" / "ledger.json").exists()
        check("(h) 缺未還原收盤時不建新帳本（補登列的 L 欄會永久留白），也不寫任何檔", g1)
        E = tmp / "e"
        update(_cut_date(full3, dt.date(2023, 10, 4)), vfull, dt.date(2023, 10, 4), E, p=p, assets=a3, log=quiet)
        n_before = len(json.loads((E / "ledger.json").read_text(encoding="utf-8"))["rows"])
        w2 = dt.date(2023, 10, 11)
        r_a = update(no_raw(_cut_date(full3, w2)), vfull, w2, E, p=p, assets=a3, log=quiet)
        cc_rows = [x for x in r_a["rows"] if x["symbol"] == "CCC" and x["week"] == _week_label(w2)]
        check("(h) 沒有未還原收盤的即時列暫不建立（其他資產照建），不寫進永遠留白的列", r_a["deferred"] == 2 and not cc_rows and r_a["new_live"] == 4)
        r_b = update(_cut_date(full3, w2), vfull, w2, E, p=p, assets=a3, log=quiet)
        cc_rows = [x for x in r_b["rows"] if x["symbol"] == "CCC" and x["week"] == _week_label(w2)]
        check("(h) 同一週資料補齊後再跑：補建那兩列（附在最後面），L 有值", r_b["new_live"] == 2 and len(cc_rows) == 2 and all(x["start_raw"] for x in cc_rows)
              and r_b["rows"][-1]["symbol"] == "CCC")

        # (i) 舊版封存（v1 → v2）
        V = tmp / "v"
        V.mkdir()
        old_files = {"ledger.json": b'{"version":"v1","rows":[\n{"id":"2026-W41-SPY-10","status":"\xe5\xbe\x85\xe5\x88\xb0\xe6\x9c\x9f"}\n]}\n',
                     "forecast.csv": b"v1 csv\n", "backtest.json": b'{"key":"v1|2026-W41"}', "ledger.prev.json": b"prev"}
        for n_, b_ in old_files.items():
            (V / n_).write_bytes(b_)
        update(_cut_date(full, dt.date(2023, 10, 4)), vfull, dt.date(2023, 10, 4), V, p=p, assets=assets, log=quiet)
        arc = V / "archive"
        check("(i) v1 封存：archive/ 有 ledger_v1.json、forecast_v1.csv、backtest_v1.json，內容與原檔位元組相同",
              all((arc / f"{a_}_v1.{e_}").read_bytes() == old_files[f"{a_}.{e_}"] for a_, e_ in (("ledger", "json"), ("forecast", "csv"), ("backtest", "json")))
              and sorted(x.name for x in arc.iterdir()) == ["backtest_v1.json", "forecast_v1.csv", "ledger_v1.json"])
        led_v = json.loads((V / "ledger.json").read_text(encoding="utf-8"))
        check("(i) v1 封存：主目錄是全新的 v2 帳本（沒有 v1 列）、舊 prev 已移走、再跑一次不再封存也不重複建",
              led_v["version"] == "v2" and all(x["version"] == "v2" for x in led_v["rows"]) and not (V / "ledger.prev.json").exists())
        b_before = (V / "ledger.json").read_bytes()
        update(_cut_date(full, dt.date(2023, 10, 4)), vfull, dt.date(2023, 10, 4), V, p=p, assets=assets, log=quiet)
        check("(i) v1 封存：重跑位元組不變", (V / "ledger.json").read_bytes() == b_before and len(list(arc.iterdir())) == 3)
        (A / "ledger.json").rename(A / "ledger.gone")
        try:
            update(_cut_date(full, weeks[-1] + dt.timedelta(days=2)), vfull, weeks[-1] + dt.timedelta(days=2), A, p=p, assets=assets, log=quiet)
            g4 = False
        except FileNotFoundError:
            g4 = True
        (A / "ledger.gone").rename(A / "ledger.json")
        check("(i) 帳本不見但 ledger.prev.json 還在 → 拒絕重建（不寫任何檔）", g4 and not (A / "ledger.json").stat().st_size == 0)

        # (i2) 要建新版帳本但缺 raw：什麼都不動（舊版也不封存）；CSV 舊列對不上時拒絕，且帳本不先寫
        V2 = tmp / "v2"
        V2.mkdir()
        for n_, b_ in old_files.items():
            (V2 / n_).write_bytes(b_)
        try:
            update(no_raw(_cut_date(full3, dt.date(2023, 10, 4))), vfull, dt.date(2023, 10, 4), V2, p=p, assets=a3, log=quiet)
            g5 = False
        except RuntimeError:
            g5 = all((V2 / n_).read_bytes() == b_ for n_, b_ in old_files.items()) and not (V2 / "archive").exists()
        check("(i) 舊版帳本在、新版資料不齊（缺 raw）→ 拒絕，舊版檔案原封不動、不封存", g5)
        F_ = tmp / "f"
        shutil.copytree(A, F_)
        csv_f = (F_ / "forecast.csv").read_text(encoding="utf-8")
        (F_ / "forecast.csv").write_text(csv_f.replace("2023-09-27", "2023-09-28", 1), encoding="utf-8")
        led_f = (F_ / "ledger.json").read_bytes()
        nxt = weeks[-1] + dt.timedelta(days=9)
        try:
            update(_cut_date(full, nxt), vfull, nxt, F_, p=p, assets=assets, log=quiet)
            g6 = False
        except RuntimeError:
            g6 = (F_ / "ledger.json").read_bytes() == led_f
        check("(i) forecast.csv 舊列被動過 → 拒絕寫入，而且帳本沒有先被寫", g6)

        # (j) 回測快取、摘要
        t_before = (A / "backtest.json").stat().st_mtime_ns
        update(_cut_date(full, weeks[-1] + dt.timedelta(days=2)), vfull, weeks[-1] + dt.timedelta(days=2), A, p=p, assets=assets, log=quiet)
        check("(j) 回測快取：同一週不重算", (A / "backtest.json").stat().st_mtime_ns == t_before)
        today_s = weeks[1] + dt.timedelta(days=2)            # 季初週（10-02 那週）
        rsum = update(_cut_date(full, today_s), vfull, today_s, tmp / "s", monthly=mon_in, p=p, assets=assets, log=quiet)
        sm = summarize(rsum["rows"], rsum["bt"], today_s, p, assets)
        json.dumps(sm, ensure_ascii=False)
        need = {"version", "horizons", "asof", "batch", "score", "recent", "backtest", "csv", "rules_csv", "columns_csv", "method", "rules"}
        check("(j) 摘要欄位齊全且可轉 JSON", need <= set(sm))
        check("(j) 摘要：horizons 含層級與約略名稱；batch＝本週所有即時列（含 steps 六個鍵）",
              [(x["h"], x["tier"], x["label"]) for x in sm["horizons"]] == [(h, *p["info"][h]) for h in p["horizons"]] and
              len(sm["batch"]) == per_h * 6 and all(x["source"] == LIVE for x in sm["batch"]) and
              all(set(s_) == {"s", "name", "value", "threshold", "result", "used_in_prediction"} for x in sm["batch"] for s_ in x["steps"]) and
              {s_["s"] for s_ in sm["batch"][0]["steps"]} >= {f"S{i}" for i in range(8)})
        check("(j) 摘要：score 即時／補登 × 六個期間，含 已到期／落在區間／方向命中／判數／多數方向",
              set(sm["score"]) == {"live", "backfill"} and all(set(sm["score"][s_]) == {str(h) for h in p["horizons"]} for s_ in sm["score"]) and
              all({"due", "band", "dir", "dir_n", "maj"} <= set(v) for s_ in sm["score"].values() for v in s_.values()))
        check("(j) 摘要：recent ≤40 列、backtest 六個期間含 方向命中／永遠猜漲／多數方向／落在區間／n",
              len(sm["recent"]) <= 40 and all(str(h) in sm["backtest"] and {"dir", "up", "maj", "band", "n"} <= set(sm["backtest"][str(h)]) for h in p["horizons"]))
        rules_from_csv = list(csv.DictReader(io.StringIO(rules_csv_text(p))))
        check("(j) 摘要：rules 與 forecast_rules.csv 同內容、csv／rules_csv／columns_csv 相對路徑",
              sm["rules"] == rules_from_csv and sm["csv"] == "data/forecast.csv" and sm["rules_csv"] == "data/forecast_rules.csv" and sm["columns_csv"] == "data/forecast_columns.csv")
        check("(j) 回測合併的多數方向 ≥ 永遠猜漲與永遠猜跌中較大者（逐資產取多數再加總）",
              all(v["maj"] is None or v["maj"] >= max(v["up"], 100 - v["up"]) - 0.011 for v in sm["backtest"].values() if isinstance(v, dict) and "maj" in v))
        check("(j) 判斷原因含期間、回測與基準比較；長期間提醒重疊", all("多數" in x["reason"] or "永遠猜" in x["reason"] for x in sm["batch"] if x["status"] != SKIPPED)
              and any("重疊" in x["reason"] for x in sm["batch"] if x["horizon"] == 252))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    bad = [n for n, c in ok if not c]
    print(f"（{time.time() - t_start:.0f} 秒）")
    if bad:
        print(f"FORECAST SELF-TEST FAILED：{len(bad)}/{len(ok)} 項失敗")
        return 1
    print(f"FORECAST SELF-TEST PASSED（{len(ok)} 項）")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    if "--run" in sys.argv:
        build()
        sys.exit(0)
    print("用法：python3 -m gfd.forecast --selftest | --run")
    sys.exit(2)
