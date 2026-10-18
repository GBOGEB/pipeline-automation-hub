#!/usr/bin/env python3
"""Preconfigured HOME TestFlight F0–F4 then independent PR F5–F7.

Run from a full local repo checkout before staging push. Receipt is local
and intentionally NEVER merges/approves/retries or dispatches GitHub Actions.
"""
import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
HEX40=re.compile('[a-f0-9]{40}\\Z')

def run(argv,timeout=90):
    start=time.monotonic()
    try:
        p=subprocess.run(argv,cwd=REPO,capture_output=True,text=True,timeout=timeout)
        return {'status':'PASS' if p.returncode==0 else 'FAIL','return_code':p.returncode,
                'elapsed_s':round(time.monotonic()-start,3)},(p.stdout+'\n'+p.stderr).strip()
    except (OSError,subprocess.TimeoutExpired) as e:
        return {'status':'ERROR','error_type':type(e).__name__,'elapsed_s':round(time.monotonic()-start,3)},''

def flight(out,mode,head=None,browser=False):
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    _,s=run(['git','rev-parse','HEAD'])
    sha=s if HEX40.fullmatch(s) else None
    if head and not HEX40.fullmatch(head):raise ValueError('INVALID_EXPECTED_GIT_SHA')
    _,staged=run(['git','diff','--cached','--name-only'])
    _,dirty=run(['git','status','--porcelain'])
    staged_paths=sorted(p for p in staged.splitlines() if p)
    dirty_paths=sorted(p for p in dirty.splitlines() if p)
    inputs=(HERE/'SUPERSTITCH_SOURCE_v1.json').read_bytes()
    checks=[]
    def check(name,argv,timeout=120):
        result,log=run(argv,timeout);result['name']=name
        if name=='F2-governed-source-contract':
            found=re.search(r'Ran (\d+) tests? in',log)
            executed=int(found.group(1)) if found else None
            success=bool(found and re.search(r'(?m)^OK(?: \(skipped=\d+\))?
    check('F1-python-syntax',[sys.executable,'-m','compileall','-q',str(HERE)])
    check('F2-governed-source-contract',[sys.executable,'-m','unittest','discover',
        '-s','mission-control/federation-atlas','-p','test_superstitch.py','-v'])
    # Output stays outside checkout by default, and source files are never edited.
    if sha:
        check('F3-visual-projection',[sys.executable,str(HERE/'build.py'),'--head',sha,
                                     '--out',str(out/'site')])
        check('F4-16-member-integrity',[sys.executable,str(HERE/'build.py'),'--head',sha,
                    '--out',str(out/'site'),'--verify-only'])
        if browser:
            check('F4-browser-3-viewport',[sys.executable,str(HERE/'browser_qa.py'),
                '--html',str(out/'site/index.html'),'--out',str(out/'browser'),'--head',sha],180)
    identity_match=bool(sha and (head is None or sha==head))
    core_ok=bool(identity_match and checks and all(x['status']=='PASS' for x in checks))
    if mode=='home' and not staged_paths:
        status='LOCAL_PREVIEW_NOT_STAGED' if core_ok else 'FAIL'
    elif mode=='pr':
        status='PASS_LOCAL_PR_REPRODUCTION' if core_ok else 'FAIL'
    else:status='PASS_LOCAL_STAGED_TESTFLIGHT' if core_ok else 'FAIL'
    receipt={'schema':'missioncontrol.superstitch.home_testflight.v1',
        'mode':mode,'status':status,'head_sha':sha,'expected_head_sha':head,
        'expected_head_matches':identity_match,'staged_file_count':len(staged_paths),
        'dirty_entry_count':len(dirty_paths),
        'staged_paths_sha256':hashlib.sha256('\n'.join(staged_paths).encode()).hexdigest(),
        'python':platform.python_version(),'os':platform.system(),
        'source_sha256':hashlib.sha256(inputs).hexdigest(),
        'checks':checks,'observed_run_id':None,'observed_job_id':None,
        'worker_hours':None,'capacity':None,'governed_merge_admission':'HOLD',
        'qps_owner_acceptance':None,'qualification':'LOCAL_ONLY_NOT_GITHUB_NATIVE'}
    (out/'home_testflight_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',default='/tmp/w34-testflight');p.add_argument('--mode',choices=('home','pr'),default='home');p.add_argument('--expected-head');p.add_argument('--browser',action='store_true');a=p.parse_args()
    result=flight(a.out,a.mode,a.expected_head,a.browser)
    print(json.dumps({'status':result['status'],'checks':[(c['name'],c['status']) for c in result['checks']],
      'staged':result['staged_file_count'],'qualification':result['qualification']}))
    sys.exit(0 if result['status'].startswith('PASS_') else 2)
,log))
            skipped=re.search(r'(?m)^OK \(skipped=(\d+)\)
    check('F1-python-syntax',[sys.executable,'-m','compileall','-q',str(HERE)])
    check('F2-governed-source-contract',[sys.executable,'-m','unittest','discover',
        '-s','mission-control/federation-atlas','-p','test_superstitch.py','-v'])
    # Output stays outside checkout by default, and source files are never edited.
    if sha:
        check('F3-visual-projection',[sys.executable,str(HERE/'build.py'),'--head',sha,
                                     '--out',str(out/'site')])
        check('F4-8-member-integrity',[sys.executable,str(HERE/'build.py'),'--head',sha,
                    '--out',str(out/'site'),'--verify-only'])
        if browser:
            check('F4-browser-3-viewport',[sys.executable,str(HERE/'browser_qa.py'),
                '--html',str(out/'site/index.html'),'--out',str(out/'browser'),'--head',sha],180)
    identity_match=bool(sha and (head is None or sha==head))
    core_ok=bool(identity_match and checks and all(x['status']=='PASS' for x in checks))
    if mode=='home' and not staged_paths:
        status='LOCAL_PREVIEW_NOT_STAGED' if core_ok else 'FAIL'
    elif mode=='pr':
        status='PASS_LOCAL_PR_REPRODUCTION' if core_ok else 'FAIL'
    else:status='PASS_LOCAL_STAGED_TESTFLIGHT' if core_ok else 'FAIL'
    receipt={'schema':'missioncontrol.superstitch.home_testflight.v1',
        'mode':mode,'status':status,'head_sha':sha,'expected_head_sha':head,
        'expected_head_matches':identity_match,'staged_file_count':len(staged_paths),
        'dirty_entry_count':len(dirty_paths),
        'staged_paths_sha256':hashlib.sha256('\n'.join(staged_paths).encode()).hexdigest(),
        'python':platform.python_version(),'os':platform.system(),
        'source_sha256':hashlib.sha256(inputs).hexdigest(),
        'checks':checks,'observed_run_id':None,'observed_job_id':None,
        'worker_hours':None,'capacity':None,'governed_merge_admission':'HOLD',
        'qps_owner_acceptance':None,'qualification':'LOCAL_ONLY_NOT_GITHUB_NATIVE'}
    (out/'home_testflight_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',default='/tmp/w34-testflight');p.add_argument('--mode',choices=('home','pr'),default='home');p.add_argument('--expected-head');p.add_argument('--browser',action='store_true');a=p.parse_args()
    result=flight(a.out,a.mode,a.expected_head,a.browser)
    print(json.dumps({'status':result['status'],'checks':[(c['name'],c['status']) for c in result['checks']],
      'staged':result['staged_file_count'],'qualification':result['qualification']}))
    sys.exit(0 if result['status'].startswith('PASS_') else 2)
,log)
            result['tests_executed']=executed
            result['tests_skipped']=int(skipped.group(1)) if skipped else (0 if success else None)
            result['tests_passed']=(executed-result['tests_skipped']) if success else None
            result['tests_failed']=0 if success else None
            result['minimum_native_cases']=26
            if not success or executed is None or executed<26:
                result['status']='FAIL'
                result['error']='W35_TEST_DENOMINATOR_OR_NATIVE_COMMAND_FAILED'
        checks.append(result)
    check('F1-python-syntax',[sys.executable,'-m','compileall','-q',str(HERE)])
    check('F2-governed-source-contract',[sys.executable,'-m','unittest','discover',
        '-s','mission-control/federation-atlas','-p','test_superstitch.py','-v'])
    # Output stays outside checkout by default, and source files are never edited.
    if sha:
        check('F3-visual-projection',[sys.executable,str(HERE/'build.py'),'--head',sha,
                                     '--out',str(out/'site')])
        check('F4-8-member-integrity',[sys.executable,str(HERE/'build.py'),'--head',sha,
                    '--out',str(out/'site'),'--verify-only'])
        if browser:
            check('F4-browser-3-viewport',[sys.executable,str(HERE/'browser_qa.py'),
                '--html',str(out/'site/index.html'),'--out',str(out/'browser'),'--head',sha],180)
    identity_match=bool(sha and (head is None or sha==head))
    core_ok=bool(identity_match and checks and all(x['status']=='PASS' for x in checks))
    if mode=='home' and not staged_paths:
        status='LOCAL_PREVIEW_NOT_STAGED' if core_ok else 'FAIL'
    elif mode=='pr':
        status='PASS_LOCAL_PR_REPRODUCTION' if core_ok else 'FAIL'
    else:status='PASS_LOCAL_STAGED_TESTFLIGHT' if core_ok else 'FAIL'
    receipt={'schema':'missioncontrol.superstitch.home_testflight.v1',
        'mode':mode,'status':status,'head_sha':sha,'expected_head_sha':head,
        'expected_head_matches':identity_match,'staged_file_count':len(staged_paths),
        'dirty_entry_count':len(dirty_paths),
        'staged_paths_sha256':hashlib.sha256('\n'.join(staged_paths).encode()).hexdigest(),
        'python':platform.python_version(),'os':platform.system(),
        'source_sha256':hashlib.sha256(inputs).hexdigest(),
        'checks':checks,'observed_run_id':None,'observed_job_id':None,
        'worker_hours':None,'capacity':None,'governed_merge_admission':'HOLD',
        'qps_owner_acceptance':None,'qualification':'LOCAL_ONLY_NOT_GITHUB_NATIVE'}
    (out/'home_testflight_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',default='/tmp/w34-testflight');p.add_argument('--mode',choices=('home','pr'),default='home');p.add_argument('--expected-head');p.add_argument('--browser',action='store_true');a=p.parse_args()
    result=flight(a.out,a.mode,a.expected_head,a.browser)
    print(json.dumps({'status':result['status'],'checks':[(c['name'],c['status']) for c in result['checks']],
      'staged':result['staged_file_count'],'qualification':result['qualification']}))
    sys.exit(0 if result['status'].startswith('PASS_') else 2)
