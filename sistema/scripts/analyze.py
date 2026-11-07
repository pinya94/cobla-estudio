"""Analyse the tenor 2 part against the others: partners, entries, exposed passages, difficulty."""
import json, sys
from fractions import Fraction as F
sys.path.insert(0, "scripts")
from build_score import consensus_caps, PARTS, fix_measure

from config import ME, MASTER, SHORT, TOTAL, CFG, OFFSET
NAMES = {p[0]: p[1] for p in PARTS}
SECTIONS = [(x["start"], x["name"]) for x in CFG["sections"]]


def load_events():
    master = json.load(open(f"build/{MASTER}.json"))
    caps = consensus_caps(master)
    from config import PICKUP
    if PICKUP:
        caps[0] = sum((F(e["ql"]) for e in master[0]["events"]), F(0)) or caps[0]
    keys = [m["key"] for m in master]
    parts = {}
    for pid, *_ in PARTS:
        ms = json.load(open(f"build/{pid}.json"))
        meas = []
        for i, m in enumerate(ms):
            ev, _ = fix_measure(m, caps[i], pid)
            pos, on = F(0), []
            for e in ev:
                if e["t"] == "n":
                    on.append((pos, e["midi"], e["ql"], bool(e.get("tie"))))
                pos += e["ql"]
            meas.append(on)
        parts[pid] = meas
    return parts, caps, keys


def section_of(n):
    s = SECTIONS[0]
    for st, name in SECTIONS:
        if n >= st:
            s = (st, name)
    return s


def relation(a, b):
    """a, b: onset lists of one measure. Returns (same_rhythm, interval_class or None)."""
    if not a or not b:
        return False, None
    ra = [x[0] for x in a]; rb = [x[0] for x in b]
    if ra != rb:
        # allow partner rhythm that is a superset/subset with >=80% overlap
        common = set(ra) & set(rb)
        if len(common) < 0.8 * max(len(ra), len(rb)):
            return False, None
    pa = {x[0]: x[1] for x in a}; pb = {x[0]: x[1] for x in b}
    CAT = {0: 0, 3: 3, 4: 3, 8: 8, 9: 8, 5: 5, 7: 5}
    iv = [CAT.get(abs(pa[t] - pb[t]) % 12, 99) for t in pa if t in pb]
    if not iv:
        return True, None
    from collections import Counter
    c, k = Counter(iv).most_common(1)[0]
    if k < 0.6 * len(iv):
        return True, "mix"
    return True, c


def rel_text(iv):
    if iv == 0: return "al unísono"
    if iv in (3, 4): return "en terceras"
    if iv in (8, 9): return "en sextas"
    if iv in (5, 7): return "en cuartas/quintas"
    return "con el mismo ritmo"


KEY_PCS = {-1: {5, 7, 9, 10, 0, 2, 4}, 0: {0, 2, 4, 5, 7, 9, 11}, 2: {2, 4, 6, 7, 9, 11, 1}}


def difficulty(on, cap, key):
    if not on:
        return 0
    s = 0.0
    beats = float(cap) / 0.5 if cap in (F(3, 2),) else float(cap)
    s += len(on) / max(beats, 1) * 1.0
    s += sum(1.5 for x in on if x[2] <= F(1, 4))
    s += sum(1.0 for x in on if (x[1] % 12) not in KEY_PCS.get(key, set()))
    s += sum(1.0 for a, b in zip(on, on[1:]) if abs(a[1] - b[1]) > 5)
    s += sum(0.7 for x in on if x[0] % F(1, 2) != 0 and x[2] >= F(1, 2))  # off-beat long notes
    return s


def main():
    parts, caps, keys = load_events()
    me = parts[ME]
    others = [p[0] for p in PARTS if p[0] != ME]
    N = len(me)
    per = []
    for i in range(N):
        a = me[i]
        partners = []
        for o in others:
            same, iv = relation(a, parts[o][i])
            if same:
                partners.append((o, iv))
        playing = [o for o in others if parts[o][i]]
        per.append(dict(n=i + 1, play=bool(a), partners=partners, playing=playing,
                        diff=difficulty(a, caps[i], keys[i])))
    # --- phrases: contiguous playing measures, grouped by main partner
    def main_partner(x):
        if not x["play"]:
            return "rest"
        if not x["partners"]:
            return "solo" if len(x["playing"]) <= 1 else "propia"
        # prefer unison/thirds with tarotas
        CMP = [p["id"] for p in CFG["parts"] if p["role"] == "companeros"]
        pr = sorted(x["partners"], key=lambda t: (t[1] not in (0, 3, 4, 8, 9), t[0] not in CMP))
        return pr[0][0] + ":" + str(pr[0][1])

    labels = [main_partner(x) for x in per]
    # smooth single-measure blips
    for i in range(1, N - 1):
        if labels[i] != labels[i - 1] and labels[i - 1] == labels[i + 1] and labels[i] != "rest":
            labels[i] = labels[i - 1]
    phrases = []
    i = 0
    while i < N:
        j = i
        sec = section_of(i + 1)[0]
        while j + 1 < N and labels[j + 1] == labels[i] and section_of(j + 2)[0] == sec:
            j += 1
        phrases.append(dict(start=i + 1, end=j + 1, label=labels[i]))
        i = j + 1
    # merge tiny phrases (1 measure) into neighbours when playing
    out = []
    for ph in phrases:
        if out and ph["label"] != "rest" and ph["end"] - ph["start"] < 1 and out[-1]["label"] != "rest" and section_of(ph["start"])[0] == section_of(out[-1]["start"])[0]:
            out[-1]["end"] = ph["end"]
        else:
            out.append(ph)
    phrases = out

    notes = []

    def add(n0, n1, kind, text):
        notes.append(dict(start=n0, end=n1, kind=kind, text=text))

    for ph in phrases:
        lab = ph["label"]
        if lab == "rest":
            continue
        if lab == "solo":
            add(ph["start"], ph["end"], "solo", "¡Solo! Estás casi solo: cuidado con afinación y tempo")
        elif lab == "propia":
            # who has the melody?
            seg = range(ph["start"] - 1, ph["end"])
            mel = max([p["id"] for p in CFG["parts"] if p["id"] != ME and p["role"] != "base"] or others, key=lambda o: sum(len(parts[o][k]) for k in seg))
            add(ph["start"], ph["end"], "propia", f"Línea propia: nadie hace tu ritmo, aguanta tu parte (la melodía la lleva {SHORT[mel]})")
        else:
            o, iv = lab.split(":")
            iv = None if iv in ("None", "mix") else int(iv)
            others_same = sorted({p for x in per[ph["start"] - 1:ph["end"]] for p, _ in x["partners"]} - {o})
            extra = (" (y mismo ritmo que " + ", ".join(SHORT[p] for p in others_same) + ")") if others_same else ""
            add(ph["start"], ph["end"], "con", f"Vas con {SHORT[o]} {rel_text(iv)}{extra}")
    # entries
    for i in range(N):
        if per[i]["play"] and (i == 0 or not per[i - 1]["play"]):
            k = i - 1
            while k >= 0 and not per[k]["play"]:
                k -= 1
            rest_len = i - 1 - k
            if rest_len >= 2 or i == 0:
                before = per[i - 1]["playing"] if i > 0 else []
                # most active part in the measure before = the cue to listen to
                cue = sorted(before, key=lambda o: -len(parts[o][i - 1]))[:2]
                together = [p for p, _ in per[i]["partners"]]
                t = f"ENTRADA tras {rest_len} compases de silencio" if i else "Entrada inicial"
                if cue:
                    t += f". Escucha antes a {' y '.join(SHORT[c] for c in cue)}"
                if together:
                    t += f". Entras junto a {', '.join(SHORT[p] for p in together[:3])}"
                add(i + 1, i + 1, "entrada", t)
    # difficult measures: top 12 by score, grouped
    playing_m = [x for x in per if x["play"]]
    ds = sorted(x["diff"] for x in playing_m)
    cut = max(4.0, ds[int(len(ds) * 0.85)] if ds else 99)
    scored = sorted([x for x in playing_m if x["diff"] >= cut], key=lambda x: -x["diff"])[:max(3, len(playing_m) // 12)]
    hard = sorted(x["n"] for x in scored)
    groups = []
    for n in hard:
        if groups and n - groups[-1][-1] <= 2:
            groups[-1].append(n)
        else:
            groups.append([n])
    for g in groups:
        add(g[0], g[-1], "dificil", "Pasaje difícil: estúdialo lento y en bucle")
    res = dict(offset=OFFSET, sections=[dict(start=s, name=n, end=(SECTIONS[k + 1][0] - 1 if k + 1 < len(SECTIONS) else TOTAL))
                         for k, (s, n) in enumerate(SECTIONS)],
               notes=sorted(notes, key=lambda x: (x["start"], x["kind"] != "entrada")),
               per=[dict(n=x["n"], play=x["play"], partners=[p for p, _ in x["partners"]], diff=round(x["diff"], 1)) for x in per])
    json.dump(res, open(f"out/analysis_{ME}.json", "w"), ensure_ascii=False, indent=1)
    for s in res["sections"]:
        print(f"\n== {s['name']} ({s['start']}-{s['end']})")
        for nt in res["notes"]:
            if s["start"] <= nt["start"] <= s["end"]:
                print(f"  c.{nt['start']}-{nt['end']} [{nt['kind']}] {nt['text']}")


if __name__ == "__main__":
    main()
