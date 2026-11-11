"""Which checks run on every PR? Read-only census over recently merged PRs.

    python tools/threads/check_presence.py OUT.json REPO [REPO ...] [--limit 40]

For each repo it reads the last ``--limit`` PRs merged into the default branch and the
check runs on each PR's head commit (name, app id, conclusion). It records how many PRs
each (name, app) pair appeared on and succeeded on.

Use it before making a check required in a ruleset. A check is a safe required candidate
only if it ran on every PR (Dependabot ones included) and is not a known no-op
(``|| true``, ``|| echo``, echo scaffolds). Otherwise PRs that skip it wait forever.
Inspect each "all but one" case by hand. Commit statuses (for example the hub's
First-Pass Closure) are not check runs and do not appear here; they are matched by context.
Re-run after any workflow rename.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

try:
    from . import _common as c
except ImportError:  # run as a script
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import _common as c

SUCCESS = ("success", "neutral", "skipped")
BOTS = ("app/", "dependabot")


def tally(prs: list[dict], runs_of) -> dict:
    """Per ``name<TAB>app``: PRs present on, PRs succeeded on. The newest run per pair counts."""
    seen = collections.defaultdict(lambda: {"present": 0, "success": 0, "app": None})
    for p in prs:
        latest = {}
        for r in runs_of(p["headRefOid"]):
            latest.setdefault((r["name"], r["app"]), r["c"])
        for (name, app), concl in latest.items():
            s = seen[f"{name}\t{app}"]
            s["present"] += 1
            s["app"] = app
            s["success"] += concl in SUCCESS
    return dict(seen)


def candidates(census: dict) -> list[str]:
    """Check keys present on every PR of the census (the starting list for required checks)."""
    return sorted(k for k, v in census["checks"].items() if v["present"] == census["prs"] and census["prs"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("out", type=Path)
    ap.add_argument("repos", nargs="+")
    ap.add_argument("--limit", type=int, default=40)
    a = ap.parse_args(argv)
    out = {}
    for repo in a.repos:
        full = f"{c.OWNER}/{repo}"
        prs = c.gh_json("pr", "list", "-R", full, "--state", "merged", "--limit", str(a.limit),
                        "--json", "number,headRefOid,author,mergedAt")

        def runs_of(sha, full=full):
            return c.gh_json("api", f"repos/{full}/commits/{sha}/check-runs?per_page=100",
                             "--jq", "[.check_runs[]|{name,app:.app.id,c:.conclusion}]")

        out[repo] = {"prs": len(prs), "bots": sum(p["author"]["login"].startswith(BOTS) for p in prs),
                     "checks": tally(prs, runs_of)}
        out[repo]["on_every_pr"] = candidates(out[repo])
        print(f"{repo}: {len(prs)} PRs, {len(out[repo]['checks'])} distinct checks, "
              f"{len(out[repo]['on_every_pr'])} on every PR", flush=True)
    a.out.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
