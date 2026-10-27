"""Source-matched G0/G1/G2 pulse QA; source history is append-only."""
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import incremental as mod

class IncrementalContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs=[json.loads((ROOT/'samples'/n).read_text(encoding="utf-8")) for n in ('fleet_g0.json','fleet_g1_snapshot.json','fleet_g2_snapshot.json')]

    def docs_copy(self):return copy.deepcopy(self.docs)

    def test_legal_increment(self):
        r=mod.analyze(*self.docs)
        self.assertEqual([p['observed_cells'] for p in r['pulses']],[1,6,8])
        self.assertEqual(r['pulses'][2]['new_cells'],2)
        self.assertEqual(r['pulses'][2]['unobserved_cells'],34)

    def test_coverage_security_only_status(self):
        r=mod.analyze(*self.docs)
        self.assertEqual(r['increment']['families'],['coverage','security'])
        self.assertIsNone(r['increment']['coverage_numerator'])
        self.assertIsNone(r['increment']['matched_security_fingerprint_change'])

    def test_no_new_root_credit(self):
        r=mod.analyze(*self.docs)
        self.assertIsNone(r['increment']['verified_roots_closed'])
        self.assertFalse(r['authority_transfer'] or r['dispatch_authorized'] or r['merge_authorized'])

    def test_reject_modified_g0(self):
        x=self.docs_copy();x[1]['observations'][0]['job_id']+=1
        with self.assertRaises(ValueError):mod.analyze(*x)

    def test_reject_modified_g1(self):
        x=self.docs_copy();x[2]['observations'][1]['job_id']+=1
        with self.assertRaises(ValueError):mod.analyze(*x)

    def test_reject_taxonomy_change(self):
        x=self.docs_copy();x[2]['repositories'][0]['target_families'].pop()
        with self.assertRaises(ValueError):mod.analyze(*x)

    def test_reject_promoted_test_counts(self):
        x=self.docs_copy();x[2]['observations'][-1]['test_counts']={'executed':1,'passed':1,'failed':0,'skipped':0}
        with self.assertRaises(ValueError):mod.analyze(*x)

    def test_reject_forged_byte_proof(self):
        x=self.docs_copy();x[2]['observations'][-1]['artifact']={'id':1,'archive_sha256':'a'*64,'bytes_verified':True}
        with self.assertRaises(ValueError):mod.analyze(*x)

    def test_reject_failed_native_job(self):
        x=self.docs_copy();x[2]['observations'][-1]['job_conclusion']='failure'
        with self.assertRaises(ValueError):mod.analyze(*x)

    def test_reject_unsupported_family(self):
        x=self.docs_copy();x[2]['observations'][-1]['family']='federation'
        with self.assertRaises(ValueError):mod.analyze(*x)

    def test_reject_duplicate_observation(self):
        x=self.docs_copy();x[2]['observations'].append(copy.deepcopy(x[2]['observations'][-1]))
        with self.assertRaises(ValueError):mod.analyze(*x)

    def test_manifest_digest_repeatable(self):
        with tempfile.TemporaryDirectory() as d:
            r=mod.analyze(*self.docs)
            a=mod.emit(r,Path(d));b=mod.emit(r,Path(d))
            self.assertEqual(a,b)
            self.assertEqual(a,hashlib.sha256((Path(d)/'incremental_pulses.json').read_bytes()).hexdigest())

    def test_no_inferred_pca_bt(self):
        r=mod.analyze(*self.docs)
        self.assertFalse(r['pca_ready'] or r['3pstar_ready'])
        self.assertIsNone(r['prediction']['calibrated_probability'])

if __name__=='__main__':unittest.main()
