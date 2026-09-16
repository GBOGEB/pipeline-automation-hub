#!/usr/bin/env python3
from __future__ import annotations

import argparse
import itertools
import json
import math
from pathlib import Path

EPS = 1e-12


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _norm(a):
    return math.sqrt(_dot(a, a))


def tucker_congruence(a, b):
    na, nb = _norm(a), _norm(b)
    if na <= EPS or nb <= EPS:
        return 0.0
    return _dot(a, b) / (na * nb)


def _common_features(ref_component, cand_component):
    return sorted(set(ref_component["loadings"]) & set(cand_component["loadings"]))


def component_congruence(ref_component, cand_component):
    features = _common_features(ref_component, cand_component)
    if not features:
        return 0.0, []
    a = [float(ref_component["loadings"][f]) for f in features]
    b = [float(cand_component["loadings"][f]) for f in features]
    return tucker_congruence(a, b), features


def relative_eigengap(components, index):
    if index >= len(components) - 1:
        return None
    current = float(components[index]["eigenvalue"])
    nxt = float(components[index + 1]["eigenvalue"])
    if current <= EPS:
        return None
    return max(0.0, current - nxt) / current


def best_assignment(reference, candidate, max_components=6):
    k = min(len(reference), len(candidate), int(max_components))
    if k == 0:
        return []
    matrix = [[component_congruence(reference[i], candidate[j])[0] for j in range(k)] for i in range(k)]
    best_perm = None
    best_score = -1.0
    for perm in itertools.permutations(range(k)):
        score = sum(abs(matrix[i][perm[i]]) for i in range(k))
        if score > best_score + EPS:
            best_score = score
            best_perm = perm
    return [(i, best_perm[i], matrix[i][best_perm[i]]) for i in range(k)]


def align_receipts(reference, candidate, *, max_components=6,
                   min_abs_congruence=0.90, min_relative_eigengap=0.05):
    ref = reference["components"]
    cand = candidate["components"]
    assignment = best_assignment(ref, cand, max_components=max_components)
    rows = []
    for ref_idx, cand_idx, raw_phi in assignment:
        rc = ref[ref_idx]
        cc = cand[cand_idx]
        features = _common_features(rc, cc)
        sign = -1.0 if raw_phi < 0.0 else 1.0
        aligned = {f: sign * float(cc["loadings"][f]) for f in features}
        ref_vec = [float(rc["loadings"][f]) for f in features]
        aligned_vec = [aligned[f] for f in features]
        aligned_phi = tucker_congruence(ref_vec, aligned_vec)
        ref_gap = relative_eigengap(ref, ref_idx)
        cand_gap = relative_eigengap(cand, cand_idx)
        gaps = [x for x in (ref_gap, cand_gap) if x is not None]
        min_gap = min(gaps) if gaps else None
        congruent = abs(raw_phi) >= float(min_abs_congruence)
        separated = min_gap is not None and min_gap >= float(min_relative_eigengap)
        rows.append({
            "reference_component": rc["component"],
            "candidate_component": cc["component"],
            "component_reordered": ref_idx != cand_idx,
            "common_features": features,
            "raw_tucker_congruence": raw_phi,
            "sign_flip_applied": raw_phi < 0.0,
            "aligned_tucker_congruence": aligned_phi,
            "reference_relative_eigengap": ref_gap,
            "candidate_relative_eigengap": cand_gap,
            "minimum_relative_eigengap": min_gap,
            "congruence_check": "PASS" if congruent else "FAIL",
            "eigengap_check": "PASS" if separated else "AMBIGUOUS",
            "component_identity_reliable": congruent and separated,
            "aligned_candidate_loadings": aligned,
            "interpretation": (
                "ORIENTATION_ONLY_SIGN_FLIP" if raw_phi < 0.0 and congruent else
                "COMPONENT_REORDERING_WITH_CONGRUENT_STRUCTURE" if ref_idx != cand_idx and congruent else
                "CONGRUENT_SAME_ORIENTATION" if congruent else
                "STRUCTURAL_CHANGE_OR_NOISY_COMPONENT"
            ),
        })

    reliable = all(row["component_identity_reliable"] for row in rows) if rows else False
    return {
        "schema": "missioncontrol.temporal_pca_alignment.v1",
        "reference_source_sha": reference.get("source_sha"),
        "candidate_source_sha": candidate.get("source_sha"),
        "diagnostic_only": True,
        "governing_control_policy_changed": False,
        "thresholds": {
            "min_abs_tucker_congruence": float(min_abs_congruence),
            "min_relative_eigengap": float(min_relative_eigengap),
            "max_components": int(max_components),
        },
        "component_alignment": rows,
        "all_component_identities_reliable": reliable,
        "doctrine": {
            "raw_loading_sign_is_not_temporal_direction": True,
            "sign_alignment_required_before_loading_comparison": True,
            "component_matching_required_before_loading_comparison": True,
            "small_eigengap_makes_individual_component_identity_ambiguous": True,
            "policy_strength_is_not_pca_loading_sign": True,
        },
        "authority_transfer": False,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reference", required=True)
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-components", type=int, default=6)
    ap.add_argument("--min-abs-congruence", type=float, default=0.90)
    ap.add_argument("--min-relative-eigengap", type=float, default=0.05)
    args = ap.parse_args()
    reference = json.loads(Path(args.reference).read_text(encoding="utf-8"))
    candidate = json.loads(Path(args.candidate).read_text(encoding="utf-8"))
    result = align_receipts(
        reference,
        candidate,
        max_components=args.max_components,
        min_abs_congruence=args.min_abs_congruence,
        min_relative_eigengap=args.min_relative_eigengap,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
