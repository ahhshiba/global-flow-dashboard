"""資料來源轉接層。只用 Python 標準函式庫。

每個函式回傳乾淨的 {"YYYY-MM": value} 或結構化資料；網路錯誤一律往上拋，
由呼叫端記進 coverage，不在這裡吞掉。
"""
import datetime as dt
import html
import io
import itertools
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

UA = "Mozilla/5.0 (X11; Linux x86_64) GlobalFlowDashboard/1.0"
SEC_UA = "GlobalFlowDashboard personal-research"


def http_get(url, *, headers=None, timeout=45, retries=2, backoff=2.5):
    h = {"User-Agent": UA}
    h.update(headers or {})
    last = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001 - 重試後原樣拋出
            last = e
            if attempt < retries:
                time.sleep(backoff * (attempt + 1))
    raise last


def get_json(url, **kw):
    return json.loads(http_get(url, **kw).decode("utf-8"))


def _f(v):
    try:
        x = float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return x if x == x else None


# ── Yahoo Finance ──
def yahoo_chart(symbol, *, interval, start=None, rng=None, adjusted=True):
    q = {"interval": interval, "events": "div,split"}
    if rng:
        q["range"] = rng
    else:
        q["period1"] = int(dt.datetime.fromisoformat(start).replace(tzinfo=dt.timezone.utc).timestamp())
        q["period2"] = int(time.time()) + 86400
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?{urllib.parse.urlencode(q)}"
    d = get_json(url)
    res = (d.get("chart") or {}).get("result")
    if not res:
        raise RuntimeError(f"Yahoo 無資料：{symbol} {(d.get('chart') or {}).get('error')}")
    r = res[0]
    ts = r.get("timestamp") or []
    close = r["indicators"]["quote"][0].get("close") or []
    adj = (r["indicators"].get("adjclose") or [{}])[0].get("adjclose") if adjusted else None
    off = r["meta"].get("gmtoffset") or 0
    out = []
    for i, t in enumerate(ts):
        v = adj[i] if adj and i < len(adj) and adj[i] is not None else (close[i] if i < len(close) else None)
        if v is None:
            continue
        out.append((dt.datetime.fromtimestamp(t + off, dt.timezone.utc).date(), float(v)))
    return out, r["meta"]


def yahoo_monthly(symbol, start, adjusted=True):
    rows, _ = yahoo_chart(symbol, interval="1mo", start=start, adjusted=adjusted)
    out = {}
    for day, v in rows:
        out[f"{day.year:04d}-{day.month:02d}"] = v  # 同月多列時保留最後一列
    return out


def yahoo_daily(symbol, rng="6mo"):
    rows, _meta = yahoo_chart(symbol, interval="1d", rng=rng, adjusted=False)
    return sorted({day.isoformat(): v for day, v in rows}.items())


# ── 台灣中央銀行統計資料庫 ──
_CBC_CACHE = {}


def cbc_table(filename):
    if filename not in _CBC_CACHE:
        d = get_json(f"https://cpx.cbc.gov.tw/API/DataAPI/Get?FileName={filename}")
        struct = d["data"]["structure"]
        dims = [[x["data"].strip() for x in struct[k]] for k in sorted(struct, key=lambda s: int(s[5:]))]
        cols = [" / ".join(p) for p in itertools.product(*dims)]
        out = {c: {} for c in cols}
        for row in d["data"]["dataSets"]:
            m = re.fullmatch(r"(\d{4})M(\d{2})", str(row[0]).strip())
            if not m:
                continue
            key = f"{m.group(1)}-{m.group(2)}"
            for c, v in zip(cols, row[1:]):
                x = _f(v)
                if x is not None:
                    out[c][key] = x
        _CBC_CACHE[filename] = (out, d["meta"])
    return _CBC_CACHE[filename]


def cbc_series(filename, column_prefix):
    table, _meta = cbc_table(filename)
    for col, vals in table.items():
        if col.startswith(column_prefix):
            return vals
    raise KeyError(f"央行 {filename} 找不到欄位「{column_prefix}」，現有：{list(table)[:8]}")


# ── 世界銀行 API ──
def worldbank(indicator, countries, start=1995):
    url = (f"https://api.worldbank.org/v2/country/{';'.join(countries)}/indicator/{indicator}"
           f"?format=json&date={start}:{dt.date.today().year}&per_page=5000")
    d = get_json(url)
    out = {}
    for x in (d[1] if len(d) > 1 and d[1] else []):
        if x.get("value") is None:
            continue
        code = x.get("countryiso3code") or x["country"]["id"]
        out.setdefault(code, {})[x["date"]] = float(x["value"])
    return out


# ── 世界銀行 Pink Sheet（xlsx，用 zipfile 解析）──
PINK_PAGE = "https://www.worldbank.org/en/research/commodity-markets"
PINK_FALLBACK = ("https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/"
                 "related/CMO-Historical-Data-Monthly.xlsx")
_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def pink_sheet_workbook():
    url = PINK_FALLBACK
    try:
        page = http_get(PINK_PAGE, timeout=30, retries=1).decode("utf-8", "ignore")
        m = re.search(r"https://[^\"']*CMO-Historical-Data-Monthly\.xlsx", page)
        if m:
            url = m.group(0)
    except Exception:  # noqa: BLE001 - 找不到新連結就用已知連結
        pass
    return http_get(url, timeout=120), url


def xlsx_sheet_rows(blob, sheet_name):
    z = zipfile.ZipFile(io.BytesIO(blob))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rid = next(s.get(_REL) for s in wb.find("m:sheets", _NS) if s.get("name") == sheet_name)
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    target = next(r.get("Target") for r in rels if r.get("Id") == rid).lstrip("/")
    if not target.startswith("xl/"):
        target = "xl/" + target
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")):
            shared.append("".join(t.text or "" for t in si.iter(f"{{{_NS['m']}}}t")))
    rows = []
    for r in ET.fromstring(z.read(target)).find("m:sheetData", _NS):
        cells = {}
        for c in r:
            col = re.sub(r"\d", "", c.get("r"))
            v = c.find("m:v", _NS)
            if v is None:
                is_ = c.find("m:is", _NS)
                val = "".join(t.text or "" for t in is_.iter(f"{{{_NS['m']}}}t")) if is_ is not None else None
            else:
                val = shared[int(v.text)] if c.get("t") == "s" else v.text
            cells[col] = val
        rows.append(cells)
    return rows


def pink_sheet_columns(blob, sheet_name):
    """回傳 {欄位標題: {"YYYY-MM": value}}；標題取資料列之前最靠近的文字列（略過單位列）。"""
    rows = xlsx_sheet_rows(blob, sheet_name)
    first = next(i for i, r in enumerate(rows) if re.fullmatch(r"\d{4}M\d{2}", str(r.get("A") or "").strip()))
    headers = {}
    for r in rows[max(0, first - 4):first]:
        for col, val in r.items():
            s = str(val or "").strip()
            if col == "A" or not s or s.startswith(("(", "[")):
                continue
            headers.setdefault(col, []).append(s)
    out = {}
    for col, parts in headers.items():
        vals = {}
        for r in rows[first:]:
            m = re.fullmatch(r"(\d{4})M(\d{2})", str(r.get("A") or "").strip())
            x = _f(r.get(col)) if m else None
            if x is not None:
                vals[f"{m.group(1)}-{m.group(2)}"] = x
        if vals:
            out[parts[-1]] = vals
    return out


# ── 日本財務省 JGB ──
MOF_ALL = "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/historical/jgbcme_all.csv"
MOF_CUR = "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/jgbcme.csv"


def mof_jgb_daily(tenor="10Y"):
    out = {}
    for url in (MOF_ALL, MOF_CUR):
        try:
            text = http_get(url, timeout=120).decode("latin-1")
        except Exception:
            if url == MOF_ALL:
                raise
            continue
        header = None
        for line in text.splitlines():
            cells = [c.strip() for c in line.split(",")]
            if cells and cells[0] == "Date":
                header = cells
                continue
            if not header or tenor not in header or not re.fullmatch(r"\d{4}/\d{1,2}/\d{1,2}", cells[0]):
                continue
            idx = header.index(tenor)
            x = _f(cells[idx]) if idx < len(cells) else None
            if x is not None:
                y, m, d = map(int, cells[0].split("/"))
                out[dt.date(y, m, d).isoformat()] = x
    return sorted(out.items())


def mof_jgb_monthly(tenor="10Y"):
    return {day[:7]: v for day, v in mof_jgb_daily(tenor)}


# ── 美國財政部 TIC：主要外國持有美債 ──
TIC_HIST = "https://ticdata.treasury.gov/resource-center/data-chart-center/tic/Documents/mfhhis01.txt"
TIC_CUR = "https://ticdata.treasury.gov/resource-center/data-chart-center/tic/Documents/slt_table5.txt"
_MON = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def _tic_name(raw):
    s = raw.strip().strip('"').lower()
    s = re.sub(r"\s*\d+/\s*$", "", s)
    return re.sub(r"\s+", " ", s)


def tic_holders(wanted_keys):
    out = {key: {} for key in wanted_keys}

    def put(name, keys, vals):
        n = _tic_name(name)
        for key in wanted_keys:
            if n == key or n.startswith(key + ","):
                for k, v in zip(keys, vals):
                    x = _f(v)
                    if k and x is not None:
                        out[key][k] = x

    months = keys = None
    for line in http_get(TIC_HIST, timeout=60).decode("latin-1").splitlines():
        toks = [c.strip() for c in line.split("\t")]
        if sum(1 for t in toks if t in _MON) >= 6:
            months = [_MON.get(t) for t in toks]
            keys = None
            continue
        if toks and toks[0] == "Country" and months:
            keys = [f"{int(yr):04d}-{mo:02d}" if mo and re.fullmatch(r"\d{4}", yr) else None
                    for mo, yr in zip(months, toks)]
            continue
        if keys and toks and toks[0] and not toks[0].startswith("-"):
            put(toks[0], keys[1:], toks[1:])

    keys = None
    for line in http_get(TIC_CUR, timeout=60).decode("latin-1").splitlines():
        toks = [c.strip() for c in line.split("\t")]
        if toks and toks[0] == "Country":
            keys = [t if re.fullmatch(r"\d{4}-\d{2}", t) else None for t in toks[1:]]
            continue
        if keys and toks and toks[0]:
            put(toks[0], keys, toks[1:])
    return out


# ── 公司現金流 ──
OCF_TAGS = ["NetCashProvidedByUsedInOperatingActivities",
            "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"]
CAPEX_TAGS = ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets",
              "PaymentsForCapitalImprovements"]


def sec_cashflow(cik):
    d = get_json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json",
                 headers={"User-Agent": SEC_UA}, timeout=120)
    gaap = d.get("facts", {}).get("us-gaap", {})

    def annual(tags):
        by_end = {}
        for rank, tag in enumerate(tags):
            for x in gaap.get(tag, {}).get("units", {}).get("USD", []):
                if not x.get("start") or not str(x.get("form", "")).startswith(("10-K", "20-F")):
                    continue
                days = (dt.date.fromisoformat(x["end"]) - dt.date.fromisoformat(x["start"])).days
                if not 350 <= days <= 380:
                    continue
                prev = by_end.get(x["end"])
                # 優先序：排前面的標籤 > 同標籤較新的申報（重編後數字）
                if prev is None or rank < prev["_rank"] or (rank == prev["_rank"] and x["filed"] > prev["filed"]):
                    by_end[x["end"]] = dict(x, _rank=rank)
        return {k: v["val"] for k, v in by_end.items()}

    ocf, capex = annual(OCF_TAGS), annual(CAPEX_TAGS)
    years = [dict(end=end, ocf=ocf[end], capex=capex.get(end),
                  fcf=(ocf[end] - capex[end]) if end in capex else None) for end in sorted(ocf)]
    return d.get("entityName"), years


def finmind_cashflow(stock_id, start="2005-01-01"):
    d = get_json("https://api.finmindtrade.com/api/v4/data?" + urllib.parse.urlencode(
        dict(dataset="TaiwanStockCashFlowsStatement", data_id=stock_id, start_date=start)), timeout=90)
    if d.get("status") != 200:
        raise RuntimeError(f"FinMind {stock_id}: {d.get('msg')}")
    ocf, capex = {}, {}
    for x in d.get("data", []):
        if not x["date"].endswith("-12-31"):
            continue  # 台灣現金流量表為年初累計，12/31 即全年
        if x["type"] in ("CashFlowsFromOperatingActivities", "NetCashInflowFromOperatingActivities"):
            ocf.setdefault(x["date"], x["value"])
        elif x["type"] == "PropertyAndPlantAndEquipment":
            capex[x["date"]] = -x["value"]  # FinMind 以負數記支出
    return [dict(end=end, ocf=ocf[end], capex=capex.get(end),
                 fcf=(ocf[end] - capex[end]) if end in capex else None) for end in sorted(ocf)]


# ── 鉅亨網 ──
CNYES_HEADERS = {"Referer": "https://www.cnyes.com/", "Origin": "https://www.cnyes.com"}


def cnyes_news(category, start_ts, end_ts, max_pages=5):
    items, page = [], 1
    while page <= max_pages:
        url = (f"https://api.cnyes.com/media/api/v1/newslist/category/{category}?"
               + urllib.parse.urlencode(dict(limit=100, startAt=start_ts, endAt=end_ts, page=page)))
        block = get_json(url, headers=CNYES_HEADERS, timeout=30).get("items") or {}
        items.extend(block.get("data") or [])
        if page >= int(block.get("last_page") or 1):
            break
        page += 1
        time.sleep(0.3)
    return items


def cnyes_history(symbol, days=150):
    now = int(time.time()) + 86400
    url = ("https://ws.api.cnyes.com/ws/api/v1/charting/history?"
           + urllib.parse.urlencode({"resolution": "D", "symbol": symbol, "from": now, "to": now - days * 86400}))
    data = get_json(url, headers=CNYES_HEADERS, timeout=30).get("data") or {}
    rows = {}
    for t, c in zip(data.get("t") or [], data.get("c") or []):
        if c is not None:
            rows[dt.datetime.fromtimestamp(t, dt.timezone.utc).date().isoformat()] = float(c)
    return sorted(rows.items())


def strip_html(s, limit=160):
    text = html.unescape(html.unescape(s or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit] + ("…" if len(text) > limit else "")
