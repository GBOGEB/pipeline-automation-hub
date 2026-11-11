"""File parked intents as GitHub issues (label ``parked-intent``), idempotently.

    python tools/threads/parked_intents.py SPEC.json [--dry-run]

SPEC.json (``parked-intent-spec/1.0``)::

    {"date": "YYYY-MM-DD", "map": "<local handover path>",
     "items": [{"id", "repo", "title", "intent", "done_when",
                "sessions": [[title, "local_<id>"], ...],
                "wake": {"paths": [...], "keywords": [...], "refs": ["repo#N", "#N"]}}],
     "comment_only": [{"id", "repo", "issue", "body"}]}

Each issue body ends with ``<!-- parked-intent:v1 {"id", "sessions", "wake"} -->``, which
wake_check.py reads through ``triway_burndown.parked_intent_meta``. An item whose id
already has an issue (open or closed) is skipped, and a comment whose
``Parked intent <id>`` heading is already on the issue is skipped, so re-running is safe.
Run ``--dry-run`` first.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    from . import _common as c
except ImportError:  # run as a script
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import _common as c


def ensure_label(repo: str) -> None:
    names = c.gh_json("label", "list", "-R", f"{c.OWNER}/{repo}", "--search", c.LABEL, "--json", "name")
    if not any(n["name"] == c.LABEL for n in names):
        c.gh("label", "create", c.LABEL, "-R", f"{c.OWNER}/{repo}", "--color", "8a6d3b",
             "--description", "Intent parked from an archived Claude thread; wake_check.py watches its triggers")


def existing(repo: str) -> dict[str, int]:
    """Parked id -> issue number, over open and closed issues of ``repo``."""
    found = {}
    for i in c.gh_json("issue", "list", "-R", f"{c.OWNER}/{repo}", "--label", c.LABEL, "--state", "all",
                       "--limit", "500", "--json", "number,body"):
        meta = c.triway.parked_intent_meta(i.get("body"))
        if meta and meta.get("id"):
            found[meta["id"]] = i["number"]
    return found


def _ticks(values) -> str:
    return ", ".join("`" + v + "`" for v in values)


def body(item: dict, spec_map: str, date: str) -> str:
    meta = {"id": item["id"], "sessions": [s[1] for s in item["sessions"]], "wake": item["wake"]}
    sessions = "\n".join("- " + t + ": `" + sid + "` (claude://claude.ai/epitaxy/" + sid + ")"
                         for t, sid in item["sessions"])
    w = item["wake"]
    trig = [("- paths: " + _ticks(w["paths"])) if w.get("paths") else "",
            ("- keywords: " + ", ".join(w["keywords"])) if w.get("keywords") else "",
            ("- references: " + ", ".join(w["refs"])) if w.get("refs") else ""]
    return (f"**Parked intent {item['id']}**, from the thread roll-up of {date} (`{spec_map}` in the local work folder). "
            "No live thread, PR or issue owned this when its source thread was archived.\n\n"
            f"## Intent\n{item['intent']}\n\n## Done when\n{item['done_when']}\n\n"
            f"## Source threads (unarchive to resume)\n{sessions}\n\n"
            "## Wake triggers\nThe daily wake check lists this issue when new activity matches:\n"
            + "\n".join(t for t in trig if t) + "\n\n"
            + c.MARK + json.dumps(meta, separators=(",", ":")) + " -->\n")


def already_commented(posted: list[str], pid: str) -> bool:
    """True if a comment carries ``Parked intent <pid>`` not followed by an id character (U2 is not U23)."""
    pat = re.compile(r"Parked intent " + re.escape(pid) + r"(?![0-9A-Za-z])")
    return any(pat.search(b or "") for b in posted)


def bad_refs(spec: dict) -> list[str]:
    """Items whose wake refs do not parse; the filer refuses the spec so a bad marker is never filed."""
    out = []
    for item in spec.get("items", []):
        for r in item.get("wake", {}).get("refs", []):
            try:
                c.split_ref(r, item["repo"])
            except ValueError:
                out.append(f"{item['id']}: {r!r}")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("spec", type=Path)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    spec = json.loads(a.spec.read_text(encoding="utf-8"))
    date = spec.get("date", "")
    bad = bad_refs(spec)
    if bad:
        print("REFUSED: wake refs must be repo#N, #N or N: " + "; ".join(bad), file=sys.stderr)
        return 2
    results = []
    for repo in sorted({i["repo"] for i in spec.get("items", [])}):
        if not a.dry_run:
            ensure_label(repo)
        have = existing(repo)
        for item in (i for i in spec["items"] if i["repo"] == repo):
            if item["id"] in have:
                results.append((item["id"], repo, have[item["id"]], "exists"))
            elif a.dry_run:
                results.append((item["id"], repo, None, "would create"))
            else:
                url = c.gh("issue", "create", "-R", f"{c.OWNER}/{repo}", "--title", f"[{item['id']}] {item['title']}",
                           "--label", c.LABEL, "--body-file", "-", stdin=body(item, spec["map"], date)).strip()
                results.append((item["id"], repo, url.rsplit("/", 1)[-1], "created"))
    for cm in spec.get("comment_only", []):
        posted = c.gh_json("issue", "view", str(cm["issue"]), "-R", f"{c.OWNER}/{cm['repo']}", "--json", "comments",
                           "--jq", "[.comments[].body]")
        if already_commented(posted, cm["id"]):
            results.append((cm["id"], cm["repo"], cm["issue"], "exists"))
            continue
        if not a.dry_run:
            c.gh("issue", "comment", str(cm["issue"]), "-R", f"{c.OWNER}/{cm['repo']}", "--body-file", "-",
                 stdin=cm["body"])
        results.append((cm["id"], cm["repo"], cm["issue"], "would comment" if a.dry_run else "commented"))
    for r in results:
        print("\t".join(str(x) for x in r))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
