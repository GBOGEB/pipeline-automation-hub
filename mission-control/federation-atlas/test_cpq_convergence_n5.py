"""Fail-closed CPQ N5 source, graph, temporal and output tests."""
import copy
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import cpq_convergence_n5 as c

SHA='a'*40

def fixture():
    ids=['CPQ-%03d'%n for n in range(1,19)]
    work=set(sum(c.WAVES.values(),[]))
    items=[]
    for k in ids:
        state='TODO' if k in work else 'DONE'
        if k in ('CPQ-003','CPQ-005'):state='ACTIVE'
        if k in ('CPQ-016','CPQ-018'):state='UNKNOWN_NEEDS_READER'
        flow='READY' if state=='TODO' else 'LINKED'
        h=[dict(at='W1.C1.I0.S0',state='TODO',flow='READY',evidence='initial'),
           dict(at='W1.C1.I2.S1',state=state,flow=flow,evidence='evidence '+k)]
        items.append(dict(id=k,title='Title '+k,done_when='Proof '+k,control_when='Repeat '+k,
                          history=h,depends_on=['CPQ-010'] if k=='CPQ-013' else [],severity='P1',links=[]))
    queue=dict(schema='missioncontrol.code_purple.bd_queue.v1',items=items,
               authority_transfer=False,formal_credit_delta=0)
    repos=['GBOGEB/'+v for v in ('ABACUS','CODEX','cryoplant-project','pipeline-automation-hub','Q_engineering_tools','document-organization-system','DOCX_RTM_Automation')]
    p1=[dict(repo=r,head='abcdef0',**{'class':'GREEN_CONTROL'}) for r in repos]
    p2=[dict(repo=r,head='b'*40,run_id=i+1,job_id=100+i,attempt=1,**{'class':'PROVE_UNKNOWN'}) for i,r in enumerate(repos)]
    top7=dict(schema='missioncontrol.code_purple.top7_census_pulses.v1',authority_transfer=False,
              pulses=[dict(pulse=1,rows=p1,observed_on='2026-09-28'),
                      dict(pulse=2,rows=p2,observed_on='2026-10-16')])
    return queue,top7

class CPQN5Tests(unittest.TestCase):
    def test_positive_canonical_census_and_routes(self):
        q,t=fixture();out=c.converge(q,t,SHA,observed_on='2026-10-17')
        self.assertEqual(out['metrics']['canonical_rows'],18)
        self.assertEqual({k:out['metrics'][k] for k in ('open','active','todo','reader','done')},
                         {'open':9,'active':2,'todo':5,'reader':2,'done':9})
        self.assertEqual(out['metrics']['work_orders_with_routes'],9)
        self.assertEqual(out['metrics']['source_readback_coverage'],{'numerator':18,'denominator':18})
        self.assertIsNone(out['metrics']['qualified_changed_line_coverage'])
        self.assertIsNone(out['metrics']['accepted_causal_root_closures'])
        self.assertEqual(out['admission'],'HOLD')
        self.assertFalse(out['dispatch_authorized'])
    def test_source_sha_mandatory(self):
        q,t=fixture()
        for sha in (None,True,'bad','A'*40,'abcdef0','g'*40):
            with self.subTest(sha=sha),self.assertRaises(ValueError):c.converge(q,t,sha)
    def test_duplicate_and_truncated_census_fail_closed(self):
        q,t=fixture();q['items'][0]=copy.deepcopy(q['items'][1]);
        with self.assertRaisesRegex(ValueError,'bad/duplicate'):c.converge(q,t,SHA)
        q,t=fixture();q['items'].pop()
        with self.assertRaisesRegex(ValueError,'18-item'):c.converge(q,t,SHA)
    def test_wrong_schema_and_authority_transfer(self):
        for change in (lambda q:q.update(schema='fake'),lambda q:q.update(authority_transfer=True),
                       lambda q:q.update(formal_credit_delta=1)):
            q,t=fixture();change(q)
            with self.assertRaises(ValueError):c.converge(q,t,SHA)
    def test_corrupt_history_rejected(self):
        variants=[lambda h:h.pop(),lambda h:h.reverse(),lambda h:h[1].update(at=h[0]['at']),
                  lambda h:h[1].update(at='2026-10-17'),lambda h:h[1].update(state='MERGED'),
                  lambda h:h[1].update(flow=None)]
        for variant in variants:
            q,t=fixture();variant(q['items'][0]['history'])
            if len(q['items'][0]['history'])==1:continue
            with self.subTest(variant=variant),self.assertRaises(ValueError):c.converge(q,t,SHA)
    def test_missing_item_title_and_dov_fails(self):
        for k,v in [('title',''),('done_when','')]:
            q,t=fixture();q['items'][0][k]=v
            with self.assertRaises(ValueError):c.converge(q,t,SHA)
    def test_self_or_unknown_dependency_rejected(self):
        for dep in ('CPQ-013','CPQ-099'):
            q,t=fixture();q['items'][12]['depends_on']=[dep]
            with self.assertRaises(ValueError):c.converge(q,t,SHA)
    def test_dependency_cycle_rejected(self):
        q,t=fixture();q['items'][9]['depends_on']=['CPQ-013']
        with self.assertRaisesRegex(ValueError,'cycle'):c.converge(q,t,SHA)
    def test_unexpected_new_open_item_requires_owner_routing(self):
        q,t=fixture();q['items'][0]['history'][-1]['state']='ACTIVE'
        with self.assertRaisesRegex(ValueError,'unclassified'):c.converge(q,t,SHA)
    def test_no_classification_by_integer_zero(self):
        q,t=fixture();out=c.converge(q,t,SHA)
        self.assertIsNone(out['top7']['matched_fleet_delta'])
        self.assertIsNone(out['top7']['top14_promotion'])
        self.assertNotEqual(out['root_credit'],'0')
    def test_current_top7_native_identity_breadth(self):
        q,t=fixture();out=c.converge(q,t,SHA)
        self.assertEqual(out['top7']['pulses'][-1]['native_identity_complete'],7)
        self.assertFalse(out['top7']['pair_eligible_for_source_match'])
        self.assertIn('WITHHELD',out['top7']['comparison'])
    def test_matching_two_pulses_is_still_not_proof_of_effect(self):
        q,t=fixture()
        for r in t['pulses'][0]['rows']:
            r.update(head='c'*40,run_id=999,job_id=999,attempt=1)
        out=c.converge(q,t,SHA)
        self.assertTrue(out['top7']['pair_eligible_for_source_match'])
        self.assertIsNone(out['top7']['matched_fleet_delta'])
    def test_top7_duplicate_or_changed_population_fails(self):
        for edit in (lambda x:x['pulses'][1]['rows'][0].update(repo=x['pulses'][1]['rows'][1]['repo']),
                     lambda x:x['pulses'][0]['rows'].pop(),
                     lambda x:x['pulses'][1]['rows'][0].update(repo='GBOGEB/unknown'),
                     lambda x:x['pulses'][1].update(pulse=0),
                     lambda x:x.update(authority_transfer=True),
                     lambda x:x.update(schema='false')):
            q,t=fixture();edit(t)
            with self.subTest(edit=edit),self.assertRaises(ValueError):c.converge(q,t,SHA)
    def test_top7_unqualified_run_identity_not_credited(self):
        for k,v in [('run_id',0),('job_id',True),('attempt',None),('head','f'*7)]:
            q,t=fixture();t['pulses'][-1]['rows'][0][k]=v
            out=c.converge(q,t,SHA)
            self.assertEqual(out['top7']['pulses'][-1]['native_identity_complete'],6)
            self.assertIsNone(out['top7']['matched_fleet_delta'])
    def test_cross_schema_rejects_absent_pulses(self):
        q,t=fixture();t['pulses']=[]
        with self.assertRaisesRegex(ValueError,'two observed'):c.converge(q,t,SHA)
    def test_html_escapes_xss_and_preserves_controls(self):
        q,t=fixture();q['items'][0]['title']='<img src=x onerror=alert(1)>'
        rendered=c.render_html(c.converge(q,t,SHA))
        self.assertNotIn('<img src=x onerror=',rendered)
        self.assertIn('\\u003cimg',rendered)
        for token in ('id="items"','id="search"','id="status"','function draw()','id="top7"'):
            self.assertIn(token,rendered)
    def test_cli_is_byte_stable_and_does_not_mutate_source(self):
        q,t=fixture()
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);a=root/'q.json';b=root/'t.json';dst=root/'out';
            a.write_text(json.dumps(q));b.write_text(json.dumps(t))
            pre=(hashlib.sha256(a.read_bytes()).hexdigest(),hashlib.sha256(b.read_bytes()).hexdigest())
            args=['--queue',str(a),'--top7',str(b),'--head',SHA,'--out',str(dst),'--observed-on','2026-10-17']
            c.main(args)
            x=(dst/'cpq-n5.json').read_bytes();h=(dst/'cpq-n5.html').read_bytes()
            c.main(args)
            self.assertEqual(x,(dst/'cpq-n5.json').read_bytes())
            self.assertEqual(h,(dst/'cpq-n5.html').read_bytes())
            self.assertEqual(pre,(hashlib.sha256(a.read_bytes()).hexdigest(),hashlib.sha256(b.read_bytes()).hexdigest()))
    def test_ordinal_history_tolerates_evidence_without_timestamp(self):
        q,t=fixture();q['items'][0]['history'][-1]['evidence']='No timestamp, no false age'
        self.assertEqual(c.converge(q,t,SHA)['metrics']['canonical_rows'],18)
    def test_open_dependencies_classified_as_dependency_not_done(self):
        q,t=fixture();o=c.converge(q,t,SHA)
        root=next(x for x in o['items'] if x['id']=='CPQ-013')
        self.assertEqual(root['route'],'DEPENDENCY_CONTROL')
        self.assertEqual(root['dependencies'],['CPQ-010'])
        self.assertEqual(root['state'],'TODO')

if __name__ == '__main__':unittest.main()