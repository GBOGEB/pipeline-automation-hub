#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / 'controls/QPS_W189_FEDERATION_SAMPLE4_CURRENT_v1.json'
MATRIX = ROOT / 'triage/w189/QPS_W189_CROSS_SURFACE_FEATURE_MATRIX_v0.1.json'
RUNTIME = ROOT / 'triage/w189/QPS_W189_FEDERATION_EXPANSION_RUNTIME_CONTROL_v0.1.json'
PAIRWISE = ROOT / 'triage/w189/QPS_W189_PAIRWISE_DISPOSITION_LEDGER_v0.1.json'
CENSUS = ROOT / 'triage/w189/QPS_W189_FEDERATION_FLEET_CENSUS_v0.1.json'

def load(p): return json.loads(p.read_text(encoding='utf-8'))
def req(x,m):
    if not x: raise SystemExit('W189R REJECT: '+m)

def main():
    c,m,r,p,f = map(load,(CONTROL,MATRIX,RUNTIME,PAIRWISE,CENSUS))
    req(c['wave']=='W189R','control not return state')
    req(c['source_package']['merge']=='dd28b8471bada007add5b1a94b3d131f7d0b6748','source merge mismatch')
    req(c['native_missioncontrol_runtime']['recorded_steps']==0 and c['native_missioncontrol_runtime']['compensated'] is False,'#923 native gate weakened')
    for v in (c['federated_exact_proof']['pr_head'],c['federated_exact_proof']['postmerge_repeat']):
        req(v['runner_id']>0 and v['result']=='PASS','federated repeat missing')
    req(c['measurement']['breadth']['value']==1.0 and c['measurement']['depth']['value']==1.0 and c['measurement']['penetration']==1.0,'B/D/PEN incomplete')
    req(c['analytics']['accepted_bounded_samples']==4,'accepted sample count mismatch')
    req(c['fleet_census']['accessible_repository_universe_total'] is None and c['fleet_census']['mission_relevant_surface_denominator'] is None,'fleet denominator fabricated')
    req(all(v==0 for v in c['formal_credit_delta'].values()),'formal credit changed')
    req(len(m['rows'])==4 and sum(int(x['accepted_sample']) for x in m['rows'])==4,'matrix not 4/4 accepted')
    req(m['measured_n4_stability']['state']=='MEASURED_SMALL_N_N4_PC1_STABLE_PC2_ROTATING','n4 PCA state mismatch')
    req(m['measured_n4_stability']['pc1_loading_congruence_abs']>0.99,'PC1 stability missing')
    req(m['measured_n4_stability']['pc2_loading_congruence_abs']<0.20,'PC2 rotation guard missing')
    req(r['acceptance']['accepted_sample'] is True and r['acceptance']['accepted_bounded_sample_count']==4,'runtime acceptance mismatch')
    req(r['bt']['transport_unregularized_mle']=='NO_FINITE_MLE','BT separation guard missing')
    req(r['bt']['global_state'].startswith('WITHHELD_'),'global BT admitted')
    req(r['fleet_census']['mission_relevant_governed_surface_denominator'] is None,'runtime fleet denominator fabricated')
    req(r['child_guard']['visual_n200_control_promotion'] is False,'child promoted by federation')
    comp=p['bt_gate']['repeated_comparable_component']
    req(comp['observed_comparisons']==2 and comp['unregularized_mle_state']=='SEPARATED_2_TO_0_NO_FINITE_MLE','pairwise evidence changed')
    req(f['denominator_model']['mission_relevant_governed_surface_universe']['value'] is None,'census denominator fabricated')
    print('W189R PASS: sample4 accepted; B=D=PEN=1; n4 PC1 stable/PC2 rotating; BT/fleet/child guards preserved')

if __name__=='__main__': main()
