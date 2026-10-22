#!/usr/bin/env python3
"""Merge the 16:9 Code Purple deck with its portrait pulse page; add bookmarks and metadata.

Usage: python merge_deck.py [--build DIR] [--out FILE] [--census FILE]
Inputs come from build_deck.js (BUILD/deck_landscape.pdf, deck_portrait.pdf, deck_sections.json).
"""
import argparse
import json
from pathlib import Path

from pypdf import PdfReader, PdfWriter

ROOT = Path(__file__).resolve().parents[1]
PORTRAIT_AT = 9  # the portrait pulse detail follows slide 09


def count_links(pdf: Path) -> tuple[int, int, int]:
    r = PdfReader(str(pdf))
    links = internal = 0
    for pg in r.pages:
        for a in pg.get("/Annots") or []:
            o = a.get_object()
            if o.get("/Subtype") != "/Link":
                continue
            links += 1
            if "/Dest" in o or (o.get("/A") or {}).get("/S") == "/GoTo":
                internal += 1
    return len(r.pages), links, internal


def merge(build: Path, out: Path, subject: str) -> tuple[int, int, int]:
    w = PdfWriter(clone_from=str(build / "deck_landscape.pdf"))
    w.insert_page(PdfReader(str(build / "deck_portrait.pdf")).pages[0], index=PORTRAIT_AT)
    w.add_metadata({"/Title": "Global Code Purple", "/Author": "GBO (prepared with Claude)", "/Subject": subject})
    for name, idx in json.loads((build / "deck_sections.json").read_text()):
        w.add_outline_item(name, idx)  # build_deck.js numbers pages with the portrait page already counted
        if name.startswith("C"):
            w.add_outline_item("    Pulse, portrait detail", PORTRAIT_AT)
    w.page_mode = "/UseOutlines"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wb") as fh:
        w.write(fh)
    return count_links(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", default=str(ROOT / "build"))
    ap.add_argument("--out", default=str(ROOT / "build" / "Code-Purple-deck.pdf"))
    ap.add_argument("--census", default=None)
    a = ap.parse_args()
    cands = [a.census, ROOT / "kit/out/census.json", ROOT / "site/code-purple/kit/census.json"]
    census = next(Path(c) for c in cands if c and Path(c).is_file())
    c = json.loads(census.read_text())
    subject = f"Code Purple status deck, GitHub readback {c['generated_at'][:16].replace('T', ' ')} UTC"
    pages, links, internal = merge(Path(a.build), Path(a.out), subject)
    print(json.dumps({"pages": pages, "links": links, "internal": internal, "out": a.out}))


if __name__ == "__main__":
    main()
