#!/usr/bin/env python3
"""Render site/redtrace-slides.html to an interactive PDF (site/redtrace-slides.pdf).

Interactive = one 16:9 page per slide, a bookmark (outline) entry per slide, the
Contents slide and every footer 'Contents' link as internal GoTo links, run/commit/repo
references as external URI links, document opens in outline view. Chromium print is not
byte-deterministic; the manifest records the PDF as non-deterministic and the QA below
asserts structure (pages = slides, outline = slides, internal + external links present).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject

SITE = Path(__file__).resolve().parents[1] / "site"
SRC, OUT = SITE / "redtrace-slides.html", SITE / "redtrace-slides.pdf"


def render(tmp: Path) -> None:
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1280, "height": 720})
        pg.goto(SRC.as_uri())
        pg.emulate_media(media="print")
        pg.pdf(path=str(tmp), width="1280px", height="720px", print_background=True,
               prefer_css_page_size=True, outline=False, tagged=True)
        b.close()


def annotate(tmp: Path) -> dict:
    manifest = json.loads((SITE / "redtrace-manifest.json").read_text(encoding="utf-8"))
    outline = manifest["slide_outline"]
    w = PdfWriter(clone_from=str(tmp))
    if len(w.pages) != len(outline):
        raise SystemExit(f"REDTRACE_PDF_FAIL: {len(w.pages)} pages vs {len(outline)} slides")
    for i, s in enumerate(outline):
        w.add_outline_item(f"{i + 1}. {s['title']}", i)
    w.add_metadata({"/Title": "JADE N+8 · Red-trace federation ledger", "/Author": "GBOGEB federation (agent-generated, read-only)",
                    "/Subject": "EVERRED / GREEN→RED / RED→GREEN across 5 core repos + gap analysis",
                    "/Keywords": "GOGREEN, EVERRED, red-trace, JADE, Mission Control"})
    w._root_object[NameObject("/PageMode")] = NameObject("/UseOutlines")
    with OUT.open("wb") as f:
        w.write(f)
    r = PdfReader(str(OUT))
    internal = external = 0
    for page in r.pages:
        for a in page.get("/Annots") or []:
            a = a.get_object()
            act = a.get("/A")
            if act is not None and act.get_object().get("/URI"):
                external += 1
            elif a.get("/Dest") is not None or (act is not None and act.get_object().get("/S") == "/GoTo"):
                internal += 1
    rep = {"pages": len(r.pages), "outline_items": len(r.outline), "internal_links": internal,
           "external_links": external, "bytes": OUT.stat().st_size}
    if rep["outline_items"] != len(outline) or internal < len(outline) or external < 5:
        raise SystemExit(f"REDTRACE_PDF_FAIL: {rep}")
    return rep


def main():
    tmp = OUT.with_suffix(".raw.pdf")
    render(tmp)
    try:
        rep = annotate(tmp)
    finally:
        tmp.unlink(missing_ok=True)
    print(json.dumps({"status": "PASS", **rep}, sort_keys=True))


if __name__ == "__main__":
    sys.exit(main())
