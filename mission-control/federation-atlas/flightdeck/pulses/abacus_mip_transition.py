"""Read-only N/N+1 workflow-name-matched telemetry transition (no inference)."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

SCHEMA='code-purple.mc.abacus-mip-transition.v1'
SHA=re.compile(r'[a-f0-9]{40}\Z')
TERMINAL={'success','failure','cancelled','neutral','skipped','timed_out',
          'stale','action_required','startup_failure'}


def require(ok,msg):
    if not ok: raise ValueError(msg)


def series(doc):
    require(isinstance(doc,dict) and doc.get('repository')=='GBOGEB/ABACUS'
            and isinstance(doc.get('source_sha'),str)
            and SHA.fullmatch(doc['source_sha'])
            and doc.get('acquisition')=='github-actions-rest-exact-pull-request-cohort'
            and doc.get('census_complete') is True,
            'native source cohort unbound')
    runs=doc.get('runs')
    require(isinstance(runs,list) and 0<len(runs)<=50
            and doc.get('run_attempts_observed')==len(runs),
            'run count missing or incomplete')
    output={};seen=set()
    for item in runs:
        require(isinstance(item,dict)
                and item.get('head_sha')==doc['source_sha']
                and isinstance(item.get('name'),str) and item['name']
                and type(item.get('id')) is int and item['id']>0
                and type(item.get('run_attempt')) is int and item['run_attempt']>0
                and item.get('status')=='completed'
                and item.get('conclusion') in TERMINAL,
                'nonterminal or mismatched run identity')
        identity=(item['id'],item['run_attempt'])
        require(identity not in seen,'duplicate run attempt')
        seen.add(identity)
        require(item['name'] not in output, 'same workflow name repeated in cohort')
        output[item['name']]=item['conclusion']
    return output


def compare(before,after,*,before_digest,after_digest):
    old,new=series(before),series(after)
    require(before['source_sha']!=after['source_sha'],
            'distinct source SHAs required')
    require(set(old)==set(new),'unmatched workflow-name cohort')
    require(len(old)>=2,'at least two matched workflow identities required')
    matrix={}
    rows=[]
    for name in sorted(old):
        a,b=old[name],new[name]
        key=a+' -> '+b
        matrix[key]=matrix.get(key,0)+1
        rows.append({'workflow':name,'before':a,'after':b,
                     'transition':key,'same_outcome':a==b})
    n=len(rows)
    was=sum(s=='success' for s in old.values())
    now=sum(s=='success' for s in new.values())
    gains=sum(row['before']!='success' and row['after']=='success' for row in rows)
    losses=sum(row['before']=='success' and row['after']!='success' for row in rows)
    require(gains-losses==now-was,'paired count conservation')
    return {
        'schema':SCHEMA,'source_repository':'GBOGEB/ABACUS',
        'source_sha_before':before['source_sha'],
        'source_sha_after':after['source_sha'],
        'native_input_sha256_before':before_digest,
        'native_input_sha256_after':after_digest,
        'matching':'EXACT_WORKFLOW_NAMES_ONLY_CONFIG_MATCH_UNVERIFIED',
        'population_matched':True,'n_matched_workflow_names':n,
        'success_before':was,'success_after':now,
        'success_share_before_pct':round(100*was/n,3),
        'success_share_after_pct':round(100*now/n,3),
        'success_delta_pp':round(100*(now-was)/n,3),
        'workflow_gains':gains,'workflow_losses':losses,
        'transitions':rows,'transition_matrix':dict(sorted(matrix.items())),
        'inferential':{
            'independent_process_waves':None,
            'paired_mcnemar_p':None,
            'pca_pc1_variance_pct':None,
            'bradley_terry_win_probability_pct':None,
            'anova_p':None,'manova_p':None,
            'confidence_intervals_90_95_99':{'90':None,'95':None,'99':None},
            'reason':'matched workflow identities are correlated CI manifestations; no independent repeated source process'},
        'evidence_class':'DESCRIPTIVE_NATIVE_GITHUB_RUN_METADATA',
        'root_closures':None,'authority_transfer':False,
        'merge_admission':'HOLD','qps_acceptance':'DEFER'
    }


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--before',required=True,type=Path)
    p.add_argument('--after',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    x=p.parse_args(argv)
    require(len({x.before.resolve(),x.after.resolve(),x.output.resolve()})==3,
            'input output file alias')
    docs=[];digests=[]
    for name in (x.before,x.after):
        require(name.is_file() and not name.is_symlink()
                and 0<name.stat().st_size<10_000_000,'unsafe native input')
        raw=name.read_bytes();docs.append(json.loads(raw))
        digests.append(hashlib.sha256(raw).hexdigest())
    result=compare(docs[0],docs[1],before_digest=digests[0],after_digest=digests[1])
    x.output.parent.mkdir(parents=True,exist_ok=True)
    x.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print('paired_descriptive_delta_pp='+str(result['success_delta_pp']))
    print('statistical_admission=HOLD')

if __name__=='__main__':
    main()
