"""Fail-closed GOGREEN source-bound test counts and scoped branch/statement coverage."""
from __future__ import annotations
import argparse,hashlib,json,re,subprocess
from pathlib import Path
SHA40=re.compile(r'[0-9a-f]{40}\Z')
REPO=re.compile(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z')
TESTS=re.compile(r'(?m)^Ran ([0-9]+) tests in [0-9.]+s\s*$')
OK=re.compile(r'(?m)^OK(?: \(skipped=([0-9]+)\))?\s*$')

def sha256(raw):
    return hashlib.sha256(raw).hexdigest()

def positive_count(value):
    if type(value) is not int or value < 0:
        raise ValueError('invalid coverage count')
    return value

def produce(coverage_bytes,log_bytes,repository,expected_sha,checked_out_sha,wave_id,comparison=None):
    if (not isinstance(repository,str) or not REPO.fullmatch(repository)
            or not isinstance(expected_sha,str) or not SHA40.fullmatch(expected_sha)
            or checked_out_sha!=expected_sha):
        raise ValueError('exact checkout/repository provenance mismatch')
    if not isinstance(wave_id,str) or not re.fullmatch(r'G[0-9]+-P[0-9]+',wave_id):
        raise ValueError('invalid wave identity')
    text=log_bytes.decode('utf-8')
    matches=TESTS.findall(text)
    oks=OK.findall(text)
    if len(matches)!=1 or len(oks)!=1:
        raise ValueError('missing or ambiguous successful unittest terminal proof')
    executed=int(matches[0])
    skipped=int(oks[0]) if oks[0] else 0
    if executed<1 or skipped>=executed:
        raise ValueError('zero-passing or nonreconciling test denominator')
    cov=json.loads(coverage_bytes)
    meta=cov.get('meta')
    if not isinstance(meta,dict) or meta.get('branch_coverage') is not True or not meta.get('version'):
        raise ValueError('missing branch mode and coverage tool version')
    files=cov.get('files')
    if not isinstance(files,dict) or not files:
        raise ValueError('missing coverage production file census')
    production={}
    for name,record in files.items():
        normal=str(name).replace('\\','/')
        # Count only canonical repository-relative production paths. A file under
        # another root containing this fragment is not part of the GOGREEN cohort.
        # Reject aliases rather than silently manufacturing a coverage denominator.
        if 'mission-control/gogreen/' in normal:
            parts=normal.split('/')
            if parts[:2]!=['mission-control','gogreen'] or any(
                    part in ('','.','..') for part in parts):
                raise ValueError('ambiguous coverage production path')
        if not normal.startswith('mission-control/gogreen/') or '/tests/' in normal or not normal.endswith('.py'):
            continue
        sums=record.get('summary')
        if not isinstance(sums,dict):
            raise ValueError('invalid coverage module summary')
        n={k:positive_count(sums.get(k)) for k in
           ('num_statements','covered_lines','num_branches','covered_branches')}
        if (n['num_statements']==0 or n['covered_lines']>n['num_statements']
                or n['covered_branches']>n['num_branches']):
            raise ValueError('incoherent coverage numerator or denominator')
        if normal in production:
            raise ValueError('duplicate normalized production path')
        production[normal]=n
    if not production:
        raise ValueError('no production files eligible')
    covered_lines=sum(x['covered_lines'] for x in production.values())
    lines=sum(x['num_statements'] for x in production.values())
    covered_branches=sum(x['covered_branches'] for x in production.values())
    branches=sum(x['num_branches'] for x in production.values())
    # Breadth-first, measured-cohort-only zero coverage census. This is not
    # a repository inventory or an authenticated 42-cell federation reading.
    zero_statement_modules=sorted(k for k,v in production.items()
        if v['covered_lines']==0)
    zero_branch_modules=sorted(k for k,v in production.items()
        if v['num_branches']>0 and v['covered_branches']==0)
    n=covered_lines+covered_branches
    d=lines+branches
    result={'schema':'gogreen.pulse.metrics.v1','wave_id':wave_id,
        'repository':repository,'source_sha':expected_sha,
        'source_checkout_matched':True,'coverage_tool_version':meta['version'],
        'coverage_mode':'STATEMENTS_PLUS_BRANCHES',
        'test_selection':'unittest discover -s mission-control/gogreen/tests',
        'tests':{'executed':executed,'passed':executed-skipped,'failed':0,'skipped':skipped},
        'coverage':{'covered_statements':covered_lines,'eligible_statements':lines,
                    'covered_branches':covered_branches,'eligible_branches':branches,
                    'combined_covered':n,'combined_eligible':d,
                    'combined_percent':round(100*n/d,4),'production_modules':production,
                    'zero_statement_modules':zero_statement_modules,
                    'zero_branch_modules':zero_branch_modules,
                    'nonzero_statement_modules':len(production)-len(zero_statement_modules),
                    'measured_zero_gate':('FAIL' if zero_statement_modules or zero_branch_modules
                                          else 'PASS_MEASURED_COHORT_ONLY'),
                    'inventory_scope':'COVERAGE_JSON_REPORTED_ONLY'},
        'comparability':'NO_BASELINE_SUPPLIED','comparable_delta_pp':None,
        'comparable_zero_statement_delta':None,'comparable_zero_branch_delta':None,
        'evidence_source':'LOCAL_OR_CI_PRODUCER_NOT_EXTERNAL_GITHUB_AUTHENTICATION',
        'coverage_json_sha256':sha256(coverage_bytes),'unittest_log_sha256':sha256(log_bytes),
        'native_artifact_bytes_verified':False,'real_child_capacity':None,
        'statistical_independence':None,'merge_authorized':False,'child_acceptance':'DEFER'}
    if comparison is not None:
        old=comparison
        old_cov=old.get('coverage',{})
        old_mod=old_cov.get('production_modules',{})
        comparable=(old.get('schema')==result['schema']
            and old.get('repository')==repository
            and old.get('coverage_tool_version')==meta['version']
            and old.get('coverage_mode')==result['coverage_mode']
            and old.get('test_selection')==result['test_selection']
            and set(old_mod)==set(production)
            and all(old_mod[k].get('num_statements')==production[k]['num_statements']
                and old_mod[k].get('num_branches')==production[k]['num_branches']
                for k in production))
        result['comparability']='MATCHED_SCOPE' if comparable else 'INCOMPARABLE_SCOPE_OR_TOOL'
        if comparable:
            # Scope equality is necessary but not sufficient. Recompute every
            # baseline aggregate from its constituent per-module counts before
            # permitting a numerical wave-to-wave delta.
            keys=('num_statements','covered_lines','num_branches','covered_branches')
            if old.get('source_checkout_matched') is not True or old.get('merge_authorized') is not False:
                raise ValueError('baseline coverage integrity: provenance or authority')
            if any(type(m.get(k)) is not int or m[k]<0 for m in old_mod.values() for k in keys):
                raise ValueError('baseline coverage integrity: invalid module count')
            if any(m['num_statements']==0 or m['covered_lines']>m['num_statements']
                   or m['covered_branches']>m['num_branches'] for m in old_mod.values()):
                raise ValueError('baseline coverage integrity: incoherent module count')
            sums={k:sum(m[k] for m in old_mod.values()) for k in keys}
            old_covered=sums['covered_lines']+sums['covered_branches']
            old_eligible=sums['num_statements']+sums['num_branches']
            required={'covered_statements':sums['covered_lines'],
                      'eligible_statements':sums['num_statements'],
                      'covered_branches':sums['covered_branches'],
                      'eligible_branches':sums['num_branches'],
                      'combined_covered':old_covered,
                      'combined_eligible':old_eligible,
                      'combined_percent':round(100*old_covered/old_eligible,4)}
            if any(old_cov.get(k)!=v for k,v in required.items()):
                raise ValueError('baseline coverage integrity: aggregate mismatch')
            result['comparable_delta_pp']=round(result['coverage']['combined_percent']
                - required['combined_percent'],4)
            old_zero_statement=sum(m['covered_lines']==0 for m in old_mod.values())
            old_zero_branch=sum(m['num_branches']>0 and m['covered_branches']==0
                for m in old_mod.values())
            result['comparable_zero_statement_delta']=(
                len(zero_statement_modules)-old_zero_statement)
            result['comparable_zero_branch_delta']=(
                len(zero_branch_modules)-old_zero_branch)
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--coverage-json',type=Path,required=True)
    p.add_argument('--unittest-log',type=Path,required=True)
    p.add_argument('--repository',required=True)
    p.add_argument('--expected-sha',required=True)
    p.add_argument('--wave-id',default='G2-P1')
    p.add_argument('--baseline',type=Path)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    comparison=json.loads(args.baseline.read_text()) if args.baseline else None
    report=produce(args.coverage_json.read_bytes(),args.unittest_log.read_bytes(),
        args.repository,args.expected_sha,head,args.wave_id,comparison)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    raw=(json.dumps(report,indent=2,sort_keys=True)+'\n').encode()
    args.output.write_bytes(raw)
    manifest={'schema':'gogreen.pulse.files.v1','source_sha':head,
              'sha256':{args.coverage_json.name:sha256(args.coverage_json.read_bytes()),
                        args.unittest_log.name:sha256(args.unittest_log.read_bytes()),
                        args.output.name:sha256(raw)}}
    (args.output.parent/'pulse_manifest.json').write_text(
        json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'tests':report['tests'],'coverage':report['coverage']['combined_percent'],
        'comparability':report['comparability'],'merge_authorized':False}))

if __name__=='__main__':
    main()
