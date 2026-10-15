"""G5 fail-closed census, process methods, DAG and scalability regressions."""
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
import federation as f
SAMPLES=HERE/'samples'

class FederationContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g0=json.loads((SAMPLES/'fleet_g0.json').read_text())
        cls.g1=json.loads((SAMPLES/'fleet_g1_snapshot.json').read_text())
        cls.doc=json.loads((SAMPLES/'federation_g5.json').read_text())

    def sample(self):
        return copy.deepcopy(self.doc)

    def test_positive_sample(self):
        f.validate(self.doc)

    def test_fixed_breadth_and_full_unknown_count(self):
        r=f.calculate(self.g0,self.g1,self.doc)
        self.assertEqual((r['population']['target_cells'],r['population']['G0_observed'],r['population']['G1_observed'],r['population']['G1_unobserved']),(42,1,6,36))
        self.assertEqual(r['population']['breadth_delta_pp'],11.9048)
        self.assertIsNone(r['depth']['pca_fit_evidence'])

    def test_typed_dag_has_no_fabricated_links(self):
        r=f.calculate(self.g0,self.g1,self.doc)
        self.assertEqual(r['depth']['declared_edges'],13)
        self.assertEqual(r['depth']['native_executed_edges'],0)
        self.assertEqual(r['depth']['recipient_accepted_edges'],0)
        self.assertEqual(r['qps_disposition'],'DEFER')

    def test_disjointed_scout_first_six_repos(self):
        r=f.calculate(self.g0,self.g1,self.doc)
        self.assertEqual(r['fan_out']['packets_staged'],6)
        self.assertEqual(len({p['repository'] for p in r['fan_out']['packets']}),6)
        self.assertEqual(r['fan_out']['still_unplanned'],30)
        self.assertFalse(any(p['dispatch_authorized'] or p['mutation_paths'] for p in r['fan_out']['packets']))

    def test_reject_implicit_authority(self):
        for fld in ('authority_transfer','dispatch_authorized','merge_authorized','security_waiver'):
            with self.subTest(field=fld):
                d=self.sample();d[fld]=True
                with self.assertRaises(ValueError):f.validate(d)
        d=self.sample();d['qps_disposition']='ACCEPT'
        with self.assertRaises(ValueError):f.validate(d)

    def test_reject_historical_source_forgery(self):
        d=self.sample();d['nodes'][0]['source_sha']='a'*40
        with self.assertRaisesRegex(ValueError,'node source'):f.validate(d)

    def test_reject_pr_claim_current(self):
        d=self.sample();d['pr_observations'][0]['observed_head_is_current']=True
        with self.assertRaises(ValueError):f.validate(d)

    def test_reject_rex_self_acceptance(self):
        d=self.sample();d['pr_observations'][0]['accepted_rex_return']=True
        with self.assertRaises(ValueError):f.validate(d)

    def test_reject_qps_self_acceptance(self):
        d=self.sample();d['pr_observations'][0]['qps_accepted']=True
        with self.assertRaises(ValueError):f.validate(d)

    def test_reject_fake_native_edge(self):
        d=self.sample();d['edges'][0]['level']='CONSUMER_NATIVE'
        with self.assertRaisesRegex(ValueError,'real receipt'):f.validate(d)

    def test_reject_fake_qps_relay(self):
        d=self.sample();d['edges'][0]['level']='RECIPIENT_ACCEPTED';d['edges'][0]['receipt']={'sha256':'hash','run_id':123}
        with self.assertRaisesRegex(ValueError,'QPS owner'):f.validate(d)

    def test_reject_declaration_with_fake_receipt(self):
        d=self.sample();d['edges'][0]['receipt']={'url':'synthetic'}
        with self.assertRaises(ValueError):f.validate(d)

    def test_reject_cycle(self):
        d=self.sample();d['edges'].append({'source':'qps_triage','target':'hub_mission','level':'DECLARED','receipt':None})
        with self.assertRaisesRegex(ValueError,'DAG cycle'):f.validate(d)

    def test_reject_repeated_edge(self):
        d=self.sample();d['edges'].append(copy.deepcopy(d['edges'][0]))
        with self.assertRaisesRegex(ValueError,'duplicate federation edge'):f.validate(d)

    def test_reject_unknown_node(self):
        d=self.sample();d['edges'][0]['target']='ghost'
        with self.assertRaises(ValueError):f.validate(d)

    def test_reject_pr_burndown_mismatch(self):
        d=self.sample();d['pr_observations'][0]['workflow_conclusions']['success']+=1
        with self.assertRaisesRegex(ValueError,'do not reconcile'):f.validate(d)

    def test_reject_branch_sha_mismatch(self):
        d=self.sample();d['repos'][0]['catalog_sha']='f'*40
        with self.assertRaisesRegex(ValueError,'node source'):f.calculate(self.g0,self.g1,d)

    def test_reject_scope_population_drift(self):
        d=self.sample();d['repos'][0]['target_families'].pop()
        with self.assertRaises(ValueError):f.validate(d)

    def test_reject_g0_overwrite(self):
        g1=copy.deepcopy(self.g1);g1['observations'][0]['job_id']+=1
        with self.assertRaisesRegex(ValueError,'historical G0'):f.calculate(self.g0,g1,self.doc)

    def test_reject_unsafe_parallelism(self):
        for bad in (0,17,False,1.5):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):f.calculate(self.g0,self.g1,self.doc,max_parallel=bad)

    def test_restrict_packet_budget(self):
        r=f.calculate(self.g0,self.g1,self.doc,max_parallel=2,max_packets=3)
        self.assertEqual(r['fan_out']['packets_staged'],3)
        self.assertEqual(r['fan_out']['still_unplanned'],33)

    def test_emit_deterministic_and_digest(self):
        r=f.calculate(self.g0,self.g1,self.doc)
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)
            a=f.emit(r,out);b=f.emit(r,out)
            self.assertEqual(a,b)
            self.assertEqual(a,hashlib.sha256((out/'federation_census.json').read_bytes()).hexdigest())
            self.assertIn('GOGREEN G5',(out/'federation_pulse.md').read_text())

    def test_cli_real_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=[sys.executable,str(HERE/'federation.py'),'--g0',str(SAMPLES/'fleet_g0.json'),'--g1',str(SAMPLES/'fleet_g1_snapshot.json'),'--snapshot',str(SAMPLES/'federation_g5.json'),'--out',tmp]
            res=subprocess.run(p,check=True,text=True,capture_output=True,timeout=10)
            self.assertEqual(json.loads(res.stdout)['packets_staged'],6)

    def test_n_plus_two_not_calibrated(self):
        r=f.calculate(self.g0,self.g1,self.doc)
        self.assertEqual(len(r['n_plus_2']),2)
        self.assertTrue(all(p['probability'] is None for p in r['n_plus_2']))
        self.assertEqual(r['methods']['3PSTAR'],'CANDIDATE_ONLY_NO_STATISTICAL_TRIAL')

    def test_merged_pr_cannot_be_trusted_replay(self):
        r=f.calculate(self.g0,self.g1,self.doc)
        self.assertTrue(any(p['status']=='MERGED' for p in r['wave_states']['current_pr_snapshots']))
        self.assertEqual(r['depth']['consumer_native_edges'],0)

if __name__ == '__main__':unittest.main()
