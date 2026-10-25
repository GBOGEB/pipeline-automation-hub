#!/usr/bin/env python3
"""Refresh the whole P process site from GitHub, or rebuild it offline from committed data.

Live:     python refresh.py            (gh CLI with read access to the probed repos)
Offline:  python refresh.py --offline  (no network: rebuild pages from site/ data)
Steps: readback (Code Purple lift) -> ruleset drift -> EVERRED harvest -> p_decide -> pages -> PDFs -> site/ + manifest.
Every path resolves from this file; outputs land in site/ (published) and build/ (scratch, gitignored).
"""
import argparse
import hashlib
import html
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SITE = ROOT / "site"
PY = sys.executable


def run(*cmd, cwd=ROOT):
    print("+", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], cwd=cwd, check=True)


def live_row(c: dict) -> str:
    """Static fallback for the Code Purple header (rewritten between census markers on every refresh)."""
    def pill(t, style=""):
        return f'    <span class="pill"{style}>{html.escape(t)}</span>\n'
    rep = ' style="background:var(--rep);border-color:var(--rep-s);color:var(--rep-ink)"'
    ok = ' style="background:var(--pass);border-color:var(--pass-s);color:var(--pass-ink)"'
    met = sum(1 for x in c["lift"] if x["ok"])
    s = pill(("LIFTED" if c["lifted"] else "NOT LIFTED") + f" · {met} of {len(c['lift'])} lift criteria", ok if c["lifted"] else rep)
    s += pill("read back " + c["generated_at"][:16].replace("T", " ") + " UTC")
    for p in c.get("prs", []):
        if p.get("role") in ("unblocker", "debt-ratchet"):
            s += pill(f"{p['repo'].split('/')[1]} #{p['number']} · {'merged' if p.get('merged') else p.get('state')}", ok if p.get("merged") else "")
    for n, v in c.get("repos", {}).items():
        s += pill(f"{n.split('/')[1]}: {v.get('open_prs')} open PRs")
    if c.get("merges_since_unblock") is not None:
        s += pill(f"{c['merges_since_unblock']} merges since unblock")
    return s


def stamp_code_purple(page: Path, census: dict) -> None:
    t = page.read_text(encoding="utf-8")
    new, n = re.subn(r"(<!-- census:begin[^>]*-->\n).*?(<!-- census:end -->)", lambda m: m.group(1) + live_row(census) + m.group(2), t, flags=re.S)
    if n != 1:
        raise SystemExit("census markers missing in code-purple/index.html")
    page.write_text(new, encoding="utf-8", newline="\n")


def print_page_pdf(page: Path, pdf: Path) -> int:
    """A4 reader companion of the Code Purple page (print CSS opens every tab), same as the HTML."""
    from playwright.sync_api import sync_playwright
    from pypdf import PdfReader
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.route("**/fonts.g*/**", lambda r: r.abort())
        pg.goto(page.as_uri())
        pg.wait_for_timeout(500)
        pg.pdf(path=str(pdf), format="A4", print_background=True)
        b.close()
    return len(PdfReader(str(pdf)).pages)


def copy(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--no-pdf", action="store_true")
    a = ap.parse_args()
    if not a.offline:
        run(PY, "kit/readback.py", "kit/incident.yaml", "--out", "kit/out")
        run(PY, ROOT / "rulesets/verify_rulesets.py", cwd=ROOT / "rulesets")
        run(PY, "everred/harvest.py", "--drift", "rulesets/drift.json")
        for f in ("everred.json", "register.md", "rex_return.yaml"):
            copy(ROOT / "everred/out" / f, SITE / "everred/data" / f)
        for f in ("census.json", "after_action.md"):
            copy(ROOT / "kit/out" / f, SITE / "code-purple/kit" / f)
    census_f = SITE / "code-purple/kit/census.json"
    census = json.loads(census_f.read_text(encoding="utf-8"))
    copy(ROOT / "everred/roots.yaml", SITE / "everred/data/roots.yaml")
    for f in ("incident.yaml", "readback.py"):
        copy(ROOT / "kit" / f, SITE / "code-purple/kit" / f)
    run(PY, "p_decide.py", "--census", census_f, "--everred", SITE / "everred/data/everred.json")
    run(PY, "everred/build_page.py", "--report", SITE / "everred/data/everred.json", "--census", census_f)
    # Code Purple page: stamp the static header from the census, then publish page + assets
    src = ROOT / "code-purple"
    stamp_code_purple(src / "index.html", census)
    for f in ("index.html", "assets/model.js", "assets/app.js"):
        copy(src / f, SITE / "code-purple" / f)
    for f in list((ROOT / "rulesets").glob("*.json")):
        if f.name != "survey.json":
            copy(f, SITE / "rulesets" / f.name)
    run(PY, "build_p_process.py", *(["--no-pdf"] if a.no_pdf else []))
    if not a.no_pdf:
        run("node", src / "build_deck.js", "--census", census_f)
        run(PY, src / "merge_deck.py", "--census", census_f, "--out", SITE / "code-purple/Code-Purple-deck.pdf")
        copy(ROOT / "build/code-purple.md", SITE / "code-purple/code-purple.md")
        print_page_pdf(SITE / "code-purple/index.html", SITE / "code-purple/code-purple.pdf")
    files = sorted(p for p in SITE.rglob("*") if p.is_file() and p.name != "manifest.json")
    man = {"schema": "p-process.site/1.0", "census_at": census["generated_at"],
           "files_sha256": {p.relative_to(SITE).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    (SITE / "manifest.json").write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"site_files": len(files), "census_at": census["generated_at"], "lifted": census["lifted"]}))


if __name__ == "__main__":
    main()
