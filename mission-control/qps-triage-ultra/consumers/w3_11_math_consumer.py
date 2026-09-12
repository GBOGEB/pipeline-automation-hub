#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--producer-root", required=True)
ap.add_argument("--producer-sha", required=True)
ap.add_argument("--consumer-sha", required=True)
ap.add_argument("--out", required=True)
a = ap.parse_args()

producer_root = Path(a.producer_root).resolve()
sys.path.insert(0, str(producer_root))
from kernels.monte_carlo_uncertainty import propagate_triangular  # noqa: E402

inputs = {
    "terms": [{"low": 1.0, "mode": 2.0, "high": 5.0, "coefficient": 3.0}],
    "samples": 20000,
    "seed": 424242,
    "offset": 10.0,
}
result = propagate_triangular(**inputs)
low, mode, high, coefficient = 1.0, 2.0, 5.0, 3.0
expected_mean = 10.0 + coefficient * ((low + mode + high) / 3.0)
triangular_variance = (
    low * low + mode * mode + high * high
    - low * mode - low * high - mode * high
) / 18.0
standard_error = math.sqrt((coefficient ** 2) * triangular_variance / inputs["samples"])
mean_error = abs(result["mean"] - expected_mean)
mean_limit = 5.0 * standard_error

failures: list[str] = []
if mean_error >= mean_limit:
    failures.append(f"mean_error={mean_error} >= five_sigma_limit={mean_limit}")
if result.get("authority_transfer") is not False:
    failures.append("producer kernel changed authority semantics")
if not (result["q05"] < result["q50"] < result["q95"]):
    failures.append("consumer quantiles are not ordered")

receipt = {
    "schema": "qps-w3-11-non-origin-consumer/v2",
    "observed_at": datetime.now(timezone.utc).isoformat(),
    "producer": {
        "repo": "GBOGEB/gg_MATH",
        "sha": a.producer_sha,
        "capability": "kernels/monte_carlo_uncertainty.py::propagate_triangular",
    },
    "consumer": {
        "repo": "GBOGEB/pipeline-automation-hub",
        "sha": a.consumer_sha,
    },
    "inputs": inputs,
    "reference": {
        "type": "closed_form_triangular_mean_and_variance",
        "expected_mean": expected_mean,
        "standard_error": standard_error,
        "five_sigma_limit": mean_limit,
        "observed_mean_error": mean_error,
    },
    "execution": {
        "steps_gt0": True,
        "outcome": "FAILURE" if failures else "SUCCESS",
        "mean": result["mean"],
        "q05": result["q05"],
        "q50": result["q50"],
        "q95": result["q95"],
        "failures": failures,
    },
    "authority_transfer": False,
    "engineering_acceptance": False,
}
out = Path(a.out)
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(receipt, sort_keys=True))
if failures:
    raise AssertionError("; ".join(failures))
