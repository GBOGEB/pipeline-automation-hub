#!/usr/bin/env python3
"""Measured-only W3 fleet analytics.

The input is a source-bound telemetry document.  This module deliberately
refuses controller scores, expert seeds, and synthetic fixtures as project
PCA evidence.  It standardizes only common measured numeric CI/runtime fields.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

EPS = 1e-12


def mean(xs):
    return sum(xs) / len(xs)


def sample_std(xs):
    if len(xs) < 2:
        return 0.0
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def identity(n):
    return [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]


def jacobi_eigen_symmetric(matrix, max_iter=256, tol=1e-12):
    """Dependency-free Jacobi eigensolver for a real symmetric matrix."""
    a = [list(map(float, row)) for row in matrix]
    n = len(a)
    v = identity(n)
    if n == 0:
        return [], []

    for _ in range(max_iter):
        p = q = 0
        largest = 0.0
        for i in range(n):
            for j in range(i + 1, n):
                x = abs(a[i][j])
                if x > largest:
                    largest = x
                    p, q = i, j
        if largest < tol:
            break

        app, aqq, apq = a[p][p], a[q][q], a[p][q]
        phi = 0.5 * math.atan2(2.0 * apq, aqq - app)
        c, s = math.cos(phi), math.sin(phi)

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

    values = [a[i][i] for i in range(n)]
    vectors = [[v[r][c] for r in range(n)] for c in range(n)]
    pairs = sorted(zip(values, vectors), key=lambda x: x[0], reverse=True)
    return [p[0] for p in pairs], [p[1] for p in pairs]


def canonicalize(vec):
    if not vec:
        return vec
    k = max(range(len(vec)), key=lambda i: abs(vec[i]))
    if vec[k] < 0:
        return [-x for x in vec]
    return vec


def analyze(doc):
    contract = doc["comparability_contract"]
    rows = doc["rows"]
    required = contract["required_common_numeric_fields"]

    failures = []
    if doc.get("evidence_class") != "MEASURED_API_OBSERVATION":
        failures.append("EVIDENCE_CLASS_NOT_MEASURED_API_OBSERVATION")
    if len(rows) < int(contract["minimum_rows"]):
        failures.append("INSUFFICIENT_ROWS")
    if len({r.get("repo") for r in rows}) < int(contract["minimum_distinct_repos"]):
        failures.append("INSUFFICIENT_DISTINCT_REPOS")
    if len({r.get("mission_id") for r in rows}) < int(contract["minimum_distinct_missions"]):
        failures.append("INSUFFICIENT_DISTINCT_MISSIONS")

    for i, row in enumerate(rows):
        for field in required:
            value = row.get(field)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                failures.append(f"ROW_{i}_NON_NUMERIC_{field}")
        if row.get("runner_assigned") != 1:
            failures.append(f"ROW_{i}_RUNNER_NOT_ASSIGNED")
        if row.get("terminal_success") != 1:
            failures.append(f"ROW_{i}_NOT_SUCCESS")
        if row.get("failed_step_count") != 0:
            failures.append(f"ROW_{i}_FAILED_STEPS_NONZERO")

    if failures:
        return {
            "schema": "qps-w3-measured-analytics-receipt/v1",
            "outcome": "DEFER_COMPARABILITY_CONTRACT_FAILED",
            "failures": sorted(set(failures)),
            "w3_13": "WITHHELD",
            "w3_14": "WITHHELD",
            "w3_15": "WITHHELD_NO_CURRENT_FRONTIER_PAIRWISE_OUTCOMES"
        }

    stats = {}
    variable_fields = []
    for field in required:
        values = [float(r[field]) for r in rows]
        mu = mean(values)
        sd = sample_std(values)
        stats[field] = {"mean": mu, "sample_std": sd, "minimum": min(values), "maximum": max(values)}
        if sd > EPS:
            variable_fields.append(field)

    if len(variable_fields) < 2:
        return {
            "schema": "qps-w3-measured-analytics-receipt/v1",
            "outcome": "DEFER_INSUFFICIENT_VARIABLE_FIELDS",
            "w3_13": "PASS_THREE_COMPARABLE_MEASURED_FLEET_PULSES",
            "w3_14": "WITHHELD",
            "w3_15": "WITHHELD_NO_CURRENT_FRONTIER_PAIRWISE_OUTCOMES",
            "field_stats": stats
        }

    z = []
    for row in rows:
        z.append([(float(row[f]) - stats[f]["mean"]) / stats[f]["sample_std"] for f in variable_fields])

    n = len(z)
    p = len(variable_fields)
    cov = [[sum(z[r][i] * z[r][j] for r in range(n)) / (n - 1) for j in range(p)] for i in range(p)]
    eigvals, eigvecs = jacobi_eigen_symmetric(cov)
    eigvals = [0.0 if abs(x) < EPS else x for x in eigvals]
    total = sum(x for x in eigvals if x > 0)

    components = []
    pc_index = 1
    for eig, vec in zip(eigvals, eigvecs):
        if eig <= EPS:
            continue
        vec = canonicalize(vec)
        scores = [sum(z[r][j] * vec[j] for j in range(p)) for r in range(n)]
        components.append({
            "component": f"PC{pc_index}",
            "eigenvalue": eig,
            "explained_variance_ratio": eig / total if total else 0.0,
            "loadings": {variable_fields[j]: vec[j] for j in range(p)},
            "scores": [
                {
                    "mission_id": rows[r]["mission_id"],
                    "repo": rows[r]["repo"],
                    "run_id": rows[r]["run_id"],
                    "score": scores[r]
                }
                for r in range(n)
            ]
        })
        pc_index += 1

    return {
        "schema": "qps-w3-measured-analytics-receipt/v1",
        "outcome": "PASS_MEASURED_RUNTIME_FOOTPRINT_PCA" if components else "DEFER_NUMERICAL_DEGENERACY",
        "evidence_class": "MEASURED_NUMERIC_ONLY",
        "row_count": n,
        "distinct_repos": len({r["repo"] for r in rows}),
        "distinct_missions": len({r["mission_id"] for r in rows}),
        "rows": [
            {"mission_id": r["mission_id"], "repo": r["repo"], "run_id": r["run_id"], "source_sha": r["source_sha"]}
            for r in rows
        ],
        "field_stats": stats,
        "pca_fields": variable_fields,
        "standardization": "sample_z_score",
        "components": components,
        "statistical_boundary": "n=3 is the registry minimum; covariance rank is at most n-1. Interpret loadings as runtime-footprint pressure, not engineering maturity or causal effect.",
        "w3_13": "PASS_THREE_COMPARABLE_MEASURED_FLEET_PULSES",
        "w3_14": "PASS_MEASURED_PCA" if components else "WITHHELD",
        "w3_15": "WITHHELD_NO_CURRENT_FRONTIER_PAIRWISE_OUTCOMES",
        "authority_transfer": False
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="mission-control/qps-triage-ultra/w3_fleet_telemetry.json")
    ap.add_argument("--out")
    args = ap.parse_args()
    doc = json.loads(Path(args.input).read_text(encoding="utf-8"))
    receipt = analyze(doc)
    text = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if receipt["outcome"].startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
