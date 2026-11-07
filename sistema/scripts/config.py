"""Piece configuration (piece.json in the working folder) shared by all scripts."""
import json, subprocess, re

CFG = json.load(open("piece.json"))
import os
MASTER = CFG["me"]
ME = os.environ.get("ME") or CFG["me"]
PICKUP = 1 if CFG.get("pickup") else 0  # anacrusis printed as measure 0
TOTAL = CFG["total_measures"] + PICKUP
OFFSET = -PICKUP  # printed number = internal index + OFFSET
PARTS = [(p["id"], p["name"], p["program"], p["clef"]) for p in CFG["parts"]]
SHORT = {p["id"]: p["short"] for p in CFG["parts"]}
PDF = {p["id"]: "parts/" + p["pdf"] for p in CFG["parts"]}


def npages(pid):
    out = subprocess.run(["pdfinfo", PDF[pid]], capture_output=True, text=True).stdout
    return int(re.search(r"Pages:\s+(\d+)", out).group(1))


def pagewidth(pid):
    out = subprocess.run(["pdfinfo", PDF[pid]], capture_output=True, text=True).stdout
    return float(re.search(r"Page size:\s+([\d.]+) x", out).group(1))


def overrides():
    o = {}
    for k, v in CFG.get("overrides", {}).items():
        pid, n = k.split(":")
        o[(pid, int(n))] = [(a, b) for a, b in v]
    return o

import unicodedata
SLUG = re.sub(r"[^A-Za-z0-9]+", "_", unicodedata.normalize("NFKD", CFG["title"]).encode("ascii", "ignore").decode()).strip("_")
