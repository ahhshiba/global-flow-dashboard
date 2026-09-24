"""傳導鏈量測：把「上游事件 → 第二層 → 第三層…」的假說，用 1995 年起的月資料逐段檢定。

所有數字都是歷史樣本內的描述，不是預測，也沒有做樣本外交易驗證。為了不讓統計看起來比實際可靠：
- 連續（或間隔 ≤ 3 個月）的觸發月合併成「一次事件」，事件數才是真正的樣本數。
- 每個條件報酬都附無條件基準，只有高出基準的部分才有討論價值。
- p 值用整段觸發序列循環位移得到，保留報酬自相關與事件群聚；位移檢定只說明
  「隨機挑同樣多的時點有多容易達到同樣結果」，不是交易勝率。
"""
import numpy as np

from . import config as C

GAP = 3          # 兩次觸發間隔 ≤ 3 個月視為同一次事件
PROFILE_MONTHS = 12


def r(v, nd=2):
    if v is None:
        return None
    v = float(v)
    return round(v, nd) if np.isfinite(v) else None


def _kind(series, sid):
    return (series.get(sid) or {}).get("kind", "price")


def transform(g, sid, op, kind):
    """把序列轉成條件要用的量：chgN＝過去 N 個月變動（價格 %、殖利率 bp）；level＝原始水準。"""
    a = g.arr.get(sid)
    if a is None:
        return None
    if op == "level":
        return a.copy()
    k = int(op.replace("chg", ""))
    out = np.full(len(a), np.nan)
    with np.errstate(all="ignore"):
        if kind == "yield":
            out[k:] = (a[k:] - a[:-k]) * 100
        else:
            out[k:] = 100 * np.log(a[k:] / a[:-k])
    return out


def trigger_mask(vals, cmp_, thr, end):
    m = np.zeros(len(vals), bool)
    ok = np.isfinite(vals)
    m[ok] = (vals[ok] >= thr) if cmp_ == ">=" else (vals[ok] <= thr)
    m[end + 1:] = False          # 未完成的當月不算
    return m


def forward(g, sid, h, kind):
    a = g.arr[sid]
    n = len(a)
    out = np.full(n, np.nan)
    with np.errstate(all="ignore"):
        if kind == "yield":
            out[:n - h] = (a[h:] - a[:n - h]) * 100
        else:
            out[:n - h] = 100 * np.log(a[h:] / a[:n - h])
    return out


def worst_path(g, sid, h, kind):
    """區間內最深的逆行：價格取期間最低點相對起點，殖利率取最大反向變動。"""
    a = g.arr[sid]
    n = len(a)
    out = np.full(n, np.nan)
    for t in range(n - h):
        seg = a[t + 1:t + h + 1]
        if not np.isfinite(a[t]) or not np.isfinite(seg).all():
            continue
        with np.errstate(all="ignore"):
            out[t] = (seg.min() - a[t]) * 100 if kind == "yield" else 100 * np.log(seg.min() / a[t])
    return out


def episodes(mask, gap=GAP):
    idx = np.where(mask)[0]
    if not idx.size:
        return []
    starts = [int(idx[0])]
    for prev, cur in zip(idx, idx[1:]):
        if cur - prev > gap:
            starts.append(int(cur))
    return starts


def dist(vals):
    v = np.asarray([x for x in vals if x is not None and np.isfinite(x)], dtype=float)
    if not v.size:
        return dict(n=0)
    return dict(n=int(v.size), mean=r(v.mean()), median=r(np.median(v)), hit=r(100 * (v > 0).mean(), 0),
                p10=r(np.percentile(v, 10)), p90=r(np.percentile(v, 90)), worst=r(v.min()), best=r(v.max()))


def shift_p(fwd, mask, iters=2000, seed=20260924):
    """整段觸發序列循環位移，看隨機時點有多容易達到同樣的平均值（雙尾）。"""
    valid = np.isfinite(fwd)
    obs = fwd[mask & valid]
    if obs.size < 3:
        return None
    target = float(obs.mean())
    rng = np.random.default_rng(seed)
    n = len(mask)
    ge = le = tot = 0
    for _ in range(iters):
        m2 = np.roll(mask, int(rng.integers(1, n))) & valid
        if m2.sum() < 3:
            continue
        mu = float(fwd[m2].mean())
        tot += 1
        ge += mu >= target
        le += mu <= target
    if not tot:
        return None
    return r(min(1.0, 2 * min((ge + 1) / (tot + 1), (le + 1) / (tot + 1))), 3)


def measure_link(g, series, up, dn, end):
    """上游事件 → 下游：多久傳導到、機率多高、下游報酬分布與逆行幅度。"""
    up_kind, dn_kind = _kind(series, up["sid"]), _kind(series, dn["sid"])
    up_vals, dn_vals = transform(g, up["sid"], up["op"], up_kind), transform(g, dn["sid"], dn["op"], dn_kind)
    if up_vals is None or dn_vals is None:
        return None
    up_mask = trigger_mask(up_vals, up["cmp"], up["thr"], end)
    dn_mask = trigger_mask(dn_vals, dn["cmp"], dn["thr"], end)
    W = C.CHAIN_WITHIN
    starts = episodes(up_mask)

    def wait(t):
        for j in range(1, W + 1):
            if t + j <= end and dn_mask[t + j]:
                return j
        return None

    def occurred(t):
        return None if t + W > end else bool(dn_mask[t + 1:t + 1 + W].any())

    ev_hits = [occurred(t) for t in starts]
    ev_hits = [x for x in ev_hits if x is not None]
    base_hits = [occurred(t) for t in range(end + 1) if np.isfinite(dn_vals[t])]
    base_hits = [x for x in base_hits if x is not None]
    waits = [w for w in (wait(t) for t in starts) if w is not None]

    horizons = {}
    for hh in C.CHAIN_HORIZONS:
        f = forward(g, dn["sid"], hh, dn_kind)
        ev, bl = dist([f[t] for t in starts]), dist(f[:end + 1])
        mae = dist([worst_path(g, dn["sid"], hh, dn_kind)[t] for t in starts])
        horizons[str(hh)] = dict(
            event=ev, base=bl, mae=mae,
            lift=r(ev["median"] - bl["median"]) if ev.get("median") is not None and bl.get("median") is not None else None,
            p=shift_p(f, up_mask))

    f1 = forward(g, dn["sid"], 1, dn_kind)
    profile = []
    for j in range(1, PROFILE_MONTHS + 1):
        vals = [f1[t + j] for t in starts if t + j <= end]
        d = dist(vals)
        profile.append(dict(m=j, mean=d.get("mean"), n=d.get("n", 0)))

    # 先行 vs 追價：事件當下，下游自己過去 3 個月是否已經往預期方向走了
    trail = transform(g, dn["sid"], "chg3", dn_kind)
    f3 = forward(g, dn["sid"], 3, dn_kind)
    want_down = dn["cmp"] == "<="
    not_yet, already = [], []
    for t in starts:
        if not np.isfinite(trail[t]) or not np.isfinite(f3[t]):
            continue
        moved = trail[t] <= 0 if want_down else trail[t] >= 0
        (already if moved else not_yet).append(f3[t])
    prob = r(100 * np.mean(ev_hits), 0) if ev_hits else None
    prob_base = r(100 * np.mean(base_hits), 0) if base_hits else None
    # 判定只分三級，避免把不顯著的結果說得像訊號
    h3 = horizons["3"]
    strong_ret = h3.get("p") is not None and h3["p"] <= 0.05 and h3["event"].get("n", 0) >= 10
    prob_lift = r(prob - prob_base) if prob is not None and prob_base is not None else None
    verdict = ("傳導與報酬都顯著" if strong_ret and (prob_lift or 0) >= 10
               else "只有傳導明顯" if (prob_lift or 0) >= 10
               else "報酬顯著但傳導普通" if strong_ret else "與平常沒有明顯差別")
    return dict(
        from_=up["id"], to=dn["id"], within=W,
        unit="bp" if dn_kind == "yield" else "%", prob_lift=prob_lift, verdict=verdict,
        prob=prob, prob_n=len(ev_hits), prob_base=prob_base,
        wait_median=r(float(np.median(waits)), 1) if waits else None, wait_n=len(waits),
        horizons=horizons, profile=profile,
        timing=dict(not_yet=dist(not_yet), already=dist(already), direction="down" if want_down else "up"))


def build(g, series, months, log=print):
    end = g.end
    out, findings = [], []
    for chain in C.CHAINS:
        nodes, masks = [], []
        ok = True
        for nd in chain["nodes"]:
            kind = _kind(series, nd["sid"])
            vals = transform(g, nd["sid"], nd["op"], kind)
            if vals is None:
                ok = False
                break
            m = trigger_mask(vals, nd["cmp"], nd["thr"], end)
            masks.append(m)
            fin_idx = np.where(np.isfinite(vals[:end + 1]))[0]
            cur = int(fin_idx[-1]) if fin_idx.size else None
            nodes.append(dict(id=nd["id"], sid=nd["sid"], name=series[nd["sid"]]["name"], label=nd["label"],
                              why=nd["why"], op=nd["op"], cmp=nd["cmp"], thr=nd["thr"], kind=kind,
                              current=r(vals[cur]) if cur is not None else None,
                              current_at=months[cur] if cur is not None else None,
                              triggered=bool(m[cur]) if cur is not None else None,
                              months_triggered=int(m.sum()), episodes=len(episodes(m))))
        if not ok:
            continue
        links = [measure_link(g, series, chain["nodes"][i], chain["nodes"][i + 1], end)
                 for i in range(len(chain["nodes"]) - 1)]
        links = [x for x in links if x]

        # 全鏈同時成立（通常樣本很少，照實呈現）
        all_mask = np.logical_and.reduce(masks)
        term = chain["nodes"][-1]
        term_kind = _kind(series, term["sid"])
        starts_all = episodes(all_mask)
        full = dict(months=int(all_mask.sum()), episodes=len(starts_all),
                    dates=[months[t] for t in starts_all][-8:], horizons={})
        for hh in C.CHAIN_HORIZONS:
            f = forward(g, term["sid"], hh, term_kind)
            full["horizons"][str(hh)] = dict(event=dist([f[t] for t in starts_all]), base=dist(f[:end + 1]))

        # 第一層事件的近期紀錄：發生時間與末端標的其後 6 個月表現
        head_mask = masks[0]
        f6 = forward(g, term["sid"], 6, term_kind)
        recent = [dict(at=months[t], outcome=r(f6[t])) for t in episodes(head_mask)][-6:]

        active = [n["id"] for n in nodes if n["triggered"]]
        summary = dict(
            links=len(links),
            transmit=sum(1 for l in links if (l.get("prob_lift") or 0) >= 10),
            significant=sum(1 for l in links if "報酬" in (l.get("verdict") or "") and "顯著" in l["verdict"]),
            # 先行 vs 追價：哪一邊的 3 個月中位數比較好（只在兩邊都有 ≥ 3 次事件時判定）
            timing=[dict(link=f"{l['from_']}→{l['to']}",
                         better="尚未反應時進場" if (l["timing"]["not_yet"].get("median") or -99) > (l["timing"]["already"].get("median") or -99) else "已反應後進場",
                         not_yet=l["timing"]["not_yet"].get("median"), already=l["timing"]["already"].get("median"),
                         n_not_yet=l["timing"]["not_yet"].get("n", 0), n_already=l["timing"]["already"].get("n", 0))
                    for l in links if l["timing"]["not_yet"].get("n", 0) >= 3 and l["timing"]["already"].get("n", 0) >= 3])
        out.append(dict(id=chain["id"], name=chain["name"], thesis=chain["thesis"], nodes=nodes, links=links,
                        full=full, recent=recent, terminal=term["sid"], summary=summary,
                        active=dict(count=len(active), of=len(nodes), ids=active)))

        if active:
            first = links[0] if links else None
            txt = f"{len(active)}/{len(nodes)} 個節點目前成立（{'、'.join(n['label'] for n in nodes if n['triggered'])}）。"
            if first and first["prob"] is not None:
                txt += (f" 歷史上第一層成立後 {C.CHAIN_WITHIN} 個月內第二層跟著成立的比例 {first['prob']:.0f}%"
                        f"（平常 {first['prob_base']:.0f}%，{first['prob_n']} 次事件）；{first['verdict']}。")
            findings.append(dict(tab="chains", tone="alert" if len(active) >= 3 else "neutral",
                                 title=f"{chain['name']}：目前 {len(active)}/{len(nodes)} 層成立", text=txt))
    log(f"[chains] {len(out)} 條鏈、{sum(len(c['links']) for c in out)} 段連結")
    return dict(items=out, within=C.CHAIN_WITHIN, horizons=C.CHAIN_HORIZONS, gap=GAP,
                note="事件數為合併後的獨立事件；報酬為樣本內歷史分布，未做樣本外交易驗證。"), findings
