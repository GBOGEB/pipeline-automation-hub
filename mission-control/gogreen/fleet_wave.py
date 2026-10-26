#!/usr/bin/env python3
"""G4: bounded MissionControl-Wide census and staged, disjoint scout packets.

NO network, execution, mutation, merge admission or QPS acceptance. Historical
pinned catalogues are historical, never called current without a fresh readback.
"""
from __future__ import annotations
import argparse, hashlib, json, re
from pathlib import Path
from spine import build, _check_catalog, canonical

DOMAINS=('MIP','DMAIC','PCA_BT','REX','LDAB_LLDB','CENSUS','THREE_P_STAR','QPS_TRIAGE')
PRIORITY={'ci_contract':0,'security':0,'coverage':1,'federation':1,
          'runtime':2,'qps_triage':2,'math_model':3,'artifact':3}


def digest(o):
    return hashlib.sha256(canonical(o).encode()).hexdigest()


def checked_scout(scout,catalog):
    if (not isinstance(scout,dict) or scout.get('schema')!='gogreen.readonly-scout.v1'
        or scout.get('mode')!='PASSIVE_GET_ONLY' or scout.get('worker_dispatches')!=0
        or scout.get('external_authority_transfer') is not False
        or scout.get('security_waiver') is not False or scout.get('complete_fleet_census') is not False):
        raise ValueError('untrusted scout source or authority claim')
    runs,jobs=scout.get('requested_runs_per_repo'),scout.get('requested_jobs_per_run')
    if type(runs) is not int or type(jobs) is not int or not 1<=runs<=8 or not 1<=jobs<=8:
        raise ValueError('invalid bounded sample budget')
    rows=scout.get('repositories')
    if not isinstance(rows,list) or len(rows)!=len(catalog):
        raise ValueError('missing repository census')
    found=set()
    for r in rows:
        if (not isinstance(r,dict) or r.get('repository') not in catalog
            or r['repository'] in found
            or r.get('source_sha')!=catalog[r['repository']]['head_sha']):
            raise ValueError('duplicate/stale source SHA in scout')
        found.add(r['repository'])
        if (type(r.get('runs_considered')) is not int or not 0<=r['runs_considered']<=runs
            or type(r.get('successful_jobs_seen')) is not int
            or not 0<=r['successful_jobs_seen']<=runs*jobs):
            raise ValueError('impossible observation cardinality')
        if (r.get('fetch_state') not in ('UNKNOWN','UNKNOWN_ERROR','OBSERVED_PARTIAL_SAMPLE')
            or r.get('truncated') not in (True,False,None)):
            raise ValueError('invalid partial census classification')
    bad=scout.get('unattributed_non_green');errors=scout.get('collection_errors')
    if not isinstance(bad,list) or not isinstance(errors,list):
        raise ValueError('missing first-red and error ledgers')
    if any(not isinstance(e,dict) or e.get('repository') not in catalog for e in bad+errors):
        raise ValueError('unattributed error/first-red outside declared scope')
    return rows,bad,errors


def rollup(intake,scout,pulse='G4-P0',prior=None,max_packets=8):
    if not isinstance(pulse,str) or not re.fullmatch(r'G\d+-P\d+',pulse):
        raise ValueError('invalid pulse identity')
    if type(max_packets) is not int or not 1<=max_packets<=8:
        raise ValueError('disjoint fanout cap exceeded')
    evidence,_,_=build(intake)
    catalog=_check_catalog(intake['repositories'])
    rows,non_green,errors=checked_scout(scout,catalog)
    cells={(repo,f) for repo,p in catalog.items() for f in p['target_families']}
    observed={(o['repository'],o['family']) for o in evidence['observations']}
    qualified={(o['repository'],o['family']) for o in evidence['observations']
               if o['status'] in ('NATIVE_PASS_METADATA','NATIVE_PASS_BYTES_VERIFIED')}
    proven={(o['repository'],o['family']) for o in evidence['observations']
            if o['status']=='NATIVE_PASS_BYTES_VERIFIED'}
    packets=[]
    for i,(repo,family) in enumerate(sorted(cells-observed,
            key=lambda t:(PRIORITY[t[1]],t[0],t[1]))[:max_packets]):
        packets.append({'id':f'{pulse}-S{i+1:02d}','repo':repo,
                        'sha':catalog[repo]['head_sha'],'family':family,
                        'state':'STAGED_NOT_LAUNCHED','mutation':False,
                        'root_id':None,'owner':'UNASSIGNED','disposition':'UNKNOWN'})
    m={'catalog_repos':len(catalog),'reachable_repos':sum(r['fetch_state']=='OBSERVED_PARTIAL_SAMPLE' for r in rows),
       'candidate_cells':len(cells),'observed_cells':len(observed),'status_only_cells':len({(o['repository'],o['family']) for o in evidence['observations'] if o['status']=='NATIVE_PASS_STATUS_ONLY'}),
       'producer_metadata_cells':len(qualified),'verified_bytes_cells':len(proven),
       'unobserved_cells':len(cells-observed),'sampled_runs':sum(r['runs_considered'] for r in rows),
       'sampled_successful_jobs':sum(r['successful_jobs_seen'] for r in rows),
       'truncated_repos':sum(r['truncated'] is True for r in rows),
       'unattributed_first_reds':len(non_green),'collection_errors':len(errors),
       'packets_staged':len(packets),'packets_launched':0,
       'root_closure':None,'rex_accepted':None,'lldb_authenticated':None,
       'real_worker_capacity':None,'statistically_independent_trials':None,
       'matched_coverage_delta_pp':None}
    result={'schema':'gogreen.fleet-wave.v1','pulse':pulse,
            'catalog_sha256':digest(intake['repositories']),
            'input_sha256':digest(intake),'scout_sha256':digest(scout),
            'sample_limit':{'runs_per_repo':scout['requested_runs_per_repo'],
                            'jobs_per_run':scout['requested_jobs_per_run']},
            'metrics':m,'packets':packets,
            'repos':[{k:r.get(k) for k in ('repository','source_sha','fetch_state','runs_considered','successful_jobs_seen','truncated')} for r in rows],
            'domains':{d:{'state':'UNKNOWN','qualified_receipts':None,'admission':'DEFER' if d=='QPS_TRIAGE' else 'NOT_ESTABLISHED'} for d in DOMAINS},
            'merge_authorized':False,'security_waiver':False,
            'authority_transfer':False,'qps_disposition':'DEFER',
            'classification':'BOUNDED_METADATA_SAMPLE_NOT_NATIVE_CHILD_ACCEPTANCE'}
    if prior is not None:
        if not isinstance(prior,dict) or prior.get('schema')!=result['schema']:
            raise ValueError('invalid prior wave schema')
        if prior.get('catalog_sha256')==result['catalog_sha256']:
            result['delta']={'scope':'MATCHED_CATALOG',
                  'observed_cells':m['observed_cells']-prior['metrics']['observed_cells'],
                  'verified_bytes_cells':m['verified_bytes_cells']-prior['metrics']['verified_bytes_cells'],
                  'errors':m['collection_errors']-prior['metrics']['collection_errors']}
        else:
            result['delta']={'scope':'INCOMPARABLE_CATALOG','observed_cells':None,
                             'verified_bytes_cells':None,'errors':None}
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--intake',required=True,type=Path)
    ap.add_argument('--scout',required=True,type=Path)
    ap.add_argument('--baseline',type=Path)
    ap.add_argument('--pulse',default='G4-P0')
    ap.add_argument('--out',required=True,type=Path)
    x=ap.parse_args()
    data=lambda p: json.loads(p.read_text(encoding="utf-8")) if p else None
    obj=rollup(data(x.intake),data(x.scout),x.pulse,data(x.baseline))
    x.out.parent.mkdir(parents=True,exist_ok=True)
    x.out.write_text(json.dumps(obj,sort_keys=True,indent=2)+'\n',encoding="utf-8",newline="\n")
    print(canonical({'pulse':x.pulse,'metrics':obj['metrics'],'admission':'HOLD'}))

if __name__=='__main__':main()
