import copy,importlib.util,json,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
S=importlib.util.spec_from_file_location('worker_viewer',HERE/'worker_viewer.py')
MOD=importlib.util.module_from_spec(S);S.loader.exec_module(MOD)

class ViewerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan=json.loads((HERE/'worker_plan.json').read_text())
        cls.obs=json.loads((HERE/'OBSERVED_P3_20261016.json').read_text())
    def test_source_bound(self):
        MOD.validate(self.plan,self.obs)
        self.assertEqual(5,len(self.obs['prs']))
    def test_generation_sealed(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=MOD.build(HERE/'worker_plan.json',HERE/'OBSERVED_P3_20261016.json',tmp)
            b=MOD.build(HERE/'worker_plan.json',HERE/'OBSERVED_P3_20261016.json',tmp)
            self.assertEqual(a,b)
            self.assertIn('Actual Crew/REX UNKNOWN',(Path(tmp)/'index.html').read_text())
    def test_refuse_security_waiver(self):
        d=copy.deepcopy(self.obs);d['authority']['security_waiver']=True
        with self.assertRaises(ValueError):MOD.validate(self.plan,d)
    def test_refuse_forged_root(self):
        d=copy.deepcopy(self.obs);d['authority']['root_closed']=0
        with self.assertRaises(ValueError):MOD.validate(self.plan,d)
    def test_refuse_bad_head(self):
        d=copy.deepcopy(self.obs);d['prs'][0]['head_sha']='main'
        with self.assertRaises(ValueError):MOD.validate(self.plan,d)
    def test_refuse_negative_count(self):
        d=copy.deepcopy(self.obs);d['prs'][0]['success']=-1
        with self.assertRaises(ValueError):MOD.validate(self.plan,d)
    def test_refuse_duplicate_pr(self):
        d=copy.deepcopy(self.obs);d['prs'].append(copy.deepcopy(d['prs'][0]))
        with self.assertRaises(ValueError):MOD.validate(self.plan,d)

if __name__=='__main__':unittest.main()
