"""Depth-first negative coverage: reject bad semantics, inputs and non-comparable pulses."""
import contextlib
import copy
import io
import json
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
import federation, incremental
SAMPLES=HERE/'samples'

class DeepNegative(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc=json.loads((SAMPLES/'federation_g5.json').read_text())
        cls.g0=json.loads((SAMPLES/'fleet_g0.json').read_text())
        cls.g1=json.loads((SAMPLES/'fleet_g1_snapshot.json').read_text())
        cls.g2=json.loads((SAMPLES/'fleet_g2_snapshot.json').read_text())

    def test_validation_invalid_inputs_matrix(self):
        transforms=[
            lambda d: d.update(schema='wrong'),
            lambda d: d.update(snapshot_at=None),
            lambda d: d.update(snapshot_at='2026-10-15T09:00:00'),
            lambda d: d.update(repos=[]),
            lambda d: d['repos'].__setitem__(0,None),
            lambda d: d['repos'][0].update(repository=d['repos'][1]['repository']),
            lambda d: d['repos'][0].update(catalog_sha='bad'),
            lambda d: d['repos'][0].update(target_families=None),
            lambda d: d['repos'][0].update(source_kind='UNTRUSTED'),
            lambda d: d.update(pr_observations=None),
            lambda d: d['pr_observations'][0].update(repository='GBOGEB/UNKNOWN'),
            lambda d: d['pr_observations'][0].update(status='MYSTERY'),
            lambda d: d['pr_observations'][0].update(head_sha='bad'),
            lambda d: d['pr_observations'].append(copy.deepcopy(d['pr_observations'][0])),
            lambda d: d['pr_observations'][0].update(workflow_sample_size=True),
            lambda d: d['pr_observations'][0].update(workflow_conclusions={'success':2}),
            lambda d: d.update(nodes=[]),
            lambda d: d['nodes'][0].update(id='bad id'),
            lambda d: d['nodes'][0].update(role='UNKNOWN'),
            lambda d: d['edges'][0].update(level='FAKE_NATIVE'),
        ]
        for i, mutate in enumerate(transforms):
            with self.subTest(i=i):
                doc=copy.deepcopy(self.doc)
                mutate(doc)
                with self.assertRaises((ValueError,TypeError)):
                    federation.validate(doc)

    def test_native_edges_cannot_be_self_verified_with_string_sha(self):
        for level in ('PRODUCER_NATIVE','CONSUMER_NATIVE','RECIPIENT_ACCEPTED'):
            d=copy.deepcopy(self.doc)
            d['edges'][0].update(level=level,receipt={'sha256':'a'*64,'run_id':1})
            with self.subTest(level=level):
                with self.assertRaises(ValueError): federation.validate(d)

    def test_bad_census_input_matrix(self):
        for kind in ('typed','taxonomy','overflow','scope','historical'):
            g0,g1,g2=copy.deepcopy((self.g0,self.g1,self.g2))
            if kind=='typed': g2=None
            elif kind=='taxonomy': g1['repositories'][0]['head_sha']='f'*40
            elif kind=='overflow': g2['observations'].append(g2['observations'][-1].copy())
            elif kind=='scope': g2['observations'][-1]['family']='runtime'
            elif kind=='historical': g2['observations'][0]['suite_id']='forged'
            with self.subTest(kind=kind):
                with self.assertRaises(ValueError): incremental.analyze(g0,g1,g2)

    def test_refuse_unsupported_dispatch_parameters(self):
        for key in ('max_parallel','max_packets','per_repo'):
            with self.subTest(key=key):
                with self.assertRaises(ValueError): federation.calculate(self.g0,self.g1,self.doc,**{key:0})

    def test_federation_cli_covered(self):
        with tempfile.TemporaryDirectory() as tmp:
            args=[str(HERE/'federation.py'),'--g0',str(SAMPLES/'fleet_g0.json'),'--g1',str(SAMPLES/'fleet_g1_snapshot.json'),'--snapshot',str(SAMPLES/'federation_g5.json'),'--out',tmp]
            with patch.object(sys,'argv',args), contextlib.redirect_stdout(io.StringIO()):
                runpy.run_path(str(HERE/'federation.py'),run_name='__main__')
            self.assertTrue((Path(tmp)/'federation_census.json').exists())

    def test_incremental_cli_covered(self):
        with tempfile.TemporaryDirectory() as tmp:
            args=[str(HERE/'incremental.py'),'--g0',str(SAMPLES/'fleet_g0.json'),'--g1',str(SAMPLES/'fleet_g1_snapshot.json'),'--g2',str(SAMPLES/'fleet_g2_snapshot.json'),'--out',tmp]
            with patch.object(sys,'argv',args), contextlib.redirect_stdout(io.StringIO()):
                runpy.run_path(str(HERE/'incremental.py'),run_name='__main__')
            self.assertTrue((Path(tmp)/'incremental_pulses.json').exists())

if __name__=='__main__': unittest.main()
