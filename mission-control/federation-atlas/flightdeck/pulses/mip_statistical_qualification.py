"""Source-independent statistical eligibility gate, not a competing math kernel.

Executable method implementations remain owned by GBOGEB/gg_MATH.
This module validates experimental geometry and routes eligible requests.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

METHODS = ("wilson_90", "wilson_95", "wilson_99", "pca", "bradley_terry",
           "anova", "manova")
SCHEMA = "code-purple.statistical-design.v1"


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def positive_int(value, minimum=1):
    return type(value) is int and value >= minimum


def qualify(plan):
    require(isinstance(plan, dict) and plan.get("schema") == SCHEMA, "invalid schema")
    require(plan.get("authority_transfer") is False, "authority transfer prohibited")
    require(plan.get("source_bound") is True, "source binding required")
    require(plan.get("cohort_matched") is True, "matched cohort required")
    n = plan.get("independent_units")
    p = plan.get("feature_count")
    require(positive_int(n, 0) and positive_int(p, 0), "invalid n/p dimensions")
    independence = plan.get("independence_verified") is True
    complete = plan.get("complete_terminal") is True
    same_scope = plan.get("same_scope") is True
    success = plan.get("successes")
    require(success is None or positive_int(success, 0) and success <= n,
            "invalid success numerator")
    groups = plan.get("group_sizes", [])
    require(isinstance(groups, list) and all(positive_int(g) for g in groups),
            "invalid group sizes")
    pairs = plan.get("pairwise_comparisons", 0)
    connected = plan.get("comparison_graph_connected") is True
    require(positive_int(pairs, 0), "invalid pairwise comparison count")
    finite_bt = plan.get("finite_bt_fit_conditions") is True
    covrank = plan.get("covariance_rank")
    require(covrank is None or positive_int(covrank, 0), "invalid covariance rank")
    same_units = plan.get("same_units") is True
    residual = plan.get("residual_diagnostics_pass") is True
    eigengap = plan.get("eigenspace_diagnostics_pass") is True
    approved_design = plan.get("sampling_design_approved") is True
    binomial = all((independence, complete, same_scope, approved_design,
                    success is not None, n >= 2))
    pca = all((independence, same_scope, same_units, eigengap,
               p >= 2, n > p, covrank is not None, covrank >= p))
    bt = all((independence, same_scope, connected, finite_bt, pairs >= 1,
              len(groups) >= 2))
    anova = all((independence, same_scope, residual, len(groups) >= 2,
                 min(groups, default=0) >= 2, sum(groups) == n))
    manova = all((anova, p >= 2, covrank is not None, covrank >= p,
                  n > (len(groups) + p)))
    ready = {"wilson_90": binomial, "wilson_95": binomial,
             "wilson_99": binomial, "pca": pca, "bradley_terry": bt,
             "anova": anova, "manova": manova}
    return {
        "schema": "code-purple.statistical-qualification.v1",
        "source_sha": plan.get("source_sha"),
        "geometry": {"n_independent": n, "p": p, "p_over_n": (
            round(p / n, 8) if n else None)},
        "method_status": {k: ("ELIGIBLE_FOR_PROVIDER_REVIEW" if ready[k]
                              else "HOLD_DESIGN_NOT_QUALIFIED") for k in METHODS},
        "numeric_intervals": {str(x): None for x in (90, 95, 99)},
        "pca_explained_variance": None,
        "bradley_terry_win_probability": None,
        "anova_effect": None,
        "manova_effect": None,
        "provider": "GBOGEB/gg_MATH",
        "provider_execution_verified": False,
        "independent_engineering_acceptance": False,
        "authority_transfer": False,
        "merge_authorized": False,
        "qps_acceptance": "DEFER",
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    require(args.input.is_file() and not args.input.is_symlink(),
            "valid plain file required")
    require(args.input.resolve() != args.out.resolve(), "input/output collision")
    require(args.input.stat().st_size <= 1_000_000, "oversized design")
    result = qualify(json.loads(args.input.read_text(encoding="utf-8")))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n",
                        encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
