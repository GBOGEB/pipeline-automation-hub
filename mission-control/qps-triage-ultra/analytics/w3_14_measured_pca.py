#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


def jacobi_eigh(a: list[list[float]], tol: float = 1e-12, max_iter: int = 10000):
    """Eigenpairs for a real symmetric matrix using Jacobi rotations."""
    n = len(a)
    m = [row[:] for row in a]
    v = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for _ in range(max_iter):
        p, q, peak = 0, 1 if n > 1 else 0, 0.0
        for i in range(n):
            for j in range(i + 1, n):
                value = abs(m[i][j])
                if value > peak:
                    p, q, peak = i, j, value
        if peak < tol:
            break
        app, aqq, apq = m[p][p], m[q][q], m[p][q]
        phi = 0.5 * math.atan2(2.0 * apq, aqq - app)
        c, s = math.cos(phi), math.sin(phi)

        for k in range(n):
            if k not in (p, q):
                mkp, mkq = m[k][p], m[k][q]
                m[k][p] = m[p][k] = c * mkp - s * mkq
                m[k][q] = m[q][k] = s * mkp + c * mkq
        m[p][p] = c*c*app - 2*s*c*apq + s*s*aqq
        m[q][q] = s*s*app + 2*s*c*apq + c*c*aqq
        m[p][q] = m[q][p] = 0.0
        for k in range(n):
            vkp, vkq = v[k][p], v[k][q]
            v[k][p] = c * vkp - s * vkq
            v[k][q] = s * vkp + c * vkq
    else:
        raise RuntimeError("Jacobi eigensolver did not converge")

    values = [m[i][i] for i in range(n)]
    vectors = [[v[row][col] for row in range(n)] for col in range(n)]
    pairs = sorted(zip(values, vectors), key=lambda pair: pair[0], reverse=True)
    return [p[0] for p in pairs], [p[1] for p in pairs]


def mean(xs):
    return sum(xs) / len(xs)


def sample_std(xs):
    mu = mean(xs)
    return math.sqrt(sum((x - mu) ** 2 for x in xs) / (len(xs) - 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--source-sha", required=True)
    args = ap.parse_args()

    path = Path(args.input)
    raw = path.read_bytes()
    data = json.loads(raw)
    rows = data["rows"]
    features = data["features"]
    if len(rows) < 3:
        raise ValueError("W3-13 measured floor is not satisfied")
    if any(r.get("evidence_class") != "MEASURED" for r in rows):
        raise ValueError("PCA refuses non-MEASURED fleet rows")
    if any(data["pca_input_policy"].get(k) != 0 for k in ("synthetic_rows", "expert_seeded_rows", "user_mandated_rows")):
        raise ValueError("PCA refuses synthetic/expert-seeded/user-mandated row unlocks")

    columns = {f: [float(r[f]) for r in rows] for f in features}
    active = []
    zcols = {}
    dropped = []
    for f, values in columns.items():
        sd = sample_std(values)
        if sd == 0.0:
            dropped.append(f)
            continue
        mu = mean(values)
        active.append(f)
        zcols[f] = [(x - mu) / sd for x in values]
    if len(active) < 2:
        raise ValueError("fewer than two varying measured features")

    n = len(rows)
    p = len(active)
    cov = [[0.0] * p for _ in range(p)]
    for i, fi in enumerate(active):
        for j, fj in enumerate(active):
            cov[i][j] = sum(zcols[fi][r] * zcols[fj][r] for r in range(n)) / (n - 1)

    eigenvalues, eigenvectors = jacobi_eigh(cov)
    eigenvalues = [max(0.0, x) for x in eigenvalues]
    total = sum(eigenvalues)
    if total <= 0:
        raise ValueError("measured covariance has no variance")
    evr = [x / total for x in eigenvalues]

    components = []
    for idx, (value, ratio, vector) in enumerate(zip(eigenvalues, evr, eigenvectors), start=1):
        loadings = {f: vector[i] for i, f in enumerate(active)}
        ranked = sorted(loadings.items(), key=lambda kv: abs(kv[1]), reverse=True)
        components.append({
            "component": f"PC{idx}",
            "eigenvalue": value,
            "explained_variance_ratio": ratio,
            "loadings": loadings,
            "dominant_features": [{"feature": f, "loading": w} for f, w in ranked[:3]],
        })

    pc1_pc2_ratio = (evr[0] / evr[1]) if len(evr) > 1 and evr[1] > 0 else None
    # This is an explicitly INFERRED navigation heuristic, not measured evidence.
    heuristic_threshold = 1.20
    pc1_flattened = pc1_pc2_ratio is not None and pc1_pc2_ratio <= heuristic_threshold
    focus_index = 1 if pc1_flattened and len(components) > 1 else 0
    focus = components[focus_index]
    feature_actions = {
        "wall_seconds": "reduce execution/runtime friction",
        "outcome_success": "stabilize pass/control state",
        "defect_observed": "attack first-red defect generation",
        "repair_present_in_head": "propagate proven repairs into controlled heads",
        "consumer_execution": "expand verified non-origin consumption",
        "receipt_emitted": "preserve receipt-on-failure and receipt-on-success lineage",
    }
    action_ranking = [
        {
            "rank": rank,
            "feature": item["feature"],
            "loading_abs": abs(item["loading"]),
            "action": feature_actions[item["feature"]],
            "basis_component": focus["component"],
            "evidence_class": "INFERRED_FROM_MEASURED_PCA",
        }
        for rank, item in enumerate(focus["dominant_features"], start=1)
    ]

    receipt = {
        "schema": "qps-w3-14-measured-pca/v1",
        "source_sha": args.source_sha,
        "input_sha256": hashlib.sha256(raw).hexdigest(),
        "input_rows": len(rows),
        "row_evidence_class": "MEASURED",
        "synthetic_rows": 0,
        "features_active": active,
        "features_dropped_zero_variance": dropped,
        "components": components,
        "pc1_to_pc2_variance_ratio": pc1_pc2_ratio,
        "pc1_flattening_interpretation": {
            "evidence_class": "INFERRED",
            "heuristic_ratio_threshold": heuristic_threshold,
            "pc1_flattened_relative_to_pc2": pc1_flattened,
            "navigation_focus": focus["component"],
        },
        "next_action_ranking": action_ranking,
        "execution": {"steps_gt0": True, "outcome": "SUCCESS"},
        "authority_transfer": False,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
