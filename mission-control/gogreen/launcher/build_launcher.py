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
from html import unescape
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
# Catalog fields derived from the read-at commit only (github = repo_url/blob/source_sha/path).
CATALOG_PULSE_KEYS = ("github",)


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=HERE, capture_output=True, text=True,
                          encoding="utf-8", check=True).stdout


def read_at(sha: str, path: str) -> tuple[str, str]:
    """Return (blob OID, text) of ``path`` at commit ``sha``."""
    oid = git("rev-parse", f"{sha}:{path}").strip()
    return oid, git("cat-file", "blob", oid)


def read_texts(sha: str, paths: list[str]) -> dict[str, str]:
    """Text of each of ``paths`` at commit ``sha``, read in one ``git cat-file --batch``."""
    if not paths:
        return {}
    req = "".join(f"{sha}:{p}\n" for p in paths).encode("utf-8")
    out = subprocess.run(["git", "cat-file", "--batch"], cwd=HERE, input=req,
                         capture_output=True, check=True).stdout
    texts, pos = {}, 0
    for path in paths:
        end = out.index(b"\n", pos)
        header = out[pos:end].decode("utf-8").split()
        if len(header) != 3 or header[1] != "blob":
            raise FileNotFoundError(f"{sha}:{path} is not a blob ({' '.join(header)})")
        size = int(header[2])
        texts[path] = out[end + 1:end + 1 + size].decode("utf-8", errors="replace")
        pos = end + 1 + size + 1
    return texts


def parse(path: str, text: str):
    if path.endswith(".csv"):
        return list(csv.DictReader(io.StringIO(text)))
    return json.loads(text)


def pick(doc, path: str):
    """Read a dotted path; ``name[]`` maps the rest of the path over a list.

    ``name{}`` does the same over a mapping's entries, each seen as
    ``{"key": k, "value": v}`` in the owner's order (e.g. repo-keyed state).
    Returns (value, found). A missing key gives (None, False); nothing is coerced.
    """
    if path == "[]":
        return doc, isinstance(doc, list)
    head, _, rest = path.partition(".")
    if head.endswith("{}"):
        mapping = doc.get(head[:-2]) if isinstance(doc, dict) else None
        if not isinstance(mapping, dict):
            return None, False
        entries = [{"key": k, "value": v} for k, v in mapping.items()]
        if not rest:
            return entries, True
        return [pick(entry, rest)[0] for entry in entries], True
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


def page_title(text: str, fallback: str) -> str:
    m = TITLE.search(text)
    return (unescape(m.group(1)).strip() if m else "") or fallback


def html_paths(sha: str) -> list[str]:
    """Every committed ``*.html`` path at commit ``sha``, sorted."""
    return sorted(p for p in git("ls-tree", "-r", "--full-tree", "--name-only", "-z", sha).split("\0")
                  if p.lower().endswith(".html"))


def group_of(path: str) -> str:
    """Catalog group: the first two directory levels of the path ('.' at the repo root)."""
    return "/".join(path.split("/")[:-1][:2]) or "."


def catalog(sha: str, repo_url: str) -> list[dict]:
    """Discovery list of every committed HTML page. Navigation only: no OID, no metric."""
    out = []
    for path, text in read_texts(sha, html_paths(sha)).items():
        out.append({"path": path, "group": group_of(path),
                    "title": page_title(text, posixpath.basename(path)),
                    "href": rel(path), "github": f"{repo_url}/blob/{sha}/{path}"})
    return sorted(out, key=lambda e: (e["group"], e["path"]))


def hub(spec: dict, sha: str) -> dict:
    """Cross-repo dashboard hub. In-repo entries (path only) are read at ``sha``: a missing
    file fails the build and the title comes from the page (a declared ``title`` is only the
    fallback for a page without one). Entries naming a ``repo`` or a
    ``url`` are declared, not probed, and are copied as written. Navigation only: no metric."""
    in_repo = lambda e: "repo" not in e and "url" not in e
    texts = read_texts(sha, [e["path"] for e in spec["entries"] if in_repo(e)])
    entries = []
    for e in spec["entries"]:
        out = dict(e)
        if in_repo(e):
            out.update(title=page_title(texts[e["path"]], e.get("title") or posixpath.basename(e["path"])), href=rel(e["path"]))
        entries.append(out)
    return {"note": spec["note"], "verified": spec["verified"], "entries": entries}


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

    # Linked pages are navigation, not inputs: record only what the page shows (title), so
    # regenerating a linked page does not make the launcher stale. A missing page still fails.
    pages = []
    texts = read_texts(sha, [p["path"] for p in spec["pages"]])
    for p in spec["pages"]:
        text = texts[p["path"]]
        pages.append({"group": p["group"], "path": p["path"], "href": rel(p["path"]),
                      "title": page_title(text, p["path"])})

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
        "pages_site": spec.get("pages_site"),
        "self_path": SELF_DIR + "/index.html",
        "catalog": catalog(sha, spec["repo_url"]),
        "hub": hub(spec["hub"], sha),
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


def stale_reason(committed: dict, fresh: dict) -> str:
    """Name what differs: changed inputs, changed page titles, or else the tile/page declarations."""
    parts = []
    old_in, new_in = committed.get("inputs", {}), fresh["inputs"]
    inputs = sorted(p for p in set(old_in) | set(new_in) if old_in.get(p) != new_in.get(p))
    if inputs:
        parts.append("changed inputs: " + ", ".join(inputs))
    old_pg = {p["path"]: p.get("title") for p in committed.get("pages", [])}
    new_pg = {p["path"]: p["title"] for p in fresh["pages"]}
    pages = sorted(p for p in set(old_pg) | set(new_pg) if old_pg.get(p) != new_pg.get(p))
    if pages:
        parts.append("changed pages: " + ", ".join(pages))
    old_cat = {e["path"]: e.get("title") for e in committed.get("catalog", [])}
    new_cat = {e["path"]: e["title"] for e in fresh.get("catalog", [])}
    for label, names in (("added", sorted(set(new_cat) - set(old_cat))),
                         ("removed", sorted(set(old_cat) - set(new_cat))),
                         ("retitled", sorted(p for p in set(old_cat) & set(new_cat)
                                             if old_cat[p] != new_cat[p]))):
        if names:
            parts.append(f"catalog {label}: " + ", ".join(names))
    old_hub = {e.get("path") or e.get("url"): e.get("title") for e in (committed.get("hub") or {}).get("entries", [])}
    new_hub = {e.get("path") or e.get("url"): e.get("title") for e in fresh.get("hub", {}).get("entries", [])}
    hub_changed = sorted(k for k in set(old_hub) | set(new_hub) if old_hub.get(k) != new_hub.get(k))
    if hub_changed:
        parts.append("hub changed: " + ", ".join(hub_changed))
    return "; ".join(parts) or "tile or page declarations changed (sources.json, template or builder)"


def strip_pulse(snapshot: dict) -> dict:
    """The snapshot without what only names the read-at commit (see PULSE_KEYS)."""
    out = {k: v for k, v in snapshot.items() if k not in PULSE_KEYS}
    if "catalog" in out:
        out["catalog"] = [{k: v for k, v in e.items() if k not in CATALOG_PULSE_KEYS}
                          for e in out["catalog"]]
    return out


def check(sha: str) -> list[str]:
    """Problems with the committed outputs, rebuilt from ``sha``; empty means current."""
    problems = []
    committed = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    fresh = project(json.loads(SOURCES.read_text(encoding="utf-8")), sha)
    if strip_pulse(committed) != strip_pulse(fresh):
        problems.append("launcher.json is stale; " + stale_reason(committed, fresh))
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
          "pages=%d" % len(snapshot["pages"]), "catalog=%d" % len(snapshot["catalog"]), "hub=%d" % len(snapshot["hub"]["entries"]), "missing=%d" % len(snapshot["missing_fields"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
