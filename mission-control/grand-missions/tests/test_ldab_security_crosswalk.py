"""Regression tests for non-compensating LDAB and scanner evidence."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("crosswalk", ROOT / "validate_ldab_security_crosswalk.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
source = json.loads((ROOT / "LDAB_SECURITY_CENSUS_CROSSWALK_20261013.json").read_text())

def test_source_bound_crosswalk():
    assert mod.validate(source)["bandit_findings"] == 62

def test_forged_live_ldab_evidence_rejected():
    doc = copy.deepcopy(source)
    doc["ldab"]["container_id"] = "invented-container"
    with pytest.raises(ValueError, match="cannot claim"):
        mod.validate(doc)

def test_bandit_count_change_without_delta_rejected():
    doc = copy.deepcopy(source)
    doc["observation"]["bandit_touched_counts"]["B101"] = 60
    with pytest.raises(ValueError, match="delta discrepancy"):
        mod.validate(doc)

def test_security_self_admission_rejected():
    doc = copy.deepcopy(source)
    doc["observation"]["security_admission"] = "ACCEPT"
    with pytest.raises(ValueError, match="security admission"):
        mod.validate(doc)

def test_duplicate_finding_family_rejected():
    doc = copy.deepcopy(source)
    doc["linked_findings"].append(copy.deepcopy(doc["linked_findings"][0]))
    with pytest.raises(ValueError, match="duplicate census"):
        mod.validate(doc)
