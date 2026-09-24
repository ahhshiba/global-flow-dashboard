"""抓取 30 年歷史資料 → data/raw/*.json。

單一來源失敗時保留上一次成功的快取並標記 stale，不會用空資料覆蓋。
"""
import datetime as dt
import json
import pathlib
import time

from . import config as C
from . import sources as S

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"


def _load(name, default):
    p = RAW / name
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            pass
    return default


def _save(name, obj):
    RAW.mkdir(parents=True, exist_ok=True)
    tmp = RAW / (name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    tmp.replace(RAW / name)


def _trim(vals, start=C.START_MONTH):
    return {k: v for k, v in sorted(vals.items()) if k >= start}


def _err(e):
    return f"{type(e).__name__}: {e}"[:300]


def splice_before(primary, secondary):
    """primary 起始月之前用 secondary 接續，按最早重疊月的比例換算。"""
    overlap = sorted(k for k in primary if secondary.get(k))
    if not overlap:
        return primary, None
    first, k0 = min(primary), overlap[0]
    ratio = primary[k0] / secondary[k0]
    out = {k: v * ratio for k, v in secondary.items() if k < first}
    out.update(primary)
    return out, k0


def _src_label(src):
    return {"yahoo": f"Yahoo Finance {src[1]}", "cbc": f"台灣央行 {src[1]}",
            "wb_pink": "世界銀行 Pink Sheet", "mof_jgb": "日本財務省 JGB"}[src[0]]


def fetch_series(log):
    old = _load("series.json", {}).get("values", {})
    values, cov, pink = {}, [], None

    def pink_cols(sheet):
        nonlocal pink
        if pink is None:
            try:
                blob, url = S.pink_sheet_workbook()
                pink = {"url": url, "Monthly Prices": S.pink_sheet_columns(blob, "Monthly Prices"),
                        "Monthly Indices": S.pink_sheet_columns(blob, "Monthly Indices")}
            except Exception as e:  # noqa: BLE001
                pink = {"error": _err(e)}
        if "error" in pink:
            raise RuntimeError(pink["error"])
        return pink[sheet]

    for s in C.SERIES:
        src = s["src"]
        try:
            if src[0] == "yahoo":
                vals = S.yahoo_monthly(src[1], "1994-12-01", adjusted=not (len(src) > 2 and src[2] == "close"))
            elif src[0] == "cbc":
                vals = S.cbc_series(src[1], src[2])
            elif src[0] == "wb_pink":
                cols = pink_cols(src[1])
                norm = lambda s: " ".join(s.replace("*", " ").split()).lower()  # noqa: E731 - 表頭有雙空格與 ** 註記
                want = norm(src[2])
                key = (next((k for k in cols if norm(k) == want), None)
                       or next((k for k in cols if norm(k).startswith(want)), None))
                if key is None:
                    raise KeyError(f"Pink Sheet「{src[1]}」找不到「{src[2]}」，現有：{list(cols)[:40]}")
                vals = cols[key]
            elif src[0] == "mof_jgb":
                vals = S.mof_jgb_monthly(src[1])
            else:
                raise ValueError(f"未知來源 {src[0]}")
            spliced = None
            if s.get("splice"):
                sp = s["splice"]
                vals, spliced = splice_before(vals, S.cbc_series(sp[1], sp[2]))
            vals = _trim(vals)
            if not vals:
                raise RuntimeError("起始月之後沒有資料")
            values[s["id"]] = vals
            cov.append(dict(id=s["id"], name=s["name"], source=_src_label(src), status="ok",
                            start=min(vals), end=max(vals), n=len(vals), spliced_at=spliced))
        except Exception as e:  # noqa: BLE001 - 單一序列失敗不影響其他
            if s["id"] in old:
                values[s["id"]] = old[s["id"]]
            cov.append(dict(id=s["id"], name=s["name"], source=_src_label(src),
                            status="stale" if s["id"] in old else "error", error=_err(e)))
        log(f"  {cov[-1]['status']:>5}  {s['id']:<14} {cov[-1].get('start', '')}→{cov[-1].get('end', '')}"
            f" {cov[-1].get('error', '')}")
        if src[0] == "yahoo":
            time.sleep(0.35)

    for mkt, cfg in C.LEADERS.items():
        for ticker, name, _cnyes, _key in cfg["items"]:
            sid = f"lead_{mkt}_{ticker}"
            try:
                vals = _trim(S.yahoo_monthly(ticker, "1994-12-01", adjusted=True))
                if not vals:
                    raise RuntimeError("沒有資料")
                values[sid] = vals
                cov.append(dict(id=sid, name=name, source=f"Yahoo Finance {ticker}", status="ok",
                                start=min(vals), end=max(vals), n=len(vals)))
            except Exception as e:  # noqa: BLE001
                if sid in old:
                    values[sid] = old[sid]
                cov.append(dict(id=sid, name=name, source=f"Yahoo Finance {ticker}",
                                status="stale" if sid in old else "error", error=_err(e)))
            log(f"  {cov[-1]['status']:>5}  {sid:<18} {cov[-1].get('start', '')}→{cov[-1].get('end', '')}")
            time.sleep(0.35)

    _save("series.json", dict(fetched_at=dt.datetime.now().isoformat(timespec="seconds"),
                              pink_url=(pink or {}).get("url"), values=values))
    return cov


def fetch_annual(log):
    old = _load("annual.json", {})
    out, cov = dict(old), []
    codes = [c for c, _ in C.RESERVE_COUNTRIES]
    jobs = [
        ("reserves", "世界銀行 FI.RES.TOTL.CD", lambda: S.worldbank("FI.RES.TOTL.CD", codes)),
        ("current_account", "世界銀行 BN.CAB.XOKA.CD", lambda: S.worldbank("BN.CAB.XOKA.CD", codes)),
        ("tw_reserves", "台灣央行 EF07M01", lambda: S.cbc_series("EF07M01", "外匯存底")),
        ("tic", "美國財政部 TIC", lambda: S.tic_holders([k for k, _ in C.TIC_HOLDERS])),
    ]
    for key, label, fn in jobs:
        try:
            out[key] = fn()
            cov.append(dict(id=key, name=label, source=label, status="ok"))
        except Exception as e:  # noqa: BLE001
            cov.append(dict(id=key, name=label, source=label, status="stale" if key in old else "error",
                            error=_err(e)))
        log(f"  {cov[-1]['status']:>5}  {key} {cov[-1].get('error', '')}")
    out["fetched_at"] = dt.datetime.now().isoformat(timespec="seconds")
    _save("annual.json", out)
    return cov


def fetch_company_cf(log):
    old = _load("company_cf.json", {"us": [], "tw": []})
    old_by = {(m, r["ticker"]): r for m in ("us", "tw") for r in old.get(m, [])}
    out, cov = {"us": [], "tw": []}, []
    for mkt, fetch, unit in (("us", lambda k: S.sec_cashflow(k), "USD"),
                             ("tw", lambda k: (None, S.finmind_cashflow(k)), "TWD")):
        for ticker, name, _cnyes, key in C.LEADERS[mkt]["items"]:
            try:
                entity, years = fetch(key)
                if not years:
                    raise RuntimeError("沒有年度營業現金流")
                out[mkt].append(dict(ticker=ticker, name=name, entity=entity, unit=unit, years=years))
                cov.append(dict(id=f"cf_{ticker}", name=name, source="SEC EDGAR" if mkt == "us" else "FinMind",
                                status="ok", start=years[0]["end"], end=years[-1]["end"], n=len(years)))
            except Exception as e:  # noqa: BLE001
                if (mkt, ticker) in old_by:
                    out[mkt].append(old_by[(mkt, ticker)])
                cov.append(dict(id=f"cf_{ticker}", name=name, source="SEC EDGAR" if mkt == "us" else "FinMind",
                                status="stale" if (mkt, ticker) in old_by else "error", error=_err(e)))
            log(f"  {cov[-1]['status']:>5}  cf {ticker} {cov[-1].get('error', '')}")
            time.sleep(0.4 if mkt == "us" else 1.2)
    out["fetched_at"] = dt.datetime.now().isoformat(timespec="seconds")
    _save("company_cf.json", out)
    return cov


def _c(v):
    a = abs(v)
    return round(v, 4) if a < 10 else round(v, 3) if a < 1000 else round(v, 1)


def _aggregate(rows):
    """rows：[(date, value)] 已排序 → 日／週／月／年收盤（各期間最後一筆），日期存成 1970-01-01 起的天數。"""
    epoch = dt.date(1970, 1, 1)
    today = dt.date.today()
    weeks, months, years = {}, {}, {}
    for d, v in rows:
        iso = d.isocalendar()
        weeks[(iso[0], iso[1])] = (d, v)
        months[(d.year, d.month)] = (d, v)
        years[d.year] = (d, v)

    def pack(pairs):
        return [[(d - epoch).days for d, _ in pairs], [_c(v) for _, v in pairs]]

    def cut(years_back):
        return today - dt.timedelta(days=round(365.25 * years_back))

    return dict(d=pack([r for r in rows if r[0] >= cut(C.DETAIL_KEEP_YEARS["d"])]),
                w=pack([p for p in sorted(weeks.values()) if p[0] >= cut(C.DETAIL_KEEP_YEARS["w"])]),
                m=pack(sorted(months.values())), y=pack(sorted(years.values())))


def fetch_detail(log=print):
    """單一標的線圖用的日線（每次全量重抓，分割調整不會新舊混雜）→ data/raw/detail.json。"""
    old = _load("detail.json", {}).get("items", {})
    specs = dict(C.DETAIL)
    currency = {"us": "USD", "tw": "TWD", "hk": "HKD"}
    for mkt, cfg in C.LEADERS.items():
        for ticker, _name, _cnyes, _key in cfg["items"]:
            specs[f"lead_{mkt}_{ticker}"] = ("yahoo", ticker, currency[mkt])
    start = dt.date.fromisoformat(C.START_MONTH + "-01")
    items, errors, raw = {}, [], {}
    for sid, (src, sym, unit) in specs.items():
        try:
            if src == "yahoo":
                got, _meta = S.yahoo_chart(sym, interval="1d", start="1994-12-01", adjusted=False, completed_only=True)
                time.sleep(0.35)
            elif src == "mof":
                got = [(dt.date.fromisoformat(d), v) for d, v in S.mof_jgb_daily(sym)]
            else:
                raise ValueError(f"未知來源 {src}")
            rows = sorted({d: v for d, v in got if d >= start}.items())
            if len(rows) < 30:
                raise RuntimeError("日資料不足 30 筆")
            raw[sid] = rows
            items[sid] = dict(unit=unit, src=f"{'Yahoo Finance' if src == 'yahoo' else '日本財務省'} {sym}",
                              first=rows[0][0].isoformat(), last=rows[-1][0].isoformat(), **_aggregate(rows))
        except Exception as e:  # noqa: BLE001 - 單一標的失敗沿用上次
            if sid in old:
                items[sid] = dict(old[sid], stale=True)
            errors.append(f"{sid}（{sym}）：{_err(e)}")
    if "b_us10y" in raw and "b_us3m" in raw:
        a, b = dict(raw["b_us10y"]), dict(raw["b_us3m"])
        rows = [(d, a[d] - b[d]) for d in sorted(set(a) & set(b))]
        items["d_curve"] = dict(unit="個百分點", src="Yahoo Finance ^TNX − ^IRX",
                                first=rows[0][0].isoformat(), last=rows[-1][0].isoformat(), **_aggregate(rows))
    _save("detail.json", dict(fetched_at=dt.datetime.now().isoformat(timespec="seconds"), items=items, errors=errors))
    log(f"[detail] 日／週線 {len(items)} 檔、失敗 {len(errors)}" + (f"，第一個：{errors[0]}" if errors else ""))
    return errors


def refresh_daily(log=print):
    """每天跑：月資料（讓當月數字跟上）＋日線。年度資料與公司現金流仍由 run() 每週更新。"""
    quiet = lambda m: None if m.strip().startswith("ok") else log(m)  # noqa: E731 - 只記錄失敗的序列
    log("[history] 月資料序列（每日更新當月數字）")
    cov = fetch_series(quiet)
    ids = {c["id"] for c in cov}
    old = [c for c in _load("coverage.json", {}).get("items", []) if c["id"] not in ids]
    _save("coverage.json", dict(generated_at=dt.datetime.now().isoformat(timespec="seconds"), items=old + cov))
    bad = [c for c in cov if c["status"] != "ok"]
    log(f"[history] 月資料 {len(cov) - len(bad)} 成功、{len(bad)} 失敗或沿用舊資料")
    fetch_detail(log)


def _twse_taiex_hist(log=print):
    """證交所每日加權指數 1990-01～1997-07（Yahoo ^TWII 從 1997-07 才有）。歷史資料不會變，抓過就快取。"""
    cache = _load("twse_taiex_hist.json", {})
    months = [(y, m) for y in range(1990, 1998) for m in range(1, 13) if (y, m) <= (1997, 7)]
    missing = [ym for ym in months if f"{ym[0]:04d}-{ym[1]:02d}" not in cache]
    if missing:
        log(f"[cascade] 證交所加權指數補抓 {len(missing)} 個月（每月間隔 3 秒）")
    for y, m in missing:
        try:
            cache[f"{y:04d}-{m:02d}"] = [(d.isoformat(), v) for d, v in S.twse_taiex_month(y, m)]
        except Exception as e:  # noqa: BLE001 - 缺的月份下次再補
            log(f"[cascade] 證交所 {y}-{m:02d} 失敗：{_err(e)}")
        time.sleep(3)
    if missing:
        _save("twse_taiex_hist.json", cache)
    return sorted((dt.date.fromisoformat(d), v) for rows in cache.values() for d, v in rows)


def _proxy_rows(kind, pid, log):
    if kind == "yahoo":
        rows, _ = S.yahoo_chart(pid, interval="1d", start=C.CASCADE_START, adjusted=True)
        return rows
    if kind == "eia":
        return S.eia_spot_daily(pid)
    if kind == "lbma":
        return S.lbma_daily(pid)
    if kind == "twse":
        return _twse_taiex_hist(log)
    raise ValueError(kind)


def _splice(rows, proxy):
    """在主序列開始日之前接上代理序列的報酬；接點以主序列第一天的價位對齊，接點之後完全是主序列。"""
    if not rows:
        return rows, None
    first_day, first_v = rows[0]
    before = [(d, v) for d, v in proxy if d < first_day and v > 0]
    at = [v for d, v in proxy if d >= first_day and v > 0][:1] or [before[-1][1] if before else None]
    if not before or at[0] is None:
        return rows, None
    k = first_v / at[0]
    return [(d, v * k) for d, v in before] + rows, before[-1][0].isoformat()


def fetch_cascade_daily(log=print):
    """事件衝擊分析用的日線（1979-06 起全量）→ data/raw/daily_cascade.json。不內嵌網頁，只給分析用。

    主序列（ETF／期貨）開始日之前接上 CASCADE_PROXY 的代理序列，series[sym]["proxy"] 記錄接到哪一天。
    """
    old = _load("daily_cascade.json", {}).get("series", {})
    out, errors = {}, []
    for sym, name, layer in C.CASCADE_UNIVERSE:
        try:
            rows, _meta = S.yahoo_chart(sym, interval="1d", start=C.CASCADE_START, adjusted=False, completed_only=True)
            if len(rows) < 250:
                raise RuntimeError(f"日線只有 {len(rows)} 筆")
            proxy = None
            if sym in C.CASCADE_PROXY:
                kind, pid, pname = C.CASCADE_PROXY[sym]
                try:
                    rows, until = _splice(rows, _proxy_rows(kind, pid, log))
                    if until:
                        proxy = dict(id=pid, name=pname, until=until)
                except Exception as e:  # noqa: BLE001 - 代理失敗就只用主序列
                    errors.append(f"{sym} 代理 {pid}：{_err(e)}")
            rows = [(d.isoformat(), v) for d, v in rows if d.isoformat() >= C.CASCADE_START]
            out[sym] = dict(name=name, layer=layer, dates=[d for d, _ in rows],
                            closes=[float(f"{v:.6g}") for _, v in rows], proxy=proxy)
            time.sleep(0.3)
        except Exception as e:  # noqa: BLE001
            if sym in old:
                out[sym] = dict(old[sym], stale=True)
            errors.append(f"{sym}（{name}）：{_err(e)}")
    _save("daily_cascade.json", dict(fetched_at=dt.datetime.now().isoformat(timespec="seconds"), series=out, errors=errors))
    log(f"[cascade] 日線 {len(out)}/{len(C.CASCADE_UNIVERSE)} 檔" + (f"，失敗 {len(errors)}：{errors[0]}" if errors else ""))
    return errors


def run(log=print):
    log("[history] 月資料序列")
    cov = fetch_series(log)
    log("[history] 外匯存底／經常帳／美債持有")
    cov += fetch_annual(log)
    log("[history] 公司現金流")
    cov += fetch_company_cf(log)
    log("[history] 單一標的日線")
    fetch_detail(log)
    log("[history] 事件衝擊用日線")
    fetch_cascade_daily(log)
    _save("coverage.json", dict(generated_at=dt.datetime.now().isoformat(timespec="seconds"), items=cov))
    bad = [c for c in cov if c["status"] != "ok"]
    log(f"[history] 完成：{len(cov) - len(bad)} 成功、{len(bad)} 失敗或沿用舊資料")
    return cov
