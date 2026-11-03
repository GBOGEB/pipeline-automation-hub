"""Read-only, source-bound H3 guard; no enforced recheck source may retire silently.

Derive authority only from an independently pinned base checkout, not from a
candidate's editable policy. Parse *actual* GitHub workflow_run subscriptions,
not merely a movable generated marker. Invalid evidence remains HOLD.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OWNER = Path(__file__).with_name("gate.py")
SCHEMA = "gogreen.h3.trigger-retirement-preflight.v2"


def _owner():
    spec = importlib.util.spec_from_file_location("gogreen_h3_owner", OWNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def source_head(root: Path) -> str:
    """Native git readback; never trust a caller-supplied SHA without checkout proof."""
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"], check=True,
        capture_output=True, text=True, timeout=10)
    return result.stdout.strip()


def require_clean_checkout(root: Path) -> None:
    """Fail closed if the pinned base worktree contains staged, unstaged or untracked edits.

    HEAD identity alone cannot authenticate policy and workflow bytes on disk.
    The clean checkout check binds files subsequently read to the pinned commit.
    """
    result = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain=v1",
         "--untracked-files=all"],
        check=True, capture_output=True, text=True, timeout=10,
    )
    if result.stdout.strip():
        raise ValueError("pinned base checkout is dirty; refused authority read")


def strict_enforced_names(root: Path, gate) -> tuple[list[str], set[str]]:
    """Reject missing, malformed, duplicated or non-PR ENFORCED source paths."""
    policy = gate.load_policy(None, None, root, "head")
    entries = policy["entries"]
    names = []
    paths = set()
    seen = set()
    for path, disposition in entries.items():
        if disposition != gate.ENFORCED:
            continue
        # Exact directory membership; no absolute or traversing paths.
        if (not isinstance(path, str)
                or re.fullmatch(r"\.github/workflows/[A-Za-z0-9_.-]+\.ya?ml", path) is None):
            raise ValueError("invalid enforced workflow source path")
        candidate = root / path
        if not candidate.is_file():
            raise ValueError(f"missing enforced workflow source: {path}")
        t = gate.triggers(candidate)
        if t.get("parse_error") or not t.get("pull_request"):
            raise ValueError(f"unparseable or non-PR enforced workflow: {path}")
        name = t.get("name")
        if not isinstance(name, str) or not name.strip() or name in seen:
            raise ValueError(f"missing/duplicated enforced workflow name: {path}")
        names.append(name)
        seen.add(name)
        paths.add(path)
    if not names:
        raise ValueError("empty enforced source population")
    return sorted(names), paths


def active_trigger_scope(root: Path, gate) -> dict:
    """Return actual names AND branch/type filters, rejecting invalid YAML as HOLD.

    The entire workflow_run subscription must match the independently pinned
    base. A branch-ignore change can otherwise suppress all RED recovery while
    keeping the generated workflow names unchanged.
    """
    import yaml

    source = root / gate.RECHECK
    raw = source.read_text(encoding="utf-8")
    markers = gate.declared_recheck_names(raw)
    try:
        doc = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ValueError("invalid recheck workflow YAML") from exc
    if not isinstance(doc, dict):
        raise ValueError("recheck workflow YAML is not an object")
    events = doc.get("on", doc.get(True))
    block = events.get("workflow_run") if isinstance(events, dict) else None
    if not isinstance(block, dict):
        raise ValueError("recheck workflow_run trigger missing")
    actual, types = block.get("workflows"), block.get("types")
    if (not isinstance(actual, list) or not actual
            or any(not isinstance(s, str) or not s for s in actual)
            or len(actual) != len(set(actual))
            or not isinstance(types, list) or "completed" not in types):
        raise ValueError("actual workflow_run subscription malformed")
    for name in ("branches", "branches-ignore"):
        if name in block:
            values = block[name]
            if (not isinstance(values, list) or not values
                    or any(not isinstance(s, str) or not s for s in values)
                    or len(values) != len(set(values))):
                raise ValueError(f"invalid recheck {name} filter")
    if "branches" in block and "branches-ignore" in block:
        raise ValueError("ambiguous workflow_run branches and branches-ignore")
    if actual != markers:
        raise ValueError("recheck marker differs from real workflow_run subscriptions")
    return block


def active_trigger_names(root: Path, gate) -> list[str]:
    return active_trigger_scope(root, gate)["workflows"]


def assess(required: list[str], live: list[str], proposed: list[str]) -> dict:
    """Baseline comparison never grants a source retirement or merge authority."""
    values = (required, live, proposed)
    valid = all(isinstance(xs, list) and all(isinstance(x, str) and x for x in xs)
                and len(xs) == len(set(xs)) for xs in values)
    if not valid:
        return {"schema": SCHEMA, "state": "HOLD",
                "reason": "invalid/duplicate listener identities",
                "merge_authorized": False, "production_event_reduction": False}
    required_set, live_set, proposed_set = map(set, values)
    missing_live = sorted(required_set - live_set)
    unknown_live = sorted(live_set - required_set)
    proposed_missing = sorted(required_set - proposed_set)
    proposed_extra = sorted(proposed_set - required_set)
    changed = sorted(live_set ^ proposed_set)
    state = ("BASELINE_PRESERVED" if (not missing_live and not unknown_live
              and not changed) else "HOLD")
    return {"schema": SCHEMA, "state": state,
            "required_count": len(required), "live_listener_count": len(live),
            "candidate_listener_count": len(proposed),
            "missing_live_enforced": missing_live, "unlisted_live": unknown_live,
            "candidate_missing_enforced": proposed_missing, "candidate_extra": proposed_extra,
            "changed_listener_names": changed, "verified_successor_count": 0,
            "approval_note": "No verified replacement or independent acceptance",
            "production_event_reduction": False, "merge_authorized": False}


def preflight(root: Path, base_root: Path, base_sha: str,
              proposed: list[str] | None = None) -> dict:
    """Cannot use candidate-controlled policy or missing pinned baseline."""
    if not re.fullmatch(r"[0-9a-f]{40}", base_sha):
        raise ValueError("invalid pinned base SHA")
    if source_head(base_root) != base_sha:
        raise ValueError("base checkout does not match expected GitHub base SHA")
    require_clean_checkout(base_root)
    gate = _owner()
    required, paths = strict_enforced_names(base_root, gate)
    candidate_names, candidate_paths = strict_enforced_names(root, gate)
    # A demotion is also a reduction, even if the generated listener survives.
    if not paths <= candidate_paths or not set(required) <= set(candidate_names):
        raise ValueError("candidate has demoted or removed enforced source")
    base_scope = active_trigger_scope(base_root, gate)
    if base_scope["workflows"] != required:
        raise ValueError("base owner listener/authority disagreement")
    live_scope = active_trigger_scope(root, gate)
    if live_scope != base_scope:
        raise ValueError("candidate workflow_run scope differs from pinned base")
    live = live_scope["workflows"]
    result = assess(required, live, live if proposed is None else proposed)
    result["base_sha"] = base_sha
    result["source_checkout_clean"] = True
    result["bound_workflow_run_filter"] = {
        "branches": base_scope.get("branches"),
        "branches-ignore": base_scope.get("branches-ignore"),
        "types": base_scope.get("types"),
        "workflow_count": len(base_scope["workflows"]),
    }
    result["authority_source"] = "independently_pinned_base_checkout"
    result["candidate_head"] = source_head(root)
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--base-root", type=Path, required=True)
    ap.add_argument("--base-sha", required=True)
    ap.add_argument("--proposed", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    try:
        proposed = json.loads(args.proposed.read_text(encoding="utf-8")) if args.proposed else None
        result = preflight(args.root, args.base_root, args.base_sha, proposed)
    except (OSError, ValueError, KeyError, TypeError, ImportError,
            subprocess.SubprocessError) as exc:
        result = {"schema": SCHEMA, "state": "HOLD", "reason": str(exc)[:320],
                  "merge_authorized": False, "production_event_reduction": False}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n",
                        encoding="utf-8", newline="\n")
    print(json.dumps(result, sort_keys=True))
    return 0 if result["state"] == "BASELINE_PRESERVED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
