import unittest
import ldab_dag_sipoc as m


def samples():
    nodes = ([{'id':'REPO_'+str(i),'kind':'REPO'} for i in range(5)] +
             [{'id':'STAGE_'+str(i),'kind':'STAGE','lane':'LDAB' if i==0 else 'OTHER'} for i in range(39)] +
             [{'id':'BEAM_'+str(i),'kind':'BEAM'} for i in range(10)])
    edges = ([{'source':'STAGE_'+str(i),'target':'STAGE_'+str(i+1),'kind':'PROCESS','temporal':'SAME_PULSE'} for i in range(38)] +
             [{'source':'BEAM_'+str(i),'target':'BEAM_'+str(i+1),'kind':'FEEDFORWARD','temporal':'SAME_PULSE'} for i in range(9)] +
             [{'source':'BEAM_'+str(i),'target':'BEAM_'+str(i+2),'kind':'FEEDFORWARD','temporal':'SAME_PULSE'} for i in range(4)])
    # Mirror the canonical 38 PROCESS + 10 FEEDFORWARD + 3 NEXT_PULSE FEEDBACK split.
    for edge in edges[-3:]:
        edge['kind'] = 'FEEDBACK'
        edge['temporal'] = 'NEXT_PULSE'
    graph={'schema':m.GRAPH_SCHEMA,'source_sha':'a'*40,
           'gate':{'merge_admission':'HOLD'},'scheduler':{'dispatch_authorized':False},
           'sipoc':[{'key':x,'name':x} for x in 'SIPOC'],
           'nodes':nodes,'edges':edges,
           'population':{'repositories':5,'lanes':10,'process_atoms':39,'beams':10,'nodes':54,'edges':51}}
    evidence={'schema':m.EVIDENCE_SCHEMA,'source_head_sha':'a'*40,
              'governance':{'merge_admission':'HOLD','authority_transfer':False},
              'w1':{'run':{'run_id':301,'attempt':1,'status':'queued'},
                    'jobs':{'total':1,'terminal_success_with_steps':False,
                            'ldab_step_manifestations':[]}}}
    return graph,evidence

class GraphTests(unittest.TestCase):
    def test_canonical_population_and_queued_do_not_become_red(self):
        g,e=samples();d=m.build(g,e);self.assertEqual((d['population']['nodes'],d['population']['edges']),(54,51));self.assertEqual(d['diagnostic']['w1_status'],'QUEUED_NOT_EXECUTED');self.assertIsNone(d['diagnostic']['distinct_causal_root_ids'])
    def test_mermaid_clock(self):
        g,e=samples();s=m.mermaid(m.build(g,e));self.assertIn('flowchart LR',s);self.assertIn('N+1',s);self.assertIn('HOLD',s)
    def test_unbound_edge_denied(self):
        g,e=samples();g['edges'][0]['target']='MISSING'
        with self.assertRaisesRegex(ValueError,'unbound edge'):m.build(g,e)
    def test_same_pulse_cycle_denied(self):
        g,e=samples();g['edges'][1]['target']='STAGE_0'
        with self.assertRaisesRegex(ValueError,'same-pulse DAG cycle'):m.build(g,e)
    def test_feedback_same_pulse_denied(self):
        g,e=samples();g['edges'][0]['kind']='FEEDBACK'
        with self.assertRaisesRegex(ValueError,'invalid edge clock'):m.build(g,e)
    def test_sha_mismatch_denied(self):
        g,e=samples();e['source_head_sha']='b'*40
        with self.assertRaisesRegex(ValueError,'SHA parity'):m.build(g,e)
    def test_unverified_root_promotion_denied(self):
        g,e=samples();e['w1']['jobs']['ldab_step_manifestations']=[{'root_id':'ROOT-1','causal_root_accepted':True}]
        with self.assertRaisesRegex(ValueError,'causal-root'):m.build(g,e)
    def test_absent_ldab_lane_denied(self):
        g,e=samples();g['nodes'][5]['lane']='OTHER'
        with self.assertRaisesRegex(ValueError,'LDAB stage missing'):m.build(g,e)
    def test_qps_authority_drift_denied(self):
        g,e=samples();g['gate']['merge_admission']='GO'
        with self.assertRaisesRegex(ValueError,'merge admission'):m.build(g,e)
    def test_sipoc_drift_denied(self):
        g,e=samples();g['sipoc'][2]['key']='X'
        with self.assertRaisesRegex(ValueError,'SIPOC source order'):m.build(g,e)
if __name__=='__main__':unittest.main()
