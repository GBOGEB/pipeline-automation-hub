#!/usr/bin/env python3
"""Read-only, source-bound GitHub Actions pulse intake for MissionControl.

Native metadata is not source/test/coverage proof. A coverage value is credited
only from independently fetched artifact bytes with a compatible internal receipt.
The tool never writes to GitHub, changes admission, or overwrites historical series.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import io
import json
import os
import re
import urllib.request
import urllib.parse
import zipfile
from pathlib import Path
from urllib.parse import quote

SCHEMA = 'codepurple.native-pulse/v1'
INNER = 'codepurple.pulse-measurement/v1'
REPOS = frozenset({'GBOGEB/gg_MATH', 'GBOGEB/CODEX', 'GBOGEB/ABACUS',
                   'GBOGEB/cryoplant-project', 'GBOGEB/pipeline-automation-hub',
                   'GBOGEB/DOCX_RTM_Automation'})
SHA40 = re.compile(r'[0-9a-f]{40}\Z')
SHA64 = re.compile(r'[0-9a-f]{64}\Z')
NAME = re.compile(r'[A-Za-z0-9_.-]{1,100}\Z')
MAX_ARCHIVE = 16_000_000
MAX_MEMBERS = 40


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def positive(value):
    return type(value) is int and value > 0


class TokenSafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        require(urllib.parse.urlparse(newurl).scheme == 'https', 'insecure redirect blocked')
        ret = super().redirect_request(req, fp, code, msg, headers, newurl)
        if ret is not None and urllib.parse.urlparse(newurl).hostname != 'api.github.com':
            ret.remove_header('Authorization')
        return ret


def get(api_path, token, binary=False):
    require(api_path.startswith('/repos/GBOGEB/') and '..' not in api_path
            and '//' not in api_path, 'disallowed API path')
    headers = {'Accept': 'application/vnd.github+json',
               'X-GitHub-Api-Version': '2022-11-28',
               'User-Agent': 'CODE-PURPLE-NativePulse-ReadOnly'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request('https://api.github.com' + api_path,
                                 headers=headers, method='GET')
    with urllib.request.build_opener(TokenSafeRedirect()).open(req, timeout=20) as response:
        data = response.read(MAX_ARCHIVE + 1 if binary else 8_000_000)
    if binary:
        require(len(data) <= MAX_ARCHIVE, 'artifact download over budget')
        return data
    return json.loads(data)


def collect(repo, run_id, artifact_name=None, token=''):
    require(repo in REPOS, 'repository not in controlled cohort')
    require(positive(run_id), 'invalid run ID')
    p = '/repos/' + repo + '/actions/runs/' + str(run_id)
    run = get(p, token)
    def page_set(suffix, key):
        values = []
        for page in range(1, 11):
            result = get(p + suffix + '?per_page=100&page=' + str(page), token)
            batch = result.get(key)
            require(isinstance(batch, list), 'invalid GitHub ' + key)
            values.extend(batch)
            count = result.get('total_count')
            require(type(count) is int and count >= len(values), 'invalid total_count')
            if len(values) == count:
                return values
            require(len(batch) == 100, 'truncated GitHub pagination')
        raise ValueError('GitHub pagination limit exceeded')
    jobs = {'jobs': page_set('/jobs', 'jobs')}
    artifacts = {'artifacts': page_set('/artifacts', 'artifacts')}
    raw = None
    if artifact_name is not None:
        require(NAME.fullmatch(artifact_name) is not None, 'invalid artifact name')
        matches = [x for x in artifacts['artifacts'] if x.get('name') == artifact_name]
        require(len(matches) == 1, 'requested artifact not uniquely present')
        a = matches[0]
        require(positive(a.get('id')) and a.get('expired') is False, 'artifact missing/expired')
        raw = get('/repos/' + repo + '/actions/artifacts/' + str(a['id']) + '/zip', token, True)
    return run, jobs, artifacts, raw


def _metric(value, label):
    require(isinstance(value, dict) and set(value) == {'covered', 'eligible'},
            label + ' numerator/denominator missing')
    c, n = value['covered'], value['eligible']
    require(type(c) is int and positive(n) and 0 <= c <= n, label + ' metric invalid')
    return {'covered': c, 'eligible': n, 'pct': round(100*c/n, 2)}


def _read_receipt(archive):
    require(isinstance(archive, bytes) and len(archive) <= MAX_ARCHIVE,
            'artifact bytes absent or over budget')
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        entries = z.infolist()
        require(0 < len(entries) <= MAX_MEMBERS, 'artifact member budget exceeded')
        names = [f.filename for f in entries]
        require(len(set(names)) == len(names), 'duplicate artifact member')
        require('pulse_measurement.json' in names, 'canonical receipt missing')
        for item in entries:
            mode = item.external_attr >> 16
            require(not item.is_dir() and not item.filename.startswith('/')
                    and '..' not in item.filename.replace('\\', '/').split('/')
                    and '\\' not in item.filename and not (mode & 0o170000) == 0o120000
                    and not (item.flag_bits & 1)
                    and item.file_size <= 2_000_000,
                    'unsafe ZIP member')
        require(sum(i.file_size for i in entries) <= MAX_ARCHIVE,
                'ZIP expansion limit exceeded')
        return json.loads(z.read('pulse_measurement.json'))


def validate(repo, run_id, run, jobs, artifacts, *, artifact_name=None,
             archive=None, expected_sha=None, metadata_origin='CALLER_SUPPLIED_OFFLINE'):
    require(repo in REPOS and positive(run_id), 'invalid repository/run identity')
    require(metadata_origin in ('CALLER_SUPPLIED_OFFLINE', 'LIVE_GITHUB_API'), 'invalid metadata origin')
    require(isinstance(run, dict) and run.get('id') == run_id,
            'run ID mismatch')
    require(run.get('repository', {}).get('full_name') == repo,
            'native repository mismatch')
    sha = run.get('head_sha')
    require(isinstance(sha, str) and SHA40.fullmatch(sha), 'invalid run head SHA')
    if expected_sha is not None:
        require(sha == expected_sha, 'stale/mismatched expected SHA')
    attempt = run.get('run_attempt')
    require(positive(attempt), 'run attempt missing')
    require(run.get('status') in ('completed', 'queued', 'in_progress'),
            'unsupported run state')
    if run['status'] == 'completed':
        require(run.get('conclusion') in ('success', 'failure', 'cancelled',
                 'timed_out', 'action_required', 'neutral', 'skipped', 'stale'),
                'invalid terminal run conclusion')
    else:
        require(run.get('conclusion') is None, 'nonterminal success contradiction')
    require(isinstance(jobs, dict) and isinstance(jobs.get('jobs'), list)
            and jobs['jobs'], 'native jobs missing')
    native_jobs = jobs['jobs']
    job_ids = set()
    for job in native_jobs:
        jid = job.get('id')
        require(positive(jid) and jid not in job_ids
                and job.get('run_id') == run_id
                and job.get('run_attempt', attempt) == attempt,
                'invalid or stale job identity')
        job_ids.add(jid)
    require(isinstance(artifacts, dict)
            and isinstance(artifacts.get('artifacts'), list), 'artifact list missing')
    a = None
    if artifact_name is not None:
        require(isinstance(artifact_name, str) and NAME.fullmatch(artifact_name),
                'artifact name invalid')
        matches = [x for x in artifacts['artifacts'] if x.get('name') == artifact_name]
        require(len(matches) == 1, 'artifact not uniquely listed')
        a = matches[0]
        require(positive(a.get('id')) and a.get('expired') is False,
                'artifact expired/invalid')
        if isinstance(a.get('workflow_run'), dict):
            require(a['workflow_run'].get('id') == run_id
                    and a['workflow_run'].get('head_sha') == sha,
                    'artifact run/source mismatch')
    require(archive is None or a is not None, 'unlisted ZIP cannot be accepted')
    state = 'RUN_METADATA_ONLY'
    measure = None
    archive_sha = None
    if archive is not None:
        archive_sha = digest(archive)
        inner = _read_receipt(archive)
        require(inner.get('schema') == INNER and inner.get('repository') == repo
                and inner.get('head_sha') == sha
                and inner.get('run_id') == run_id
                and inner.get('run_attempt') == attempt,
                'inner provenance does not match native run')
        jid = inner.get('job_id')
        require(jid in job_ids and any(j['id'] == jid and j.get('status') == 'completed'
                and j.get('conclusion') == 'success' for j in native_jobs),
                'inner job is not successful on exact run')
        require(run['status'] == 'completed' and run.get('conclusion') == 'success',
                'coverage credit prohibited for red or nonterminal workflow')
        require(isinstance(inner.get('selection'), str) and inner['selection']
                and isinstance(inner.get('tool'), dict)
                and isinstance(inner['tool'].get('name'), str)
                and isinstance(inner['tool'].get('version'), str)
                and SHA64.fullmatch(str(inner.get('config_sha256', ''))),
                'coverage config/test selection missing')
        scope = inner.get('source_scope')
        require(isinstance(scope, list) and scope
                and len({f.get('path') for f in scope}) == len(scope),
                'missing/duplicate source scope')
        for f in scope:
            require(isinstance(f, dict) and isinstance(f.get('path'), str)
                    and not f['path'].startswith('/') and '..' not in f['path'].split('/')
                    and SHA64.fullmatch(str(f.get('sha256', ''))),
                    'invalid source scope digest')
        tests = inner.get('tests')
        require(isinstance(tests, dict) and set(tests) == {'passed','failed','skipped'}
                and all(type(v) is int and v >= 0 for v in tests.values())
                and tests['passed'] > 0 and tests['failed'] == 0,
                'invalid/nonpassing test receipt')
        measure = {'line': _metric(inner.get('line'), 'line'),
                   'branch': _metric(inner.get('branch'), 'branch'),
                   'selection': inner['selection'], 'source_scope': scope,
                   'tests': tests, 'tool': inner['tool'],
                   'config_sha256': inner['config_sha256'],
                   'job_id': jid}
        state = 'RUN_BOUND_ARTIFACT_RECEIPT_INSPECTED'
    report = {'schema': SCHEMA, 'repository': repo, 'run_id': run_id,
              'run_attempt': attempt, 'source_sha': sha,
              'status': run['status'], 'conclusion': run.get('conclusion'),
              'job_count': len(native_jobs), 'artifact_count': len(artifacts['artifacts']),
              'artifact_name': artifact_name, 'artifact_id': a['id'] if a else None,
              'archive_sha256': archive_sha, 'evidence_depth': state,
              'metadata_origin': metadata_origin,
              'measurement_authority': ('PRODUCER_REPORTED_NOT_INDEPENDENTLY_RECOMPUTED'
                                        if measure is not None else None),
              'measurement': measure, 'native_chain_accepted': None,
              'qps_owner_decision': 'DEFER', 'merge_admitted': False,
              'root_closed': None, 'authority_transfer': False,
              'historical_series_mutated': False}
    report['event_sha256'] = digest(canonical(report).encode())
    return report


def write_event(report, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    key = report['repository'].split('/')[1] + '-' + str(report['run_id']) + '-' + str(report['run_attempt'])
    path = out / ('pulse-' + key + '-' + report['event_sha256'][:16] + '.json')
    raw = json.dumps(report, indent=2, sort_keys=True) + '\n'
    if path.exists():
        require(path.read_text(encoding='utf-8') == raw, 'existing event mutated')
    else:
        path.write_text(raw, encoding='utf-8')
    # Build from all immutable local events; do not rewrite historical QPS/G series.
    events = []
    for p in sorted(out.glob('pulse-*.json')):
        obj = json.loads(p.read_text(encoding='utf-8'))
        sig = obj.pop('event_sha256', None)
        require(sig == digest(canonical(obj).encode()), 'event tampering: ' + p.name)
        obj['event_sha256'] = sig
        events.append(obj)
    ledger = {'schema':'codepurple.native-pulse-ledger/v1',
              'evidence_kind':'OBSERVED_NATIVE_ACTIONS_NOT_MERGE_AUTHORITY',
              'events':events, 'scope_rollup':{}, 'archive_downloads_validated':sum(
                  x['measurement'] is not None for x in events)}
    # Separate axes; no synthetic P3/N+3 increments.
    for repo in sorted({x['repository'] for x in events}):
        xs = [x for x in events if x['repository'] == repo]
        ledger['scope_rollup'][repo] = {'run_events':len(xs),
           'measured_events':sum(x['measurement'] is not None for x in xs),
           'coverage_aggregated':None, 'unique_roots_closed':None}
    (out/'native_pulse_ledger.json').write_text(json.dumps(ledger,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    rows=[]
    for e in events:
        m=e['measurement']
        cov='UNKNOWN' if m is None else f"{m['line']['covered']}/{m['line']['eligible']} lines; {m['branch']['covered']}/{m['branch']['eligible']} branches"
        url='https://github.com/'+e['repository']+'/actions/runs/'+str(e['run_id'])
        rows.append('<tr><td>'+html.escape(e['repository'])+'</td><td><a href="'+html.escape(url,quote=True)+'">'+str(e['run_id'])+'</a></td><td>'+html.escape(e['source_sha'][:12])+'</td><td>'+html.escape(e['evidence_depth'])+'</td><td>'+html.escape(cov)+'</td></tr>')
    page = ('<!doctype html><html lang="en"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>CODE PURPLE native pulse evidence</title>'
            '<style>body{font:15px system-ui;max-width:1100px;margin:2rem auto;padding:0 1rem}'
            'table{border-collapse:collapse;width:100%}td,th{padding:.7rem;border-bottom:1px solid #888;text-align:left}'
            'table{display:block;overflow-x:auto}small{color:#666}</style>'
            '<h1>CODE PURPLE — Native pulse evidence</h1>'
            '<p>Read-only observation. Missing artifact bytes mean UNKNOWN coverage. '
            'Independent federation and merge admission are not inferred.</p>'
            '<table><thead><tr><th>Repository</th><th>Run</th><th>SHA</th><th>Evidence depth</th><th>Measured coverage</th></tr></thead><tbody>'
            + ''.join(rows) + '</tbody></table><small>Generated locally from immutable event files. Not automatically deployed or current-head admission.</small></html>')
    (out/'native_pulse_index.html').write_text(page,encoding='utf-8')
    return path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', required=True, choices=sorted(REPOS))
    p.add_argument('--run-id', required=True, type=int)
    p.add_argument('--artifact-name', default=None)
    p.add_argument('--expected-sha', default=None)
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--offline', action='store_true')
    p.add_argument('--run-json', type=Path)
    p.add_argument('--jobs-json', type=Path)
    p.add_argument('--artifacts-json', type=Path)
    p.add_argument('--archive', type=Path)
    args=p.parse_args()
    if args.offline:
        require(all([args.run_json, args.jobs_json, args.artifacts_json]),
                'offline input triplet required')
        run=json.loads(args.run_json.read_text())
        jobs=json.loads(args.jobs_json.read_text())
        artifacts=json.loads(args.artifacts_json.read_text())
        archive=args.archive.read_bytes() if args.archive else None
    else:
        require(not any([args.run_json,args.jobs_json,args.artifacts_json,args.archive]),
                'offline files must not be passed as live evidence')
        run,jobs,artifacts,archive=collect(args.repo,args.run_id,args.artifact_name,
              token=os.getenv('GITHUB_TOKEN',''))
    report=validate(args.repo,args.run_id,run,jobs,artifacts,
                    artifact_name=args.artifact_name,archive=archive,
                    expected_sha=args.expected_sha,
                    metadata_origin=('CALLER_SUPPLIED_OFFLINE' if args.offline else 'LIVE_GITHUB_API'))
    path=write_event(report,args.out)
    print(canonical({'status':'PASS','source_sha':report['source_sha'],
                     'evidence_depth':report['evidence_depth'],
                     'event_sha256':report['event_sha256'],'path':str(path)}))

if __name__=='__main__':
    main()