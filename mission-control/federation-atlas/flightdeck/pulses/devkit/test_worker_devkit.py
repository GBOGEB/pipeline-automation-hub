import copy
import importlib.util
import json
import pathlib
import tempfile
import unittest

BASE=pathlib.Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location('worker_devkit',BASE/'worker_devkit.py')
MOD=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)

class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg,cls.plan=MOD.load_config(BASE/'runner.toml',BASE/'worker_plan.json')
    def test_valid_plan_and_simulation(self):
        waves=MOD.plan_waves(self.plan)['waves']
        self.assertGreaterEqual(len(waves),3)
        self.assertEqual(6,sum(len(w['tasks']) for w in waves))
        self.assertTrue(all(w['simulation_only'] for w in waves))
    def test_zero_launch(self):
        r=MOD.plan_waves(self.plan)
        self.assertIsNone(r['actual_concurrency'])
        self.assertEqual('NOT_LAUNCHED',r['execution'])
    def test_duplicate_task_denied(self):
        d=copy.deepcopy(self.plan)
        d['tasks'].append(copy.deepcopy(d['tasks'][0]))
        with self.assertRaisesRegex(ValueError,'duplicate worker task'): MOD.validate_plan(d)
    def test_cycle_denied(self):
        d=copy.deepcopy(self.plan)
        d['tasks'][0]['depends_on']=['P3-06']
        with self.assertRaisesRegex(ValueError,'cyclic dependency'): MOD.validate_plan(d)
    def test_source_missing_sha_denied(self):
        d=copy.deepcopy(self.plan)
        d['tasks'][0]['source_sha']='HEAD'
        with self.assertRaisesRegex(ValueError,'source SHA'): MOD.validate_plan(d)
    def test_authority_denied(self):
        d=copy.deepcopy(self.plan)
        d['authority']['mutation_enabled']=True
        with self.assertRaisesRegex(ValueError,'authority inversion'): MOD.validate_plan(d)
    def test_overlap_writers_cannot_share_wave(self):
        d=copy.deepcopy(self.plan)
        w=d['tasks'][1]
        w['depends_on']=[]
        w['read_only']=False
        w['path_leases']=['devkit/']
        d['tasks'][0]['read_only']=False
        waves=MOD.plan_waves(d)['waves']
        idx={t['task_id']:wave['wave'] for wave in waves for t in wave['tasks']}
        self.assertNotEqual(idx['P3-01'],idx['P3-02'])
    def test_unknown_cli_is_not_authentication(self):
        out=MOD.inspect_environment(BASE,self.cfg)
        self.assertTrue(all(c['authenticated'] is None for c in out['agent_cli'].values()))
        self.assertFalse(out['agents_executed'])
    def test_environment_has_extension_snapshot(self):
        out=MOD.inspect_environment(BASE,self.cfg)
        self.assertGreaterEqual(out['extension_counts'].get('.py',0),1)
        self.assertIsNone(out['repo_git_head'])
    def test_output_receipt_invariants(self):
        r=MOD.build_receipt(BASE,self.cfg,self.plan)
        self.assertEqual('HOLD',r['authority']['admission'])
        self.assertEqual('STAGED_NOT_LAUNCHED',r['authority']['dispatch'])

if __name__=='__main__': unittest.main()
