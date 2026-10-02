"""沙盤推演：把傳導鏈、訊號劇本、事件衝擊接起來，回答「現在這些訊號亮著，接下來可能怎麼走、哪些標的期望值較好」。

四步：
1. 現況：訊號劇本的觸發條件中，哪些現在亮著（同一套定義與「最新一筆資料」口徑，數字和訊號劇本檢視一致）。
2. 推演：每條傳導鏈從目前成立的層往下看，還沒成立的下一層在 6 個月內跟著成立的歷史機率（對照平常）。
3. 期望值：每個可投資標的的「之後 h 個月報酬減掉自己平常的平均」，對全部訊號的 0/1 指標做 ridge 迴歸
   （λ 事先設定，不看樣本外結果挑）。同時亮著、彼此重疊的訊號會分攤效果，不重複計算；目前亮燈訊號的係數加總＝模型期望超額。
   區間用 12 個月一塊的區塊自助法。
4. 樣本外檢查：走步回測，每個月只用當時已經知道結果的資料估計，買期望值最高的幾個，和全體平均比；
   同時量「校準斜率」＝樣本外實際超額大約是模型值的幾倍，頁面上的「校準後」就是模型值乘上它。

5. 更深一層：鏈的每個未成立層給 6／12 個月內成立的比例；照鏈現在的狀態看剩下的層 12 個月內全部走完的比例；
   跨鏈的「下一波」＝和現在相似（亮燈重疊 ≥ SIM_THR）的月份，之後 6 個月哪些沒亮的訊號比平常更常亮起。
6. 對答案：和現在最像的歷史時點，每個只用「當時已知」的資料重跑 3～5，對照之後實際發生的事（_cases）。

原因說明不用 ridge 係數（同時亮著的訊號會互相分攤，單看係數會出現「日圓升值讓原油漲」這種看不出道理的拆法），
改列每個亮燈訊號「單獨」的歷史：用訊號劇本同一套口徑（獨立事件起點、事件後中位數減平常中位數、位移檢定 p），
兩個分頁的數字可以互相對照。

月均價序列（世界銀行、央行月均匯率）的「之後報酬」由 chains.forward 從下個月的均價算起，
走步回測估計時也多退一個月（結果要在決策當下已知）；沒有這一步，當月均價包含過去半個月，會讓回測偷看未來。

限制（頁面上照實寫）：訊號與門檻是事後設計的，回測只排除了「估計」上的偷看，排除不了「設計」上的後見之明；
另外比較過不只一種組合方式，挑選本身也是偷看，實際效果可能比回測差。報酬是對數報酬、沒有交易成本與稅；
全部是歷史統計，不是投資建議。
"""
import numpy as np

from . import chains as CH
from . import config as C
from . import playbook as PB

BLOCK = 12          # 區塊自助法的區塊長度（月）
PERM = 500          # 置換檢定次數
SIMILAR_TOP = 5     # 列出最像現在的幾個歷史時點
SIM_THR = 0.25      # 「類似案例」：亮燈訊號的 Jaccard 相似度門檻
CASES_MAX = 12      # 對答案最多看幾個類似時點
SEED = 20261002


def _key(nd):
    return (nd["sid"], nd["op"], nd["cmp"], nd["thr"])


def _masks(g, series, trig, end):
    out = []
    for t in trig:
        vals = CH.transform(g, t["sid"], t["op"], series[t["sid"]]["kind"])
        out.append(CH.trigger_mask(vals, t["cmp"], t["thr"], end))
    return np.array(out).T            # (months, K) bool


def _run_length(mask, cur):
    """目前這一段已經連續亮了幾個月（含當月）。"""
    n = 0
    while cur - n >= 0 and mask[cur - n]:
        n += 1
    return n


def _ridge(Xr, yr, lam):
    mu = float(yr.mean())
    K = Xr.shape[1]
    beta = np.linalg.solve(Xr.T @ Xr + lam * np.eye(K), Xr.T @ (yr - mu))
    return mu, beta


def _spread(preds, real, k):
    top = np.argsort(-preds)[:k]
    return float(real[top].mean() - real.mean())


def _walk_forward(X, F, Mom, h, end, start, lam, k, lags):
    """每個決策月 T 只用 t ≤ T−h（結果已知）的資料；用累加和，不必每期重算。

    同時算三種排名做對照：ridge（本頁採用）、單一訊號平均（每個亮燈訊號單獨的條件超額、收縮後取平均）、6 個月動能。
    """
    n, A = F.shape
    K = X.shape[1]
    Xf = X.astype(float)
    pr = np.full((n, A), np.nan)
    pa = np.full((n, A), np.nan)
    mus = np.full((n, A), np.nan)
    for a in range(A):
        y = F[:, a]
        v = np.isfinite(y)
        v[end - h - lags[a] + 1:] = False           # forward 已經是 NaN；這裡再保險一次
        yz = np.where(v, y, 0.0)
        xv = Xf * v[:, None]
        Sxx = np.cumsum(xv[:, :, None] * Xf[:, None, :], axis=0)
        Sxy = np.cumsum(xv * yz[:, None], axis=0)
        Sx = np.cumsum(xv, axis=0)
        Sy = np.cumsum(yz)
        Sn = np.cumsum(v.astype(float))
        for T in range(start, end - h + 1):
            i = T - h - lags[a]                         # 第 i 列的結果在 T 月底以前已經知道（月均價多退一個月）
            if i < 0 or Sn[i] < 60 or not np.isfinite(F[T, a]):
                continue
            mu = Sy[i] / Sn[i]
            b = Sxy[i] - mu * Sx[i]                     # Σ x·(y − μ)
            pr[T, a] = Xf[T] @ np.linalg.solve(Sxx[i] + lam * np.eye(K), b)
            act = Xf[T] > 0
            pa[T, a] = float(np.mean(b[act] / (Sx[i][act] + lam))) if act.any() else 0.0
            mus[T, a] = mu
    periods = []
    for T in range(start, end - h + 1):
        ok = np.isfinite(pr[T]) & np.isfinite(F[T])
        if ok.sum() < 10:
            continue
        r = F[T, ok]
        mom = np.where(np.isfinite(Mom[T, ok]), Mom[T, ok], 0.0)
        periods.append(dict(T=T, real=r, pr=pr[T, ok], pa=pa[T, ok], own=r - mus[T, ok],
                            ridge=_spread(pr[T, ok], r, k), avg=_spread(pa[T, ok], r, k), mom=_spread(mom, r, k)))
    return periods


def _offsets(periods, h, key, rng, with_p=True):
    """重疊的期間不能當獨立樣本：每 h 個月取一期（不重疊），每個起點各算一次，再看範圍。"""
    rows = []
    for off in range(h):
        sub = periods[off::h]
        if len(sub) < 8:
            continue
        s = np.array([p[key] for p in sub])
        pval = None
        if with_p:
            k = C.SCENARIO_TOPK
            null = [np.mean([float(p["real"][rng.permutation(len(p["real"]))[:k]].mean() - p["real"].mean()) for p in sub])
                    for _ in range(PERM)]
            pval = float((np.sum(np.array(null) >= s.mean()) + 1) / (PERM + 1))
        rows.append(dict(offset=off, n=len(sub), mean=CH.r(s.mean()), hit=CH.r(100 * (s > 0).mean(), 0), p=CH.r(pval, 3)))
    return rows


def _verdict(rows):
    if not rows:
        return "樣本不足"
    means = [r["mean"] for r in rows if r["mean"] is not None]
    ps = [r["p"] for r in rows if r["p"] is not None]
    if all(m > 0 for m in means) and ps and max(ps) <= 0.10:
        return "樣本外有效"
    if np.mean(means) > 0 and sum(m > 0 for m in means) > len(means) / 2:
        return "時好時壞"
    return "樣本外無效"


def _summ(periods, key):
    s = np.array([p[key] for p in periods])
    return dict(mean=CH.r(s.mean()) if s.size else None, hit=CH.r(100 * (s > 0).mean(), 0) if s.size else None)



def _node_prob(cm_i, cm_j, fin_j, upto, W):
    """上游 i 亮著、j 當下沒亮的月份，j 在 W 個月內亮起的比例，對照「j 當下沒亮的任何月份」。
    只用結果在 upto 以前已經知道的月份（t ≤ upto − W），所以也能拿來做「當時」的推演。"""
    last = upto - W
    if last < 0:
        return None
    ts = [t for t in range(last + 1) if cm_i[t] and not cm_j[t] and fin_j[t]]
    hits = [bool(cm_j[t + 1:t + 1 + W].any()) for t in ts]
    base = [bool(cm_j[t + 1:t + 1 + W].any()) for t in range(last + 1) if fin_j[t] and not cm_j[t]]
    waits = [int(np.argmax(cm_j[t + 1:t + 1 + W])) + 1 for t, hh in zip(ts, hits) if hh]
    m = np.zeros(len(cm_i), bool)
    m[ts] = True
    return dict(prob=CH.r(100 * np.mean(hits), 0) if hits else None, base=CH.r(100 * np.mean(base), 0) if base else None,
                wait=CH.r(float(np.median(waits)), 1) if waits else None, n_months=len(ts), n_episodes=len(CH.episodes(m)))


def _chain_state(cmasks, finite, on, rest, upto, H):
    """照這條鏈現在的狀態（亮著的層都亮、rest 都沒亮）的歷史月份：rest 各層與「全部走完」在 H 個月內的比例。"""
    last = upto - H
    ts = [t for t in range(max(0, last + 1))
          if all(cmasks[i][t] for i in range(len(on)) if on[i]) and all((not cmasks[j][t]) and finite[j][t] for j in rest)]
    if not ts:
        return dict(n_months=0, n_episodes=0, all=None, each={})
    each = {}
    for j in rest:
        each[str(j)] = CH.r(100 * np.mean([bool(cmasks[j][t + 1:t + 1 + H].any()) for t in ts]), 0)
    allp = CH.r(100 * np.mean([all(cmasks[j][t + 1:t + 1 + H].any() for j in rest) for t in ts]), 0)
    m = np.zeros(len(cmasks[0]), bool)
    m[ts] = True
    return dict(n_months=len(ts), n_episodes=len(CH.episodes(m)), all=allp, each=each, horizon=H,
                starts=[int(t) for t in CH.episodes(m)][-6:])


def _jaccard(X, x):
    inter = X.astype(float) @ x
    union = X.sum(axis=1) + x.sum() - inter
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(union > 0, inter / union, 0.0)


def _next_wave(X, x_state, upto, W, trig, thr=SIM_THR, min_eps=4, top=8):
    """和 x_state 相似（Jaccard ≥ thr）的歷史月份裡，之後 W 個月哪些「當下沒亮」的訊號亮起來的比例比平常高。
    只用結果在 upto 以前已知的月份。"""
    last = upto - W
    if last < 12 or x_state.sum() == 0:
        return []
    jac = _jaccard(X[:last + 1], x_state)
    sim = np.where(jac >= thr)[0]
    out = []
    for k in range(X.shape[1]):
        if x_state[k]:
            continue
        ts = [t for t in sim if not X[t, k]]
        if not ts:
            continue
        m = np.zeros(X.shape[0], bool)
        m[ts] = True
        eps = len(CH.episodes(m))
        if eps < min_eps:
            continue
        p = float(np.mean([X[t + 1:t + 1 + W, k].any() for t in ts]))
        b = float(np.mean([X[t + 1:t + 1 + W, k].any() for t in range(last + 1) if not X[t, k]]))
        if p - b >= 0.10:
            out.append(dict(id=trig[k]["id"], k=k, label=trig[k]["label"], source=trig[k]["source"], why=trig[k]["why"],
                            prob=CH.r(100 * p, 0), base=CH.r(100 * b, 0), n_months=len(ts), n_episodes=eps, _lift=p - b, _base=b))
    out.sort(key=lambda w: w["_lift"], reverse=True)          # 用沒四捨五入的差距排序
    return out[:top]


def _fit_predict(X, F, lags, T, h, lam, min_rows=60):
    """只用 T 月底以前已知結果的列（t ≤ T − h − lag）估 ridge，回傳每個資產在 X[T] 下的模型值與平常平均。"""
    A = F.shape[1]
    preds, mus = np.full(A, np.nan), np.full(A, np.nan)
    for a in range(A):
        i = T - h - lags[a]
        if i < 0:
            continue
        y = F[:i + 1, a]
        ok = np.isfinite(y)
        if ok.sum() < min_rows:
            continue
        mu, beta = _ridge(X[:i + 1][ok].astype(float), y[ok], lam)
        preds[a], mus[a] = float(X[T].astype(float) @ beta), mu
    return preds, mus



def _episode_spans(mask, upto, gap=CH.GAP):
    """照 chains.episodes 的合併規則（間隔 ≤ gap 個月算同一段）切段，回傳 [(起點, 最後一個亮著的月)]，只看 t ≤ upto。"""
    idx = np.where(mask[:upto + 1])[0]
    if not idx.size:
        return []
    spans, s0, prev = [], int(idx[0]), int(idx[0])
    for t in idx[1:]:
        t = int(t)
        if t - prev > gap:
            spans.append((s0, prev))
            s0 = t
        prev = t
    spans.append((s0, prev))
    return spans


def _signal_age(mask, cur, upto, months):
    """這個訊號目前這一段（間隔 ≤ 3 個月的短暫中斷算同一段）已經亮了幾個月，
    和歷史上已結束的各段比：中位數長度、最長一段、撐到這麼久的比例。"""
    spans = _episode_spans(mask, upto)
    here = next((sp for sp in spans if sp[0] <= cur <= sp[1]), None)
    if here is None:
        return None
    age = cur - here[0] + 1
    done = [b - a + 1 for a, b in spans if b < here[0]]
    return dict(age=age, since=months[here[0]], n_done=len(done),
                median=CH.r(float(np.median(done)), 0) if done else None,
                longest=int(max(done)) if done else None,
                share_longer=CH.r(100 * float(np.mean([d >= age for d in done])), 0) if done else None)


def _ends_within(mask, t, W, gap=CH.GAP):
    """這一層在 (t, t+W] 內「熄掉」：照段的規則，連續熄超過 gap 個月才算這一段結束。"""
    m = mask[t + 1:t + 1 + W + gap]
    run = 0
    for i, v in enumerate(m):
        run = 0 if v else run + 1
        if run > gap and i - run + 1 < W:      # 熄掉的那一段從 W 個月內開始
            return True
    return False


def _chain_frontier(cmasks, finite, on, below, term_f6, upto, H=12, W=6):
    """從這條鏈目前最深的已成立層往下看：歷史上那一層亮著、它下面的層（below）都還沒亮的月份（t ≤ upto−H），
    之後 H 個月 below 再亮幾層的分布；W 個月內最深那層熄掉（照段的規則，連續熄超過 3 個月）又沒往下傳＝斷鏈；
    末端標的 6 個月報酬依「W 個月內有沒有往下傳」分組。中間被跳過、還沒亮的上層不算在內。"""
    deepest = max(i for i in range(len(on)) if on[i])
    last = upto - H
    ts = [t for t in range(max(0, last + 1)) if cmasks[deepest][t] and all((not cmasks[j][t]) and finite[j][t] for j in below)]
    if not ts:
        return dict(n_months=0, n_episodes=0)
    rest = below
    nxt = below[0]                                   # 緊接的下一層
    depth = [int(sum(bool(cmasks[j][t + 1:t + 1 + H].any()) for j in rest)) for t in ts]
    dist = {str(d): CH.r(100 * float(np.mean([x == d for x in depth])), 0) for d in range(len(rest) + 1)}
    prop_w = [bool(cmasks[nxt][t + 1:t + 1 + W].any()) for t in ts]
    off_w = [_ends_within(cmasks[deepest], t, W) for t in ts]
    broke = [o and not pr for o, pr in zip(off_w, prop_w)]
    # 末端標的依「下一層 W 個月內有沒有亮」分組。下一層本身就是末端時不分（末端的報酬和它自己的觸發條件是同一件事，分了等於同義反覆）
    circular = nxt == len(cmasks) - 1
    went = [] if circular else [term_f6[t] for t, pr in zip(ts, prop_w) if pr and np.isfinite(term_f6[t])]
    stay = [] if circular else [term_f6[t] for t, pr in zip(ts, prop_w) if not pr and np.isfinite(term_f6[t])]
    m = np.zeros(len(cmasks[0]), bool)
    m[ts] = True
    return dict(n_months=len(ts), n_episodes=len(CH.episodes(m)), deepest=deepest, rest=rest, horizon=H,
                depth=dist, mean_depth=CH.r(float(np.mean(depth)), 1),
                broke=CH.r(100 * float(np.mean(broke)), 0), prop=CH.r(100 * float(np.mean(prop_w)), 0), circular=circular,
                term_if=dict(n=len(went), median=CH.r(float(np.median(went))) if went else None),
                term_else=dict(n=len(stay), median=CH.r(float(np.median(stay))) if stay else None))


def _cases(X, x_now, Fs, lags, assets, series, trig, chain_masks, end, months, lam, W, out_h, act_k, ev_list=()):
    """對答案：最像現在的歷史時點（Jaccard ≥ SIM_THR，彼此至少隔 12 個月，結果已經知道），
    在每個時點只用「當時已知」的資料重跑：期望值排名、傳導鏈下一層、下一波訊號；再對照之後實際發生的事。"""
    H_MAX = 12
    jac = _jaccard(X, x_now)
    jac[end - H_MAX + 1:] = 0
    picked = []
    for t in np.argsort(-jac):
        if jac[t] < SIM_THR or len(picked) >= CASES_MAX:
            break
        if any(abs(int(t) - u) < 12 for u in picked):
            continue
        picked.append(int(t))
    picked.sort()
    k5 = C.SCENARIO_TOPK
    cases, layer_scores, wave_hits, wave_base = [], [], [], []
    model_stats = {h: [] for h in (3, 6)}
    today_stats = {h: [] for h in (3, 6)}
    pools = {("model", h): [] for h in (3, 6)}       # 每個案例當時可選的標的報酬（置換檢定用：隨機挑 5 個）
    pools.update({("today", h): [] for h in (3, 6)})
    for T in picked:
        rec = dict(m=months[T], jaccard=CH.r(jac[T]), active=[trig[k]["label"] for k in range(len(trig)) if X[T, k]],
                   shared=[trig[k]["label"] for k in act_k if X[T, k]], model={}, today={})
        for h in (3, 6):
            F = Fs[h]
            preds, mus = _fit_predict(X, F, lags, T, h, lam)
            ok = np.isfinite(preds) & np.isfinite(F[T])
            if ok.sum() < 10:
                rec["model"][str(h)] = dict(ok=False, reason="當時的資料不夠估模型（至少要 60 個月）")
            else:
                idx = np.where(ok)[0]
                order = idx[np.argsort(-preds[idx])]
                allmean = float(F[T, idx].mean())
                top, bot = order[:k5], order[-k5:][::-1]
                sp = float(F[T, top].mean() - allmean)
                ls = float(F[T, top].mean() - F[T, bot].mean())
                pick = lambda ix: [dict(name=series[assets[a]]["name"], ev=CH.r(preds[a]), real=CH.r(F[T, a] - allmean)) for a in ix]
                rec["model"][str(h)] = dict(ok=True, top=pick(top), bottom=pick(bot), spread=CH.r(sp), ls=CH.r(ls),
                                            hit=bool(sp > 0), n=int(ok.sum()))
                model_stats[h].append(sp)
                pools[("model", h)].append(F[T, idx])
            # 今天的前 5／後 5 名，在這個類似時點之後的實際表現（樣本內：今天的模型用到了這段資料，只是對照）
            name_to_a = {series[s]["name"]: a for a, s in enumerate(assets)}
            cur = out_h[str(h)]
            tt = [name_to_a[r["name"]] for r in cur[:k5] if np.isfinite(F[T, name_to_a[r["name"]]])]
            bb = [name_to_a[r["name"]] for r in cur[-k5:] if np.isfinite(F[T, name_to_a[r["name"]]])]
            fin_all = np.isfinite(F[T])
            if tt and fin_all.sum() >= 10:
                am = float(F[T, fin_all].mean())
                rec["today"][str(h)] = dict(top=CH.r(float(F[T, tt].mean()) - am), bottom=CH.r(float(F[T, bb].mean()) - am) if bb else None)
                today_stats[h].append(float(F[T, tt].mean()) - am)
                pools[("today", h)].append((F[T, fin_all], len(tt)))
        # 傳導鏈：當時沒亮、上游亮著的層，當時推估的 6 個月機率 vs 之後實際有沒有亮
        layers = []
        for chain in C.CHAINS:
            cmasks, finite = chain_masks[chain["id"]]
            on = [bool(cm[T]) for cm in cmasks]
            for j in range(len(on)):
                ups = [i for i in range(j) if on[i]]
                if on[j] or not ups or not finite[j][T]:
                    continue
                r6 = _node_prob(cmasks[ups[-1]], cmasks[j], finite[j], T, W)
                if not r6 or r6["prob"] is None or r6["base"] is None or r6["n_episodes"] < 3:
                    continue
                actual = bool(cmasks[j][T + 1:T + 1 + W].any())
                layers.append(dict(chain=chain["name"], label=chain["nodes"][j]["label"], prob=r6["prob"], base=r6["base"],
                                   n=r6["n_episodes"], actual=actual))
                layer_scores.append((r6["prob"] / 100, r6["base"] / 100, actual))
        rec["layers"] = layers
        # 下一波訊號：當時推估最可能亮起的幾個，之後 6 個月有沒有亮
        wv = _next_wave(X, X[T].astype(float), T, W, trig, top=5)
        for w in wv:
            w["actual"] = bool(X[T + 1:T + 1 + W, w["k"]].any())
            wave_hits.append(w["actual"])
            wave_base.append(w["_base"])
        rec["wave"] = [{k: v for k, v in w.items() if k not in ("k", "why", "source", "_lift", "_base")} for w in wv]
        # 這個案例的故事：之後一年發生的事件、各鏈實際走到第幾層、6 個月實際最好與最差的標的（都是事後資料，只做對照）
        m_end = months[min(T + 12, len(months) - 1)]
        rec["events_after"] = ([dict(date=d, name=n, cat=c) for d, n, c in ev_list if months[T] < d[:7] <= m_end][:8]
                               if ev_list else None)      # 沒有事件資料時是 None，前端不要寫成「沒有事件」
        reached = []
        for chain in C.CHAINS:
            cmasks, finite = chain_masks[chain["id"]]
            on_T = [bool(cm[T]) for cm in cmasks]
            if not any(on_T):
                continue
            rest_T = [j for j in range(len(on_T)) if not on_T[j] and any(on_T[:j])]
            lit = [chain["nodes"][j]["label"] for j in rest_T if cmasks[j][T + 1:T + 13].any()]
            reached.append(dict(chain=chain["name"], on=int(sum(on_T)), of=len(on_T), rest=len(rest_T), lit=lit))
        rec["chains_after"] = reached
        F6 = Fs[6]
        fin6 = np.isfinite(F6[T])
        if fin6.sum() >= 10:
            am6 = float(F6[T, fin6].mean())
            order = np.argsort(-np.where(fin6, F6[T], -np.inf))
            best = [a for a in order if fin6[a]][:3]
            worst = [a for a in order[::-1] if fin6[a]][:3]
            rec["actual6"] = dict(best=[dict(name=series[assets[a]]["name"], v=CH.r(F6[T, a] - am6)) for a in best],
                                  worst=[dict(name=series[assets[a]]["name"], v=CH.r(F6[T, a] - am6)) for a in worst])
        cases.append(rec)

    rng = np.random.default_rng(SEED + 11)

    def perm_p(kind, h, obs):
        """每個案例隨機挑同樣多個標的，看平均差距 ≥ 實際的機率（單尾）。"""
        pool = pools[(kind, h)]
        if not pool:
            return None
        null = []
        for _ in range(2000):
            v = []
            for item in pool:
                vals, k = (item, k5) if kind == "model" else item
                v.append(float(vals[rng.permutation(len(vals))[:k]].mean() - vals.mean()))
            null.append(np.mean(v))
        return CH.r(float((np.sum(np.array(null) >= obs) + 1) / 2001), 3)

    def pb_tail(ps, k):
        """Poisson-binomial：每個預測有自己的平常比例，至少命中 k 個的機率（精確計算）。"""
        if not ps:
            return None
        dist = np.zeros(len(ps) + 1)
        dist[0] = 1.0
        for q in ps:
            dist[1:] = dist[1:] * (1 - q) + dist[:-1] * q
            dist[0] *= (1 - q)
        return CH.r(float(dist[k:].sum()), 3)

    def brier(rows, idx):
        return CH.r(float(np.mean([(r[idx] - (1.0 if r[2] else 0.0)) ** 2 for r in rows])), 3) if rows else None
    summ = dict(
        n=len(cases), threshold=SIM_THR,
        model={str(h): dict(n=len(v), hit=int(sum(x > 0 for x in v)), spread_mean=CH.r(float(np.mean(v))) if v else None,
                            p=perm_p("model", h, float(np.mean(v))) if v else None)
               for h, v in model_stats.items()},
        today={str(h): dict(n=len(v), hit=int(sum(x > 0 for x in v)), mean=CH.r(float(np.mean(v))) if v else None,
                            p=perm_p("today", h, float(np.mean(v))) if v else None)
               for h, v in today_stats.items()},
        layers=dict(n=len(layer_scores), happened=int(sum(r[2] for r in layer_scores)),
                    brier=brier(layer_scores, 0), brier_base=brier(layer_scores, 1),
                    pred_mean=CH.r(100 * float(np.mean([r[0] for r in layer_scores])), 0) if layer_scores else None,
                    base_mean=CH.r(100 * float(np.mean([r[1] for r in layer_scores])), 0) if layer_scores else None),
        wave=dict(n=len(wave_hits), hits=int(sum(wave_hits)),
                  base=CH.r(100 * float(np.mean(wave_base)), 0) if wave_base else None,
                  p=pb_tail(wave_base, int(sum(wave_hits))) if wave_base else None))
    lb = summ["layers"]
    lb["skill"] = CH.r(1 - lb["brier"] / lb["brier_base"], 2) if lb.get("brier") is not None and lb.get("brier_base") else None
    return cases, summ


def build(g, series, months, play, chain_block, cascade, log=print):
    end = g.end
    lam = C.SCENARIO_LAMBDA
    trig = PB._triggers(series)
    ids = [t["id"] for t in trig]
    pmap = {t["id"]: t for t in play["triggers"]}
    X = _masks(g, series, trig, end)
    K = len(trig)
    # 目前亮燈：直接用訊號劇本的判定（各序列最新一筆），兩個分頁的數字才會一致
    x_now = np.array([1.0 if pmap.get(i, {}).get("active") else 0.0 for i in ids])
    act_k = [k for k in range(K) if x_now[k]]
    active = []
    for k in act_k:
        t, p = trig[k], pmap[trig[k]["id"]]
        cur = months.index(p["current_at"]) if p.get("current_at") in months else end
        age = _signal_age(X[:, k], cur, end, months)
        blk6 = (p.get("assets") or {}).get("6") or {}
        pick = lambda rows, sign: [dict(name=r["name"], lift=r["lift"], n=r["n"], p=r["p"])
                                   for r in rows if r.get("investable") and r.get("p") is not None and r["p"] <= 0.10
                                   and np.sign(r["lift"] or 0) == sign][:3]
        active.append(dict(id=t["id"], label=t["label"], source=t["source"], why=t["why"], sid=t["sid"],
                           current=p.get("current"), current_at=p.get("current_at"),
                           run=_run_length(X[:, k], cur), episodes=p.get("episodes"), age=age,
                           best6=pick(blk6.get("top", []), 1), worst6=pick(blk6.get("bottom", []), -1)))
    active_ids = {a["id"] for a in active}
    assets = [s for s in C.PLAYBOOK_UNIVERSE if s in g.arr and s in series and s not in C.PLAYBOOK_OBSERVE_ONLY]
    start = months.index(C.SCENARIO_EVAL_START) if C.SCENARIO_EVAL_START in months else 120
    rng = np.random.default_rng(SEED)
    robust = play.get("robust", [])

    # 最像現在的歷史時點：亮燈組合的 Jaccard 相似度（每段只取最像的一個月，前後至少隔 6 個月）
    Xa = X.astype(float)
    inter = Xa @ x_now
    union = Xa.sum(axis=1) + x_now.sum() - inter
    with np.errstate(invalid="ignore", divide="ignore"):
        jac = np.where(union > 0, inter / union, 0.0)
    jac[end - max(C.PLAYBOOK_HORIZONS) + 1:] = 0     # 只列結果已經知道的時點（排除最近一年，那就是「現在」本身）
    similar, taken = [], []
    for t in np.argsort(-jac):
        if jac[t] <= 0 or len(similar) >= SIMILAR_TOP:
            break
        if any(abs(int(t) - u) < 6 for u in taken):
            continue
        taken.append(int(t))
        similar.append(dict(m=months[t], t=int(t), jaccard=CH.r(jac[t]),
                            shared=[trig[k]["label"] for k in act_k if X[t, k]]))

    # 事件衝擊：亮燈訊號 → 事件類型 → 各標的短期反應（日線事件研究）
    cats = {c["id"]: c for c in (cascade or {}).get("categories", [])}
    ev_types, by_sid_events = [], {}
    pmin = lambda r: min(r["p21"] if r["p21"] is not None else 1, r["p42"] if r["p42"] is not None else 1)
    for cat_id in sorted({c for a in active for c in C.SCENARIO_EVENT_TYPES.get(a["id"], [])}):
        cat = cats.get(cat_id)
        if not cat:
            continue
        rows = []
        for a in cat.get("assets", []):
            sid = C.SCENARIO_CASCADE_SID.get(a["id"])
            if not sid:
                continue
            row = dict(sid=sid, name=series.get(sid, {}).get("name", a["name"]), n=a.get("n"), half_day=a.get("half_day"),
                       excess21=a.get("excess21"), p21=a.get("p21"), agree21=a.get("agree21"),
                       excess42=a.get("excess42"), p42=a.get("p42"), agree42=a.get("agree42"), resp_rate=a.get("resp_rate"))
            rows.append(row)
            by_sid_events.setdefault(sid, []).append(dict(cat=cat_id, cat_name=cat["name"], **row))
        sig = sorted([r for r in rows if pmin(r) <= 0.10], key=pmin)
        recent = sorted([e for e in cascade["events"] if e["cat"] == cat_id], key=lambda e: e["date"])[-3:]
        ev_types.append(dict(id=cat_id, name=cat["name"], n=cat.get("n"),
                             from_=[a["label"] for a in active if cat_id in C.SCENARIO_EVENT_TYPES.get(a["id"], [])],
                             rows=sig[:8], recent=[dict(id=e["id"], name=e["name"], date=e["date"]) for e in recent]))

    # 期望值、原因、樣本外回測
    out_h, backtest, Fs = {}, {}, {}
    lags = [CH.lag_of(s) for s in assets]
    for h in C.PLAYBOOK_HORIZONS:
        F = np.vstack([CH.forward(g, s, h, series[s]["kind"]) for s in assets]).T
        Fs[h] = F
        Mom = np.vstack([CH.transform(g, s, "chg6", series[s]["kind"]) for s in assets]).T
        periods = _walk_forward(X, F, Mom, h, end, start, lam, C.SCENARIO_TOPK, lags)
        offs = _offsets(periods, h, "ridge", rng)
        verdict = _verdict(offs)
        cal = np.array([(p_, o_) for p in periods for p_, o_ in zip(p["pr"], p["own"])])
        slope = float(cal[:, 0] @ cal[:, 1] / (cal[:, 0] @ cal[:, 0])) if cal.size else None
        corr = float(np.corrcoef(cal[:, 0], cal[:, 1])[0, 1]) if cal.size else None
        use_cal = slope is not None and slope > 0 and verdict != "樣本外無效"
        backtest[str(h)] = dict(
            periods=len(periods), start=months[periods[0]["T"]] if periods else None,
            end=months[periods[-1]["T"]] if periods else None,
            ridge=dict(**_summ(periods, "ridge"), offsets=offs, verdict=verdict),
            avg=dict(**_summ(periods, "avg"), offsets=_offsets(periods, h, "avg", rng)),
            momentum=dict(**_summ(periods, "mom"), offsets=_offsets(periods, h, "mom", rng)),
            calibration=dict(slope=CH.r(slope), corr=CH.r(corr, 3), used=bool(use_cal)),
            n_assets=[min(len(p["real"]) for p in periods), max(len(p["real"]) for p in periods)] if periods else None,
            series=[dict(m=months[p["T"]], v=CH.r(p["ridge"])) for p in periods])
        b_avg = backtest[str(h)]["avg"]
        b_avg["verdict"] = _verdict(b_avg["offsets"])
        backtest[str(h)]["momentum"]["verdict"] = _verdict(backtest[str(h)]["momentum"]["offsets"])

        # 每個亮燈訊號單獨的歷史（訊號劇本同一套口徑），給「原因」用
        rows_all = np.arange(0, end - h + 1)
        uni = {}
        for k in act_k:
            starts = CH.episodes(X[:, k])
            ep_mask = np.zeros(len(months), bool)
            ep_mask[starts] = True
            pv = PB._shift_pvalues(ep_mask, F, end)
            uni[k] = (starts, pv)

        recs = []
        for a, sid in enumerate(assets):
            y = F[rows_all, a]
            ok = np.isfinite(y)
            if ok.sum() < 60:
                continue
            Xr = X[rows_all][ok].astype(float)
            yr = y[ok]
            mu, beta = _ridge(Xr, yr, lam)
            ev = float(x_now @ beta)
            # 區塊自助法：整塊 12 個月一起抽，保留報酬的自相關
            N = len(yr)
            nb = int(np.ceil(N / BLOCK))
            boots = []
            for _ in range(C.SCENARIO_BOOT):
                st = rng.integers(0, max(1, N - BLOCK + 1), size=nb)
                pos = np.concatenate([np.arange(b0, b0 + BLOCK) for b0 in st])[:N]
                boots.append(float(x_now @ _ridge(Xr[pos], yr[pos], lam)[1]))
            boots = np.array(boots)
            base_med = float(np.median(yr))
            evidence = []
            for k in act_k:
                starts, pv = uni[k]
                vals = [F[t, a] for t in starts if t <= end - h and np.isfinite(F[t, a])]
                if not vals:
                    continue
                lift = CH.r(float(np.median(vals))) - CH.r(base_med)    # 先各自四捨五入再相減，和訊號劇本完全一致
                evidence.append(dict(id=ids[k], label=trig[k]["label"], source=trig[k]["source"], why=trig[k]["why"],
                                     n=len(vals), lift=CH.r(lift), hit=CH.r(100 * np.mean(np.array(vals) > base_med), 0),
                                     p=CH.r(float(pv[a]), 3) if np.isfinite(pv[a]) else None, beta=CH.r(beta[k])))
            evidence.sort(key=lambda e: abs(e["lift"] or 0), reverse=True)
            refs = [dict(trigger=r["trigger"], label=r["trigger_label"], lift=r["lift"], p=r["p"], n=r["n"],
                         conflict=bool(r.get("conflict")))
                    for r in robust if r["sid"] == sid and r["horizon"] == h and r["trigger"] in active_ids]
            past = [dict(m=s["m"], jaccard=s["jaccard"], own=CH.r(F[s["t"], a] - mu) if s["t"] <= end - h and np.isfinite(F[s["t"], a]) else None)
                    for s in similar]
            recs.append(dict(sid=sid, name=series[sid]["name"], ev=CH.r(ev), cal=CH.r(ev * slope) if use_cal else None,
                             base=CH.r(mu), lo=CH.r(np.percentile(boots, 10)), hi=CH.r(np.percentile(boots, 90)),
                             prob_pos=CH.r(100 * (boots > 0).mean(), 0), evidence=evidence, robust=refs,
                             events=by_sid_events.get(sid, []), past=past))
        recs.sort(key=lambda r: r["ev"], reverse=True)
        out_h[str(h)] = recs
        f2 = lambda v: "—" if v is None else f"{v:+.2f}"      # 樣本不足時這些是 None，不能讓記錄這一行把整個推演弄掛
        log(f"[scenario] {h} 個月：樣本外 {len(periods)} 期，前 {C.SCENARIO_TOPK} 名平均多 "
            f"{f2(backtest[str(h)]['ridge']['mean'])}%（各起點 {[o['mean'] for o in offs]}，p {[o['p'] for o in offs]}）"
            f"→ {verdict}；校準斜率 {f2(slope)}；對照 單一訊號平均 {f2(b_avg['mean'])}%、動能 {f2(backtest[str(h)]['momentum']['mean'])}%")

    # 傳導鏈推演：從目前成立的層往下，還沒成立的層在 6 個月與 12 個月內跟著成立的機率；
    # 再往下一層：照這條鏈「現在的狀態」（亮著的層都亮、其餘都沒亮），剩下的層 12 個月內全部走完的比例
    W = C.CHAIN_WITHIN
    key_to_id = {_key(t): t["id"] for t in trig}
    items = {c["id"]: c for c in chain_block.get("items", [])}
    chain_masks = {}
    paths = []
    for chain in C.CHAINS:
        it = items.get(chain["id"])
        cmasks, finite = [], []   # 每條鏈都算遮罩（對答案要用到所有鏈）
        for nd in chain["nodes"]:
            vals = CH.transform(g, nd["sid"], nd["op"], series[nd["sid"]]["kind"])
            cmasks.append(CH.trigger_mask(vals, nd["cmp"], nd["thr"], end))
            finite.append(np.isfinite(vals))
        chain_masks[chain["id"]] = (cmasks, finite)
        if not it or not it["active"]["count"]:
            continue
        on = [bool(n["triggered"]) for n in it["nodes"]]
        nodes = []
        for j, (nd, info) in enumerate(zip(chain["nodes"], it["nodes"])):
            tid = key_to_id.get(_key(nd))
            row = dict(id=nd["id"], sid=nd["sid"], label=nd["label"], name=info["name"], triggered=on[j],
                       current=info["current"], current_at=info["current_at"], trigger=tid)
            ups = [i for i in range(j) if on[i]]
            if not on[j] and ups:
                i = ups[-1]
                r6 = _node_prob(cmasks[i], cmasks[j], finite[j], end, W)
                r12 = _node_prob(cmasks[i], cmasks[j], finite[j], end, 12)
                row.update(after=it["nodes"][i]["label"], **(r6 or {}))
                if r12:
                    row.update(prob12=r12["prob"], base12=r12["base"], wait12=r12["wait"])
                # 如果這一層也成立：訊號劇本裡這個訊號的穩健組合（可投資標的）
                row["if_then"] = [dict(name=r["name"], sid=r["sid"], lift=r["lift"], horizon=r["horizon"], p=r["p"])
                                  for r in robust if r["trigger"] == tid][:4]
            nodes.append(row)
        rest = [j for j in range(len(on)) if not on[j] and any(on[:j])]
        state = _chain_state(cmasks, finite, on, rest, end, 12) if rest else None
        if state and "starts" in state:
            state["dates"] = [months[t] for t in state.pop("starts")]
        frontier = None
        below = [j for j in range(len(on)) if j > max(i for i in range(len(on)) if on[i])]   # 最深已成立層之下的層
        if below:
            term_sid = chain["nodes"][-1]["sid"]
            term_f6 = CH.forward(g, term_sid, 6, series[term_sid]["kind"])
            frontier = _chain_frontier(cmasks, finite, on, below, term_f6, end)
            frontier["below"] = [chain["nodes"][j]["label"] for j in below]
            frontier["next_label"] = chain["nodes"][below[0]]["label"]
            frontier["deepest_label"] = chain["nodes"][frontier["deepest"]]["label"] if frontier.get("deepest") is not None else None
            frontier["term_name"] = series[term_sid]["name"]
            frontier.pop("deepest", None)
            frontier.pop("rest", None)
        paths.append(dict(id=chain["id"], name=chain["name"], thesis=chain["thesis"], nodes=nodes,
                          active=it["active"]["count"], of=it["active"]["of"], state=state, frontier=frontier))

    # 下一波可能亮起的訊號（跨鏈）：和現在狀態相似的月份，之後 6 個月哪些目前沒亮的訊號比平常更常亮起
    wave = [{k: v for k, v in w.items() if k not in ("k", "_lift", "_base")} for w in _next_wave(X, x_now, end, W, trig)]
    for w in wave:
        w["if_then"] = [dict(name=r["name"], lift=r["lift"], horizon=r["horizon"]) for r in robust if r["trigger"] == w["id"]][:3]

    # 對答案：過去最像現在的時點，用「當時已知」的資料重跑整套推演，再對照之後實際發生的事
    cat_name = {c["id"]: c["name"] for c in (cascade or {}).get("categories", [])}
    ev_list = sorted((e["date"], e["name"], cat_name.get(e["cat"], e["cat"])) for e in (cascade or {}).get("events", []))
    cases, case_sum = _cases(X, x_now, Fs, lags, assets, series, trig, chain_masks, end, months, lam, W, out_h, act_k, ev_list)
    log(f"[scenario] 對答案：{len(cases)} 個類似時點；"
        + "；".join(f"{h} 個月前 5 名跑贏全體 {v['hit']}/{v['n']} 次、平均 {v['spread_mean']}" for h, v in case_sum["model"].items())
        + f"；鏈的下一層 Brier {case_sum['layers'].get('brier')}（基準 {case_sum['layers'].get('brier_base')}）"
        + f"；下一波訊號命中 {case_sum['wave'].get('hits')}/{case_sum['wave'].get('n')}（基準 {case_sum['wave'].get('base')}%）")

    asof = max((a["current_at"] for a in active if a.get("current_at")), default=months[end])
    log(f"[scenario] 亮燈 {len(active)} 個訊號；最像現在的歷史時點 {[(s['m'], s['jaccard']) for s in similar]}；"
        f"{len(paths)} 條鏈有成立的層；{len(ev_types)} 個相關事件類型")
    return dict(asof=asof, active=active, horizons=C.PLAYBOOK_HORIZONS, assets=out_h, backtest=backtest,
                similar=[{k: v for k, v in s.items() if k != "t"} for s in similar],
                paths=paths, wave=wave, cases=cases, case_summary=case_sum,
                events=ev_types, within=W, event_luck=((cascade or {}).get("stats") or {}).get("fdr05"),
                model=dict(lam=lam, topk=C.SCENARIO_TOPK, eval_start=C.SCENARIO_EVAL_START, boot=C.SCENARIO_BOOT,
                           block=BLOCK, perm=PERM, triggers=K, assets=len(assets)))
