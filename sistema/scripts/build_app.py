import json, base64, glob
from config import CFG, ME, SLUG, npages
score = json.load(open("out/score.json"))
an = json.load(open(f"out/analysis_{ME}.json"))
boxes = {int(k): {kk: (round(float(vv), 1) if isinstance(vv, (int, float)) and kk != "page" else vv) for kk, vv in v.items()}
         for k, v in json.load(open(f"build/{ME}_boxes.json")).items()}
cfg = dict(title=CFG["title"], me=ME, parts=[{k: p[k] for k in ("id", "name", "short", "timbre", "role")} for p in CFG["parts"]],
           sections=CFG["sections"])
import subprocess, re
from config import PDF
info = subprocess.run(["pdfinfo", PDF[ME]], capture_output=True, text=True).stdout
pw, ph = map(float, re.search(r"Page size:\s+([\d.]+) x ([\d.]+)", info).groups())
data = dict(pageW=pw, pageH=ph, config=cfg, measures=score["measures"], parts=score["parts"],
            analysis=dict(sections=an["sections"], notes=an["notes"]), boxes=boxes)
pages = ["data:image/jpeg;base64," + base64.b64encode(open(f"app/pg-{i}.jpg", "rb").read()).decode() for i in range(1, npages(ME) + 1)]
t = open("scripts/template.html").read()
t = t.replace("/*DATA*/null", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
t = t.replace("/*PAGES*/[]", json.dumps(pages))
out = f"out/Estudio_{SLUG}_{ME}.html"
open(out, "w").write(t)
print(out, len(t) // 1024, "KB")
