"""Export cleaned measures to MusicXML (per part + full score) and MIDI with music21."""
import json, sys
from fractions import Fraction as F
from music21 import stream, note, meter, key, clef, tempo, instrument, tie, metadata
sys.path.insert(0, "scripts")
from build_score import consensus_caps, PARTS, MASTER, fix_measure
from config import SLUG

TS = {F(3, 2): "3/8", F(3): "3/4", F(2): "2/4", F(4): "4/4"}


def part_stream(pid, name, prog, cl, caps, keys):
    ms = json.load(open(f"build/{pid}.json"))
    p = stream.Part(id=pid)
    p.partName = name
    inst = instrument.Instrument(); inst.instrumentName = name; inst.midiProgram = prog
    p.insert(0, inst)
    prev_cap, prev_key = None, None
    pending_tie = None
    for i, m in enumerate(ms):
        cap = caps[i]
        mm = stream.Measure(number=i + 1)
        if i == 0:
            mm.insert(0, clef.TrebleClef() if cl == "G" else clef.BassClef())
        if cap != prev_cap:
            mm.insert(0, meter.TimeSignature(TS.get(cap) or f"{int(cap * 2)}/8")); prev_cap = cap
        if keys[i] != prev_key:
            mm.insert(0, key.KeySignature(keys[i])); prev_key = keys[i]
        ev, _ = fix_measure(m, cap, pid)
        for e in ev:
            ql = e["ql"]
            if e["t"] == "r":
                n = note.Rest(quarterLength=ql)
                if ql == cap:
                    n.fullMeasure = True
            else:
                n = note.Note(e["midi"], quarterLength=ql)
                if pending_tie is not None and pending_tie == e["midi"]:
                    n.tie = tie.Tie("stop" if not e.get("tie") else "continue")
                elif e.get("tie"):
                    n.tie = tie.Tie("start")
                pending_tie = e["midi"] if e.get("tie") else None
            mm.append(n)
        p.append(mm)
    return p


def main():
    master = json.load(open(f"build/{MASTER}.json"))
    caps = consensus_caps(master)
    from config import PICKUP
    if PICKUP:
        caps[0] = sum((F(e["ql"]) for e in master[0]["events"]), F(0)) or caps[0]
    keys = [m["key"] for m in master]
    sc = stream.Score()
    from config import CFG
    sc.insert(0, metadata.Metadata(title=CFG["title"], composer=CFG.get("composer", "")))
    for pid, name, prog, cl in PARTS:
        p = part_stream(pid, name, prog, cl, caps, keys)
        p.write("musicxml", fp=f"out/{pid}.musicxml")
        sc.insert(0, p)
    sc.write("musicxml", fp=f"out/{SLUG}_completa.musicxml")
    sc.write("midi", fp=f"out/{SLUG}_completa.mid")


if __name__ == "__main__":
    main()
