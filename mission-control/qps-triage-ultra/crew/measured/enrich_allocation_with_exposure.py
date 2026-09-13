#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTROL = ROOT / "history" / "CREW_EXPOSURE_CONTROL_RETURN_v1.json"
POLICY = ROOT / "CREW_EXPOSURE_FEATURE_POLICY_v1.json"
ALLOCATION_POLICY = ROOT / "MEASURED_ALLOCATION_POLICY_v1.json"
ALLOCATION = ROOT / "MEASURED_ALLOCATION_RECEIPT.json"

control = json.loads(CONTROL.read_text(encoding="utf-8"))
policy = json.loads(POLICY.read_text(encoding="utf-8"))
allocation_policy = json.loads(ALLOCATION_POLICY.read_text(encoding="utf-8"))
allocation = json.loads(ALLOCATION.read_text(encoding="utf-8"))

gate = control["repeat_gate"]
allocation_gate = policy["allocation_eligibility_gate"]
pca_candidate_gate = policy["pca_candidate_gate"]
assert control["schema"] == "missioncontrol.crew_exposure_control_return.v1"
assert control["status"] == allocation_gate["status_required"]
assert gate["observed_distinct_runs"] >= allocation_gate["minimum_distinct_runs"]
assert gate["observed_distinct_source_shas"] >= allocation_gate["minimum_distinct_source_shas"]
assert gate["all_assignments_predeclared"] is True
assert gate["all_assignments_accepted"] is True
assert gate["all_exposure_identities_valid"] is True
assert gate["no_canary_rows"] is True
assert gate["no_estimated_or_post_hoc_time"] is True
assert control["authority_transfer"] is False
assert control["child_binding"] is False
assert control["frontier_binding"] is False
assert control["competency_promotions"] == 0

by_crew: dict[str, list[dict]] = defaultdict(list)
run_ids = set()
source_shas = set()
for run in control["evidence_runs"]:
    run_ids.add(str(run["run_id"]))
    source_shas.add(run["source_sha"])
    for observation in run["assignments"]:
        assert observation["outcome"] == "ACCEPT"
        by_crew[observation["crew_id"]].append(observation)

feature_names = policy["allocation_features"]
for row in allocation["rows"]:
    obs = by_crew.get(row["crew_id"], [])
    if not obs:
        row["exposure_control_eligible"] = False
        continue
    values = {
        "mean_waiting_seconds": statistics.mean(o["waiting_seconds"] for o in obs),
        "mean_active_seconds": statistics.mean(o["active_seconds"] for o in obs),
        "mean_release_seconds": statistics.mean(o["release_seconds"] for o in obs),
        "mean_exposure_seconds": statistics.mean(o["exposure_seconds"] for o in obs),
    }
    row.update(values)
    row["exposure_control_eligible"] = True
    row["exposure_distinct_runs"] = len(run_ids)
    row["exposure_distinct_source_shas"] = len(source_shas)
    row["exposure_evidence_class"] = "CONTROLLED_MEASURED_THREE_PULSE"

controlled_rows = [r for r in allocation["rows"] if r.get("exposure_control_eligible")]
varying_exposure = []
for feature in feature_names:
    vals = [r[feature] for r in controlled_rows if r.get(feature) is not None]
    if len(vals) >= 2 and len(set(vals)) > 1:
        varying_exposure.append(feature)

pca_candidate_eligible = (
    control["status"] == pca_candidate_gate["status_required"]
    and len(run_ids) >= pca_candidate_gate["minimum_distinct_runs"]
    and len(source_shas) >= pca_candidate_gate["minimum_distinct_source_shas"]
    and gate["all_assignments_predeclared"] is True
    and gate["all_assignments_accepted"] is True
    and gate["no_canary_rows"] is True
    and gate["no_estimated_or_post_hoc_time"] is True
)


def jacobi_eigen_symmetric(matrix: list[list[float]], tol: float = 1e-12, max_iter: int = 200) -> tuple[list[float], list[list[float]]]:
    n = len(matrix)
    a = [row[:] for row in matrix]
    v = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    if n <= 1:
        return ([a[0][0]] if n else []), v
    for _ in range(max_iter):
        p, q = 0, 1
        maximum = abs(a[p][q])
        for i in range(n):
            for j in range(i + 1, n):
                if abs(a[i][j]) > maximum:
                    maximum = abs(a[i][j])
                    p, q = i, j
        if maximum < tol:
            break
        app, aqq, apq = a[p][p], a[q][q], a[p][q]
        angle = 0.5 * math.atan2(2.0 * apq, aqq - app)
        c, s = math.cos(angle), math.sin(angle)
        for k in range(n):
            if k in (p, q):
                continue
            akp, akq = a[k][p], a[k][q]
            a[k][p] = a[p][k] = c * akp - s * akq
            a[k][q] = a[q][k] = s * akp + c * akq
        a[p][p] = c * c * app - 2.0 * s * c * apq + s * s * aqq
        a[q][q] = s * s * app + 2.0 * s * c * apq + c * c * aqq
        a[p][q] = a[q][p] = 0.0
        for k in range(n):
            vkp, vkq = v[k][p], v[k][q]
            v[k][p] = c * vkp - s * vkq
            v[k][q] = s * vkp + c * vkq
    eigenvalues = [a[i][i] for i in range(n)]
    return eigenvalues, v


def measured_pca(rows: list[dict], candidate_features: list[str]) -> dict:
    available = []
    for feature in candidate_features:
        vals = [r.get(feature) for r in rows]
        if all(v is not None for v in vals) and len(set(vals)) > 1:
            available.append(feature)
    min_rows = allocation_policy["pca_gate"]["min_measured_rows"]
    min_varying = allocation_policy["pca_gate"]["min_varying_features"]
    result = {
        "measured_rows": len(rows),
        "eligible_rows": len(rows),
        "candidate_feature_count": len(candidate_features),
        "varying_features": len(available),
        "features_used": available,
        "sample_rank_cap": max(0, min(len(rows) - 1, len(available))),
        "small_n": True,
        "causal_interpretation_allowed": False,
        "competency_promotion_allowed": False,
    }
    if len(rows) < min_rows:
        result["status"] = "DEFER_INSUFFICIENT_ELIGIBLE_MEASURED_ROWS"
        result["components"] = []
        return result
    if len(available) < min_varying:
        result["status"] = "DEFER_INSUFFICIENT_MEASURED_VARIANCE"
        result["components"] = []
        return result

    columns = {}
    for feature in available:
        vals = [float(r[feature]) for r in rows]
        mean = statistics.mean(vals)
        std = statistics.stdev(vals)
        assert std > 0
        columns[feature] = [(v - mean) / std for v in vals]

    n = len(rows)
    p = len(available)
    covariance = [[0.0 for _ in range(p)] for _ in range(p)]
    for i, fi in enumerate(available):
        for j, fj in enumerate(available):
            covariance[i][j] = sum(a * b for a, b in zip(columns[fi], columns[fj])) / (n - 1)

    eigenvalues, eigenvectors = jacobi_eigen_symmetric(covariance)
    order = sorted(range(p), key=lambda idx: eigenvalues[idx], reverse=True)
    positive_total = sum(max(0.0, eigenvalues[idx]) for idx in order)
    rank_cap = min(n - 1, p)
    components = []
    for rank, idx in enumerate(order[:rank_cap], start=1):
        eigenvalue = max(0.0, eigenvalues[idx])
        if eigenvalue <= 1e-12:
            continue
        loadings = {feature: eigenvectors[i][idx] for i, feature in enumerate(available)}
        dominant = sorted(loadings, key=lambda f: abs(loadings[f]), reverse=True)[:3]
        components.append({
            "component": f"PC{rank}",
            "eigenvalue": eigenvalue,
            "explained_variance_ratio": (eigenvalue / positive_total if positive_total else 0.0),
            "loadings": loadings,
            "dominant_features": dominant,
        })
    result["status"] = "READY_MEASURED_SMALL_N"
    result["components"] = components
    result["explained_variance_total"] = sum(c["explained_variance_ratio"] for c in components)
    return result

base_feature_candidates = [
    "demonstrated_level",
    "acceptance_rate",
    "distinct_accepted_runs",
    "distinct_source_shas",
    "mean_execute_seconds",
    "rex_trigger_rate",
]
augmented_candidates = base_feature_candidates + policy["pca"]["candidate_features"]
pre_exposure_pca = allocation.get("pca", {})
if pca_candidate_eligible:
    allocation["pca"] = measured_pca(controlled_rows, augmented_candidates)
    allocation["pca"]["model_scope"] = "CREW_ROW_ALLOCATION_WITH_CONTROLLED_EXPOSURE"
    allocation["pca"]["pre_exposure_status"] = pre_exposure_pca.get("status")
    pca_ingest_status = "INGESTED_READY_SMALL_N" if allocation["pca"]["status"].startswith("READY") else allocation["pca"]["status"]
else:
    pca_ingest_status = "DEFER_EXPOSURE_REPEAT_GATE"

allocation["exposure_control"] = {
    "status": "CONTROLLED_PCA_CANDIDATE_FEATURES" if pca_candidate_eligible else "CONTROLLED_OPTIONAL_FEATURES",
    "source_control_return": CONTROL.name,
    "controlled_rows": len(controlled_rows),
    "distinct_runs": len(run_ids),
    "distinct_source_shas": len(source_shas),
    "allocation_features": feature_names,
    "varying_features": varying_exposure,
    "pca_candidate_eligible": pca_candidate_eligible,
    "pca_feature_ingest_status": pca_ingest_status,
    "bt_status": "NO_CHANGE_EXISTING_BT_OUTCOME_GATE",
    "competency_promotions": 0,
    "authority_transfer": False,
}

allocation["pca_pre_exposure"] = pre_exposure_pca
ALLOCATION.write_text(json.dumps(allocation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({
    "exposure_control": allocation["exposure_control"],
    "crew_row_pca": allocation["pca"],
}, sort_keys=True))
