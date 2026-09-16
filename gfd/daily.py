"""每日觀察：從鉅亨網匯入新聞與報價，自動標註重點 → data/daily/YYYY-MM-DD.json。

鉅亨網公開 API 沒有期貨／VIX／公債代碼，這些列改用 Yahoo Finance 與日本財務省，並逐列標註來源。
"""
import datetime as dt
import json
import pathlib
import statistics
import time

from . import config as C
from . import sources as S

ROOT = pathlib.Path(__file__).resolve().parent.parent
DAILY = ROOT / "data" / "daily"
TPE = dt.timezone(dt.timedelta(hours=8))
SOURCE_LABEL = {"cnyes": "鉅亨網", "yahoo": "Yahoo", "mof": "日本財務省"}
WATCH_SYMBOLS = {cn: name for cfg in C.LEADERS.values() for _t, name, cn, _k in cfg["items"]}


def day_bounds(day):
    start = dt.datetime(day.year, day.month, day.day, tzinfo=TPE)
    return int(start.timestamp()), int((start + dt.timedelta(days=1)).timestamp()) - 1


def _rows(src, symbol, cache):
    key = (src, symbol)
    if key not in cache:
        if src == "cnyes":
            cache[key] = S.cnyes_history(symbol, 150)
        elif src == "yahoo":
            cache[key] = S.yahoo_daily(symbol, "6mo")
        elif src == "mof":
            cache[key] = S.mof_jgb_daily("10Y")[-160:]
        else:
            raise ValueError(src)
    return cache[key]


def quote_entry(rows, day, unit):
    rows = [(d, v) for d, v in rows if d <= day.isoformat()]
    if len(rows) < 2:
        return None
    (d_last, v_last), (_d_prev, v_prev) = rows[-1], rows[-2]

    def delta(a, b):
        return (b - a) * 100 if unit == "bp" else (b / a - 1) * 100

    chg = delta(v_prev, v_last)
    hist = [delta(rows[i - 1][1], rows[i][1]) for i in range(max(1, len(rows) - 61), len(rows) - 1)]
    sd = statistics.pstdev(hist) if len(hist) >= 20 else 0
    z = chg / sd if sd > 0 else None
    return dict(asof=d_last, close=round(v_last, 4), chg=round(chg, 3), z=round(z, 2) if z is not None else None,
                flag=bool(z is not None and abs(z) >= C.MOVER_Z),
                stale=(day - dt.date.fromisoformat(d_last)).days > 4,
                spark=[round(v, 4) for _, v in rows[-30:]])


def score_news(item, cats, flagged_names):
    title = item.get("title") or ""
    tl = title.lower()
    kws = [k for k in (item.get("keyword") or []) if isinstance(k, str)]
    sections, reasons, hits_all = {}, [], []
    for sec, words in C.SECTION_KEYWORDS.items():
        t_hits = [w for w in words if w.lower() in tl]
        k_hits = [w for w in words if w not in t_hits and any(w.lower() in k.lower() for k in kws)]
        s = 2 * len(t_hits) + len(k_hits)
        if s:
            sections[sec] = s
            hits_all += t_hits
    score = sum(min(v, 4) for v in sections.values())
    if hits_all:
        reasons.append("命中：" + "、".join(list(dict.fromkeys(hits_all))[:4]))
    if item.get("isCategoryHeadline") or "頭條" in cats:
        score += 2
        reasons.append("鉅亨頭條")
    if "TOP" in kws:
        score += 1
    stocks = [m.get("name") for m in (item.get("market") or []) if isinstance(m, dict)]
    watch = [WATCH_SYMBOLS[m["symbol"]] for m in (item.get("market") or [])
             if isinstance(m, dict) and m.get("symbol") in WATCH_SYMBOLS]
    if watch:
        score += min(2, len(set(watch)))
        sections["equity"] = sections.get("equity", 0) + 1
        reasons.append("龍頭股：" + "、".join(list(dict.fromkeys(watch))[:3]))
    movers = [n for n in flagged_names if n and n in title]
    if movers:
        score += 2
        reasons.append("對應異常波動：" + "、".join(movers[:2]))
    return sections, score, reasons, [s for s in stocks if s][:6]


def run(day=None, log=print):
    day = day or dt.datetime.now(TPE).date()
    errors, cache = [], {}

    quotes = []
    for sec, group, src, symbol, name, unit in C.DAILY_QUOTES:
        try:
            e = quote_entry(_rows(src, symbol, cache), day, unit)
            if e is None:
                raise RuntimeError("資料不足")
            quotes.append(dict(section=sec, group=group, source=SOURCE_LABEL[src], symbol=symbol, name=name,
                               unit=unit, **e))
        except Exception as ex:  # noqa: BLE001 - 單一報價失敗不影響其他
            errors.append(f"報價 {name}（{symbol}）：{type(ex).__name__}: {ex}"[:200])
        time.sleep(0.15 if src == "cnyes" else 0.3)
    log(f"[daily] {day} 報價 {len(quotes)}/{len(C.DAILY_QUOTES)}")

    start, end = day_bounds(day)
    raw = {}
    for cat, label in C.CNYES_NEWS_CATEGORIES:
        try:
            for it in S.cnyes_news(cat, start, end):
                if not (start <= int(it.get("publishAt") or 0) <= end):
                    continue
                rec = raw.setdefault(it["newsId"], dict(item=it, cats=[]))
                if label not in rec["cats"]:
                    rec["cats"].append(label)
        except Exception as ex:  # noqa: BLE001
            errors.append(f"新聞分類 {label}：{type(ex).__name__}: {ex}"[:200])
        time.sleep(0.3)

    flagged = [q["name"].replace(" B", "") for q in quotes if q["flag"]]
    news = []
    for nid, rec in raw.items():
        it = rec["item"]
        sections, score, reasons, stocks = score_news(it, rec["cats"], flagged)
        ts = int(it.get("publishAt") or 0)
        news.append(dict(id=nid, title=it.get("title"), summary=S.strip_html(it.get("summary") or it.get("content"), 140),
                         url=f"https://news.cnyes.com/news/id/{nid}", ts=ts,
                         time=dt.datetime.fromtimestamp(ts, TPE).strftime("%H:%M"), cats=rec["cats"],
                         keywords=[k for k in (it.get("keyword") or []) if isinstance(k, str) and k != "TOP"][:6],
                         stocks=stocks, sections=sections, score=score,
                         highlight=score >= C.HIGHLIGHT_SCORE, reasons=reasons))
    news.sort(key=lambda n: (n["highlight"], n["score"], n["ts"]), reverse=True)
    log(f"[daily] {day} 新聞 {len(news)} 則、重點 {sum(n['highlight'] for n in news)} 則")

    summary = {}
    for sec, label in C.SECTIONS:
        sec_news = [n for n in news if sec in n["sections"]]
        summary[sec] = dict(label=label, news=len(sec_news), highlights=sum(n["highlight"] for n in sec_news),
                            movers=[q["name"] for q in quotes if q["section"] == sec and q["flag"]],
                            top=[n["id"] for n in sec_news if n["highlight"]][:3])

    out = dict(date=day.isoformat(), generated_at=dt.datetime.now(TPE).isoformat(timespec="seconds"),
               quotes=quotes, news=news, sections=summary, errors=errors,
               rules=dict(mover_z=C.MOVER_Z, highlight_score=C.HIGHLIGHT_SCORE))
    DAILY.mkdir(parents=True, exist_ok=True)
    path = DAILY / f"{day.isoformat()}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    if errors:
        log(f"[daily] {len(errors)} 個錯誤，第一個：{errors[0]}")
    return out


def backfill(days, log=print):
    today = dt.datetime.now(TPE).date()
    for i in range(days - 1, -1, -1):
        run(today - dt.timedelta(days=i), log=log)
