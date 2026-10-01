"""公開版的密碼門（2026-10-01 課堂：網站要有一層簡單的防護）。

GitHub Pages 只能放靜態檔，所以「登入」做不到伺服器端驗證。這裡把整個頁面用密碼加密後才發佈：
瀏覽器輸入密碼 → PBKDF2 導出金鑰 → AES-256-GCM 解密 → gzip 解壓 → 顯示頁面。新部署的 gh-pages 上只有密文，
搜尋引擎也看不到內容。限制要講清楚：
- 密文是公開的，可以離線一直猜密碼；短密碼（例如 123）幾秒就猜得到，30 萬次 PBKDF2 只是讓每次猜慢一點。
  這道門擋的是路人與搜尋引擎，不是有心人。
- 解開後密碼存在該分頁的 sessionStorage（重新整理不用再輸入），關掉分頁就清掉。
- 2026-10-01 以前部署過的明文版本，GitHub 可能仍以 commit 雜湊保留一段時間，也可能被快取或轉存。

密碼從環境變數 GFD_PUBLIC_PASSWORD 或 data/public_password.txt 讀（data/ 不進版控）。沒有密碼時 build --public
預設拒絕產出（不會悄悄發佈明文）；真的要發佈明文版，設 GFD_ALLOW_PLAINTEXT=1。
需要 `cryptography`（Ubuntu 的 python3-cryptography 套件已內建）。
"""
import base64
import gzip
import hashlib
import json
import os
import pathlib
import secrets

ROOT = pathlib.Path(__file__).resolve().parent.parent
PASSWORD_FILE = ROOT / "data" / "public_password.txt"
ITERATIONS = 300_000


def password():
    pw = os.environ.get("GFD_PUBLIC_PASSWORD")
    if pw:
        return pw.strip()
    if PASSWORD_FILE.exists():
        return PASSWORD_FILE.read_text(encoding="utf-8").strip() or None
    return None


def allow_plaintext():
    return os.environ.get("GFD_ALLOW_PLAINTEXT") == "1"


def encrypt(html, pw):
    """整頁 HTML → gzip → AES-GCM 密文（base64）＋鹽、IV。先壓縮：密文無法再壓縮，壓縮後頁面約小四倍。"""
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError as e:  # 沒裝就明講，不要讓排程只看到 traceback
        raise SystemExit("公開版加密需要 cryptography 套件（sudo apt install python3-cryptography）") from e
    salt, iv = secrets.token_bytes(16), secrets.token_bytes(12)
    key = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt, ITERATIONS, dklen=32)
    ct = AESGCM(key).encrypt(iv, gzip.compress(html.encode("utf-8"), compresslevel=9, mtime=0), None)
    return dict(salt=base64.b64encode(salt).decode(), iv=base64.b64encode(iv).decode(),
                data=base64.b64encode(ct).decode(), iter=ITERATIONS, z="gzip")


WRAPPER = """<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>資金流向觀測台</title>
<style>
  :root { --bg: #f5f6fa; --fg: #1d2130; --muted: #7d8497; --accent: #2b3f8f; --line: #c5cad6; --err: #b3261e; }
  @media (prefers-color-scheme: dark) { :root { --bg: #0d0f16; --fg: #e9ebf2; --muted: #7e8497; --accent: #93a6f2; --line: #383d51; --err: #ff8a80; } }
  body { margin: 0; min-height: 100vh; display: grid; place-items: center; background: var(--bg); color: var(--fg);
    font: 15px/1.6 -apple-system, "Noto Sans TC", "PingFang TC", "Microsoft JhengHei", sans-serif; padding: 16px; box-sizing: border-box; }
  form { width: min(360px, 100%); display: flex; flex-direction: column; gap: 10px; }
  h1 { font-size: 20px; margin: 0; } p { margin: 0; color: var(--muted); font-size: 13px; }
  input { font: inherit; padding: 9px 12px; border: 1px solid var(--line); border-radius: 6px; background: transparent; color: var(--fg); }
  button { font: inherit; padding: 9px 12px; border: 0; border-radius: 6px; background: var(--accent); color: #fff; cursor: pointer; }
  button[disabled] { opacity: .6; cursor: wait; }
  .err { color: var(--err); font-size: 13px; min-height: 1.4em; }
</style>
</head>
<body>
<form id="f" autocomplete="off">
  <h1>資金流向觀測台</h1>
  <input id="pw" type="password" placeholder="密碼" autofocus required aria-label="密碼">
  <button id="go" type="submit">進入</button>
  <div class="err" id="err" role="alert"></div>
</form>
<script id="payload" type="application/json">__PAYLOAD__</script>
<script>
(function () {
  const P = JSON.parse(document.getElementById("payload").textContent);
  const b64 = (s) => Uint8Array.from(atob(s), (c) => c.charCodeAt(0));
  const form = document.getElementById("f"), pw = document.getElementById("pw"), err = document.getElementById("err"), go = document.getElementById("go");
  async function open(password) {
    if (!window.crypto || !crypto.subtle) throw new Error("no-subtle");   // 非 HTTPS 或太舊的瀏覽器沒有 WebCrypto
    const enc = new TextEncoder();
    const base = await crypto.subtle.importKey("raw", enc.encode(password), "PBKDF2", false, ["deriveKey"]);
    const key = await crypto.subtle.deriveKey({ name: "PBKDF2", salt: b64(P.salt), iterations: P.iter, hash: "SHA-256" },
      base, { name: "AES-GCM", length: 256 }, false, ["decrypt"]);
    const plain = await crypto.subtle.decrypt({ name: "AES-GCM", iv: b64(P.iv) }, key, b64(P.data));
    let html;
    if (P.z === "gzip") {
      if (typeof DecompressionStream !== "function") throw new Error("old-browser");
      const stream = new Blob([plain]).stream().pipeThrough(new DecompressionStream("gzip"));
      html = await new Response(stream).text();
    } else {
      html = new TextDecoder().decode(plain);
    }
    try { sessionStorage.setItem("gfd:pw", password); } catch (e) { /* 無痕視窗 */ }
    document.open(); document.write(html); document.close();
  }
  form.addEventListener("submit", async (e) => {
    e.preventDefault(); err.textContent = ""; go.disabled = true;
    try { await open(pw.value); } catch (ex) {
      err.textContent = ex && ex.message === "old-browser" ? "這個瀏覽器太舊，無法解壓縮頁面；請更新瀏覽器。"
        : ex && ex.message === "no-subtle" ? "這個瀏覽器不能解密（需要 HTTPS 網址與較新的瀏覽器）。" : "密碼不對。";
      go.disabled = false; pw.select();
    }
  });
  // 同一個分頁重新整理不用再輸入
  let saved = null; try { saved = sessionStorage.getItem("gfd:pw"); } catch (e) { /* 略過 */ }
  if (saved) open(saved).catch(() => { try { sessionStorage.removeItem("gfd:pw"); } catch (e) { /* 略過 */ } });
})();
</script>
</body>
</html>
"""


def wrap(html, pw):
    payload = json.dumps(encrypt(html, pw), separators=(",", ":")).replace("</", "<\\/")
    return WRAPPER.replace("__PAYLOAD__", payload, 1)
