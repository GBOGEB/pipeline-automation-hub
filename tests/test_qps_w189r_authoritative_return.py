import json, subprocess, sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
C=ROOT/'controls/QPS_W189_FEDERATION_SAMPLE4_CURRENT_v1.json'
M=ROOT/'triage/w189/QPS_W189_CROSS_SURFACE_FEATURE_MATRIX_v0.1.json'
R=ROOT/'triage/w189/QPS_W189_FEDERATION_EXPANSION_RUNTIME_CONTROL_v0.1.json'
class T(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.c=json.loads(C.read_text()); cls.m=json.loads(M.read_text()); cls.r=json.loads(R.read_text())
 def test_accept(self):
  self.assertEqual(self.c['measurement']['depth']['value'],1.0); self.assertEqual(self.c['measurement']['penetration'],1.0); self.assertEqual(sum(x['accepted_sample'] for x in self.m['rows']),4)
 def test_pca_partial_stability(self):
  s=self.m['measured_n4_stability']; self.assertGreater(s['pc1_loading_congruence_abs'],.99); self.assertLess(s['pc2_loading_congruence_abs'],.20)
 def test_bt_withheld(self):
  self.assertEqual(self.r['bt']['transport_unregularized_mle'],'NO_FINITE_MLE'); self.assertTrue(self.r['bt']['global_state'].startswith('WITHHELD_'))
 def test_fleet_null(self): self.assertIsNone(self.r['fleet_census']['mission_relevant_governed_surface_denominator'])
 def test_child_not_promoted(self): self.assertFalse(self.r['child_guard']['visual_n200_control_promotion'])
 def test_native_noncompensating(self): self.assertEqual(self.c['native_missioncontrol_runtime']['recorded_steps'],0); self.assertFalse(self.c['native_missioncontrol_runtime']['compensated'])
 def test_validator(self):
  p=subprocess.run([sys.executable,str(ROOT/'scripts/qps_w189r_validate_authoritative_return.py')],cwd=ROOT,capture_output=True,text=True); self.assertEqual(p.returncode,0,p.stdout+p.stderr)
if __name__=='__main__': unittest.main()
