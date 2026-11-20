#!/usr/bin/env python3
"""Triage a PyCharm/JetBrains inspection run en masse: class -> recurrence -> one method per class -> Kahn waves.

Reads either
  * a directory of headless `inspect.bat` XML results (one `<InspectionShortName>.xml` per inspection), or
  * the IDE's HTML export (`index.html`, streamed; a truncated export is reported as such).

It reuses the hub owners instead of copying them (AGENTS.md L4):
  * `mission-control/maroon/hints.py`  -> GENERATED_RE (GENERATED_PATH signal), PINNED_OID_RE (PINNED_OID tag),
                                          AUTHORITY (every row is a diagnosis hint, not closure proof)
  * `mission-control/jade_temple/devops/lifecycle.py` -> topo_layers() for the wave plan

Recurrence uses MAROON's ladder by analogy, counted over distinct FILES instead of PRs:
ONCE (1 hit) / REPEAT (1 file, many hits) / RECURRING (2 files) / SYSTEMIC (3+ files).
A SYSTEMIC class gets one fold-back method (exclusion, profile, formatter, gate rule) instead of N fixes.

    python inspection_triage.py --input <dir-of-xml | index.html> --root <project root> --out <dir> [--hub C:/repos/pah_tools]
"""
from __future__ import annotations

import argparse
import collections
import csv
import html
import importlib.util
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote

SCHEMA = "gbogeb.inspection-triage.v1"


def load(hub: Path, rel: str, name: str):
    path = hub / rel
    if not path.exists():
        sys.exit(f"missing hub module {path}\n  fix: git -C \"{hub}\" sparse-checkout add "
                 "mission-control/maroon mission-control/jade_temple/devops")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- classification: inspection id (short name or HTML display name) -> class -------------------------------
VENDOR_RE = re.compile(r"(^|/)(node_modules|\.vscode/extensions|\.venv|venv|site-packages|node-v\d[^/]*|"
                       r"\.AzureToolsForIntelliJ|\.trunk|\.idea|__pycache__|\.pytest_cache)(/|$)", re.IGNORECASE)
CLASSES = {  # class: (inspection ids, method, wave step)
    "PROFILE_NOISE": ({"SpellCheckingInspection", "GrazieInspection", "LanguageDetectionInspection",
                       "Proofreading / Typo", "Proofreading / Grammar"},
                      "Off in the triage profile; later re-enable on docs only with a shared project dictionary",
                      "PROFILE"),
    "AUTOFIX": ({"MarkdownIncorrectTableFormatting", "MarkdownIncorrectlyNumberedListItem", "MarkdownNoTableBorders",
                 "Markdown / Incorrect table formatting", "Markdown / Incorrectly numbered list item",
                 "Markdown / Table doesn't have side borders", "EditorConfig / Redundant property"},
                "Bulk: format.bat (or Code > Reformat on the scope) on a branch of its own, then re-inspect",
                "AUTOFIX"),
    "SEMI_AUTO": ({"MarkdownUnresolvedFileReference", "MarkdownUnresolvedHeaderReference", "MarkdownUnresolvedLinkLabel",
                   "Markdown / Unresolved file references", "Markdown / Unresolved header reference",
                   "Markdown / Unresolved link label"},
                  "Script-assisted: resolve by basename/anchor index; bind to the canonical file, never copy (ADR-0001)",
                  "SEMI_AUTO"),
}
METHOD_VENDOR = "Exclude (iml excludeFolder / custom scope); never edit third-party or IDE files"
METHOD_GENERATED = "Regenerate from source; never hand-edit generated outputs"
METHOD_DEFECT = "Per finding: MAROON / issue queue with source proof"
STEPS = ["EXCLUDE", "PROFILE", "RERUN_BASELINE", "REGENERATE", "AUTOFIX", "SEMI_AUTO", "DEFECT_QUEUE", "FOLD_BACK"]
EDGES = [("EXCLUDE", "RERUN_BASELINE", "FEEDFORWARD"), ("PROFILE", "RERUN_BASELINE", "FEEDFORWARD"),
         ("RERUN_BASELINE", "REGENERATE", "FEEDFORWARD"), ("RERUN_BASELINE", "AUTOFIX", "FEEDFORWARD"),
         ("AUTOFIX", "SEMI_AUTO", "FEEDFORWARD"), ("REGENERATE", "SEMI_AUTO", "FEEDFORWARD"),
         ("SEMI_AUTO", "DEFECT_QUEUE", "FEEDFORWARD"), ("DEFECT_QUEUE", "FOLD_BACK", "FEEDFORWARD")]


METHOD_UNTRACKED = "Not in git: out of the repo's scope; park, move out of the checkout, or commit deliberately"


def classify(rule: str, path: str, hints, tracked: set | None = None) -> tuple[str, str, str]:
    if VENDOR_RE.search(path):
        return "OUT_OF_SCOPE_VENDOR", METHOD_VENDOR, "EXCLUDE"
    if tracked is not None and path and path not in tracked:
        return "UNTRACKED_ESTATE", METHOD_UNTRACKED, "EXCLUDE"
    if hints.GENERATED_RE.search(path):
        return "GENERATED", METHOD_GENERATED, "REGENERATE"
    for cls, (ids, method, step) in CLASSES.items():
        if rule in ids:
            return cls, method, step
    return "DEFECT", METHOD_DEFECT, "DEFECT_QUEUE"


def recurrence(files: int, hits: int) -> str:
    if files >= 3:
        return "SYSTEMIC"
    if files == 2:
        return "RECURRING"
    return "REPEAT" if hits > 1 else "ONCE"


# --- readers -------------------------------------------------------------------------------------------------
def rel(path: str, root: str) -> str:
    p = unquote(path).replace("\\", "/").replace("file://", "").replace("$PROJECT_DIR$/", "")
    r = root.replace("\\", "/").rstrip("/") + "/"
    return p[len(r):] if p.lower().startswith(r.lower()) else p


def read_xml_dir(d: Path, root: str):
    for f in sorted(d.glob("*.xml")):
        if f.name.startswith(".") or f.stem == "Descriptions":
            continue
        for _, el in ET.iterparse(f):
            if el.tag == "problem":
                pc = el.find("problem_class")
                sev = pc.get("severity", "") if pc is not None else ""
                yield f.stem, sev, rel(el.findtext("file", ""), root)
                el.clear()


def read_html(f: Path, root: str, meta: dict):
    lab = re.compile(r'<li><label for="\d+">(?:<span[^>]*>([A-Z_ ]+)</span>|<b>(.*?)</b>&nbsp;(group|inspection))')
    href = re.compile(r'<div class="location">.*?<a href="file://([^"#]+)')
    clean = lambda s: html.unescape(s.replace("&nbsp;", " "))
    grp = insp = None
    cur = ""
    last = ""
    with open(f, encoding="utf-8", errors="replace", buffering=1 << 24) as fh:
        for line in fh:
            last = line
            if '<div class="location">' in line:
                m = href.search(line)
                if m:
                    cur = rel(m.group(1), root)
                continue
            if not line.startswith("<li><label"):
                continue
            m = lab.match(line)
            if not m:
                continue
            if m.group(3) == "group":
                grp = clean(m.group(2))
            elif m.group(3) == "inspection":
                insp, cur = clean(m.group(2)), ""
            else:
                yield f"{grp} / {insp}", m.group(1), cur
    meta["truncated"] = "</html>" not in last


# --- main ----------------------------------------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--input", required=True, type=Path)
    ap.add_argument("--root", required=True, help="project root the paths are relative to")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--hub", type=Path, default=Path(__file__).resolve().parents[2])
    ap.add_argument("--source-sha", default="", help="commit the inspected tree was at (one pulse per snapshot)")
    ap.add_argument("--git-tracked", action="store_true",
                    help="classify files that git does not track at --root as UNTRACKED_ESTATE")
    a = ap.parse_args(argv)
    hints = load(a.hub, "mission-control/maroon/hints.py", "maroon_hints")
    lifecycle = load(a.hub, "mission-control/jade_temple/devops/lifecycle.py", "jade_lifecycle")

    tracked = None
    if a.git_tracked:
        import subprocess
        out = subprocess.run(["git", "-C", a.root, "ls-files", "-z"], capture_output=True, check=True).stdout
        tracked = set(out.decode("utf-8", "replace").split("\0"))
        if not a.source_sha:
            a.source_sha = subprocess.run(["git", "-C", a.root, "rev-parse", "HEAD"], capture_output=True,
                                          text=True, check=True).stdout.strip()
    meta: dict = {"truncated": False}
    rows = read_xml_dir(a.input, a.root) if a.input.is_dir() else read_html(a.input, a.root, meta)
    hits = collections.Counter()
    files: dict[tuple, set] = collections.defaultdict(set)
    sev: dict[tuple, collections.Counter] = collections.defaultdict(collections.Counter)
    for rule, severity, path in rows:
        cls, method, step = classify(rule, path, hints, tracked)
        top = path.split("/")[0] if "/" in path else "<root>"
        key = (cls, rule, top, method, step)
        hits[key] += 1
        files[key].add(path)
        sev[key][severity] += 1

    a.out.mkdir(parents=True, exist_ok=True)
    table = []
    for key, n in hits.most_common():
        cls, rule, top, method, step = key
        nf = len(files[key])
        pinned = any(hints.PINNED_OID_RE.search(p) for p in files[key])
        table.append({"class": cls, "rule": rule, "top_dir": top, "hits": n, "files": nf,
                      "recurrence": recurrence(nf, n), "severity": dict(sev[key]), "step": step,
                      "method": method, "pinned_oid": pinned, "authority": hints.AUTHORITY})
    with open(a.out / "triage.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(table[0]) if table else ["class"])
        w.writeheader()
        for t in table:
            w.writerow({**t, "severity": json.dumps(t["severity"])})

    waves = lifecycle.topo_layers(STEPS, EDGES)
    by_class = collections.Counter()
    by_step = collections.Counter()
    for t in table:
        by_class[t["class"]] += t["hits"]
        by_step[t["step"]] += t["hits"]
    total = sum(by_class.values()) or 1
    doc = {"schema": SCHEMA, "source_sha": a.source_sha, "input": str(a.input), "truncated_export": meta["truncated"],
           "total_hits": total, "by_class": dict(by_class), "waves": waves, "authority": hints.AUTHORITY}
    (a.out / "triage.json").write_text(json.dumps(doc, indent=2), encoding="utf-8", newline="\n")

    md = [f"# Inspection triage ({SCHEMA})", "",
          f"Input `{a.input.name}`, source SHA `{a.source_sha or 'UNKNOWN'}`"
          + ("  \n**Export is truncated: totals are a lower bound.**" if meta["truncated"] else ""), "",
          "| Class | Hits | Share | Method |", "|---|---:|---:|---|"]
    methods = {t["class"]: t["method"] for t in table}
    for cls, n in by_class.most_common():
        md.append(f"| {cls} | {n:,} | {n / total:.0%} | {methods[cls]} |")
    md += ["", "## Waves (Kahn, `lifecycle.topo_layers`)", ""]
    for i, layer in enumerate(waves):
        md.append(f"- W{i}: " + ", ".join(f"{s} ({by_step.get(s, 0):,})" for s in layer))
    md += ["", "## Top in-scope rules", "", "| Class | Rule | Dir | Hits | Files | Recurrence |", "|---|---|---|---:|---:|---|"]
    for t in [t for t in table if t["step"] != "EXCLUDE"][:40]:
        md.append(f"| {t['class']} | {t['rule']} | {t['top_dir']} | {t['hits']:,} | {t['files']} | {t['recurrence']} |")
    md += ["", f"Every row is `{hints.AUTHORITY}`."]
    (a.out / "TRIAGE.md").write_text("\n".join(md) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(md[:12 + len(by_class) + len(waves)]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
