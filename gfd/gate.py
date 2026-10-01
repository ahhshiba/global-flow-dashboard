"""公開版的密碼門（2026-10-01 課堂：網站要有一層簡單的防護）。

GitHub Pages 只能放靜態檔，所以「登入」做不到伺服器端驗證。這裡把整個頁面用密碼加密後才發佈：
瀏覽器輸入密碼 → PBKDF2 導出金鑰 → AES-256-GCM 解密 → 顯示頁面。GitHub 上只有密文，搜尋引擎也看不到內容。
限制要講清楚：密碼簡單（例如 123）就擋不住有心人試，這道門擋的是路人與搜尋引擎，不是攻擊者。

密碼從環境變數 GFD_PUBLIC_PASSWORD 或 data/public_password.txt 讀（data/ 不進版控）；沒有設定就不加密。
"""
import base64
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


def encrypt(html, pw):
    """整頁 HTML → 密文（base64）＋鹽、IV；用 cryptography 的 AES-GCM（瀏覽器端 WebCrypto 能解）。"""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    salt, iv = secrets.token_bytes(16), secrets.token_bytes(12)
    key = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt, ITERATIONS, dklen=32)
    ct = AESGCM(key).encrypt(iv, html.encode("utf-8"), None)
    return dict(salt=base64.b64encode(salt).decode(), iv=base64.b64encode(iv).decode(),
                data=base64.b64encode(ct).decode(), iter=ITERATIONS)


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
  <p>這個網站需要密碼。內容在你的瀏覽器裡解密，伺服器上只有密文。</p>
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
    const enc = new TextEncoder();
    const base = await crypto.subtle.importKey("raw", enc.encode(password), "PBKDF2", false, ["deriveKey"]);
    const key = await crypto.subtle.deriveKey({ name: "PBKDF2", salt: b64(P.salt), iterations: P.iter, hash: "SHA-256" },
      base, { name: "AES-GCM", length: 256 }, false, ["decrypt"]);
    const plain = await crypto.subtle.decrypt({ name: "AES-GCM", iv: b64(P.iv) }, key, b64(P.data));
    const html = new TextDecoder().decode(plain);
    try { sessionStorage.setItem("gfd:pw", password); } catch (e) { /* 無痕視窗 */ }
    document.open(); document.write(html); document.close();
  }
  form.addEventListener("submit", async (e) => {
    e.preventDefault(); err.textContent = ""; go.disabled = true;
    try { await open(pw.value); } catch (ex) { err.textContent = "密碼不對，或這個瀏覽器不支援解密。"; go.disabled = false; pw.select(); }
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
