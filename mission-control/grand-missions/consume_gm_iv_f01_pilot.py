#!/usr/bin/env python3
"""Consume the F01 independent verifier summary into a bounded MissionControl receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONTRACT = HERE / "GM_IV_F01_PILOT_CONTRACT.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(value: dict) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    contract = load(CONTRACT)
    summary = load(args.summary)
    expected_sha = contract["source_sha"]

    assert summary["verification"] == contract["required"]["verifier_result"]
    assert summary["head_sha"] == expected_sha
    assert summary["root_self_index"]["runs"] == contract["required"]["root_runs"]
    assert summary["root_self_index"]["normalized_equal"] is True
    assert int(summary["root_self_index"]["file_count"]) > 0

    nested = summary.get("nested_surface")
    if nested is not None:
        assert nested["runs"] == 2
        assert nested["normalized_equal"] is True
        assert int(nested["file_count"]) > 0

    receipt = {
        "schema": "qps.gm_iv_f01_pilot_receipt.v1",
        "wave": contract["wave"],
        "mission": contract["mission"],
        "slot": contract["slot"],
        "repository": contract["repository"],
        "source_sha": expected_sha,
        "missioncontrol_sha": os.environ.get("MISSIONCONTROL_SHA", "UNBOUND"),
        "executed_steps_gt0": True,
        "producer_verifier_chain": "PASS",
        "verifier_summary_digest_sha256": digest(summary),
        "root_self_index_digest_sha256": summary["root_self_index"]["digest_sha256"],
        "root_file_count": summary["root_self_index"]["file_count"],
        "root_assessments": summary["root_self_index"].get("assessments", {}),
        "nested_surface_present": nested is not None,
        "nested_digest_sha256": nested.get("digest_sha256") if nested else None,
        "authority_transfer": False,
        "children_bound": False,
        "disposition": contract["success_disposition"],
        "next_gate": contract["post_success_gate"],
    }

    assert receipt["missioncontrol_sha"] != "UNBOUND"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
