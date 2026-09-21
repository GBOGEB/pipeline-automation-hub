#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
INPUT = ROOT / "mission-control/qps-triage-ultra/missions/LM-10_W260_BD260_5_PROVIDER_RECEIPT_PROJECTION_v1.json"
OUT = ROOT / "mission-control/qps-triage-ultra/missions/LM-10_W260_BD260_5_TRIAGE_RECEIPT_v1.json"

EXPECTED_SOURCE = "2b27f4a6d70a11324d9a7c81d9c88995888b3d74"
EXPECTED_ARTIFACT_DIGEST = "sha256:603da43f85e9709f0372b3f487e5c15c78e628adc4f6ae19232b8108af233a15"
EXPECTED_FIXTURE = "9bdb111b1365583ba4d615176d93c7a0650dc85bcd958db8567cba48214586f5"
EXPECTED_CONTRACT = "95b8a1c7b886026d491bbf880f3a6d9ab17c4b4cdac36687593a97f130f8fd63"
ALLOWED_THRESHOLD_CLASSES = {"STATISTICAL", "PROJECT_GOVERNED", "GOVERNANCE_IDENTITY", "NONE"}

EXPECTED_CARDS = [
    {
        "index": 1,
        "keys_exact": True,
        "threshold_kind": "NO_UNIVERSAL_THRESHOLD",
        "threshold_class": "NONE",
        "disposition": "PASS_REFERENCE_PROJECT_MATH",
        "first_red": None,
    },
    {
        "index": 2,
        "keys_exact": True,
        "threshold_kind": "DISTRIBUTION_DERIVED_AND_DATA_CALIBRATED",
        "threshold_class": "STATISTICAL",
        "disposition": "PASS_REFERENCE_PROJECT_MATH",
        "first_red": None,
    },
    {
        "index": 3,
        "keys_exact": True,
        "threshold_kind": "NO_UNIVERSAL_THRESHOLD",
        "threshold_class": "NONE",
        "disposition": "PASS_ANOVA_DECOMPOSITION_MANOVA_DEFER",
        "first_red": "MANOVA_RUNTIME_NOT_PROMOTED_IN_THIS_SLICE",
    },
    {
        "index": 4,
        "keys_exact": True,
        "threshold_kind": "DATA_CALIBRATED",
        "threshold_class": "STATISTICAL",
        "disposition": "PASS_REGULARIZED_BT_PROJECT_MATH",
        "first_red": "DEFER_NO_FINITE_MLE",
    },
    {
        "index": 5,
        "keys_exact": True,
        "threshold_kind": "EXACT_IDENTITY",
        "threshold_class": "GOVERNANCE_IDENTITY",
        "disposition": "PASS_DOES_NOT_IMPLY_GUARD",
        "first_red": None,
    },
]


def validate_projection(d: dict) -> tuple[dict[str, int], list[str]]:
    p = d["provider"]
    r = d["receipt"]
    assert p["source_sha"] == EXPECTED_SOURCE
    assert r["source_sha"] == EXPECTED_SOURCE
    assert p["workflow_run"] == 35592153194
    assert p["job"] == 106308723087
    assert p["artifact_id"] == 10634743904
    assert p["artifact_digest"] == EXPECTED_ARTIFACT_DIGEST
    assert r["fixture_sha256"] == EXPECTED_FIXTURE
    assert r["contract_sha256"] == EXPECTED_CONTRACT
    assert r["status"] == "PASS_COMMON_FIXTURE_CHALLENGE"
    assert r["authority_transfer"] is False
    assert r["formal_credit_delta"] == 0
    assert r["engineering_acceptance"] is False
    assert r["qps_threshold_authority"] is False
    assert d["authority_transfer"] is False
    assert d["formal_credit_delta"] == 0

    required = set(r["required_card_keys"])
    assert required == {
        "math",
        "assumptions",
        "value",
        "threshold_kind",
        "measured_result",
        "uncertainty",
        "first_red",
        "validity_domain",
        "dmaic_kpi",
        "disposition",
    }

    cards = r["cards"]
    assert r["card_count"] == len(EXPECTED_CARDS)
    assert len(cards) == r["card_count"]

    class_counts = Counter()
    first_reds: list[str] = []
    for actual, expected in zip(cards, EXPECTED_CARDS):
        assert actual == expected, (actual, expected)
        assert actual["threshold_class"] in ALLOWED_THRESHOLD_CLASSES
        class_counts[actual["threshold_class"]] += 1
        if actual["first_red"] is not None:
            first_reds.append(actual["first_red"])

    counts = {name: class_counts.get(name, 0) for name in sorted(ALLOWED_THRESHOLD_CLASSES)}
    assert counts == {
        "GOVERNANCE_IDENTITY": 1,
        "NONE": 2,
        "PROJECT_GOVERNED": 0,
        "STATISTICAL": 2,
    }
    assert first_reds == [
        "MANOVA_RUNTIME_NOT_PROMOTED_IN_THIS_SLICE",
        "DEFER_NO_FINITE_MLE",
    ]

    assert r["explicit_defer"]["confidence_sequence"] == "RESEARCH_TODO"
    assert r["explicit_defer"]["hierarchical_bayesian_bt"] == "RESEARCH_TODO"
    assert r["explicit_defer"]["grassmann_state_space"] == "RESEARCH_TODO"
    assert r["explicit_defer"]["manova"] == "NOT_PROMOTED_IN_THIS_SLICE"
    return counts, first_reds


def build_receipt(d: dict) -> dict:
    counts, first_reds = validate_projection(d)
    return {
        "schema": "qps.lm10.w260.bd2605.triage_receipt.v1",
        "mission_id": "LM-10",
        "wave": "W260",
        "bd_id": "BD-260.5",
        "source_sha": os.environ.get("SOURCE_SHA", "LOCAL_UNBOUND"),
        "provider_source_sha": EXPECTED_SOURCE,
        "provider_run": 35592153194,
        "provider_job": 106308723087,
        "provider_artifact_id": 10634743904,
        "provider_artifact_digest": EXPECTED_ARTIFACT_DIGEST,
        "fixture_sha256": EXPECTED_FIXTURE,
        "contract_sha256": EXPECTED_CONTRACT,
        "card_count": len(EXPECTED_CARDS),
        "threshold_class_counts": counts,
        "retained_first_reds": first_reds,
        "disposition": "ACCEPT_BOUNDED_PROJECT_MATH_WITH_EXPLICIT_DEFER",
        "next": "BD-260.6_OPTIONAL_FEDERATION_DISPOSITION",
        "authority_transfer": False,
        "formal_credit_delta": 0,
        "engineering_acceptance": False,
        "qps_threshold_authority": False,
        "status": "PASS_TRIAGE_VERIFICATION",
    }


def main() -> None:
    d = json.loads(INPUT.read_text())
    out = build_receipt(d)
    OUT.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print("PASS_LM10_W260_BD260_5_TRIAGE")


if __name__ == "__main__":
    main()
