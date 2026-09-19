#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit("FAIL " + message)

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--readiness", required=True)
    ap.add_argument("--out")
    args = ap.parse_args()

    control = json.loads((HERE / "GM_I_A_MULTI_CLOCK_3PSTAR_MIP_v1.json").read_text(encoding="utf-8"))
    current = json.loads((HERE / "GM_I_A_MULTI_CLOCK_CURRENT_v1.json").read_text(encoding="utf-8"))
    readiness = json.loads(Path(args.readiness).read_text(encoding="utf-8"))

    checks = {}
    checks["method"] = control["method"] == "3PSTAR_THEN_MIP_SEQUENTIAL"
    checks["authority"] = control["authority_transfer"] is False and control["formal_credit_delta"] == 0
    checks["three_pstar"] = all(
        control["three_pstar"][phase]["result"].startswith("PASS")
        for phase in ("Refresh", "Probe", "Rank")
    )
    checks["mip"] = (
        control["mip"]["Modernize"]["result"] == "PASS"
        and control["mip"]["Innovate"]["result"] == "PASS_BOUNDED"
        and control["mip"]["Perpetuate"]["result"] == "PASS_REPOSITORY_NATIVE"
    )
    checks["readiness_schema"] = readiness["schema"] == "missioncontrol.gm_i_a.multiclock_readiness.v2"
    checks["geometry"] = readiness["measured_pulses"] == 1 and readiness["feature_count_p"] == 9
    checks["pca_gate"] = (
        readiness["pca"]["status"] == "DEFER_INSUFFICIENT_COMPARABLE_MEASURED_PULSES"
        and readiness["pca"]["minimum_rows_required"] == 27
        and readiness["pca"]["rows_remaining_to_minimum"] == 26
        and readiness["pca"]["covariance_rank_upper_bound"] == 0
    )
    checks["bt_gate"] = (
        readiness["bt_reverse_pressure"]["status"] == "DEFER_NO_FINITE_MLE_REPEAT_STRUCTURE"
        and readiness["bt_reverse_pressure"]["minimum_repeat_pulses"] == 3
        and readiness["bt_reverse_pressure"]["repeat_pulses_remaining"] == 2
        and readiness["bt_reverse_pressure"]["directed_win_graph_strongly_connected"] is False
        and readiness["bt_reverse_pressure"]["bidirectional_pair_count"] == 0
    )
    pressure = readiness["latest_pulse_descriptive_pressure"]
    checks["queue_separation"] = 0.88 < pressure["queue_fraction"] < 0.89
    checks["concentration"] = (
        0.27 < pressure["pressure_hhi"] < 0.28
        and 3.6 < pressure["effective_clock_count"] < 3.7
        and pressure["top4_fraction"] > 0.97
    )
    checks["current_pointer"] = (
        current["pca"]["status"] == "WITHHELD_N1_OF_27"
        and current["bt"]["status"] == "WITHHELD_N1_NO_STRONG_CONNECTIVITY"
        and current["next_pulse"] == "GM-I-A-MCLOCK-P002"
    )
    checks["no_promotion"] = (
        readiness["authority_transfer"] is False
        and readiness["formal_credit_delta"] == 0
        and control["engineering_credit_delta"] == 0
    )

    failed = [name for name, ok in checks.items() if not ok]
    receipt = {
        "schema": "missioncontrol.gm_i_a.multiclock_3pstar_mip_receipt.v1",
        "status": "PASS_3PSTAR_MIP_REPOSITORY_CONTROL" if not failed else "FAIL_3PSTAR_MIP_REPOSITORY_CONTROL",
        "checks": checks,
        "failed": failed,
        "next": control["next"],
        "authority_transfer": False,
        "formal_credit_delta": 0
    }
    text = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if not failed else 1

if __name__ == "__main__":
    raise SystemExit(main())
