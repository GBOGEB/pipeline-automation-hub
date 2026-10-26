import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "GM_DMAIC_EVOLUTION_T7_T14_T21_v1.json"
METRICS = ROOT / "gm_dmaic_evolution_metrics.py"

spec = importlib.util.spec_from_file_location("gm_dmaic_evolution_metrics", METRICS)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def load():
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


class GMDmaicEvolutionTests(unittest.TestCase):
    """unittest-collectable: CI runs `python -m unittest <path>` on Python 3.11,
    which exits 0 when zero tests are collected (bare functions are invisible)."""

    def test_cohort_nesting_and_uniqueness(self):
        doc = load()
        t7, t14, t21 = module.cohort_sets(doc)
        assert len(t7) == 7
        assert len(t14) == 14
        assert len(t21) == 21
        assert set(t7).issubset(t14)
        assert set(t14).issubset(t21)
        assert len(set(t21)) == 21

    def test_current_state_fails_closed_for_promotion(self):
        out = module.evaluate(load())
        assert out["top14_promotion_ready"] is False
        assert out["top21_promotion_ready"] is False
        assert out["fail_closed"]["proof_debt_unknown_blocks_top21"] is True
        assert out["fail_closed"]["unknown_repeat_metric_blocks_promotion"] is False  # bound to 8 (FAIL) by CPQ-013

    def test_abacus_depth_is_serialized(self):
        doc = load()
        a = doc["current"]["abacus"]
        assert a["d1"]["state"] == "CONTROL_AND_FRESH_HEAD_RECENSUS"
        assert a["d2"]["state"] == "CONTROL"
        assert a["d3"]["state"] == "CONTROL"
        assert a["i2"]["d1"]["state"] == "CONTROL_AND_FRESH_HEAD_RECENSUS"
        assert a["i2"]["d2"]["state"] == "CONTROL"

    def test_iteration_evolution_is_recursive_and_lineage_bound(self):
        doc = load()
        evo = doc["iteration_evolution"]
        assert evo["core_cycle"] == ["DEFINE", "MEASURE", "ANALYZE", "IMPROVE", "CONTROL"]
        assert evo["iteration_chain_integrity"] is True
        assert evo["current_level"] == "E2_RECURSIVE"
        assert evo["complete_iteration_count"] == 2
        assert evo["recursive_control_handoff_count"] == 2
        assert evo["completed_iterations"][0]["iteration_id"] == "ABACUS-I1-FIRST3"
        assert evo["completed_iterations"][0]["bounded_control_outcome"] == "CONTROLLED_WITH_RESIDUALS"
        assert evo["completed_iterations"][1]["iteration_id"] == "ABACUS-I2-RESIDUALS"
        assert evo["active_iteration"]["iteration_id"] == "ABACUS-I3-PY310"
        assert evo["active_iteration"]["input_control_receipt"]["iteration_id"] == "ABACUS-I2-RESIDUALS"
        assert evo["active_iteration"]["control_outcome"] == "POSTMERGE_GREEN_REPEAT_PENDING_CONTRACT_REVIEW"

    def test_noncompensation_guards_present(self):
        doc = load()
        guards = set(doc["noncompensation"])
        assert "ZERO_STEP_NE_APPLICATION_FAIL" in guards
        assert "PENDING_NE_GREEN" in guards
        assert "MERGE_NE_PROOF" in guards
        assert "RAW_FAILURE_REDUCTION_NE_DMAIC_MATURITY" in guards


if __name__ == "__main__":
    unittest.main()
