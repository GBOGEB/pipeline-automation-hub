"""GOGREEN G5 second native evidence pulse: append-only historical observation delta.

An exact-SHA green workflow/job is only metadata. This module never infers test
counts, coverage numerators, defect/root closure, independent trials, or approval.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from spine import build

SCHEMA = 'gogreen.g5.incremental-pulse.v1'

def analyze(g0, g1, g2):
    if not all(isinstance(p,dict) for p in (g0,g1,g2)):
        raise ValueError('typed intake objects required')
    if g0.get('repositories') != g1.get('repositories') or g1.get('repositories') != g2.get('repositories'):
        raise ValueError('denominator or exact-catalog drift')
    metrics=[]
    for x in (g0,g1,g2):
        evidence,_,_=build(x)
        metrics.append(evidence)
    baseline={ (o['repository'],o['run_id'],o['run_attempt'],o['job_id']):o for o in g0['observations'] }
    old={ (o['repository'],o['run_id'],o['run_attempt'],o['job_id']):o for o in g1['observations'] }
    new={ (o['repository'],o['run_id'],o['run_attempt'],o['job_id']):o for o in g2['observations'] }
    if len(old)!=len(g1['observations']) or len(new)!=len(g2['observations']):
        raise ValueError('duplicate source observation identity')
    if not all(old.get(k)==v for k,v in baseline.items()):
        raise ValueError('historical G0 overwritten')
    if not all(new.get(k)==v for k,v in old.items()):
        raise ValueError('historical G1 overwritten')
    extra=[r for r in metrics[2]['observations'] if (r['repository'],r['run_id'],r['run_attempt'],r['job_id']) not in old]
    if len(extra)!=2 or {(r['repository'],r['family']) for r in extra}!={('GBOGEB/ABACUS','security'),('GBOGEB/ABACUS','coverage')}:
        raise ValueError('unreviewed G2 extra observations')
    if any(r['status']!='NATIVE_PASS_STATUS_ONLY' or r['test_counts'] is not None or r['artifact_bytes_verified'] for r in extra):
        raise ValueError('status-only evidence illegally promoted')
    denoms=[m['breadth']['catalog_repo_family_cells'] for m in metrics]
    if denoms != [42,42,42]:
        raise ValueError('population not scope matched')
    observed=[m['breadth']['observed_cells'] for m in metrics]
    if observed != [1,6,8]:
        raise ValueError('nonmatching observed-cell deltas')
    result={'schema':SCHEMA, 'fixed_repositories':6,'fixed_cells':42,
            'pulses':[{'wave':f'G{i}', 'observed_cells':observed[i], 'unobserved_cells':42-observed[i],
              'breadth_pct':round(observed[i]*100/42,4), 'new_cells':observed[i]-(observed[i-1] if i else 0),
              'native_status_only_obs':metrics[i]['breadth']['native_green_status_only_observations']}
              for i in range(3)],
            'increment':{'source_repo':'GBOGEB/ABACUS','observation_count':len(extra),
              'families':sorted([r['family'] for r in extra]),
              'exact_sha':extra[0]['source_sha'],
              'run_job_pairs':sorted([{'run_id':r['run_id'],'job_id':r['job_id'],'attempt':r['run_attempt']} for r in extra],key=lambda o:o['run_id']),
              'matched_security_fingerprint_change':None,'coverage_numerator':None,'coverage_denominator':None,
              'verified_roots_closed':None},
            'fan_out':{'staged_readonly_packets':6, 'max_parallel_workers':2,'actual_dispatched':0,
              'worker_capacity':None,'repo_overlap_allowed':False},
            'prediction':{'N_plus_1':'SOURCE_BOUND_NATIVE_VERIFY_G5_G2','N_plus_2':'INDEPENDENT_CONSUMER_RECEIPT_REPLAY',
              'calibrated_probability':None},
            'authority_transfer':False, 'dispatch_authorized':False, 'merge_authorized':False,
            'qps_disposition':'DEFER','pca_ready':False,'3pstar_ready':False}
    return result

def emit(report,out):
    out.mkdir(parents=True,exist_ok=True)
    raw=(json.dumps(report,sort_keys=True,indent=2)+'\n').encode()
    digest=hashlib.sha256(raw).hexdigest()
    (out/'incremental_pulses.json').write_bytes(raw)
    (out/'incremental_pulses.sha256').write_text(digest+'\n')
    rows=['# GOGREEN incremental wave census','','| Wave | Observed | Breadth | New cells | Status only |',
          '|---|---:|---:|---:|---:|']
    for p in report['pulses']:
        rows.append(f"| {p['wave']} | {p['observed_cells']}/42 | {p['breadth_pct']:.2f}% | {p['new_cells']} | {p['native_status_only_obs']} |")
    rows+=['','All gains concern historical source-bound metadata cells. No native depth or numerical code coverage gain is inferred.','', 'SHA-256: '+digest, '']
    (out/'incremental_pulses.md').write_text('\n'.join(rows))
    return digest

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--g0',type=Path,required=True);p.add_argument('--g1',type=Path,required=True)
    p.add_argument('--g2',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    d=[json.loads(p.read_text()) for p in (a.g0,a.g1,a.g2)]
    result=analyze(*d);emit(result,a.out)
    print(json.dumps({'waves':[p['observed_cells'] for p in result['pulses']], 'source':result['increment']['exact_sha']}))

if __name__=='__main__': main()
