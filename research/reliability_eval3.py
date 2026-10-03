"""可信度研究 3：(a) 收縮後機率的校準（分箱）；(b) 兩個角度一致時的方向命中；(c) 集成用「% 平均」而不是 z 分數；(d) 前半挑資產、後半驗。"""
import sys
import numpy as np
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
from gfd import chains as CH, config as C, playbook as PB, scenario as SC
from gfd.analysis import Grid, build_series, _load

sraw = _load("series.json"); g = Grid(sraw["values"]); series = build_series(g, sraw["values"])
trig = PB._triggers(series); ids = [t["id"] for t in trig]
X = SC._masks(g, series, trig, g.end); end = g.end
W = 6; START = g.months.index("2005-01"); SPLIT = g.months.index("2016-01")
rng = np.random.default_rng(3)
links = []
for ch in C.CHAINS:
    for a, b in zip(ch["nodes"], ch["nodes"][1:]):
        ia, ib = f"{ch['id']}_{a['id']}", f"{ch['id']}_{b['id']}"
        if ia in ids and ib in ids: links.append((ch["id"], ids.index(ia), ids.index(ib)))
fin_all = {j: np.isfinite(CH.transform(g, trig[j]["sid"], trig[j]["op"], series[trig[j]["sid"]]["kind"])) for _, _, j in links}
rows = []
for T in range(START, end - W + 1):
    last = T - W
    for cid, i, j in links:
        if not (X[T, i] and not X[T, j] and fin_all[j][T]): continue
        ts = np.where(X[:last + 1, i] & ~X[:last + 1, j] & fin_all[j][:last + 1])[0]
        if len(ts) < 3: continue
        hits = np.array([X[t + 1:t + 1 + W, j].any() for t in ts])
        bts = np.where(~X[:last + 1, j] & fin_all[j][:last + 1])[0]
        base = np.mean([X[t + 1:t + 1 + W, j].any() for t in bts])
        rows.append((T, len(CH.episodes(np.isin(np.arange(len(X)), ts))), hits.mean(), base, float(X[T + 1:T + 1 + W, j].any())))
T_, n_e, p, base, y = (np.array([r[k] for r in rows], float) for k in range(5))
K = 20
q = (n_e * p + K * base) / (n_e + K)
print("(a) calibration of shrunk p (k=20): bins of q → outcome rate (n)")
for lo in (0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8):
    m = (q >= lo) & (q < lo + 0.1)
    if m.sum() >= 15: print(f"   q∈[{lo:.1f},{lo+0.1:.1f}) n={m.sum():3d}  outcome {y[m].mean():.2f}  raw p mean {p[m].mean():.2f}")
print("   raw p bins:")
for lo in (0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9):
    m = (p >= lo) & (p < lo + 0.1)
    if m.sum() >= 15: print(f"   p∈[{lo:.1f},{lo+0.1:.1f}) n={m.sum():3d}  outcome {y[m].mean():.2f}")
# 更可能的提示：用收縮後的 q 判（q − base ≥ gap）
for gap in (0.05, 0.10):
    for name, span in (("all", np.ones(len(y), bool)), ("05-15", T_ < SPLIT), ("16-26", T_ >= SPLIT)):
        m = (q - base >= gap) & span; m2 = (base - q >= gap) & span
        print(f"   shrunk gap≥{gap:.2f} {name:6} more-likely n={m.sum():3d} outcome−base {y[m].mean()-base[m].mean():+.3f}" + (f"   less-likely n={m2.sum():3d} {y[m2].mean()-base[m2].mean():+.3f}" if m2.sum() >= 10 else ""))

assets = [s for s in C.PLAYBOOK_UNIVERSE if s in g.arr and s in series and s not in C.PLAYBOOK_OBSERVE_ONLY]
lags = [CH.lag_of(s) for s in assets]; Xa = X.astype(float)
def knn_pred(T, F, h, thr=SC.SIM_THR, minn=6):
    inter = Xa[:T] @ Xa[T]; union = Xa[:T].sum(1) + Xa[T].sum() - inter
    jac = np.where(union > 0, inter / np.maximum(union, 1), 0)
    out = np.full(F.shape[1], np.nan)
    for a in range(F.shape[1]):
        m = (jac >= thr); m[T - h - lags[a] + 1:] = False
        v = F[:T, a][m[:T]]; v = v[np.isfinite(v)]
        allv = F[:T - h - lags[a] + 1, a]; allv = allv[np.isfinite(allv)]
        if len(v) >= minn and len(allv) > 30: out[a] = np.median(v) - np.median(allv)
    return out
def summ(periods, key, h, label):
    offs = SC._offsets(periods, h, key, rng); means = [o["mean"] for o in offs]; ps = [o["p"] for o in offs if o.get("p") is not None]
    print(f"    {label:20} mean {np.mean(means):+.2f} [{min(means):+.2f},{max(means):+.2f}] win% {np.mean([o['hit'] for o in offs]):.0f} p {min(ps):.3f}～{max(ps):.3f} → {SC._verdict(offs)}")
for h in (3, 6, 12):
    F = np.vstack([CH.forward(g, s, h, series[s]["kind"]) for s in assets]).T
    Mom = np.vstack([CH.transform(g, s, "chg6", series[s]["kind"]) for s in assets]).T
    periods = SC._walk_forward(X, F, Mom, h, end, START, C.SCENARIO_LAMBDA, C.SCENARIO_TOPK, lags)
    agree = {"all": [], "05-15": [], "16-26": []}; agree_n = {"all": 0, "05-15": 0, "16-26": 0}
    per_asset_first, per_asset_second = {}, {}
    for P in periods:
        T = P["T"]
        ok = np.array([np.isfinite(F[T, a]) and T - h - lags[a] >= 0 and np.isfinite(F[:T - h - lags[a] + 1, a]).sum() >= 60 for a in range(len(assets))])
        idx = np.where(ok)[0]
        kp = knn_pred(T, F, h)[idx]; kpz = np.where(np.isfinite(kp), kp, 0.0)
        P["ensavg"] = SC._spread((P["pr"] + kpz) / 2, P["real"], 5)
        # 兩角度一致（都 > +1 或都 < −1）：方向命中
        m = np.isfinite(kp) & (np.abs(P["pr"]) > 1) & (np.abs(kp) > 1) & (np.sign(P["pr"]) == np.sign(kp))
        half = "05-15" if T < SPLIT else "16-26"
        for key in ("all", half):
            agree[key].extend(list((np.sign(P["pr"][m]) == np.sign(P["own"][m])).astype(float))); agree_n[key] += 1
        # 每個資產的方向命中（相似時點 |pred|≥2）
        store = per_asset_first if T < SPLIT else per_asset_second
        for a_i, a in enumerate(idx):
            v = kp[a_i]
            if np.isfinite(v) and abs(v) >= 2: store.setdefault(a, []).append(float(np.sign(v) == np.sign(P["own"][a_i])))
    print(f"\nh={h}")
    for name, sel in (("all", lambda P: True), ("05-15", lambda P: P["T"] < SPLIT), ("16-26", lambda P: P["T"] >= SPLIT)):
        sub = [P for P in periods if sel(P)]
        summ(sub, "ensavg", h, f"集成(%平均) {name}")
    for key in ("all", "05-15", "16-26"):
        v = np.array(agree[key]); print(f"  兩角度一致的方向命中 {key}: {100*v.mean():.1f}% (n picks {len(v)}, baseline own>0 rate 隨方向)")
    # 前半挑資產（命中 ≥ 58%、n ≥ 20），後半驗
    chosen = [a for a, l in per_asset_first.items() if len(l) >= 20 and np.mean(l) >= 0.58]
    v2 = np.concatenate([per_asset_second[a] for a in chosen if a in per_asset_second]) if chosen else np.array([])
    allv2 = np.concatenate([v for v in per_asset_second.values()])
    print(f"  前半命中≥58% 的資產 {[series[assets[a]]['name'][:5] for a in chosen]} → 後半命中 {100*v2.mean() if len(v2) else float('nan'):.1f}% (n={len(v2)})；後半全部資產 {100*allv2.mean():.1f}% (n={len(allv2)})")
