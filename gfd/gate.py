"""公開版的登入頁（2026-10-01 課堂：網站要有一層簡單的登入；2026-10-02 使用者：只要形式上的登入頁，不用加密）。

做法：公開版照舊是完整的明文頁面，最上層蓋一張全螢幕的登入頁，輸入正確密碼才拿掉。
這是形式上的一道門，擋的是路過的人，不是防護——看原始碼或停用 JavaScript 就看得到內容。
頁面裡只放密碼的簡單雜湊（FNV-1a），不放明文密碼；同一個分頁登入過，重新整理不用再輸入（sessionStorage）。

密碼從環境變數 GFD_PUBLIC_PASSWORD 或 data/public_password.txt 讀（data/ 不進版控），都沒有就用 123。
"""
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
PASSWORD_FILE = ROOT / "data" / "public_password.txt"
DEFAULT_PASSWORD = "123"


def password():
    pw = os.environ.get("GFD_PUBLIC_PASSWORD")
    if pw and pw.strip():
        return pw.strip()
    if PASSWORD_FILE.exists():
        pw = PASSWORD_FILE.read_text(encoding="utf-8").strip()
        if pw:
            return pw
    return DEFAULT_PASSWORD


def fnv1a(text):
    """32 位元 FNV-1a，逐個 UTF-16 碼元計算（和頁面上 JS 的 charCodeAt 一致）。不是加密，只是不把密碼原樣寫進頁面。"""
    data = text.encode("utf-16-le")
    h = 0x811C9DC5
    for i in range(0, len(data), 2):
        h ^= data[i] | (data[i + 1] << 8)
        h = (h * 0x01000193) & 0xFFFFFFFF
    return f"{h:08x}"


LOGIN = """<div id="gfd-login" role="dialog" aria-modal="true" aria-labelledby="gfd-login-title">
<style>
  html.gfd-locked { overflow: hidden; }
  #gfd-login { position: fixed; inset: 0; z-index: 9999; display: grid; place-items: center; padding: 16px;
    background: var(--ground, #f5f6fa); color: var(--ink, #1d2130); }
  html:not(.gfd-locked) #gfd-login { display: none; }
  #gfd-login form { width: min(340px, 100%); display: flex; flex-direction: column; gap: 10px; }
  #gfd-login .gfd-login-brand { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
  #gfd-login .gfd-login-brand svg { width: 30px; height: 30px; fill: none; stroke: var(--accent, #2b3f8f); stroke-width: 2.4; stroke-linecap: round; }
  #gfd-login .gfd-login-brand path:nth-child(2) { opacity: .6; } #gfd-login .gfd-login-brand path:nth-child(3) { opacity: .32; }
  #gfd-login h1 { font: 700 22px/1.1 var(--f-disp, sans-serif); letter-spacing: .04em; margin: 0; }
  #gfd-login button { transition: transform 120ms cubic-bezier(0.23, 1, 0.32, 1); }
  #gfd-login button:active { transform: scale(0.97); }
  #gfd-login input:focus { outline: none; box-shadow: 0 0 0 3px var(--accent-soft, #e3e7f6); border-color: var(--accent, #2b3f8f); }
  #gfd-login input { font: inherit; font-size: 15px; padding: 9px 12px; border: 1px solid var(--line-strong, #c5cad6);
    border-radius: 6px; background: var(--surface, #fff); color: inherit; }
  #gfd-login button { font: inherit; font-size: 15px; padding: 9px 12px; border: 0; border-radius: 6px; cursor: pointer;
    background: var(--accent, #2b3f8f); color: var(--on-accent, #fff); }
  /* 台灣慣例 --up 是紅、--down 是綠；錯誤訊息要紅色，所以用 --up */
  #gfd-login .err { color: var(--up, #bf2e2b); font-size: 13px; min-height: 1.4em; }
</style>
<form id="gfd-login-form" autocomplete="off">
  <div class="gfd-login-brand">
    <svg viewBox="0 0 32 32" aria-hidden="true"><path d="M3 10c6-5 12 5 18 0s8-3 8-3" /><path d="M3 17c6-5 12 5 18 0s8-3 8-3" /><path d="M3 24c6-5 12 5 18 0s8-3 8-3" /></svg>
    <h1 id="gfd-login-title">資金流向觀測台</h1>
  </div>
  <input id="gfd-login-pw" type="password" placeholder="密碼" aria-label="密碼" required>
  <button type="submit">進入</button>
  <div class="err" id="gfd-login-err" role="alert"></div>
</form>
<script>
(function () {
  var HASH = "__HASH__", KEY = "gfd:login";
  function fnv1a(s) { var h = 0x811c9dc5; for (var i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0; } return ("0000000" + h.toString(16)).slice(-8); }
  var root = document.documentElement, ok = false;
  try { ok = sessionStorage.getItem(KEY) === HASH; } catch (e) { /* 無痕視窗等：每次都要輸入 */ }
  if (!ok) root.classList.add("gfd-locked");
  var form = document.getElementById("gfd-login-form"), pw = document.getElementById("gfd-login-pw"), err = document.getElementById("gfd-login-err");
  if (!ok) setTimeout(function () { pw.focus(); }, 0);
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    if (fnv1a(pw.value) === HASH) {
      try { sessionStorage.setItem(KEY, HASH); } catch (ex) { /* 略過 */ }
      root.classList.remove("gfd-locked");
      // 圖表在登入頁後面已經畫好；拿掉遮罩後觸發一次 resize，讓依寬度繪製的圖表重算
      window.dispatchEvent(new Event("resize"));
    } else {
      err.textContent = "密碼不對。";
      pw.select();
    }
  });
})();
</script>
</div>
"""


def wrap(html, pw):
    """在 <body> 一開頭插入登入頁（在儀表板內容之前，避免內容先閃出來）。"""
    marker = "<body>\n"
    if html.count(marker) != 1:
        raise SystemExit("公開版頁面找不到唯一的 <body> 起點，無法插入登入頁")
    return html.replace(marker, marker + LOGIN.replace("__HASH__", fnv1a(pw)), 1)
