import copy, importlib.util, json, pathlib, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"validate_r3_dmaic_premerge.py"
CONTRACT=ROOT/"R3_DMAIC_PREMERGE_CONTRACT_v1.json"
spec=importlib.util.spec_from_file_location("v",SCRIPT)
v=importlib.util.module_from_spec(spec); spec.loader.exec_module(v)

class TestPremerge(unittest.TestCase):
    def setUp(self): self.doc=json.loads(CONTRACT.read_text())

    def test_clean_contract(self):
        self.assertEqual(v.validate(self.doc),[])
        receipt=v.proof(self.doc)
        self.assertEqual(receipt["kpi"]["synthetic_fault_detection_rate"],1.0)
        self.assertEqual(receipt["kpi"]["false_accept_count"],0)

    def test_all_observed_faults_detected(self):
        for fault in v.FAULTS:
            with self.subTest(fault=fault):
                self.assertIn(fault,v.validate(v.inject(self.doc,fault)))

    def test_r4_overclaim_detected(self):
        d=copy.deepcopy(self.doc); d["canonical"]["gates"]["r4"]="PASS"
        self.assertIn("GATE_OR_AUTHORITY_OVERCLAIM",v.validate(d))

if __name__=="__main__": unittest.main()
