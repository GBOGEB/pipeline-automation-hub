#!/usr/bin/env python3
"""Report historical reply candidates; apply only source-bound closure proofs.

    python resolve_answered.py --repos GBOGEB/cryoplant-project,GBOGEB/CODEX [--limit 60]
    python resolve_answered.py --proofs <private proof batch.json> --ledger <private ledger.json> --apply

Dry run by default. A historical reply is only a candidate when its last comment
is from the login running this tool and that reply:

* says the fix is already on main (``Already fixed on main``, ``Superseded on main``, ``Kept as is``, ...), or
* names a fix PR in the same repository that has merged (``Fixed in #N``, ``Fixed by merged #N``,
  ``the fix is in #N``), or
* names a commit on the thread's own PR, which has merged (``Fixed in <sha>``, ``Addressed on head <sha>``).

No text pattern authorizes resolution. --apply requires the proof envelope,
current source/heads/discussion, a live lease, and a positive provider readback.
The closure adapter uses official REST and GraphQL APIs. Historical candidates
remain open until revalidated against a supported active target.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import fcntl
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
_SPEC = importlib.util.spec_from_file_location("maroon_review_threads", HERE / "review_threads.py")
RT = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(RT)

ON_MAIN = re.compile(r"^(?:Already fixed on main|Already addressed on main|Superseded on main|Kept as is|"
                     r"Already fixed)", re.I)
FIX_PR = re.compile(r"(?:fixed|corrected) in #(\d+)|the fix is in #(\d+)|fixed by merged #(\d+)", re.I)
FIX_SHA = re.compile(r"^(?:Fixed in|Addressed on head) ([0-9a-f]{7,40})\b")
# Evidence replies may open with an HTML marker and a bold title before the verdict.
PREAMBLE = re.compile(r"^(?:\s*<!--.*?-->\s*)*(?:\*\*[^*]*\*\*\s*)?", re.S)
WAIT, SKIP = "WAIT", "SKIP"


def verdict_of(body: str, pr_merged) -> str:
    """Prose discovers candidates; it never proves the finding is fixed."""
    text = PREAMBLE.sub("", body or "").strip()
    if ON_MAIN.match(text):
        return f"{WAIT} current source proof required (on-main claim)"
    match = FIX_PR.search(text)
    if match:
        number = int(next(g for g in match.groups() if g))
        return (f"{WAIT} current source proof required (merged #{number})" if pr_merged(number)
                else f"{WAIT} #{number} unmerged")
    if FIX_SHA.match(text):
        return f"{WAIT} full commit ancestry and finding-specific proof required"
    return f"{SKIP} unrecognised reply"


def answered(gh, repo: str, limit: int, me: str):
    """(pr, root comment id, verdict) for every unresolved thread on a recent merged PR whose last word is ours."""
    cache: dict[int, bool] = {}

    def pr_merged(number: int) -> bool:
        if number not in cache:
            cache[number] = bool(RT.gh_json(gh, f"repos/{repo}/pulls/{number}").get("merged_at"))
        return cache[number]

    prs, _proven = RT.recent_closed(gh, repo, limit)
    for pr in prs:
        if not pr.get("merged_at"):
            continue
        try:
            threads = RT.gh_json(gh, f"repos/{repo}/pulls/{pr['number']}/ccr/review_threads") or []
        except RuntimeError as exc:  # one unreadable PR is a reported gap, not the end of the sweep
            yield pr["number"], None, f"{SKIP} GAP threads unreadable: {str(exc)[:80]}"
            continue
        for thread in threads:
            ids = thread.get("comment_ids") or []
            if thread.get("resolved") or len(ids) < 2:
                continue
            last = RT.gh_json(gh, f"repos/{repo}/pulls/comments/{ids[-1]}")
            if (last.get("user") or {}).get("login") != me:
                continue
            yield pr["number"], ids[0], verdict_of(last.get("body", ""), pr_merged)


def apply_proofs(proof_path, ledger_path, gh):
    """One private ledger carries queue, claims and closure journals together."""
    def module(name, filename):
        spec = importlib.util.spec_from_file_location(name, HERE / filename)
        value = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(value)
        return value
    operations = module("maroon_apply_operations", "operations.py")
    closure = module("maroon_apply_closure", "closure.py")
    entries = json.loads(proof_path.read_text(encoding="utf-8"))
    if not isinstance(entries, list) or not entries:
        raise ValueError("proof batch must be a nonempty list of {proof, claim}")
    store = operations.LedgerStore(ledger_path)
    provider = closure.GitHub(gh)
    count = 0
    # Serializes this host's appliers. Shared deployments must also CAS every
    # ledger checkpoint and recheck their shared fencing lease before side effects.
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.with_suffix(ledger_path.suffix + ".closure-lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        for entry in entries:
            proof, claim = entry["proof"], entry["claim"]
            key = closure.digest(proof)
            journal = store.read().get("closure_journals", {}).get(key, {})

            def check_lease():
                packet = operations.check_lease(store, claim["root_id"], claim["lease_token"], claim["fence"])
                return closure.validate_claim(proof, packet)

            def checkpoint(value):
                with store.transaction() as data:
                    data.setdefault("closure_journals", {})[key] = value

            def close_item(receipt):
                packet = check_lease()
                receipt.update(root_id=claim["root_id"], lease_token=claim["lease_token"], fence=claim["fence"])
                receipt["core_oids"] = packet["core_oids"]
                return operations.mark_closed(store, proof["item_id"], receipt)

            closure.apply_close(proof, provider, journal, checkpoint, close_item, check_lease)
            count += 1
    return count


def main(argv=None, gh=RT.run_gh) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repos", help="comma-separated owner/name list for historical candidate report")
    parser.add_argument("--limit", type=int, default=60, help="most recently closed PRs read per repository")
    parser.add_argument("--apply", action="store_true", help="apply source-bound proofs with a live queue lease")
    parser.add_argument("--proofs", type=Path, help="private JSON list of {proof, claim}")
    parser.add_argument("--ledger", type=Path, help="private durable operations ledger")
    args = parser.parse_args(argv)
    if args.apply:
        if not args.proofs or not args.ledger:
            parser.error("--apply requires --proofs and --ledger; reply wording cannot authorize closure")
        count = apply_proofs(args.proofs, args.ledger, gh)
        print(f"resolved and ledger-closed {count} proven manifestations", file=sys.stderr)
        return 0
    if args.proofs or args.ledger:
        parser.error("proof application requires --apply")
    if not args.repos:
        parser.error("--repos is required for a candidate report")
    me = RT.gh_json(gh, "user")["login"]
    resolved = considered = 0
    for repo in [r.strip() for r in args.repos.split(",") if r.strip()]:
        for number, root, verdict in answered(gh, repo, args.limit, me):
            considered += 1
            act = root is not None and not verdict.startswith((WAIT, SKIP))
            resolved += act
            print(f"{repo}\t#{number}\t{root}\t{verdict}")
    print(f"{'resolved' if args.apply else 'would resolve'} {resolved} of {considered} answered threads",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
