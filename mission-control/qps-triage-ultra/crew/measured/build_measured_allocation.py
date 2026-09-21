#!/usr/bin/env python3
import json, math, os, statistics
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parent
policy=json.loads((ROOT/'MEASURED_ALLOCATION_POLICY_v1.json').read_text())
receipts=[]

# Live exact-SHA runtime receipts produced by the current job.
receipts_dir=Path(os.environ.get('MEASURED_LIVE_RECEIPTS_DIR', ROOT/'receipts'))
if receipts_dir.exists():
    for p in sorted(receipts_dir.glob('*.json')):
        if p.name=='RUN_SUMMARY.json':
            continue
        try:
            r=json.loads(p.read_text())
        except Exception:
            continue
        if r.get('schema')=='missioncontrol.mission_crew_task_runtime_receipt.v1':
            receipts.append(r)

# Canonical evidence returns are compact, provenance-bound references to accepted
# workflow artifacts. validate_evidence_returns.py must pass before this builder.
history=Path(os.environ.get('MEASURED_EVIDENCE_HISTORY', ROOT/'history'))
if history.exists():
    for p in sorted(history.glob('RUN_RETURN_*.json')):
        doc=json.loads(p.read_text())
        if doc.get('schema')!='missioncontrol.measured_task_run_return.v1':
            continue
        if doc.get('status') not in {
            'ACCEPTED_EXACT_SHA_RUNTIME_RETURN',
            'REJECTED_EXACT_SHA_RUNTIME_RETURN',
        }:
            continue
        for obs in doc['task_observations']:
            receipts.append({
                'schema':'missioncontrol.mission_crew_task_runtime_receipt.returned.v1',
                'crew_id':obs['crew_id'],
                'competency_dimension':obs['competency_dimension'],
                'predeclared_task_level':obs['predeclared_task_level'],
                'execute_seconds':obs['execute_seconds'],
                'disposition':obs['disposition'],
                'run_id':doc['run_id'],
                'source_sha':doc['source_sha'],
                'attribution_basis':'PREDECLARED_ASSIGNMENT',
                'evidence_return_status':doc['status'],
                'artifact_digest':doc['artifact']['digest'],
                'rex_postflight':{
                    'rex_ids_observed':obs.get('rex_ids_observed',[]),
                    'recurrence_level':(
                        'REGRESSION' if doc['rex_postflight'].get('regression') else
                        'PERSISTENT' if doc['rex_postflight'].get('persistent') else
                        'RECURRING' if doc['rex_postflight'].get('recurring') else None
                    ),
                    'preventive_action_effective':obs.get('preventive_action_effective')
                }
            })

# De-duplicate the same run+crew+dimension if a live receipt is also already in
# canonical history. Live receipt wins because it contains the fuller payload.
dedup={}
for r in receipts:
    key=(str(r['run_id']),r['source_sha'],r['crew_id'],r['competency_dimension'])
    if key not in dedup or r.get('schema')=='missioncontrol.mission_crew_task_runtime_receipt.v1':
        dedup[key]=r
receipts=list(dedup.values())

groups=defaultdict(list)
for r in receipts:
    groups[(r['crew_id'],r['competency_dimension'])].append(r)
rows=[]
for (crew,dim), rs in sorted(groups.items()):
    accepted=[r for r in rs if r['disposition']=='ACCEPT']
    rejected=[r for r in rs if r['disposition']=='REJECT']
    runs={r['run_id'] for r in accepted}
    shas={r['source_sha'] for r in accepted}
    total=len(accepted)+len(rejected)
    rex_events=sum(len(r.get('rex_postflight',{}).get('rex_ids_observed',[])) for r in rs)
    prevention=[r.get('rex_postflight',{}).get('preventive_action_effective') for r in rs]
    prevention=[x for x in prevention if x is not None]
    blocking=[]
    for r in rs:
        level=r.get('rex_postflight',{}).get('recurrence_level')
        if level in policy['measured_allocation_gate']['no_blocking_rex_levels']:
            blocking.append(level)
    eligible=(len(runs)>=policy['measured_allocation_gate']['min_accepted_distinct_runs'] and len(shas)>=policy['measured_allocation_gate']['min_distinct_source_shas'] and len(accepted)>len(rejected) and not blocking)
    demonstrated=min([r['predeclared_task_level'] for r in accepted], default=None)
    seed_weight=max(0.0,1.0-len(runs)/4.0)
    rows.append({
      'crew_id':crew,'competency_dimension':dim,'accepted':len(accepted),'rejected':len(rejected),
      'acceptance_rate':(len(accepted)/total if total else None),'distinct_accepted_runs':len(runs),
      'distinct_source_shas':len(shas),'demonstrated_level':demonstrated,
      'mean_execute_seconds':(statistics.mean([r['execute_seconds'] for r in rs]) if rs else None),
      'rex_trigger_rate':(rex_events/len(rs) if rs else 0.0),
      'prevention_success_rate':(sum(bool(x) for x in prevention)/len(prevention) if prevention else None),
      'allocation_eligible':eligible,
      'allocation_basis':('MEASURED_ONLY' if eligible else 'SEEDED_PRIOR_WITH_MEASURED_OBSERVATION_NOT_YET_ALLOCATABLE'),
      'seed_display_weight':round(seed_weight,3),'blocking_rex_levels':sorted(set(blocking))
    })

# HIST-BD-008: PCA readiness must be derived from the same eligible measured
# population that may actually enter the allocation model. Ineligible rows may
# remain visible in the receipt but cannot create artificial variance.
eligible_rows=[r for r in rows if r['allocation_eligible']]
varying=0
feature_names=['demonstrated_level','acceptance_rate','distinct_accepted_runs','distinct_source_shas','mean_execute_seconds','rex_trigger_rate']
for f in feature_names:
    vals=[r[f] for r in eligible_rows if r[f] is not None]
    if len(vals)>=2 and len(set(vals))>1:
        varying+=1
pca_ready=len(eligible_rows)>=policy['pca_gate']['min_measured_rows'] and varying>=policy['pca_gate']['min_varying_features']

if pca_ready:
    pca_status='READY'
elif len(eligible_rows)<policy['pca_gate']['min_measured_rows']:
    pca_status='DEFER_INSUFFICIENT_ELIGIBLE_MEASURED_ROWS'
else:
    pca_status='DEFER_INSUFFICIENT_MEASURED_VARIANCE'


def derive_pair_outcome(observation, tie_threshold):
    """Derive the timing result rather than trusting a stored winner label."""
    seconds_a=float(observation['seconds_a'])
    seconds_b=float(observation['seconds_b'])
    scale=max(seconds_a,seconds_b)
    relative_gap=0.0 if scale==0 else abs(seconds_a-seconds_b)/scale
    if relative_gap < tie_threshold or seconds_a==seconds_b:
        winner='TIE'
    elif seconds_a < seconds_b:
        winner=observation['strategy_a']
    else:
        winner=observation['strategy_b']
    return relative_gap,winner


def two_node_bt_abilities(wins_a, wins_b):
    """Return centered two-node BT log abilities with Jeffreys-style smoothing.

    For two strategies, BT requires ability_a-ability_b == logit(P(a beats b)).
    The previous full-log-odds-per-node shortcut doubled this separation after
    centering. This contract intentionally supports exactly two nodes; a larger
    graph requires a separately validated joint-fit implementation.
    """
    log_ratio=math.log((wins_a+0.5)/(wins_b+0.5))
    return log_ratio/2.0,-log_ratio/2.0


# REX-CM-002 analytic scale fixture. 8 wins vs 4 wins must produce one log-odds
# separation, not twice that amount.
_fixture_a,_fixture_b=two_node_bt_abilities(8.0,4.0)
_fixture_expected=math.log(8.5/4.5)
assert math.isclose(_fixture_a-_fixture_b,_fixture_expected,rel_tol=1e-12,abs_tol=1e-12)

# Fail-closed observed pairwise evidence. Timing cannot count until equivalent
# workload results were proved by the frontier semantic digest contract.
pairwise_path=ROOT/'PAIRWISE_OBSERVATIONS.json'
pairs=[]
if pairwise_path.exists():
    pair_doc=json.loads(pairwise_path.read_text())
    assert pair_doc.get('schema')=='missioncontrol.pairwise_allocation_observations.v1'
    assert pair_doc.get('status')=='CANONICAL_OBSERVED'
    assert pair_doc.get('authority_transfer') is False
    comparison_contract=pair_doc.get('comparison_contract',{})
    tie_threshold=float(comparison_contract.get('tie_relative_gap_below',-1))
    assert 0.0 <= tie_threshold < 1.0
    seen_ids=set()
    for o in pair_doc.get('observations',[]):
        oid=o.get('observation_id')
        assert oid and oid not in seen_ids
        seen_ids.add(oid)
        assert o.get('evidence_class')=='OBSERVED_EXACT_SHA_RUNTIME'
        assert o.get('comparable') is True
        assert o.get('habitat') in {'linux','windows'}
        assert isinstance(o.get('source_sha'),str) and len(o['source_sha'])==40
        assert str(o.get('run_id',''))
        assert o.get('strategy_a') and o.get('strategy_b') and o['strategy_a']!=o['strategy_b']
        assert o.get('winner') in {o['strategy_a'],o['strategy_b'],'TIE'}
        assert isinstance(o.get('semantic_digest'),str) and len(o['semantic_digest'])==64
        assert float(o.get('seconds_a',-1))>=0 and float(o.get('seconds_b',-1))>=0
        derived_gap,derived_winner=derive_pair_outcome(o,tie_threshold)
        assert math.isclose(float(o.get('relative_gap')),
                            derived_gap,rel_tol=1e-9,abs_tol=1e-12), \
            f"pair relative_gap mismatch for {oid}"
        assert o.get('winner')==derived_winner, f"pair winner mismatch for {oid}"
        pairs.append(o)
    summary=pair_doc.get('summary',{})
    assert summary.get('observed_pairs')==len(pairs)
    assert summary.get('distinct_runs')==len({str(o['run_id']) for o in pairs})
    assert summary.get('distinct_source_shas')==len({o['source_sha'] for o in pairs})

stats=defaultdict(lambda:{'wins':0.0,'losses':0.0,'ties':0})
for o in pairs:
    a,b,w=o['strategy_a'],o['strategy_b'],o['winner']
    if w=='TIE':
        stats[a]['wins']+=0.5; stats[a]['losses']+=0.5; stats[a]['ties']+=1
        stats[b]['wins']+=0.5; stats[b]['losses']+=0.5; stats[b]['ties']+=1
    elif w==a:
        stats[a]['wins']+=1.0; stats[b]['losses']+=1.0
    else:
        stats[b]['wins']+=1.0; stats[a]['losses']+=1.0

bt_nodes=[]
if stats:
    strategies=sorted(stats)
    assert len(strategies)==2, 'BT v1 control supports exactly two strategies; >2 requires a validated joint-fit contract'
    a,b=strategies
    strength_a,strength_b=two_node_bt_abilities(stats[a]['wins'],stats[b]['wins'])
    strengths={a:strength_a,b:strength_b}
    denom=sum(math.exp(v) for v in strengths.values()) or 1.0
    for s in strategies:
        strength=strengths[s]
        bt_nodes.append({'strategy':s,'bt_log_strength':strength,'normalized_strength':math.exp(strength)/denom,**stats[s]})

bt_ready=len(pairs)>=policy['bt_gate']['min_observed_pairwise_comparisons']

# Canonical frontier PCA is kept separate from the crew-row PCA above. It is a
# task/resource/habitat allocation model and must not be misread as competency PCA.
frontier_pca={'status':'DEFER_NO_CANONICAL_FRONTIER_CONTROL_RETURN'}
frontier_control=history/'FRONTIER_CONTROL_RETURN_v1.json'
if frontier_control.exists():
    fc=json.loads(frontier_control.read_text())
    assert fc.get('schema')=='missioncontrol.crew_frontier_control_return.v1'
    assert fc.get('status')=='CONTROL_ACCEPTED_REPEAT'
    gate=fc['repeat_gate']
    assert gate['distinct_runs']>=2 and gate['distinct_source_shas']>=2
    assert gate['all_16_of_16_accepted'] and gate['pca_ready_all_runs'] and gate['bt_ready_all_runs']
    assert gate['zero_competency_promotions'] and gate['authority_transfer'] is False
    assert fc['rex_control']['persistent_or_regression_total']==0
    eruns=fc['evidence_runs']
    latest=next((r for r in eruns if r.get('evidence_class')=='MERGED_MASTER'),eruns[-1])
    pc1=[r['pca']['components'][0]['explained_variance_ratio'] for r in eruns]
    pc2=[r['pca']['components'][1]['explained_variance_ratio'] for r in eruns]
    frontier_pca={
      'status':'CONTROL_READY_MEASURED_REPEAT',
      'repeat_runs':len(eruns),'distinct_source_shas':len({r['source_sha'] for r in eruns}),
      'feature_count':latest['pca']['feature_count'],'components':latest['pca']['components'],
      'pc1_explained_range':[min(pc1),max(pc1)],'pc2_explained_range':[min(pc2),max(pc2)],
      'max_abs_explained_delta':max(max(pc1)-min(pc1),max(pc2)-min(pc2)),
      'rex_persistent_or_regression_total':fc['rex_control']['persistent_or_regression_total']
    }

out={
 'schema':'missioncontrol.measured_crew_allocation_receipt.v1',
 'receipt_count':len(receipts),'returned_run_count':len({r['run_id'] for r in receipts if r.get('evidence_return_status')}),
 'rows':rows,
 'allocation_eligible_rows':len(eligible_rows),
 'pca':{'status':pca_status,'measured_rows':len(rows),'eligible_rows':len(eligible_rows),'varying_features':varying,'variance_population':'ALLOCATION_ELIGIBLE_ONLY'},
 'frontier_pca':frontier_pca,
 'bt':{
   'status':'READY_OBSERVED' if bt_ready else policy['bt_gate']['status_before_gate'],
   'observed_pairs':len(pairs),
   'nodes':bt_nodes,
   'model_contract':'TWO_NODE_BT_LOG_ODDS_V1',
   'raw_timing_consistency':'FAIL_CLOSED',
   'analytic_fixture':'PASS'
 },
 'competency_promotions':0,'authority_transfer':False
}
out['returned_run_count']=len({str(r['run_id']) for r in receipts if r.get('evidence_return_status')})
out['canonical_rejected_run_count']=len({
    str(r['run_id']) for r in receipts
    if r.get('evidence_return_status')=='REJECTED_EXACT_SHA_RUNTIME_RETURN'
})
out['canonical_rejected_observation_count']=sum(
    1 for r in receipts
    if r.get('evidence_return_status')=='REJECTED_EXACT_SHA_RUNTIME_RETURN'
    and r.get('disposition')=='REJECT'
)
out['negative_evidence_promotion_credit']=0
out['negative_evidence_pca_bt_eligible']=False

out_path=Path(os.environ.get('MEASURED_ALLOCATION_OUT', ROOT/'MEASURED_ALLOCATION_RECEIPT.json'))
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
print(json.dumps(out,sort_keys=True))
