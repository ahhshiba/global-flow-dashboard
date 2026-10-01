"""把 analysis.json 與最近幾天的每日資料內嵌成單一 HTML。

產出兩份：
  dashboard.html           完整 HTML 文件，直接用瀏覽器開
  dashboard.artifact.html  只有頁面內容（無 doctype/head/body），發佈成 Artifact 用
公開版（--public）另外產出 docs/index.html 與 docs/data/*.json。

載入速度（2026-10-02）：開頁只需要總覽與各市場分頁的資料，事件衝擊、訊號劇本、完整日線、歷史每日
占了頁面資料的八成以上。這幾塊拆出來（LAZY_KEYS），用到才拿：
  公開版   放成 docs/data/<鍵>.json，網址帶內容雜湊（?v=），頁面用到才下載
  本機版   仍是單一檔案（file:// 不能 fetch），但放在另外的 <script type="application/json">，用到才解析
頁面內嵌的日線只留總覽 KPI 用得到的尾巴（DETAIL_TAIL），完整日線在單一標的檢視打開時才載入。
"""
import datetime as dt
import hashlib
import json
import pathlib

from . import config as C
from . import faq as FQ
from . import glossary as GL

ROOT = pathlib.Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
OUT = ROOT / "dashboard.html"
OUT_ARTIFACT = ROOT / "dashboard.artifact.html"
OUT_PUBLIC = ROOT / "docs" / "index.html"
OUT_PUBLIC_DATA = ROOT / "docs" / "data"
LAZY_KEYS = ("cascade", "playbook", "detail", "daily_latest", "daily")
# 總覽 KPI 用到的日線尾巴：走勢小圖取最後 120 個交易日；「12 月」漲跌往回找一年前的週收盤（60 週 > 一年＋落差）
DETAIL_TAIL = {"d": 130, "w": 60}
TPE = dt.timezone(dt.timedelta(hours=8))


def _write(path, text):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _json(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def _detail_tail(items):
    """每個標的只留 DETAIL_TAIL 的日／週線尾巴與中繼資料；月／年線與更早的日線等打開單一標的檢視時再載入。"""
    out = {}
    for sid, D in items.items():
        t = {k: v for k, v in D.items() if k not in ("d", "w", "m", "y")}
        for r, n in DETAIL_TAIL.items():
            if D.get(r):
                t[r] = [D[r][0][-n:], D[r][1][-n:]]
        out[sid] = t
    return out


def run(log=print, public=False):
    ana_path = ROOT / "data" / "analysis.json"
    if not ana_path.exists():
        raise SystemExit("找不到 data/analysis.json，請先執行：python3 gfd.py analyze")
    analysis = json.loads(ana_path.read_text(encoding="utf-8"))
    day_files = sorted((ROOT / "data" / "daily").glob("????-??-??.json"))[-C.DAILY_KEEP_IN_HTML:]
    daily = [json.loads(p.read_text(encoding="utf-8")) for p in reversed(day_files)]
    if public:
        # 公開示範版：新聞只留標題與連結，不轉載鉅亨網的摘要內文
        daily = [dict(d, news=[{k: v for k, v in n.items() if k != "summary"} for n in d["news"]]) for d in daily]
    detail_path = ROOT / "data" / "raw" / "detail.json"
    detail = json.loads(detail_path.read_text(encoding="utf-8")) if detail_path.exists() else {}
    detail_items = detail.get("items", {})
    # 鉅亨每日分頁先只拿最新一天（daily_latest），選了別的日期才拿全部（daily）
    lazy = dict(cascade=analysis.get("cascade"), playbook=analysis.get("playbook"), detail=detail_items,
                daily_latest=daily[0] if daily else None, daily=daily)
    lazy_text = {k: _json(v) for k, v in lazy.items()}
    if public:
        # 公開版：大塊資料各自一個檔，網址帶內容雜湊，內容沒變就沿用瀏覽器快取
        OUT_PUBLIC_DATA.mkdir(parents=True, exist_ok=True)
        lazy_src = {}
        for k, text in lazy_text.items():
            _write(OUT_PUBLIC_DATA / f"{k}.json", text)
            lazy_src[k] = f"data/{k}.json?v={hashlib.sha256(text.encode('utf-8')).hexdigest()[:10]}"
        for stale in OUT_PUBLIC_DATA.glob("*.json"):  # docs/data 是產物目錄：不再產出的舊檔不留著被部署出去
            if stale.stem not in LAZY_KEYS:
                stale.unlink()
        lazy_tags = ""
    else:
        lazy_src = {k: f"#gfd-lazy-{k}" for k in LAZY_KEYS}
        # 本機版：同一個檔案裡另外的 JSON 區塊，開頁時瀏覽器只當文字收下，用到才解析
        lazy_tags = "".join('<script id="gfd-lazy-%s" type="application/json">%s</script>\n' % (k, lazy_text[k].replace("</", "<\\/"))
                            for k in LAZY_KEYS)
    core = {k: v for k, v in analysis.items() if k not in ("cascade", "playbook")}
    # 報頭、報價跑馬燈、KPI 只用最新一天的收盤（不含走勢小圖）與重點則數；新聞列表在鉅亨每日分頁載入完整資料後才畫
    latest = dict(date=daily[0]["date"], quotes=[{k: v for k, v in q.items() if k != "spark"} for q in daily[0]["quotes"]],
                  highlights=sum(1 for n in daily[0]["news"] if n.get("highlight"))) if daily else None
    day_index = [dict(date=d["date"], highlights=sum(1 for n in d["news"] if n.get("highlight"))) for d in daily]
    payload = dict(built_at=dt.datetime.now(TPE).isoformat(timespec="seconds"), analysis=core, latest=latest, day_index=day_index,
                   sections=[dict(id=a, label=b) for a, b in C.SECTIONS],
                   detail=_detail_tail(detail_items), detail_fetched_at=detail.get("fetched_at"), public=public,
                   glossary=GL.payload(), faq=FQ.payload(), lazy=lazy_src)
    data = _json(payload).replace("</", "<\\/")
    js = "\n;\n".join(p.read_text(encoding="utf-8") for p in sorted((WEB / "js").glob("*.js")))

    body = (WEB / "template.html").read_text(encoding="utf-8")
    for marker, content in (("/*__CSS__*/", (WEB / "app.css").read_text(encoding="utf-8")),
                            ("/*__JS__*/", js), ("/*__DATA__*/", data), ("<!--__LAZY__-->\n", lazy_tags)):
        if body.count(marker) != 1:
            raise SystemExit(f"template.html 的 {marker} 標記必須剛好出現一次")
        body = body.replace(marker, content, 1)

    full = ('<!doctype html>\n<html lang="zh-Hant">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n</head>\n<body>\n'
            + body + "\n</body>\n</html>\n")
    if public:
        from . import gate
        OUT_PUBLIC.parent.mkdir(parents=True, exist_ok=True)
        _write(OUT_PUBLIC, gate.wrap(full, gate.password()))
        extra = sum((OUT_PUBLIC_DATA / f"{k}.json").stat().st_size for k in LAZY_KEYS) / 1024
        log(f"[build] 公開版 {OUT_PUBLIC}（{OUT_PUBLIC.stat().st_size / 1024:.0f} KB，前面有登入頁；新聞不含摘要；"
            f"用到才載入的 docs/data/ 另 {extra:.0f} KB）")
        return OUT_PUBLIC
    _write(OUT, full)
    _write(OUT_ARTIFACT, body)
    log(f"[build] {OUT}（{OUT.stat().st_size / 1024:.0f} KB，內嵌 {len(daily)} 天每日資料）")
    return OUT
