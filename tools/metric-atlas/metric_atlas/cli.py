"""Local CLI: python -m metric_atlas.cli --help."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile
from .analytics import analyze, validate, simulate, matched_comparison
from .render import render_html

BASE = Path(__file__).resolve().parents[1]


def read_ledger(path):
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    validate(data)
    return data


def verify_zip(path, expected_sha=None):
    raw=Path(path).read_bytes()
    digest=hashlib.sha256(raw).hexdigest()
    with zipfile.ZipFile(path) as z:
        bad=z.testzip()
        files=[{'name':i.filename,'uncompressed_bytes':i.file_size,'compressed_bytes':i.compress_size,
                'sha256':hashlib.sha256(z.read(i)).hexdigest()}
               for i in z.infolist() if not i.is_dir()]
    return {'path':str(path),'archive_bytes':len(raw),'sha256':digest,
            'integrity':'PASS' if bad is None else 'FAIL',
            'expected_sha_matches':digest==expected_sha if expected_sha else None,
            'members':files}


def build(args):
    data=read_ledger(args.input)
    analysis=analyze(data)
    target=Path(args.output)
    target.mkdir(parents=True,exist_ok=True)
    (target/'metric_ledger.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    (target/'metric_analysis.json').write_text(json.dumps(analysis,indent=2)+'\n',encoding='utf-8')
    (target/'index.html').write_text(render_html(data),encoding='utf-8')
    with (target/'metric_ledger.csv').open('w',newline='',encoding='utf-8') as f:
        keys=['id','scope_id','metric','step','repo','pr','sha','value','numerator','denominator','unit','state','observed_at','population_key','source','note']
        w=csv.DictWriter(f,fieldnames=keys,extrasaction='ignore');w.writeheader();w.writerows(data['measurements'])
    with (target/'metric_events.ndjson').open('w',encoding='utf-8') as f:
        for r in data['measurements']:
            f.write(json.dumps(r,ensure_ascii=False)+'\n')
    ranks=analysis['rankings']['relative_test_growth']
    lines=['# CODE PURPLE metric wave report','',f"As-of source context: {data.get('as_of')}",
           f"Total typed measurements: {len(data['measurements'])}",
           f"Independently native-artifact observations: {analysis['native_measurements']}",
           f"Historical native #533 archive SHA-256: `{data['native_archive']['sha256']}`",'',
           '## Normalized test-growth leader (only within test-count metric)','']
    for r in ranks:
        lines.append(f"- {r['label']}: {r['increment']:+.0f} passing tests; {r['growth_pct']:+.2f}% across one observed step.")
    lines.extend(['','## Causal attribution and unknowns','',
                  'Historical recurring Matplotlib fingerprint reached 7 PRs; this is NOT seven accepted root closures.',
                  'N20 rolling mean is UNKNOWN for every seeded cohort with fewer than 20 observations.',
                  'No worker-hours, full fleet coverage, latest effective ruleset, or automatic merge approval is inferred.','',
                  '## Coverage comparability',''])
    broad=[r for r in data['measurements'] if r['scope_id']=='ABACUS:PY312_BROAD' and r['metric']=='statement_coverage']
    c=matched_comparison(broad[0],broad[1]) if len(broad)>=2 else {'status':'UNKNOWN'}
    lines.append(f"- Broad ABACUS two-head comparison: {c['status']}; a raw change is not a matched coverage improvement.")
    lines.extend(['','## Due diligence / next priorities','',
                  '1. Verify Python 3.10 Matplotlib failure root with canonical owner; count exact-head jobs actually cleared.',
                  '2. Repair remaining MD032 without weakening required CI and prove fresh exact-head outcome.',
                  '3. Increase reproducible longitudinal observations toward N20; preserve phase/runner/denominator identity.',
                  '4. Gather worker-hours, attempt identity and branch numerators before declaring yield/stability winners.',
                  '5. Keep #530 ZIP verifier, #531 breadth producer and #533 viewer roles disjoint.'])
    (target/'wave_report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'state':'BUILT','output':str(target.resolve()),'observations':len(data['measurements']),
                      'files':sorted(p.name for p in target.iterdir())},indent=2))


def gh_api(endpoint):
    try:
        r=subprocess.run(['gh','api','-H','Accept: application/vnd.github+json',endpoint],
            capture_output=True,text=True,timeout=45,check=False)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError('gh CLI unavailable or timed out; install and authenticate gh first') from exc
    if r.returncode!=0:
        raise RuntimeError('gh read-only API failed: '+r.stderr.strip()[:300])
    return json.loads(r.stdout)


def collect_gh(args):
    """Read-only GitHub probe. Never counts native tests from checks names alone."""
    if '/' not in args.repo:
        raise RuntimeError('--repo must be owner/repository')
    pr=gh_api(f'repos/{args.repo}/pulls/{args.pr}')
    head=pr['head']['sha']
    checks=gh_api(f'repos/{args.repo}/commits/{head}/check-runs?per_page=100')
    payload={'schema':'codepurple.gh_probe.v1','state':'RAW_CHECK_METADATA_NOT_ATTESTED',
             'repo':args.repo,'pr':args.pr,'head_sha':head,'base_sha':pr['base']['sha'],
             'draft':pr.get('draft'),'mergeable':pr.get('mergeable'),
             'check_total_api':checks.get('total_count'),
             'check_first_page':[{'id':x.get('id'),'name':x.get('name'),'status':x.get('status'),
                                   'conclusion':x.get('conclusion'),'url':x.get('html_url'),
                                   'head_sha':x.get('head_sha')} for x in checks.get('check_runs',[])],
             'pagination_complete':len(checks.get('check_runs',[]))>=checks.get('total_count',0),
             'native_test_counts':None,'artifact_integrity':None,'root_attributions':None,
             'note':'Read-only raw check inventory; job/attempt/artifact/test proofs remain UNKNOWN.'}
    Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    Path(args.output).write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
    print('Wrote read-only metadata:',args.output,'SHA:',head)


def main(argv=None):
    parser=argparse.ArgumentParser(description='CODE PURPLE scope-bound N-indexed Metric Atlas')
    sp=parser.add_subparsers(dest='command',required=True)
    b=sp.add_parser('build',help='Generate HTML, CSV, NDJSON, JSON metrics and report')
    b.add_argument('--input',type=Path,default=BASE/'data/observations.json')
    b.add_argument('--output',type=Path,default=BASE/'run')
    v=sp.add_parser('verify-zip',help='Verify actual archive CRC, members, and SHA-256')
    v.add_argument('zip',type=Path)
    v.add_argument('--expected-sha')
    c=sp.add_parser('collect-gh',help='Optional authenticated GitHub read-only check inventory')
    c.add_argument('--repo',required=True)
    c.add_argument('--pr',required=True,type=int)
    c.add_argument('--output',type=Path,required=True)
    s=sp.add_parser('simulate',help='UNVERIFIED N+i continuation for a comparable cohort')
    s.add_argument('--scope-metric',required=True,help='e.g. MC:METHOD_ATLAS::tests_passed')
    s.add_argument('--pulses',type=int,default=3)
    args=parser.parse_args(argv)
    try:
        if args.command=='build':build(args)
        elif args.command=='verify-zip':
            result=verify_zip(args.zip,args.expected_sha)
            print(json.dumps(result,indent=2))
            if result['integrity']!='PASS' or result['expected_sha_matches'] is False:return 2
        elif args.command=='collect-gh':collect_gh(args)
        elif args.command=='simulate':
            h=analyze(read_ledger(BASE/'data/observations.json'))['histories'].get(args.scope_metric)
            if not h:raise RuntimeError('Unknown scope-metric; inspect run/metric_analysis.json')
            print(json.dumps(simulate(h,args.pulses),indent=2))
        return 0
    except (ValueError,FileNotFoundError,RuntimeError,zipfile.BadZipFile) as e:
        print('ERROR:',e,file=sys.stderr);return 1


if __name__=='__main__':
    raise SystemExit(main())
