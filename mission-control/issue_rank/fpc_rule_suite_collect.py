#!/usr/bin/env python3
"""Owner-only, read-only collector for fpc.rule-suite-export.v1 (FPC_RULE_SUITE_JOIN_README steps 1-3).

    python mission-control/issue_rank/fpc_rule_suite_collect.py \
      --events mission-control/issue_rank/evidence/FPC_MERGE_COHORT_29_20261112.json \
      --out <dir>

Runs only GET calls through the owner's authenticated ``gh`` session (Administration read is
required; an integration token gets HTTP 403). It writes DIR/raw/list_p<n>.json,
DIR/raw/suite_<id>.json, DIR/OWNER_RULE_SUITES_EXPORT.json and DIR/SHA256SUMS, then feed the
export to fpc_rule_suite_join.py. It never mutates GitHub, never prints a token, and grants no
authority: the join keeps merge admission HOLD.

``assess()`` is the pure decision: state is COMPLETE only when pagination ended on a short page,
every detail GET succeeded, no rule_evaluations list reached GitHub's 50-entry metadata cap and
the oldest listed suite predates the event window. Anything else is INCOMPLETE, and the join then
treats every event as unresolved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = "GBOGEB/pipeline-automation-hub"
REF = "refs/heads/master"
SCHEMA = "fpc.rule-suite-export.v1"
TOLERANCE = timedelta(minutes=15)
PER_PAGE = 100
METADATA_CAP = 50
SUITE_FIELDS = ("id", "actor_id", "actor_name", "before_sha", "after_sha", "ref", "repository_id",
                "repository_name", "pushed_at", "result", "evaluation_result", "rule_evaluations")


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def event_window(events: list[dict]) -> tuple[datetime, datetime]:
    times = [_ts(e["merged_at"]) for e in events]
    return min(times) - TOLERANCE, max(times) + TOLERANCE


def assess(pages: list[list[dict]], details: dict[int, dict | None], events: list[dict],
           list_error: str | None = None) -> dict:
    """Pure: decide the export state from what was actually read. Fail closed on any gap."""
    limits = [list_error] if list_error else []
    listed = [row for page in pages for row in page]
    pagination_complete = list_error is None and bool(pages) and len(pages[-1]) < PER_PAGE
    if not pagination_complete and not list_error:
        limits.append("last list page was full; more pages may exist")
    missing = sorted(r["id"] for r in listed if details.get(r["id"]) is None)
    details_complete = not missing
    if missing:
        limits.append(f"detail GET failed for suites {missing}")
    suites = [{k: details[r["id"]].get(k) for k in SUITE_FIELDS}
              for r in sorted(listed, key=lambda r: r["id"]) if details.get(r["id"]) is not None]
    truncated = any(len(s.get("rule_evaluations") or []) >= METADATA_CAP for s in suites)
    if truncated:
        limits.append(f"a rule_evaluations list reached the {METADATA_CAP}-entry metadata cap")
    lo, hi = event_window(events)
    oldest = min((_ts(s["pushed_at"]) for s in suites), default=None)
    covered = oldest is not None and oldest <= lo
    if not covered:
        limits.append(f"oldest suite {oldest and _iso(oldest)} does not predate window_start {_iso(lo)}")
    complete = pagination_complete and details_complete and not truncated and covered
    return {"schema": SCHEMA, "repository": REPO, "ref": REF,
            "state": "COMPLETE" if complete else "INCOMPLETE", "filter": "all",
            "pagination_complete": pagination_complete, "details_complete": details_complete,
            "metadata_truncated": truncated, "window_start": _iso(lo), "window_end": _iso(hi),
            "limitations": limits, "suites": suites}


def _gh_get(path: str) -> tuple[str | None, str]:
    env = {k: v for k, v in os.environ.items() if k not in ("GITHUB_TOKEN", "GH_TOKEN")}
    r = subprocess.run(["gh", "api", path], capture_output=True, encoding="utf-8", env=env, check=False)
    return (r.stdout if r.returncode == 0 else None), r.stderr.strip()[:200]


def collect(events: list[dict], out: Path) -> dict:
    raw = out / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    receipts, pages, list_error = [], [], None

    def keep(name: str, endpoint: str, body: str) -> None:
        (raw / name).write_text(body, encoding="utf-8", newline="\n")
        receipts.append({"endpoint": "GET /" + endpoint, "file": "raw/" + name,
                         "sha256": hashlib.sha256(body.encode("utf-8")).hexdigest()})

    for page in range(1, 21):
        ep = (f"repos/{REPO}/rulesets/rule-suites?ref={REF}&time_period=week"
              f"&rule_suite_result=all&per_page={PER_PAGE}&page={page}")
        body, err = _gh_get(ep)
        if body is None:
            list_error = f"list page {page}: {err}"
            break
        keep(f"list_p{page}.json", ep, body)
        pages.append(json.loads(body))
        if len(pages[-1]) < PER_PAGE:
            break
    details = {}
    for row in sorted((r for p in pages for r in p), key=lambda r: r["id"]):
        ep = f"repos/{REPO}/rulesets/rule-suites/{row['id']}?include_metadata=true"
        body, _ = _gh_get(ep)
        details[row["id"]] = None if body is None else json.loads(body)
        if body is not None:
            keep(f"suite_{row['id']}.json", ep, body)
    export = assess(pages, details, events, list_error)
    export.update({"captured_at": _iso(datetime.now(timezone.utc)),
                   "collector": "owner gh CLI session, GET only",
                   "verification": "self-checked by the collector; independent replay still required",
                   "receipts": receipts})
    (out / "OWNER_RULE_SUITES_EXPORT.json").write_text(
        json.dumps(export, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    sums = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(out).as_posix()}"
            for p in sorted([out / "OWNER_RULE_SUITES_EXPORT.json", *raw.glob("*.json")])]
    (out / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8", newline="\n")
    return export


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--events", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    a = p.parse_args(argv)
    export = collect(json.loads(a.events.read_text(encoding="utf-8"))["events"], a.out)
    print(json.dumps({k: export[k] for k in ("state", "pagination_complete", "details_complete",
                                             "metadata_truncated", "window_start", "window_end")}))
    for item in export["limitations"]:
        print("LIMIT " + item)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
