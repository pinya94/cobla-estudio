"""Build the web folder of one piece (all voices): python3 scripts/build_site.py <site_dir>
Needs: build/<part>.json for every part (assemble + build done), out/score.json, img/<part>-<n>.png.
Writes <site_dir>/<SLUG>/ with index.html, data.js, img/, pdf/, files."""
import json, os, subprocess, sys, shutil
from PIL import Image
sys.path.insert(0, "scripts")
from config import CFG, SLUG, PDF, npages


def page_size(pdf):
    import re
    info = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True).stdout
    return tuple(map(float, re.search(r"Page size:\s+([\d.]+) x ([\d.]+)", info).groups()))


def main(site):
    dest = os.path.join(site, SLUG)
    os.makedirs(f"{dest}/img", exist_ok=True); os.makedirs(f"{dest}/pdf", exist_ok=True)
    score = json.load(open("out/score.json"))
    voices = {}
    an = None
    for p in CFG["parts"]:
        v = p["id"]
        env = dict(os.environ, ME=v)
        subprocess.run([sys.executable, "scripts/run.py", "boxes"], env=env, check=True)
        subprocess.run([sys.executable, "scripts/analyze.py"], env=env, check=True, stdout=subprocess.DEVNULL)
        subprocess.run([sys.executable, "scripts/annotate_pdf.py"], env=env, check=True, stdout=subprocess.DEVNULL)
        an = json.load(open(f"out/analysis_{v}.json"))
        boxes = {int(k): {kk: (round(float(vv), 1) if isinstance(vv, (int, float)) and kk != "page" else vv) for kk, vv in b.items()}
                 for k, b in json.load(open(f"build/{v}_boxes.json")).items()}
        n = npages(v)
        for i in range(1, n + 1):
            im = Image.open(f"img/{v}-{i}.png").convert("L")
            im = im.resize((im.width * 130 // 300, im.height * 130 // 300), Image.LANCZOS)
            im.save(f"{dest}/img/{v}-{i}.jpg", quality=72, optimize=True)
        pw, ph = page_size(PDF[v])
        voices[v] = dict(boxes=boxes, notes=an["notes"], pages=n, pageW=pw, pageH=ph)
        shutil.copy(f"out/{SLUG}_{v}_anotada.pdf", f"{dest}/pdf/{v}.pdf")
    for ext in ("musicxml", "mid"):
        shutil.copy(f"out/{SLUG}_completa.{ext}", f"{dest}/{SLUG}.{ext}")
    cfg = dict(title=CFG["title"], me=CFG["me"],
               parts=[{k: p[k] for k in ("id", "name", "short", "timbre", "role")} for p in CFG["parts"]],
               sections=CFG["sections"])
    data = dict(offset=an.get("offset", 0), config=cfg, measures=score["measures"], parts=score["parts"], sections=an["sections"], voices=voices,
                files=dict(xml=f"{SLUG}.musicxml", mid=f"{SLUG}.mid"))
    with open(f"{dest}/data.js", "w") as f:
        f.write("window.DATA=" + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";")
    shutil.copy("scripts/site_template.html", f"{dest}/index.html")
    meta = dict(slug=SLUG, title=CFG["title"], subtitle=CFG.get("subtitle", ""), composer=CFG.get("composer", ""),
                voices=[p["name"] for p in CFG["parts"]], measures=len(score["measures"]),
                notes=CFG.get("site_note", ""))
    json.dump(meta, open(f"{dest}/meta.json", "w"), ensure_ascii=False)
    print("site ok:", dest)


if __name__ == "__main__":
    main(sys.argv[1])
