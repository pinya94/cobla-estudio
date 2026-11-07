"""Extract layout info per page: staff (system) y positions, system-start measure numbers,
multirest numerals. Coordinates in PDF points (72 dpi)."""
import json, re, subprocess, sys
from PIL import Image
import numpy as np

DPI = 300
SCALE = 72 / DPI


def staves(png):
    im = np.array(Image.open(png).convert("L")) < 128
    frac = im.mean(axis=1)
    rows = np.where(frac > 0.6)[0]
    # group consecutive rows into lines
    lines = []
    for r in rows:
        if lines and r - lines[-1][-1] <= 2:
            lines[-1].append(r)
        else:
            lines.append([r])
    ys = [np.mean(l) for l in lines]
    # group into staves of 5 lines with similar spacing
    st = []
    i = 0
    while i + 4 < len(ys):
        grp = ys[i:i + 5]
        d = np.diff(grp)
        if d.max() < 40 and d.min() > 15:
            st.append((grp[0] * SCALE, grp[4] * SCALE))
            i += 5
        else:
            i += 1
    return st


def words(pdf, page):
    out = subprocess.run(["pdftotext", "-bbox", "-enc", "UTF-8", "-f", str(page), "-l", str(page), pdf, "-"],
                         capture_output=True, text=True).stdout
    ws = []
    for m in re.finditer(r'xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)<', out):
        x0, y0, x1, y1 = map(float, m.groups()[:4])
        ws.append(dict(x0=x0, y0=y0, x1=x1, y1=y1, t=m.group(5)))
    return ws


def shift(s):
    # big music-font digits are encoded with an offset of -1 ('/' = 0)
    return "".join(str((ord(c) - ord('/')) % 10) if c in "/0123456789" else "?" for c in s)


def ocr_multirests(png, top, bot):
    """Find multirest bars (thick bar on the middle line) in one staff and OCR the number above.
    Returns [(x_pt, count)]."""
    import pytesseract
    img = Image.open(png).convert("L")
    a = np.array(img) < 128
    t, b = int(round(top / SCALE)), int(round(bot / SCALE))
    sp = (b - t) / 4
    mid = (t + b) / 2
    band = a[int(mid - sp * 0.12):int(mid + sp * 0.12) + 1]
    col = band.mean(axis=0) > 0.95
    res = []
    x = 0
    W = a.shape[1]
    while x < W:
        if col[x]:
            x0 = x
            while x < W and col[x]:
                x += 1
            def has_end(cx):
                c0, c1 = max(0, cx - 4), min(W, cx + 5)
                seg = a[int(mid - sp * 0.9):int(mid + sp * 0.9) + 1, c0:c1].any(axis=1)
                return seg.mean() > 0.9
            if x - x0 > 2.5 * sp and has_end(x0) and has_end(x - 1):
                from PIL import ImageOps
                crop = img.crop((x0 + int(sp * 0.3), int(t - 2.6 * sp), x - int(sp * 0.3), int(t - 0.3 * sp)))
                arr = np.array(crop) < 128
                ys, xs = np.where(arr)
                if len(ys):
                    # keep only the lowest line of ink (the number), dropping text such as tempo or "PONT" above it
                    rows = np.where(arr.any(axis=1))[0]
                    y1 = rows.max(); y0 = y1
                    while y0 - 1 in set(rows) or (y0 - 2 in set(rows)):
                        y0 -= 1
                    sub = arr[y0:y1 + 1]
                    cols = np.where(sub.any(axis=0))[0]
                    crop = crop.crop((cols.min(), y0, cols.max() + 1, y1 + 1))
                crop = ImageOps.expand(crop, border=20, fill=255)
                txt = pytesseract.image_to_string(crop, config="--psm 7 -c tessedit_char_whitelist=0123456789").strip()
                if not txt.isdigit():
                    cx = (x0 + x) / 2
                    for hw in (0.75, 1.3, 1.9):
                        c2 = img.crop((int(cx - hw * sp), int(t - 2.05 * sp), int(cx + hw * sp), int(t - 0.2 * sp)))
                        ar2 = np.array(c2) < 128
                        if not ar2.any():
                            continue
                        yy, xx = np.where(ar2)
                        c2 = ImageOps.expand(c2.crop((xx.min(), yy.min(), xx.max() + 1, yy.max() + 1)), border=20, fill=255)
                        t2 = pytesseract.image_to_string(c2, config="--psm 7 -c tessedit_char_whitelist=0123456789").strip()
                        if t2.isdigit():
                            txt = t2
                            break
                if not txt.isdigit():
                    eng = _rapid()
                    cx = (x0 + x) / 2
                    for hw in (1.9, 1.3, 0.75):
                        c2 = img.crop((int(cx - hw * sp), int(t - 2.3 * sp), int(cx + hw * sp), int(t - 0.15 * sp)))
                        c2 = ImageOps.expand(c2, border=30, fill=255).convert("RGB")
                        r = eng(np.array(c2))
                        cand = [re.sub(r"\D", "", z) for z in (r.txts or [])]
                        cand = [z for z in cand if z]
                        if cand:
                            txt = cand[-1]
                            break
                if txt.isdigit():
                    res.append(((x0 + x) / 2 * SCALE, int(txt)))
                else:
                    res.append(((x0 + x) / 2 * SCALE, None))
        x += 1
    return res


_ENG = None


def _rapid():
    global _ENG
    if _ENG is None:
        import logging
        logging.getLogger("RapidOCR").setLevel(logging.ERROR)
        from rapidocr import RapidOCR
        _ENG = RapidOCR()
    return _ENG


def is_musescore(pdf):
    out = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True).stdout
    return "MuseScore" in out


def page_layout(pdf, png, page):
    st = staves(png)
    ws = words(pdf, page)
    pw = Image.open(png).width * SCALE
    systems = [dict(top=t, bot=b, start=None, multirests=[], pw=pw) for t, b in st]

    def nearest(y):
        best = None
        for i, s in enumerate(systems):
            d = 0 if s['top'] - 25 <= y <= s['bot'] + 10 else min(abs(y - s['top']), abs(y - s['bot']))
            if best is None or d < best[0]:
                best = (d, i)
        return best[1]

    smufl = any(any(0xE000 <= ord(c) <= 0xF8FF for c in w['t']) for w in ws)  # MuseScore (SMuFL font)
    if smufl:
        big0 = [dict(w, t="".join(chr(ord('/') + ord(c) - 0xE080) if 0xE080 <= ord(c) <= 0xE089 else "x" for c in w['t']))
                for w in ws if any(0xE080 <= ord(c) <= 0xE089 for c in w['t'])]
        big0 = [w for w in big0 if re.fullmatch(r'[/0-9]+', w['t'])]
    else:
        big0 = [w for w in ws if 40 < (w['y1'] - w['y0']) < 52 and re.fullmatch(r'[/0-9]+', w['t'])]
    big = []
    for w in big0:
        n = len(w['t']); cw = (w['x1'] - w['x0']) / n
        for k, ch in enumerate(w['t']):
            big.append(dict(w, x0=w['x0'] + k * cw, x1=w['x0'] + (k + 1) * cw, t=ch, wid=id(w)))
    for w in ws:
        h = w['y1'] - w['y0']
        if re.fullmatch(r'\d+', w['t']) and w['x0'] < 50 and 7 < h < 11.5:
            # system start number sits just above the staff top
            ycen = (w['y0'] + w['y1']) / 2
            i = nearest(ycen + 8)
            if abs(systems[i]['top'] - (ycen + 8)) > 30:
                continue  # page number or other stray digits, not a measure number
            systems[i]['start'] = int(w['t'])
    # big digits: time signatures come as stacked pairs at same x; multirest numbers stand alone
    used = set()
    for a in range(len(big)):
        for b in range(len(big)):
            if a != b and abs((big[a]['x0']+big[a]['x1']) - (big[b]['x0']+big[b]['x1'])) < 4 and 5 < abs(big[a]['y0'] - big[b]['y0']) < 15:
                used.add(a); used.add(b)
    # re-join adjacent unused chars from the same word into numbers
    groups = []
    for k, w in enumerate(big):
        if k in used:
            continue
        if groups and groups[-1]['wid'] == w['wid'] and groups[-1]['last'] == k - 1:
            groups[-1]['t'] += w['t']; groups[-1]['last'] = k
        else:
            groups.append(dict(w, last=k))
    for w in groups:
        # glyph box is tall; visual baseline region - take box center minus offset
        ycen = w['y0'] + (35 if smufl else 25)
        i = nearest(ycen)
        systems[i]['multirests'].append((w['x0'], int(shift(w['t']))))
    if is_musescore(pdf):
        # MuseScore: use SMuFL digits from the text layer when present, else OCR the multirest numbers
        for s in systems:
            found = ocr_multirests(png, s['top'], s['bot'])
            txt = sorted(s['multirests'])
            if smufl and len(txt) == len(found) and txt:
                # same multirests found both ways: the text-layer digits are exact, OCR may misread (9 -> 3)
                found = [(x, n) for (x, _), (_, n) in zip(sorted(found), txt)]
            s['multirests'] = [(x, n if n is not None else 1) for x, n in found]
            s['ocr_fail'] = sum(1 for _, n in found if n is None)
    for s in systems:
        s['mr_x'] = [x for x, _ in sorted(s['multirests'])]
        s['multirests'] = [n for _, n in sorted(s['multirests'])]
    return systems


if __name__ == "__main__":
    part = sys.argv[1]
    res = []
    from config import PDF, npages
    for p in range(1, npages(part) + 1):
        res.append(page_layout(PDF[part], f"img/{part}-{p}.png", p))
    print(json.dumps(res, indent=1))
