import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "GM_DAB_FLAKE8_PROPAGATION_T7_T14_T21_v1.json"


def load():
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def cohorts(doc):
    t7 = list(doc["cohorts"]["top7"])
    t14 = t7 + list(doc["cohorts"]["top14_extension"])
    t21 = t14 + list(doc["cohorts"]["top21_extension"])
    return t7, t14, t21


def test_cohort_sizes_nesting_and_uniqueness():
    doc = load()
    t7, t14, t21 = cohorts(doc)
    assert len(t7) == 7
    assert len(t14) == 14
    assert len(t21) == 21
    assert set(t7).issubset(t14)
    assert set(t14).issubset(t21)
    assert len(set(t21)) == 21


def test_breadth_modes_fail_closed():
    doc = load()
    breadth = doc["breadth_control"]
    assert breadth["top7"]["mode"] == "ACTIVE_CENSUS_AND_REPAIR"
    assert breadth["top7"]["repair_admission"] is True
    assert breadth["top14"]["mode"] == "SHADOW_MEASURE_AND_CLASSIFY"
    assert breadth["top14"]["repair_admission"] is False
    assert breadth["top21"]["mode"] == "HOLD_TELEMETRY_ONLY"
    assert breadth["top21"]["repair_admission"] is False


def test_abacus_seed_is_exact_yield_and_hard_lane_stays_bounded():
    doc = load()
    mech = doc["seed_evidence"]["mechanical"]
    hard = doc["seed_evidence"]["hard"]
    assert mech["pre_total"] - mech["post_total"] == 394
    assert mech["pre_w293"] - mech["post_w293"] == 394
    assert mech["result"] == "PASS_EXACT_YIELD"
    assert hard["reconstructable_repairs"] == 5
    assert hard["postmerge_exact_census"] == "PENDING_BIND"
    assert doc["operating_model"]["dab_hard"]["bulk_semantic_autofix"] is False


def test_noncompensation_blocks_breadth_credit_leakage():
    doc = load()
    guards = set(doc["noncompensation"])
    assert "DAB_CENSUS_NE_COHORT_PROMOTION" in guards
    assert "TOP14_SHADOW_NE_REPAIR_ADMISSION" in guards
    assert "TOP21_TELEMETRY_NE_REPAIR_ADMISSION" in guards
    assert doc["authority_transfer"] is False
    assert doc["formal_credit_delta"] == 0
    assert doc["engineering_credit_delta"] == 0
