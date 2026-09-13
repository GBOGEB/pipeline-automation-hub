#!/usr/bin/env python3
"""Compatibility/control wrapper for the GM-IV PILOT_2_OF_8 recensus.

v1 remains the immutable four-frontier evidence executor. v2 supplies the
single observed schema alias from the first v1 run and adds the later-arriving
Crew Exposure PCA Control validator as a terminal moving-base gate.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import run_gm_iv_pilot2_recensus as v1

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PY = sys.executable


def main() -> int:
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--out-dir", required=True)
    known, _ = ap.parse_known_args()
    out_dir = Path(known.out_dir).resolve()

    original_read_json = v1.read_json

    def compatible_read_json(path: Path):
        data = original_read_json(path)
        # F01 historical assessor correctly exposes live state as gm_iv_state.
        # v1's first observed run looked for mission_state; alias only in memory.
        if isinstance(data, dict) and "gm_iv_state" in data and "mission_state" not in data:
            data = dict(data)
            data["mission_state"] = data["gm_iv_state"]
        return data

    v1.read_json = compatible_read_json
    rc = v1.main()
    if rc != 0:
        return rc

    pca_validator = (
        REPO
        / "mission-control"
        / "qps-triage-ultra"
        / "crew"
        / "measured"
        / "validate_exposure_pca_control.py"
    )
    proc = subprocess.run(
        [PY, str(pca_validator)],
        cwd=REPO,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    pca_out = out_dir / "crew-exposure-pca-control-validation.json"
    pca_out.write_text(proc.stdout, encoding="utf-8")
    try:
        pca = json.loads(proc.stdout)
    except json.JSONDecodeError:
        print(proc.stdout)
        return 1

    pca_ok = (
        proc.returncode == 0
        and pca.get("status") == "PASS"
        and pca.get("historical_evidence_stage") == "STAGED_ACTIVE_RECON_2_OF_8"
        and pca.get("current_mission_state") == "STAGED_ACTIVE_PILOT_2_OF_8"
        and pca.get("authority_transfer") is False
        and pca.get("competency_promotions") == 0
    )

    final_path = out_dir / "GM_IV_PILOT2_FINAL_RECENSUS.json"
    final = json.loads(final_path.read_text(encoding="utf-8"))
    final["checks"]["15_exposure_pca_control_history_forward"] = pca_ok
    final["moving_base_controls"] = {
        "crew_exposure_pca_control": {
            "status": pca.get("status"),
            "historical_evidence_stage": pca.get("historical_evidence_stage"),
            "current_mission_state": pca.get("current_mission_state"),
            "sample_rank_cap": pca.get("sample_rank_cap"),
            "bt_observed_pairs": pca.get("bt_observed_pairs"),
            "authority_transfer": pca.get("authority_transfer"),
            "competency_promotions": pca.get("competency_promotions"),
        }
    }
    final["result"] = "PASS" if all(final["checks"].values()) else "FAIL"
    final_path.write_text(
        json.dumps(final, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(final, indent=2, sort_keys=True))
    return 0 if final["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
