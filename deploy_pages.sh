#!/usr/bin/env bash
# 把 docs/index.html 與 docs/data/*.json 推到 gh-pages 分支（每次都是單一 commit，覆蓋舊的，repo 不會愈長愈大）。
# 需要 python3 gfd.py build --public 的產物與已設定的 origin。
# docs/data/ 是頁面用到才下載的大塊資料（事件衝擊、訊號劇本、完整日線、鉅亨每日），頁面裡的網址帶內容雜湊。
set -euo pipefail
cd "$(dirname "$0")"

[ -f docs/index.html ] || { echo "沒有 docs/index.html，先跑：python3 gfd.py build --public"; exit 1; }
git rev-parse --git-dir >/dev/null 2>&1 || { echo "這裡還不是 git repo"; exit 1; }
git remote get-url origin >/dev/null 2>&1 || { echo "沒有 origin remote"; exit 1; }

# 頁面引用的 data/*.json 必須都在、內容雜湊也對得上；否則推上去的頁面會載不到資料
while read -r ref; do
  f="docs/${ref%%\?v=*}"; want="${ref##*\?v=}"
  [ -f "$f" ] || { echo "頁面引用了 $f 但檔案不存在，先重跑：python3 gfd.py build --public"; exit 1; }
  [ "$(sha256sum "$f" | cut -c1-10)" = "$want" ] || { echo "$f 和頁面引用的版本不符，先重跑：python3 gfd.py build --public"; exit 1; }
done < <(grep -o 'data/[A-Za-z0-9_-]*\.json?v=[0-9a-f]*' docs/index.html | sort -u)

PAGE=$(git hash-object -w docs/index.html)
NOJEKYLL=$(printf '' | git hash-object -w --stdin)
ENTRIES=$(printf '100644 blob %s\tindex.html\n100644 blob %s\t.nojekyll' "$PAGE" "$NOJEKYLL")
DATA_FILES=(docs/data/*.json)
if [ -f "${DATA_FILES[0]}" ]; then
  DATA_TREE=$(for f in "${DATA_FILES[@]}"; do printf '100644 blob %s\t%s\n' "$(git hash-object -w "$f")" "$(basename "$f")"; done | git mktree)
  ENTRIES=$(printf '%s\n040000 tree %s\tdata' "$ENTRIES" "$DATA_TREE")
fi
TREE=$(printf '%s\n' "$ENTRIES" | git mktree)
COMMIT=$(git commit-tree "$TREE" -m "deploy: $(date '+%Y-%m-%d %H:%M') 資金流向觀測台公開示範版")
git push -q --force origin "$COMMIT":refs/heads/gh-pages
# 每次部署都在本機 .git 寫一份新的頁面與資料 blob，舊的部署 commit 推上去後就不再被任何分支引用；
# 清掉三天以上的無引用物件（git gc 預設要等兩週），避免 .git 每天長十幾 MB
git prune --expire=3.days.ago 2>/dev/null || true
echo "已部署 gh-pages（commit ${COMMIT:0:7}，頁面 $(du -h docs/index.html | cut -f1)，資料 $(du -ch docs/data/*.json 2>/dev/null | tail -1 | cut -f1)）"
