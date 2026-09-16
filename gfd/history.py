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
                got, _meta = S.yahoo_chart(sym, interval="1d", start="1994-12-01", adjusted=False)
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


def run(log=print):
    log("[history] 月資料序列")
    cov = fetch_series(log)
    log("[history] 外匯存底／經常帳／美債持有")
    cov += fetch_annual(log)
    log("[history] 公司現金流")
    cov += fetch_company_cf(log)
    log("[history] 單一標的日線")
    fetch_detail(log)
    _save("coverage.json", dict(generated_at=dt.datetime.now().isoformat(timespec="seconds"), items=cov))
    bad = [c for c in cov if c["status"] != "ok"]
    log(f"[history] 完成：{len(cov) - len(bad)} 成功、{len(bad)} 失敗或沿用舊資料")
    return cov
