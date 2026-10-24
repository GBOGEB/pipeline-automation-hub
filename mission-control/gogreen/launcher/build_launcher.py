#!/usr/bin/env python3
"""GoGreen launcher: read-only projection of canonical owners' committed outputs.

Computes no metric. Every value is read verbatim from an owner's output file,
all at one commit (AGENTS.md L4 one owner per metric, L6 one pulse per snapshot).
Missing or null values stay null and render as "unknown", never zero.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import posixpath
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCES = HERE / "sources.json"
TEMPLATE = HERE / "launcher_template.html"
SNAPSHOT = HERE / "launcher.json"
PAGE = HERE / "index.html"
SELF_DIR = "mission-control/gogreen/launcher"
SCHEMA = "gogreen.launcher.snapshot.v1"
DATA_HOLE = "/*GOGREEN_LAUNCHER_DATA*/null"
TITLE = re.compile(r"<title>([^<]*)</title>", re.I)
# Fields that name the commit the build read from; --check ignores them so a
# rebuild on a later commit with unchanged inputs is not reported as stale.
PULSE_KEYS = ("source_sha", "source_date")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=HERE, capture_output=True, text=True,
                          encoding="utf-8", check=True).stdout


def read_at(sha: str, path: str) -> tuple[str, str]:
    """Return (blob OID, text) of ``path`` at commit ``sha``."""
    oid = git("rev-parse", f"{sha}:{path}").strip()
    return oid, git("cat-file", "blob", oid)


def parse(path: str, text: str):
    if path.endswith(".csv"):
        return list(csv.DictReader(io.StringIO(text)))
    return json.loads(text)


def pick(doc, path: str):
    """Read a dotted path; ``name[]`` maps the rest of the path over a list.

    Returns (value, found). A missing key gives (None, False); nothing is coerced.
    """
    if path == "[]":
        return doc, isinstance(doc, list)
    head, _, rest = path.partition(".")
    if head.endswith("[]"):
        items = doc if head == "[]" else (doc.get(head[:-2]) if isinstance(doc, dict) else None)
        if not isinstance(items, list):
            return None, False
        if not rest:
            return items, True
        return [pick(item, rest)[0] for item in items], True
    if not isinstance(doc, dict) or head not in doc:
        return None, False
    return (pick(doc[head], rest) if rest else (doc[head], True))


def rel(target: str) -> str:
    return posixpath.relpath(target, SELF_DIR)


def project(spec: dict, sha: str) -> dict:
    inputs: dict[str, dict] = {}
    missing: list[str] = []

    def load(path: str):
        if path not in inputs:
            oid, text = read_at(sha, path)
            inputs[path] = {"oid": oid, "doc": parse(path, text)}
        return inputs[path]["doc"]

    def field(doc, tile_id: str, f: dict) -> dict:
        value, found = pick(doc, f["path"])
        if not found:
            missing.append(f"{tile_id}:{f['path']}")
        out = {"label": f["label"], "path": f["path"], "value": value}
        if "unit" in f:
            out["unit"] = f["unit"]
        return out

    tiles = []
    for t in spec["tiles"]:
        tile = {"id": t["id"], "label": t["label"],
                "pages": [{"path": p, "href": rel(p)} for p in t.get("pages", [])]}
        if "unresolved" in t:
            tile["unresolved"] = t["unresolved"]
            tiles.append(tile)
            continue
        doc = load(t["input"])
        tile.update(owner=t["owner"], input=t["input"], input_oid=inputs[t["input"]]["oid"],
                    schema=doc.get("schema") if isinstance(doc, dict) else None)
        if "status" in t:
            tile["status"] = field(doc, t["id"], {"label": "Status", "path": t["status"]})
        if "headline" in t:
            tile["headline"] = field(doc, t["id"], t["headline"])
        tile["fields"] = [field(doc, t["id"], f) for f in t.get("fields", [])]
        tile["lists"] = []
        for spec_list in t.get("lists", []):
            rows, found = pick(doc, spec_list["path"])
            if not found:
                missing.append(f"{t['id']}:{spec_list['path']}")
                rows = []
            cols = spec_list["columns"]
            tile["lists"].append({
                "label": spec_list["label"], "columns": [c["label"] for c in cols],
                "rows": [[pick(r, c["key"])[0] for c in cols] for r in rows]})
        tiles.append(tile)

    pages = []
    for p in spec["pages"]:
        oid, text = read_at(sha, p["path"])
        m = TITLE.search(text)
        pages.append({"group": p["group"], "path": p["path"], "href": rel(p["path"]), "oid": oid,
                      "title": m.group(1).strip() if m else p["path"]})

    return {
        "schema": SCHEMA,
        "rule": spec["rule"],
        "repo_url": spec["repo_url"],
        "source_sha": sha,
        "source_date": git("show", "-s", "--format=%cI", sha).strip(),
        "computes_metrics": False,
        "inputs": {p: v["oid"] for p, v in sorted(inputs.items())},
        "missing_fields": missing,
        "pages": pages,
        "tiles": tiles,
    }


def render(snapshot: dict) -> str:
    html = TEMPLATE.read_text(encoding="utf-8")
    if html.count(DATA_HOLE) != 1:
        raise ValueError("template must contain the data anchor exactly once")
    data = (json.dumps(snapshot, ensure_ascii=True, separators=(",", ":"), sort_keys=True, allow_nan=False)
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))
    return html.replace(DATA_HOLE, data)


def dump(snapshot: dict) -> str:
    return json.dumps(snapshot, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def check(sha: str) -> list[str]:
    """Problems with the committed outputs, rebuilt from ``sha``; empty means current."""
    problems = []
    committed = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    fresh = project(json.loads(SOURCES.read_text(encoding="utf-8")), sha)
    strip = lambda s: {k: v for k, v in s.items() if k not in PULSE_KEYS}
    if strip(committed) != strip(fresh):
        changed = sorted(p for p in set(committed["inputs"]) | set(fresh["inputs"])
                         if committed["inputs"].get(p) != fresh["inputs"].get(p))
        problems.append("launcher.json is stale; changed inputs: " + (", ".join(changed) or "sources.json"))
    if PAGE.read_text(encoding="utf-8") != render(committed):
        problems.append("index.html does not match render(launcher.json)")
    if committed["missing_fields"]:
        problems.append("owner fields missing: " + ", ".join(committed["missing_fields"]))
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rev", default="HEAD", help="commit to read every owner output from (default HEAD)")
    ap.add_argument("--check", action="store_true", help="verify committed outputs instead of writing")
    args = ap.parse_args(argv)
    sha = git("rev-parse", f"{args.rev}^{{commit}}").strip()
    if args.check:
        problems = check(sha)
        for p in problems:
            print("GOGREEN_LAUNCHER_STALE:", p, file=sys.stderr)
        print("GOGREEN_LAUNCHER_CHECK=" + ("FAIL" if problems else "PASS"), "rev=" + sha)
        return 1 if problems else 0
    snapshot = project(json.loads(SOURCES.read_text(encoding="utf-8")), sha)
    SNAPSHOT.write_text(dump(snapshot), encoding="utf-8", newline="\n")
    PAGE.write_text(render(snapshot), encoding="utf-8", newline="\n")
    print("GOGREEN_LAUNCHER_BUILD=PASS", "rev=" + sha, "tiles=%d" % len(snapshot["tiles"]),
          "pages=%d" % len(snapshot["pages"]), "missing=%d" % len(snapshot["missing_fields"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
