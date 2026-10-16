"""Read-only GOGREEN regime and queue-wave receipts; never authorizes CI/admission."""
from __future__ import annotations
import json, hashlib, re, math
from datetime import datetime, timezone
from pathlib import Path

SHA = re.compile(r'^[0-9a-f]{40}$')
REGIMES = ('CONGESTED','RECOVERING','STABLE')

def _utc(s):
    if not isinstance(s,str): raise ValueError('missing UTC clock')
    try: dt = datetime.fromisoformat(s.replace('Z','+00:00'))
    except ValueError as e: raise ValueError('bad timestamp') from e
    if dt.utcoffset() is None or dt.utcoffset().total_seconds() != 0: raise ValueError('UTC required')
    return dt

def _number(x):
    if type(x) is not int or x<0: raise ValueError('nonnegative integer required')
    return x

def _count_or_unknown(x):
    return None if x is None else _number(x)

def _ids(x):
    if x is None: return None
    if not isinstance(x,list) or any(type(v) is not int or v<=0 for v in x) or len(set(x)) != len(x):
        raise ValueError('unique positive run IDs required')
    return sorted(x)

def _quantile(values,p):
    if not values: return None
    s=sorted(values)
    return round(s[math.ceil(p*len(s))-1],3)

def validate(x):
    if not isinstance(x,dict) or x.get('schema')!='gogreen.queue-wave.v1': raise ValueError('schema')
    if not isinstance(x.get('repo'),str) or '/' not in x['repo']: raise ValueError('repo')
    if not isinstance(x.get('sha'),str) or not SHA.fullmatch(x['sha']): raise ValueError('sha')
    _utc(x.get('observed_at'))
    _number(x.get('queued'))
    for k in ('new_run_ids','exited_run_ids','queued_run_ids'):_ids(x.get(k))
    if x.get('queued_run_ids') is not None and len(x['queued_run_ids']) != x['queued']:
        raise ValueError('incomplete queue IDs cannot be represented as complete')
    age=x.get('queue_age_seconds')
    if age is not None and (not isinstance(age,list) or any(type(z) not in (int,float) or not math.isfinite(z) or z<0 for z in age)):
        raise ValueError('queue ages')
    for k in ('pass','fail','cancelled'): _count_or_unknown(x.get('terminal',{}).get(k))
    cov=x.get('coverage')
    if cov is not None:
        if not isinstance(cov,dict): raise ValueError('coverage')
        for key in ('covered','eligible'):_number(cov.get(key))
        if cov['eligible']==0 or cov['covered']>cov['eligible']:raise ValueError('coverage denominator')
        if not cov.get('scope') or not cov.get('tool') or not cov.get('selection'):raise ValueError('coverage contract')
        if cov.get('sha')!=x['sha']:raise ValueError('coverage source mismatch')
    wc=x.get('worker_cost_minutes')
    if wc is not None and (type(wc) not in (int,float) or not math.isfinite(wc) or wc<0):raise ValueError('worker cost')
    roots=x.get('verified_closed_root_ids')
    if roots is not None and (not isinstance(roots,list) or len(set(roots))!=len(roots) or any(not isinstance(z,str) or not z for z in roots)):
        raise ValueError('closed roots')
    return x

def _coverage_delta(a,b):
    x,y=a.get('coverage'),b.get('coverage')
    if x is None or y is None:return None
    fields=('eligible','scope','tool','selection')
    if any(x[z]!=y[z] for z in fields):return None
    return round(100*(y['covered']-x['covered'])/x['eligible'],4)

def wave(previous,current,runner_proof=False,tests_proof=False,no_first_red=False,requested='RECOVERING'):
    a,b=validate(previous),validate(current)
    if a['repo']!=b['repo'] or a['sha']!=b['sha']:raise ValueError('unmatched source cohort')
    if _utc(a['observed_at'])>=_utc(b['observed_at']):raise ValueError('nonincreasing observations')
    if requested not in REGIMES:raise ValueError('regime')
    old,new=a.get('queued_run_ids'),b.get('queued_run_ids')
    arrivals=sorted(set(new)-set(old)) if old is not None and new is not None else None
    exits=sorted(set(old)-set(new)) if old is not None and new is not None else None
    if b.get('new_run_ids') is not None and arrivals is not None and sorted(b['new_run_ids'])!=arrivals:raise ValueError('arrival identity disagreement')
    if b.get('exited_run_ids') is not None and exits is not None and sorted(b['exited_run_ids'])!=exits:raise ValueError('exit identity disagreement')
    ages=b.get('queue_age_seconds')
    root_ids=b.get('verified_closed_root_ids')
    gates={'two_comparable_observations':True,'runner_evidence':runner_proof is True,
           'test_evidence':tests_proof is True,'no_new_disqualifying_first_red':no_first_red is True,
           'complete_run_identity':arrivals is not None}
    promoted=all(gates[k] for k in ('two_comparable_observations','runner_evidence','test_evidence','no_new_disqualifying_first_red'))
    # No statistical threshold or worker capacity is inferred from queue counts.
    # Stable additionally requires a non-growing queue and complete ID reconciliation.
    if requested == 'STABLE':
        promoted = promoted and b['queued'] <= a['queued'] and arrivals is not None
    regime=requested if promoted else 'CONGESTED'
    return {'schema':'gogreen.queue-wave.receipt.v1','source_sha':b['sha'],'repo':b['repo'],
            'from_at':a['observed_at'],'to_at':b['observed_at'],'queued_before':a['queued'],
            'queued_after':b['queued'],'queued_delta':b['queued']-a['queued'],
            'new_run_ids':arrivals,'exited_run_ids':exits,
            'new_run_ids_count':len(arrivals) if arrivals is not None else None,
            'exited_run_ids_count':len(exits) if exits is not None else None,
            'queue_age_p50_seconds':_quantile(ages,.5) if ages is not None else None,
            'queue_age_p95_seconds':_quantile(ages,.95) if ages is not None else None,
            'terminal':{k:b.get('terminal',{}).get(k) for k in ('pass','fail','cancelled')},
            'coverage_delta_pp':_coverage_delta(a,b),'worker_cost_minutes':b.get('worker_cost_minutes'),
            'independently_verified_root_closures':len(root_ids) if root_ids is not None else None,
            'root_ids':root_ids,'gates':gates,'requested_regime':requested,'regime':regime,
            'queue_decrease_not_root_closure':True,'dispatch_authorized':False,
            'merge_authorized':False,'security_waiver':False,'qps_disposition':'DEFER'}

def emit(receipt,out):
    p=Path(out);p.mkdir(parents=True,exist_ok=True)
    raw=(json.dumps(receipt,sort_keys=True,indent=2)+'\n').encode();(p/'regime_receipt.json').write_bytes(raw)
    digest=hashlib.sha256(raw).hexdigest()
    (p/'regime_manifest.json').write_text(json.dumps({'schema':'gogreen.regime.manifest.v1','sha256':{'regime_receipt.json':digest},'authority_transfer':False},sort_keys=True)+'\n')
    return digest
