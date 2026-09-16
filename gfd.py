#!/usr/bin/env python3
"""資金流向觀測台 CLI。

  python3 gfd.py all              # 需要時更新歷史 → 分析 → 今日鉅亨 → 產出 dashboard.html
  python3 gfd.py history          # 重抓 30 年歷史資料並重算分析
  python3 gfd.py analyze          # 只重算分析（不連網）
  python3 gfd.py daily [--date YYYY-MM-DD | --backfill N]
  python3 gfd.py build            # 只重新產出 dashboard.html
"""
import argparse
import datetime as dt
import pathlib
import time

from gfd import analysis, build, daily, history

ROOT = pathlib.Path(__file__).resolve().parent
HISTORY_MAX_AGE_DAYS = 7


def history_is_stale():
    p = ROOT / "data" / "raw" / "series.json"
    return not p.exists() or time.time() - p.stat().st_mtime > HISTORY_MAX_AGE_DAYS * 86400


def main():
    p = argparse.ArgumentParser(description="資金流向觀測台")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("history", help="重抓 30 年歷史資料並重算分析")
    sub.add_parser("analyze", help="只重算分析")
    d = sub.add_parser("daily", help="匯入鉅亨網每日新聞與報價")
    d.add_argument("--date", help="指定日期 YYYY-MM-DD（台北時間）")
    d.add_argument("--backfill", type=int, help="補抓最近 N 天")
    b = sub.add_parser("build", help="產出 dashboard.html")
    b.add_argument("--public", action="store_true", help="另外產出 docs/index.html（公開示範版，新聞不含摘要）")
    a = sub.add_parser("all", help="完整流程")
    a.add_argument("--force-history", action="store_true", help="不論快取新舊都重抓歷史")
    args = p.parse_args()

    if args.cmd == "history":
        history.run()
        analysis.run()
    elif args.cmd == "analyze":
        analysis.run()
    elif args.cmd == "daily":
        if args.backfill:
            daily.backfill(args.backfill)
        else:
            daily.run(dt.date.fromisoformat(args.date) if args.date else None)
    elif args.cmd == "build":
        build.run(public=args.public)
    elif args.cmd == "all":
        if args.force_history or history_is_stale():
            history.run()
        else:
            history.fetch_detail()  # 日／週線每次都更新；月資料一週重抓一次就夠
        analysis.run()
        now = dt.datetime.now(daily.TPE)
        if now.hour < 12:
            # 早上那次：美股已收盤、前一天新聞已出齊，重匯前一天讓它完整
            daily.run(now.date() - dt.timedelta(days=1))
        daily.run(now.date())
        build.run()
        if (ROOT / "docs").exists():
            build.run(public=True)  # 有 docs/ 就順手更新公開示範版


if __name__ == "__main__":
    main()
