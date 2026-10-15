#!/usr/bin/env python3
"""Observed W169 source-bound telemetry; phase-02 KPI taxonomy remains canonical.

One native run is one scoped observation, never a fleet-wide KPI or QPS ACCEPT.
Source is an exact byte copy of a public ABACUS Actions receipt, SHA-pinned.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
PIN = HERE / "evidence/W169_NATIVE_PIN_v1.json"
SOURCE = HERE / "evidence/W169_QPLANT_K8S_RUNTIME_RECEIPT.json"
TAXONOMY = HERE / "PHASE02_KPI_TAXONOMY_v1.json"
SHA40 = re.compile(r"^[a-f0-9]{40}$")
SHA256 = re.compile(r"^[a-f0-9]{64}$")


def evaluate(pin: dict, raw: bytes, taxonomy: dict) -> dict:
    if taxonomy.get("schema") != "missioncontrol.phase02_kpi_taxonomy.v1":
        raise ValueError("parent KPI taxonomy changed")
    expected_ids = {"QUEUE_P95", "EXACT_HEAD_PROOF_YIELD", "FIRST_RED_COUNT",
                    "ACCEPTED_RECEIPT_YIELD", "PREDICTION_VS_ACTUAL", "RUNNER_HEALTH"}
    if {r["id"] for r in taxonomy["kpis"]} != expected_ids:
        raise ValueError("canonical KPI identity drift")
    if pin.get("schema") != "missioncontrol.sideload.w169.native-artifact-pin.v1" or pin.get("source_repo") != "GBOGEB/ABACUS":
        raise ValueError("source pin owner/schema mismatch")
    if pin.get("evidence_class") != "HISTORICAL_EXACT_SHA_NATIVE_ARTIFACT_LOCALLY_HASH_VERIFIED":
        raise ValueError("snapshot falsely declared live")
    if pin.get("authority_transfer") is not False or pin.get("engineering_credit_delta") != 0 or pin.get("child_disposition") != "DEFER" or pin.get("release") != "HOLD":
        raise ValueError("QPS authority or release promotion")
    if not SHA40.fullmatch(pin.get("source_sha", "")) or not SHA256.fullmatch(pin.get("source_receipt_sha256", "")):
        raise ValueError("untrusted source hash")
    if (pin.get("run_id"), pin.get("job_id"), pin.get("attempt"), pin.get("artifact_id")) != (38774568289, 116558746360, 1, 11993466494):
        raise ValueError("unrecognized source run/job/attempt/artifact")
    if not SHA256.fullmatch(pin.get("artifact_zip_sha256", "")) or not pin.get("artifact_url", "").startswith("https://github.com/GBOGEB/ABACUS/actions/runs/38774568289/artifacts/"):
        raise ValueError("missing archived source identity")
    if hashlib.sha256(raw).hexdigest() != pin["source_receipt_sha256"] or len(raw) != pin["source_receipt_size_bytes"]:
        raise ValueError("exact-source raw receipt mismatch")
    receipt = json.loads(raw)
    if receipt.get("schema") != "qplant-k8s-real-api-runtime-receipt/v1" or receipt.get("source_sha") != pin["source_sha"]:
        raise ValueError("wrong W169 source receipt")
    if any(receipt.get(k) != "success" for k in ("real_kubernetes_api", "server_side_admission", "canonical_image_build", "workload_rollout", "health_measurement")):
        raise ValueError("native W169 stage not successful")
    if receipt.get("static_contract") != "PASS" or receipt["authority"] != {
        "control_eligible": False, "edge_inherited": False, "engineering_credit_delta": 0, "w165_child_credit": 0
    }:
        raise ValueError("unsupported W169 source/authority")
    row = receipt.get("feature_row", {})
    if row.get("schema") != "qplant-k8s-runtime-feature-row/v1" or row.get("source_sha") != pin["source_sha"]:
        raise ValueError("feature row provenance mismatch")
    if row.get("pca_eligible") is not False or row.get("null_not_zero") is not True:
        raise ValueError("statistical validity falsely promoted")
    measured = ("request_p50_ms", "request_p95_ms", "cold_start_p50_seconds",
                "cold_start_p95_seconds", "cluster_create_seconds", "rollout_seconds",
                "execute_seconds_observed", "image_build_seconds", "image_size_mib",
                "restart_count")
    for key in measured:
        val = row.get(key)
        if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val) or val < 0:
            raise ValueError("missing or invalid observed metric " + key)
    if row["request_p95_ms"] < row["request_p50_ms"] or row["cold_start_p95_seconds"] < row["cold_start_p50_seconds"]:
        raise ValueError("invalid p95 vs p50")
    for missing in ("queue_seconds", "cpu_peak_millicores", "memory_peak_mib"):
        if row.get(missing) is not None:
            raise ValueError("unsupported metric imputation " + missing)
    # This is a W169 SINGLE-RUN proof slice, not the canonical six-KPI population.
    return {
        "schema": "missioncontrol.sideload.w169.telemetry-projection.v1",
        "source_class": pin["evidence_class"], "source_repo": pin["source_repo"],
        "source_sha": pin["source_sha"], "source_run_id": pin["run_id"],
        "source_job_id": pin["job_id"], "attempt": pin["attempt"],
        "source_artifact_id": pin["artifact_id"], "source_url": pin["artifact_url"],
        "source_receipt_sha256": pin["source_receipt_sha256"],
        "artifact_zip_sha256": pin["artifact_zip_sha256"],
        "observation_count": 1,
        "w169_scoped_native_proof_yield": {"numerator": 1, "denominator": 1, "scope": "ONLY_THIS_PINNED_W169_RUN"},
        "real_k8s_api_stage": "SUCCESS_EXACT_PINNED_RUN",
        "workload_stage": "SUCCESS_EXACT_PINNED_RUN",
        "metrics": {key: row[key] for key in measured},
        "unbound": {
            "queue_p95_seconds": None, "cpu_peak_millicores": None,
            "memory_peak_mib": None, "sideload_rejection_count": None,
            "first_red_propagation_count": None, "fleet_exact_head_proof_yield": None,
            "federation_accepted_receipt_yield": None, "full_four_hop_authenticated": None,
            "edge_qualified": None, "qps_child_acceptance": None
        },
        "parent_kpi_taxonomy": "mission-control/federation-atlas/PHASE02_KPI_TAXONOMY_v1.json",
        "qps_disposition": "DEFER", "release": "HOLD",
        "authority_transfer": False, "formal_credit_delta": 0, "engineering_credit_delta": 0,
    }


def build(out: Path, pin_path: Path = PIN, source_path: Path = SOURCE) -> dict:
    pin = json.loads(pin_path.read_text(encoding="utf-8"))
    taxonomy = json.loads(TAXONOMY.read_text(encoding="utf-8"))
    result = evaluate(pin, source_path.read_bytes(), taxonomy)
    out.mkdir(parents=True, exist_ok=True)
    target = out / "sideload-telemetry.json"
    content = json.dumps(result, indent=2, sort_keys=True) + "\n"
    target.write_text(content, encoding="utf-8")
    manifest = {
        "schema": "missioncontrol.sideload.w169.telemetry-manifest.v1",
        "source_receipt_sha256": pin["source_receipt_sha256"],
        "projection_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "source_class": pin["evidence_class"], "admission": "HOLD",
        "qps_disposition": "DEFER", "authority_transfer": False,
    }
    (out / "sideload-telemetry.sha256.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(build(args.out), sort_keys=True))
