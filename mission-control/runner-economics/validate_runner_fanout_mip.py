#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTROL = ROOT / "mission-control/runner-economics/RUNNER_FANOUT_MIP_CONTROL_v1.json"

EXCLUSION_FILES = [
    ".github/workflows/gm-iv-pilot2-final-recensus.yml",
    ".github/workflows/gm-iv-pilot2-governor.yml",
    ".github/workflows/gm-v-governor-readiness.yml",
    ".github/workflows/gm-fleet-02b.yml",
    ".github/workflows/gm-fleet-03-f01-pilot.yml",
    ".github/workflows/gm-fleet-03-ring1-recon.yml",
    ".github/workflows/gm-fleet-03-ring2-recon.yml",
    ".github/workflows/gm-fleet-03-capacity-gate.yml",
    ".github/workflows/gm-iv-active8-governor-readiness.yml",
    ".github/workflows/gm-fleet-03-f03-pilot.yml",
]

SPECIALIST_PATHS = {
    ".github/workflows/w3-14-measured-pca.yml": [
        "mission-control/qps-triage-ultra/analytics/**",
        "mission-control/qps-triage-ultra/crew/measured/frontier/temporal/**",
        ".github/workflows/w3-14-measured-pca.yml",
    ],
    ".github/workflows/w3-13-measured-telemetry.yml": [
        "mission-control/qps-triage-ultra/analytics/W3_13_MEASURED_PULSES.json",
        ".github/workflows/w3-13-measured-telemetry.yml",
    ],
    ".github/workflows/w3-11-non-origin-math-consumer.yml": [
        "mission-control/qps-triage-ultra/consumers/w3_11_math_consumer.py",
        ".github/workflows/w3-11-non-origin-math-consumer.yml",
    ],
    ".github/workflows/crew-telemetry-role-gap.yml": [
        "mission-control/qps-triage-ultra/crew/**",
        ".github/workflows/crew-telemetry-role-gap.yml",
    ],
}

PRESERVED_BROAD = {
    ".github/workflows/first-pass-closure-gate.yml": "pull_request_target:",
    ".github/workflows/qps-triage-ultra-w0.yml": "pull_request:",
    ".github/workflows/w3-16-m03-w0-recon.yml": "pull_request:",
}

def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")

def pull_request_block(content: str) -> str:
    marker = "  pull_request:\n"
    start = content.find(marker)
    if start < 0:
        return ""
    tail = content[start:]
    candidates = [
        pos for token in ("  workflow_dispatch:", "  push:", "permissions:")
        if (pos := tail.find(token, len(marker))) >= 0
    ]
    end = min(candidates) if candidates else len(tail)
    return tail[:end]

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-sha", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    c = json.loads(CONTROL.read_text(encoding="utf-8"))
    checks: dict[str, bool] = {}

    checks["01_baseline_bound"] = (
        c["baseline"]["pr"] == 326
        and c["baseline"]["head_sha"] == "31b3adf1ad17082fa4f383e2c2cedcf9aeb42706"
        and c["baseline"]["registered_workflow_count"] == 19
        and c["baseline"]["queue_exposure_ratio"] == 0.8811
    )

    for path in EXCLUSION_FILES:
        body = text(path)
        checks[f"exclude::{Path(path).name}"] = (
            "mission-control/grand-missions/**" in body
            and "!mission-control/grand-missions/analytics/**" in body
            and "mission-control/grand-missions/analytics/" not in body.replace(
                "!mission-control/grand-missions/analytics/**", ""
            )
        )

    for path, expected in SPECIALIST_PATHS.items():
        block = pull_request_block(text(path))
        checks[f"scope::{Path(path).name}"] = (
            "paths:" in block and all(p in block for p in expected)
        )

    fpc = text(".github/workflows/first-pass-closure-gate.yml")
    checks["preserve::first_pass_closure_global"] = (
        "pull_request_target:" in fpc
        and "types: [opened, synchronize, reopened, ready_for_review, edited]" in fpc
    )
    qps = pull_request_block(text(".github/workflows/qps-triage-ultra-w0.yml"))
    w316 = pull_request_block(text(".github/workflows/w3-16-m03-w0-recon.yml"))
    checks["preserve::qps_federation_broad"] = "paths:" not in qps
    checks["preserve::w3_16_broad"] = "paths:" not in w316

    modeled = c["modeled_after_pure_gmia_analytics_change"]
    checks["modeled_reduction_is_non_authoritative"] = (
        modeled["expected_registered_workflows"] == 5
        and modeled["modeled_reduction_count"] == 14
        and modeled["classification"] == "MODEL_PENDING_POSTMERGE_MEASURED_PROBE"
        and c["mip"]["Perpetuate"]["postmerge_probe_required"] is True
    )

    checks["non_compensation"] = (
        c["authority_transfer"] is False
        and c["formal_credit_delta"] == 0
        and c["engineering_credit_delta"] == 0
        and "DO_NOT_CLAIM_QPS_923_RECOVERY" in c["guards"]
    )

    passed = all(checks.values())
    receipt = {
        "schema": "missioncontrol.runner_fanout_mip_validation.v1",
        "source_sha": args.source_sha,
        "result": "PASS_RUNNER_FANOUT_MIP_CONTROL" if passed else "FAIL_RUNNER_FANOUT_MIP_CONTROL",
        "checks": checks,
        "check_count": len(checks),
        "baseline_registered_workflows": 19,
        "modeled_registered_workflows_after": 5,
        "modeled_reduction_count": 14,
        "modeled_reduction_ratio": modeled["modeled_reduction_ratio"],
        "postmerge_measured_probe_required": True,
        "qps_923_compensation": False,
        "authority_transfer": False,
        "formal_credit_delta": 0,
    }
    Path(args.out).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if passed else 1

if __name__ == "__main__":
    raise SystemExit(main())
