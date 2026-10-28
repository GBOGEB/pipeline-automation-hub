"""W378 read-only source-bound delta/graph pilot regression tests."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from metric_atlas import topic_exchange as tx, topic_wave as m

FIXTURE=Path(__file__).with_name('pilot_3topic.json')

def sample():
    return json.loads(FIXTURE.read_text())

class GraphTests(unittest.TestCase):
    def setUp(self): self.p=sample()
    def broken(self, callback, message):
        p=copy.deepcopy(self.p);callback(p)
        with self.assertRaisesRegex(ValueError,message):m.pilot(p)
    def test_pilot_three_topics(self):
        r=m.pilot(self.p)
        self.assertEqual(r['metrics']['topics'],3)
        self.assertEqual(r['metrics']['nodes'],14)
        self.assertEqual(r['metrics']['next_pulse_edges'],1)
        self.assertEqual(r['metrics']['actual_worker_capacity'],None)
        self.assertFalse(r['authority_transfer'])
    def test_unchanged_source_staged(self):
        r=m.pilot(self.p)
        d={x['topic']:x['decision'] for x in r['topics']}
        self.assertEqual(d['electrical.icd.feeders'],'STAGED_NOT_DELIVERED')
    def test_targeted_recensus_only_drift_topic(self):
        r=m.pilot(self.p)
        x={v['topic']:v for v in r['topics']}
        self.assertTrue(x['metrics.census.ack']['source_recensus_required'])
        self.assertFalse(x['electrical.icd.feeders']['source_recensus_required'])
        self.assertEqual(r['metrics']['source_recensus_requested'],1)
    def test_unrelated_head_needs_bridge_not_recensus(self):
        r=m.pilot(self.p)
        x={v['topic']:v for v in r['topics']}
        self.assertEqual(x['publishing.r07.oid']['decision'],'VERIFY_HEAD_BRIDGE_NO_FULL_RECENSUS')
    def test_readers_disjoint_and_bounded(self):
        r=m.pilot(self.p)
        self.assertEqual([x['reader_lane'] for x in r['topics']],[0,1,0])
        self.assertTrue(all(x['native_worker_id'] is None for x in r['topics']))
    def test_one_reader_supported(self):
        self.p['max_readers']=1
        self.assertEqual(set(x['reader_lane'] for x in m.pilot(self.p)['topics']),{0})
    def test_third_reader_blocked(self):self.broken(lambda p:p.update(max_readers=3),'UNBOUNDED_READERS')
    def test_fourth_topic_blocked(self):self.broken(lambda p:p['packets'].append(copy.deepcopy(p['packets'][0])),'PILOT_PACKET_CAP')
    def test_duplicate_topic_blocked(self):self.broken(lambda p:p['packets'].append(copy.deepcopy(p['packets'][0])) if p['packets'].pop() else None,'DUPLICATE_TOPIC_OWNER')
    def test_unauthorised_writer_blocked(self):self.broken(lambda p:p.update(source_writers=1),'UNAUTHORIZED_WRITER')
    def test_authority_false_required(self):self.broken(lambda p:p.update(authority_transfer=True),'AUTHORITY_PROMOTION')
    def test_empty_pilot_denied(self):self.broken(lambda p:p.update(packets=[]),'PILOT_PACKET_CAP')
    def test_wrong_schema_denied(self):self.broken(lambda p:p.update(schema='other'),'INVALID_PILOT_SCHEMA')
    def test_unsubscribed_recipient_denied(self):self.broken(lambda p:p['packets'][0].update(recipient='GBOGEB/OTHER'),'UNSUBSCRIBED_RECIPIENT')
    def test_cross_sha_packet_denied(self):self.broken(lambda p:p['packets'][0]['packet'].update(producer_head='f'*40),'PACKET_DIGEST_MISMATCH')
    def test_bad_current_head_denied(self):self.broken(lambda p:p['packets'][0].update(current_head='abcd'),'INVALID_CURRENT_IDENTITY')
    def test_missing_node_owner_denied(self):self.broken(lambda p:p['nodes'][0].update(owner=''),'MISSING_NODE_OWNER')
    def test_duplicate_node_denied(self):self.broken(lambda p:p['nodes'][1].update(id='S.ELEC'),'DUPLICATE_OR_INVALID_NODE')
    def test_invalid_oid_denied(self):self.broken(lambda p:p['nodes'][0].update(blob_oid='oid123'),'INVALID_GIT_BLOB_OID')
    def test_invalid_git_sha_denied(self):self.broken(lambda p:p['nodes'][0].update(head_sha='abc'),'INVALID_COMMIT_SHA')
    def test_unknown_oid_remains_unknown(self):self.assertEqual(m.label(self.p['nodes'][3],'OID'),'OID UNKNOWN')
    def test_projections_preserve_node_identity(self):
        r=m.pilot(self.p)
        for view,v in r['graph']['projections'].items():
            for lens, text in v.items():
                self.assertEqual(text.count('["'),len(self.p['nodes']))
                self.assertIn('flowchart LR',text)
    def test_nine_projections(self):
        self.assertEqual(sum(map(len,m.pilot(self.p)['graph']['projections'].values())),9)
    def test_next_pulse_is_dotted(self):
        self.assertIn('-.->',m.make_mermaid(self.p['nodes'],self.p['edges'],'FUNCTION','DAG'))
    def test_same_pulse_cycle_denied(self):
        self.broken(lambda p:p['edges'].append({'from':'G.CI','to':'S.TOPIC','relation':'DEPENDS'}),'SAME_PULSE_CYCLE')
    def test_next_pulse_cycle_allowed(self):
        self.assertEqual(m.pilot(self.p)['metrics']['next_pulse_edges'],1)
    def test_duplicate_edge_denied(self):self.broken(lambda p:p['edges'].append(copy.deepcopy(p['edges'][0])),'FOREIGN_OR_DUPLICATE_EDGE')
    def test_unknown_edge_node_denied(self):self.broken(lambda p:p['edges'][0].update(to='NOT_A_NODE'),'FOREIGN_OR_DUPLICATE_EDGE')
    def test_extra_edge_field_denied(self):self.broken(lambda p:p['edges'][0].update(authority='YES'),'INVALID_EDGE_SHAPE')
    def test_too_many_next_pulse_edges_denied(self):
        def mutate(p):
            p['edges'] += [{'from':'C.HUB','to':v,'relation':'NEXT_PULSE'} for v in ['S.ELEC','S.TOPIC','S.R07']]
        self.broken(mutate,'UNBOUNDED_FEEDBACK')
    def test_unique_oid_and_commit_lens(self):
        nodes=self.p['nodes']
        self.assertNotEqual(m.label(nodes[0],'SHA'),m.label(nodes[0],'OID'))
    def test_unapproved_status_not_green(self):
        self.assertEqual(m.pilot(self.p)['merge_admission'],'HOLD')
    def test_missing_real_queue_metrics_remain_null(self):
        metrics=m.pilot(self.p)['metrics']
        for k in ('queue_wait_p95_seconds','saved_runner_minutes','bd_flow_delta','coverage_delta'):
            self.assertIsNone(metrics[k])
    def test_deterministic_graph_output(self):
        self.assertEqual(m.digest(m.pilot(self.p)),m.digest(m.pilot(sample())))
    def test_html_has_both_real_toggles_and_svg(self):
        body=m.render_html(m.pilot(self.p))
        self.assertIn('<select id="lens">',body)
        self.assertIn('<select id="view">',body)
        self.assertIn('<svg id="graph"',body)
        self.assertIn('addEventListener',body)
    def test_html_does_not_expose_restricted_binary(self):
        s=m.render_html(m.pilot(self.p))
        self.assertNotIn('GITHUB_TOKEN',s)
        self.assertNotIn('RESTRICTED_SOURCE_BYTES',s)
    def test_canonical_manifest_no_self_hash(self):
        with tempfile.TemporaryDirectory() as d:
            manifest=m.emit(self.p,d)
            self.assertNotIn('manifest.json',manifest['files_sha256'])
            for f,h in manifest['files_sha256'].items():
                self.assertEqual(hashlib.sha256((Path(d)/f).read_bytes()).hexdigest(),h)
            self.assertEqual(len(manifest['files_sha256']),11)
    def test_comparison_same_cohort(self):
        a=m.pilot(self.p)
        self.assertEqual(m.compare(a,a)['delta']['changed_packet_sha'],0)
    def test_comparison_method_drift_rejected(self):
        a=m.pilot(self.p);b=copy.deepcopy(a);b['method_version']='2'
        self.assertFalse(m.compare(a,b)['comparable'])
    def test_comparison_scope_drift_rejected(self):
        a=m.pilot(self.p);b=copy.deepcopy(a);b['topics'].pop()
        self.assertFalse(m.compare(a,b)['comparable'])
    def test_comparison_receipt_changed_no_claim_of_closure(self):
        a=m.pilot(self.p);b=copy.deepcopy(a);b['topics'][0]['packet_sha256']='f'*64
        self.assertEqual(m.compare(a,b)['delta']['changed_packet_sha'],1)
        self.assertEqual(b['formal_credit_delta'],0)

if __name__=='__main__':unittest.main()
