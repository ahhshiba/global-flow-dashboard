"""名詞解釋分頁的內容。

每一條：id、term（中文）、en（英文）、cat（分類）、short（一句話）、read（怎麼看／為什麼重要）、
links（本站哪裡看：分頁 id，或 "cascade:<事件 id>" 直接打開那個事件）、related（相關名詞 id）、
class_note（True＝2026-10-01 課堂討論提到的名詞）。

內容只寫定義與看法的依據；數字標「約」的是量級，不是精確統計。build 時會呼叫 validate()，
連結到不存在的分頁、事件或名詞會直接失敗，不會默默變成死連結。
"""
from . import config as C

CATS = [
    ("macro", "總體經濟與利率"),
    ("fx", "匯市"),
    ("bond", "債市"),
    ("equity", "股市與財務報表"),
    ("commodity", "商品"),
    ("history", "歷史事件"),
    ("theory", "經濟理論"),
    ("method", "本站用語（統計）"),
]

TABS = {"overview", "fx", "bond", "equity", "commodity", "flow", "vol", "cascade", "chains", "playbook",
        "research", "daily", "glossary"}


def _e(id, term, en, cat, short, read, links=(), related=(), class_note=False):
    return dict(id=id, term=term, en=en, cat=cat, short=short, read=read, links=list(links),
                related=list(related), class_note=class_note)


ENTRIES = [
    # ── 總體經濟與利率 ──
    _e("fisher", "費雪方程式", "Fisher equation", "macro",
       "名目利率 ≈ 實質利率 ＋ 預期通膨率。",
       "名目利率 4%、預期通膨 3%，實質利率約 1%。央行常用實質利率判斷政策鬆緊：通膨下降而名目利率不動，"
       "實質利率等於自動上升、政策變緊；反過來，通膨上升而不升息，實質利率下降、政策變鬆。"
       "它說明的是三者的關係，不是央行的決策規則——升降息還要看就業、金融穩定等。",
       links=["bond"], related=["nominal_real", "expected_inflation", "policy_rate", "cpi"], class_note=True),
    _e("nominal_real", "名目利率／實質利率", "Nominal vs. real interest rate", "macro",
       "名目利率是看得到的利率；實質利率是扣掉通膨後，錢真正的購買力報酬。",
       "存款利率 2%、通膨 3%，實質利率 −1%：錢放著其實在變薄。實質利率高時，不生利息的資產（黃金）"
       "相對吃虧；實質利率低或為負時，資金傾向流向股票、商品等資產。",
       links=["bond", "commodity"], related=["fisher", "gold_dollar"]),
    _e("expected_inflation", "預期通膨", "Inflation expectations", "macro",
       "市場或民眾預期未來的通膨率；會影響工資、定價與長天期利率。",
       "常見量法：名目公債殖利率減去同天期抗通膨公債（TIPS）殖利率，叫「損益兩平通膨率」；"
       "或用消費者調查。預期一旦失控（大家都相信會一直漲），央行要用更高的利率才壓得住。",
       related=["fisher", "cpi"]),
    _e("policy_rate", "政策利率（貨幣利率）", "Policy rate", "macro",
       "央行直接設定的短期利率：美國是聯邦資金利率，台灣是重貼現率。",
       "短天期公債殖利率（例如美國 3 個月國庫券）幾乎貼著政策利率走；長天期殖利率則加上對未來"
       "成長與通膨的預期。課堂說的「貨幣利率」指的就是這一端。",
       links=["bond"], related=["fed", "curve", "yield"], class_note=True),
    _e("fed", "聯準會", "Federal Reserve / FOMC", "macro",
       "美國的中央銀行；聯邦公開市場委員會（FOMC）一年開 8 次會決定利率。",
       "法定雙重目標是充分就業與物價穩定（通膨目標 2%，以 PCE 物價衡量）。會後聲明、點陣圖與主席談話"
       "常比利率決定本身更能移動市場（本站事件衝擊收錄了 1994 首次升息、2013 縮減恐慌、2022 傑克森洞等）。",
       links=["cascade:taper13", "cascade:jackson22", "cascade:fed94"], related=["policy_rate", "qe"]),
    _e("gdp", "國內生產毛額 GDP", "Gross domestic product", "macro",
       "一個國家一段期間內生產的最終商品與服務總值。",
       "看國力與償債能力的基礎：GDP 大、成長穩，借錢的能力（與可承受的債務）就高。比較國家時要分清楚"
       "名目或實質、市場匯率或購買力平價。統計品質各國不同，資料可信度本身也是判斷的一部分。",
       related=["cpi", "reserves", "sovereign"], class_note=True),
    _e("cpi", "消費者物價指數 CPI", "Consumer price index", "macro",
       "一籃子消費品價格的變化，最常用的通膨指標。",
       "「核心 CPI」扣掉波動大的食物與能源，較能看出趨勢。油價、肥料、農產品漲價會一層層推高 CPI"
       "（見傳導鏈的通膨鏈）。",
       links=["chains"], related=["fisher", "fertilizer", "ripple"], class_note=True),
    _e("qe", "量化寬鬆 QE", "Quantitative easing", "macro",
       "政策利率已近零時，央行改成大量買進公債等資產，壓低長天期利率、增加市場資金。",
       "反向操作叫縮表（QT）。2013 年柏南奇只是暗示要「縮減購債」，就引發美債殖利率急升與新興市場資金外流。",
       links=["cascade:taper13", "cascade:draghi12"], related=["liquidity_trap", "fed"]),
    _e("potential_output", "潛在產出／產能", "Potential output / capacity", "macro",
       "總體經濟：不引發通膨加速時，經濟能持續生產的最大量。產業：一個產業目前能生產的上限。",
       "實際產出高於潛在產出（產出缺口為正）通常伴隨通膨壓力。課堂在能源談的「潛在產能」是後一個意思："
       "已探明儲量、可動用的鑽機與產能，決定價格上漲時供給能多快跟上。",
       related=["shale"], class_note=True),
    _e("infrastructure", "基礎建設週期", "Infrastructure cycle", "macro",
       "大規模興建電網、交通、資料中心時，銅、鋁、鋼鐵等原物料需求大增，相關出口國的貨幣跟著走強。",
       "例：AI 資料中心與電網 → 銅需求 → 礦產出口國（智利、澳洲）受惠。課堂提到可觀察「人口多、仍落後、"
       "政治正在開放」的國家，一旦啟動基礎建設就是長期的原物料需求來源。",
       links=["commodity", "chains"], related=["copper", "aluminum", "nickel"], class_note=True),
    _e("ripple", "傳導鏈／漣漪效應", "Transmission chain / ripple effect", "macro",
       "一件事發生後，影響一層層往下傳：上游原物料 → 中游產業 → 下游需求 → 資金面。",
       "課堂例子：油價漲 → 肥料漲 → 農產品漲 → 通膨 → 經濟走弱 → 可能升息 → 經濟再受衝擊。能算到第幾層，"
       "就能提早避開風險。本站「傳導鏈」逐段量測這類假說，「事件衝擊」看真實事件後各層多快反應。",
       links=["chains", "cascade"], related=["shock_duration", "fertilizer", "cpi"], class_note=True),
    _e("shock_duration", "短暫／長期／永久衝擊", "Temporary vs. persistent shocks", "macro",
       "依事件影響持續多久分類：幾週內回到原位是短暫；持續數月到數年是長期；從此改變結構是永久。",
       "例：2019 年沙烏地油設施遇襲，油價幾天就回落（短暫）；1985 年廣場協議改變日圓水位與日本經濟路徑"
       "（長期到永久）。課堂另提到中國事件常被政策壓住，約半年後才浮現。本站「事件衝擊」目前只量到兩個月，"
       "更長的持續性還沒有量。",
       links=["cascade:abqaiq", "cascade:plaza85"], related=["ripple"], class_note=True),

    # ── 匯市 ──
    _e("dxy", "美元指數 DXY", "U.S. Dollar Index", "fx",
       "美元對六種貨幣的加權平均：歐元約 57.6%、日圓 13.6%、英鎊 11.9%、加幣 9.1%、瑞典克朗 4.2%、瑞郎 3.6%。",
       "歐元佔一半以上，所以 DXY 大致是歐元/美元的鏡像；人民幣、新台幣都不在裡面。DXY 上升＝美元走強，"
       "通常對新興市場與原物料價格不利。",
       links=["fx"], related=["quote_convention", "gold_dollar"]),
    _e("quote_convention", "匯率報價方式", "Quote convention", "fx",
       "大多數貨幣報「1 美元換多少外幣」（美元/日圓 158＝1 美元換 158 日圓）；歐元、英鎊、澳幣、紐幣反過來，"
       "報「1 單位外幣換多少美元」（歐元/美元 1.08）。",
       "讀圖時方向相反：美元/日圓數字上升＝日圓變弱；歐元/美元數字上升＝歐元變強。課堂說「只有歐元相反」，"
       "其實英鎊、澳幣、紐幣也是這種報法。本站的「歐元/美元」上升代表歐元走強。",
       links=["fx"], related=["dxy"], class_note=True),
    _e("carry", "套利交易", "Carry trade", "fx",
       "借低利率貨幣（如日圓），換成高利率貨幣或資產賺利差。",
       "平時穩定賺利差，一旦低利率貨幣升值或風險升高，大家同時平倉、買回日圓，會造成日圓急升與股市急跌"
       "（2024-08-05 日經單日 −12.4%）。這也是課堂說「利率高但國力弱，錢不會留」的機制。",
       links=["chains", "cascade:carry24"], related=["hot_money"], class_note=True),
    _e("hot_money", "熱錢", "Hot money", "fx",
       "追逐利差或匯差、隨時可能撤走的短期資金。",
       "熱錢流入讓貨幣短期走強，但不代表國力；利差縮小或風險升高就快速流出。長期資金（直接投資、產業移入）"
       "才反映國力。",
       related=["carry", "speculative_attack"], class_note=True),
    _e("reserves", "外匯存底", "Foreign exchange reserves", "fx",
       "央行持有的外國資產：外幣、外國公債（以美債為主）、黃金等。",
       "用途是穩定匯率、支付進口、應付外債。夠不夠的兩把常用尺：可支付幾個月進口（三個月是常見下限），"
       "以及是否大於一年內到期的外債。存底不足的國家容易被投機客攻擊（1997 泰國、韓國）。"
       "存底增減主要來自貿易順逆差與資金進出。",
       links=["fx", "flow", "cascade:baht97"], related=["current_account", "tic", "speculative_attack"], class_note=True),
    _e("current_account", "經常帳", "Current account", "fx",
       "貿易收支 ＋ 海外投資收益 ＋ 移轉收支；順差代表一國對外淨賺錢。",
       "長期順差的國家（台灣、日本、中國）累積外匯存底與海外資產；長期逆差的國家要靠外資流入補足，"
       "外資一撤就有貨幣壓力。",
       links=["flow"], related=["reserves"]),
    _e("tic", "美債持有（TIC 報告）", "Treasury International Capital", "fx",
       "美國財政部每月公布各國持有的美國公債金額。",
       "日本與中國長期是前兩大持有國。一國減持美債可能是為了護匯（賣美債換本幣）或分散風險；"
       "增持則常伴隨貿易順差。",
       links=["flow"], related=["reserves"], class_note=True),
    _e("speculative_attack", "投機性攻擊", "Speculative attack", "fx",
       "釘住匯率的貨幣若外匯存底不夠，投機客大量放空它，央行賣存底護盤，存底見底就只能放手貶值。",
       "經典案例：1992 年英鎊退出歐洲匯率機制、1997 年泰銖。關鍵指標是存底相對短期外債與進口的比例。",
       links=["cascade:erm92", "cascade:baht97"], related=["reserves", "asia97"], class_note=True),
    _e("managed_float", "管理浮動匯率（人民幣中間價）", "Managed float / CNY fixing", "fx",
       "中國人民銀行每天公布人民幣中間價，境內人民幣只能在中間價上下 2% 內波動；境外人民幣（CNH）較自由。",
       "這就是課堂說「他想升就升、想貶就貶」：價格由政策引導，不完全由供需決定，所以不建議當交易標的。"
       "2015 年 811 匯改是中間價機制的一次大改。",
       links=["cascade:cny815", "chains"], related=["hot_money"], class_note=True),
    _e("brexit", "英國脫歐與英鎊", "Brexit and the pound", "fx",
       "2016-06-23 英國公投決定脫離歐盟，英鎊隔天重挫；之後英鎊與歐元的走勢不再同步。",
       "課堂建議看歐元時把英鎊一起放進來比較。本站目前還沒有英鎊序列。",
       links=["cascade:brexit", "cascade:ukbudget22"], related=["quote_convention"], class_note=True),

    # ── 債市 ──
    _e("yield", "殖利率", "Yield (to maturity)", "bond",
       "以現在的價格買進、持有到到期，每年可得的報酬率。",
       "債券價格和殖利率反向：價格跌，殖利率就升。新聞說「殖利率飆升」，意思是債券在被賣、價格在跌。",
       links=["bond"], related=["price_yield", "curve", "policy_rate"], class_note=True),
    _e("price_yield", "債券價格與殖利率反向", "Price–yield relationship", "bond",
       "市場利率上升時，舊債券的固定票息變得不吸引人，價格必須下跌才賣得掉，於是殖利率上升。",
       "大約：價格變動 ≈ −存續期間 × 殖利率變動。10 年期公債存續期間約 8 年，殖利率升 1 個百分點，"
       "價格約跌 8%。恐慌時資金搶買公債避險，價格上漲、殖利率下跌；若市場擔心的是通膨或財政，"
       "反而是賣公債，殖利率上升——這就是同樣是「怕」，殖利率方向卻可能相反的原因。",
       links=["bond"], related=["duration", "yield"], class_note=True),
    _e("duration", "存續期間", "Duration", "bond",
       "債券價格對利率變動的敏感度，單位是年。",
       "期限越長、票息越低，存續期間越長、價格波動越大。長天期公債 ETF（如 TLT）利率一動，價格就大動。",
       links=["bond"], related=["price_yield"]),
    _e("curve", "殖利率曲線（短天期／長天期）", "Yield curve", "bond",
       "同一發行人不同到期日的殖利率連成的曲線。",
       "正常是向上斜：借越久要求越高的補償。短天期（3 個月、2 年）貼著政策利率與對升降息的預期；"
       "長天期（10 年、30 年）反映長期成長、通膨預期與期限溢酬。本站有 3 個月、5 年、10 年、30 年四個天期。",
       links=["bond"], related=["inversion", "policy_rate", "yield"], class_note=True),
    _e("inversion", "殖利率曲線倒掛", "Yield-curve inversion", "bond",
       "短天期殖利率高於長天期（例如 3 個月 > 10 年）。",
       "代表市場預期未來會降息、經濟會轉弱。美國歷次衰退前多出現過倒掛，但時間差從半年到兩年不等，"
       "也有倒掛後沒有衰退的時候。本站的「殖利率曲線（10 年減 3 個月）」小於 0 就是倒掛。",
       links=["bond", "cascade"], related=["curve"]),
    _e("credit_spread", "信用利差", "Credit spread", "bond",
       "公司債殖利率減去同天期公債殖利率，是投資人要求的違約風險補償。",
       "景氣好時收窄、危機時急速擴大；高收益債的利差對壞消息最敏感。",
       links=["bond"], related=["ig_hy"]),
    _e("ig_hy", "投資級債／高收益債", "Investment grade vs. high yield", "bond",
       "信用評等 BBB−（含）以上是投資級；以下是高收益債（俗稱垃圾債）。",
       "課堂建議買穩定大型公司的債券、避開題材股型的公司。本站用投資級基金 VWESX／LQD 與高收益 VWEHX／HYG 代表兩類。",
       links=["bond"], related=["credit_spread", "corporate_bond"], class_note=True),
    _e("corporate_bond", "公司債", "Corporate bond", "bond",
       "公司發行的債券；能不能還錢取決於公司穩定的現金流，而不是股價題材。",
       "看發行公司的營業現金流、負債比與評等。台灣與美國個別公司債缺免費長歷史資料，本站以公司債基金代理。",
       links=["bond", "flow"], related=["ig_hy", "cf"], class_note=True),
    _e("sovereign", "國家償債能力", "Sovereign creditworthiness", "bond",
       "國家借錢靠稅收還，稅收來自經濟規模，所以國債的根本是 GDP 與財政紀律。",
       "人口年輕、資源多的國家不一定還得起錢，政治制度與財政紀律才是關鍵（阿根廷多次違約）。",
       related=["gdp"], class_note=True),

    # ── 股市與財務報表 ──
    _e("bs", "資產負債表", "Balance sheet", "equity",
       "某一天公司擁有什麼（資產）、欠什麼（負債）、股東剩多少（權益）：資產 ＝ 負債 ＋ 股東權益。",
       "看負債比、流動比率：短期要還的錢，手上的流動資產夠不夠。",
       related=["is", "cf", "se"], class_note=True),
    _e("is", "損益表", "Income statement", "equity",
       "一段期間的營收、成本、費用與淨利。",
       "淨利是會計數字，含很多估計（折舊、應收帳款）；要和現金流量表對照，看賺的是不是真的錢。",
       related=["bs", "cf", "se"], class_note=True),
    _e("cf", "現金流量表", "Cash-flow statement", "equity",
       "一段期間現金真正的進出，分營業、投資、融資三部分。",
       "營業現金流 − 資本支出 ＝ 自由現金流，是發股利、買回、還債的來源。本站「現金流」分頁列出美股與台股龍頭的這三項。",
       links=["flow"], related=["bs", "is", "se"], class_note=True),
    _e("se", "股東權益變動表", "Statement of changes in equity", "equity",
       "股東權益這一年怎麼變：加淨利，減股利、庫藏股買回，加減增資等。",
       "持續大量買回庫藏股的公司，每股盈餘會被墊高；要分辨盈餘成長是本業還是股數變少。",
       related=["bs", "is", "cf"], class_note=True),
    _e("rotation", "類股輪動", "Sector rotation", "equity",
       "資金在不同產業或題材之間輪流進出。",
       "課堂說題材股「一波一波的，一下就沒了」：輪動快的標的，進出時點比基本面更決定報酬，風險也更高。",
       links=["equity"], related=["pe"], class_note=True),
    _e("pe", "本益比", "Price-to-earnings ratio", "equity",
       "股價 ÷ 每股盈餘；投資人願意為每 1 元盈餘付幾元。",
       "本益比高代表市場對未來成長期待高；整體市場本益比偏高時，壞消息造成的下跌通常較大。",
       links=["equity"], related=["is"]),

    # ── 商品 ──
    _e("wti_brent", "WTI 與布蘭特原油", "WTI and Brent crude", "commodity",
       "兩大原油基準價：WTI 在美國奧克拉荷馬州庫欣交割（紐約商業交易所），布蘭特代表北海原油（洲際交易所）。",
       "布蘭特代表海運的國際原油，通常略高於 WTI。2020-04-20 WTI 期貨曾因儲油空間耗盡跌到負值。",
       links=["commodity", "cascade:negoil20"], related=["shale", "conventional_oil", "exchanges"]),
    _e("conventional_oil", "傳統石油", "Conventional oil", "commodity",
       "存在孔隙多、容易流動的岩層中，直井就能開採，例如沙烏地的大油田。",
       "開採成本最低，是 OPEC 能調節供給、打價格戰的底氣。",
       related=["shale", "offshore_oil", "heavy_oil"], class_note=True),
    _e("shale", "頁岩油", "Shale (tight) oil", "commodity",
       "封存在緻密頁岩中的原油，要用水平鑽井加水力壓裂才能開採；2010 年後讓美國成為最大產油國。",
       "單井產量衰退快，必須一直鑽新井；但從決定開鑽到出油只要數月，油價一漲就能較快增產，"
       "所以頁岩油限制了油價長期飆漲的空間。成本高於中東傳統油田，油價太低時會減產。",
       links=["commodity"], related=["conventional_oil", "potential_output"], class_note=True),
    _e("heavy_oil", "重油／油砂", "Heavy oil / oil sands", "commodity",
       "密度高、黏稠的原油，例如加拿大油砂、委內瑞拉奧利諾科帶。",
       "儲量很大，但開採與煉製成本高、需要特殊煉油設備，油價低時最先失去競爭力。",
       related=["conventional_oil", "shale"], class_note=True),
    _e("offshore_oil", "海上石油", "Offshore oil", "commodity",
       "在海床下開採的石油，如墨西哥灣、巴西鹽下層、北海。",
       "深水專案從投資到出油常要五到十年，資本支出大；颶風與事故會中斷供給（2005 卡崔娜、2010 深水地平線）。",
       links=["cascade:katrina", "cascade:macondo"], related=["conventional_oil"], class_note=True),
    _e("natgas", "天然氣", "Natural gas", "commodity",
       "常和石油一起被開採出來，但它是獨立的燃料市場，價格由地區供需決定。",
       "三大基準：美國亨利港、歐洲 TTF、亞洲液化天然氣（LNG）。運輸要靠管線或液化船，所以各地價差可以很大"
       "（2022 年歐洲天然氣危機）。天然氣也是氮肥的主要原料。",
       links=["commodity", "cascade:nordstream"], related=["fertilizer"], class_note=True),
    _e("fertilizer", "肥料（氮、磷、鉀）", "Fertilizers", "commodity",
       "農作物三大養分：氮肥（尿素、氨）、磷肥、鉀肥。",
       "氮肥主要用天然氣製造，所以能源漲價會推高肥料成本，再推高農產品成本——課堂的「油漲 → 肥料漲 → 農產品漲」"
       "更精確的路徑是天然氣。俄羅斯與白俄羅斯是鉀肥大出口國，2022 年戰爭同時衝擊能源與肥料。",
       links=["chains", "cascade:ukraine22"], related=["natgas", "corn", "ripple"], class_note=True),
    _e("corn", "玉米", "Corn (maize)", "commodity",
       "以產量計全球最大的穀物，約 12 億噸；美國最大產國（約三分之一），其次中國、巴西。",
       "多數用作飼料與生質乙醇，直接當主食的比例不高；所以玉米價格同時連動肉類成本與油價。"
       "主要在芝加哥期貨交易所（CBOT）交易。",
       links=["commodity"], related=["soybean", "wheat", "exchanges", "fertilizer"], class_note=True),
    _e("soybean", "大豆", "Soybeans", "commodity",
       "巴西最大產國，其次美國、阿根廷；中國是最大進口國，約佔全球大豆貿易六成。",
       "壓榨成豆粕（飼料）與豆油；美中貿易戰時是中國反制美國的主要商品。主要在 CBOT 交易。",
       links=["commodity", "cascade:tariff18"], related=["corn", "exchanges"], class_note=True),
    _e("wheat", "小麥", "Wheat", "commodity",
       "全球產量約 8 億噸；中國、印度、歐盟產量大，俄羅斯是最大出口國，烏克蘭、美國、加拿大、澳洲也是主要出口國。",
       "直接當主食的比例比玉米高；2022 年俄烏戰爭後一週內大漲。美國期貨有芝加哥軟紅冬麥與堪薩斯硬紅冬麥。",
       links=["commodity", "cascade:ukraine22"], related=["corn", "exchanges"], class_note=True),
    _e("exchanges", "主要商品交易所", "Commodity exchanges", "commodity",
       "芝加哥商業交易所集團（CME：CBOT 穀物、NYMEX 能源、COMEX 金屬）、洲際交易所（ICE：布蘭特、軟性商品）、"
       "倫敦金屬交易所（LME：銅、鋁、鎳）、上海期貨交易所與大連、鄭州商品交易所。",
       "同一商品在不同交易所的價格差，反映運費、品質與地區供需。",
       related=["corn", "wti_brent", "copper"], class_note=True),
    _e("gold_standard", "金本位與布列敦森林體系", "Gold standard / Bretton Woods", "commodity",
       "金本位：貨幣可按固定比例兌換黃金。1944 年布列敦森林體系：各國貨幣釘住美元，美元可按每盎司 35 美元向美國兌換黃金。",
       "1971-08-15 尼克森宣布停止美元兌換黃金，之後進入浮動匯率與法定貨幣時代。美元從此靠美國的經濟、"
       "軍事與金融市場深度維持準備貨幣地位，而不是靠黃金。",
       links=["commodity"], related=["gold_dollar", "dxy"], class_note=True),
    _e("gold_dollar", "黃金與美元", "Gold and the dollar", "commodity",
       "黃金以美元計價，美元走強時其他國家買黃金變貴，金價常與美元反向。",
       "黃金不生利息，所以實質利率上升時持有黃金的機會成本變高、金價承壓；危機時則是避險資產"
       "（本站量到：金融危機後一個月黃金 10 次漲 9 次）。",
       links=["commodity", "cascade"], related=["gold_standard", "nominal_real", "dxy"], class_note=True),
    _e("copper", "銅", "Copper", "commodity",
       "導電性好，用於電線、電網、電動車、資料中心；常被叫做「銅博士」，因為需求反映景氣。",
       "智利產量最大（約四分之一），其次是剛果民主共和國與秘魯；中國是最大消費國。AI 與電網建設是近年的新需求。",
       links=["commodity"], related=["infrastructure", "exchanges"], class_note=True),
    _e("aluminum", "鋁", "Aluminum", "commodity",
       "用於建築、交通工具與包裝；中國生產全球約六成的原鋁。",
       "冶煉非常耗電，電價與能源政策影響供給；基礎建設與汽車輕量化帶動需求。",
       links=["commodity"], related=["infrastructure"], class_note=True),
    _e("nickel", "鎳", "Nickel", "commodity",
       "約三分之二用於不鏽鋼，其餘多用於電池；印尼供應全球過半。",
       "2022-03 倫敦金屬交易所鎳價兩天內暴漲並暫停交易，是空頭被軋的極端案例。",
       related=["lithium", "infrastructure"], class_note=True),
    _e("lithium", "鋰", "Lithium", "commodity",
       "電池的關鍵原料；澳洲（硬岩礦）產量最大，智利、阿根廷從鹽湖提取，精煉產能集中在中國。",
       "價格隨電動車需求劇烈循環；本站目前沒有鋰的價格序列。",
       related=["nickel", "rare_earth"], class_note=True),
    _e("rare_earth", "稀土", "Rare earth elements", "commodity",
       "17 種元素（15 種鑭系元素加鈧、釔），用於永磁馬達（電動車、風機）、國防與電子。",
       "中國約佔七成開採、九成精煉。難處不在礦，而在分離精煉：化學流程複雜、污染重、要長年累積技術，"
       "所以美國即使有礦（加州 Mountain Pass），重建完整供應鏈的成本與時間都很高。",
       related=["lithium"], class_note=True),

    # ── 歷史事件 ──
    _e("plaza", "廣場協議", "Plaza Accord (1985)", "history",
       "1985-09-22 美、日、西德、法、英在紐約廣場飯店協議聯手讓美元貶值。",
       "日圓兩年多內升值約一倍，日本出口受壓；日本央行長期寬鬆應對，資金推升股市與房地產泡沫，"
       "1989 年底升息後泡沫破裂（見「失落的三十年」）。",
       links=["cascade:plaza85", "cascade:boj89"], related=["lost_decades", "dxy"], class_note=True),
    _e("lost_decades", "失落的三十年", "Japan's lost decades", "history",
       "1990 年泡沫破裂後，日本長期低成長、通貨緊縮、銀行壞帳拖累。",
       "日經指數 1989-12-29 的高點 38,915 點，直到 2024-02 才被突破。常被用來說明資產泡沫、流動性陷阱"
       "與通貨緊縮怎麼互相強化。",
       links=["cascade:boj89"], related=["deflation", "liquidity_trap", "plaza"], class_note=True),
    _e("asia97", "1997 亞洲金融風暴", "1997 Asian financial crisis", "history",
       "1997-07-02 泰國外匯存底耗盡、放棄泰銖釘住美元，危機擴散到印尼、韓國、馬來西亞、菲律賓；"
       "韓國 11 月向國際貨幣基金求援。",
       "共同條件：匯率釘住美元、大量短期外幣借款、經常帳逆差、房地產泡沫與銀行監理鬆散；1995 年後美元走強、"
       "日圓走弱又削弱了出口競爭力。不只是「被攻擊」，而是結構先有破口。",
       links=["cascade:baht97", "cascade:hk97"], related=["speculative_attack", "reserves"], class_note=True),
    _e("china_property", "中國房地產危機", "China property crisis", "history",
       "2020 年起監管「三道紅線」限制建商負債，資金鏈斷裂，恆大等大型建商違約，房價與土地出讓收入下滑。",
       "地方政府高度依賴賣地收入，房市下滑同時打擊地方財政與家庭財富。政策會先壓住表面數字，"
       "影響常延後才浮現——呼應課堂說中國事件「不會不發生，只是晚一點發生」。",
       links=["cascade:evergrande21"], related=["managed_float"], class_note=True),

    # ── 經濟理論 ──
    _e("islm", "IS-LM 模型（希克斯—漢森模型）", "IS-LM model (Hicks–Hansen)", "theory",
       "用兩條線找出利率與產出的均衡：IS 是商品市場（利率越低、投資越多、產出越高），LM 是貨幣市場"
       "（產出越高、貨幣需求越大、利率越高）。",
       "財政政策移動 IS 線，貨幣政策移動 LM 線。陷入流動性陷阱時 LM 線在低利率處變平，央行再印錢也壓不低利率，"
       "這時財政政策比貨幣政策有效——日本 1990 年代就是例子。（逐字稿的「希克斯底線模型」應是這個模型。）",
       related=["liquidity_trap", "deflation"], class_note=True),
    _e("liquidity_trap", "流動性陷阱", "Liquidity trap", "theory",
       "利率已降到接近零，民眾與銀行寧可持有現金，央行增加貨幣供給也刺激不了借貸與消費。",
       "日本 1990 年代後、美國與歐洲 2008 年後都出現過；央行因此改用量化寬鬆、前瞻指引，或需要財政支出接手。",
       links=["cascade:boj89"], related=["islm", "qe", "deflation"], class_note=True),
    _e("deflation", "通貨緊縮", "Deflation", "theory",
       "物價全面、持續下跌。",
       "看似東西變便宜，但大家延後消費、企業延後投資；債務的實質負擔變重，形成惡性循環。"
       "成因常是需求不足、資產泡沫破裂後去槓桿。日本是最長的案例。",
       related=["lost_decades", "liquidity_trap", "fisher"], class_note=True),

    # ── 本站用語 ──
    _e("vix", "VIX 恐慌指數", "CBOE Volatility Index", "method",
       "用 S&P 500 選擇權價格推算的未來 30 天預期波動率（年化 %）。",
       "平常約 12–20，超過 30 代表市場緊張；2020-03-16 收盤 82.69 是歷史最高收盤。VIX 是跟著股市下跌一起飆高的，"
       "比較像同步到落後的溫度計，而不是預告；股市大跌後 VIX 必然先飆後回落，所以本站訊號劇本把它列為觀察指標、不列入可投資標的。",
       links=["vol", "playbook"], related=["leading_lagging"], class_note=True),
    _e("leading_lagging", "領先／同步／落後指標", "Leading / coincident / lagging indicators", "method",
       "領先指標在景氣轉折前先動（新訂單、殖利率曲線）；同步指標同時動（工業生產）；落後指標事後才確認（失業率、VIX 的高點）。",
       "判斷「現在該做什麼」要靠領先指標；落後指標用來確認、不適合用來進出場。本站「30 年關聯」有各組配對的領先落後月數。",
       links=["research"], related=["vix", "inversion"], class_note=True),
    _e("log_return", "對數報酬", "Log return", "method",
       "ln(今天價格 ÷ 起點價格) × 100。小幅變動時幾乎等於百分比報酬。",
       "好處是可以直接相加：兩週 +3% 再兩週 −1%，合計就是 +2%。大跌時會比百分比數字大一些（−20.5% 的單日跌幅是 −22.9 對數報酬）。",
       links=["cascade"], related=["bp"]),
    _e("bp", "基點 bp", "Basis point", "method",
       "0.01 個百分點。殖利率從 4.00% 升到 4.25% ＝ 上升 25bp。",
       "利率與殖利率的變動一律用 bp 表示，避免「上升 25%」這種誤讀。",
       links=["bond"], related=["yield"]),
    _e("sigma", "標準差 σ", "Standard deviation", "method",
       "一個標的「平常一天波動多大」的尺度。",
       "本站判斷事件有沒有「實質反應」：累積變動超過事件前 60 天的 2σ×√天數才算，所以波動大的標的要動更多才算數。",
       links=["cascade"], related=["baseline"]),
    _e("baseline", "無條件基準（平常）", "Unconditional baseline", "method",
       "不管有沒有事件，這個標的任意一天起算同樣天數的中位數與上漲機率。",
       "S&P 500 平常一個月就有約六成機率上漲。事件後的數字一定要跟「平常」比，否則長期上漲的資產在任何事件後都像有「錢流入」。",
       links=["cascade", "playbook"], related=["excess", "pvalue"]),
    _e("excess", "超額", "Excess over baseline", "method",
       "事件後的中位數 − 平常的中位數。",
       "本站訊號劇本與事件衝擊的排名都用超額，不用原始報酬。",
       links=["playbook", "cascade"], related=["baseline"]),
    _e("pvalue", "p 值", "p-value", "method",
       "假設事件其實沒有效果，純靠運氣也能看到這麼極端結果的機率。",
       "p 越小越不像巧合；但檢定做得越多，p 小的格子本來就會越多，所以還要看偽發現率。",
       links=["playbook", "cascade"], related=["fdr"]),
    _e("fdr", "偽發現率／多重檢定", "False discovery rate", "method",
       "所有「通過」的結果裡，估計有多少比例其實是運氣。",
       "本站做法是虛無校準：把事件日期隨機移位、整套重跑，看假事件也有幾格通過，當作運氣預期。"
       "事件衝擊的分類比較約三分之二、訊號劇本約一半是運氣——這是用來提醒不要過度解讀單一格子。",
       links=["playbook", "cascade"], related=["pvalue"]),
    _e("proxy", "代理序列", "Proxy series", "method",
       "原標的還沒有資料的年代，用性質相近的序列代替（例：1999 年以前用 Fidelity 能源基金代替能源股 ETF）。",
       "只取代理在接點之前的報酬、以接點價位對齊；代理與原標的不是同一個資產，明細中逐筆標註。",
       links=["cascade"], related=[]),
]


def validate():
    """連結到不存在的分頁、事件或名詞，就直接失敗。"""
    cats = {c for c, _ in CATS}
    ids = [e["id"] for e in ENTRIES]
    events = {e["id"] for e in C.SHOCK_EVENTS}
    problems = []
    if len(ids) != len(set(ids)):
        problems.append("名詞 id 重複")
    for e in ENTRIES:
        if e["cat"] not in cats:
            problems.append(f"{e['id']}：分類 {e['cat']} 不存在")
        for link in e["links"]:
            tab, _, event = link.partition(":")
            if tab not in TABS:
                problems.append(f"{e['id']}：分頁 {tab} 不存在")
            if event and event not in events:
                problems.append(f"{e['id']}：事件 {event} 不存在")
        for r in e["related"]:
            if r not in ids:
                problems.append(f"{e['id']}：相關名詞 {r} 不存在")
    if problems:
        raise ValueError("名詞解釋內容有問題：" + "；".join(problems))


def payload():
    validate()
    return dict(cats=[dict(id=a, name=b) for a, b in CATS], entries=ENTRIES,
                events={e["id"]: e["name"] for e in C.SHOCK_EVENTS})
