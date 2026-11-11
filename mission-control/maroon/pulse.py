#!/usr/bin/env python3
"""CODE MAROON pulse: open-PR review threads -> verdicts -> clustered fix actions -> Kahn DAG -> workers.

One pulse reads every open PR (`open_threads.py`), decides what each unresolved thread needs, and turns
the result into a dependency graph of actions that can run in parallel without two workers ever writing
the same branch. It keeps a BD-queue ledger across pulses, so a finding seen before is recognised as such.

Per unresolved thread, a verdict (first match wins):

| Verdict | Evidence | Action | Confidence |
|---|---|---|---|
| ANSWERED | our last reply already proves the fix (resolve_answered.verdict_of, imported) | resolve | high |
| WAIT | our last reply names a fix PR that has not merged | none until it merges | - |
| HUMAN_PENDING | a person replied last | none: the owner answers | - |
| SUGGESTION_APPLIED | every ```suggestion``` block of the thread is in the file at the PR head | reply + resolve | high |
| OUT_OF_SCOPE | the thread's path is no longer changed by the PR at its head | reply + resolve, carry to ledger | high |
| FP_HISTORY | the same finding was kept as is on two or more earlier threads | reply + resolve | medium |
| SEEN_FIXED | the same finding was resolved on an earlier PR | worker checks for a regression | - |
| GENERATED | the path is a generated or pinned output | worker regenerates, never hand-edits | - |
| LIKELY_ADDRESSED | the thread is outdated and its anchor line is gone at the head | worker verifies, replies | - |
| NEEDS_FIX | anything else | worker fixes on the PR branch | - |

A finding is identified by `finding_key` = repo + theme + the significant words of its first line, so
Copilot and Codex flagging the same defect, or the same defect flagged on five PRs, is one finding.
Near-duplicates in a theme merge when their word sets overlap by at least `NEAR_DUP`.

Actions (DAG nodes), each with a SIPOC record and one write target at most per branch:

- `resolve:<repo>#<n>`: resolve threads whose evidence is already in hand (no code change). Runs first.
- `cluster:<key>`: a finding open on two or more PRs. One worker applies one coherent fix to each PR
  branch in turn, so N repeats are one DAG action, not N independent fixes.
- `fix:<repo>#<n>`: one worker per PR branch for the remaining threads of that PR.
- `fold:<key>`: a finding seen on three or more PRs over all pulses (SYSTEMIC). One worker turns it into
  method: a test, lint rule, gate rule, AGENTS.md or skill line, on its own branch.
- `close:<repo>#<n>`: after the workers, resolve the threads they answered.

Edges: cluster -> fix (same branch), fix -> close, and a chain between any nodes that write the same
branch. Waves are Kahn layers (`topo_layers`, jade_temple/devops/lifecycle.py, imported: AGENTS.md L4).

Authority: `act` replies to and resolves threads only with `--apply`, only for high-confidence verdicts
unless `--include-medium`, and only when the PR head and thread are unchanged since the read. It never
pushes code, merges, approves or dismisses a review. Workers push fixes to PR branches; nothing merges.

    python pulse.py plan --raw <dir>/raw_open.json --ledger <ledger.json> --me <login> --out <dir>
    python pulse.py act  --plan <dir>/MAROON_PULSE_PLAN.json --ledger <ledger.json> [--apply] [--include-medium]
    python pulse.py run  --owner GBOGEB --ledger <ledger.json> --out <dir> [--apply]   # fetch + plan + act
    python pulse.py seed --review <dir>/raw_review.json --ledger <ledger.json>          # history from closed PRs
    python pulse.py done --ledger <ledger.json> --node <id> --status DONE|FAILED [--note ...]
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import importlib.util
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RT = _load("maroon_review_threads", HERE / "review_threads.py")
RA = _load("maroon_resolve_answered", HERE / "resolve_answered.py")
OT = _load("maroon_open_threads", HERE / "open_threads.py")
LIFECYCLE = _load("jade_devops_lifecycle", HERE.parents[1] / "mission-control" / "jade_temple" / "devops" / "lifecycle.py")
RANK = _load("maroon_runner", HERE / "maroon.py").RANK

PLAN_SCHEMA = "code_maroon.pulse_plan.v1"
LEDGER_SCHEMA = "code_maroon.ledger.v1"
PUBLIC_SCHEMA = "code_maroon.pulse_public.v1"
MARKER = "<!-- code-maroon:{verdict}:{key} -->"
NEAR_DUP = 0.6
STALE_DISPATCH = timedelta(hours=24)
MAX_ATTEMPTS = 3
HIGH = {"ANSWERED", "SUGGESTION_APPLIED", "OUT_OF_SCOPE"}
MEDIUM = {"FP_HISTORY"}
NO_ACTION = {"WAIT", "HUMAN_PENDING"}
WORKER = {"NEEDS_FIX", "GENERATED", "LIKELY_ADDRESSED", "SEEN_FIXED"}
STOP = set("the this that with from into when then than there their these those which while where would could "
           "should must does have will also only just more less some each every any not but for are was were "
           "can its it's has had been being use uses used using file files line lines code here".split())
GENERATED_RE = re.compile(r"(^|/)(site|outputs?|generated|dist|build)/|(^|/)data/.*\.(json|csv|ya?ml)$|"
                          r"(package-lock\.json|poetry\.lock|uv\.lock|\.lock)$|_GENERATED|(^|/)snapshot\.json$")
# Files whose git OIDs other outputs pin (CLAUDE.md: JADE outputs pin p-process files, scale_dock.py and the
# census). A change to one needs the JADE DAG generator re-run, so the node carries that post-step.
CORE_OID_RE = re.compile(r"^mission-control/gogreen/scale_dock\.py$|(^|/)p-process[^/]*$|"
                         r"^mission-control/.*census.*\.(json|csv|ya?ml)$", re.I)
# A scanner's rule id (`yaml.github-actions.security.mutable-action-tag`, `python.lang.security.audit.x`, `B602`)
# is the strongest identity a finding has: two findings of one rule are one fix, two rules never are.
RULE_RE = re.compile(r"\b([a-z0-9_]+(?:\.[a-z0-9_-]+){2,})\b|\b(B\d{3}|[EFWS]\d{3,4}|CWE-\d+|CVE-\d{4}-\d{4,}|GHSA(?:-[a-z0-9]{4}){3})\b", re.I)
TAGS = [
    ("METHOD", re.compile(r"\bmethod|runbook|\bskill\b|sipoc|\bdag\b|agents\.md|playbook|fold[- ]?back", re.I)),
    ("REX", re.compile(r"\brex\b|lessons?[- ]learned|retro|post-?mortem", re.I)),
    ("SCALING_PROOF", re.compile(r"scal\w*[ _-]?proof|proof[ _-]of[ _-]scale", re.I)),
    ("SCALING_PILOT", re.compile(r"\bpilot", re.I)),
    ("SCALING", re.compile(r"\bscal(e|ing)\b|scale[_-]?dock|fan[- ]?out", re.I)),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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
    """A scanner rule id in the title, or None. A dotted id needs a hyphen or four segments, so prose that
    names code (`os.path.join`) is not mistaken for a rule."""
    for m in RULE_RE.finditer(title or ""):
        if m.group(2):
            return m.group(2).upper()
        if "-" in m.group(1) or m.group(1).count(".") >= 3:
            return m.group(1).lower()
    return None


def finding_key(repo: str, theme: str, title: str) -> str:
    rule = rule_of(title)
    ident = f"rule:{rule}" if rule else " ".join(sorted(words(title)))
    return hashlib.sha1(f"{repo}|{theme}|{ident}".encode()).hexdigest()[:12]


def tags_of(*texts: str, paths=()) -> list[str]:
    blob = " ".join(t or "" for t in texts)
    found = [name for name, rx in TAGS if rx.search(blob)]
    if any(CORE_OID_RE.search(p or "") for p in paths):
        found.append("CORE_OID")
    return found


# ---------------------------------------------------------------------------------------------------- ledger
def new_ledger(owner: str | None) -> dict:
    return {"schema": LEDGER_SCHEMA, "owner": owner, "pulses": [], "findings": {}, "queue": {}}


def load_ledger(path: Path, owner: str | None = None) -> dict:
    if not path.exists():
        return new_ledger(owner)
    ledger = json.loads(path.read_text(encoding="utf-8"))
    if ledger.get("schema") != LEDGER_SCHEMA:
        raise ValueError(f"{path}: schema {ledger.get('schema')!r}, expected {LEDGER_SCHEMA}")
    for key in ("pulses", "findings", "queue"):
        ledger.setdefault(key, [] if key == "pulses" else {})
    return ledger


def save_json(obj, path: Path) -> None:
    """Atomic write: a crash never leaves a half-written ledger or plan."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def recurrence(f: dict) -> str:
    prs = len(f["prs"])
    if prs >= 3:
        return "SYSTEMIC"
    if prs >= 2:
        return "RECURRING"
    if len(f["threads"]) >= 2 or f["pulses_seen"] >= 2:
        return "REPEAT"
    return "ONCE"


def observe(ledger: dict, key: str, repo: str, theme: str, title: str, thread: dict, pr_ref: str, when: str,
            verdict: str, tags: list[str], pulse_id: str) -> dict:
    """Add one thread to its finding: counts, frequency, modal path and reviewer, tags, first and last seen."""
    f = ledger["findings"].setdefault(key, {
        "repo": repo, "theme": theme, "title": title, "first_seen": when, "last_seen": when, "pulses": [],
        "pulses_seen": 0, "prs": [], "threads": [], "paths": {}, "reviewers": {}, "verdicts": {}, "tags": [],
        "status": "open", "evidence": [], "kept": 0, "fixed": 0})
    f["last_seen"] = max(f["last_seen"], when)
    f["first_seen"] = min(f["first_seen"], when)
    if pulse_id not in f["pulses"]:
        f["pulses"] = (f["pulses"] + [pulse_id])[-50:]
        f["pulses_seen"] += 1
    if pr_ref not in f["prs"]:
        f["prs"].append(pr_ref)
    tid = f"{pr_ref}/{thread['number']}"
    if tid not in f["threads"]:
        f["threads"].append(tid)
        for field, value in (("paths", thread.get("path")), ("reviewers", thread.get("reviewer_family"))):
            if value:
                f[field][value] = f[field].get(value, 0) + 1
    f.setdefault("thread_verdicts", {})[tid] = verdict  # latest verdict per thread: re-planning is idempotent
    f["verdicts"] = dict(collections.Counter(f["thread_verdicts"].values()))
    f["tags"] = sorted(set(f["tags"]) | set(tags))
    f["occurrences"] = len(f["threads"])
    f["frequency"] = round(f["occurrences"] / max(1, f["pulses_seen"]), 2)
    f["modal_path"] = max(f["paths"], key=lambda p: (f["paths"][p], p)) if f["paths"] else None
    f["modal_reviewer"] = max(f["reviewers"], key=lambda r: (f["reviewers"][r], r)) if f["reviewers"] else None
    f["recurrence"] = recurrence(f)
    return f


def seed(ledger: dict, review_raw: dict) -> int:
    """History from `review_threads.py fetch` (closed PRs): resolved threads count as fixed before."""
    n = 0
    for repo, entry in review_raw.get("repos", {}).items():
        for t in entry.get("alerts", []):
            key = finding_key(repo, t["theme"], t["title"])
            f = observe(ledger, key, repo, t["theme"], t["title"], t, f"{repo}#{t['pr']}", t.get("closed_at") or "",
                        "HISTORY_RESOLVED" if t["state"] == "resolved" else "HISTORY_OPEN",
                        tags_of(t["title"], paths=[t.get("path")]), "seed:" + review_raw.get("fetched_at", ""))
            if t["state"] == "resolved" and t.get("pr_merged"):
                f["fixed"] += 1
                f["evidence"] = (f["evidence"] + [f"resolved on merged {repo}#{t['pr']}"])[-10:]
            n += 1
    return n


# ---------------------------------------------------------------------------------------------------- triage
def verdict_of(thread: dict, pr: dict, me: str, finding: dict | None, pr_merged) -> tuple[str, str]:
    """(verdict, reason) for one unresolved thread on an open PR. Order matters: evidence before suspicion."""
    if thread.get("last_login") == me and thread.get("replies"):
        said = RA.verdict_of(thread.get("last_body", ""), pr_merged)
        if said.startswith(RA.WAIT):
            return "WAIT", said
        if said == "fixed on this merged PR":
            sha = (RA.FIX_SHA.match(RA.PREAMBLE.sub("", thread["last_body"]).strip()) or [None, ""])[1]
            if sha and any(c.startswith(sha) for c in pr.get("commits", [])):
                return "ANSWERED", f"fix commit {sha[:10]} is on this PR"
            return "NEEDS_FIX", f"reply names {sha[:10]}, which is not a commit of this PR"
        if not said.startswith(RA.SKIP):
            kept = re.match(r"Kept as is", RA.PREAMBLE.sub("", thread.get("last_body", "")).strip(), re.I)
            return "ANSWERED", "kept as is" if kept else said
    elif thread.get("replies") and RT.reviewer_family(thread.get("last_login")) == "human" \
            and thread.get("last_login") != thread.get("reviewer"):
        return "HUMAN_PENDING", f"{thread.get('last_login')} replied last"
    if thread.get("suggestion_applied"):
        return "SUGGESTION_APPLIED", f"suggestion present at head {pr['head_sha'][:10]}"
    if thread.get("path") and not thread.get("path_in_pr"):
        return "OUT_OF_SCOPE", f"{thread['path']} is no longer changed by the PR at {pr['head_sha'][:10]}"
    if finding and finding.get("kept", 0) >= 2:
        return "FP_HISTORY", f"kept as is {finding['kept']} times before"
    if finding and finding.get("fixed", 0) >= 1:
        return "SEEN_FIXED", "fixed before: " + "; ".join(finding.get("evidence", [])[-3:])
    if thread.get("path") and GENERATED_RE.search(thread["path"]) and thread.get("theme") != "security":
        return "GENERATED", f"{thread['path']} is a generated or pinned output: regenerate it"
    if thread.get("outdated") and thread.get("anchor_at_head") is False:
        return "LIKELY_ADDRESSED", "thread outdated and its anchor line is gone at the head"
    return "NEEDS_FIX", "no evidence of a fix at the head"


def clusters_of(items: list[dict]) -> dict[str, str]:
    """Union near-duplicate findings (same repo and theme, word overlap >= NEAR_DUP) onto one key."""
    parent = {i["key"]: i["key"] for i in items}

    def find(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k
    by_theme = collections.defaultdict(dict)
    for i in items:
        if not rule_of(i["title"]):  # rule findings are already exact; never merge two rules
            by_theme[(i["repo"], i["theme"])][i["key"]] = set(i["words"])
    for group in by_theme.values():
        keys = sorted(group)
        for x in range(len(keys)):
            for y in range(x + 1, len(keys)):
                a, b = group[keys[x]], group[keys[y]]
                if a and b and len(a & b) / len(a | b) >= NEAR_DUP:
                    parent[find(keys[y])] = find(keys[x])
    return {k: find(k) for k in parent}


def triage(raw: dict, ledger: dict, me: str, pr_merged) -> list[dict]:
    """Every unresolved thread on an open PR, with verdict, finding key (near-duplicates merged) and tags."""
    items = []
    for repo, entry in raw["repos"].items():
        for pr in entry.get("prs", []):
            for t in pr["threads"]:
                if t["state"] != "open":
                    continue
                key = finding_key(repo, t["theme"], t["title"])
                verdict, reason = verdict_of(t, pr, me, ledger["findings"].get(key), lambda n, r=repo: pr_merged(r, n))
                items.append({"repo": repo, "pr": pr["number"], "pr_ref": f"{repo}#{pr['number']}", "key": key,
                              "words": words(t["title"]), "theme": t["theme"], "title": t["title"],
                              "severity": t["severity"], "verdict": verdict, "reason": reason, "thread": t["number"],
                              "thread_id": t.get("thread_id"), "path": t.get("path"), "line": t.get("line"),
                              "url": t.get("url"), "reviewer": t.get("reviewer"), "last_id": t.get("last_id"),
                              "tags": tags_of(t["title"], pr.get("title"), pr.get("head_ref"), " ".join(pr.get("labels", [])),
                                              paths=[t.get("path")])})
    canon = clusters_of(items)
    for i in items:
        i["key"] = canon[i["key"]]
    return items


# ---------------------------------------------------------------------------------------------------- DAG
def priority(threads: list[dict], pr: dict | None, finding: dict | None = None) -> int:
    worst = max((RANK.get(t["severity"], 0) for t in threads), default=0)
    score = worst * 10 + len(threads)
    if pr:
        score += 30 if pr.get("mergeable_state") in ("blocked", "clean", "unstable") else 0
        score += 0 if pr.get("draft") else 20
    if finding:
        score += 5 * len(finding.get("prs", []))
    return score


def sipoc(node: dict) -> dict:
    return {
        "supplier": sorted({t["reviewer"] or "unknown" for t in node["threads"]}) or ["ledger"],
        "input": {"threads": [t["thread"] for t in node["threads"]], "heads": node.get("heads", {}),
                  "paths": sorted({t["path"] for t in node["threads"] if t["path"]})},
        "process": node["kind"],
        "output": {"resolve": "threads resolved with an evidence reply",
                   "cluster": "one coherent commit per PR branch, a `Fixed in <sha>` reply per thread",
                   "fix": "commits on the PR branch, a `Fixed in <sha>` or `Kept as is: <reason>` reply per thread",
                   "fold": "one PR that turns the finding into method (test, lint, gate rule, AGENTS.md or skill)",
                   "close": "threads answered by the workers, resolved"}[node["kind"]],
        "customer": ["merge gate (unresolved threads, first-pass-closure)", "CODE MAROON ledger"],
    }


BOT_BRANCH_RE = re.compile(r"^(dependabot|renovate|pre-commit-ci|copilot/)", re.I)


def no_push(pr: dict) -> str | None:
    """Why no worker may push to this PR's branch, or None. A fork is not ours; a bot rebases its branch
    and drops foreign commits. Their findings still count, and reach the default branch through fold-back."""
    if pr.get("head_repo") not in (None, pr["repo"]):
        return "FORK"
    if BOT_BRANCH_RE.match(pr.get("head_ref") or "") or (pr.get("author") or "").endswith("[bot]"):
        return "BOT_BRANCH"
    return None


def build_plan(raw: dict, ledger: dict, items: list[dict], me: str) -> dict:
    prs = {f"{repo}#{p['number']}": dict(p, repo=repo) for repo, e in raw["repos"].items() for p in e.get("prs", [])}
    nodes: dict[str, dict] = {}

    def node(nid, kind, threads, writes, pr=None, finding=None, **extra):
        n = {"id": nid, "kind": kind, "threads": threads, "writes": sorted(writes),
             "executor": "maroon-act" if kind in ("resolve", "close") else "worker",
             "heads": {ref: prs[ref]["head_sha"] for ref in sorted({t["pr_ref"] for t in threads})},
             "priority": priority(threads, pr, finding), "tags": sorted({g for t in threads for g in t["tags"]}),
             **extra}
        n["sipoc"] = sipoc(n)
        nodes[nid] = n
        return n

    by_pr = collections.defaultdict(list)
    for i in items:
        by_pr[i["pr_ref"]].append(i)
    open_by_key = collections.defaultdict(list)
    for i in items:
        if i["verdict"] in WORKER:
            open_by_key[i["key"]].append(i)
    pushable = {ref for ref, pr in prs.items() if not no_push(pr)}
    for k in list(open_by_key):
        open_by_key[k] = [t for t in open_by_key[k] if t["pr_ref"] in pushable]
    clustered = {k for k, ts in open_by_key.items() if len({t["pr_ref"] for t in ts}) >= 2}

    for ref, ts in sorted(by_pr.items()):
        pr = prs[ref]
        ready = [t for t in ts if t["verdict"] in HIGH | MEDIUM]
        if ready:
            node(f"resolve:{ref}", "resolve", ready, [], pr)
        work = [t for t in ts if t["verdict"] in WORKER and t["key"] not in clustered]
        if work and ref in pushable:
            node(f"fix:{ref}", "fix", work, [f"{pr['repo']}@{pr['head_ref']}"], pr,
                 branch=pr["head_ref"], base=pr["base_ref"], core_oid=any("CORE_OID" in t["tags"] for t in work))
    # Findings repeated on the same set of PRs are one worker: it walks those branches once and lands one
    # coherent commit per branch for all of them, instead of one chained worker per finding.
    by_refs = collections.defaultdict(list)
    for key in sorted(clustered):
        by_refs[tuple(sorted({t["pr_ref"] for t in open_by_key[key]}))].append(key)
    for refs, keys in sorted(by_refs.items()):
        ts = [t for k in keys for t in open_by_key[k]]
        cid = keys[0] if len(keys) == 1 else hashlib.sha1("|".join(keys).encode()).hexdigest()[:12]
        worst = max((ledger["findings"].get(k) or {} for k in keys), key=lambda f: len(f.get("prs", [])))
        node(f"cluster:{cid}", "cluster", ts, [f"{prs[r]['repo']}@{prs[r]['head_ref']}" for r in refs],
             None, worst, findings=keys, branches={r: prs[r]["head_ref"] for r in refs},
             core_oid=any("CORE_OID" in t["tags"] for t in ts))
    for key, f in sorted(ledger["findings"].items()):
        live = [i for i in items if i["key"] == key and i["verdict"] in WORKER]
        if f.get("recurrence") == "SYSTEMIC" and live and f.get("status") != "method":
            node(f"fold:{key}", "fold", live, [f"{f['repo']}@maroon/fold-{key}"], None, f,
                 recurrence=f["recurrence"], occurrences=f.get("occurrences"), prs_seen=len(f["prs"]))
    for nid in [n for n in nodes if n.startswith(("fix:", "cluster:"))]:
        for ref in nodes[nid]["heads"]:
            if nid.startswith("cluster:") and f"fix:{ref}" in nodes:
                continue  # the fix node closes after itself; a close per PR covers both
            if f"close:{ref}" not in nodes:
                node(f"close:{ref}", "close", [t for t in items if t["pr_ref"] == ref and t["verdict"] in WORKER], [],
                     prs[ref])

    edges = []
    for nid, n in nodes.items():
        if n["kind"] == "cluster":
            edges += [(nid, f"fix:{ref}", "FEEDFORWARD_SAME_BRANCH") for ref in n["heads"] if f"fix:{ref}" in nodes]
        if n["kind"] in ("fix", "cluster"):
            edges += [(nid, f"close:{ref}", "FEEDFORWARD_CLOSE") for ref in n["heads"] if f"close:{ref}" in nodes]
    # One writer per branch per wave: chain every pair of nodes that write the same target.
    order = {"cluster": 0, "fix": 1, "fold": 2}
    writers = collections.defaultdict(list)
    for nid, n in nodes.items():
        for w in n["writes"]:
            writers[w].append(nid)
    for w, ids in writers.items():
        ids.sort(key=lambda i: (order[nodes[i]["kind"]], -nodes[i]["priority"], i))
        edges += [(a, b, "FEEDFORWARD_WRITE_ORDER") for a, b in zip(ids, ids[1:])]
    edges = sorted(set(edges))
    waves = LIFECYCLE.topo_layers(sorted(nodes), edges)
    waves = [sorted(w, key=lambda i: (-nodes[i]["priority"], i)) for w in waves]
    for w in waves:  # proof, not hope: no wave holds two writers of one branch
        seen = collections.Counter(t for i in w for t in nodes[i]["writes"])
        clash = [t for t, c in seen.items() if c > 1]
        if clash:
            raise AssertionError(f"wave writes one branch twice: {clash}")
    for idx, w in enumerate(waves):
        for i in w:
            nodes[i]["wave"] = idx
    counts = collections.Counter(i["verdict"] for i in items)
    return {"schema": PLAN_SCHEMA, "programme": "CODE_MAROON", "fetched_at": raw["fetched_at"], "planned_at": utc_now(),
            "me": me, "merge_authority": False,
            "heads": {repo: e.get("base_head_sha") for repo, e in raw["repos"].items()},
            "coverage": {repo: e.get("coverage") for repo, e in raw["repos"].items()},
            "gaps": {repo: e.get("gaps", []) for repo, e in raw["repos"].items() if e.get("gaps")},
            "threads_open": len(items), "verdicts": dict(sorted(counts.items())),
            "findings": len({i["key"] for i in items}), "clusters": len(clustered),
            "nodes": nodes, "edges": [list(e) for e in edges], "waves": waves}


def pulse_id_of(raw: dict) -> str:
    return "P" + raw["fetched_at"].replace("-", "").replace(":", "")[:13]


def record_findings(ledger: dict, raw: dict, items: list[dict]) -> str:
    """Fold this pulse's threads into the ledger's findings before planning, so recurrence is current."""
    pulse_id = pulse_id_of(raw)
    for i in items:
        observe(ledger, i["key"], i["repo"], i["theme"], i["title"], {"number": i["thread"], "path": i["path"],
                "reviewer_family": RT.reviewer_family(i["reviewer"])}, i["pr_ref"], raw["fetched_at"], i["verdict"],
                i["tags"], pulse_id)
    return pulse_id


def augment(ledger: dict, raw: dict, items: list[dict], plan: dict) -> str:
    """Record the pulse in the BD-queue ledger: every node's queue state, and the pulse itself."""
    pulse_id = pulse_id_of(raw)
    live = set(plan["nodes"])
    stale = (datetime.fromisoformat(raw["fetched_at"]) - STALE_DISPATCH).isoformat(timespec="seconds")
    for nid, q in ledger["queue"].items():
        if q["state"] in ("QUEUED", "DISPATCHED") and nid not in live:
            q.update(state="OBSERVED_CLOSED", closed_at=raw["fetched_at"])  # its threads are gone
        elif q["state"] == "DISPATCHED" and (q.get("at") or "") < stale:
            q.update(state="QUEUED", stale_dispatch=q.get("at"))  # a worker that never reported: offer it again
    for nid, n in plan["nodes"].items():
        q = ledger["queue"].setdefault(nid, {"state": "QUEUED", "first_queued": raw["fetched_at"], "attempts": 0})
        if q["state"] == "FAILED" and q.get("attempts", 0) >= MAX_ATTEMPTS:
            q.update(state="BLOCKED", blocked_at=raw["fetched_at"])  # stop re-dispatching: the owner decides
        elif q["state"] in ("DONE", "OBSERVED_CLOSED", "FAILED"):
            q.update(state="QUEUED", reopened=raw["fetched_at"])  # same node needed again: it recurred
            q["recurred"] = q.get("recurred", 0) + 1
        q.update(kind=n["kind"], wave=n["wave"], priority=n["priority"], threads=len(n["threads"]),
                 heads=n["heads"], last_pulse=pulse_id)
    ledger["pulses"] = (ledger["pulses"] + [{
        "id": pulse_id, "fetched_at": raw["fetched_at"], "heads": plan["heads"], "threads_open": plan["threads_open"],
        "verdicts": plan["verdicts"], "nodes": len(plan["nodes"]), "waves": len(plan["waves"])}])[-200:]
    return pulse_id


def ready_nodes(plan: dict, ledger: dict) -> list[str]:
    """Worker nodes whose every predecessor is done: the next disjoint set to dispatch."""
    done = {nid for nid, q in ledger["queue"].items() if q["state"] in ("DONE", "OBSERVED_CLOSED")}
    preds = collections.defaultdict(set)
    for a, b, _ in plan["edges"]:
        preds[b].add(a)
    out = []
    for wave in plan["waves"]:
        for nid in wave:
            n = plan["nodes"][nid]
            blocking = {p for p in preds[nid] if plan["nodes"][p]["executor"] == "worker"}
            if n["executor"] == "worker" and ledger["queue"].get(nid, {}).get("state") == "QUEUED" and blocking <= done:
                out.append(nid)
    # disjoint by construction inside a wave; across waves, drop any later node that writes a target already taken
    taken, picked = set(), []
    for nid in out:
        w = set(plan["nodes"][nid]["writes"])
        if not w & taken:
            picked.append(nid)
            taken |= w
    return picked


def brief(n: dict, plan: dict) -> str:
    """The whole contract a worker gets: one node, its threads, its limits, its receipt line."""
    lines = [f"# CODE MAROON worker: `{n['id']}`", "",
             f"Kind **{n['kind']}**, wave {n['wave']}, priority {n['priority']}. Tags: {', '.join(n['tags']) or 'none'}.", ""]
    if n["kind"] == "fold":
        lines += [f"This finding was seen {n.get('occurrences')} times on {n.get('prs_seen')} PRs. Do not fix the instances "
                  "(other nodes do). Make it stop recurring: add the smallest test, lint rule, gate rule, AGENTS.md "
                  "pitfall or skill line that catches it, on a new branch from the default branch, in its own PR.", ""]
    for ref, head in n["heads"].items():
        branch = (n.get("branches") or {}).get(ref) or n.get("branch")
        lines.append(f"- `{ref}` branch `{branch}` head `{head}`")
    if n.get("findings"):
        lines += ["", f"These {len(n['findings'])} finding(s) repeat across the PRs above. Fix each once, the same "
                  "way on every branch, in one commit per branch. If the defect comes from the default branch "
                  "rather than these PRs, say so in your report: one fix there is better than N."]
    lines += ["", "| Thread | Verdict | Severity | Where | Finding |", "|---|---|---|---|---|"]
    for t in n["threads"]:
        lines.append(f"| [{t['thread']}]({t['url']}) | {t['verdict']} | {t['severity']} | `{t['path']}:{t['line']}` | "
                     f"{t['title'].replace('|', '/')} |")
    lines += ["", "## Contract", "",
              "1. Work in your own worktree (`git worktree add`). Check out the branch and stop with `HEAD_MOVED` if its head "
              "is not the one above: someone else is on it.",
              "2. Deep-read every thread on the head. Verdict hints are triage, not proof.",
              "3. Valid finding: smallest fix, with a failing-before and passing-after test where one is practical. "
              "One coherent commit per branch for a cluster. Generated paths: regenerate, never hand-edit.",
              "4. Invalid finding: reply `Kept as is: <reason>` on the thread. No code change.",
              "5. Push to the PR branch (never force). Then reply on each fixed thread `Fixed in <full sha>.` "
              "(that exact form is what `act`/`resolve_answered` accept as evidence).",
              "6. Verify on the repo's declared runtime (`.python-version` / CI matrix). The head moved, so the PR's "
              "first-pass-closure receipt must be written again: `python scripts/fpc_receipt.py --pr N --write` where the repo has it.",
              "7. Never merge, approve, dismiss a review or resolve a thread yourself: `close` nodes resolve after you.",
              f"8. Last line of your report: `MAROON_WORKER=DONE|FAILED node={n['id']} commits=<shas> replies=<n>`."]
    if n.get("core_oid"):
        lines.append("9. A CORE_OID path is touched: re-run the JADE DAG generator and commit its outputs in the same push.")
    return "\n".join(lines) + "\n"


def public_counts(plan: dict, ledger: dict) -> dict:
    """Counts only (no paths, titles or thread text), safe beside MAROON_PUBLIC.json."""
    rec = collections.Counter(f.get("recurrence") for f in ledger["findings"].values())
    return {"schema": PUBLIC_SCHEMA, "programme": "CODE_MAROON", "fetched_at": plan["fetched_at"],
            "merge_authority": False, "threads_open": plan["threads_open"], "verdicts": plan["verdicts"],
            "findings": plan["findings"], "clusters": plan["clusters"], "nodes": len(plan["nodes"]),
            "waves": len(plan["waves"]), "ledger_findings": len(ledger["findings"]), "recurrence": dict(rec),
            "pulses": len(ledger["pulses"])}


def report(plan: dict, ledger: dict, ready: list[str]) -> str:
    lines = [f"# CODE MAROON pulse {plan['fetched_at']}", "",
             f"{plan['threads_open']} unresolved threads on open PRs -> {plan['findings']} findings "
             f"({plan['clusters']} repeated across PRs) -> {len(plan['nodes'])} actions in {len(plan['waves'])} waves.", "",
             "| Verdict | Threads |", "|---|---|"]
    lines += [f"| {v} | {c} |" for v, c in plan["verdicts"].items()]
    lines += ["", "## Waves (Kahn layers; one writer per branch per wave)", ""]
    for i, w in enumerate(plan["waves"]):
        lines.append(f"{i}. " + ", ".join(f"`{nid}` ({len(plan['nodes'][nid]['threads'])})" for nid in w))
    lines += ["", "## Ready for workers now", ""] + [f"- `{nid}`" for nid in ready] + ["" if ready else "- none"]
    top = sorted((f for f in ledger["findings"].values() if f.get("recurrence") in ("RECURRING", "SYSTEMIC")),
                 key=lambda f: (-len(f["prs"]), -f.get("occurrences", 0)))[:15]
    lines += ["", "## Recurring findings (ledger)", "", "| Recurrence | PRs | Seen | Theme | Modal path | Tags | Finding |",
              "|---|---|---|---|---|---|---|"]
    lines += [f"| {f['recurrence']} | {len(f['prs'])} | {f.get('occurrences')} | {f['theme']} | `{f.get('modal_path')}` | "
              f"{','.join(f['tags'])} | {f['title'][:90].replace('|', '/')} |" for f in top]
    if plan["gaps"]:
        lines += ["", "## Gaps", ""] + [f"- {r}: {g}" for r, gs in plan["gaps"].items() for g in gs]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------------------------------- act
RESOLVE_MUTATION = "mutation($id: ID!) { resolveReviewThread(input: {threadId: $id}) { thread { isResolved } } }"


def reply_text(t: dict, head: str) -> str | None:
    """The evidence reply for a verdict, phrased so resolve_answered.verdict_of recognises it later."""
    marker = MARKER.format(verdict=t["verdict"], key=t["key"])
    if t["verdict"] == "ANSWERED":
        return None
    if t["verdict"] == "SUGGESTION_APPLIED":
        return f"Fixed in {head}: the suggested change is on the PR head.\n\n{marker}"
    if t["verdict"] == "OUT_OF_SCOPE":
        return (f"Kept as is: `{t['path']}` is no longer changed by this PR at {head[:10]}. CODE MAROON carries the "
                f"finding as `{t['key']}` for the default branch.\n\n{marker}")
    if t["verdict"] == "FP_HISTORY":
        return (f"Kept as is: the same finding (`{t['key']}`) was reviewed and kept on earlier threads. Reopen if this "
                f"instance differs.\n\n{marker}")
    return None


def act(plan: dict, ledger: dict, gh=RT.run_gh, apply: bool = False, include_medium: bool = False,
        max_actions: int = 25, use_ccr: bool = False) -> list[dict]:
    """Reply to and resolve the threads of `resolve` and `close` nodes, re-checking everything first."""
    allowed = HIGH | (MEDIUM if include_medium else set())
    done = {nid for nid, q in ledger["queue"].items() if q.get("state") in ("DONE", "OBSERVED_CLOSED")}
    results, budget = [], max_actions
    me = plan["me"]
    for wave in plan["waves"]:
        for nid in wave:
            n = plan["nodes"][nid]
            if n["executor"] != "maroon-act":
                continue
            workers = {a for a, b, _ in plan["edges"] if b == nid}
            if n["kind"] == "close" and not workers <= done:
                results.append({"node": nid, "outcome": "WAIT_WORKERS", "waiting_on": sorted(workers - done)})
                continue
            for ref, head in n["heads"].items():
                repo, number = ref.rsplit("#", 1)
                todo = [t for t in n["threads"] if t["pr_ref"] == ref and t["verdict"] in allowed]
                if n["kind"] == "close":
                    todo = []  # close nodes act on what the workers answered: re-read and re-triage below
                    try:
                        fresh = OT.read_pr(gh, repo, int(number), OT.thread_index_ccr if use_ccr else OT.thread_index_graphql, {})
                    except (RuntimeError, KeyError, ValueError) as error:
                        results.append({"node": nid, "pr": ref, "outcome": "GAP", "why": str(error)[:120]})
                        continue
                    cache = {}

                    def merged(num, repo=repo, cache=cache):
                        if num not in cache:
                            cache[num] = bool(RT.gh_json(gh, f"repos/{repo}/pulls/{num}").get("merged_at"))
                        return cache[num]
                    for t in fresh["threads"]:
                        if t["state"] == "open" and t["number"] in {x["thread"] for x in n["threads"]}:
                            v, why = verdict_of(t, fresh, me, None, merged)
                            if v == "ANSWERED":
                                todo.append({"pr_ref": ref, "thread": t["number"], "thread_id": t.get("thread_id"),
                                             "verdict": v, "reason": why, "key": "", "last_id": t.get("last_id")})
                    head = fresh["head_sha"]
                if not todo:
                    continue
                try:
                    now = RT.gh_json(gh, f"repos/{repo}/pulls/{number}")
                    index = (OT.thread_index_ccr if use_ccr else OT.thread_index_graphql)(gh, repo, int(number))
                except RuntimeError as error:
                    results += [{"node": nid, "pr": ref, "thread": t["thread"], "outcome": "GAP", "why": str(error)[:120]}
                                for t in todo]
                    continue
                for t in todo:
                    base = {"node": nid, "pr": ref, "thread": t["thread"], "verdict": t["verdict"]}
                    if now.get("state") != "open":
                        results.append({**base, "outcome": "SKIP_NOT_OPEN"})
                        continue
                    if now["head"]["sha"] != head:
                        results.append({**base, "outcome": "SKIP_HEAD_MOVED"})
                        continue
                    meta = index.get(t["thread"])
                    if not meta or meta["resolved"]:
                        results.append({**base, "outcome": "SKIP_ALREADY_RESOLVED" if meta else "SKIP_THREAD_GONE"})
                        continue
                    if budget <= 0:
                        results.append({**base, "outcome": "SKIP_BUDGET"})
                        continue
                    text = reply_text(t, head)
                    if not apply:
                        results.append({**base, "outcome": "WOULD_" + ("REPLY_AND_RESOLVE" if text else "RESOLVE")})
                        budget -= 1
                        continue
                    if text:
                        code, _, err = gh(["api", "-X", "POST", f"repos/{repo}/pulls/{number}/comments/{t['thread']}/replies",
                                           "-f", f"body={text}"])
                        if code:
                            results.append({**base, "outcome": "FAIL_REPLY", "why": err.strip()[:120]})
                            continue
                    if use_ccr or not meta.get("thread_id"):
                        code, _, err = gh(["api", "-X", "POST", f"repos/{repo}/pulls/{number}/ccr/comments/{t['thread']}/resolve"])
                    else:
                        code, _, err = gh(["api", "graphql", "-f", f"query={RESOLVE_MUTATION}", "-f", f"id={meta['thread_id']}"])
                    results.append({**base, "outcome": "FAIL_RESOLVE" if code else ("REPLIED_AND_RESOLVED" if text else "RESOLVED"),
                                    **({"why": err.strip()[:120]} if code else {})})
                    budget -= 1
                    if not code:
                        f = ledger["findings"].get(t.get("key") or "")
                        if f:
                            if t["verdict"] == "OUT_OF_SCOPE":
                                pass  # not this PR's debt; the finding stays open for the default branch
                            elif t["verdict"] == "FP_HISTORY" or t.get("reason") == "kept as is":
                                f["kept"] += 1
                            else:
                                f["fixed"] += 1
                                f["evidence"] = (f["evidence"] + [f"{t['verdict']} on {ref}"])[-10:]
    for nid, n in plan["nodes"].items():
        if n["executor"] == "maroon-act" and apply:
            mine = [r for r in results if r["node"] == nid]
            if mine and all(r["outcome"].startswith(("RESOLVED", "REPLIED", "SKIP_ALREADY")) for r in mine):
                ledger["queue"].setdefault(nid, {"attempts": 0})["state"] = "DONE"
    return results


# ---------------------------------------------------------------------------------------------------- CLI
def merged_lookup(gh=RT.run_gh):
    cache: dict[tuple, bool] = {}

    def merged(repo: str, number: int) -> bool:
        if (repo, number) not in cache:
            try:
                cache[(repo, number)] = bool(RT.gh_json(gh, f"repos/{repo}/pulls/{number}").get("merged_at"))
            except RuntimeError:
                cache[(repo, number)] = False  # unreadable proves nothing: treated as not merged (WAIT)
        return cache[(repo, number)]
    return merged


def plan_pulse(raw: dict, ledger: dict, me: str, out: Path, pr_merged) -> dict:
    items = triage(raw, ledger, me, pr_merged)
    record_findings(ledger, raw, items)
    plan = build_plan(raw, ledger, items, me)
    pulse_id = augment(ledger, raw, items, plan)
    plan["pulse"] = pulse_id
    ready = ready_nodes(plan, ledger)
    plan["ready"] = ready
    out.mkdir(parents=True, exist_ok=True)
    save_json(plan, out / "MAROON_PULSE_PLAN.json")
    save_json(public_counts(plan, ledger), out / "MAROON_PULSE_PUBLIC.json")
    (out / "MAROON_PULSE.md").write_text(report(plan, ledger, ready), encoding="utf-8", newline="\n")
    briefs = out / "briefs"
    briefs.mkdir(exist_ok=True)
    for nid in ready:
        (briefs / (re.sub(r"[^A-Za-z0-9._-]+", "_", nid) + ".md")).write_text(brief(plan["nodes"][nid], plan),
                                                                              encoding="utf-8", newline="\n")
    return plan


def main(argv=None, gh=RT.run_gh) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan", help="verdicts, clusters, DAG and briefs from raw_open.json; updates the ledger")
    p.add_argument("--raw", required=True, type=Path)
    a = sub.add_parser("act", help="reply to and resolve evidence-backed threads (dry run without --apply)")
    a.add_argument("--plan", required=True, type=Path)
    r = sub.add_parser("run", help="fetch + plan + act: the scheduled pulse")
    who = r.add_mutually_exclusive_group(required=True)
    who.add_argument("--owner")
    who.add_argument("--repos")
    s = sub.add_parser("seed", help="add closed-PR history (review_threads.py raw) to the ledger")
    s.add_argument("--review", required=True, type=Path)
    d = sub.add_parser("done", help="record a worker receipt for a node")
    d.add_argument("--node", required=True)
    d.add_argument("--status", required=True, choices=("DONE", "FAILED", "DISPATCHED"))
    d.add_argument("--note", default="")
    for x in (p, a, r, s, d):
        x.add_argument("--ledger", required=True, type=Path)
    for x in (p, r):
        x.add_argument("--out", required=True, type=Path)
        x.add_argument("--me", help="login whose replies count as evidence (default: the gh login)")
    for x in (a, r):
        x.add_argument("--apply", action="store_true", help="write to GitHub; without it, report only")
        x.add_argument("--include-medium", action="store_true", help="also act on FP_HISTORY verdicts")
        x.add_argument("--max-actions", type=int, default=25)
        x.add_argument("--threads", choices=("graphql", "ccr"), default="graphql")
    args = ap.parse_args(argv)
    gh = OT.retrying(gh)
    ledger = load_ledger(args.ledger)

    if args.cmd == "seed":
        n = seed(ledger, json.loads(args.review.read_text(encoding="utf-8")))
        save_json(ledger, args.ledger)
        print("MAROON_SEED=PASS", f"threads={n}", f"findings={len(ledger['findings'])}")
        return 0
    if args.cmd == "done":
        q = ledger["queue"].setdefault(args.node, {"attempts": 0})
        q.update(state=args.status, note=args.note[:300], at=utc_now())
        q["attempts"] = q.get("attempts", 0) + (args.status == "DISPATCHED")
        save_json(ledger, args.ledger)
        print("MAROON_DONE=PASS", f"node={args.node}", f"state={args.status}")
        return 0
    if args.cmd in ("plan", "run"):
        me = args.me or RT.gh_json(gh, "user")["login"]
        if args.cmd == "run":
            repos = [x.strip() for x in args.repos.split(",") if x.strip()] if args.repos else None
            raw = OT.fetch(args.owner, repos, gh=gh,
                           index_of=OT.thread_index_ccr if args.threads == "ccr" else OT.thread_index_graphql)
            save_json(raw, args.out / "raw_open.json")
            ledger["owner"] = ledger.get("owner") or raw["owner"]
        else:
            raw = json.loads(args.raw.read_text(encoding="utf-8"))
        plan = plan_pulse(raw, ledger, me, args.out, merged_lookup(gh))
        print("MAROON_PULSE_PLAN=PASS", f"pulse={plan['pulse']}", f"threads_open={plan['threads_open']}",
              f"findings={plan['findings']}", f"clusters={plan['clusters']}", f"nodes={len(plan['nodes'])}",
              f"waves={len(plan['waves'])}", f"ready={len(plan['ready'])}", f"out={args.out}")
        if args.cmd == "plan":
            save_json(ledger, args.ledger)
            return 0
    else:
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        if plan.get("schema") != PLAN_SCHEMA:
            raise SystemExit(f"{args.plan}: not a {PLAN_SCHEMA} plan")
    results = act(plan, ledger, gh, apply=args.apply, include_medium=args.include_medium,
                  max_actions=args.max_actions, use_ccr=args.threads == "ccr")
    save_json(ledger, args.ledger)
    out_dir = args.out if args.cmd == "run" else args.plan.parent
    save_json(results, out_dir / "MAROON_ACT.json")
    tally = collections.Counter(x["outcome"] for x in results)
    print("MAROON_ACT=PASS", f"apply={args.apply}", *(f"{k}={v}" for k, v in sorted(tally.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
