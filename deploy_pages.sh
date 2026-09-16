#!/usr/bin/env bash
# 把 docs/index.html 推到 gh-pages 分支（每次都是單一 commit，覆蓋舊的，repo 不會愈長愈大）。
# 需要 docs/index.html（python3 gfd.py build --public 產生）與已設定的 origin。
set -euo pipefail
cd "$(dirname "$0")"

[ -f docs/index.html ] || { echo "沒有 docs/index.html，先跑：python3 gfd.py build --public"; exit 1; }
git rev-parse --git-dir >/dev/null 2>&1 || { echo "這裡還不是 git repo"; exit 1; }
git remote get-url origin >/dev/null 2>&1 || { echo "沒有 origin remote"; exit 1; }

PAGE=$(git hash-object -w docs/index.html)
NOJEKYLL=$(printf '' | git hash-object -w --stdin)
TREE=$(printf '100644 blob %s\tindex.html\n100644 blob %s\t.nojekyll\n' "$PAGE" "$NOJEKYLL" | git mktree)
COMMIT=$(git commit-tree "$TREE" -m "deploy: $(date '+%Y-%m-%d %H:%M') 資金流向觀測台公開示範版")
git push -q --force origin "$COMMIT":refs/heads/gh-pages
echo "已部署 gh-pages（commit ${COMMIT:0:7}，$(du -h docs/index.html | cut -f1)）"
