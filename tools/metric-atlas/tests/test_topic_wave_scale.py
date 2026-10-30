"""P1 six-topic fan-in without source dispatch, issue writes or forged native telemetry."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from metric_atlas import topic_wave_scale as m

FIXTURE=Path(__file__).with_name('pilot_6topic.json')
def sample():return json.loads(FIXTURE.read_text())

class ScaleTests(unittest.TestCase):
    def setUp(self):self.p=sample()
    def bad(self,fn,reason):
        p=copy.deepcopy(self.p);fn(p)
        with self.assertRaisesRegex(ValueError,reason):m.plan(p)
    def test_pilot_six_topic_two_waves(self):
        r=m.plan(self.p);self.assertEqual(r['planned_topic_count'],6)
        self.assertEqual(r['wave_count'],2)
        self.assertEqual(len(r['producer_repos']),3)
        self.assertEqual(r['existing_cron_reused_count'],3)
    def test_typed_targets(self):
        self.assertEqual(m.plan(self.p)['bd_targets_count'],5)
    def test_no_physical_dispatch_claim(self):
        z=m.plan(self.p)
        self.assertEqual(z['metrics']['native_runners_launched'],0)
        self.assertEqual(z['metrics']['source_writers'],0)
        self.assertEqual(z['merge_admission'],'HOLD')
    def test_unknown_queue_metrics_remain_unknown(self):
        z=m.plan(self.p)['metrics']
        for key in ('queue_p95_seconds','native_worker_minutes','saved_scan_minutes','matched_bd_net_burn','root_closures'):
            self.assertIsNone(z[key])
    def test_targeted_recensus_not_six_full_scans(self):
        z=m.plan(self.p)['metrics']
        self.assertEqual(z['source_recensus_scenarios'],1)
    def test_wave_receipt_chain(self):
        z=m.plan(self.p)
        self.assertIsNone(z['waves'][0]['parent_receipt_sha256'])
        self.assertEqual(z['waves'][1]['parent_receipt_sha256'],z['waves'][0]['receipt_sha256'])
    def test_wave_digest_determinism(self):
        self.assertEqual(m.plan(self.p),m.plan(sample()))
    def test_source_owner_not_six(self):
        self.assertEqual(m.plan(self.p)['producer_repos'],['GBOGEB/ABACUS','GBOGEB/cryoplant-project','GBOGEB/pipeline-automation-hub'])
    def test_wrong_schema(self):self.bad(lambda p:p.update(schema='x'),'INVALID_SCALE_SCHEMA')
    def test_source_writer_denied(self):self.bad(lambda p:p.update(source_writers=1),'FORGED_EXECUTION')
    def test_native_runner_denied(self):self.bad(lambda p:p.update(native_runners_launched=1),'FORGED_EXECUTION')
    def test_reader_cap_denied(self):self.bad(lambda p:p.update(max_parallel_readers=3),'CAPACITY_UNKNOWN_NO_SCALE')
    def test_wave_over_capacity_denied(self):self.bad(lambda p:p.update(max_parallel_readers=1),'WAVE_OVER_CAPACITY')
    def test_missing_second_wave(self):self.bad(lambda p:p['waves'].pop(),'REQUIRE_TWO_BOUNDED_WAVES')
    def test_duplicate_wave_topic(self):self.bad(lambda p:p['waves'][1]['packets'].__setitem__(0,copy.deepcopy(p['waves'][0]['packets'][0])),'OVERLAPPING_TOPIC_LEASE')
    def test_missing_topic_second_wave(self):self.bad(lambda p:p['waves'][1]['packets'].pop(),'THREE_TOPICS_PER_WAVE')
    def test_mixed_graph_rejected(self):self.bad(lambda p:p['waves'][1]['nodes'][0].update(function='independent competing owner'),'INCONSISTENT_GRAPH_SOURCE')
    def test_target_missing_head_denied(self):self.bad(lambda p:p['bd_targets'][2].update(head_sha='bad'),'BAD_TARGET_HEAD')
    def test_duplicate_target_denied(self):self.bad(lambda p:p['bd_targets'].append(copy.deepcopy(p['bd_targets'][0])),'DUPLICATE_BD_TARGET')
    def test_unbound_target_denied(self):self.bad(lambda p:p['bd_targets'][0].update(topic='outside.scope'),'FALSE_BD_SOURCE_PROOF')
    def test_false_issue_closure_denied(self):self.bad(lambda p:p['bd_targets'][0].update(evidence='CLOSED_VERIFIED'),'FALSE_BD_SOURCE_PROOF')
    def test_changed_cron_file_denied(self):self.bad(lambda p:p['existing_cron'][0].update(path='../../unsafe.yml'),'BAD_CRON_ID')
    def test_duplicate_cron_denied(self):self.bad(lambda p:p['existing_cron'].append(copy.deepcopy(p['existing_cron'][0])),'BAD_CRON_ID')
    def test_invalid_cron_denied(self):self.bad(lambda p:p['existing_cron'][0].update(expression='* * *'),'BAD_CRON_EXPRESSION')
    def test_fake_scheduler_denied(self):self.bad(lambda p:p['existing_cron'][0].update(evidence='ACTIVE_NEW_CRON'),'CRON_AUTHORITY_FORGED')
    def test_no_new_schedules_issued(self):self.assertEqual(m.plan(self.p)['new_cron_jobs_created'],0)
    def test_manifest_and_file_hash(self):
        with tempfile.TemporaryDirectory() as td:
            out=m.emit(self.p,td)
            obj=json.loads((Path(td)/'manifest.json').read_text())
            self.assertEqual(obj['fan_in_sha256'],hashlib.sha256((Path(td)/'fan-in.json').read_bytes()).hexdigest())
            self.assertEqual(out['planned_topic_count'],6)
    def test_source_graph_invariance(self):
        z=m.plan(self.p)
        self.assertRegex(z['source_graph_sha256'],r'^[a-f0-9]{64}$')
    def test_temporal_scope_error_propagates(self):
        self.bad(lambda p:p['waves'][1]['packets'][0]['packet'].__setitem__('producer_head','wrong'),'PACKET_DIGEST_MISMATCH')
    def test_exact_recipient_subscription_preserved(self):
        r=m.plan(self.p)
        self.assertTrue(all(x['topic_ids'] for x in r['waves']))

if __name__=='__main__':unittest.main()
