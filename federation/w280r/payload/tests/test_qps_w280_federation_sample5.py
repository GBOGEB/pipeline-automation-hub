#!/usr/bin/env python3
import importlib.util, json, pathlib, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts/qps_w280_validate_federation_sample5.py"
spec=importlib.util.spec_from_file_location("w280r_validator",SCRIPT)
mod=importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(mod)

class W280RTests(unittest.TestCase):
    def test_return_passes(self):
        r=mod.validate()
        self.assertEqual(r["result"],"PASS_AUTHORITATIVE_RETURN_PAYLOAD")
        self.assertTrue(r["sample5_accepted"])
        self.assertEqual(r["accepted_bounded_samples"],5)
        self.assertEqual(r["depth"],1.0)
        self.assertEqual(r["penetration"],1.0)
    def test_global_bt_stays_withheld(self):
        b=json.loads(mod.BT.read_text())
        self.assertFalse(b["repair_component"]["finite_unregularized_mle"])
        self.assertTrue(b["separate_allocation_component"]["finite_two_node_unregularized_mle"])
        self.assertFalse(b["separate_allocation_component"]["bridge_to_repair_component"])
        self.assertEqual(b["global_state"],"WITHHELD_DISCONNECTED_HETEROGENEOUS_COMPARISON_GRAPH")
    def test_surface_denominator_is_deduped_not_repo_count(self):
        f=json.loads(mod.CENSUS.read_text())
        self.assertEqual(f["accessible_repository_universe_total"],83)
        self.assertEqual(f["denominator"]["governed_surface_denominator"],12)
        credited=[x for x in f["rows"] if x["denominator_credit"]==1]
        self.assertEqual(len({x["surface"] for x in credited}),12)
        self.assertIsNone(f["global_fleet_penetration"])
    def test_923_not_compensated(self):
        r=json.loads(mod.RUNTIME.read_text())
        self.assertEqual(r["native_source_runtime"]["state"],"WITHHELD_INFRA_PREEXECUTION_REX_006")
        self.assertFalse(r["native_source_runtime"]["compensated"])

if __name__=="__main__": unittest.main()
