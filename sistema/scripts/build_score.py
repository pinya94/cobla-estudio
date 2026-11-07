"""Combine assembled parts into one clean model (score.json) + MusicXML/MIDI exports."""
import json, os
from fractions import Fraction as F

from config import PARTS, MASTER, overrides

# manual corrections after visual check (part, measure) -> events [(midi|None, ql)]
OVERRIDES = overrides()



def consensus_caps(master):
    """measure capacity = most common capacity across all parts (robust to OMR errors in one part)"""
    from collections import Counter
    allp = [json.load(open(f"build/{p[0]}.json")) for p in PARTS]
    caps = []
    for i in range(len(master)):
        sec = Counter(F(ms[i]["cap"]) for ms in allp if i < len(ms) and ms[i].get("cap"))
        # actual durations of measures that contain notes are the strongest evidence
        def actual(m):
            tot = sum((F(e["ql"]) for e in m["events"]), F(0))
            if m.get("cap"):
                c0 = F(m["cap"]); q = tot - c0
                if q in (F(1, 2), F(1, 4)):
                    qs = [F(e["ql"]) for e in m["events"]]
                    if any(qs[k:k + 3] == [q] * 3 for k in range(len(qs) - 2)):
                        return c0
            return tot
        act = Counter(actual(ms[i]) for ms in allp
                      if i < len(ms) and any(e["t"] == "n" for e in ms[i]["events"]))
        cand = Counter()
        for d, k in act.items():
            cand[d] += 2 * k
        for d, k in sec.items():
            cand[d] += k
        top = cand.most_common()
        caps.append(top[0][0] if top else F(master[i]["cap"]))
    from config import CFG
    for k, v in CFG.get("caps", {}).items():  # manual measure lengths (internal index): {"80": "2"}
        caps[int(k) - 1] = F(v)
    return caps


def load(p):
    return json.load(open(f"build/{p}.json"))


def fix_measure(m, cap, part):
    ev = [dict(e, ql=F(e["ql"])) for e in m["events"]]
    if (part, m["n"]) in OVERRIDES:
        ev = [dict(t="r" if p is None else "n", midi=p, ql=F(q)) for p, q in OVERRIDES[(part, m["n"])]]
        return ev, None
    tot = sum((e["ql"] for e in ev), F(0))
    if tot == cap:
        return ev, None
    if all(e["t"] == "r" for e in ev):
        return [dict(t="r", ql=cap)], None
    # OMR often drops triplet brackets: 3 eighths read as normal eighths (+1/2 too long)
    for q in (F(1, 2), F(1, 4)):
        extra = q / 2 * 1  # 3 notes of q in the time of 2 -> saves q
        if tot - cap == q:
            for k in range(len(ev) - 2):
                if all(ev[k + j]["ql"] == q for j in range(3)):
                    for j in range(3):
                        ev[k + j] = dict(ev[k + j], ql=q * F(2, 3))
                    return ev, None
    # proportional rescale keeps alignment; flag for review
    if tot > 0:
        k = cap / tot
        ev = [dict(e, ql=e["ql"] * k) for e in ev]
    return ev, f"rescaled {tot}->{cap}"


def main():
    master = load(MASTER)
    caps = consensus_caps(master)
    from config import PICKUP
    if PICKUP:
        caps[0] = sum((F(e["ql"]) for e in master[0]["events"]), F(0)) or caps[0]
    keys = [m["key"] for m in master]
    from config import CFG
    score = dict(title=CFG["title"], subtitle=CFG.get("subtitle", ""), composer=CFG.get("composer", ""),
                 measures=[dict(n=i + 1, cap=str(c), key=keys[i]) for i, c in enumerate(caps)], parts=[])
    report = {}
    for pid, name, prog, clef in PARTS:
        ms = load(pid)
        assert len(ms) == len(caps), (pid, len(ms))
        notes = []  # absolute timeline: start (quarters), dur, midi, measure
        t = F(0)
        flags = []
        for i, m in enumerate(ms):
            ev, flag = fix_measure(m, caps[i], pid)
            if flag:
                flags.append((i + 1, flag))
            pos = t
            for e in ev:
                if e["t"] == "n":
                    notes.append(dict(s=pos, d=e["ql"], p=e["midi"], m=i + 1, tie=bool(e.get("tie")) or "start" in (e.get("slur") or [])))
                pos += e["ql"]
            t += caps[i]
        # merge ties
        merged = []
        for nt in notes:
            if merged and merged[-1]["tie"] and merged[-1]["p"] == nt["p"] and merged[-1]["s"] + merged[-1]["d"] == nt["s"]:
                merged[-1]["d"] += nt["d"]; merged[-1]["tie"] = nt["tie"]
            else:
                merged.append(dict(nt))
        score["parts"].append(dict(id=pid, name=name, program=prog, clef=clef,
                                   notes=[[float(n["s"]), float(n["d"]), n["p"], n["m"]] for n in merged]))
        report[pid] = flags
    os.makedirs("out", exist_ok=True)
    json.dump(score, open("out/score.json", "w"))
    for k, v in report.items():
        print(k, len(v), v[:12])


if __name__ == "__main__":
    main()
