"""Behavioural tests for mission-control/qps-triage-ultra/consumers/w3_11_math_consumer.py.

The module is a script: it parses argv, imports the producer kernel from --producer-root and
writes its receipt at import time. Each test builds a fake producer kernel in tmp_path.
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TARGET = REPO_ROOT / "mission-control" / "qps-triage-ultra" / "consumers" / "w3_11_math_consumer.py"

# Closed-form reference used by the consumer: offset + coefficient * (low + mode + high) / 3.
EXPECTED_MEAN = 10.0 + 3.0 * (1.0 + 2.0 + 5.0) / 3.0
STANDARD_ERROR = math.sqrt(9.0 * ((1 + 4 + 25 - 2 - 5 - 10) / 18.0) / 20000)


def _kernel(tmp_path, result: dict) -> Path:
    root = tmp_path / "producer"
    pkg = root / "kernels"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "monte_carlo_uncertainty.py").write_text(
        "CALLS = []\n"
        "def propagate_triangular(**kwargs):\n"
        "    CALLS.append(kwargs)\n"
        f"    return {result!r}\n",
        encoding="utf-8",
    )
    return root


def _run(monkeypatch, tmp_path, result: dict):
    root = _kernel(tmp_path, result)
    out = tmp_path / "nested" / "receipt.json"
    monkeypatch.setattr(sys, "argv", ["consumer", "--producer-root", str(root), "--producer-sha", "p" * 40,
                                      "--consumer-sha", "c" * 40, "--out", str(out)])
    monkeypatch.setattr(sys, "path", list(sys.path))
    for name in ("kernels", "kernels.monte_carlo_uncertainty"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    spec = importlib.util.spec_from_file_location("cw_w3_11_math_consumer", TARGET)
    module = importlib.util.module_from_spec(spec)
    error = None
    try:
        spec.loader.exec_module(module)
    except AssertionError as exc:
        error = exc
    kernel_calls = sys.modules["kernels.monte_carlo_uncertainty"].CALLS
    for name in ("kernels", "kernels.monte_carlo_uncertainty"):
        sys.modules.pop(name, None)
    receipt = json.loads(out.read_text(encoding="utf-8"))
    return receipt, error, kernel_calls, root


GOOD = {"mean": EXPECTED_MEAN + 0.001, "q05": 13.0, "q50": 17.5, "q95": 23.0, "authority_transfer": False}


def test_success_receipt(monkeypatch, tmp_path, capsys):
    receipt, error, calls, root = _run(monkeypatch, tmp_path, GOOD)
    assert error is None
    assert calls == [{"terms": [{"low": 1.0, "mode": 2.0, "high": 5.0, "coefficient": 3.0}],
                      "samples": 20000, "seed": 424242, "offset": 10.0}]
    assert sys.path[0] == str(root.resolve())
    assert receipt["schema"] == "qps-w3-11-non-origin-consumer/v2"
    assert receipt["producer"]["sha"] == "p" * 40
    assert receipt["consumer"] == {"repo": "GBOGEB/pipeline-automation-hub", "sha": "c" * 40}
    ref = receipt["reference"]
    assert ref["expected_mean"] == pytest.approx(18.0)
    assert ref["standard_error"] == pytest.approx(STANDARD_ERROR)
    assert ref["five_sigma_limit"] == pytest.approx(5 * STANDARD_ERROR)
    assert ref["observed_mean_error"] == pytest.approx(0.001)
    assert receipt["execution"]["outcome"] == "SUCCESS"
    assert receipt["execution"]["failures"] == []
    assert receipt["authority_transfer"] is False and receipt["engineering_acceptance"] is False
    assert json.loads(capsys.readouterr().out) == receipt


def test_mean_outside_five_sigma_fails(monkeypatch, tmp_path):
    bad = dict(GOOD, mean=EXPECTED_MEAN + 1.0)
    receipt, error, _, _ = _run(monkeypatch, tmp_path, bad)
    assert isinstance(error, AssertionError)
    assert "five_sigma_limit" in str(error)
    assert receipt["execution"]["outcome"] == "FAILURE"
    assert len(receipt["execution"]["failures"]) == 1


def test_authority_and_quantile_failures_are_all_reported(monkeypatch, tmp_path):
    bad = dict(GOOD, q05=20.0, q50=17.5)
    bad.pop("authority_transfer")
    receipt, error, _, _ = _run(monkeypatch, tmp_path, bad)
    failures = receipt["execution"]["failures"]
    assert failures == ["producer kernel changed authority semantics", "consumer quantiles are not ordered"]
    assert str(error) == "; ".join(failures)
    assert receipt["execution"]["outcome"] == "FAILURE"


def test_equal_quantiles_count_as_unordered(monkeypatch, tmp_path):
    receipt, error, _, _ = _run(monkeypatch, tmp_path, dict(GOOD, q95=17.5))
    assert receipt["execution"]["failures"] == ["consumer quantiles are not ordered"]
    assert error is not None
