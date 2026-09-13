#!/usr/bin/env python3
import json, statistics
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parent
policy=json.loads((ROOT/'MEASURED_ALLOCATION_POLICY_v1.json').read_text())
receipts=[]

# Live exact-SHA runtime receipts produced by the current job.
receipts_dir=ROOT/'receipts'
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
history=ROOT/'history'
if history.exists():
    for p in sorted(history.glob('RUN_RETURN_*.json')):
        doc=json.loads(p.read_text())
        if doc.get('schema')!='missioncontrol.measured_task_run_return.v1':
            continue
        if doc.get('status')!='ACCEPTED_EXACT_SHA_RUNTIME_RETURN':
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

varying=0
feature_names=['demonstrated_level','acceptance_rate','distinct_accepted_runs','distinct_source_shas','mean_execute_seconds','rex_trigger_rate']
for f in feature_names:
    vals=[r[f] for r in rows if r[f] is not None]
    if len(vals)>=2 and len(set(vals))>1:
        varying+=1
eligible_rows=[r for r in rows if r['allocation_eligible']]
pca_ready=len(eligible_rows)>=policy['pca_gate']['min_measured_rows'] and varying>=policy['pca_gate']['min_varying_features']
pairwise_path=ROOT/'PAIRWISE_OBSERVATIONS.json'
pairs=[]
if pairwise_path.exists():
    pairs=json.loads(pairwise_path.read_text()).get('observations',[])
bt_ready=len(pairs)>=policy['bt_gate']['min_observed_pairwise_comparisons']

if pca_ready:
    pca_status='READY'
elif len(eligible_rows)<policy['pca_gate']['min_measured_rows']:
    pca_status='DEFER_INSUFFICIENT_ELIGIBLE_MEASURED_ROWS'
else:
    pca_status='DEFER_INSUFFICIENT_MEASURED_VARIANCE'

out={
 'schema':'missioncontrol.measured_crew_allocation_receipt.v1',
 'receipt_count':len(receipts),'returned_run_count':len({r['run_id'] for r in receipts if r.get('evidence_return_status')}),
 'rows':rows,
 'allocation_eligible_rows':len(eligible_rows),
 'pca':{'status':pca_status,'measured_rows':len(rows),'eligible_rows':len(eligible_rows),'varying_features':varying},
 'bt':{'status':'READY' if bt_ready else policy['bt_gate']['status_before_gate'],'observed_pairs':len(pairs)},
 'competency_promotions':0,'authority_transfer':False
}
(ROOT/'MEASURED_ALLOCATION_RECEIPT.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
print(json.dumps(out,sort_keys=True))
