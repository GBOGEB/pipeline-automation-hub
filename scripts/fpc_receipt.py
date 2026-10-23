#!/usr/bin/env python3
"""Build (and optionally write) the FPC_RECEIPT_V1 PR-body receipt for a PR.

The First-Pass Closure Gate (scripts/first_pass_closure_gate.py) fails closed on
every PR whose body lacks an ``<!-- FPC_RECEIPT_V1 {...} -->`` block binding
successful exact-head proof runs. This helper removes the manual step:

    python scripts/fpc_receipt.py --pr 123            # dry run: print receipt
    python scripts/fpc_receipt.py --pr 123 --write    # replace/insert in PR body

It reads the live PR head/base SHA via the ``gh`` CLI, lists completed/success
workflow runs on that exact head, and keeps only runs whose identity the gate
itself would trust. Identity + content checks are delegated to the gate's own
``allowed_purposes`` (imported, not copied), so this helper can never claim a
proof the trusted controller would reject.

The receipt it produces is evidence binding only. The gate still independently
re-validates every run, the Codex exact-head review and protected paths.

Exit codes: 0 receipt covers every required purpose; 1 coverage incomplete
(missing purposes are listed on stderr, nothing is written); 2 usage/API error.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import first_pass_closure_gate as gate  # noqa: E402

REPO_ROOT = SCRIPTS_DIR.parent
DEFAULT_POLICY = REPO_ROOT / "mission-control" / "quality" / "FIRST_PASS_CLOSURE_POLICY_v1.json"
RECEIPT_SCHEMA = "first_pass_closure/v1"
SECTION_HEADING = "## First-Pass Closure receipt"

Runner = Callable[[list[str], str | None], str]


def _run_gh(args: list[str], stdin: str | None = None) -> str:
    proc = subprocess.run(
        ["gh", *args],
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if proc.returncode != 0:
        raise gate.GateError(
            f"GH_CLI_FAILED: gh {' '.join(args[:3])}: {proc.stderr.strip()[:500]}"
        )
    return proc.stdout


class GhClient:
    """Duck-typed stand-in for gate.ApiClient backed by the ``gh`` CLI.

    Uses the caller's existing ``gh auth`` login, so no token handling here.
    """

    def __init__(self, runner: Runner = _run_gh):
        self.runner = runner

    def get(self, path: str) -> Any:
        out = self.runner(["api", path.lstrip("/")], None)
        return json.loads(out) if out.strip() else None

    def get_all(self, path: str) -> list[Any]:
        rows: list[Any] = []
        page = 1
        while True:
            sep = "&" if "?" in path else "?"
            chunk = self.get(f"{path}{sep}per_page=100&page={page}")
            if not isinstance(chunk, list):
                raise gate.GateError(f"EXPECTED_LIST: {path}")
            rows.extend(chunk)
            if len(chunk) < 100:
                return rows
            page += 1

    def patch_pr_body(self, repo: str, pr_number: int, body: str) -> None:
        self.runner(
            ["api", "--method", "PATCH", f"repos/{repo}/pulls/{pr_number}", "--input", "-"],
            json.dumps({"body": body}),
        )


def detect_repo(runner: Runner = _run_gh) -> str:
    out = runner(["repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"], None)
    repo = out.strip()
    if repo.count("/") != 1:
        raise gate.GateError("REPO_UNRESOLVED: pass --repo OWNER/NAME")
    return repo


def list_success_runs(client: Any, repo: str, head_sha: str) -> list[dict[str, Any]]:
    """All completed/success workflow runs bound to exactly ``head_sha``."""
    runs: list[dict[str, Any]] = []
    page = 1
    while True:
        payload = client.get(
            f"/repos/{repo}/actions/runs?head_sha={head_sha}&status=success"
            f"&per_page=100&page={page}"
        )
        chunk = (payload or {}).get("workflow_runs") or []
        runs.extend(chunk)
        if len(chunk) < 100:
            break
        page += 1
    return [
        r
        for r in runs
        if r.get("head_sha") == head_sha
        and r.get("status") == "completed"
        and r.get("conclusion") == "success"
        and type(r.get("id")) is int
    ]


def select_runs(
    client: Any,
    policy: dict[str, Any],
    repo: str,
    base_sha: str,
    runs: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], set[str], list[str]]:
    """Pick the newest trusted run per still-uncovered purpose.

    Returns (selected run specs, covered purposes, notes on rejected runs).
    Trust is decided by gate.allowed_purposes (allowlist identity plus
    candidate/base workflow-content equality), exactly as the gate does.
    """
    selected: list[dict[str, Any]] = []
    covered: set[str] = set()
    notes: list[str] = []
    for run in sorted(runs, key=lambda r: r["id"], reverse=True):
        if covered >= gate.REQUIRED_PURPOSES:
            break
        bound = {**run, "repository": {"full_name": repo}}
        try:
            purposes, _trust = gate.allowed_purposes(client, policy, repo, base_sha, bound)
        except gate.GateError as exc:
            reason = str(exc)
            if not reason.startswith("UNTRUSTED_PROOF_WORKFLOW_IDENTITY"):
                notes.append(f"run {run['id']} ({run.get('name')}): {reason}")
            continue
        if purposes - covered:
            selected.append({"repo": repo, "run_id": run["id"]})
            covered |= purposes
    return selected, covered, notes


def build_receipt(head_sha: str, required_runs: list[dict[str, Any]]) -> dict[str, Any]:
    return {"schema": RECEIPT_SCHEMA, "head_sha": head_sha, "required_runs": required_runs}


def missing_purposes(covered: set[str]) -> list[str]:
    return sorted(gate.REQUIRED_PURPOSES - set(covered))


def render_marker(receipt: dict[str, Any]) -> str:
    return "<!-- FPC_RECEIPT_V1\n" + json.dumps(receipt, indent=2) + "\n-->"


def upsert_marker(body: str | None, receipt: dict[str, Any]) -> str:
    """Replace the first FPC_RECEIPT_V1 block (incl. template skeleton) or append one."""
    block = render_marker(receipt)
    text = body or ""
    match = gate.MARKER_RE.search(text)
    if match:
        return text[: match.start()] + block + text[match.end():]
    suffix = f"{SECTION_HEADING}\n\n{block}\n"
    if not text.strip():
        return suffix
    return text.rstrip("\n") + "\n\n" + suffix


def generate(
    client: Any, repo: str, pr_number: int, policy: dict[str, Any]
) -> tuple[dict[str, Any], list[str], list[str], dict[str, Any]]:
    pr = client.get(f"/repos/{repo}/pulls/{pr_number}")
    head_sha = ((pr or {}).get("head") or {}).get("sha")
    base_sha = ((pr or {}).get("base") or {}).get("sha")
    if not isinstance(head_sha, str) or len(head_sha) != 40:
        raise gate.GateError("PR_HEAD_UNAVAILABLE")
    if not isinstance(base_sha, str) or len(base_sha) != 40:
        raise gate.GateError("PR_BASE_UNAVAILABLE")

    notes: list[str] = []
    protected = gate.protected_control_changes(client, repo, pr_number, policy)
    if protected:
        notes.append(
            "PR changes protected FPC controller paths; the gate will return "
            "CONTROL_PLANE_CHANGE_REQUIRES_BOOTSTRAP regardless of receipt: "
            + ",".join(protected)
        )

    runs = list_success_runs(client, repo, head_sha)
    selected, covered, run_notes = select_runs(client, policy, repo, base_sha, runs)
    notes.extend(run_notes)
    receipt = build_receipt(head_sha, selected)
    return receipt, missing_purposes(covered), notes, pr


def main(argv: list[str] | None = None, client: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--pr", type=int, required=True, help="pull request number")
    parser.add_argument("--repo", help="OWNER/NAME (default: gh repo view)")
    parser.add_argument("--policy", default=str(DEFAULT_POLICY))
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", default=True,
                      help="print the receipt block only (default)")
    mode.add_argument("--write", action="store_true",
                      help="replace/insert the receipt block in the PR body")
    args = parser.parse_args(argv)

    try:
        client = client or GhClient()
        repo = args.repo or detect_repo(client.runner)
        policy = gate.load_policy(args.policy)
        receipt, missing, notes, pr = generate(client, repo, args.pr, policy)
    except gate.GateError as exc:
        print(f"FPC_RECEIPT=ERROR:{exc}", file=sys.stderr)
        return 2

    for note in notes:
        print(f"note: {note}", file=sys.stderr)
    if missing:
        print(
            f"FPC_RECEIPT=INCOMPLETE head={receipt['head_sha'][:12]} "
            f"missing_purposes={','.join(missing)}",
            file=sys.stderr,
        )
        print(
            "Wait for (or re-run) the allowlisted 'First-Pass Closure Proof' workflow "
            "on this exact head, then retry.",
            file=sys.stderr,
        )
        print(render_marker(receipt))
        return 1

    # Self-check against the gate's own parser before showing or writing it.
    gate.parse_receipt(render_marker(receipt))

    if args.write:
        new_body = upsert_marker(pr.get("body"), receipt)
        if new_body == (pr.get("body") or ""):
            print(f"FPC_RECEIPT=UNCHANGED pr={args.pr}", file=sys.stderr)
        else:
            try:
                client.patch_pr_body(repo, args.pr, new_body)
            except gate.GateError as exc:
                print(f"FPC_RECEIPT=ERROR:{exc}", file=sys.stderr)
                return 2
            print(f"FPC_RECEIPT=WRITTEN pr={args.pr}", file=sys.stderr)
    print(render_marker(receipt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
