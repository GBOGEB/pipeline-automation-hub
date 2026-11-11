#!/usr/bin/env python3
"""CODE MAROON diagnosis hints: recurrence, history and false-positive signals over the operations ledger.

`operations.py` owns intake, the ledger, leases, the Kahn plan and closure (OPERATIONS.md). This
add-on reads that ledger (read-only, as JSON) and tells a diagnosing worker what is already known about
each open observation, so N repeats of one defect are diagnosed once and past fixes are reused:

- **Finding identity** across PRs, branches and pulses: a scanner rule id where the title has one
  (`yaml.github-actions...mutable-action-tag`, `B602`, `CWE-79`), otherwise repository, theme and the
  significant words of the first line. Near-duplicates merge; two rules never do.
- **Recurrence** per finding: `ONCE`, `REPEAT`, `RECURRING` (2 PRs), `SYSTEMIC` (3+ PRs), with sightings,
  frequency per pulse, reopens, first and last seen, modal path and reviewer.
- **Tags** from PR branch, title and thread: `METHOD`, `REX`, `SCALING_PROOF`, `SCALING_PILOT`, `SCALING`,
  and `PINNED_OID` for paths whose git OIDs JADE outputs pin (re-run the JADE DAG generator).
- **Signals** per open observation: `NO_PUSH_BOT_BRANCH`, `NO_PUSH_FORK`, `SEEN_FIXED`, `FP_HISTORY`,
  `REOPENED`, `GENERATED_PATH`, and with `--check-heads` `SUGGESTION_AT_HEAD` or `ANCHOR_GONE_AT_HEAD`.
- **Proposals**: `group_findings` calls for one finding repeated on one PR branch, a cross-PR method
  for one finding on several PRs, and a fold-back for a `SYSTEMIC` finding (test, lint, gate rule,
  AGENTS.md or skill line, so it stops recurring).

Every hint is `DIAGNOSIS_HINT_NOT_CLOSURE_PROOF`. Nothing here groups, claims, replies, resolves or
closes: a trusted worker reads the source and calls `operations.group_findings` or `closure` itself.
`--check-heads` reads GitHub (comment body, file at the head); everything else is offline.

    python hints.py --ledger <private>/MAROON_OPERATIONS.json --out <private dir> [--history raw_review.json] [--check-heads]
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCHEMA = "code_maroon.hints.v1"
PUBLIC_SCHEMA = "code_maroon.hints_public.v1"
LEDGER_SCHEMA = "code_maroon.operations.v1"
AUTHORITY = "DIAGNOSIS_HINT_NOT_CLOSURE_PROOF"
NEAR_DUP = 0.6
MAX_FILE_BYTES = 400_000

_spec = importlib.util.spec_from_file_location("maroon_hints_review", HERE / "review_threads.py")
RT = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(RT)

STOP = set("the this that with from into when then than there their these those which while where would could "
           "should must does have will also only just more less some each every any not but for are was were "
           "can its has had been being use uses used using file files line lines code here semgrep finding "
           "codeql copilot codex oss".split())
# A scanner rule id is the strongest identity a finding has. A dotted id needs a hyphen or four segments,
# so prose that names code (`os.path.join`) is not mistaken for a rule; short codes come from known families.
RULE_RE = re.compile(r"\b([a-z0-9_]+(?:\.[a-z0-9_-]+){2,})\b|"
                     r"\b(B\d{3}|[EFWS]\d{3,4}|CWE-\d+|CVE-\d{4}-\d{4,}|GHSA(?:-[a-z0-9]{4}){3})\b", re.IGNORECASE)
GENERATED_RE = re.compile(r"(^|/)(site|outputs?|generated|dist|build)/|(^|/)data/.*\.(json|csv|ya?ml)$|"
                          r"(package-lock\.json|poetry\.lock|uv\.lock|\.lock)$|_GENERATED|(^|/)snapshot\.json$")
# Paths whose git OIDs JADE outputs pin (scale_dock.py, p-process files, the census): a change needs the
# JADE DAG generator re-run in the same push.
PINNED_OID_RE = re.compile(r"^mission-control/gogreen/scale_dock\.py$|(^|/)p-process[^/]*$|"
                           r"^mission-control/.*census.*\.(json|csv|ya?ml)$", re.IGNORECASE)
BOT_BRANCH_RE = re.compile(r"^(dependabot|renovate|pre-commit-ci|copilot/)", re.IGNORECASE)
TAGS = [
    ("METHOD", re.compile(r"\bmethod|runbook|\bskill\b|sipoc|\bdag\b|agents\.md|playbook|fold[- ]?back", re.IGNORECASE)),
    ("REX", re.compile(r"\brex\b|lessons?[- ]learned|retro|post-?mortem", re.IGNORECASE)),
    ("SCALING_PROOF", re.compile(r"scal\w*[ _-]?proof|proof[ _-]of[ _-]scale", re.IGNORECASE)),
    ("SCALING_PILOT", re.compile(r"\bpilot", re.IGNORECASE)),
    ("SCALING", re.compile(r"\bscal(e|ing)\b|scale[_-]?dock|fan[- ]?out", re.IGNORECASE)),
]
SUGGESTION_RE = re.compile(r"```suggestion[^\n]*\n(.*?)```", re.DOTALL)
FP_WORDS = ("false_positive", "false-positive", "kept as is", "not a defect")


# ---------------------------------------------------------------------------------------------- identity
def words(title: str) -> list[str]:
    """Significant words of a finding's first line, in order: no paths, numbers, quotes or stop words."""
    text = re.sub(r"`[^`]*`|\S+/\S+|\S+\.\w{1,5}\b|\d+", " ", (title or "").lower())
    seen, out = set(), []
    for w in re.findall(r"[a-z][a-z_]{2,}", text):
        if w not in STOP and w not in seen:
            seen.add(w)
            out.append(w)
    return out[:10]


def rule_of(title: str) -> str | None:
    for m in RULE_RE.finditer(title or ""):
        if m.group(2):
            return m.group(2).upper()
        if "-" in m.group(1) or m.group(1).count(".") >= 3:
            return m.group(1).lower()
    return None


def finding_key(repo: str, title: str) -> str:
    rule = rule_of(title)
    theme = RT.theme_of(title or "")
    ident = f"rule:{rule}" if rule else f"{theme}|{' '.join(sorted(words(title)))}"
    return "f-" + hashlib.sha256(f"{repo}|{ident}".encode()).hexdigest()[:16]


def merge_near_duplicates(items: list[dict]) -> dict[str, str]:
    """key -> canonical key. Findings without a rule id in one repo and theme merge at >= NEAR_DUP overlap."""
    parent = {i["key"]: i["key"] for i in items}

    def find(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k
    groups = collections.defaultdict(dict)
    for i in items:
        if not rule_of(i["title"]):
            groups[(i["repo"], RT.theme_of(i["title"] or ""))][i["key"]] = set(words(i["title"]))
    for group in groups.values():
        keys = sorted(group)
        for x, a in enumerate(keys):
            for b in keys[x + 1:]:
                sa, sb = group[a], group[b]
                if sa and sb and len(sa & sb) / len(sa | sb) >= NEAR_DUP:
                    parent[find(b)] = find(a)
    return {k: find(k) for k in parent}


def tags_of(*texts, path: str | None = None) -> list[str]:
    blob = " ".join(t or "" for t in texts)
    found = [name for name, rx in TAGS if rx.search(blob)]
    if path and PINNED_OID_RE.search(path):
        found.append("PINNED_OID")
    return found


def no_push(row: dict) -> str | None:
    """Why no worker should push to this observation's branch: a fork is not ours, a bot rebase drops commits."""
    if row.get("head_repo") and row["head_repo"] != row["repo"]:
        return "NO_PUSH_FORK"
    if BOT_BRANCH_RE.match(row.get("head_ref") or ""):
        return "NO_PUSH_BOT_BRANCH"
    return None


def closed_as_false_positive(row: dict) -> bool:
    """A closed observation whose closure receipt classified it as a false positive."""
    blob = json.dumps(row.get("closure_receipts") or [], sort_keys=True).lower()
    return row.get("semantic_state") == "closed" and any(w in blob for w in FP_WORDS)


def recurrence(prs: int, sightings: int, pulses: int) -> str:
    if prs >= 3:
        return "SYSTEMIC"
    if prs >= 2:
        return "RECURRING"
    if sightings >= 2 or pulses >= 2:
        return "REPEAT"
    return "ONCE"


# ---------------------------------------------------------------------------------------------- GitHub
def run_gh(args: list[str]) -> tuple[int, str, str]:
    p = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8", timeout=120, check=False)
    return p.returncode, p.stdout, p.stderr


def head_signals(row: dict, gh=run_gh) -> list[dict]:
    """Read-only: is the thread's suggestion already in the file at the head, or its anchor line gone?"""
    if not (row.get("path") and row.get("head_sha") and row.get("comment_id")):
        return []
    code, out, _ = gh(["api", f"repos/{row['repo']}/pulls/comments/{row['comment_id']}"])
    body = json.loads(out).get("body", "") if code == 0 else ""
    code, text, _ = gh(["api", "-H", "Accept: application/vnd.github.raw",
                        f"repos/{row['repo']}/contents/{urllib.parse.quote(row['path'], safe='/')}?ref={row['head_sha']}"])
    if code or len(text) > MAX_FILE_BYTES or "\x00" in text:
        return []
    flat = " ".join(text.split())
    hints = []
    suggestions = [" ".join(s.split()) for s in SUGGESTION_RE.findall(body or "") if s.strip()]
    if suggestions and all(s in flat for s in suggestions):
        hints.append({"code": "SUGGESTION_AT_HEAD", "detail": f"every suggestion block is in {row['path']} at {row['head_sha'][:10]}"})
    anchor = " ".join((row.get("anchor") or "").split())
    if len(anchor) >= 12 and anchor not in flat:  # a short anchor (`}`) proves nothing either way
        hints.append({"code": "ANCHOR_GONE_AT_HEAD", "detail": f"the commented line is not in {row['path']} at {row['head_sha'][:10]}"})
    return hints


# ---------------------------------------------------------------------------------------------- analysis
def load_ledger(path: Path) -> dict:
    ledger = json.loads(path.read_text(encoding="utf-8"))
    if ledger.get("schema") != LEDGER_SCHEMA:
        raise ValueError(f"{path}: schema {ledger.get('schema')!r}, expected {LEDGER_SCHEMA}")
    return ledger


def history_rows(review_raw: dict | None) -> list[dict]:
    """Closed-PR threads from `review_threads.py fetch` as ledger-shaped rows: history only, never work."""
    rows = []
    for repo, entry in (review_raw or {}).get("repos", {}).items():
        for t in entry.get("alerts", []):
            rows.append({"id": f"hist-{repo}#{t['pr']}/{t['number']}", "repo": repo, "pr": t["pr"],
                         "title": t.get("title"), "path": t.get("path"), "reviewer": t.get("reviewer"),
                         "semantic_state": "closed" if t.get("state") == "resolved" and t.get("pr_merged") else "history",
                         "history": True, "first_seen": t.get("closed_at"), "last_seen": t.get("closed_at"),
                         "sighting_count": 1, "reopen_count": 0, "closure_receipts": []})
    return rows


def analyse(ledger: dict, review_raw: dict | None = None, gh=None) -> dict:
    rows = [dict(r) for r in ledger.get("observations", {}).values()] + history_rows(review_raw)
    for r in rows:
        r["key"] = finding_key(r["repo"], r.get("title") or "")
    canon = merge_near_duplicates([{"key": r["key"], "repo": r["repo"], "title": r.get("title") or ""} for r in rows])
    by_key = collections.defaultdict(list)
    for r in rows:
        r["key"] = canon[r["key"]]
        by_key[r["key"]].append(r)
    pulses = max(1, len(ledger.get("pulses", {})))
    findings = {}
    for key, rs in by_key.items():
        prs = sorted({f"{r['repo']}#{r['pr']}" for r in rs})
        sightings = sum(r.get("sighting_count", 1) for r in rs)
        paths = collections.Counter(r["path"] for r in rs if r.get("path"))
        reviewers = collections.Counter(RT.reviewer_family(r.get("reviewer")) for r in rs if r.get("reviewer"))
        live = [r for r in rs if not r.get("history")]
        findings[key] = {
            "repo": rs[0]["repo"], "title": rs[0].get("title"), "rule": rule_of(rs[0].get("title") or ""),
            "theme": RT.theme_of(rs[0].get("title") or ""), "prs": prs, "observations": len(rs),
            "open": sum(1 for r in live if r.get("semantic_state") != "closed"),
            "closed": sum(1 for r in rs if r.get("semantic_state") == "closed"),
            "false_positive_closures": sum(1 for r in rs if closed_as_false_positive(r)),
            "sightings": sightings, "frequency": round(sightings / pulses, 2),
            "reopens": sum(r.get("reopen_count", 0) for r in rs),
            "first_seen": min((r.get("first_seen") or "" for r in rs), default=""),
            "last_seen": max((r.get("last_seen") or "" for r in rs), default=""),
            "modal_path": max(paths, key=lambda p: (paths[p], p)) if paths else None,
            "modal_reviewer": max(reviewers, key=lambda v: (reviewers[v], v)) if reviewers else None,
            "recurrence": recurrence(len(prs), sightings, max((r.get("sighting_count", 1) for r in rs), default=1)),
            "tags": sorted({t for r in rs for t in tags_of(r.get("title"), r.get("head_ref"), path=r.get("path"))}),
        }

    observations = {}
    for key, rs in by_key.items():
        f = findings[key]
        for r in rs:
            if r.get("history") or r.get("semantic_state") == "closed":
                continue
            hints = []
            why = no_push(r)
            if why:
                hints.append({"code": why, "detail": "do not claim treat on this branch; fix on the default branch "
                                                    "and let the bot or fork owner pick it up"})
            others_fixed = [o for o in rs if o is not r and o.get("semantic_state") == "closed" and not closed_as_false_positive(o)]
            if others_fixed:
                hints.append({"code": "SEEN_FIXED", "detail": "same finding closed before on "
                              + ", ".join(sorted({f"{o['repo']}#{o['pr']}" for o in others_fixed})[:5])
                              + ": reuse that method, check for a regression"})
            if f["false_positive_closures"] >= 2:
                hints.append({"code": "FP_HISTORY", "detail": f"closed as a false positive {f['false_positive_closures']} times "
                              "before: verify this instance against those receipts first"})
            if r.get("reopen_count"):
                hints.append({"code": "REOPENED", "detail": f"provider reopened it {r['reopen_count']} time(s): diagnose, "
                              "do not assume a recurring defect"})
            if r.get("path") and GENERATED_RE.search(r["path"]) and f["theme"] != "security":
                hints.append({"code": "GENERATED_PATH", "detail": "generated or pinned output: regenerate, never hand-edit"})
            if gh is not None and r.get("pr_state", "open") == "open":
                hints += head_signals(r, gh)
            observations[r["id"]] = {"finding": key, "root_id": r.get("root_id"), "repo": r["repo"], "pr": r["pr"],
                                     "head_ref": r.get("head_ref"), "head_sha": r.get("head_sha"), "path": r.get("path"),
                                     "recurrence": f["recurrence"], "tags": f["tags"], "hints": hints}

    proposals = []
    groups = collections.defaultdict(list)
    for oid, o in observations.items():
        groups[(o["finding"], o["repo"], o["pr"], o["head_sha"])].append(oid)
    for (key, repo, pr, head), ids in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        roots = {observations[i]["root_id"] for i in ids}
        if len(ids) >= 2 and len(roots) >= 2 and not any(no_push({"repo": repo, **{
                "head_ref": observations[i]["head_ref"]}}) for i in ids):
            proposals.append({"kind": "GROUP_FINDINGS", "finding": key, "pr": f"{repo}#{pr}", "head_sha": head,
                              "item_ids": sorted(ids), "remediation_key": key,
                              "call": "operations.group_findings(store, item_ids, remediation_key, method=..., proof_refs=[...])",
                              "note": "only after a source read shows one treatment covers every member"})
    for key, f in sorted(findings.items(), key=lambda kv: (-len(kv[1]["prs"]), kv[0])):
        open_prs = sorted({f"{o['repo']}#{o['pr']}" for o in observations.values() if o["finding"] == key})
        if len(open_prs) >= 2:
            proposals.append({"kind": "ONE_METHOD_MANY_PACKETS", "finding": key, "prs": open_prs,
                              "note": "diagnose once, then apply the same method per branch packet; if the defect "
                                      "comes from the default branch, one fix there beats one per PR"})
        if f["recurrence"] == "SYSTEMIC" and f["open"]:
            proposals.append({"kind": "FOLD_BACK", "finding": key, "prs_seen": len(f["prs"]), "title": f["title"],
                              "note": "open one PR that stops the recurrence: a test, lint rule, gate rule, "
                                      "AGENTS.md pitfall or skill line"})
    return {"schema": SCHEMA, "programme": "CODE_MAROON", "authority": AUTHORITY, "merge_authority": False,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "ledger_revision": ledger.get("revision"), "pulses": len(ledger.get("pulses", {})),
            "findings": findings, "observations": observations, "proposals": proposals}


def public_counts(result: dict) -> dict:
    """Counts only: no titles, paths, PR numbers or keys."""
    return {"schema": PUBLIC_SCHEMA, "programme": "CODE_MAROON", "authority": AUTHORITY,
            "generated_at": result["generated_at"], "pulses": result["pulses"], "findings": len(result["findings"]),
            "open_observations": len(result["observations"]),
            "recurrence": dict(collections.Counter(f["recurrence"] for f in result["findings"].values())),
            "hints": dict(collections.Counter(h["code"] for o in result["observations"].values() for h in o["hints"])),
            "proposals": dict(collections.Counter(p["kind"] for p in result["proposals"]))}


def report(result: dict) -> str:
    pub = public_counts(result)
    lines = [f"# CODE MAROON hints {result['generated_at']}", "",
             f"{pub['open_observations']} open observations, {pub['findings']} findings over {pub['pulses']} pulse(s). "
             "Hints guide diagnosis; none of them is closure proof.", "",
             "| Recurrence | Findings |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in sorted(pub["recurrence"].items())]
    lines += ["", "| Hint | Observations |", "|---|---|"] + [f"| {k} | {v} |" for k, v in sorted(pub["hints"].items())]
    lines += ["", "## Proposals", ""]
    for p in result["proposals"]:
        where = p.get("pr") or ", ".join(p.get("prs", [])) or f"{p.get('prs_seen')} PRs"
        f = result["findings"][p["finding"]]
        name = (f["rule"] or f["title"] or "")[:70].replace("|", "/")
        lines.append(f"- **{p['kind']}** `{p['finding']}` {name} ({where}): {p['note']}")
    top = sorted(result["findings"].items(), key=lambda kv: (-len(kv[1]["prs"]), -kv[1]["sightings"]))[:20]
    lines += ["", "## Findings by reach", "", "| Recurrence | PRs | Open | Closed | Sightings | Freq | Modal path | Tags | Finding |",
              "|---|---|---|---|---|---|---|---|---|"]
    lines += [f"| {f['recurrence']} | {len(f['prs'])} | {f['open']} | {f['closed']} | {f['sightings']} | {f['frequency']} | "
              f"`{f['modal_path']}` | {','.join(f['tags'])} | {(f['rule'] or f['title'] or '')[:80].replace('|', '/')} |"
              for _, f in top]
    return "\n".join(lines) + "\n"


def save(obj, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def main(argv=None, gh=run_gh) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ledger", required=True, type=Path, help="private operations ledger (code_maroon.operations.v1)")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--history", type=Path, help="closed-PR raw_review.json from review_threads.py fetch")
    ap.add_argument("--check-heads", action="store_true", help="read GitHub for suggestion and anchor evidence")
    args = ap.parse_args(argv)
    history = json.loads(args.history.read_text(encoding="utf-8")) if args.history else None
    result = analyse(load_ledger(args.ledger), history, gh if args.check_heads else None)
    save(result, args.out / "MAROON_HINTS.json")
    save(public_counts(result), args.out / "MAROON_HINTS_PUBLIC.json")
    (args.out / "MAROON_HINTS.md").write_text(report(result), encoding="utf-8", newline="\n")
    pub = public_counts(result)
    print("MAROON_HINTS=PASS", f"findings={pub['findings']}", f"open={pub['open_observations']}",
          *(f"{k}={v}" for k, v in sorted(pub["proposals"].items())), f"out={args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
