#!/usr/bin/env bash
# 每日更新：歷史快取超過 7 天才重抓 → 重算分析 → 匯入今日鉅亨網 → 產出 dashboard.html
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p logs
exec >> "logs/daily_$(date +%Y%m).log" 2>&1
exec 9> logs/.run_daily.lock
if ! flock -n 9; then
  echo "=== $(date '+%F %T') 上一次更新還在跑，這次略過 ==="
  exit 0
fi
echo "=== $(date '+%F %T') ==="
python3 gfd.py all

# 有 git repo 且有 origin 就順手更新 GitHub Pages 公開示範版（失敗不影響本機更新）
if [ -d .git ] && [ -f docs/index.html ]; then
  ./deploy_pages.sh || echo "部署 gh-pages 失敗（檢查 gh auth status）"
fi
echo "=== done $(date '+%F %T') ==="
