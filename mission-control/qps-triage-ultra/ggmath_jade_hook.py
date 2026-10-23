#!/usr/bin/env python3
"""Disabled-by-default hook that hands gg_MATH bridge evidence to JADE rolling-5.

JADE's rolling-5 engine is not on master yet.  Until ``ggmath_jade_hook_v1.json``
is switched to ``enabled: true`` in a reviewed PR *and* the engine files exist,
this hook returns a DEFER status and writes nothing.  When enabled it emits a
read-only annotation document; it can never change JADE gates, NIRVANA,
streaks or release credit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOOK_PATH = HERE / "ggmath_jade_hook_v1.json"
REPO_ROOT = HERE.parents[1]
ANNOTATION_SCHEMA = "jade.temple.ggmath_annotation.v1"


class HookHold(Exception):
    def __init__(self, status: str, detail: str = ""):
        super().__init__(f"{status}: {detail}" if detail else status)
        self.status = status


def validate_hook(hook: dict) -> dict:
    if hook.get("schema") != "qps-ggmath-jade-hook/v1":
        raise HookHold("DEFER_JADE_HOOK_INVALID", "schema")
    if hook.get("authority_transfer") is not False:
        raise HookHold("DEFER_AUTHORITY_PROMOTION_REJECTED", "hook authority_transfer")
    contract = hook.get("contract", {})
    if contract.get("read_only") is not True:
        raise HookHold("DEFER_JADE_HOOK_INVALID", "hook must be read-only")
    for key in ("may_change_jade_gates", "may_change_nirvana_or_streaks", "release_credit",
                "pca_outputs_are_bt_evidence"):
        if contract.get(key) is not False:
            raise HookHold("DEFER_AUTHORITY_PROMOTION_REJECTED", key)
    if type(hook.get("enabled")) is not bool:
        raise HookHold("DEFER_JADE_HOOK_INVALID", "enabled must be boolean")
    return hook


def jade_annotation(receipt: dict, hook: dict, repo_root: Path = REPO_ROOT) -> dict:
    """Return the JADE annotation, or raise HookHold while the hook is not live."""
    validate_hook(hook)
    if not hook["enabled"]:
        raise HookHold(hook["activation"]["disabled_status"], "hook disabled by default")
    missing = [p for p in hook["activation"]["requires_on_master"] if not (Path(repo_root) / p).is_file()]
    if missing:
        raise HookHold(hook["activation"]["missing_target_status"], ", ".join(missing))
    flow = receipt["measured"]["flow_kpi_gm_i_a"]
    pressure = receipt["measured"]["bt_reverse_pressure_gm_i_a"]
    per_repo: dict[str, dict] = {}
    for job in flow.get("jobs", []):
        row = per_repo.setdefault(job["repo"], {"queue_seconds": 0.0, "execute_seconds": 0.0, "lanes": []})
        row["queue_seconds"] += job["queue_seconds"]
        row["execute_seconds"] += job["execute_seconds"]
        row["lanes"].append(job["lane"])
    for row in per_repo.values():
        total = row["queue_seconds"] + row["execute_seconds"]
        row["flow_efficiency"] = None if total == 0 else row["execute_seconds"] / total
        row["lanes"] = sorted(row["lanes"])
    receipt_bytes = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "schema": ANNOTATION_SCHEMA,
        "provider": receipt["provider"],
        "bridge_receipt_canonical_sha256": hashlib.sha256(receipt_bytes).hexdigest(),
        "flow_status": flow["status"],
        "per_repo_queue_pressure": dict(sorted(per_repo.items())),
        "reverse_pressure_status": pressure["status"],
        "threshold_kind": {f["from"].split(".")[-1]: f["threshold_kind"] for f in hook["feeds"]},
        "read_only": True,
        "changes_jade_gates": False,
        "release_credit": False,
        "authority_transfer": False,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--receipt", type=Path, default=HERE / "ggmath_bridge_receipt.json")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    hook = json.loads(HOOK_PATH.read_text(encoding="utf-8"))
    try:
        doc = jade_annotation(json.loads(args.receipt.read_text(encoding="utf-8")), hook)
    except HookHold as hold:
        print(json.dumps({"status": hold.status, "authority_transfer": False}, sort_keys=True))
        return 0 if hold.status == "DEFER_JADE_HOOK_DISABLED" else 2
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8", newline="\n")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
