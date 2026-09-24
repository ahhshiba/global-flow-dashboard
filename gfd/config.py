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

# ── 傳導鏈（事件 → 第二層 → 第三層…）──
# 每個節點都要有可判定的觸發條件，程式才能量測「上游成立後，下游多久成立、值多少」。
# op：chg1/chg3/chg6/chg12＝過去 N 個月變動（價格用對數報酬 %、殖利率用 bp）；level＝原始水準。
# 這些鏈是先寫下經濟學上的假說，再用 1995 年以來的月資料檢定，不是從資料挖出來的規則。
CHAIN_WITHIN = 6      # 下游條件要在上游成立後幾個月內出現才算「傳導到了」
CHAIN_HORIZONS = [1, 3, 6, 12]
CHAINS = [
    dict(id="dollar", name="美元緊縮鏈", tab="chains",
         thesis="美元是全球融資貨幣。美元走強＝離岸美元變貴，先壓非美股市，再壓以美元計價的原物料，最後透過需求走弱回到債市。",
         nodes=[
             dict(id="dxy", sid="fx_dxy", op="chg6", cmp=">=", thr=3.0,
                  label="美元指數 6 個月升值 ≥ 3%", why="美元走強代表全球美元流動性收緊"),
             dict(id="hsi", sid="eq_hsi", op="chg3", cmp="<=", thr=-3.0,
                  label="恆生指數 3 個月跌 ≥ 3%", why="港股是離岸美元最敏感的亞洲市場"),
             dict(id="copper", sid="c_copper", op="chg3", cmp="<=", thr=-3.0,
                  label="銅價 3 個月跌 ≥ 3%", why="以美元計價的工業金屬跟著變貴、需求轉弱"),
             dict(id="agri", sid="ci_agri", op="chg6", cmp="<=", thr=-3.0,
                  label="農產品指數 6 個月下跌", why="傳導到民生物價，通常最慢"),
             dict(id="ust", sid="b_ust_long", op="chg6", cmp=">=", thr=3.0,
                  label="美國長債 6 個月上漲 ≥ 3%", why="需求轉弱、通膨預期下滑後，長債受惠"),
         ]),
    dict(id="carry", name="日圓套利平倉鏈", tab="chains",
         thesis="日圓是低利融資貨幣。日債殖利率上行使借日圓成本升高，套利部位被迫平倉，先賣掉流動性最好的美股，再擴散到半導體與台股。",
         nodes=[
             dict(id="jgb", sid="b_jp10y", op="chg6", cmp=">=", thr=20.0,
                  label="日本 10 年殖利率 6 個月上升 ≥ 20bp", why="日圓融資成本上升是套利交易的壓力來源"),
             dict(id="jpy", sid="fx_usdjpy", op="chg3", cmp="<=", thr=-2.0,
                  label="日圓 3 個月升值 ≥ 2%", why="平倉要買回日圓，日圓走升本身就是平倉的痕跡"),
             dict(id="spx", sid="eq_spx", op="chg3", cmp="<=", thr=-3.0,
                  label="S&P 500 3 個月跌 ≥ 3%", why="先賣流動性最好的資產"),
             dict(id="sox", sid="eq_sox", op="chg3", cmp="<=", thr=-5.0,
                  label="費城半導體 3 個月跌 ≥ 5%", why="高 beta 的科技股跌得更深"),
             dict(id="twii", sid="eq_twii", op="chg3", cmp="<=", thr=-5.0,
                  label="台股 3 個月跌 ≥ 5%", why="台股權重集中半導體，是這條鏈的末端"),
         ]),
    dict(id="inflation", name="通膨傳導鏈", tab="chains",
         thesis="油價是通膨預期最直接的輸入。油價急漲推升長天期殖利率，折現率上升先壓縮成長股評價，曲線趨平，避險需求轉向黃金。",
         nodes=[
             dict(id="oil", sid="c_brent", op="chg6", cmp=">=", thr=20.0,
                  label="布蘭特原油 6 個月漲 ≥ 20%", why="能源是通膨預期的主要輸入"),
             dict(id="ust10", sid="b_us10y", op="chg6", cmp=">=", thr=40.0,
                  label="美 10 年殖利率 6 個月上升 ≥ 40bp", why="通膨預期推升長率"),
             dict(id="ndx", sid="eq_ndx", op="chg3", cmp="<=", thr=-3.0,
                  label="那斯達克 100 3 個月下跌 ≥ 3%", why="折現率上升對長天期現金流的成長股傷害最大"),
             dict(id="curve", sid="d_curve", op="level", cmp="<=", thr=0.5,
                  label="美債 10 年−3 個月利差 ≤ 0.5 個百分點", why="升息壓過成長預期時曲線趨平甚至倒掛"),
             dict(id="gold", sid="c_gold", op="chg6", cmp=">=", thr=5.0,
                  label="黃金 6 個月漲 ≥ 5%", why="實質利率見頂後避險與抗通膨需求轉向黃金"),
         ]),
    dict(id="cycle", name="景氣擴張鏈", tab="chains",
         thesis="銅相對黃金走強代表實體需求回來。半導體是製造業景氣的前緣，接著是台股，外資匯入推升台幣，最後風險偏好擴散到信用債。",
         nodes=[
             dict(id="cuau", sid="d_cu_au", op="chg6", cmp=">=", thr=10.0,
                  label="銅/黃金比 6 個月上升 ≥ 10%", why="實體需求相對避險需求轉強"),
             dict(id="sox", sid="eq_sox", op="chg3", cmp=">=", thr=8.0,
                  label="費城半導體 3 個月漲 ≥ 8%", why="半導體是製造業循環的前緣"),
             dict(id="twii", sid="eq_twii", op="chg3", cmp=">=", thr=5.0,
                  label="台股 3 個月漲 ≥ 5%", why="台股跟著半導體循環走"),
             dict(id="twd", sid="fx_usdtwd", op="chg3", cmp="<=", thr=-1.0,
                  label="新台幣 3 個月升值 ≥ 1%", why="外資買超需要先換成台幣"),
             dict(id="hy", sid="b_hy", op="chg6", cmp=">=", thr=2.0,
                  label="高收益債 6 個月漲 ≥ 2%", why="風險偏好擴散到信用市場是循環的後段"),
         ]),
    dict(id="panic", name="恐慌反轉鏈", tab="chains",
         thesis="恐慌指數衝高時信用市場先失血，股市補跌；這條鏈要檢驗的是「相對低點買入」這個說法在歷史上值多少、又要承受多深的逆行。",
         nodes=[
             dict(id="vix", sid="v_vix", op="level", cmp=">=", thr=30.0,
                  label="VIX 月底 ≥ 30", why="恐慌指數站上 30 是壓力事件的客觀門檻"),
             dict(id="hy", sid="b_hy", op="chg3", cmp="<=", thr=-3.0,
                  label="高收益債 3 個月跌 ≥ 3%", why="信用市場先反映流動性壓力"),
             dict(id="spx", sid="eq_spx", op="chg3", cmp="<=", thr=-8.0,
                  label="S&P 500 3 個月跌 ≥ 8%", why="股市補跌，常是事件的中後段"),
             dict(id="twii", sid="eq_twii", op="chg3", cmp="<=", thr=-10.0,
                  label="台股 3 個月跌 ≥ 10%", why="台股在全球恐慌中的跌幅通常更大"),
         ]),
    dict(id="china", name="中國與人民幣鏈", tab="chains",
         thesis="人民幣走貶通常伴隨中國內需與信用轉弱，先反映在港股，再到工業金屬，最後透過供應鏈影響台韓電子。",
         nodes=[
             dict(id="cny", sid="fx_usdcny", op="chg6", cmp=">=", thr=2.0,
                  label="人民幣 6 個月貶值 ≥ 2%", why="匯率是中國政策與內需壓力的出口"),
             dict(id="hsi", sid="eq_hsi", op="chg3", cmp="<=", thr=-5.0,
                  label="恆生指數 3 個月跌 ≥ 5%", why="港股是中國資產的離岸定價"),
             dict(id="metals", sid="ci_metals", op="chg3", cmp="<=", thr=-3.0,
                  label="金屬與礦產指數 3 個月下跌", why="中國是工業金屬的最大需求方"),
             dict(id="sox", sid="eq_sox", op="chg3", cmp="<=", thr=-5.0,
                  label="費城半導體 3 個月跌 ≥ 5%", why="透過供應鏈與終端需求傳導到電子"),
         ]),
]

# ── 事件衝擊鏈（真實事件 → 兩週／一個月／兩個月的逐層傳導）──
# 這裡用「日線」而不是月資料，因為兩週的尺度用月資料做不出來。
CASCADE_WINDOWS = [10, 21, 42]     # 交易日：約兩週、一個月、兩個月
CASCADE_PRE = 10                   # 事件前先看幾個交易日（判斷有沒有提前反映）
CASCADE_REACT_SIGMA = 2.0          # 首次反應門檻：累積變動 ≥ 2σ×√天數（σ 為事件前 60 日的日波動）
CASCADE_MAX_DAYS = 42

CASCADE_START = "1979-06-01"      # 1980 年初的事件也要有 60 個交易日的事前波動可算

# 五層：從上游原物料一路到資金面。id 為 Yahoo 代碼。
CASCADE_UNIVERSE = [
    ("CL=F", "WTI 原油", "upstream"), ("NG=F", "天然氣", "upstream"), ("GC=F", "黃金", "upstream"),
    ("SI=F", "白銀", "upstream"),
    ("HG=F", "銅", "upstream"), ("KE=F", "小麥", "upstream"), ("ZC=F", "玉米", "upstream"), ("ZS=F", "大豆", "upstream"),
    ("XLE", "美國能源股", "resources"), ("XOP", "油氣探勘股", "resources"), ("XLB", "美國原物料股", "resources"),
    ("IGE", "天然資源股", "resources"), ("GDX", "金礦股", "resources"), ("^GSPTSE", "加拿大 TSX（資源國）", "resources"),
    ("XLI", "美國工業股", "industry"), ("IYT", "美國運輸股", "industry"), ("2603.TW", "長榮", "industry"),
    ("2609.TW", "陽明", "industry"), ("2002.TW", "中鋼", "industry"), ("1301.TW", "台塑", "industry"),
    ("6505.TW", "台塑化", "industry"),
    ("XLY", "非必需消費股", "downstream"), ("XLP", "必需消費股", "downstream"), ("XLK", "美國科技股", "downstream"),
    ("^SOX", "費城半導體", "downstream"), ("2330.TW", "台積電", "downstream"), ("^TWII", "台灣加權", "downstream"),
    ("^GSPC", "S&P 500", "downstream"), ("^NDX", "那斯達克 100", "downstream"), ("^HSI", "恆生指數", "downstream"),
    ("^N225", "日經 225", "downstream"), ("^GDAXI", "德國 DAX", "downstream"), ("^FTSE", "英國富時 100", "downstream"),
    ("^TNX", "美 10 年殖利率", "money"), ("^IRX", "美 3 個月利率", "money"), ("DX-Y.NYB", "美元指數", "money"),
    ("JPY=X", "美元/日圓", "money"), ("TWD=X", "美元/新台幣", "money"), ("TLT", "美國長債 ETF", "money"),
    ("HYG", "高收益債 ETF", "money"), ("XLU", "公用事業股", "money"), ("XLF", "美國金融股", "money"),
    ("^VIX", "VIX", "money"),
]
# ETF 與期貨大多 1999–2000 年才有日線。更早的事件用「代理序列」接在前面：
# 只取代理序列在主序列開始日之前的報酬，接點以主序列第一天的價位對齊，所以接點之後完全是原序列。
# 種類：yahoo＝Yahoo 代碼（共同基金用還原淨值，避免配息日假跌）、eia＝美國能源資訊署現貨日價、
# lbma＝倫敦金銀定盤價、twse＝證交所每日加權指數（1990 起）。
CASCADE_PROXY = {
    "CL=F": ("eia", "RWTC", "WTI 現貨價（EIA）"),
    "GC=F": ("lbma", "gold_pm", "倫敦黃金下午定盤價"),
    "SI=F": ("lbma", "silver", "倫敦白銀定盤價"),
    "XLE": ("yahoo", "FSENX", "Fidelity 能源產業基金"),
    "XLB": ("yahoo", "FSDPX", "Fidelity 原物料產業基金"),
    "GDX": ("yahoo", "^XAU", "費城金銀礦業指數"),
    "IYT": ("yahoo", "FSRFX", "Fidelity 運輸產業基金"),
    "XLY": ("yahoo", "FSRPX", "Fidelity 零售產業基金"),
    "XLP": ("yahoo", "FDFAX", "Fidelity 必需消費產業基金"),
    "XLK": ("yahoo", "FSPTX", "Fidelity 科技產業基金"),
    "^SOX": ("yahoo", "FSELX", "Fidelity 半導體產業基金"),
    "^NDX": ("yahoo", "^IXIC", "那斯達克綜合指數"),
    "^TWII": ("twse", "TAIEX", "證交所每日加權指數"),
    "TLT": ("yahoo", "VUSTX", "Vanguard 長期公債基金"),
    "HYG": ("yahoo", "VWEHX", "Vanguard 高收益公司債基金"),
    "XLU": ("yahoo", "FSUTX", "Fidelity 公用事業產業基金"),
    "XLF": ("yahoo", "FIDSX", "Fidelity 金融產業基金"),
}
CASCADE_LAYERS = [("upstream", "上游：原物料與能源價格"), ("resources", "中游：能源與資源股"),
                  ("industry", "中游：工業、運輸與石化鋼鐵"), ("downstream", "下游：終端需求與科技股"),
                  ("money", "資金面：利率、匯率、避險")]
CASCADE_RATE_IDS = {"^TNX", "^IRX", "^VIX"}   # 這幾個用變動點數／百分點表示，不是報酬
# 同一分類裡，兩個事件相隔不到這麼多天（日曆日）時，分類彙總只算較早那一個，
# 否則同一段價格路徑會被算兩次。單一事件頁仍然會列出，並標出與哪些事件的視窗重疊。
CASCADE_DEDUP_DAYS = 30
CASCADE_NULL_ROUNDS = 20          # 虛無校準：把事件日隨機移位重跑幾輪
CASCADE_NULL_SPAN = 1095           # 移位範圍：原日期前後三年（保留大致相同的年代與資料涵蓋）
CASCADE_OVERLAP_DAYS = 60          # 約 42 個交易日：在這個距離內的事件，兩個月視窗會互相污染
# 「類型比較」矩陣的欄：各層各挑代表，事件類型之間才比得起來
CASCADE_COMPARE = ["CL=F", "GC=F", "XLE", "GDX", "^GSPC", "^NDX", "^SOX", "^TWII", "^N225", "^HSI",
                   "XLP", "XLU", "TLT", "HYG", "^TNX", "DX-Y.NYB", "^VIX"]

# 真實事件清單：日期為公開已知的事件發生日（approx=True 者為區間起點的概略日）。
# 事件發生在美股收盤後或週末時，日期填「消息公布日」，基準自動取那之前最後一個收盤。
# 這是研究用清單，可自行增刪；分類用來做跨事件彙總。
SHOCK_EVENTS = [
    # 戰爭與地緣衝突
    dict(id="kuwait90", date="1990-08-02", cat="geo", name="伊拉克入侵科威特", note="兩國合計約占全球 7% 原油供給，油價兩個月內翻倍"),
    dict(id="storm91", date="1991-01-17", cat="geo", name="沙漠風暴空襲開始", note="開戰當天油價單日崩跌約三分之一、美股大漲——「開戰即利空出盡」的經典案例"),
    dict(id="ussr91", date="1991-08-19", cat="geo", name="蘇聯八一九政變", note="三天後失敗，年底蘇聯解體"),
    dict(id="taiwan95", date="1995-07-21", cat="geo", name="第一次台海飛彈試射", note="7/21–26 於彭佳嶼外海試射"),
    dict(id="taiwan96", date="1996-03-08", cat="geo", name="台海飛彈危機（首次總統直選前）", note="向基隆、高雄外海試射；美國派兩個航艦戰鬥群"),
    dict(id="sep11", date="2001-09-11", cat="geo", name="美國 911 恐怖攻擊", note="美股停市四個交易日，重啟後補跌"),
    dict(id="iraq03", date="2003-03-20", cat="geo", name="美軍入侵伊拉克", note="開戰前油價已大漲，開戰後回落"),
    dict(id="libya11", date="2011-02-17", cat="geo", name="利比亞內戰爆發", approx=True, note="阿拉伯之春擴散，日產能中斷"),
    dict(id="crimea14", date="2014-03-01", cat="geo", name="俄羅斯出兵克里米亞", note="俄國國會 3/1（週六）授權出兵，3/3 全球股市下跌"),
    dict(id="ukraine22", date="2022-02-24", cat="geo", name="俄羅斯全面入侵烏克蘭", note="能源與穀物同時受衝擊"),
    dict(id="pelosi22", date="2022-08-02", cat="geo", name="裴洛西訪台", note="解放軍 8/4 起環台軍演"),
    dict(id="israel23", date="2023-10-07", cat="geo", name="哈瑪斯攻擊以色列", note="中東地緣風險升高"),
    dict(id="redsea24", date="2024-01-12", cat="geo", name="紅海航運危機升溫", approx=True, note="繞道好望角，運費與運期上升"),
    dict(id="iran25", date="2025-06-13", cat="geo", name="以色列空襲伊朗", note="6/22 美國轟炸伊朗核設施，6/24 停火"),
    # 能源與商品供給衝擊
    dict(id="katrina", date="2005-08-29", cat="energy", name="卡崔娜颶風登陸", note="墨西哥灣油氣生產與煉廠中斷"),
    dict(id="macondo", date="2010-04-20", cat="energy", name="深水地平線漏油", note="墨西哥灣鑽探禁令"),
    dict(id="fukushima", date="2011-03-11", cat="energy", name="東日本大地震與福島事故", note="核電停擺，日本轉向 LNG"),
    dict(id="opec14", date="2014-11-27", cat="energy", name="OPEC 拒絕減產", note="維也納會議決定維持產量（美國感恩節休市），油價一年半內腰斬再腰斬"),
    dict(id="abqaiq", date="2019-09-14", cat="energy", name="沙烏地 Abqaiq 油設施遇襲", note="一度中斷全球約 5% 供給"),
    dict(id="opec20", date="2020-03-06", cat="energy", name="OPEC+ 維也納會談破局",
         note="當日減產協議談判破裂；沙俄價格戰 3/8 開打、油價 3/9 單日崩跌，本表以談判破局日為事件日"),
    dict(id="negoil20", date="2020-04-20", cat="energy", name="WTI 期貨跌成負值", note="5 月合約結算 −37.63 美元，儲油空間耗盡"),
    dict(id="suez21", date="2021-03-23", cat="energy", name="長賜輪卡住蘇伊士運河", note="3/29 脫困，全球貨櫃航運延誤"),
    dict(id="colonial", date="2021-05-07", cat="energy", name="Colonial 油管遭勒索軟體攻擊", note="美東成品油供應中斷"),
    dict(id="eugas21", date="2021-09-01", cat="energy", name="歐洲天然氣危機升溫", approx=True, note="庫存偏低與供給收緊"),
    dict(id="nordstream", date="2022-09-26", cat="energy", name="北溪管線遭破壞", note="歐洲天然氣供給結構性改變"),
    # 金融危機與信用事件
    dict(id="conti84", date="1984-05-09", cat="crisis", name="伊利諾大陸銀行擠兌", approx=True, note="當時美國第七大銀行，聯邦存保公司接管，「大到不能倒」一詞由此而來"),
    dict(id="barings95", date="1995-02-26", cat="crisis", name="霸菱銀行倒閉", note="交易員李森押注日經期貨虧損（阪神地震後日經重挫），週日宣布破產"),
    dict(id="ltcm98", date="1998-09-23", cat="crisis", name="長期資本管理公司紓困", note="紐約聯邦準備銀行召集 14 家銀行注資 36 億美元"),
    dict(id="bnp07", date="2007-08-09", cat="crisis", name="法國巴黎銀行凍結次貸基金", note="信用緊縮起點，歐洲央行當天緊急注資"),
    dict(id="bear08", date="2008-03-14", cat="crisis", name="貝爾斯登獲緊急融資", note="聯準會經摩根大通緊急融資，兩天後以每股 2 美元賤賣"),
    dict(id="lehman", date="2008-09-15", cat="crisis", name="雷曼兄弟破產", note="全球信用凍結"),
    dict(id="greece10", date="2010-04-27", cat="crisis", name="希臘主權債遭降為垃圾級", note="標普同日調降葡萄牙，歐債危機擴散"),
    dict(id="usdowngrade", date="2011-08-05", cat="crisis", name="標普調降美國主權評等", note="全球股市重挫"),
    dict(id="evergrande21", date="2021-09-20", cat="crisis", name="恆大違約疑慮", note="恆指重挫、全球股市跟跌（中國中秋休市）"),
    dict(id="svb", date="2023-03-10", cat="crisis", name="矽谷銀行倒閉", note="區域銀行擠兌與降息預期"),
    # 市場崩盤與流動性事件（事件本身就是市場的急跌，看的是它怎麼傳到其他市場）
    dict(id="silver80", date="1980-03-27", cat="crash", name="白銀星期四", note="韓特兄弟囤積白銀的保證金追繳失敗，銀價單日崩跌"),
    dict(id="crash87", date="1987-10-19", cat="crash", name="黑色星期一", note="道瓊單日 −22.6%，程式交易與投資組合保險踩踏"),
    dict(id="hk97", date="1997-10-23", cat="crash", name="國際炒家狙擊港幣", note="金管局抽緊銀根捍衛聯繫匯率，恆指單日 −10.4%；10/27 美股首次熔斷"),
    dict(id="china07", date="2007-02-27", cat="crash", name="上證單日重挫 8.8%", note="「二二七」全球股市連鎖下跌"),
    dict(id="flash10", date="2010-05-06", cat="crash", name="美股閃電崩盤", note="道瓊盤中 20 分鐘內跌近千點後收回大半"),
    dict(id="china15", date="2015-08-24", cat="crash", name="中國黑色星期一", note="人民幣匯改兩週後，上證單日 −8.5%、美股開盤道瓊跌逾千點"),
    dict(id="volmag18", date="2018-02-05", cat="crash", name="波動率崩盤（Volmageddon）", note="VIX 單日翻倍，做空波動率商品清算"),
    dict(id="carry24", date="2024-08-05", cat="crash", name="日圓套利交易平倉", note="7/31 日銀升息＋8/2 美國就業數據疲弱，日經單日 −12.4%"),
    # 央行轉向與利率衝擊
    dict(id="boj89", date="1989-12-25", cat="cb", name="日銀三重野升息", note="新總裁上任一週即升息至 4.25%；日經四天後見歷史高點，泡沫破裂"),
    dict(id="fed94", date="1994-02-04", cat="cb", name="聯準會五年來首次升息", note="「債券大屠殺」起點，一年內升息 300bp"),
    dict(id="fedcut01", date="2001-01-03", cat="cb", name="聯準會會議間緊急降息 50bp", note="網路泡沫破裂後的第一刀"),
    dict(id="draghi12", date="2012-07-26", cat="cb", name="德拉吉「不惜一切代價」", note="歐債危機轉折點"),
    dict(id="taper13", date="2013-05-22", cat="cb", name="柏南奇暗示縮減購債", note="「縮減恐慌」：美債殖利率與新興市場資金外流"),
    dict(id="liftoff15", date="2015-12-16", cat="cb", name="聯準會海嘯後首次升息", note="結束七年零利率"),
    dict(id="bojnirp16", date="2016-01-29", cat="cb", name="日銀宣布負利率", note="隨後日圓不跌反升"),
    dict(id="pivot19", date="2019-01-04", cat="cb", name="鮑爾轉向「耐心」", note="2018 年底美股急跌後，聯準會暗示暫停升息"),
    dict(id="jackson22", date="2022-08-26", cat="cb", name="鮑爾傑克森洞「會帶來痛苦」", note="八分鐘演講，S&P 當天 −3.4%"),
    dict(id="boj_ycc", date="2022-12-20", cat="cb", name="日本央行放寬 YCC 區間", note="日圓急升、全球利率跳動"),
    dict(id="pivot23", date="2023-12-13", cat="cb", name="聯準會點陣圖轉向降息", note="預告隔年降息三次"),
    dict(id="cut24", date="2024-09-18", cat="cb", name="聯準會首次降息 50bp", note="本輪降息循環開始"),
    # 匯率與國際收支危機
    dict(id="mexico82", date="1982-08-12", cat="fx", name="墨西哥宣布無力償債", note="拉美債務危機爆發；美股同月見底展開長多"),
    dict(id="plaza85", date="1985-09-22", cat="fx", name="廣場協議", note="五國聯手讓美元貶值（週日簽署），日圓兩年內升值近一倍"),
    dict(id="erm92", date="1992-09-16", cat="fx", name="英鎊退出歐洲匯率機制", note="「黑色星期三」，索羅斯放空英鎊"),
    dict(id="peso94", date="1994-12-20", cat="fx", name="墨西哥披索貶值", note="龍舌蘭危機"),
    dict(id="baht97", date="1997-07-02", cat="fx", name="泰銖放棄釘住美元", note="亞洲金融風暴起點"),
    dict(id="russia98", date="1998-08-17", cat="fx", name="俄羅斯違約與盧布貶值", note="一個月後引爆長期資本管理公司危機"),
    dict(id="snb15", date="2015-01-15", cat="fx", name="瑞士央行取消歐元兌瑞郎下限", note="瑞郎盤中升值近 30%"),
    dict(id="cny815", date="2015-08-11", cat="fx", name="人民幣 811 匯改", note="中間價機制改革，人民幣一次性貶值"),
    dict(id="lira18", date="2018-08-10", cat="fx", name="土耳其里拉崩跌", note="美國加倍課徵土耳其鋼鋁關稅，新興市場連鎖賣壓"),
    dict(id="ukbudget22", date="2022-09-23", cat="fx", name="英國迷你預算", note="英鎊創歷史新低、英債殖利率暴衝，英格蘭銀行緊急購債"),
    # 貿易與政策衝擊
    dict(id="brexit", date="2016-06-23", cat="policy", name="英國脫歐公投", note="隔日英鎊與全球股市重挫"),
    dict(id="s301_18", date="2018-03-22", cat="policy", name="川普簽署對中 301 關稅備忘錄", note="美中貿易戰開端"),
    dict(id="tariff18", date="2018-07-06", cat="policy", name="美國對中首波關稅生效", note="340 億美元商品加徵 25%"),
    dict(id="trade19", date="2019-05-05", cat="policy", name="川普宣布對中關稅調高至 25%", note="週日推文，談判破裂"),
    dict(id="liberation25", date="2025-04-03", cat="policy", name="「解放日」對等關稅", note="4/2 美股盤後宣布；4/9 宣布暫緩 90 天"),
    # 選舉與政局
    dict(id="tw04", date="2004-03-20", cat="election", name="三一九槍擊與總統大選", note="3/19 下午槍擊（台股已收盤），3/22 開盤重挫"),
    dict(id="us16", date="2016-11-09", cat="election", name="川普首次當選", note="開票結果在台北時間 11/9 白天揭曉，基準為 11/8 收盤"),
    dict(id="us20", date="2020-11-04", cat="election", name="拜登當選（開票日）", note="基準為 11/3 投票日收盤"),
    dict(id="us24", date="2024-11-06", cat="election", name="川普再度當選", note="基準為 11/5 投票日收盤"),
    # 科技與產業週期
    dict(id="huawei19", date="2019-05-16", cat="tech", name="華為列入實體清單", note="美國商務部 5/15 盤後宣布"),
    dict(id="chips22", date="2022-10-07", cat="tech", name="美國對中先進晶片出口管制", note="限制先進製程設備與 AI 晶片出口"),
    dict(id="chatgpt22", date="2022-11-30", cat="tech", name="ChatGPT 上線", note="生成式 AI 行情起點（當時市場幾乎沒反應）"),
    dict(id="nvda23", date="2023-05-25", cat="tech", name="輝達財測大幅上修", note="5/24 盤後公布，隔日股價 +24%"),
    dict(id="deepseek25", date="2025-01-27", cat="tech", name="DeepSeek 衝擊", note="R1 於 1/20 發布，1/27 AI 股重挫（輝達單日 −17%）；台股農曆年休市至 2/3"),
    # 疫情
    dict(id="sars03", date="2003-03-12", cat="pandemic", name="WHO 發布 SARS 全球警訊", note="八天後美軍入侵伊拉克，兩者視窗重疊"),
    dict(id="h1n1_09", date="2009-04-24", cat="pandemic", name="H1N1 新型流感爆發", note="墨西哥與美國通報疫情（週五），6 月 WHO 宣布大流行"),
    dict(id="covid_early20", date="2020-01-20", cat="pandemic", name="中國證實新冠人傳人", note="美股 1/20 休市；市場一個月後才真正反應"),
    dict(id="covid", date="2020-03-11", cat="pandemic", name="WHO 宣布新冠為全球大流行", note="流動性危機與封城"),
    # 天災與事故
    dict(id="chernobyl86", date="1986-04-28", cat="disaster", name="車諾比核災曝光", note="4/26（週六）事故，4/28 瑞典偵測到輻射後蘇聯承認"),
    dict(id="kobe95", date="1995-01-17", cat="disaster", name="阪神大地震", note="日本開盤前發生；日經隨後重挫並拖垮霸菱銀行"),
    dict(id="quake921", date="1999-09-21", cat="disaster", name="九二一大地震", note="凌晨發生，台股停市數日；科學園區停電影響晶圓代工"),
    dict(id="texas21", date="2021-02-15", cat="disaster", name="德州寒流大停電", approx=True, note="2/13–17 冬季風暴，天然氣井與電廠凍結"),
    dict(id="hualien24", date="2024-04-03", cat="disaster", name="花蓮強震", note="台股開盤前發生，晶圓廠短暫疏散"),
]
SHOCK_CATS = [("geo", "戰爭與地緣衝突"), ("energy", "能源與商品供給衝擊"), ("crisis", "金融危機與信用事件"),
              ("crash", "市場崩盤與流動性事件"), ("cb", "央行轉向與利率衝擊"), ("fx", "匯率與國際收支危機"),
              ("policy", "貿易與政策衝擊"), ("election", "選舉與政局"), ("tech", "科技與產業週期"),
              ("pandemic", "疫情"), ("disaster", "天災與事故")]

# ── 訊號劇本（事件前兆 × 事件後全資產期望值）──
# 期望值一律看「相對該資產自己的無條件基準」的超額，並要通過三道關卡才標為穩健。
PLAYBOOK_SPLIT = "2012-01"      # 樣本外切點：前半段找到的規律，後半段要同方向
PLAYBOOK_MIN_EPISODES = 8       # 獨立事件數下限
PLAYBOOK_MAX_P = 0.10           # 列表用的寬鬆 p 值上限
PLAYBOOK_STRICT_P = 0.02        # 標為穩健所需的嚴格 p 值（位移檢定的下限約 0.005）
PLAYBOOK_HORIZONS = [3, 6, 12]
PLAYBOOK_TOP = 12               # 每個期間保留的排行長度（另外保留最差 3 名）
# 事件後要排名的資產（涵蓋股、債、匯、商品；殖利率以 bp 呈現，不與報酬混排）
PLAYBOOK_UNIVERSE = [
    "eq_spx", "eq_ndx", "eq_dji", "eq_sox", "eq_hsi", "eq_twii", "eq_n225", "eq_sse",
    "b_ust_long", "b_ig", "b_hy", "b_brk",
    "c_gold", "c_silver", "c_platinum", "c_copper", "c_alu", "c_brent", "c_wti", "c_natgas",
    "c_maize", "c_soy", "c_wheat", "ci_energy", "ci_agri", "ci_metals", "ci_precious",
    "fx_dxy", "fx_usdtwd", "fx_usdjpy", "fx_usdcny", "fx_eurusd",
    "b_us10y", "b_us3m", "b_jp10y", "d_curve", "v_vix",
]
# 這些是觀察指標，不是能直接買進持有的標的（VIX 要用期貨或選擇權、殖利率與利差要用債券部位表達）。
# 事件後它們常出現「機械性」的強烈反應（例如股市大跌後 VIX 必然先衝高再回落），
# 放在同一張排行榜會把真正可投資的標的擠掉，所以分開呈現。
PLAYBOOK_OBSERVE_ONLY = ["v_vix", "d_curve", "b_us10y", "b_us3m", "b_jp10y"]

# 除了傳導鏈的節點以外，另外納入這些常被討論的訊號（格式同鏈節點）
PLAYBOOK_EXTRA_TRIGGERS = [
    dict(id="curve_inv", sid="d_curve", op="level", cmp="<=", thr=0.0,
         label="美債殖利率曲線倒掛（10 年 < 3 個月）", why="歷史上數次領先衰退，但領先時間長短差很多"),
    dict(id="vix_25", sid="v_vix", op="level", cmp=">=", thr=25.0,
         label="VIX 月底 ≥ 25", why="比 30 寬的壓力門檻，事件較多"),
    dict(id="dxy_down", sid="fx_dxy", op="chg6", cmp="<=", thr=-3.0,
         label="美元指數 6 個月貶值 ≥ 3%", why="美元走弱時資金通常流向非美資產"),
    dict(id="twd_weak", sid="fx_usdtwd", op="chg3", cmp=">=", thr=2.0,
         label="新台幣 3 個月貶值 ≥ 2%", why="外資撤出台灣時，匯率通常先動"),
    dict(id="spx_dd", sid="eq_spx", op="chg12", cmp="<=", thr=-10.0,
         label="S&P 500 12 個月跌 ≥ 10%", why="年度級別的空頭，檢驗長線進場點"),
    dict(id="gold_run", sid="c_gold", op="chg6", cmp=">=", thr=15.0,
         label="黃金 6 個月漲 ≥ 15%", why="避險或通膨預期急升的痕跡"),
    dict(id="rates_up", sid="b_us10y", op="chg6", cmp=">=", thr=80.0,
         label="美 10 年殖利率 6 個月上升 ≥ 80bp", why="利率衝擊，對長天期資產最不利"),
    dict(id="rates_down", sid="b_us10y", op="chg6", cmp="<=", thr=-80.0,
         label="美 10 年殖利率 6 個月下降 ≥ 80bp", why="降息預期或避險買盤湧入"),
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
