"""Overlay study annotations on the original PDF of my part + append a study-guide page."""
import json, io
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor, Color

pdfmetrics.registerFont(TTFont("DV", "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf"))
pdfmetrics.registerFont(TTFont("DVB", "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf"))

from config import CFG, ME, PDF, SHORT, SLUG, npages
PALETTE = ["#1f6fd1", "#1a9a4a", "#8a3fc7", "#0e9aa7", "#9a5b1a", "#c2185b", "#5d7a00", "#00838f"]
OTHERS = [p["id"] for p in CFG["parts"] if p["id"] != ME]
COL = {pid: PALETTE[i % len(PALETTE)] for i, pid in enumerate(OTHERS)}
COL.update({"propia": "#6b6b6b", "solo": "#d12f2f"})
SHORT2KEY = {SHORT[p]: p for p in OTHERS}
MYNAME = next(p["name"] for p in CFG["parts"] if p["id"] == ME)

an = json.load(open(f"out/analysis_{ME}.json"))
boxes = {int(k): v for k, v in json.load(open(f"build/{ME}_boxes.json")).items()}
src = PdfReader(PDF[ME])
W, H = float(src.pages[0].mediabox.width), float(src.pages[0].mediabox.height)


def key_of(nt):
    if nt["kind"] == "con":
        for s, k in SHORT2KEY.items():
            if nt["text"].startswith("Vas con " + s):
                return k
    return nt["kind"]


def short_label(nt):
    t = nt["text"]
    if nt["kind"] == "con":
        t = t.split(" (")[0].replace("Vas con ", "con ")
        t = t.replace("con el mismo ritmo", "mismo ritmo")
        return t
    if nt["kind"] == "propia":
        return "tu línea" + (" · melodía: " + t.split("la lleva ")[1].rstrip(")") if "la lleva" in t else "")
    if nt["kind"] == "solo":
        return "¡SOLO!"
    return t


def x_range(n):
    b = boxes[n]
    x0 = b["x0"] if b["x0"] is not None else b["x1"] - 45
    return x0, b["x1"]


def runs(n0, n1):
    """split measure range into per-(page, staff) runs"""
    out = []
    for n in range(n0, n1 + 1):
        b = boxes[n]
        k = (b["page"], round(b["top"]))
        if out and out[-1][0] == k:
            out[-1][1].append(n)
        else:
            out.append((k, [n]))
    return out


overlays = {p: [] for p in range(1, npages(ME) + 1)}
for nt in an["notes"]:
    for (p, top), ns in runs(nt["start"], nt["end"]):
        overlays[p].append((nt, ns))


def draw_page(c, p):
    lanes = {}
    for nt, ns in overlays[p]:
        b0 = boxes[ns[0]]
        x0, _ = x_range(ns[0]); _, x1 = x_range(ns[-1])
        top_pdf = H - b0["top"]  # staff top line in PDF coords
        bot_pdf = H - b0["bot"]
        kind = nt["kind"]
        if kind == "dificil":
            c.setFillColor(Color(1, 0.6, 0, alpha=0.16)); c.setStrokeColor(Color(1, 0.5, 0, alpha=0.8))
            c.setLineWidth(0.8)
            c.roundRect(x0 + 1, bot_pdf - 6, x1 - x0 - 2, top_pdf - bot_pdf + 12, 3, stroke=1, fill=1)
            c.setFillColor(HexColor("#d97a00")); c.setFont("DVB", 6)
            c.drawString(x0 + 2, bot_pdf - 12.5, "⚠ difícil")
        elif kind == "entrada":
            c.setFillColor(HexColor("#d12f2f"))
            xm = x0 + 4
            p_ = c.beginPath(); p_.moveTo(xm, top_pdf + 4); p_.lineTo(xm + 5, top_pdf + 4); p_.lineTo(xm + 2.5, top_pdf); p_.close()
            c.drawPath(p_, fill=1, stroke=0)
            cue = nt["text"].split("Escucha antes a ")[1].split(".")[0] if "Escucha antes a " in nt["text"] else ""
            c.setFont("DVB", 6.2)
            c.drawString(xm, bot_pdf - 13 if False else top_pdf + 19, "ENTRA" + (f" · escucha {cue}" if cue else ""))
        else:
            k = key_of(nt)
            col = HexColor(COL.get(k, "#555555"))
            y = top_pdf + 8
            c.setStrokeColor(col); c.setLineWidth(1.6)
            c.line(x0 + 2, y, x1 - 2, y)
            c.line(x0 + 2, y, x0 + 2, y - 3); c.line(x1 - 2, y, x1 - 2, y - 3)
            c.setFillColor(col); c.setFont("DVB", 6.2)
            lab = short_label(nt)
            # keep label within bracket width when possible
            maxw = max(x1 - x0 - 4, 40)
            while pdfmetrics.stringWidth(lab, "DVB", 6.2) > maxw and len(lab) > 8:
                lab = lab[:-2]
            c.drawString(x0 + 3, y + 2, lab)
    # legend on page 1 bottom
    if p == 1:
        c.setFont("DVB", 6.5); c.setFillColor(HexColor("#222222"))
        x, y = 40, 14
        c.drawString(x, y, "Guía " + SHORT[ME] + ":")
        x += 52
        for k, name in [(o, "con " + SHORT[o]) for o in OTHERS] + [("propia", "tu línea")]:
            c.setStrokeColor(HexColor(COL[k])); c.setLineWidth(1.6); c.line(x, y + 2, x + 12, y + 2)
            c.setFillColor(HexColor(COL[k])); c.drawString(x + 14, y, name); x += 20 + pdfmetrics.stringWidth(name, "DVB", 6.5)
        c.setFillColor(HexColor("#d12f2f")); c.drawString(x, y, "▼ entrada"); x += 42
        c.setFillColor(HexColor("#d97a00")); c.drawString(x, y, "⚠ pasaje difícil")


def guide_pages():
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))
    y = H - 50

    def line(t, font="DV", size=8.5, color="#222222", indent=0, gap=12):
        nonlocal y
        if y < 50:
            c.showPage(); y = H - 50
        c.setFont(font, size); c.setFillColor(HexColor(color)); c.drawString(45 + indent, y, t); y -= gap

    line(f"{CFG['title']} — Guía de estudio · {MYNAME}", "DVB", 13, gap=18)
    line("Análisis automático a partir de las particellas. Revísalo en el ensayo: puede haber algún error de lectura.", "DV", 8, "#666666", gap=18)
    for s in an["sections"]:
        line(f"{s['name']}  (c. {s['start'] + an.get('offset', 0)}–{s['end'] + an.get('offset', 0)})", "DVB", 10, gap=13)
        items = [nt for nt in an["notes"] if s["start"] <= nt["start"] <= s["end"]]
        if not items:
            line("Descansas toda la sección.", "DV", 8.5, "#666666", 10)
        for nt in items:
            o = an.get("offset", 0)
            rng = f"c. {nt['start'] + o}" + (f"–{nt['end'] + o}" if nt["end"] != nt["start"] else "")
            col = {"entrada": "#d12f2f", "dificil": "#d97a00"}.get(nt["kind"], COL.get(key_of(nt), "#333333"))
            line(f"{rng}:  {nt['text']}", "DV", 8.2, col, 10, gap=11)
        y -= 6
    c.save()
    return PdfReader(io.BytesIO(buf.getvalue()))


w = PdfWriter()
for i, page in enumerate(src.pages):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))
    draw_page(c, i + 1)
    c.save()
    ov = PdfReader(io.BytesIO(buf.getvalue())).pages[0]
    page.merge_page(ov)
    w.add_page(page)
for pg in guide_pages().pages:
    w.add_page(pg)
w.write(f"out/{SLUG}_{ME}_anotada.pdf")
print("ok")
