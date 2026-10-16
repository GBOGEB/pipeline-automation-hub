"""Canonical gg_MATH-only reference dispatch for qualified experiment designs.

A passed geometry screen is not independent-sampling authentication. Numerical
results here are synthetic reference diagnostics, never ABACUS process inference.
"""
from __future__ import annotations

import argparse
import importlib
import json
import math
import re
import subprocess
import sys
from pathlib import Path

from mip_statistical_qualification import qualify, require

HEX40 = re.compile(r"[0-9a-f]{40}\Z")
INPUT = "code-purple.mip.provider-request.v1"
OUT = "code-purple.mip.provider-reference.v1"


def verify_provider(root, expected):
    require(isinstance(expected, str) and HEX40.fullmatch(expected),
            "exact provider SHA required")
    p = Path(root)
    require(p.is_dir() and not p.is_symlink(), "canonical provider checkout missing")
    try:
        observed = subprocess.check_output(
            ["git", "-C", str(p), "rev-parse", "HEAD"], text=True,
            timeout=10).strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError("provider git identity unavailable") from exc
    require(observed == expected, "provider binary/source SHA mismatch")
    require((p / "kernels" / "stats_core.py").is_file()
            and (p / "kernels" / "pca_reference.py").is_file()
            and (p / "kernels" / "bradley_terry.py").is_file()
            and (p / "kernels" / "manova_reference.py").is_file(),
            "missing canonical provider kernels")
    path = str(p.resolve())
    if path not in sys.path:
        sys.path.insert(0, path)
    return observed


def evaluate(request, *, provider_root=None):
    require(isinstance(request, dict) and request.get("schema") == INPUT
            and request.get("authority_transfer") is False,
            "invalid provider request or authority")
    data_class = request.get("data_class")
    require(data_class in ("SYNTHETIC_REFERENCE", "NATIVE_UNVERIFIED"),
            "unsupported evidence class")
    plan = request.get("design")
    screen = qualify(plan)
    out = {
        "schema": OUT,
        "data_class": data_class,
        "geometry": screen["geometry"],
        "eligibility": screen["method_status"],
        "provider": "GBOGEB/gg_MATH",
        "provider_sha": None,
        "provider_executed": False,
        "methods": {x: {"status": "HOLD_UNQUALIFIED"}
                    for x in ("wilson", "pca", "bradley_terry", "anova", "manova")},
        "source_trials_independently_authenticated": None,
        "numerical_reference_is_process_inference": False,
        "formal_root_closures": None,
        "security_waiver": False, "authority_transfer": False,
        "merge_authorized": False, "qps_acceptance": "DEFER",
        "admission": "HOLD",
    }
    if data_class != "SYNTHETIC_REFERENCE":
        for item in out["methods"].values():
            item["status"] = "HOLD_NATIVE_INDEPENDENCE_NOT_ATTESTED"
        return out
    expected = request.get("provider_sha")
    require(provider_root is not None, "pinned provider checkout required")
    out["provider_sha"] = verify_provider(provider_root, expected)
    out["provider_executed"] = True
    # Import only from the verified provider tree; no copied numerical kernels.
    stats = importlib.import_module("kernels.stats_core")
    pca = importlib.import_module("kernels.pca_reference")
    bt = importlib.import_module("kernels.bradley_terry")
    data = request.get("reference_data")
    require(isinstance(data, dict), "synthetic reference data required")
    yes = "ELIGIBLE_FOR_PROVIDER_REVIEW"
    if screen["method_status"]["wilson_90"] == yes:
        bands = {str(level): stats.wilson_proportion_interval(
            plan["successes"], plan["independent_units"], level=level / 100)
            for level in (90, 95, 99)}
        out["methods"]["wilson"] = {
            "status": "SYNTHETIC_REFERENCE_ONLY",
            "confidence_bands": bands, "interval_type": "FIXED_HORIZON_WILSON",
            "independent_process_samples_proven": False,
        }
    if screen["method_status"]["pca"] == yes:
        rows = data.get("pca_rows")
        require(isinstance(rows, list)
                and len(rows) == plan["independent_units"]
                and all(isinstance(r, list)
                        and len(r) == plan["feature_count"] for r in rows),
                "PCA observations must match qualified n-by-p geometry")
        current = pca.pca_reference(rows, scale=True)
        eig = current["eigenvalues"]
        pa = pca.parallel_analysis(rows, simulations=20, percentile=0.95,
                                   seed=17, scale=True)
        stability = pca.bootstrap_loading_stability(
            rows, simulations=24, seed=17, scale=True, components=1)
        report = {
            "status": "SYNTHETIC_REFERENCE_ONLY",
            "n": current["n"], "p": current["p"],
            "eigenvalues": eig,
            "explained_variance_ratio": current["explained_variance_ratio"],
            "pc1_explained_variance_pct": round(
                100 * current["explained_variance_ratio"][0], 6),
            "eigengap_1_2": eig[0] - eig[1] if len(eig) >= 2 else None,
            "retained_candidate_count": pa["retained_candidate_count"],
            "null_thresholds": pa["null_eigenvalue_thresholds"],
            "pc1_bootstrap_congruence": stability["summary"][0],
            "bootstrap_simulations": stability["simulations"],
            "temporal_alignment": None,
        }
        if "pca_reference_rows" in data:
            previous = data["pca_reference_rows"]
            require(isinstance(previous, list)
                    and len(previous) == len(rows)
                    and all(isinstance(r, list)
                            and len(r) == plan["feature_count"] for r in previous),
                    "temporal PCA matrices must share matched dimensions")
            align = importlib.import_module("kernels.pca_alignment")
            old = pca.pca_reference(previous, scale=True)
            aligned = align.align_pca_fits(old, current)
            report["temporal_alignment"] = {
                "classification": aligned["classification"],
                "any_component_identity_ambiguous":
                    aligned["any_component_identity_ambiguous"],
                "matches": aligned["matches"],
            }
        out["methods"]["pca"] = report
    if screen["method_status"]["anova"] == yes:
        groups = data.get("anova_groups")
        require(isinstance(groups, list) and [len(x) for x in groups]
                == plan["group_sizes"], "ANOVA group replication mismatch")
        result = stats.one_way_anova(groups)
        require(math.isfinite(result["f_statistic"]),
                "undefined ANOVA F; change design instead of promoting")
        out["methods"]["anova"] = {
            "status": "SYNTHETIC_REFERENCE_ONLY",
            "f_statistic": result["f_statistic"],
            "eta_squared": result["eta_squared"],
            "df_between": result["df_between"],
            "df_within": result["df_within"],
            "p_value": None,
        }
    if screen["method_status"]["bradley_terry"] == yes:
        pairs = data.get("winner_loser_pairs")
        require(isinstance(pairs, list)
                and len(pairs) == plan["pairwise_comparisons"],
                "BT pairwise comparison denominator mismatch")
        ranked = bt.rank_pairs(pairs, iterations=160)
        if ranked["status"] != "PASS_TESTABLE_ENGINE":
            out["methods"]["bradley_terry"] = {
                "status": "HOLD_" + ranked["status"],
                "pairwise_probabilities": None,
            }
        else:
            # Full Wald uncertainty, when available, is calculated only by the
            # canonical scipy/numpy provider. No ad-hoc CI from win counts.
            extended = importlib.import_module("kernels.bt_uncertainty")
            fit = extended.fit_bradley_terry(pairs, penalty=0.0)
            if fit["status"] != "PASS":
                out["methods"]["bradley_terry"] = {
                    "status": "HOLD_NO_FINITE_MLE", "pairwise_probabilities": None}
            else:
                names = sorted(ranked["scores"])
                comparisons = []
                for i, a in enumerate(names):
                    for b in names[i+1:]:
                        comparisons.append({
                            "a": a, "b": b,
                            "intervals": {str(level): extended.pair_probability_interval(
                                fit, a, b, level=level / 100)
                                for level in (90, 95, 99)},
                        })
                out["methods"]["bradley_terry"] = {
                    "status": "SYNTHETIC_REFERENCE_ONLY",
                    "comparison_n": len(pairs),
                    "classical_mle": fit["fit_kind"],
                    "pairwise_probabilities": comparisons,
                    "model_covariance_kind": fit["covariance_kind"],
                }
    if screen["method_status"]["manova"] == yes:
        groups = data.get("manova_groups")
        require(isinstance(groups, list)
                and len(groups) == len(plan["group_sizes"])
                and all(isinstance(g, list)
                        and len(g) == plan["group_sizes"][i]
                        and all(isinstance(row, list)
                                and len(row) == plan["feature_count"]
                                for row in g) for i, g in enumerate(groups)),
                "MANOVA multivariate group n-by-p geometry mismatch")
        module = importlib.import_module("kernels.manova_reference")
        native = module.manova_reference(groups)
        out["methods"]["manova"] = {
            "status": "SYNTHETIC_REFERENCE_ONLY",
            "provider_schema": native["schema"],
            "wilks_lambda": native["wilks_lambda"],
            "pillai_trace": native["pillai_trace"],
            "p_value": native["p_value"],
            "df_between": native["df_between"],
            "df_within": native["df_within"],
            "independence_authenticated": None,
        }
    else:
        out["methods"]["manova"] = {
            "status": "HOLD_DESIGN_NOT_QUALIFIED",
            "requested_eligibility": screen["method_status"]["manova"],
            "wilks_lambda": None, "pillai_trace": None, "p_value": None,
        }
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--provider-root", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    require(args.input.is_file() and not args.input.is_symlink(),
            "untrusted/linked design input rejected")
    require(args.input.resolve() != args.out.resolve(), "input output alias")
    report = evaluate(json.loads(args.input.read_text(encoding="utf-8")),
                      provider_root=args.provider_root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, sort_keys=True, indent=2,
                                   allow_nan=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
