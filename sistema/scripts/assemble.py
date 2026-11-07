"""Assemble OMR pages of one part into a measure list, fixing multirest counts with PDF layout.
Output: build/<part>.json with measures [{n, time:[b,bt], key, events:[{t:'n'|'r', midi, ql, tie}]}]"""
import json, sys, subprocess
import xml.etree.ElementTree as ET
from fractions import Fraction as F
sys.path.insert(0, "scripts")
from layout import page_layout

STEP = dict(C=0, D=2, E=4, F=5, G=7, A=9, B=11)


def parse_page(path):
    root = ET.parse(path).getroot()
    part = root.find("part")
    systems = [[]]
    div = 1
    for m in part.findall("measure"):
        pr = m.find("print")
        if pr is not None and pr.get("new-system") == "yes" and systems[-1]:
            systems.append([])
        meas = dict(time=None, key=None, multirest=None, events=[], barline=None)
        nxt = None
        for el in m:
            if el.tag == "attributes":
                d = el.find("divisions")
                if d is not None:
                    div = int(d.text)
                k = el.find("key/fifths")
                if k is not None:
                    meas["key"] = int(k.text)
                t = el.find("time")
                if t is not None:
                    meas["time"] = [int(t.find("beats").text), int(t.find("beat-type").text)]
                mr = el.find("measure-style/multiple-rest")
                if mr is not None:
                    meas["multirest"] = int(mr.text)
            elif el.tag == "note":
                if el.find("chord") is not None:
                    continue  # keep top line only (monophonic parts)
                if el.find("duration") is None:
                    continue  # grace note
                dur = F(int(el.find("duration").text), div)
                ev = dict(ql=dur)
                if el.find("rest") is not None:
                    ev["t"] = "r"
                else:
                    p = el.find("pitch")
                    alt = p.find("alter")
                    midi = 12 * (int(p.find("octave").text) + 1) + STEP[p.find("step").text] + (int(float(alt.text)) if alt is not None else 0)
                    ev["t"] = "n"; ev["midi"] = midi
                    ties = [x.get("type") for x in el.findall("tie")]
                    ties += [x.get("type") for x in el.findall("notations/tied")]
                    slurs = [x.get("type") for x in el.findall("notations/slur")]
                    if "start" in ties:
                        ev["tie"] = True
                    if slurs:
                        ev["slur"] = slurs
                meas["events"].append(ev)
            elif el.tag == "barline":
                meas["barline"] = (el.findtext("bar-style") or "")
        systems[-1].append(meas)
    return systems


from config import TOTAL, PDF, npages, pagewidth, PICKUP


def is_restish(m):
    return m["multirest"] is not None or all(e["t"] == "r" for e in m["events"])



def solve(seg, mrs, target, rel=None, mpos=None):
    """DP over OMR measures. State (i, j, produced). Returns plan list."""
    import functools, sys
    sys.setrecursionlimit(10000)
    n = len(seg)
    rest = [is_restish(m) for _, _, m in seg]
    flag = [m["multirest"] is not None for _, _, m in seg]
    durs = [sum((e["ql"] for e in m["events"]), F(0)) for _, _, m in seg]
    odd = [durs[i] not in PLAUSIBLE for i in range(n)]
    INF = 10 ** 9

    @functools.lru_cache(None)
    def f(i, j, prod):
        if prod > target + 2:
            return INF, ()
        if i == n:
            if j < len(mrs):
                return INF, ()
            d = target - prod
            if d == 0:
                return 0, ()
            if d > 0 and d <= 3:
                return 60 * d, tuple(("pad", n, 1) for _ in range(d))
            return INF, ()
        best = (INF, ())
        # normal measure
        c = 3 if flag[i] else 0
        r = f(i + 1, j, prod + 1)
        if r[0] + c < best[0]:
            best = (r[0] + c, (("norm", i, 1),) + r[1])
        # multirest group of length L starting at i
        if j < len(mrs):
            for L in range(1, 4):
                if i + L > n:
                    break
                def mc(q):
                    return 0 if flag[q] else (2 if rest[q] else (6 if odd[q] else 30))
                c = sum(mc(q) for q in range(i, i + L)) + 2 * (L - 1)
                if rel and mpos and j < len(mpos):
                    rp, rs, rx = rel[i]; mp, ms_, mx = mpos[j]
                    c += 50 if (rp, rs) != (mp, ms_) else int(200 * abs(rx - mx))
                r = f(i + L, j + 1, prod + mrs[j])
                if r[0] + c < best[0]:
                    best = (r[0] + c, (("mr", i, mrs[j]),) + tuple(("skip", i + q, 0) for q in range(1, L)) + r[1])
        # delete a spurious measure
        r = f(i + 1, j, prod)
        if r[0] + 70 < best[0]:
            best = (r[0] + 70, (("skip", i, 0),) + r[1])
        # pad a missing measure here
        if prod < target:
            r = f(i, j, prod + 1) if False else (INF, ())
        return best

    cost, plan = f(0, 0, 0)
    if cost >= INF:
        return [("norm", i, 1) for i in range(n)], 999
    return list(plan), cost


def assemble(part):
    log = []
    systems = []  # (page, si, measures, layout)
    for p in range(1, npages(part) + 1):
        sysx = parse_page(f"omr/{part}-{p}.musicxml")
        lay = page_layout(PDF[part], f"img/{part}-{p}.png", p)
        if len(sysx) != len(lay):
            log.append(f"p{p}: OMR systems {len(sysx)} vs layout {len(lay)}")
        for si, ms in enumerate(sysx):
            L = lay[si] if si < len(lay) else dict(start=None, multirests=[])
            if L.get("start") is not None:
                L["start"] += PICKUP
            systems.append((p, si, ms, L))
    systems[0][3]["start"] = 1
    from collections import Counter
    allm = [m for s in systems for m in s[2] if m["events"] and m["multirest"] is None]
    cnt = Counter(sum((e["ql"] for e in m["events"]), F(0)) for m in allm)
    global PLAUSIBLE
    PLAUSIBLE = {d for d, c in cnt.items() if c >= 0.03 * len(allm)}
    log.append(f"plausible durations {sorted(map(str, PLAUSIBLE))}")
    anchors = [i for i, s in enumerate(systems) if s[3]["start"]] + [len(systems)]
    out = []
    for a, b in zip(anchors, anchors[1:]):
        st = systems[a][3]["start"]
        target = (systems[b][3]["start"] if b < len(systems) else TOTAL + 1) - st
        seg = [(p, si, m) for (p, si, ms, L) in systems[a:b] for m in ms]
        rel = [(p, si, (k + 0.5) / len(ms)) for (p, si, ms, L) in systems[a:b] for k, m in enumerate(ms)]
        mrs = [n for s in systems[a:b] for n in s[3]["multirests"]]
        mpos = [(s[0], s[1], (x - 40) / (s[3].get("pw", 612) - 80)) for s in systems[a:b] for x in s[3].get("mr_x", [])]
        plan, cost = solve(seg, mrs, target, rel, mpos)
        if cost >= 50:
            log.append(f"seg@{st}: forced fix cost {cost} (omr {len(seg)}, mrs {mrs}, target {target})")
        for (kind, i, cnt) in plan:
            if kind == "pad":
                p, si, _ = seg[min(i, len(seg) - 1)]
                out.append(dict(time=None, key=None, events=[], rest=True, page=p, system=si, padded=True))
                continue
            p, si, m = seg[i]
            if kind == "mr":
                for k2 in range(cnt):
                    out.append(dict(time=m["time"] if k2 == 0 else None, key=m["key"] if k2 == 0 else None,
                                    events=[], rest=True, page=p, system=si, mrgroup=f"{p}-{si}-{i}"))
            elif kind == "norm":
                if m["multirest"] is not None:
                    out.append(dict(time=m["time"], key=m["key"], events=[], rest=True, page=p, system=si))
                else:
                    m.update(page=p, system=si)
                    out.append(m)
            # kind 'skip': absorbed into a multirest group or deleted
    # time signatures: keep OMR change locations, infer numerator from content
    changes = [i for i, m in enumerate(out) if m.get("time")] or [0]
    if changes[0] != 0: changes = [0] + changes
    for ci, c in enumerate(changes):
        e = changes[ci + 1] if ci + 1 < len(changes) else len(out)
        from collections import Counter
        tots = Counter(sum((ev["ql"] for ev in m["events"]), F(0)) for m in out[c:e] if m["events"])
        if tots:
            cap = tots.most_common(1)[0][0]
        else:
            cap = None
        for m in out[c:e]:
            m["cap"] = cap
    # split merged measures (2x capacity) to absorb padded measures in the same system
    i = 0
    while i < len(out):
        m = out[i]
        if m.get("padded"):
            cands = [j for j in range(len(out)) if out[j].get("page") == m["page"] and abs(out[j].get("system", -9) - m["system"]) <= 1
                     and out[j]["events"] and out[j].get("cap") and sum((e["ql"] for e in out[j]["events"]), F(0)) == 2 * out[j]["cap"]]
            if cands:
                j = cands[0]; mm = out[j]; cap = mm["cap"]; acc = F(0); a, b = [], []
                for e in mm["events"]:
                    (a if acc < cap else b).append(e); acc += e["ql"]
                if sum((e["ql"] for e in a), F(0)) == cap:
                    m2 = dict(mm, events=b, time=None); mm["events"] = a
                    out.pop(i); out.insert(j + 1 if j < i else j, m2)
                    log.append(f"split merged measure near pad")
                    continue
            if 0 < i < len(out) - 1 and out[i - 1]["events"] == out[i + 1]["events"]:
                out[i] = dict(out[i - 1], time=None, padded=True)
                log.append(f"pad filled by repetition at {i+1}")
            else:
                log.append(f"pad kept at {i+1}")
        i += 1
    key = 0
    for i, m in enumerate(out):
        m["n"] = i + 1
        if m.get("key") is not None: key = m["key"]
        m["key"] = key
        cap = m["cap"]
        tot = sum((e["ql"] for e in m["events"]), F(0))
        if not m["events"]:
            m["events"] = [dict(t="r", ql=cap or F(3, 2))]
        elif tot != cap:
            m["bad"] = f"duration {tot} != {cap}"
    return out, log


if __name__ == "__main__":
    part = sys.argv[1]
    meas, log = assemble(part)
    for e in log: print("LOG", e)
    bad = [m for m in meas if m.get("bad")]
    print(part, "measures:", len(meas), "bad:", len(bad))
    for m in bad: print("  m", m["n"], m["bad"], [(e["t"], e.get("midi"), str(e["ql"])) for e in m["events"]])
    def ser(o):
        if isinstance(o, F): return str(o)
        raise TypeError
    import os; os.makedirs("build", exist_ok=True)
    json.dump(meas, open(f"build/{part}.json", "w"), default=ser)
