import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "GM_DMAIC_EVOLUTION_T7_T14_T21_v1.json"
METRICS = ROOT / "gm_dmaic_evolution_metrics.py"

spec = importlib.util.spec_from_file_location("gm_dmaic_evolution_metrics", METRICS)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def load():
    return json.loads(CONTRACT.read_text(encoding="utf-8"))

def test_cohort_nesting_and_uniqueness():
    doc = load()
    t7, t14, t21 = module.cohort_sets(doc)
    assert len(t7) == 7
    assert len(t14) == 14
    assert len(t21) == 21
    assert set(t7).issubset(t14)
    assert set(t14).issubset(t21)
    assert len(set(t21)) == 21

def test_current_state_fails_closed_for_promotion():
    out = module.evaluate(load())
    assert out["top14_promotion_ready"] is False
    assert out["top21_promotion_ready"] is False
    assert out["fail_closed"]["proof_debt_unknown_blocks_top21"] is True

def test_abacus_depth_is_serialized():
    doc = load()
    a = doc["current"]["abacus"]
    assert a["d1"]["state"] == "ROOT_CLEARED_NEXT_RED_EXPOSED"
    assert a["d2"]["state"] == "PATCHED_WAIT_EXACT_HEAD_PROOF"
    assert a["d3"]["state"] == "HELD_UNTIL_D2_CONTROL"

def test_noncompensation_guards_present():
    doc = load()
    guards = set(doc["noncompensation"])
    assert "ZERO_STEP_NE_APPLICATION_FAIL" in guards
    assert "PENDING_NE_GREEN" in guards
    assert "MERGE_NE_PROOF" in guards
    assert "RAW_FAILURE_REDUCTION_NE_DMAIC_MATURITY" in guards
