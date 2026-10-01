"""老師的提問與交辦，學員回答後更新（2026-10-01 課堂）。顯示在「名詞解釋・FAQ」分頁的 FAQ 檢視。

每題：id、q（問題）、cat（分類）、asked（哪次課提的）、status（open／answered）、answer（學員的回答，空字串＝未答）、
links（本站哪裡看：分頁 id、"cascade:<事件 id>" 或 "glossary:<名詞 id>"）。
回答請直接改這個檔案的 answer 與 status，再 `python3 gfd.py build`。build 時會檢查連結存在。
"""
from . import config as C
from . import glossary as G

CATS = [("macro", "總體與利率"), ("bond", "債市"), ("equity", "股市與財報"), ("commodity", "商品"),
        ("fx", "匯市與外匯存底"), ("history", "歷史事件"), ("site", "網站")]


def _q(id, q, cat, links=(), answer="", asked="2026-10-01"):
    return dict(id=id, q=q, cat=cat, asked=asked, status="answered" if answer else "open", answer=answer, links=list(links))


ITEMS = [
    _q("fisher", "費雪方程式是什麼？它和聯準會的利率決策有什麼關係？", "macro", ["glossary:fisher", "bond"]),
    _q("yield_relations", "殖利率、債券利率、貨幣利率三者之間怎麼互相影響？", "bond", ["glossary:yield", "glossary:price_yield", "glossary:policy_rate", "bond"]),
    _q("yield_panic", "為什麼市場一怕，殖利率有時反而上升？大家搶著出場時發生了什麼？", "bond", ["glossary:price_yield", "cascade"]),
    _q("curve", "短天期與長天期殖利率的差異是什麼？曲線倒掛代表什麼？", "bond", ["glossary:curve", "glossary:inversion", "bond"]),
    _q("statements", "四大財務報表各看什麼？怎麼分辨賺的是不是真的錢？", "equity", ["glossary:bs", "glossary:is", "glossary:cf", "glossary:se", "flow"]),
    _q("exam", "高級業務員考試的重點範圍是什麼？", "equity"),
    _q("oil_types", "頁岩油、傳統石油、重油、海上石油有什麼差別？儲量與成本差多少？", "commodity",
       ["glossary:shale", "glossary:conventional_oil", "glossary:heavy_oil", "glossary:offshore_oil", "commodity"]),
    _q("energy_capacity", "能源目前的市場產值與潛在產能是多少？", "commodity", ["glossary:potential_output", "commodity"]),
    _q("grains", "玉米、大豆、小麥的全球總產值與總需求是多少？主要產國在哪裡？在哪個交易所交易？", "commodity",
       ["glossary:corn", "glossary:soybean", "glossary:wheat", "glossary:exchanges", "commodity"]),
    _q("gold_standard", "金本位是什麼？美元的準備貨幣地位是怎麼來的？", "commodity", ["glossary:gold_standard", "glossary:gold_dollar", "commodity"]),
    _q("copper", "銅的主要產國在哪裡？需求來自哪些產業？", "commodity", ["glossary:copper", "commodity"]),
    _q("rare_earth", "為什麼稀土由中國主導？美國為什麼很難把產能拿回來？", "commodity", ["glossary:rare_earth"]),
    _q("fertilizer_chain", "油價 → 肥料 → 農產品 → 通膨 → 升息，這條鏈在資料裡成立嗎？", "commodity",
       ["glossary:fertilizer", "glossary:ripple", "chains", "commodity"]),
    _q("reserves_top10", "GDP 前十大國家的外匯存底有多少？各國持有多少美債？存底夠不夠？", "fx",
       ["glossary:reserves", "glossary:tic", "fx"]),
    _q("asia97", "1997 年亞洲金融風暴為什麼發生？泰國與韓國各自的問題是什麼？", "history",
       ["glossary:asia97", "glossary:speculative_attack", "cascade:baht97", "cascade:hk97"]),
    _q("plaza", "廣場協議是什麼？日本為什麼陷入失落的三十年？", "history",
       ["glossary:plaza", "glossary:lost_decades", "cascade:plaza85", "cascade:boj89"]),
    _q("islm", "IS-LM（希克斯—漢森）模型說什麼？流動性陷阱是什麼？", "history", ["glossary:islm", "glossary:liquidity_trap"]),
    _q("deflation", "通貨緊縮的原因與影響是什麼？", "history", ["glossary:deflation", "glossary:lost_decades"]),
    _q("china_property", "中國房地產風暴是怎麼造成的？政府做了什麼？", "history", ["glossary:china_property", "cascade:evergrande21"]),
    _q("shock_types", "怎麼把歷史事件分成短暫、長期、永久衝擊？中國的事件是不是真的半年後才浮現？", "history",
       ["glossary:shock_duration", "cascade"]),
    _q("site_login", "網站要加一層簡單的登入。", "site", [],
       answer="已做：2026-10-01 起公開版整頁用密碼加密後才發佈（在瀏覽器裡解密，新部署的網站上只有密文，搜尋引擎看不到）。"
              "密碼設在本機的 data/public_password.txt。簡單的密碼只能擋路人：密文公開，有心人可以離線一直猜。"
              "之前部署過的明文版本可能還留在 GitHub 或網路快取裡一段時間。"),
    _q("site_faq", "把老師的提問做成 FAQ 放在網站上，學員回答後更新。", "site", [],
       answer="已做：和名詞解釋放在同一個分頁（「名詞解釋・FAQ」，上方切換）。回答寫在 gfd/faq.py 的 answer 欄，重新產生頁面就會更新。"),
    _q("site_embed", "網站是公開的，注意不要直接嵌入他人平台，自己收集資料整理即可。", "site", ["daily"],
       answer="目前「鉅亨每日」只列新聞標題與連結（公開版不含摘要），行情數字是自己抓來計算的；沒有嵌入任何外部頁面。"),
]


def validate():
    cats = {c for c, _ in CATS}
    ids = [i["id"] for i in ITEMS]
    events = {e["id"] for e in C.SHOCK_EVENTS}
    terms = {e["id"] for e in G.ENTRIES}
    problems = []
    if len(ids) != len(set(ids)):
        problems.append("FAQ id 重複")
    for i in ITEMS:
        if i["cat"] not in cats:
            problems.append(f"{i['id']}：分類 {i['cat']} 不存在")
        if i["status"] not in ("open", "answered"):
            problems.append(f"{i['id']}：status 必須是 open 或 answered")
        for link in i["links"]:
            kind, _, target = link.partition(":")
            if not target:                       # 純分頁連結，例如 "bond"、"cascade"
                if kind not in G.TABS:
                    problems.append(f"{i['id']}：分頁 {kind} 不存在")
            elif kind == "cascade":
                if target not in events:
                    problems.append(f"{i['id']}：事件 {target} 不存在")
            elif kind == "glossary":
                if target not in terms:
                    problems.append(f"{i['id']}：名詞 {target} 不存在")
            else:
                problems.append(f"{i['id']}：連結 {link} 格式不對")
    if problems:
        raise ValueError("FAQ 內容有問題：" + "；".join(problems))


def payload():
    validate()
    return dict(cats=[dict(id=a, name=b) for a, b in CATS], items=ITEMS,
                events={e["id"]: e["name"] for e in C.SHOCK_EVENTS}, terms={e["id"]: e["term"] for e in G.ENTRIES})
