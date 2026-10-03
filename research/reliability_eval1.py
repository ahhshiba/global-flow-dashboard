"""可信度研究 1：傳導鏈下一層的機率、期望值排行，用走步樣本外評分；試幾個候選改法。只讀資料，不改產品。"""
import json, sys, time
import numpy as np
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
from gfd import chains as CH, config as C, playbook as PB, scenario as SC
from gfd.analysis import Grid, build_series, _load

sraw = _load("series.json"); g = Grid(sraw["values"]); series = build_series(g, sraw["values"])
trig = PB._triggers(series); ids = [t["id"] for t in trig]
X = SC._masks(g, series, trig, g.end); end = g.end
W = 6; START = g.months.index("2005-01")
rng = np.random.default_rng(1)

# ── 1. 傳導鏈下一層：每個月、每段「上游亮、這層沒亮」的連結，都用當時以前的資料推一次 ──
links = []
for ch in C.CHAINS:
    nodes = ch["nodes"]
    for a, b in zip(nodes, nodes[1:]):
        ia, ib = f"{ch['id']}_{a['id']}", f"{ch['id']}_{b['id']}"
        if ia in ids and ib in ids:
            links.append((ch["id"], ids.index(ia), ids.index(ib)))
print("links", len(links))
fin_all = {j: np.isfinite(CH.transform(g, trig[j]["sid"], trig[j]["op"], series[trig[j]["sid"]]["kind"])) for _, _, j in links}
rows = []   # (T, link, n, p, base, outcome)
for T in range(START, end - W + 1):
    last = T - W
    for cid, i, j in links:
        if not (X[T, i] and not X[T, j] and fin_all[j][T]):
            continue
        ts = np.where(X[:last + 1, i] & ~X[:last + 1, j] & fin_all[j][:last + 1])[0]
        if len(ts) < 3:
            continue
        hits = np.array([X[t + 1:t + 1 + W, j].any() for t in ts])
        bts = np.where(~X[:last + 1, j] & fin_all[j][:last + 1])[0]
        base = np.mean([X[t + 1:t + 1 + W, j].any() for t in bts])
        out = X[T + 1:T + 1 + W, j].any()
        rows.append((T, cid, len(ts), len(CH.episodes(np.isin(np.arange(len(X)), ts))), hits.mean(), base, float(out)))
R = np.array([(r[2], r[3], r[4], r[5], r[6]) for r in rows])
n_m, n_e, p, base, y = R.T
print(f"chain predictions: {len(R)} (months {START}..{end-W}), outcome rate {y.mean():.2f}")
def brier(q): return float(np.mean((q - y) ** 2))
yrs = np.array([g.months[r[0]][:4] for r in rows])
def boot_diff(qa, qb, B=2000):
    ys = sorted(set(yrs)); d = []
    for _ in range(B):
        pick = rng.choice(ys, len(ys)); m = np.concatenate([np.where(yrs == s)[0] for s in pick])
        d.append(np.mean((qa[m] - y[m]) ** 2) - np.mean((qb[m] - y[m]) ** 2))
    d = np.array(d); return float(np.mean(d)), float(np.percentile(d, 5)), float(np.percentile(d, 95))
print(f"  raw p       Brier {brier(p):.4f}   base Brier {brier(base):.4f}   skill {1 - brier(p)/brier(base):+.3f}")
for k in (5, 10, 20, 40, 80):
    q = (n_e * p + k * base) / (n_e + k)
    m, lo, hi = boot_diff(q, base)
    print(f"  shrink k={k:2d} (by episodes) Brier {brier(q):.4f}  skill {1 - brier(q)/brier(base):+.3f}   Δ vs base {m:+.4f} [{lo:+.4f},{hi:+.4f}]")
for k in (20, 40, 80):
    q = (n_m * p + k * base) / (n_m + k)
    print(f"  shrink k={k:2d} (by months)   Brier {brier(q):.4f}  skill {1 - brier(q)/brier(base):+.3f}")
# 只用段數 ≥ N 的預測
for N in (5, 10, 15):
    m = n_e >= N
    print(f"  only n_episodes>={N}: n={m.sum()} raw skill {1 - brier(p[m]*1)/brier(base[m]*1) if False else 1 - np.mean((p[m]-y[m])**2)/np.mean((base[m]-y[m])**2):+.3f}")
# 方向：p > base 預測「比平常更可能」—— 命中率
dir_m = np.abs(p - base) >= 0.10
print(f"  |p-base|>=10pp: n={dir_m.sum()}, outcome when p>base: {y[dir_m & (p > base)].mean():.2f} (base {base[dir_m & (p > base)].mean():.2f}); when p<base: {y[dir_m & (p < base)].mean():.2f} (base {base[dir_m & (p < base)].mean():.2f})")

# ── 2. 期望值排行：ridge vs 相似時點 vs 位階 vs 集成；方向模型 ──
assets = [s for s in C.PLAYBOOK_UNIVERSE if s in g.arr and s in series and s not in C.PLAYBOOK_OBSERVE_ONLY]
lags = [CH.lag_of(s) for s in assets]
Xa = X.astype(float)
def knn_pred(T, F, h):
    """相似時點：Jaccard ≥ thr 的 t ≤ T−h−lag，各資產中位 own 超額"""
    inter = Xa[:T] @ Xa[T]; union = Xa[:T].sum(1) + Xa[T].sum() - inter
    jac = np.where(union > 0, inter / np.maximum(union, 1), 0)
    out = np.full(F.shape[1], np.nan)
    for a in range(F.shape[1]):
        m = (jac >= SC.SIM_THR); m[T - h - lags[a] + 1:] = False
        v = F[:T, a][m[:T]]; v = v[np.isfinite(v)]
        allv = F[:T - h - lags[a] + 1, a]; allv = allv[np.isfinite(allv)]
        if len(v) >= 6 and len(allv) > 30:
            out[a] = np.median(v) - np.median(allv)
    return out
PCT = {}
for a, s in enumerate(assets):
    arr = g.arr[s]; pct = np.full(len(arr), np.nan)
    for t in range(len(arr)):
        if np.isfinite(arr[t]):
            w = arr[max(0, t - 119):t + 1]; w = w[np.isfinite(w)]
            if len(w) >= 36: pct[t] = 100 * (w < arr[t]).mean() + 50 * (w == arr[t]).mean()
    PCT[a] = pct
def pct_pred(T, F, h):
    out = np.full(F.shape[1], np.nan)
    for a in range(F.shape[1]):
        pc = PCT[a]
        if not np.isfinite(pc[T]): continue
        b = min(4, int(pc[T] // 20)); upto = T - h - lags[a]
        if upto < 60: continue
        bb = np.floor(np.minimum(np.nan_to_num(pc[:upto + 1], nan=-1), 99.9) / 20).astype(int)
        m = (bb == b) & np.isfinite(F[:upto + 1, a]); allm = np.isfinite(F[:upto + 1, a])
        if m.sum() >= 12:
            out[a] = np.median(F[:upto + 1, a][m]) - np.median(F[:upto + 1, a][allm])
    return out
def zs(v):
    v = np.array(v, float); ok = np.isfinite(v)
    if ok.sum() < 3: return np.zeros_like(v)
    z = np.zeros_like(v); z[ok] = (v[ok] - v[ok].mean()) / (v[ok].std() + 1e-9); return z
for h in (3, 6, 12):
    t0 = time.time()
    F = np.vstack([CH.forward(g, s, h, series[s]["kind"]) for s in assets]).T
    Mom = np.vstack([CH.transform(g, s, "chg6", series[s]["kind"]) for s in assets]).T
    periods = SC._walk_forward(X, F, Mom, h, end, START, C.SCENARIO_LAMBDA, C.SCENARIO_TOPK, lags)
    stats = {k: [] for k in ("ridge", "knn", "pct", "ens2", "ens3", "ridge_sign", "knn_sign")}
    hit = {k: [] for k in ("ridge", "knn", "pct", "ens3")}
    for P in periods:
        T = P["T"]
        # _walk_forward 的遮罩：F[T,a] 有值、且到 T−h−lag 為止有 ≥ 60 筆結果
        ok = np.array([np.isfinite(F[T, a]) and T - h - lags[a] >= 0 and np.isfinite(F[:T - h - lags[a] + 1, a]).sum() >= 60 for a in range(len(assets))])
        idx = np.where(ok)[0]
        assert len(idx) == len(P["real"]), (len(idx), len(P["real"]))
        kp = knn_pred(T, F, h); pp = pct_pred(T, F, h)
        r = P["real"]; own = P["own"]
        kp, pp = kp[idx], pp[idx]
        z_r, z_k, z_p = zs(P["pr"]), zs(np.where(np.isfinite(kp), kp, 0)), zs(np.where(np.isfinite(pp), pp, 0))
        stats["ridge"].append(SC._spread(P["pr"], r, 5)); stats["knn"].append(SC._spread(np.where(np.isfinite(kp), kp, -99), r, 5))
        stats["pct"].append(SC._spread(np.where(np.isfinite(pp), pp, -99), r, 5))
        stats["ens2"].append(SC._spread(z_r + z_k, r, 5)); stats["ens3"].append(SC._spread(z_r + z_k + z_p, r, 5))
        # 方向：預測超額 >0 的資產，實際 own>0 的比例
        for key, pred in (("ridge_sign", P["pr"]), ("knn_sign", kp)):
            m = np.isfinite(pred) & (np.abs(pred) > 0.5)
            if m.sum(): stats[key].append(float(np.mean(np.sign(pred[m]) == np.sign(own[m]))))
        for key, pred in (("ridge", P["pr"]), ("knn", kp), ("pct", pp), ("ens3", z_r + z_k + z_p)):
            top = np.argsort(-np.where(np.isfinite(pred), pred, -99))[:5]; hit[key].append(float(np.mean(own[top] > 0)))
    print(f"\nh={h}: {len(periods)} periods ({time.time()-t0:.0f}s)")
    for k in ("ridge", "knn", "pct", "ens2", "ens3"):
        v = np.array(stats[k]); sub = v[::h]
        print(f"  {k:6} top5−all mean {v.mean():+.2f}  non-overlap mean {sub.mean():+.2f}  win% {100*np.mean(sub>0):.0f}  " + (f"top5 own>0 {100*np.mean(hit[k]):.0f}%" if k in hit else ""))
    for k in ("ridge_sign", "knn_sign"):
        v = np.array(stats[k]); print(f"  {k:10} direction hit {100*v.mean():.1f}% (n periods {len(v)})")
