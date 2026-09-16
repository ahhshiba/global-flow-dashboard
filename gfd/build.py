"""把 analysis.json 與最近幾天的每日資料內嵌成單一 HTML。

產出兩份：
  dashboard.html           完整 HTML 文件，直接用瀏覽器開
  dashboard.artifact.html  只有頁面內容（無 doctype/head/body），發佈成 Artifact 用
"""
import datetime as dt
import json
import pathlib

from . import config as C

ROOT = pathlib.Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
OUT = ROOT / "dashboard.html"
OUT_ARTIFACT = ROOT / "dashboard.artifact.html"
OUT_PUBLIC = ROOT / "docs" / "index.html"
TPE = dt.timezone(dt.timedelta(hours=8))


def _write(path, text):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


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
    payload = dict(built_at=dt.datetime.now(TPE).isoformat(timespec="seconds"), analysis=analysis, daily=daily,
                   sections=[dict(id=a, label=b) for a, b in C.SECTIONS],
                   detail=detail.get("items", {}), detail_fetched_at=detail.get("fetched_at"), public=public)
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    js = "\n;\n".join(p.read_text(encoding="utf-8") for p in sorted((WEB / "js").glob("*.js")))

    body = (WEB / "template.html").read_text(encoding="utf-8")
    for marker, content in (("/*__CSS__*/", (WEB / "app.css").read_text(encoding="utf-8")),
                            ("/*__JS__*/", js), ("/*__DATA__*/", data)):
        if body.count(marker) != 1:
            raise SystemExit(f"template.html 的 {marker} 標記必須剛好出現一次")
        body = body.replace(marker, content, 1)

    full = ('<!doctype html>\n<html lang="zh-Hant">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n</head>\n<body>\n'
            + body + "\n</body>\n</html>\n")
    if public:
        OUT_PUBLIC.parent.mkdir(parents=True, exist_ok=True)
        _write(OUT_PUBLIC, full)
        log(f"[build] 公開版 {OUT_PUBLIC}（{OUT_PUBLIC.stat().st_size / 1024:.0f} KB，新聞不含摘要）")
        return OUT_PUBLIC
    _write(OUT, full)
    _write(OUT_ARTIFACT, body)
    log(f"[build] {OUT}（{OUT.stat().st_size / 1024:.0f} KB，內嵌 {len(daily)} 天每日資料）")
    return OUT
