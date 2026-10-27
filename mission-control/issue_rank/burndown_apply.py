#!/usr/bin/env python3
"""Burndown slices over an issue_rank pulse: verification packs and checkbox proposals.

Two slices, both dry-run unless ``--apply`` is given:

``verify``    For every open checklist item that references a closed child, gather
              the child's evidence (merge SHA, check rollup on the merge commit,
              review decision, issue close reason) and classify the item:
              ``TICK_READY`` (the item is a bare reference and every child merged or
              completed), ``VERIFY`` (children closed, the item asks for more than
              closure), ``WITHDRAW_CANDIDATE`` (a child closed as not planned or
              unmerged), ``WAIT`` (a child still open).
``checkbox``  For issues whose DoD / DoV / STEPS criteria are plain bullets, propose
              turning each declared bullet into ``- [ ]``. Nothing is ticked.

``--apply`` edits issue bodies through the GitHub API. It re-reads the live body,
recomputes the change on it, refuses if the body changed since the snapshot, and
appends one sha256-chained row per edit to ``edits.jsonl``. Issue edits are owner
decisions: apply only with the owner's explicit go-ahead. Ticks are not proof; a
``TICK_READY`` tick records that the referenced child merged or completed, nothing more.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import issue_rank as ir  # noqa: E402

tw = ir.triway
SCHEMA = "jade.issue-burndown.slices.v1"
EDIT_SCHEMA = "jade.issue-burndown.edit.v1"
# Words that make an item ask for more than "the child closed".
DEMANDS = re.compile(
    r"\b(verif\w*|review\w*|owner|evidence|exact[- ]head|approv\w*|after|only|decid\w*|authori[sz]\w*"
    r"|security|prove|proof|validat\w*|confirm\w*|disposition|admission|gate|record|human|eligible)\b", re.I)
BARE_REST = 40  # characters of text left after removing references and markup


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def bare(text: str) -> bool:
    """An item that is essentially just its references (``#858``, ``#858 hub runner``)."""
    rest = tw.REF.sub("", text)
    rest = re.sub(r"[`*_~\[\]()>:|,;.\-–—/#]+", " ", rest).strip()
    return len(rest) <= BARE_REST and not DEMANDS.search(rest)


# ---------------------------------------------------------------- evidence

CHILD_Q = ("... on Issue{state stateReason closedAt} "
           "... on PullRequest{state merged mergedAt reviewDecision "
           "mergeCommit{oid statusCheckRollup{state}}}")


def child_evidence(gh, keys: list[str], batch: int = 60) -> dict[str, dict | None]:
    out: dict[str, dict | None] = {}
    for start in range(0, len(keys), batch):
        chunk = keys[start:start + batch]
        parts, alias = [], {}
        for i, k in enumerate(chunk):
            repo, n = k.split("#")
            owner, name = repo.split("/")
            alias[f"c{i}"] = k
            parts.append(f'c{i}:repository(owner:"{owner}",name:"{name}"){{issueOrPullRequest(number:{int(n)})'
                         f"{{__typename {CHILD_Q}}}}}")
        data = gh("query{" + " ".join(parts) + "}", allow_not_found=True)
        for a, k in alias.items():
            node = ((data or {}).get(a) or {}).get("issueOrPullRequest")
            out[k] = node
    return out


def child_verdict(node: dict | None) -> str:
    if not node:
        return "UNKNOWN"
    if node["__typename"] == "PullRequest":
        if node["state"] == "OPEN":
            return "OPEN"
        return "DONE" if node.get("merged") else "UNMERGED"
    if node["state"] == "OPEN":
        return "OPEN"
    return "DONE" if node.get("stateReason") in (None, "COMPLETED") else "NOT_PLANNED"


def verify_items(issue: dict, evidence: dict[str, dict | None]) -> list[dict]:
    rows = []
    for ln, line in enumerate((issue.get("body") or "").splitlines()):
        m = tw.ITEM.match(line)
        if not m or m.group(1) != " ":
            continue
        refs = [ir.key(r["repo"], r["number"]) for r in ir.extract_refs(line, issue["repo"])]
        refs = [r for r in refs if r in evidence]
        if not refs:
            continue
        verdicts = {r: child_verdict(evidence[r]) for r in refs}
        if not any(v in ("DONE", "UNMERGED", "NOT_PLANNED") for v in verdicts.values()):
            continue
        if any(v in ("OPEN", "UNKNOWN") for v in verdicts.values()):
            cls = "WAIT"
        elif any(v in ("UNMERGED", "NOT_PLANNED") for v in verdicts.values()):
            cls = "WITHDRAW_CANDIDATE"
        elif bare(m.group(2)):
            cls = "TICK_READY"
        else:
            cls = "VERIFY"
        rows.append({"line": ln, "text": m.group(2)[:300], "class": cls,
                     "children": {r: {"verdict": verdicts[r], **_brief(evidence[r])} for r in refs}})
    return rows


def _brief(node: dict | None) -> dict:
    if not node:
        return {}
    if node["__typename"] == "PullRequest":
        mc = node.get("mergeCommit") or {}
        return {"type": "PR", "merged_at": node.get("mergedAt"), "merge_sha": mc.get("oid"),
                "merge_checks": (mc.get("statusCheckRollup") or {}).get("state"),
                "review_decision": node.get("reviewDecision")}
    return {"type": "Issue", "closed_at": node.get("closedAt"), "state_reason": node.get("stateReason")}


# ---------------------------------------------------------------- checkbox

def checkbox_body(body: str) -> tuple[str, int]:
    """``body`` with each declared DoD / DoV / STEPS bullet turned into ``- [ ]``."""
    declared = {x["text"] for sec in tw.checklist(body).values()
                for x in sec["declared"] if x["form"] == "BULLET"}
    out, n, fence, section = [], 0, None, "OTHER"
    for line in body.splitlines(keepends=True):
        mark = line.strip()[:3]
        if fence:
            fence = None if mark == fence else fence
            out.append(line)
            continue
        if mark in ("```", "~~~"):
            fence = mark
            out.append(line)
            continue
        h = tw.HEADING.match(line.rstrip("\r\n"))
        if h:
            section = tw._section(next(g for g in h.groups() if g))[0]
        b = tw.BULLET.match(line.rstrip("\r\n"))
        if (b and not h and section != "OTHER" and not tw.ITEM.match(line.rstrip("\r\n"))
                and b.group(1)[:300] in declared):
            lead = line[:len(line) - len(line.lstrip())]
            rest = line.lstrip()
            marker = re.match(r"(?:>\s*)*(?:[-*+]|\d+[.)])\s+", rest).group(0)
            line = lead + marker + "[ ] " + rest[len(marker):]
            n += 1
        out.append(line)
    return "".join(out), n


# ---------------------------------------------------------------- slices

def slices(snapshot: dict, model: dict, gh, top: int = 10, skip: set[str] = frozenset()) -> dict:
    issues = {ir.key(r, i["number"]): {**i, "repo": r}
              for r, d in snapshot["repos"].items() for i in d["issues"]}
    ranked = [i for i in model["items"] if i["type"] == "Issue" and i["key"] in issues]
    # Every checklist reference of every open issue, so WAIT / TICK_READY are complete.
    wanted = sorted({ir.key(r["repo"], r["number"])
                     for k in issues for line in (issues[k].get("body") or "").splitlines()
                     if tw.ITEM.match(line) for r in ir.extract_refs(line, issues[k]["repo"])})
    evidence = child_evidence(gh, wanted) if wanted else {}
    verify = []
    for it in ranked:
        rows = verify_items(issues[it["key"]], evidence)
        if rows:
            verify.append({"issue": it["key"], "rank": it["rank_global"], "lane": it["lane"],
                           "progress": it["progress"], "private": it.get("private"), "items": rows})
    # skip: issues whose bullets are options or dispositions, not criteria (owner judgement).
    track = [it for it in ranked if it["lane"] == "TRACK_DOD" and it["key"] not in skip][:top]
    checkbox = []
    for it in track:
        body = issues[it["key"]].get("body") or ""
        new, n = checkbox_body(body)
        if n:
            checkbox.append({"issue": it["key"], "rank": it["rank_global"], "private": it.get("private"),
                             "converted": n, "before_sha256": sha(body), "after_sha256": sha(new),
                             "diff": _diff(body, new)})
    counts: dict[str, int] = {}
    for v in verify:
        for r in v["items"]:
            counts[r["class"]] = counts.get(r["class"], 0) + 1
    return {"schema": SCHEMA, "fetched_at": snapshot.get("fetched_at"),
            "heads": {r: d.get("head_sha") for r, d in snapshot["repos"].items()},
            "authority_transfer": False, "applied": False,
            "summary": {"verify_items": counts, "verify_issues": len(verify),
                        "checkbox_issues": len(checkbox),
                        "checkbox_items": sum(c["converted"] for c in checkbox)},
            "verify": verify, "checkbox": checkbox}


def _diff(a: str, b: str) -> list[str]:
    return [f"- {x}\n+ {y}" for x, y in zip(a.splitlines(), b.splitlines()) if x != y]


# ---------------------------------------------------------------- apply

def tick_body(body: str, lines: set[int]) -> str:
    out = []
    for i, line in enumerate(body.splitlines(keepends=True)):
        if i in lines:
            line = re.sub(r"\[ \]", "[x]", line, count=1)
        out.append(line)
    return "".join(out)


def append_edit(path: Path, record: dict) -> dict:
    prev = None
    if path.exists():
        rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
        prev = rows[-1]["row_sha256"] if rows else None
    row = {"schema": EDIT_SCHEMA, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "prev_sha256": prev, **record}
    row["row_sha256"] = sha(json.dumps(row, sort_keys=True))
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
    return row


def live_body(repo: str, number: int) -> str:
    out = subprocess.run(["gh", "api", f"repos/{repo}/issues/{number}", "--jq", ".body // \"\""],
                         capture_output=True, text=True, check=True, encoding="utf-8").stdout
    return out[:-1] if out.endswith("\n") else out


def patch_body(repo: str, number: int, body: str) -> None:
    subprocess.run(["gh", "api", "-X", "PATCH", f"repos/{repo}/issues/{number}", "--input", "-"],
                   input=json.dumps({"body": body}), capture_output=True, text=True, check=True,
                   encoding="utf-8")


def apply(report: dict, snapshot: dict, which: str, ledger: Path, only: set[str] | None = None) -> list[dict]:
    issues = {ir.key(r, i["number"]): i for r, d in snapshot["repos"].items() for i in d["issues"]}
    done = []
    plan = []
    if which in ("tick", "all"):
        for v in report["verify"]:
            lines = {r["line"] for r in v["items"] if r["class"] == "TICK_READY"}
            if lines:
                plan.append(("tick", v["issue"], lines))
    if which in ("checkbox", "all"):
        plan += [("checkbox", c["issue"], None) for c in report["checkbox"]]
    for kind, k, lines in plan:
        if only and k not in only:
            continue
        repo, n = k.rsplit("#", 1)
        before = live_body(repo, int(n))
        snap = issues[k].get("body") or ""
        if sha(before.replace("\r\n", "\n")) != sha(snap.replace("\r\n", "\n")):
            done.append({"issue": k, "kind": kind, "status": "SKIPPED_BODY_CHANGED"})
            continue
        after = tick_body(before, lines) if kind == "tick" else checkbox_body(before)[0]
        if after == before:
            continue
        patch_body(repo, int(n), after)
        row = append_edit(ledger, {"issue": k, "kind": kind, "before_sha256": sha(before),
                                   "after_sha256": sha(after), "lines": sorted(lines or [])})
        done.append({"issue": k, "kind": kind, "status": "APPLIED", "row_sha256": row["row_sha256"]})
    return done


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pulse", type=Path, default=ir.DEFAULT_OUT / "jade",
                    help="pulse directory with snapshot.json and issue_rank.json")
    ap.add_argument("--top", type=int, default=10, help="TRACK_DOD issues to propose checkboxes for")
    ap.add_argument("--apply", choices=("tick", "checkbox", "all"),
                    help="edit issue bodies (owner go-ahead required)")
    ap.add_argument("--only", nargs="*", help="limit --apply to these issue keys")
    ap.add_argument("--skip", nargs="*", default=[],
                    help="issue keys left out of the checkbox slice (bullets are options, not criteria)")
    args = ap.parse_args(argv)
    snap = json.loads((args.pulse / "snapshot.json").read_text(encoding="utf-8"))
    model = json.loads((args.pulse / "issue_rank.json").read_text(encoding="utf-8"))
    report = slices(snap, model, ir.Gh(), args.top, set(args.skip))
    out = args.pulse / "burndown_slices.json"
    out.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"{out} {report['summary']}")
    if args.apply:
        res = apply(report, snap, args.apply, args.pulse / "edits.jsonl", set(args.only) if args.only else None)
        for r in res:
            print(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
