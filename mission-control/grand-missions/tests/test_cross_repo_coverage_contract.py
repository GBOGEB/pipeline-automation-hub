"""Regression tests for common cohort evidence interpretation."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
TARGET = HERE / "validate_cross_repo_coverage.py"
spec = importlib.util.spec_from_file_location("cohort_validation", TARGET)
validation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validation)
SOURCE = json.loads((HERE / "CROSS_REPO_COVERAGE_ROLLUP_20261013.json").read_text())

def test_pinned_native_receipts_validate():
    assert validation.validate(SOURCE) == {
        "schema": "missioncontrol.cross_repo_coverage_validation.v1",
        "repositories": 3, "measured": 3, "unknown": 0, "authority_transfer": False,
    }

def test_partial_denominator_is_not_zero():
    bad = copy.deepcopy(SOURCE)
    bad["observations"][2]["status"] = "INCOMPLETE_INSTRUMENTATION"
    bad["observations"][2]["missing_source_files"] = ["tests/missing.py"]
    bad["observations"][2]["percent"] = 0.0
    with pytest.raises(ValueError, match="incomplete instrumentation"):
        validation.validate(bad)

def test_true_zero_with_complete_denominator_is_measured():
    good = copy.deepcopy(SOURCE)
    row = good["observations"][0]
    row["covered_lines"] = 0
    row["percent"] = 0.0
    assert validation.validate(good)["measured"] == 3

def test_duplicate_repo_fails():
    bad = copy.deepcopy(SOURCE)
    bad["observations"].append(copy.deepcopy(bad["observations"][0]))
    with pytest.raises(ValueError, match="duplicate repository"):
        validation.validate(bad)

def test_inflated_covered_count_fails():
    bad = copy.deepcopy(SOURCE)
    bad["observations"][0]["covered_lines"] = 177
    with pytest.raises(ValueError, match="numerator/denominator"):
        validation.validate(bad)

def test_drifted_percentage_fails():
    bad = copy.deepcopy(SOURCE)
    bad["observations"][1]["percent"] = 100.0
    with pytest.raises(ValueError, match="percentage inconsistent"):
        validation.validate(bad)

def test_incomplete_missing_list_cannot_be_empty():
    bad = copy.deepcopy(SOURCE)
    bad["observations"][2]["status"] = "INCOMPLETE_INSTRUMENTATION"
    bad["observations"][2]["percent"] = None
    bad["observations"][2]["missing_source_files"] = []
    with pytest.raises(ValueError, match="incomplete instrumentation"):
        validation.validate(bad)

def test_security_clearance_without_protection_rejected():
    bad = copy.deepcopy(SOURCE)
    bad["observations"][0]["security_clearance"] = True
    with pytest.raises(ValueError, match="branch protection"):
        validation.validate(bad)

def test_invalid_hash_fails():
    bad = copy.deepcopy(SOURCE)
    bad["observations"][1]["artifact_sha256"] = "0" * 63
    with pytest.raises(ValueError, match="artifact hash"):
        validation.validate(bad)

def test_no_authority_transfer():
    bad = copy.deepcopy(SOURCE)
    bad["authority_transfer"] = True
    with pytest.raises(ValueError, match="authority"):
        validation.validate(bad)
