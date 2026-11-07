"""Pipeline completo: python3 scripts/run.py [paso]
Pasos: render, omr, assemble, build, export, boxes, analyze, annotate, app, all (por defecto).
Requiere piece.json y las particellas PDF en parts/."""
import os, sys, subprocess, json
sys.path.insert(0, os.path.dirname(__file__))
from config import CFG, ME, PDF, npages

PIDS = [p["id"] for p in CFG["parts"]]


def sh(cmd):
    print("$", cmd); subprocess.run(cmd, shell=True, check=True)


def render():
    os.makedirs("img", exist_ok=True); os.makedirs("app", exist_ok=True)
    for pid in PIDS:
        if not os.path.exists(f"img/{pid}-1.png"):
            sh(f'pdftoppm -r 300 -png "{PDF[pid]}" img/{pid}')
        # pdftoppm pads page numbers when >9 pages; normalise
        for f in os.listdir("img"):
            if f.startswith(pid + "-0"):
                os.rename(f"img/{f}", f"img/{pid}-{int(f[len(pid)+1:-4])}.png")
    sh(f'pdftoppm -r 130 -jpeg -jpegopt quality=72 "{PDF[ME]}" app/pg')
    for f in os.listdir("app"):
        if f.startswith("pg-0"):
            os.rename(f"app/{f}", f"app/pg-{int(f[3:-4])}.jpg")


def omr():
    os.makedirs("omr", exist_ok=True)
    for pid in PIDS:
        for p in range(1, npages(pid) + 1):
            if not os.path.exists(f"omr/{pid}-{p}.musicxml"):
                sh(f"cp img/{pid}-{p}.png omr/ && cd omr && homr {pid}-{p}.png > {pid}-{p}.log 2>&1")


def assemble():
    for pid in PIDS:
        sh(f"python3 scripts/assemble.py {pid}")


def boxes():
    sys.argv = ["x"]
    from barlines import measure_boxes
    b, r = measure_boxes(ME)
    bad = [x for x in r if x[2] != x[3]]
    if bad:
        print("AVISO: sistemas con barras no cuadradas (p, sistema, compases modelo, barras):", bad)
    json.dump({k: {kk: (float(vv) if vv is not None and kk != "page" else vv) for kk, vv in v.items()} for k, v in b.items()},
              open(f"build/{ME}_boxes.json", "w"))


STEPS = dict(render=render, omr=omr, assemble=assemble,
             build=lambda: sh("python3 scripts/build_score.py"), export=lambda: sh("python3 scripts/export.py"),
             boxes=boxes, analyze=lambda: sh("python3 scripts/analyze.py"),
             annotate=lambda: sh("python3 scripts/annotate_pdf.py"), app=lambda: sh("python3 scripts/build_app.py"))

if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else "all"
    os.makedirs("build", exist_ok=True); os.makedirs("out", exist_ok=True)
    order = list(STEPS) if step == "all" else [step]
    for s in order:
        print(f"\n===== {s} =====")
        STEPS[s]()
