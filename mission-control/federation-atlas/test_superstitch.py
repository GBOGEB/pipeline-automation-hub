"""Fail-closed source, graph, protection, hierarchy and packaging tests for W34."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

MOD=Path(__file__).resolve().parent/'superstitch'
sys.path.insert(0,str(MOD))
import build as b
HEAD='a'*40

class SuperstitchContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.model=json.loads(b.SOURCE.read_text(encoding='utf-8'))
    def d(self):return copy.deepcopy(self.model)
    def test_source_schema_validated(self):self.assertEqual(b.validate(self.d())['schema'],b.SCHEMA)
    def test_exposes_all_adjacent_lanes(self):self.assertEqual(len(self.model['lanes']),6)
    def test_detects_shared_canonical_nodes(self):
        from collections import Counter
        ids=Counter(n['canonical_id'] for n in self.model['nodes'])
        self.assertEqual(sum(v>1 for v in ids.values()),3)
    def test_no_fabricated_running_status(self):
        m=self.d();m['nodes'][0]['status']='RUNNING'
        with self.assertRaisesRegex(ValueError,'FABRICATED_LIVE_STATUS'):b.validate(m)
    def test_no_public_private_qps_source_path(self):
        m=self.d();src=next(x for x in m['source_refs'] if x['id']=='QPS-CHILD');src['path']='confidential.yaml'
        with self.assertRaisesRegex(ValueError,'PRIVATE_SOURCE_LEAK'):b.validate(m)
    def test_unauthenticated_orphan_graph_edge_fail_closed(self):
        m=self.d();m['edges'][0]['from']='not-a-source-node'
        with self.assertRaisesRegex(ValueError,'EDGE_ENDPOINT_INVALID'):b.validate(m)
    def test_native_binding_requires_real_receipt(self):
        m=self.d();m['edges'][0]['binding']='NATIVE_RECEIPT'
        with self.assertRaisesRegex(ValueError,'NATIVE_EDGE_WITHOUT_SOURCE_RECEIPT'):b.validate(m)
    def test_next_pulse_feedback_is_separate_from_dag_cycle(self):
        m=self.d();b.validate(m)
        m['edges'].append({'from':'next-pulse','to':'mc533','kind':'DEPENDENCY','binding':'ROLE_ONLY','label':'cycle'})
        with self.assertRaisesRegex(ValueError,'CYCLIC_CORE_DAG'):b.validate(m)
    def test_merging_source_role_and_approval_rejected(self):
        m=self.d();m['authority']['qps_owner_acceptance']=True
        with self.assertRaisesRegex(ValueError,'AUTHORITY_PROMOTION'):b.validate(m)
    def test_historical_denominator_immutable(self):
        m=self.d();m['observations']['historical_six_repo_breadth']['observed']=42
        with self.assertRaisesRegex(ValueError,'FALSE_BREADTH'):b.validate(m)
    def test_render_all_graph_nodes_and_duplicate_identity(self):
        s=b.draw_svg(self.d());self.assertEqual(s.count('class="graph-node'),len(self.model['nodes']))
        self.assertIn('data-canonical="DOW.RECEIPT"',s);self.assertIn('data-canonical="KEB.GRAPH"',s)
        self.assertIn('data-binding="DECLARED"',s)
    def test_reverse_routing_has_declared_feedback(self):
        s=b.draw_svg(self.d());self.assertIn('class="edge retrigger"',s)
    def test_source_sha_must_be_exact(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,'EXACT_40_SHA_REQUIRED'):
                b.do_build(b.SOURCE,Path(d),'main')
    def test_generated_byte_manifest_integrity(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);m=b.do_build(b.SOURCE,out,HEAD)
            self.assertEqual(b.verify(out,HEAD),m)
            self.assertEqual(len(m['member_sha256']),8)
            self.assertIn('taxonomy.json',m['member_sha256']);self.assertIn('glossary.json',m['member_sha256'])
    def test_tampered_asset_blocks_release(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);b.do_build(b.SOURCE,out,HEAD)
            (out/'graph.svg').write_text('<svg>fake</svg>')
            with self.assertRaisesRegex(ValueError,'TAMPERED_MEMBER:graph.svg'):b.verify(out,HEAD)
    def test_html_semantic_assets_and_controls(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);b.do_build(b.SOURCE,out,HEAD)
            s=(out/'index.html').read_text()
            for item in ('Hierarchy inspector','Superstitch DAG','DAG activity','SIPOC','SPINE','TESTFLIGHT','data-canonical','source-model','depth','Show all DAGs'):
                # SPINE is in embedded glossary
                self.assertIn(item,s)
            self.assertNotIn('Last updated Feb 10, 2025',s)
            self.assertNotIn('>Live</span>',s)
    def test_public_inputs_have_stable_source_sha(self):
        self.assertTrue(all(x['head'] is None or len(x['head'])==40 for x in self.model['source_refs']))
    def test_breadth_and_code_coverage_do_not_combine(self):
        o=self.model['observations'];self.assertEqual(o['historical_six_repo_breadth'],{
          'observed':6,'eligible':42,'evidence_class':'HISTORICAL_NOT_FRESH_CENSUS'})
        self.assertEqual(o['math_g3p_single_module']['statements'],[172,172])
        self.assertEqual(o['math_g3p_single_module']['branches'],[84,84])
    def test_taxonomy_glossary_child_authority(self):
        d=json.loads((MOD/'SUPERSTITCH_TAXONOMY_v1.json').read_text());g=json.loads((MOD/'SUPERSTITCH_GLOSSARY_v1.json').read_text());self.assertFalse(d['authority_transfer']);self.assertFalse(g['authority_transfer'])
        self.assertGreaterEqual(len(g['terms']),15)

if __name__=='__main__':unittest.main()
