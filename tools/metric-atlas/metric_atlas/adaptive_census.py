#!/usr/bin/env python3
"""Read-only governed census scaling: catalog -> 3 bounded slices -> partials -> diff.

Not a scheduler, GitHub publisher, debugger, or source-writing worker. Extends (does
not replace) pipeline-automation-hub/metric_atlas/census.py observation contract.
Every count is source-pinned and independent of merge/security/LDAB authority.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
from collections import Counter
from pathlib import Path, PurePosixPath

MANIFEST_SCHEMA = 'code-purple.adaptive-census.manifest.v1'
PARTIAL_SCHEMA = 'code-purple.adaptive-census.partial.v1'
ROLLUP_SCHEMA = 'code-purple.adaptive-census.rollup.v1'
SOURCE_SCHEMA = 'code-purple.branch-coverage-compact.v1'
SHA40 = re.compile(r'[a-f0-9]{40}\Z')
SHA64 = re.compile(r'[a-f0-9]{64}\Z')
ALLOWED_REPOS = {'GBOGEB/ABACUS', 'GBOGEB/CODEX', 'GBOGEB/cryoplant-project'}
STRATA = ('ZERO_COVERED', 'PARTIAL', 'FULLY_COVERED', 'ZERO_ELIGIBLE')

class CensusError(ValueError):
    pass

def canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(',', ':'))

def digest(obj):
    return hashlib.sha256(canonical(obj).encode('utf-8')).hexdigest()

def require(condition, message):
    if not condition:
        raise CensusError(message)

def valid_int(value, minimum=0):
    return type(value) is int and value >= minimum

def safe_path(name):
    require(isinstance(name, str) and bool(name) and '\\' not in name, 'bad path')
    p = PurePosixPath(name)
    require(not p.is_absolute() and '..' not in p.parts and str(p) == name, 'path traversal')
    return name

def summary(row):
    require(isinstance(row, dict) and isinstance(row.get('summary'), dict), 'module summary absent')
    s = row['summary']
    for f in ('num_branches', 'covered_branches', 'num_statements', 'covered_lines'):
        require(valid_int(s.get(f)), 'invalid '+f)
    require(s['covered_branches'] <= s['num_branches'] and s['covered_lines'] <= s['num_statements'], 'coverage overflow')
    ex = row.get('executed_branches')
    mi = row.get('missing_branches')
    require(isinstance(ex, list) and isinstance(mi, list), 'branch arcs missing')
    def convert(x):
        require(isinstance(x,list) and len(x)==2 and all(type(y) is int for y in x), 'malformed arc')
        return tuple(x)
    e = set(map(convert, ex))
    m = set(map(convert, mi))
    require(len(e)==len(ex) and len(m)==len(mi) and not(e & m), 'duplicate or overlapping arcs')
    require(len(e)==s['covered_branches'] and len(e)+len(m)==s['num_branches'], 'arc universe discrepancy')
    return s

def validate_source(obj):
    require(isinstance(obj,dict) and obj.get('schema')==SOURCE_SCHEMA, 'unknown coverage input')
    require(obj.get('repository') in ALLOWED_REPOS, 'repo outside canonical federation census allowlist')
    require(isinstance(obj.get('exact_head'),str) and SHA40.fullmatch(obj['exact_head']), 'invalid source SHA')
    require(obj.get('authority_transfer') is False and obj.get('merge_admission')=='HOLD', 'invalid authority')
    require(isinstance(obj.get('modules'),dict) and obj['modules'], 'no measured modules')
    totals = Counter()
    for name,row in obj['modules'].items():
        safe_path(name)
        s=summary(row)
        for key in ('num_branches','covered_branches','num_statements','covered_lines'):
            totals[key]+=s[key]
    require(dict(totals)==obj.get('canonical_totals'), 'source rollup parity failed')
    native=obj.get('artifact_zip_sha256')
    local=obj.get('local_report_sha256')
    require((native is None) != (local is None), 'exactly one native ZIP or local report digest required')
    proof=native or local
    require(isinstance(proof,str) and SHA64.fullmatch(proof), 'source evidence digest invalid')
    if local is not None:
        require(obj.get('evidence_class')=='LOCAL_COVERAGE_DECLARED_HEAD_NOT_NATIVE', 'local source falsely claiming native status')
    return obj

def adapt_coverage_json(report, *, repository, exact_head):
    """Convert a standard coverage.py JSON (branch=True) into a local-only census.

    The supplied exact_head is DECLARED, not authenticated against a checkout.
    Never emit native claims from this adapter.
    """
    require(repository in ALLOWED_REPOS, 'repository outside federation allowlist')
    require(isinstance(exact_head,str) and SHA40.fullmatch(exact_head), 'missing declared exact head')
    require(isinstance(report,dict) and isinstance(report.get('files'),dict) and report['files'], 'coverage.py files missing')
    modules={}
    totals=Counter()
    for path,row in report['files'].items():
        safe_path(path)
        s=summary(row)
        modules[path]={key:row[key] for key in ('executed_branches','missing_branches','summary')}
        for key in ('num_branches','covered_branches','num_statements','covered_lines'):
            totals[key]+=s[key]
    source={'schema':SOURCE_SCHEMA,'repository':repository,'exact_head':exact_head,
        'evidence_class':'LOCAL_COVERAGE_DECLARED_HEAD_NOT_NATIVE',
        'local_report_sha256':digest(report),'artifact_zip_sha256':None,
        'canonical_totals':dict(totals),'modules':modules,
        'authority_transfer':False,'merge_admission':'HOLD'}
    return validate_source(source)

def source_evidence_sha(source):
    return source.get('artifact_zip_sha256') or source.get('local_report_sha256')

def classify(s):
    if s['num_branches']==0: return 'ZERO_ELIGIBLE'
    if s['covered_branches']==0: return 'ZERO_COVERED'
    if s['covered_branches']==s['num_branches']: return 'FULLY_COVERED'
    return 'PARTIAL'

def select_order(source,seed):
    """Stratified controls + targeted opportunity picks; not random inference."""
    bystratum={k:[] for k in STRATA}
    for path,row in source['modules'].items():
        s=row['summary']
        bystratum[classify(s)].append(path)
    for group in bystratum.values():
        group.sort(key=lambda p: digest([seed,source['exact_head'],p]))
    calibrations=[]
    # Reproducible stratum mix in first slots, not an unbiased probability sample.
    while any(bystratum.values()):
        for name in STRATA:
            if bystratum[name]:calibrations.append(bystratum[name].pop(0))
    # Every fourth slot is breadth / calibration; other slots prefer missed arcs.
    targeted=sorted(source['modules'], key=lambda p:(
        -(source['modules'][p]['summary']['num_branches']-source['modules'][p]['summary']['covered_branches']),
        digest([seed,'target',p])))
    order=[]; seen=set();ca=iter(calibrations);ta=iter(targeted)
    for position in range(len(source['modules'])):
        channel='STRATIFIED_BREADTH' if position%4==0 else 'MISSED_ARC_PRIORITY'
        candidate=ca if channel=='STRATIFIED_BREADTH' else ta
        p=next((v for v in candidate if v not in seen),None)
        if p is None:
            p=next(v for v in source['modules'] if v not in seen)
        seen.add(p);order.append({'path':p,'selection_channel':channel,'stratum':classify(source['modules'][p]['summary'])})
    require(len(order)==len(source['modules']) and len({r['path'] for r in order})==len(order),'selection not disjoint')
    return order

def plan(source, *, caps=(8,16,32), seed='N6-20261017', max_readers=2):
    validate_source(source)
    require(isinstance(caps,(tuple,list)) and len(caps)==3 and all(valid_int(x,1) for x in caps), 'need 3 positive cumulative caps')
    require(0<caps[0]<caps[1]<caps[2]<=len(source['modules']), 'cumulative scope caps invalid')
    require(caps[1]<=2*caps[0] and caps[2]<=2*caps[1], 'growth >2x needs a separate approval')
    require(valid_int(max_readers,1) and max_readers<=4,'read-only concurrency cap exceeded')
    require(isinstance(seed,str) and re.fullmatch('[A-Za-z0-9_.-]{1,80}',seed),'bad seed')
    sequence=select_order(source,seed)
    slices=[];begin=0
    for i,end in enumerate(caps,1):
        rows=sequence[begin:end]
        s_id='CENSUS-'+digest([source['repository'],source['exact_head'],source_evidence_sha(source),seed,i,[r['path'] for r in rows]])[:20]
        slices.append({'pulse':i,'slice_id':s_id,'selected':rows,'incremental_modules':len(rows),'cumulative_modules':end,
            'release_condition':'STRUCTURAL_QA_PASS_READ_ONLY_ONLY', 'native_worker_lease':None})
        begin=end
    obj={
        'schema':MANIFEST_SCHEMA,'mode':'READ_ONLY_LOCAL_CENSUS',
        'repository':source['repository'],'exact_head':source['exact_head'],
        'source_artifact_sha256':source_evidence_sha(source),
        'source_payload_sha256':digest(source),'source_evidence_class':source.get('evidence_class'), 'selection_seed':seed,
        'source_scope':'FROZEN_SOURCE_NATIVE_CANONICAL_CONTEXT','total_modules':len(source['modules']),
        'global_known_branches':source['canonical_totals']['num_branches'],
        'global_known_covered_branches':source['canonical_totals']['covered_branches'],
        'caps':list(caps),'read_only_max_concurrent_readers':max_readers,
        'native_ci_jobs_dispatched':0,'source_writers_dispatched':0,'debug_sessions_claimed':None,
        'source_owner_write_leases':None,'native_test_execution_requested':False,
        'qps_census_crosswalk':{'producer_schema':'qps-metric-census/v1','mode':'adapter_proposal_only','authoritative_orchestrator':'GBOGEB/pipeline-automation-hub','native_receipt_schema':'qps-metric-receipt/v1','native_receipt_claimed':False},
        'slices':slices,'authority_transfer':False,'security_waiver':False,'merge_admission':'HOLD'}
    obj['manifest_sha256']=digest(obj)
    return obj

def verify_manifest(source, manifest):
    validate_source(source)
    require(isinstance(manifest,dict) and manifest.get('schema')==MANIFEST_SCHEMA,'bad manifest schema')
    mh=manifest.get('manifest_sha256')
    require(isinstance(mh,str) and SHA64.fullmatch(mh),'bad manifest digest')
    require(mh==digest({k:v for k,v in manifest.items() if k!='manifest_sha256'}),'modified manifest')
    require(source['exact_head']==manifest.get('exact_head') and digest(source)==manifest.get('source_payload_sha256') and source_evidence_sha(source)==manifest.get('source_artifact_sha256'),'stale source')
    require(manifest.get('native_ci_jobs_dispatched')==0 and manifest.get('source_writers_dispatched')==0 and manifest.get('authority_transfer') is False and manifest.get('merge_admission')=='HOLD','authority escalated')
    if not valid_int(manifest.get('read_only_max_concurrent_readers'),1) or manifest['read_only_max_concurrent_readers']>4:
        raise CensusError('illegal concurrency')
    expected=plan(source,caps=manifest['caps'],seed=manifest['selection_seed'],max_readers=manifest['read_only_max_concurrent_readers'])
    require(expected==manifest,'not deterministic or source-disjoint')
    return manifest

async def _audit(source, row, sem):
    async with sem:
        # Intentionally no async external API/runner call: only local verification.
        path=row['path'];s=summary(source['modules'][path]);await asyncio.sleep(0)
        return {'path':path,'selection_channel':row['selection_channel'], 'stratum':row['stratum'],
            'eligible_arcs':s['num_branches'],'covered_arcs':s['covered_branches'],
            'missing_arcs':s['num_branches']-s['covered_branches'],
            'eligible_statements':s['num_statements'],'covered_statements':s['covered_lines'],
            'arc_universe_sha256':digest([source['modules'][path]['executed_branches'],source['modules'][path]['missing_branches']]),
            'first_red_confirmed':None, 'source_owner':None,'owner_effort_hours':None,
            'code_written':False,'new_tests_executed':None,'ldab_execution':None}

async def emit_partials(source,manifest):
    verify_manifest(source,manifest)
    sem=asyncio.Semaphore(manifest['read_only_max_concurrent_readers'])
    out=[];prior=None
    for s in manifest['slices']:
        rows=await asyncio.gather(*[_audit(source,row,sem) for row in s['selected']])
        rows.sort(key=lambda x:x['path'])
        packet={'schema':PARTIAL_SCHEMA,'repository':manifest['repository'],'exact_head':manifest['exact_head'],
            'manifest_sha256':manifest['manifest_sha256'],'source_payload_sha256':manifest['source_payload_sha256'],
            'slice_id':s['slice_id'],'pulse':s['pulse'],'parent_receipt_sha256':prior,
            'state':'VERIFIED_LOCAL_CENSUS_ONLY','producer':'LOCAL_READ_ONLY_REPLAY',
            'source_kind':('LOCAL_COVERAGE_USER_SUPPLIED_SOURCE_SHA' if source.get('local_report_sha256') is not None else 'NATIVE_COVERAGE_ARCHIVE_ALREADY_MEASURED'),'native_execution_run_id':None,
            'new_native_tests':None,'new_confirmed_reds':None,'source_writes':0,
            'scope_rows':rows,'records':len(rows),
            'authority_transfer':False,'security_waiver':False,'merge_admission':'HOLD'}
        packet['receipt_sha256']=digest({k:v for k,v in packet.items() if k!='receipt_sha256'})
        prior=packet['receipt_sha256'];out.append(packet)
    return out

def verify_partial(source, manifest, partial):
    verify_manifest(source,manifest)
    require(isinstance(partial,dict) and partial.get('schema')==PARTIAL_SCHEMA,'partial schema mismatch')
    allowed={'schema','repository','exact_head','manifest_sha256','source_payload_sha256','slice_id','pulse',
             'parent_receipt_sha256','state','producer','source_kind','native_execution_run_id',
             'new_native_tests','new_confirmed_reds','source_writes','scope_rows','records',
             'authority_transfer','security_waiver','merge_admission','receipt_sha256'}
    require(set(partial)==allowed,'unexpected partial fields')
    require(partial.get('state')=='VERIFIED_LOCAL_CENSUS_ONLY','forged partial status')
    expected_kind=('LOCAL_COVERAGE_USER_SUPPLIED_SOURCE_SHA' if source.get('local_report_sha256') is not None
                   else 'NATIVE_COVERAGE_ARCHIVE_ALREADY_MEASURED')
    require(partial.get('source_kind')==expected_kind,'falsified producer provenance')
    hh=partial.get('receipt_sha256')
    require(isinstance(hh,str) and SHA64.fullmatch(hh),'missing receipt SHA')
    require(hh==digest({k:v for k,v in partial.items() if k!='receipt_sha256'}),'partial altered')
    require(partial.get('repository')==manifest['repository'] and partial.get('exact_head')==manifest['exact_head'] and partial.get('manifest_sha256')==manifest['manifest_sha256'] and partial.get('source_payload_sha256')==manifest['source_payload_sha256'],'partial head or source stale')
    require(partial.get('producer')=='LOCAL_READ_ONLY_REPLAY' and partial.get('native_execution_run_id') is None and partial.get('new_native_tests') is None and partial.get('new_confirmed_reds') is None,'forged native proof')
    require(partial.get('source_writes')==0 and partial.get('authority_transfer') is False and partial.get('merge_admission')=='HOLD' and partial.get('security_waiver') is False,'unauthorized actions')
    slice_rows=[s for s in manifest['slices'] if s['slice_id']==partial.get('slice_id') and s['pulse']==partial.get('pulse')]
    require(len(slice_rows)==1,'unknown slice identity')
    selected={r['path']:r for r in slice_rows[0]['selected']}
    observed=partial.get('scope_rows')
    require(isinstance(observed,list) and len(observed)==len(selected) and partial.get('records')==len(selected),'partial count missing')
    seen=set()
    for row in observed:
        require(isinstance(row,dict) and row.get('path') in selected and row['path'] not in seen,'partial path duplicate/foreign')
        require(set(row)=={'path','selection_channel','stratum','eligible_arcs','covered_arcs',
            'missing_arcs','eligible_statements','covered_statements','arc_universe_sha256',
            'first_red_confirmed','source_owner','owner_effort_hours','code_written',
            'new_tests_executed','ldab_execution'},'unrecognized row metadata')
        seen.add(row['path'])
        s=summary(source['modules'][row['path']])
        expected={'eligible_arcs':s['num_branches'],'covered_arcs':s['covered_branches'],
                  'missing_arcs':s['num_branches']-s['covered_branches'],
                  'eligible_statements':s['num_statements'],'covered_statements':s['covered_lines'],
                  'arc_universe_sha256':digest([source['modules'][row['path']]['executed_branches'],source['modules'][row['path']]['missing_branches']]),
                  'stratum':selected[row['path']]['stratum'],'selection_channel':selected[row['path']]['selection_channel']}
        for k,v in expected.items(): require(row.get(k)==v,'unmatched metric/source arc at '+row['path'])
        require(row.get('first_red_confirmed') is None and row.get('source_owner') is None and row.get('owner_effort_hours') is None and row.get('code_written') is False and row.get('new_tests_executed') is None and row.get('ldab_execution') is None,'false authority/worker proof')
    return partial

def rollup(source,manifest,packets):
    verify_manifest(source,manifest)
    ids=set();accepted={}; prior=None;steps=[];ledger=[]
    # Duplicates identical are idempotent. Conflicting content fails during validation.
    uniq={}
    for p in packets:
        verify_partial(source,manifest,p)
        sid=p['slice_id']
        if sid in uniq:
            require(canonical(uniq[sid])==canonical(p),'conflicting duplicate partial')
        else:uniq[sid]=p
    for s in manifest['slices']:
        p=uniq.get(s['slice_id'])
        require(p is not None,'missing partial – hold promotion')
        require(p.get('parent_receipt_sha256')==prior,'broken partial hash chain')
        prior=p['receipt_sha256']
        delta={'modules':0,'eligible_arcs':0,'covered_arcs':0,'missing_arcs':0}
        for row in p['scope_rows']:
            path=row['path']
            require(path not in accepted,'overlap across disjoint pulses')
            accepted[path]=row
            delta['modules']+=1
            for key in ('eligible_arcs','covered_arcs','missing_arcs'):
                delta[key]+=row[key]
            ledger.append({'pulse':s['pulse'],'slice_id':s['slice_id'],**row})
        cumul={'modules':len(accepted),'eligible_arcs':sum(z['eligible_arcs'] for z in accepted.values()),'covered_arcs':sum(z['covered_arcs'] for z in accepted.values()),'missing_arcs':sum(z['missing_arcs'] for z in accepted.values())}
        require(cumul['modules']==s['cumulative_modules'],'cumulative slice count drift')
        steps.append({'pulse':s['pulse'],'delta':delta,'cumulative':cumul,
            'sample_coverage_percent':round(100*cumul['covered_arcs']/cumul['eligible_arcs'],4) if cumul['eligible_arcs'] else None,
            'read_only_census_integrity':'PASS_LOCAL','native_execution_proof':'NOT_PERFORMED',
            'next_read_only_slice':'ELIGIBLE_IF_LOCAL_INVARIANTS_PASS' if s['pulse']<3 else 'COMPLETED_LOCAL',
            'next_source_worker_dispatch':'HOLD_PENDING_NATIVE_AND_OWNER_GATES',
            'run_attempt_job_ids':None,'confirmed_roots_closed':None,
            'partial_receipt_sha256':p['receipt_sha256']})
    total=source['canonical_totals']['num_branches'];s=steps[-1]['cumulative']
    return {'schema':ROLLUP_SCHEMA,'repository':manifest['repository'],'exact_head':manifest['exact_head'],
        'manifest_sha256':manifest['manifest_sha256'],'source_payload_sha256':manifest['source_payload_sha256'],
        'census_pulses':steps,'module_ledger':ledger,'audit':{'sample_modules':s['modules'],
            'source_modules_known':len(source['modules']),'sampling_fraction':round(s['modules']/len(source['modules']),6),
            'sampled_known_arcs':s['eligible_arcs'],'total_known_native_arcs':total,
            'sampled_arc_fraction':round(s['eligible_arcs']/total,6) if total else None,
            'true_denominator_growth_on_frozen_head':0,
            'incremental_matched_coverage_gain':None,'new_native_test_count':None,
            'new_confirmed_red_count':None,'native_test_workers_launched':0,
            'source_writers_launched':0,'LDAB_sessions_verified':None,
            'root_closures_verified':None,'unseen_source_files_outside_coverage_catalog':None,
            'sampling_is_statistically_representative':False,
            'census_is_prior_known_population_subset':True,
            'reporting_gap_arcs':6},
        'decision':'LOCAL_DISCOVERY_COMPLETE_EXTERNAL_GATES_HOLD',
        'qps_census_integration':'CONSUMER_ADAPTER_ONLY_NO_DISPATCH',
        'authority_transfer':False,'security_waiver':False,'merge_admission':'HOLD'}

def write_json(p,obj):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n',encoding='utf-8')

def emit_files(root,source,manifest,partials,receipt):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    write_json(root/'census_request.json',manifest)
    for i,p in enumerate(partials,1):write_json(root/f'partial_A{i}.json',p)
    write_json(root/'census_rollup.json',receipt)
    with (root/'census_events.ndjson').open('w',encoding='utf-8') as f:
        for s in receipt['census_pulses']:
            f.write(canonical({'kind':'PARTIAL_CENSUS_EMITTED','source_head':source['exact_head'],
              'manifest_sha256':manifest['manifest_sha256'],'pulse':s['pulse'],
              'incremental':s['delta'],'cumulative':s['cumulative'],
              'receipt_sha256':s['partial_receipt_sha256'],'native_root_claim':None,
              'authority_transfer':False})+'\n')
    with (root/'census_module_diff.ndjson').open('w',encoding='utf-8') as f:
        for item in receipt['module_ledger']:
            f.write(canonical({'schema':'code-purple.census.path-observation.v1',
                **{k:v for k,v in item.items() if k not in ('owner_effort_hours',)}})+'\n')

def main(argv=None):
    p=argparse.ArgumentParser(description='N6 bounded disjoint coverage census; always read-only')
    sources=p.add_mutually_exclusive_group(required=True)
    sources.add_argument('--native',type=Path,help='frozen source-bound N5 compact JSON')
    sources.add_argument('--coverage-py',type=Path,help='ordinary coverage.py --branch JSON: LOCAL ONLY')
    p.add_argument('--repository',choices=sorted(ALLOWED_REPOS))
    p.add_argument('--exact-head',help='declared 40-character git SHA, unverified for local inputs')
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--caps',default='8,16,32')
    p.add_argument('--seed',default='N6-20261017')
    p.add_argument('--max-readers',type=int,default=2)
    p.add_argument('--verify-only',action='store_true')
    args=p.parse_args(argv)
    if args.native:
        source=json.loads(args.native.read_text(encoding='utf-8'))
    else:
        require(args.repository is not None and args.exact_head is not None,'local coverage requires explicit repository and declared exact SHA')
        source=adapt_coverage_json(json.loads(args.coverage_py.read_text(encoding='utf-8')),repository=args.repository,exact_head=args.exact_head)
    caps=tuple(int(x) for x in args.caps.split(','))
    manifest=plan(source,caps=caps,seed=args.seed,max_readers=args.max_readers)
    if args.verify_only:
        packets=[json.loads((args.out/f'partial_A{i}.json').read_text()) for i in range(1,4)]
        existing=json.loads((args.out/'census_rollup.json').read_text())
        rec=rollup(source,manifest,packets)
        require(rec==existing,'persisted rollup drift')
        print(json.dumps({'status':'PASS_LOCAL','modules':rec['audit']['sample_modules'],'manifest_sha256':manifest['manifest_sha256']}))
        return 0
    packets=asyncio.run(emit_partials(source,manifest))
    receipt=rollup(source,manifest,packets)
    emit_files(args.out,source,manifest,packets,receipt)
    print(json.dumps({'status':'PASS_LOCAL_READ_ONLY','samples':receipt['audit']['sample_modules'],'global_modules':receipt['audit']['source_modules_known'],
            'max_readers':args.max_readers,'native_jobs_dispatched':0,'merge_admission':'HOLD'}))
    return 0

if __name__=='__main__':
    raise SystemExit(main())