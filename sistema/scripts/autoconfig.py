"""Fill piece.json automatically after OMR: total_measures, tempo, sections (from double bars / meter / key changes).
python3 scripts/autoconfig.py [--title "..."]   (keeps fields already set by hand when --keep is given)"""
import json, re, subprocess, sys, os
from collections import Counter
from fractions import Fraction as F
sys.path.insert(0, "scripts")

cfg = json.load(open("piece.json"))
pdf = lambda pid: "parts/" + next(p["pdf"] for p in cfg["parts"] if p["id"] == pid)


def npages(pid):
    out = subprocess.run(["pdfinfo", pdf(pid)], capture_output=True, text=True).stdout
    return int(re.search(r"Pages:\s+(\d+)", out).group(1))


def total_for(pid):
    from layout import page_layout
    from assemble import parse_page
    n = npages(pid)
    lay = page_layout(pdf(pid), f"img/{pid}-{n}.png", n)
    sysx = parse_page(f"omr/{pid}-{n}.musicxml")
    if not lay or not sysx:
        return None
    last_l, last_s = lay[-1], sysx[-1]
    if last_l["start"] is None:
        return None
    mrs = last_l["multirests"]
    flagged = sum(1 for m in last_s if m["multirest"] is not None)
    k = max(len(mrs), flagged)
    return last_l["start"] + len(last_s) - 1 + sum(mrs) - min(k, len(mrs))


def tempo():
    for p in cfg["parts"]:
        txt = subprocess.run(["pdftotext", "-f", "1", "-l", "1", pdf(p["id"]), "-"], capture_output=True, text=True).stdout
        m = re.search(r"=\s*(\d{2,3})", txt)
        if m:
            return int(m.group(1))
    return None


def main():
    keep = "--keep" in sys.argv
    tots = [t for t in (total_for(p["id"]) for p in cfg["parts"]) if t]
    tot = Counter(tots).most_common(1)[0][0]
    print("totales por voz:", tots, "->", tot)
    if not (keep and cfg.get("total_measures")):
        cfg["total_measures"] = tot
    json.dump(cfg, open("piece.json", "w"), ensure_ascii=False, indent=1)
    # assemble master to find structure
    subprocess.run([sys.executable, "scripts/assemble.py", cfg["me"]], check=True, stdout=subprocess.DEVNULL)
    ms = json.load(open(f"build/{cfg['me']}.json"))
    bpm = tempo()
    starts = [1]
    for i, m in enumerate(ms[:-1]):
        nxt = ms[i + 1]
        if (m.get("barline") or "") in ("light-light", "light-heavy", "heavy-light") or nxt.get("time") or (nxt["key"] != m["key"]):
            starts.append(i + 2)
    # merge sections shorter than 4 measures into the previous one
    clean = []
    for s in starts:
        if clean and s - clean[-1] < 4:
            continue
        clean.append(s)
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    secs = []
    for k, s in enumerate(clean):
        cap = F(ms[s - 1]["cap"]) if ms[s - 1].get("cap") else F(1)
        beat = 1.5 if cap in (F(3, 2), F(3)) and "8" in str(ms[s - 1].get("time") or "") else 1
        # compound meters (6/8, 3/8, 9/8, 12/8): beat = dotted quarter
        if cap in (F(3, 2), F(9, 2), F(6)) or (cap == F(3) and beat == 1.5):
            beat = 1.5
        secs.append(dict(start=s, name=("Introducción" if k == 0 and len(clean) > 1 else f"Parte {letters[k % 26]}"),
                         bpm=bpm or (66 if beat == 1.5 else 96), beat=beat))
    if not (keep and len(cfg.get("sections", [])) > 1):
        cfg["sections"] = secs
    json.dump(cfg, open("piece.json", "w"), ensure_ascii=False, indent=1)
    print("tempo:", bpm, "secciones:", [(s["start"], s["name"]) for s in cfg["sections"]])


if __name__ == "__main__":
    main()
