"""JADE root docs: one masthead, one nav footer, links that resolve.

The root markdown of mission-control/jade_temple is the project's front door.
Every page in ORDER opens with its H1, then one masthead line, and ends with a
nav footer to its neighbours. Nothing sits above the H1: dated "update" banners
go to CHANGELOG.md. --check fails on any drift; --write applies the canonical
masthead and footer and leaves the body untouched.

    python mission-control/jade_temple/tools/root_docs.py --check
    python mission-control/jade_temple/tools/root_docs.py --write
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# One value for every page; the owner names the point release here, then --write.
RELEASE = "UNNAMED (owner sets SemVer)"
ADMISSION = "`MERGE_ADMISSION=HOLD`"
STATUSES = ("ACTIVE", "PROPOSAL", "REFERENCE", "HISTORICAL")
# (file, doc id, nav label, status), in reading order.
ORDER = (
    ("README.md", "JT-R", "README", "ACTIVE"),
    ("00_START_HERE.md", "JT-00", "00 Start here", "ACTIVE"),
    ("01_PROJECT_INSTRUCTIONS.md", "JT-01", "01 Project instructions", "ACTIVE"),
    ("02_CHARTER.md", "JT-02", "02 Charter", "ACTIVE"),
    ("03_JADE_CASTE_METHOD.md", "JT-03", "03 JADE_CASTE method", "PROPOSAL"),
    ("04_REPO_ROOT_SPINE_CONTRACT.md", "JT-04", "04 Root SPINE contract", "PROPOSAL"),
    ("05_MACH_TIERS.md", "JT-05", "05 MACH tiers", "PROPOSAL"),
    ("06_WAVE_PLAN.md", "JT-06", "06 Wave plan", "ACTIVE"),
    ("07_HANDOVER_RECURSION.md", "JT-07", "07 Handover recursion", "ACTIVE"),
    ("08_PR_READY.md", "JT-08", "08 Bootstrap PR", "HISTORICAL"),
    ("09_PROJECT_UPLOAD_GUIDE.md", "JT-09", "09 Project upload guide", "REFERENCE"),
    ("CHANGELOG.md", "JT-CL", "Changelog", "ACTIVE"),
)
# Root pages outside the standard for now, with the reason.
DEFERRED = {
    "DROPIN_NEXT_CHAT.md": "append-only CP.HANDOFF log, each wave prepends its checkpoint (W2 decision)",
}
INDEX = "00_START_HERE.md"
NAV = "**Nav:** "
MAST = re.compile(r"^> \*\*Doc\*\* \S+ · \*\*Status\*\* \S+ · \*\*Release\*\* .+ · "
                  r"\*\*Admission\*\* `[^`]+` · \*\*Updated\*\* (?P<updated>\S+)$")
# Inline [text](dest "title") and reference definitions [ref]: dest; <dest> may hold spaces.
DEST = r"(<[^>\n]*>|[^\s()<>]+)"
LINK = re.compile(r"\]\(\s*" + DEST + r"""(?:\s+(?:"[^"]*"|'[^']*'|\([^)]*\)))?\s*\)""")
REFDEF = re.compile(r"^ {0,3}\[[^\]]+\]:\s*" + DEST)
SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:", re.I)


def masthead(doc: str, status: str, updated: str) -> str:
    return (f"> **Doc** {doc} · **Status** {status} · **Release** {RELEASE} · "
            f"**Admission** {ADMISSION} · **Updated** {updated}")


def nav(i: int, order=ORDER) -> str:
    parts = []
    if i > 0:
        parts.append(f"[← {order[i - 1][2]}]({order[i - 1][0]})")
    parts.append(f"[Index]({INDEX})")
    if i + 1 < len(order):
        parts.append(f"[{order[i + 1][2]} →]({order[i + 1][0]})")
    return NAV + " · ".join(parts)


def split(text: str):
    """(h1, masthead or None, body lines) or None when the page does not open with its H1."""
    lines = text.replace("\r\n", "\n").split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    if not lines or not lines[0].startswith("# "):
        return None
    h1, rest = lines[0], lines[1:]
    while rest and not rest[0].strip():
        rest.pop(0)
    mast = rest.pop(0) if rest and rest[0].startswith("> **Doc**") else None
    while rest and not rest[0].strip():
        rest.pop(0)
    while rest and not rest[-1].strip():
        rest.pop()
    if rest and rest[-1].startswith(NAV):
        rest.pop()
        while rest and not rest[-1].strip():
            rest.pop()
        if rest and rest[-1].strip() == "---":
            rest.pop()
        while rest and not rest[-1].strip():
            rest.pop()
    return h1, mast, rest


def render(i: int, text: str, today: str, order=ORDER):
    """The canonical page, keeping an existing masthead's Updated date."""
    parts = split(text)
    if parts is None:
        return None
    h1, mast, body = parts
    m = MAST.match(mast) if mast else None
    updated = m["updated"] if m else today
    _, doc, _, status = order[i]
    return "\n".join([h1, "", masthead(doc, status, updated), "", *body, "", "---", "", nav(i, order)]) + "\n"


def links(text: str):
    """Relative link targets outside fenced code."""
    fenced = False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            found = LINK.findall(line) + REFDEF.findall(line)
            yield from (t[1:-1] if t.startswith("<") else t for t in found)


def problems(root: Path = ROOT, order=ORDER, deferred=DEFERRED, today: str | None = None):
    today = today or dt.date.today().isoformat()
    out = []
    listed = {o[0] for o in order} | set(deferred)
    for p in sorted(root.glob("*.md")):
        if p.name not in listed:
            out.append(f"{p.name}: root page is neither in ORDER nor DEFERRED")
    ids = [o[1] for o in order]
    if len(set(ids)) != len(ids):
        out.append("ORDER: doc ids are not unique")
    for i, (name, _, _, status) in enumerate(order):
        p = root / name
        if not p.is_file():
            out.append(f"{name}: missing")
            continue
        text = p.read_text(encoding="utf-8")
        if status not in STATUSES:
            out.append(f"{name}: status {status!r} not in {STATUSES}")
        want = render(i, text, today, order)
        if want is None:
            out.append(f"{name}: first line is not the H1 (move banners into CHANGELOG.md)")
            continue
        if want != text:
            out.append(f"{name}: masthead/footer not canonical (run root_docs.py --write)")
        lines = text.split("\n")
        m = MAST.match(lines[2]) if len(lines) > 2 else None
        if m:
            try:
                if dt.date.fromisoformat(m["updated"]).isoformat() > today:
                    out.append(f"{name}: Updated {m['updated']} is after {today}")
            except ValueError:
                out.append(f"{name}: Updated {m['updated']!r} is not an ISO date")
        for target in links(text):
            if SCHEME.match(target) or target.startswith("#"):
                continue
            if not (root / target.split("#", 1)[0]).exists():
                out.append(f"{name}: broken link {target}")
    return out


def write(root: Path = ROOT, order=ORDER, today: str | None = None):
    today = today or dt.date.today().isoformat()
    changed, refused = [], []
    for i, (name, *_rest) in enumerate(order):
        p = root / name
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8")
        want = render(i, text, today, order)
        if want is None:
            refused.append(name)
        elif want != text:
            p.write_text(want, encoding="utf-8", newline="\n")
            changed.append(name)
    return changed, refused


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true", help="apply canonical masthead and footer")
    ap.add_argument("--check", action="store_true", help="fail on drift (default)")
    ap.add_argument("--today", help="ISO date for new mastheads (default: today)")
    a = ap.parse_args(argv)
    if a.write:
        changed, refused = write(today=a.today)
        for n in changed:
            print(f"wrote {n}")
        for n in refused:
            print(f"refused {n}: first line is not the H1", file=sys.stderr)
    found = problems(today=a.today)
    for f in found:
        print(f, file=sys.stderr)
    print(f"root docs: {len(ORDER)} pages, {len(found)} problem(s); deferred: {', '.join(DEFERRED)}")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
