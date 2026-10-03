"""可信度研究 2：把 eval1 的發現拿到前後半樣本確認（前半挑、後半驗），附置換／自助法 p；看技巧集中在哪些資產。"""
import sys, time
import numpy as np
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
from gfd import chains as CH, config as C, playbook as PB, scenario as SC
from gfd.analysis import Grid, build_series, _load

sraw = _load("series.json"); g = Grid(sraw["values"]); series = build_series(g, sraw["values"])
trig = PB._triggers(series); ids = [t["id"] for t in trig]
X = SC._masks(g, series, trig, g.end); end = g.end
W = 6; START = g.months.index("2005-01"); SPLIT = g.months.index("2016-01")
rng = np.random.default_rng(2)

# ── 1. 傳導鏈：方向的命中（p 比平常高 ≥ gap 時，實際發生率 vs 平常）前後半各看 ──
links = []
for ch in C.CHAINS:
    nodes = ch["nodes"]
    for a, b in zip(nodes, nodes[1:]):
        ia, ib = f"{ch['id']}_{a['id']}", f"{ch['id']}_{b['id']}"
        if ia in ids and ib in ids:
            links.append((ch["id"], ids.index(ia), ids.index(ib)))
fin_all = {j: np.isfinite(CH.transform(g, trig[j]["sid"], trig[j]["op"], series[trig[j]["sid"]]["kind"])) for _, _, j in links}
rows = []
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
        rows.append((T, cid, j, len(CH.episodes(np.isin(np.arange(len(X)), ts))), hits.mean(), base, float(X[T + 1:T + 1 + W, j].any())))
T_, n_e, p, base, y = np.array([r[0] for r in rows]), np.array([r[3] for r in rows], float), np.array([r[4] for r in rows]), np.array([r[5] for r in rows]), np.array([r[6] for r in rows])
yrs = np.array([g.months[t][:4] for t in T_])
def lift(m):
    """p>base 的那組：實際發生率 − 平常；block bootstrap（按年）90% 區間"""
    if m.sum() < 10: return None
    obs = y[m].mean() - base[m].mean()
    ys = sorted(set(yrs[m])); d = []
    for _ in range(2000):
        pick = rng.choice(ys, len(ys)); mm = np.concatenate([np.where((yrs == s) & m)[0] for s in pick])
        d.append(y[mm].mean() - base[mm].mean())
    return obs, np.percentile(d, 5), np.percentile(d, 95), int(m.sum())
print("chain direction (p > base by ≥ gap): outcome − base, 90% block-bootstrap CI")
for gap in (0.05, 0.10, 0.15, 0.20):
    for name, span in (("all", np.ones(len(y), bool)), ("2005-15", T_ < SPLIT), ("2016-26", T_ >= SPLIT)):
        up = (p - base >= gap) & span; dn = (base - p >= gap) & span
        r1, r2 = lift(up), lift(dn)
        print(f"  gap≥{gap:.2f} {name:8} more-likely: " + (f"{r1[0]:+.3f} [{r1[1]:+.3f},{r1[2]:+.3f}] n={r1[3]}" if r1 else "n<10") + "   less-likely: " + (f"{r2[0]:+.3f} [{r2[1]:+.3f},{r2[2]:+.3f}] n={r2[3]}" if r2 else "n<10"))
m = (np.abs(p - base) >= 0.10) & (n_e >= 10)
print("  gap≥0.10 & episodes≥10:", lift(m & (p > base)), lift(m & (p < base)))
# 每條鏈的方向命中
print("  per chain (gap≥0.10, more-likely): outcome vs base")
for cid in sorted(set(r[1] for r in rows)):
    m = (p - base >= 0.10) & np.array([r[1] == cid for r in rows])
    if m.sum() >= 15: print(f"    {cid:10} n={m.sum():3d} outcome {y[m].mean():.2f} base {base[m].mean():.2f}")

# ── 2. 排行：前後半、置換 p；相似時點的參數敏感度（只在前半看）；集成 ──
assets = [s for s in C.PLAYBOOK_UNIVERSE if s in g.arr and s in series and s not in C.PLAYBOOK_OBSERVE_ONLY]
lags = [CH.lag_of(s) for s in assets]
Xa = X.astype(float)
def knn_pred(T, F, h, thr, minn=6):
    inter = Xa[:T] @ Xa[T]; union = Xa[:T].sum(1) + Xa[T].sum() - inter
    jac = np.where(union > 0, inter / np.maximum(union, 1), 0)
    out = np.full(F.shape[1], np.nan)
    for a in range(F.shape[1]):
        m = (jac >= thr); m[T - h - lags[a] + 1:] = False
        v = F[:T, a][m[:T]]; v = v[np.isfinite(v)]
        allv = F[:T - h - lags[a] + 1, a]; allv = allv[np.isfinite(allv)]
        if len(v) >= minn and len(allv) > 30:
            out[a] = np.median(v) - np.median(allv)
    return out
def zs(v):
    v = np.array(v, float); ok = np.isfinite(v); z = np.zeros_like(v)
    if ok.sum() >= 3: z[ok] = (v[ok] - v[ok].mean()) / (v[ok].std() + 1e-9)
    return z
def summarize(periods, key, h, label):
    offs = SC._offsets(periods, h, key, rng)
    means = [o["mean"] for o in offs]; ps = [o["p"] for o in offs if o.get("p") is not None]
    hits = [o["hit"] for o in offs]
    print(f"    {label:22} mean/offset {np.mean(means):+.2f} [{min(means):+.2f},{max(means):+.2f}]  win% {np.mean(hits):.0f}  p {min(ps):.3f}～{max(ps):.3f}  → {SC._verdict(offs)}")
for h in (3, 6, 12):
    F = np.vstack([CH.forward(g, s, h, series[s]["kind"]) for s in assets]).T
    Mom = np.vstack([CH.transform(g, s, "chg6", series[s]["kind"]) for s in assets]).T
    periods = SC._walk_forward(X, F, Mom, h, end, START, C.SCENARIO_LAMBDA, C.SCENARIO_TOPK, lags)
    for P in periods:
        T = P["T"]
        ok = np.array([np.isfinite(F[T, a]) and T - h - lags[a] >= 0 and np.isfinite(F[:T - h - lags[a] + 1, a]).sum() >= 60 for a in range(len(assets))])
        idx = np.where(ok)[0]
        for thr in (0.2, 0.25, 0.3):
            kp = knn_pred(T, F, h, thr)[idx]
            P[f"knn{thr}"] = SC._spread(np.where(np.isfinite(kp), kp, -99), P["real"], 5)
            if thr == 0.25:
                P["ens2"] = SC._spread(zs(P["pr"]) + zs(np.where(np.isfinite(kp), kp, 0)), P["real"], 5)
                P["kp"] = kp; P["idx"] = idx
    print(f"\nh={h}")
    for name, sel in (("all", lambda P: True), ("2005-15", lambda P: P["T"] < SPLIT), ("2016-26", lambda P: P["T"] >= SPLIT)):
        sub = [P for P in periods if sel(P)]
        print(f"  {name} ({len(sub)} periods)")
        for key, label in (("ridge", "ridge (現行)"), ("knn0.25", "相似時點 thr.25"), ("ens2", "集成 ridge+相似")):
            summarize(sub, key, h, label)
        if name == "2005-15":
            for thr in (0.2, 0.3): summarize(sub, f"knn{thr}", h, f"相似時點 thr{thr}（敏感度）")
    # 每個資產：相似時點預測 ≥ +2 時，實際 own 超額的平均與命中（全期）
    per = {}
    for P in periods:
        for a_i, a in enumerate(P["idx"]):
            v = P["kp"][a_i]
            if np.isfinite(v) and abs(v) >= 2:
                per.setdefault(assets[a], []).append((np.sign(v), P["own"][a_i]))
    rows_a = []
    for s, lst in per.items():
        arr = np.array(lst); n = len(arr)
        if n >= 30:
            agree = np.mean(np.sign(arr[:, 1]) == arr[:, 0]); rows_a.append((agree, n, s, np.mean(arr[:, 0] * arr[:, 1])))
    rows_a.sort(reverse=True)
    print("  相似時點 |pred|≥2：各資產方向命中（n≥30）：", "、".join(f"{series[s]['name'][:6]} {100*a:.0f}%({n})" for a, n, s, _ in rows_a[:8]), " … 最差：", "、".join(f"{series[s]['name'][:6]} {100*a:.0f}%" for a, n, s, _ in rows_a[-3:]))
