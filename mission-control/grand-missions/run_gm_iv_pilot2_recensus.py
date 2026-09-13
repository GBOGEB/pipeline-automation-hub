#!/usr/bin/env python3
"""Execute a no-loss exact-head GM-IV PILOT_2_OF_8 recensus.

This runner deliberately re-executes the frontier evidence needed by the
Governor transition instead of trusting stale pull-request check metadata.
Historical recon/pilot assessors remain non-promotional; only the Governor
assessor may authorize the stage transition.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import nbformat
import yaml
from nbconvert.preprocessors import ExecutePreprocessor

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PY = sys.executable

F01_SHA = "d85dc2de1b4beb88bc8e8ce4796784f4577f9a96"
F02_SHA = "10334b5f1e684784025c3fc0a277c88c19089275"
F03_SHA = "1eba2240a86d1fd2bd6375e2fac481caf645cdde"
F04_SHA = "2c36c6cb4cce0c29e5adfb97743ddb7b17b0eb99"
NOTEBOOK_DIGEST = "718faee59adbe581809fc7eb01339a577c67caa5df5e3fc5287d6f800be739ad"


def run(cmd, *, cwd=None, check=True, capture=False, timeout=None, env=None):
    merged = os.environ.copy()
    if env:
        merged.update(env)
    kwargs = {
        "cwd": cwd,
        "check": check,
        "text": True,
        "env": merged,
        "timeout": timeout,
    }
    if capture:
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.STDOUT
    return subprocess.run(cmd, **kwargs)


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def exact_fetch(url: str, sha: str, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=False)
    run(["git", "-C", str(dest), "init"])
    run(["git", "-C", str(dest), "remote", "add", "origin", url])
    run(["git", "-C", str(dest), "fetch", "--depth=1", "origin", sha])
    run(["git", "-C", str(dest), "checkout", "--detach", "FETCH_HEAD"])
    actual = run(["git", "-C", str(dest), "rev-parse", "HEAD"], capture=True).stdout.strip()
    if actual != sha:
        raise RuntimeError(f"exact fetch mismatch {url}: {actual} != {sha}")


def git_clean(repo: Path) -> bool:
    return not run(["git", "-C", str(repo), "status", "--porcelain"], capture=True).stdout.strip()


def call_assessor(script: str, args: list[str], out: Path, source_sha: str) -> None:
    env = {"SOURCE_SHA": source_sha}
    run([PY, str(HERE / script), *args, "--out", str(out)], cwd=REPO, env=env)


def execute_notebook_twice(f03: Path):
    notebook = f03 / "notebooks" / "population.ipynb"

    def execute_once():
        nb = nbformat.read(notebook, as_version=4)
        ExecutePreprocessor(timeout=120, kernel_name="python3").preprocess(
            nb, {"metadata": {"path": str(notebook.parent)}}
        )
        cells = 0
        errors = 0
        governed = []
        for cell in nb.cells:
            if cell.cell_type != "code":
                continue
            cells += 1
            outputs = []
            for out in cell.get("outputs", []):
                kind = out.get("output_type")
                item = {"output_type": kind}
                if kind == "error":
                    errors += 1
                    item.update(ename=out.get("ename"), evalue=out.get("evalue"))
                elif kind == "stream":
                    item.update(name=out.get("name"), text=out.get("text", ""))
                elif kind in ("execute_result", "display_data"):
                    data = out.get("data", {})
                    item["data"] = {
                        k: data[k]
                        for k in sorted(data)
                        if k in ("text/plain", "text/html")
                    }
                outputs.append(item)
            governed.append({"source": cell.source, "outputs": outputs})
        raw = json.dumps(governed, sort_keys=True, separators=(",", ":")).encode()
        return cells, errors, sha256_bytes(raw)

    first = execute_once()
    second = execute_once()
    return first, second


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    out = Path(args.out_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    source_sha = os.environ.get("SOURCE_SHA") or run(
        ["git", "rev-parse", "HEAD"], cwd=REPO, capture=True
    ).stdout.strip()
    if len(source_sha) != 40:
        raise RuntimeError("SOURCE_SHA is not exact")

    work = Path(tempfile.mkdtemp(prefix="gmiv-pilot2-recensus-"))
    checks: dict[str, bool] = {}
    details: dict[str, object] = {}
    try:
        f01 = work / "f01"
        f02 = work / "f02"
        f03 = work / "f03"
        f04 = work / "f04"
        exact_fetch("https://github.com/GBOGEB/DOCX_RTM_Automation.git", F01_SHA, f01)
        exact_fetch("https://github.com/GBOGEB/attest-build-provenance.git", F02_SHA, f02)
        exact_fetch("https://github.com/GBOGEB/codespaces-jupyter.git", F03_SHA, f03)
        exact_fetch("https://github.com/GBOGEB/yaml-reference-parser.git", F04_SHA, f04)
        checks["01_exact_four_frontier_fetch"] = all(
            run(["git", "-C", str(p), "rev-parse", "HEAD"], capture=True).stdout.strip() == s
            for p, s in ((f01, F01_SHA), (f02, F02_SHA), (f03, F03_SHA), (f04, F04_SHA))
        )

        # F01 Ring1 self-index and controlled pilot proof.
        f01_index = out / "f01-self-index.json"
        run([PY, str(f01 / "scripts" / "mip_repo_self_index.py"), "--output", str(f01_index)])
        pos = run([PY, str(f01 / "scripts" / "validate_adr_ocd_bridge.py")], capture=True)
        pos_text = pos.stdout
        (out / "f01-positive.txt").write_text(pos_text, encoding="utf-8")
        bridge = yaml.safe_load((f01 / "federation" / "ADR_OCD" / "bridge_manifest.yaml").read_text(encoding="utf-8"))
        bridge["qps_authority_source"]["repo"] = "GBOGEB/NOT_THE_QPS_AUTHORITY"
        bad_manifest = out / "f01-bad-manifest.yaml"
        bad_manifest.write_text(yaml.safe_dump(bridge, sort_keys=False), encoding="utf-8")
        neg = run(
            [PY, str(f01 / "scripts" / "validate_adr_ocd_bridge.py"), "--manifest", str(bad_manifest)],
            check=False,
            capture=True,
        )
        (out / "f01-negative.txt").write_text(neg.stdout, encoding="utf-8")
        f01_runtime = {
            "schema": "qps.gm_iv_f01_target_runtime.v1",
            "target_repository": "GBOGEB/DOCX_RTM_Automation",
            "target_sha": F01_SHA,
            "entrypoint": "scripts/validate_adr_ocd_bridge.py",
            "positive_exit_code": pos.returncode,
            "positive_pass_marker": "ADR_OCD bridge validation passed" in pos_text,
            "positive_validated_surface_count": sum(
                marker in pos_text
                for marker in (
                    "validated glossary:",
                    "validated bridge manifest:",
                    "validated taxonomy:",
                    "validated QPS triage applicability:",
                )
            ),
            "positive_output_sha256": sha256_bytes(pos_text.encode()),
            "negative_exit_code": neg.returncode,
            "negative_rejection_marker": "qps_authority_source.repo must be GBOGEB/cryoplant-project" in neg.stdout,
            "negative_output_sha256": sha256_bytes(neg.stdout.encode()),
            "target_dirty_file_count": 0 if git_clean(f01) else 1,
            "target_application_modified": False,
        }
        f01_runtime_path = out / "f01-pilot-runtime.json"
        write_json(f01_runtime_path, f01_runtime)
        checks["02_f01_positive_negative_clean"] = (
            pos.returncode == 0
            and f01_runtime["positive_pass_marker"]
            and f01_runtime["positive_validated_surface_count"] >= 4
            and neg.returncode != 0
            and f01_runtime["negative_rejection_marker"]
            and git_clean(f01)
        )

        f01_assess_1 = out / "f01-assess-1.json"
        f01_assess_2 = out / "f01-assess-2.json"
        call_assessor(
            "assess_gm_iv_f01_pilot.py",
            ["--runtime-receipt", str(f01_runtime_path)],
            f01_assess_1,
            source_sha,
        )
        call_assessor(
            "assess_gm_iv_f01_pilot.py",
            ["--runtime-receipt", str(f01_runtime_path)],
            f01_assess_2,
            source_sha,
        )
        f01a = read_json(f01_assess_1)
        checks["03_f01_assessor_repeat_history"] = (
            f01_assess_1.read_bytes() == f01_assess_2.read_bytes()
            and f01a["frontier_disposition"] == "PILOT_CONTROL_READY"
            and f01a["historical_evidence_stage"] == "STAGED_ACTIVE_RECON_2_OF_8"
            and f01a["mission_state"] == "STAGED_ACTIVE_PILOT_2_OF_8"
            and f01a["mission_promotion"].startswith("WITHHELD_FROM_F01_RECURRENCE")
        )

        f02_action = (f02 / "action.yml").read_text(encoding="utf-8")
        f02_readme = (f02 / "README.md").read_text(encoding="utf-8")
        checks["04_f02_reference_contract"] = (
            'using: "composite"' in f02_action
            and "uses: actions/attest@" in f02_action
            and "wrapper" in f02_readme.lower()
            and "new implementations should use `actions/attest`" in f02_readme
            and git_clean(f02)
        )
        ring1_1 = out / "ring1-1.json"
        ring1_2 = out / "ring1-2.json"
        call_assessor(
            "assess_gm_iv_ring1.py",
            ["--f01-receipt", str(f01_index), "--f02-action", str(f02 / "action.yml"), "--f02-readme", str(f02 / "README.md")],
            ring1_1,
            source_sha,
        )
        call_assessor(
            "assess_gm_iv_ring1.py",
            ["--f01-receipt", str(f01_index), "--f02-action", str(f02 / "action.yml"), "--f02-readme", str(f02 / "README.md")],
            ring1_2,
            source_sha,
        )
        r1 = read_json(ring1_1)
        checks["05_ring1_repeat_history"] = (
            ring1_1.read_bytes() == ring1_2.read_bytes()
            and r1["result"] == "PASS"
            and r1["historical_evidence_stage"] == "RECON_2_OF_8"
            and r1["current_mission_state"] == "STAGED_ACTIVE_PILOT_2_OF_8"
            and r1["dispositions"]["GM-IV-F01"]["disposition"] == "PILOT"
            and r1["dispositions"]["GM-IV-F02"]["disposition"] == "REFERENCE"
        )

        # F03 controlled pilot and Ring2 runtime.
        boundary_pos = run(
            [PY, str(HERE / "validate_gm_iv_f03_boundary.py"), str(f03 / "level1" / "ssot.json")],
            capture=True,
        )
        (out / "f03-boundary-positive.txt").write_text(boundary_pos.stdout, encoding="utf-8")
        bad_ssot_data = read_json(f03 / "level1" / "ssot.json")
        bad_ssot_data["authority_transfer"] = True
        bad_ssot = out / "f03-bad-ssot.json"
        write_json(bad_ssot, bad_ssot_data)
        boundary_neg = run(
            [PY, str(HERE / "validate_gm_iv_f03_boundary.py"), str(bad_ssot)],
            check=False,
            capture=True,
        )
        (out / "f03-boundary-negative.txt").write_text(boundary_neg.stdout, encoding="utf-8")
        boundary_markers = (
            "validated F03 Level-1 SSOT identity",
            "validated F03 runtime producer role",
            "validated F03 authority_transfer=false",
            "validated F03 must_not authority boundary",
            "F03 authority validation passed",
        )
        f03_boundary = {
            "schema": "qps.gm_iv_f03_boundary_receipt.v1",
            "positive_exit_code": boundary_pos.returncode,
            "positive_marker_count": sum(m in boundary_pos.stdout for m in boundary_markers),
            "negative_exit_code": boundary_neg.returncode,
            "negative_rejection_observed": "authority_transfer must be false" in boundary_neg.stdout,
            "target_repository_modified": False,
        }
        f03_boundary_path = out / "f03-boundary.json"
        write_json(f03_boundary_path, f03_boundary)

        first, second = execute_notebook_twice(f03)
        c1, e1, d1 = first
        c2, e2, d2 = second
        f03_control = {
            "schema": "qps.gm_iv_f03_controlled_runtime_receipt.v1",
            "target_sha": F03_SHA,
            "run1_code_cells": c1,
            "run2_code_cells": c2,
            "total_error_count": e1 + e2,
            "run1_digest": d1,
            "run2_digest": d2,
            "repeat_equal": d1 == d2,
            "target_dirty_count": 0 if git_clean(f03) else 1,
            "gm_v_state": "HELD",
        }
        f03_control_path = out / "f03-runtime-control.json"
        write_json(f03_control_path, f03_control)
        checks["06_f03_positive_negative_runtime_clean"] = (
            boundary_pos.returncode == 0
            and f03_boundary["positive_marker_count"] == 5
            and boundary_neg.returncode != 0
            and f03_boundary["negative_rejection_observed"]
            and c1 > 0 and c2 > 0 and e1 == 0 and e2 == 0
            and d1 == d2 == NOTEBOOK_DIGEST
            and git_clean(f03)
        )

        f03_assess_1 = out / "f03-assess-1.json"
        f03_assess_2 = out / "f03-assess-2.json"
        f03_contract = HERE / "GM_IV_F03_PILOT_CONTRACT.json"
        call_assessor(
            "assess_gm_iv_f03_pilot.py",
            ["--contract", str(f03_contract), "--runtime", str(f03_control_path), "--boundary", str(f03_boundary_path), "--source-sha", source_sha],
            f03_assess_1,
            source_sha,
        )
        call_assessor(
            "assess_gm_iv_f03_pilot.py",
            ["--contract", str(f03_contract), "--runtime", str(f03_control_path), "--boundary", str(f03_boundary_path), "--source-sha", source_sha],
            f03_assess_2,
            source_sha,
        )
        f03a = read_json(f03_assess_1)
        checks["07_f03_assessor_repeat_history"] = (
            f03_assess_1.read_bytes() == f03_assess_2.read_bytes()
            and f03a["frontier_disposition"] == "PILOT_CONTROL_READY"
            and f03a["historical_evidence_stage"] == "STAGED_ACTIVE_RECON_2_OF_8"
            and f03a["mission_state"] == "STAGED_ACTIVE_PILOT_2_OF_8"
            and f03a["mission_promotion"].startswith("WITHHELD_FROM_F03_RECURRENCE")
        )

        f03_ring = {
            "schema": "qps.gm_iv_f03_runtime_receipt.v1",
            "target_sha": F03_SHA,
            "executed_code_cells": min(c1, c2),
            "error_count": e1 + e2,
            "run1_digest": d1,
            "run2_digest": d2,
            "repeat_equal": d1 == d2,
            "mesh_role": "REPRODUCIBLE_NOTEBOOK_RUNTIME_PRODUCER",
            "must_not_override_child_authority": True,
            "source_dirty_count": 0 if git_clean(f03) else 1,
        }
        f03_ring_path = out / "f03-ring2-runtime.json"
        write_json(f03_ring_path, f03_ring)

        # F04 bounded legacy runtime attempt and reference classification.
        f04_run = work / "f04-run"
        shutil.copytree(f04, f04_run)
        f04_proc = run(
            ["make", "-C", str(f04_run), "test"],
            check=False,
            capture=True,
            timeout=180,
        )
        (out / "f04-test.log").write_text(f04_proc.stdout, encoding="utf-8")
        readme = (f04 / "ReadMe.md").read_text(encoding="utf-8")
        identity = "YAML 1.2 Reference Parsers" in readme and "make test" in readme
        authority_claim = False
        for p in f04.rglob("*"):
            if not p.is_file() or ".git" in p.parts or p.stat().st_size > 1_000_000:
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if "gbogeb/cryoplant-project" in text.lower() or "qps authority" in text.lower():
                authority_claim = True
                break
        f04_receipt = {
            "schema": "qps.gm_iv_f04_reference_receipt.v1",
            "target_sha": F04_SHA,
            "test_attempted": True,
            "test_exit_code": f04_proc.returncode,
            "reference_parser_identity": identity,
            "qps_authority_claim_detected": authority_claim,
            "source_dirty_count": 0 if git_clean(f04) else 1,
        }
        f04_receipt_path = out / "f04-reference.json"
        write_json(f04_receipt_path, f04_receipt)
        checks["08_f04_reference_real_attempt"] = identity and not authority_claim and git_clean(f04)

        ring2_1 = out / "ring2-1.json"
        ring2_2 = out / "ring2-2.json"
        ring2_contract = HERE / "GM_IV_RING2_RECON_CONTRACT.json"
        call_assessor(
            "assess_gm_iv_ring2.py",
            ["--contract", str(ring2_contract), "--f03", str(f03_ring_path), "--f04", str(f04_receipt_path), "--source-sha", source_sha],
            ring2_1,
            source_sha,
        )
        call_assessor(
            "assess_gm_iv_ring2.py",
            ["--contract", str(ring2_contract), "--f03", str(f03_ring_path), "--f04", str(f04_receipt_path), "--source-sha", source_sha],
            ring2_2,
            source_sha,
        )
        r2 = read_json(ring2_1)
        checks["09_ring2_repeat_history"] = (
            ring2_1.read_bytes() == ring2_2.read_bytes()
            and r2["result"] == "PASS"
            and r2["historical_evidence_stage"] == "STAGED_ACTIVE_RECON_2_OF_8"
            and r2["mission_state"] == "STAGED_ACTIVE_PILOT_2_OF_8"
            and r2["dispositions"]["GM-IV-F03"]["disposition"] == "PILOT_READY"
            and r2["dispositions"]["GM-IV-F04"]["disposition"] == "REFERENCE"
            and r2["mission_promotion"].startswith("WITHHELD_FROM_RING2_RECURRENCE")
        )

        # Core active control validators.
        governor = out / "governor.json"
        fleet = out / "fleet.json"
        capacity_1 = out / "capacity-1.json"
        capacity_2 = out / "capacity-2.json"
        call_assessor("assess_gm_iv_pilot2_governor.py", [], governor, source_sha)
        call_assessor("validate_gm_fleet.py", [], fleet, source_sha)
        call_assessor("assess_gm_fleet_03.py", [], capacity_1, source_sha)
        call_assessor("assess_gm_fleet_03.py", [], capacity_2, source_sha)
        gov = read_json(governor)
        checks["10_governor_transition"] = (
            gov["result"] == "PASS"
            and gov["promotion_decision"] == "PROMOTE_PILOT_2_OF_8"
            and gov["mission_state"] == "STAGED_ACTIVE_PILOT_2_OF_8"
            and gov["next_stage"] == "WITHHELD_PENDING_SEPARATE_RECON_4_OF_8_GOVERNOR_GATE"
        )
        checks["11_fleet_capacity_regressions"] = (
            read_json(fleet)["source_sha"] == source_sha
            and capacity_1.read_bytes() == capacity_2.read_bytes()
            and read_json(capacity_1)["structural_gate"] == "PASS"
        )

        econ = run([PY, str(HERE / "validate_gm_iv_evidence_economics.py")], cwd=REPO, capture=True)
        (out / "evidence-economics.json").write_text(econ.stdout, encoding="utf-8")
        econ_data = json.loads(econ.stdout)
        checks["12_evidence_economics"] = econ.returncode == 0 and econ_data["status"] == "PASS" and econ_data["passed"] == econ_data["denominator"]

        # Instrumentation canary using exact arithmetic, never mission-performance eligible.
        opened = datetime.now(timezone.utc).replace(microsecond=123456)
        started = opened + timedelta(seconds=1)
        ended = started + timedelta(seconds=2)
        released = ended + timedelta(seconds=1)
        canary = {
            "schema": "missioncontrol.crew_exposure_receipt.v1",
            "mission_id": "INSTRUMENTATION_CANARY",
            "task_id": "GM_IV_PILOT2_RECENSUS_CLOCK",
            "assignment_id": os.environ.get("GITHUB_RUN_ID", "LOCAL"),
            "crew_id": "CANARY_ONLY",
            "crew_role": "INSTRUMENTATION_CANARY",
            "assignment_opened_at": opened.isoformat(),
            "task_started_at": started.isoformat(),
            "task_ended_at": ended.isoformat(),
            "assignment_released_at": released.isoformat(),
            "waiting_seconds": 1.0,
            "active_seconds": 2.0,
            "release_seconds": 1.0,
            "exposure_seconds": 4.0,
            "intervention_type": "INSTRUMENTATION",
            "outcome": "CONTROL",
            "source_sha": source_sha,
            "receipt_evidence_class": "INSTRUMENTATION_CANARY_ONLY",
            "authority_transfer": False,
            "child_binding": False,
            "frontier_binding": False,
            "pca_eligible": False,
            "bt_eligible": False,
            "competency_promotion_eligible": False,
            "mission_performance_eligible": False,
        }
        canary_path = out / "crew-exposure-canary.json"
        write_json(canary_path, canary)
        crew_validator = REPO / "mission-control" / "qps-triage-ultra" / "crew" / "measured" / "validate_crew_exposure.py"
        crew = run([PY, str(crew_validator), str(canary_path)], cwd=REPO, capture=True)
        (out / "crew-exposure-validation.json").write_text(crew.stdout, encoding="utf-8")
        crew_data = json.loads(crew.stdout)
        checks["13_crew_exposure_microsecond_control"] = (
            crew.returncode == 0
            and crew_data["status"] == "PASS"
            and crew_data.get("time_resolution") == "MICROSECOND_INTEGER"
        )

        registry = read_json(HERE / "GRAND_MISSION_REGISTRY.json")
        gm = {m["id"]: m for m in registry["grand_missions"]}
        gm4 = gm["GM-IV"]
        gm5 = gm["GM-V"]
        checks["14_terminal_shape"] = (
            gm4["state"] == "STAGED_ACTIVE_PILOT_2_OF_8"
            and gm4["controlled_pilot_frontiers"] == ["GM-IV-F01", "GM-IV-F03"]
            and gm4["reference_frontiers"] == ["GM-IV-F02", "GM-IV-F04"]
            and gm4["unfilled_frontier_slots"] == ["GM-IV-F05", "GM-IV-F06", "GM-IV-F07", "GM-IV-F08"]
            and gm4["children"] == []
            and registry["authority_transfer"] is False
            and gm5["state"] == "HELD"
            and gm5["children"] == []
        )

        result = "PASS" if all(checks.values()) else "FAIL"
        receipt = {
            "schema": "qps.gm_iv_pilot2_final_recensus.v1",
            "source_sha": source_sha,
            "run_id": os.environ.get("GITHUB_RUN_ID", "LOCAL"),
            "result": result,
            "checks": checks,
            "details": details,
            "controlled_pilots": ["GM-IV-F01", "GM-IV-F03"],
            "references": ["GM-IV-F02", "GM-IV-F04"],
            "unfilled": ["GM-IV-F05", "GM-IV-F06", "GM-IV-F07", "GM-IV-F08"],
            "children_bound": False,
            "authority_transfer": False,
            "gm_v_state": "HELD",
            "next_stage": "WITHHELD_PENDING_SEPARATE_RECON_4_OF_8_GOVERNOR_GATE",
        }
        final = out / "GM_IV_PILOT2_FINAL_RECENSUS.json"
        write_json(final, receipt)
        print(json.dumps(receipt, indent=2, sort_keys=True))
        return 0 if result == "PASS" else 1
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
