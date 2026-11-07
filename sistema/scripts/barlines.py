"""Find barline x positions per staff and map model measures -> boxes on the PDF page (points)."""
import json, sys
import numpy as np
from PIL import Image
sys.path.insert(0, "scripts")
from layout import staves, page_layout, SCALE


def barlines(png):
    img = np.array(Image.open(png).convert("L")) < 128
    res = []
    for top, bot in staves(png):
        t, b = int(round(top / SCALE)), int(round(bot / SCALE))
        band = img[t:b + 1]
        frac = band.mean(axis=0)
        above = img[max(0, t - 12):t - 3].mean(axis=0)
        below = img[b + 3:b + 12].mean(axis=0)
        cols = np.where((frac > 0.97) & (above < 0.75) & (below < 0.75))[0]
        # stems sit next to noteheads; barlines have mostly empty staff on both sides
        def side(c, lo, hi):
            x0, x1 = max(0, c + lo), min(band.shape[1], c + hi)
            return band[:, x0:x1].mean() if x1 > x0 else 0
        runs = []
        for c in cols:
            if runs and c - runs[-1][-1] <= 3:
                runs[-1].append(c)
            else:
                runs.append([c])
        keep = []
        for r in runs:
            thick = len(r) >= 6
            lim = 0.5 if thick else 0.3
            # double / repeat barlines: look past the neighbouring line too
            if side(r[0], -11, -3) < lim + 0.05 and side(r[-1], 3, 11) < lim + 0.05 or thick:
                keep.extend(r)
            elif side(r[0], -16, -4) < 0.3 or side(r[-1], 4, 16) < 0.3:
                # thin line next to a thick one (double bar / repeat)
                near = [q for q in runs if q is not r and len(q) >= 6 and min(abs(q[0] - r[-1]), abs(r[0] - q[-1])) < 25]
                if near:
                    keep.extend(r)
        cols = np.array(sorted(keep), dtype=int)
        xs = []
        for c in cols:
            if xs and c - xs[-1][-1] <= 3:
                xs[-1].append(c)
            else:
                xs.append([c])
        groups = []
        for g in xs:
            x = np.mean(g)
            if groups and x - groups[-1][-1] < 25:  # double bar
                groups[-1].append(x)
            else:
                groups.append([x])
        # drop start-repeat / header lines right after clef, key and time signature
        sp = (b - t) / 4
        row = img[t]
        left = int(np.argmax(row)) if row.any() else 0
        groups = [g for g in groups if g[-1] - left > 6 * sp]
        res.append(dict(top=top, bot=bot, bars=[(g[0] * SCALE, g[-1] * SCALE) for g in groups]))
    return res


def measure_boxes(part):
    meas = json.load(open(f"build/{part}.json"))
    boxes = {}
    report = []
    from config import npages
    for p in range(1, npages(part) + 1):
        bl = barlines(f"img/{part}-{p}.png")
        for si, st in enumerate(bl):
            ms = [m for m in meas if m["page"] == p and m["system"] == si]
            # visual measures: consecutive multirest measures created from one OMR measure collapse to one box
            vis = []
            for m in ms:
                if m.get("rest") and vis and vis[-1][0].get("rest") and not m.get("time") and vis[-1][0].get("mrgroup") == m.get("mrgroup"):
                    vis[-1].append(m)
                else:
                    vis.append([m])
            bars = list(st["bars"])
            # reconcile detected barlines with the number of visual measures
            n_need = len(vis)
            def segs(bs):
                return [(bs[k][0] - (bs[k - 1][1] if k else 60)) for k in range(len(bs))]
            while len(bars) > n_need and len(bars) > 1:
                w = segs(bars)
                k = min(range(len(bars) - 1), key=lambda q: w[q])  # never drop the final barline
                bars.pop(k)
            while len(bars) < n_need and bars:
                w = segs(bars)
                k = max(range(len(bars)), key=lambda q: w[q])
                left = bars[k - 1][1] if k else 60
                mid = (left + bars[k][0]) / 2
                bars.insert(k, (mid, mid))
            # first box starts after clef/key/time: use staff start x from the first barline gap heuristic
            left = 60 if si else 60
            edges = [b[1] for b in bars]
            n_vis = len(edges)
            report.append((p, si, len(vis), len(st["bars"])))
            for k, g in enumerate(vis[:n_vis]):
                x0 = edges[k - 1] if k > 0 else None
                x1 = bars[k][0]
                for m in g:
                    boxes[m["n"]] = dict(page=p, x0=x0, x1=x1, top=st["top"], bot=st["bot"], span=len(g))
    # measures whose staff was not detected: reuse the nearest previous box so nothing breaks downstream
    for m in meas:
        if m["n"] not in boxes:
            prev = [k for k in boxes if k < m["n"]]
            if prev:
                boxes[m["n"]] = dict(boxes[max(prev)])
                report.append(("fallback", m["n"], 0, 0))
    return boxes, report


if __name__ == "__main__":
    b, r = measure_boxes(sys.argv[1])
    for x in r:
        print(x)
