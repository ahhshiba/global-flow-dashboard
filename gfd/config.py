"""資金流向觀測台：所有標的、分組、研究設定都集中在這裡。

要換龍頭股、加標的、改重點關鍵字，只改這個檔，其他程式不用動。
"""

START_MONTH = "1995-01"

# kind:
#   price  → 以月對數報酬(%)計算關聯；圖表用「起點=100」指數化
#   yield  → 以月變動(bp)計算關聯；圖表畫原始殖利率(%)
#   level  → VIX 這類水位型指標，以月對數變動計算關聯
# src:
#   ("yahoo", symbol[, "close"])     月線；個股/基金預設用還原權息收盤
#   ("cbc", file, column)            中央銀行統計資料庫（月資料）
#   ("wb_pink", sheet, header)       世界銀行 Pink Sheet（月均價）
#   ("mof_jgb", tenor)               日本財務省 JGB 殖利率（日資料取月底）
SERIES = [
    # ── 匯市 ──
    dict(id="fx_dxy", group="fx", name="美元指數 DXY", kind="price", unit="指數",
         src=("yahoo", "DX-Y.NYB", "close"), note="月底值"),
    dict(id="fx_usdtwd", group="fx", name="美元/新台幣", kind="price", unit="TWD",
         src=("cbc", "BP01M01", "新台幣NTD/USD"), note="央行月均匯率；上升＝台幣貶值"),
    dict(id="fx_usdjpy", group="fx", name="美元/日圓", kind="price", unit="JPY",
         src=("cbc", "BP01M01", "日圓JPY/USD"), note="月均匯率；上升＝日圓貶值"),
    dict(id="fx_usdcny", group="fx", name="美元/人民幣", kind="price", unit="CNY",
         src=("cbc", "BP01M01", "人民幣CNY/USD"), note="月均匯率；上升＝人民幣貶值"),
    dict(id="fx_eurusd", group="fx", name="歐元/美元", kind="price", unit="USD",
         src=("cbc", "BP01M01", "歐元USD/EUR"), note="月均匯率，1999 年歐元誕生起；上升＝歐元升值"),

    # ── 債市 ──
    dict(id="b_us3m", group="bond", name="美國 3 個月國庫券", kind="yield", unit="%",
         src=("yahoo", "^IRX", "close"), note="殖利率，月底值"),
    dict(id="b_us5y", group="bond", name="美國 5 年期公債", kind="yield", unit="%",
         src=("yahoo", "^FVX", "close"), note="殖利率，月底值"),
    dict(id="b_us10y", group="bond", name="美國 10 年期公債", kind="yield", unit="%",
         src=("yahoo", "^TNX", "close"), note="殖利率，月底值"),
    dict(id="b_us30y", group="bond", name="美國 30 年期公債", kind="yield", unit="%",
         src=("yahoo", "^TYX", "close"), note="殖利率，月底值"),
    dict(id="b_jp10y", group="bond", name="日本 10 年期國債", kind="yield", unit="%",
         src=("mof_jgb", "10Y"), note="日本財務省公布，取每月最後一個交易日"),
    dict(id="b_tw_disc", group="bond", name="台灣央行重貼現率", kind="yield", unit="%",
         src=("cbc", "EG2AM01", "重貼現率"), note="台灣 10 年公債無免費長歷史，以政策利率代表台灣利率循環"),
    dict(id="b_ust_long", group="bond", name="美國長天期公債基金 VUSTX", kind="price", unit="USD",
         src=("yahoo", "VUSTX"), note="還原息總報酬，代表美債價格"),
    dict(id="b_ig", group="bond", name="投資級公司債基金 VWESX", kind="price", unit="USD",
         src=("yahoo", "VWESX"), note="還原息總報酬；前十大公司債的代理（無免費逐券歷史）"),
    dict(id="b_hy", group="bond", name="高收益公司債基金 VWEHX", kind="price", unit="USD",
         src=("yahoo", "VWEHX"), note="還原息總報酬"),
    dict(id="b_lqd", group="bond", name="投資級公司債 ETF LQD", kind="price", unit="USD",
         src=("yahoo", "LQD"), note="2002 年起"),
    dict(id="b_hyg", group="bond", name="高收益債 ETF HYG", kind="price", unit="USD",
         src=("yahoo", "HYG"), note="2007 年起"),
    dict(id="b_brk", group="bond", name="波克夏 BRK-A", kind="price", unit="USD",
         src=("yahoo", "BRK-A"), note="手握大量美國短債與現金，放在債市觀察其與利率的關係"),

    # ── 股市 ──
    dict(id="eq_spx", group="equity", name="S&P 500", kind="price", unit="點",
         src=("yahoo", "^GSPC", "close"), note="價格指數"),
    dict(id="eq_ndx", group="equity", name="那斯達克 100", kind="price", unit="點",
         src=("yahoo", "^NDX", "close"), note="價格指數"),
    dict(id="eq_dji", group="equity", name="道瓊工業", kind="price", unit="點",
         src=("yahoo", "^DJI", "close"), note="價格指數"),
    dict(id="eq_sox", group="equity", name="費城半導體", kind="price", unit="點",
         src=("yahoo", "^SOX", "close"), note="價格指數；台股連動核心"),
    dict(id="eq_hsi", group="equity", name="恆生指數", kind="price", unit="點",
         src=("yahoo", "^HSI", "close"), note="價格指數"),
    dict(id="eq_twii", group="equity", name="台灣加權指數", kind="price", unit="點",
         src=("yahoo", "^TWII", "close"), splice=("cbc", "EF07M01", "股票市場股價指數"),
         note="1997-07 前以央行月資料接續（按重疊月比例換算）"),
    dict(id="eq_n225", group="equity", name="日經 225（參考）", kind="price", unit="點",
         src=("yahoo", "^N225", "close"), note="價格指數"),
    dict(id="eq_sse", group="equity", name="上證指數（參考）", kind="price", unit="點",
         src=("yahoo", "000001.SS", "close"), note="價格指數"),

    # ── 商品 ──
    dict(id="c_gold", group="commodity", name="黃金", kind="price", unit="$/oz",
         src=("wb_pink", "Monthly Prices", "Gold"), note="月均價"),
    dict(id="c_silver", group="commodity", name="白銀", kind="price", unit="$/oz",
         src=("wb_pink", "Monthly Prices", "Silver"), note="月均價"),
    dict(id="c_platinum", group="commodity", name="白金", kind="price", unit="$/oz",
         src=("wb_pink", "Monthly Prices", "Platinum"), note="月均價"),
    dict(id="c_copper", group="commodity", name="銅", kind="price", unit="$/mt",
         src=("wb_pink", "Monthly Prices", "Copper"), note="月均價"),
    dict(id="c_alu", group="commodity", name="鋁", kind="price", unit="$/mt",
         src=("wb_pink", "Monthly Prices", "Aluminum"), note="月均價"),
    dict(id="c_iron", group="commodity", name="鐵礦砂", kind="price", unit="$/dmtu",
         src=("wb_pink", "Monthly Prices", "Iron ore, cfr spot"), note="月均價"),
    dict(id="c_brent", group="commodity", name="布蘭特原油", kind="price", unit="$/bbl",
         src=("wb_pink", "Monthly Prices", "Crude oil, Brent"), note="月均價"),
    dict(id="c_wti", group="commodity", name="WTI 原油", kind="price", unit="$/bbl",
         src=("wb_pink", "Monthly Prices", "Crude oil, WTI"), note="月均價"),
    dict(id="c_natgas", group="commodity", name="美國天然氣", kind="price", unit="$/mmbtu",
         src=("wb_pink", "Monthly Prices", "Natural gas, US"), note="月均價"),
    dict(id="c_maize", group="commodity", name="玉米", kind="price", unit="$/mt",
         src=("wb_pink", "Monthly Prices", "Maize"), note="月均價"),
    dict(id="c_soy", group="commodity", name="大豆", kind="price", unit="$/mt",
         src=("wb_pink", "Monthly Prices", "Soybeans"), note="月均價"),
    dict(id="c_wheat", group="commodity", name="小麥", kind="price", unit="$/mt",
         src=("wb_pink", "Monthly Prices", "Wheat, US HRW"), note="月均價"),
    dict(id="ci_energy", group="commodity_index", name="能源指數", kind="price", unit="2010=100",
         src=("wb_pink", "Monthly Indices", "Energy"), note="世界銀行商品指數"),
    dict(id="ci_agri", group="commodity_index", name="農產品指數", kind="price", unit="2010=100",
         src=("wb_pink", "Monthly Indices", "Agriculture"), note="世界銀行商品指數"),
    dict(id="ci_metals", group="commodity_index", name="金屬與礦產指數", kind="price", unit="2010=100",
         src=("wb_pink", "Monthly Indices", "Metals & Minerals"), note="世界銀行商品指數"),
    dict(id="ci_precious", group="commodity_index", name="貴金屬指數", kind="price", unit="2010=100",
         src=("wb_pink", "Monthly Indices", "Precious Metals"), note="世界銀行商品指數"),
    dict(id="ci_nonenergy", group="commodity_index", name="非能源原物料指數", kind="price", unit="2010=100",
         src=("wb_pink", "Monthly Indices", "Non-energy"), note="世界銀行商品指數"),

    # ── VIX ──
    dict(id="v_vix", group="vol", name="VIX 恐慌指數", kind="level", unit="點",
         src=("yahoo", "^VIX", "close"), note="月底值"),
]

# 龍頭股觀察清單：大型權值股，不宣稱是即時市值排名，請依需要自行調整。
# (Yahoo 代碼, 名稱, 鉅亨代碼, 現金流來源鍵：美股=SEC CIK／台股=股票代號／港股=None)
LEADERS = {
    "us": dict(title="美股龍頭", index="eq_spx", items=[
        ("AAPL", "蘋果", "USS:AAPL:STOCK", 320193),
        ("MSFT", "微軟", "USS:MSFT:STOCK", 789019),
        ("NVDA", "輝達", "USS:NVDA:STOCK", 1045810),
        ("AMZN", "亞馬遜", "USS:AMZN:STOCK", 1018724),
        ("GOOGL", "Alphabet", "USS:GOOGL:STOCK", 1652044),
        ("META", "Meta", "USS:META:STOCK", 1326801),
        ("AVGO", "博通", "USS:AVGO:STOCK", 1730168),
        ("TSLA", "特斯拉", "USS:TSLA:STOCK", 1318605),
        ("BRK-B", "波克夏 B", "USS:BRK.B:STOCK", 1067983),
        ("JPM", "摩根大通", "USS:JPM:STOCK", 19617),
    ]),
    "tw": dict(title="台股龍頭", index="eq_twii", items=[
        ("2330.TW", "台積電", "TWS:2330:STOCK", "2330"),
        ("2317.TW", "鴻海", "TWS:2317:STOCK", "2317"),
        ("2454.TW", "聯發科", "TWS:2454:STOCK", "2454"),
        ("2308.TW", "台達電", "TWS:2308:STOCK", "2308"),
        ("2382.TW", "廣達", "TWS:2382:STOCK", "2382"),
        ("2881.TW", "富邦金", "TWS:2881:STOCK", "2881"),
        ("2882.TW", "國泰金", "TWS:2882:STOCK", "2882"),
        ("2891.TW", "中信金", "TWS:2891:STOCK", "2891"),
        ("2412.TW", "中華電", "TWS:2412:STOCK", "2412"),
        ("3711.TW", "日月光投控", "TWS:3711:STOCK", "3711"),
    ]),
    "hk": dict(title="港股龍頭", index="eq_hsi", items=[
        ("0700.HK", "騰訊控股", "HKS:00700:STOCK", None),
        ("9988.HK", "阿里巴巴", "HKS:09988:STOCK", None),
        ("1299.HK", "友邦保險", "HKS:01299:STOCK", None),
        ("0005.HK", "匯豐控股", "HKS:00005:STOCK", None),
        ("0939.HK", "建設銀行", "HKS:00939:STOCK", None),
        ("1398.HK", "工商銀行", "HKS:01398:STOCK", None),
        ("3690.HK", "美團", "HKS:03690:STOCK", None),
        ("0941.HK", "中國移動", "HKS:00941:STOCK", None),
        ("1810.HK", "小米集團", "HKS:01810:STOCK", None),
        ("0388.HK", "香港交易所", "HKS:00388:STOCK", None),
    ]),
}

# 各國外匯存底（世界銀行年資料，含黃金）＋台灣（央行月資料，不含黃金）
RESERVE_COUNTRIES = [("CHN", "中國"), ("JPN", "日本"), ("USA", "美國"), ("EMU", "歐元區"), ("HKG", "香港")]
CURRENT_ACCOUNT_COUNTRIES = RESERVE_COUNTRIES

# 美國財政部 TIC：主要外國持有美債
TIC_HOLDERS = [("japan", "日本"), ("china", "中國大陸"), ("united kingdom", "英國"),
               ("taiwan", "台灣"), ("hong kong", "香港"), ("grand total", "外國合計")]

# 歷史危機區間（月份為概略區間）
EVENTS = [
    ("asia97", "亞洲金融風暴", "1997-07", "1998-01"),
    ("ltcm98", "俄羅斯違約／LTCM", "1998-08", "1998-10"),
    ("dotcom", "網路泡沫破裂", "2000-03", "2002-10"),
    ("gfc", "全球金融海嘯", "2007-10", "2009-02"),
    ("euro11", "歐債危機／美債降評", "2011-07", "2011-10"),
    ("china15", "中國股災／人民幣貶值", "2015-06", "2016-02"),
    ("q4_18", "升息＋貿易戰", "2018-10", "2018-12"),
    ("covid", "新冠疫情", "2020-02", "2020-03"),
    ("hike22", "通膨與暴力升息", "2022-01", "2022-10"),
]

# 關聯熱圖使用的核心標的
CORE_IDS = ["fx_dxy", "fx_usdtwd", "fx_usdjpy", "fx_usdcny", "fx_eurusd",
            "b_us3m", "b_us10y", "b_jp10y", "b_ust_long", "b_ig", "b_hy", "b_brk",
            "eq_spx", "eq_sox", "eq_hsi", "eq_twii",
            "c_gold", "c_copper", "c_brent", "c_maize", "c_soy", "v_vix"]

# 重點關聯配對：滾動相關＋領先落後
PAIRS = [
    ("eq_twii", "fx_usdtwd", "台股 × 美元/新台幣", "負相關代表外資匯入（台幣升值）與台股同步，是台灣熱錢最直接的指紋。"),
    ("eq_twii", "eq_sox", "台股 × 費城半導體", "台股權重高度集中半導體，這條線衡量台股是否只是費半的影子。"),
    ("eq_spx", "b_us10y", "美股 × 美10年殖利率變動", "正相關＝成長預期主導（股債反向）；轉負＝通膨／升息主導，股債同跌。"),
    ("eq_hsi", "fx_dxy", "恆生指數 × 美元指數", "美元走強時，資金是否撤出亞洲、港股承壓。"),
    ("fx_usdcny", "eq_hsi", "美元/人民幣 × 恆生指數", "人民幣貶值通常伴隨中港資產外流。"),
    ("c_gold", "fx_dxy", "黃金 × 美元指數", "傳統上負相關；相關轉弱代表央行買金等非美元因素主導。"),
    ("c_copper", "eq_spx", "銅 × 美股", "銅是實體景氣溫度計，與風險資產同向時代表景氣循環主導。"),
    ("fx_usdjpy", "eq_spx", "美元/日圓 × 美股", "日圓套利交易：日圓貶值（線上升）與美股同漲，平倉時一起跌。"),
    ("c_brent", "b_us10y", "布蘭特原油 × 美10年殖利率變動", "油價推升通膨預期，進而推升長天期殖利率。"),
    ("v_vix", "b_hy", "VIX × 高收益債", "恐慌上升時信用資產被拋售的程度。"),
    ("b_jp10y", "b_us10y", "日債 × 美債殖利率變動", "全球利率是否同步；日銀政策轉向時關係會斷裂。"),
    ("c_maize", "c_soy", "玉米 × 大豆", "同一塊農地的替代作物，也共同受生質燃料與天候影響。"),
    ("b_brk", "eq_spx", "波克夏 × 美股", "波克夏與大盤的連動，高現金部位時期往往相關下降。"),
]

# 資金風險偏好指數的組成：(鍵, 名稱, 計算方式, 方向, 說明)
COMPOSITE = [
    ("dollar", "美元強弱", "美元指數 6 個月對數變動", -1, "美元走強＝全球美元流動性收緊、資金回流美國"),
    ("fear", "市場恐慌", "VIX 月底水位", -1, "VIX 高＝避險需求上升"),
    ("carry", "日圓套利", "美元/日圓 3 個月對數變動", +1, "日圓走貶＝套利資金外流追逐高收益資產"),
    ("growth", "景氣實需", "銅/黃金比值 6 個月對數變動", +1, "銅相對黃金走強＝景氣擴張、實需資金進場"),
    ("credit", "信用胃納", "高收益債 − 投資級債 6 個月報酬差", +1, "高收益債跑贏＝市場願意承擔信用風險"),
    ("asia", "亞洲資金", "美元/新台幣 3 個月對數變動", -1, "台幣升值＝外資匯入亞洲"),
]
COMPOSITE_Z_WINDOW = 60
COMPOSITE_Z_MIN = 36

# 資金流向地圖使用的資產
FLOWMAP = [("eq_spx", "美股"), ("eq_ndx", "那斯達克"), ("eq_twii", "台股"), ("eq_hsi", "港股"),
           ("eq_n225", "日股"), ("eq_sse", "陸股"), ("b_ust_long", "美長債"), ("b_ig", "投資級債"),
           ("b_hy", "高收益債"), ("c_gold", "黃金"), ("c_copper", "銅"), ("c_brent", "原油"),
           ("ci_agri", "農產品"), ("fx_dxy", "美元")]

# 已知資料缺口（誠實揭露在儀表板上）：(項目, 原因, 替代做法)
GAPS = [
    ("台灣／美國前 10 大公司債", "逐券殖利率與價格沒有免費的 30 年歷史來源",
     "以 VWESX／VWEHX（1995 起）、LQD／HYG 公司債基金總報酬代理"),
    ("台灣 10 年期公債殖利率", "櫃買中心與央行未提供可程式化的長歷史序列",
     "以央行重貼現率代表台灣利率循環；每日頁籤追蹤鉅亨網債市新聞"),
    ("港股公司現金流", "港交所財報無免費結構化 API", "僅列美股（SEC EDGAR）與台股（FinMind）"),
    ("台灣經常帳", "央行國際收支表無公開 JSON 端點", "以美債持有（TIC）與外匯存底觀察台灣對外資金"),
    ("鉅亨網期貨／VIX／公債報價", "鉅亨網公開報價 API 不提供這些商品代碼",
     "每日頁籤的商品、VIX、美債殖利率改用 Yahoo Finance，日債用日本財務省，並逐列標註來源"),
    ("匯率月資料口徑", "30 年匯率取自央行（月平均），美元指數與股債為月底值",
     "月均值會平滑波動，關聯係數略為低估；每日頁籤使用鉅亨網收盤"),
]

# ── 單一標的線圖（日／週／月／年）──
# 日線保留年數、週線保留年數；月線與年線從 1995 起。收盤價已含分割調整、不含股息。
DETAIL_KEEP_YEARS = {"d": 3, "w": 15}
# series id → (來源, 代碼, 單位)。沒列在這裡的序列（央行、世界銀行、比值）只提供月／年。
# 注意期貨的報價單位和世界銀行月均價不同（例：玉米 美分/蒲式耳 vs 美元/公噸）。
DETAIL = {
    "fx_dxy": ("yahoo", "DX-Y.NYB", "指數"), "fx_usdtwd": ("yahoo", "TWD=X", "TWD"),
    "fx_usdjpy": ("yahoo", "JPY=X", "JPY"), "fx_usdcny": ("yahoo", "CNY=X", "CNY"),
    "fx_eurusd": ("yahoo", "EURUSD=X", "USD"),
    "b_us3m": ("yahoo", "^IRX", "%"), "b_us5y": ("yahoo", "^FVX", "%"), "b_us10y": ("yahoo", "^TNX", "%"),
    "b_us30y": ("yahoo", "^TYX", "%"), "b_jp10y": ("mof", "10Y", "%"),
    "b_ust_long": ("yahoo", "VUSTX", "USD"), "b_ig": ("yahoo", "VWESX", "USD"), "b_hy": ("yahoo", "VWEHX", "USD"),
    "b_lqd": ("yahoo", "LQD", "USD"), "b_hyg": ("yahoo", "HYG", "USD"), "b_brk": ("yahoo", "BRK-A", "USD"),
    "eq_spx": ("yahoo", "^GSPC", "點"), "eq_ndx": ("yahoo", "^NDX", "點"), "eq_dji": ("yahoo", "^DJI", "點"),
    "eq_sox": ("yahoo", "^SOX", "點"), "eq_hsi": ("yahoo", "^HSI", "點"), "eq_twii": ("yahoo", "^TWII", "點"),
    "eq_n225": ("yahoo", "^N225", "點"), "eq_sse": ("yahoo", "000001.SS", "點"),
    "c_gold": ("yahoo", "GC=F", "$/oz"), "c_silver": ("yahoo", "SI=F", "$/oz"), "c_platinum": ("yahoo", "PL=F", "$/oz"),
    "c_copper": ("yahoo", "HG=F", "$/lb"), "c_alu": ("yahoo", "ALI=F", "$/mt"),
    "c_brent": ("yahoo", "BZ=F", "$/bbl"), "c_wti": ("yahoo", "CL=F", "$/bbl"), "c_natgas": ("yahoo", "NG=F", "$/mmbtu"),
    "c_maize": ("yahoo", "ZC=F", "美分/蒲式耳"), "c_soy": ("yahoo", "ZS=F", "美分/蒲式耳"),
    "c_wheat": ("yahoo", "KE=F", "美分/蒲式耳"),
    "v_vix": ("yahoo", "^VIX", "點"),
}

# ── 每日（鉅亨網）──
SECTIONS = [("fx", "匯市"), ("bond", "債市"), ("equity", "股市"), ("commodity", "商品"),
            ("flow", "資金流"), ("vol", "VIX")]

CNYES_NEWS_CATEGORIES = [
    ("headline", "頭條"), ("tw_stock", "台股"), ("us_stock", "美股"), ("wd_stock", "國際股"),
    ("hk_stock", "港股"), ("cn_stock", "陸股"), ("forex", "外匯"), ("future", "期貨"),
    ("energy", "能源"), ("wd_macro", "國際政經"), ("tw_macro", "台灣政經"),
]

# 每日報價：(section, 分組, 來源, 代碼, 名稱, 單位)  單位 pct＝漲跌幅% / bp＝殖利率變動
DAILY_QUOTES = [
    ("fx", "匯率", "cnyes", "GI:DXY:INDEX", "美元指數", "pct"),
    ("fx", "匯率", "cnyes", "FX:USDTWD:FOREX", "美元/新台幣", "pct"),
    ("fx", "匯率", "cnyes", "FX:USDJPY:FOREX", "美元/日圓", "pct"),
    ("fx", "匯率", "cnyes", "FX:USDCNY:FOREX", "美元/人民幣", "pct"),
    ("fx", "匯率", "cnyes", "FX:USDCNH:FOREX", "美元/離岸人民幣", "pct"),
    ("fx", "匯率", "cnyes", "FX:EURUSD:FOREX", "歐元/美元", "pct"),
    ("bond", "殖利率", "yahoo", "^IRX", "美 3 個月", "bp"),
    ("bond", "殖利率", "yahoo", "^FVX", "美 5 年", "bp"),
    ("bond", "殖利率", "yahoo", "^TNX", "美 10 年", "bp"),
    ("bond", "殖利率", "yahoo", "^TYX", "美 30 年", "bp"),
    ("bond", "殖利率", "mof", "JGB10Y", "日 10 年", "bp"),
    ("bond", "公司債與波克夏", "yahoo", "LQD", "投資級債 LQD", "pct"),
    ("bond", "公司債與波克夏", "yahoo", "HYG", "高收益債 HYG", "pct"),
    ("bond", "公司債與波克夏", "cnyes", "USS:BRK.B:STOCK", "波克夏 B", "pct"),
    ("equity", "指數", "cnyes", "TWS:TSE01:INDEX", "台灣加權", "pct"),
    ("equity", "指數", "cnyes", "GI:INX:INDEX", "S&P 500", "pct"),
    ("equity", "指數", "cnyes", "GI:IXIC:INDEX", "那斯達克", "pct"),
    ("equity", "指數", "cnyes", "GI:DJI:INDEX", "道瓊", "pct"),
    ("equity", "指數", "cnyes", "GI:SOX:INDEX", "費城半導體", "pct"),
    ("equity", "指數", "cnyes", "GI:HSI:INDEX", "恆生指數", "pct"),
    ("equity", "指數", "cnyes", "GI:SSEC:INDEX", "上證指數", "pct"),
    ("commodity", "貴金屬", "yahoo", "GC=F", "黃金期貨", "pct"),
    ("commodity", "貴金屬", "yahoo", "SI=F", "白銀期貨", "pct"),
    ("commodity", "工業金屬", "yahoo", "HG=F", "銅期貨", "pct"),
    ("commodity", "能源", "yahoo", "CL=F", "WTI 原油", "pct"),
    ("commodity", "能源", "yahoo", "BZ=F", "布蘭特原油", "pct"),
    ("commodity", "能源", "yahoo", "NG=F", "天然氣", "pct"),
    ("commodity", "農產品", "yahoo", "ZC=F", "玉米期貨", "pct"),
    ("commodity", "農產品", "yahoo", "ZS=F", "大豆期貨", "pct"),
    ("vol", "波動", "yahoo", "^VIX", "VIX", "pct"),
]
for _mkt, _cfg in LEADERS.items():
    for _y, _name, _cnyes, _ in _cfg["items"]:
        DAILY_QUOTES.append(("equity", _cfg["title"], "cnyes", _cnyes, _name, "pct"))

MOVER_Z = 2.0            # 日變動超過近 60 日標準差的倍數 → 標註異常波動
HIGHLIGHT_SCORE = 7      # 新聞重點門檻（2026-09-15 實測：門檻 4 會標出 47% 的新聞，7 約 22%）
DAILY_KEEP_IN_HTML = 30  # 儀表板內嵌最近幾天的每日資料

# 新聞重點關鍵字（標題命中權重 2、鉅亨關鍵字命中權重 1）
SECTION_KEYWORDS = {
    # 不放單獨的「美元」：新聞金額（「105 美元」「20 億美元」）會大量誤中
    "fx": ["美元指數", "美元走", "美元升", "美元貶", "美元攀", "美元避險", "強勢美元", "弱勢美元", "新台幣", "台幣",
           "日圓", "日元", "人民幣", "歐元", "匯率", "匯市", "外匯存底", "外匯", "升值", "貶值", "韓元", "港幣"],
    "bond": ["殖利率", "公債", "國債", "美債", "日債", "公司債", "債券", "債市", "利率", "降息",
             "升息", "聯準會", "Fed", "FOMC", "鮑爾", "央行", "日銀", "歐洲央行", "波克夏", "巴菲特",
             "信用利差", "垃圾債", "高收益債", "投資級"],
    "equity": ["台股", "美股", "港股", "陸股", "恆指", "恆生", "費半", "那斯達克", "標普", "道瓊",
               "台積電", "輝達", "蘋果", "微軟", "博通", "特斯拉", "騰訊", "阿里", "鴻海", "聯發科",
               "Meta", "Alphabet", "亞馬遜", "小米", "美團", "匯豐", "權值股", "龍頭"],
    "commodity": ["黃金", "金價", "白銀", "貴金屬", "銅價", "原油", "油價", "布蘭特", "WTI", "天然氣",
                  "OPEC", "玉米", "大豆", "小麥", "農產品", "原物料", "鐵礦", "大宗商品"],
    "flow": ["現金流", "資金流", "外資", "熱錢", "匯出", "匯入", "淨流入", "淨流出", "資金行情",
             "主權基金", "外匯存底", "持有美債", "拋售", "撤資", "避險", "套利交易", "流動性", "QT", "QE"],
    "vol": ["VIX", "恐慌指數", "恐慌", "波動率", "崩跌", "暴跌", "重挫", "熔斷", "黑天鵝"],
}
