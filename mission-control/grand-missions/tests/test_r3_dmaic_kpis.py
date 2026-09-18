import copy, importlib.util, json, pathlib, unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"measure_r3_dmaic_kpis.py"
CONTRACT=ROOT/"R3_DMAIC_KPI_CONTRACT_v1.json"
spec=importlib.util.spec_from_file_location("kpi",SCRIPT)
kpi=importlib.util.module_from_spec(spec); spec.loader.exec_module(kpi)

class TestR3DMAICKPI(unittest.TestCase):
    def setUp(self):
        self.doc=json.loads(CONTRACT.read_text())

    def test_exact_metrics(self):
        got=kpi.validate(self.doc)
        self.assertEqual(set(got),set(self.doc["expected_kpis"]))
        self.assertEqual(got["pr_count"],8)
        self.assertEqual(got["mean_merge_lead_seconds"],210)
        self.assertEqual(got["median_merge_lead_seconds"],169)
        self.assertEqual(got["historical_first_pass_closure_rate"],0.25)
        self.assertEqual(got["repair_closure_yield"],1.0)
        self.assertEqual(got["physical_prerequisite_reduction_fraction"],0.5)

    def test_gate_overclaim_rejected(self):
        d=copy.deepcopy(self.doc); d["guards"]["r4"]="PASS"
        with self.assertRaises(SystemExit): kpi.validate(d)

    def test_metric_drift_rejected(self):
        d=copy.deepcopy(self.doc); d["population"]["prs"][0]["merge_lead_seconds"]=204
        with self.assertRaises(SystemExit): kpi.validate(d)

    def test_missing_expected_kpi_rejected(self):
        d=copy.deepcopy(self.doc); d["expected_kpis"].pop("current_successor_binding_delta")
        with self.assertRaises(SystemExit): kpi.validate(d)

    def test_non_boolean_closed_rejected(self):
        d=copy.deepcopy(self.doc); d["observed_defect_classes"][0]["closed"]="false"
        with self.assertRaises(SystemExit): kpi.validate(d)

if __name__=="__main__":
    unittest.main()
