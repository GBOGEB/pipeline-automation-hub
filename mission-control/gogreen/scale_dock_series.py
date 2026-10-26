#!/usr/bin/env python3
"""CODE PURPLE scale-dock real-pulse adapter: live read-only GitHub -> HISTORICAL_REPLAY series.

A pulse reads each public repo's default-branch head once (AGENTS.md L6) and records every Actions
job on that exact head. A failed job is a RED manifestation; a job identity that was RED in the
previous pulse and passes on the new head is RECOVERED. PR-head failures are not findings here
(the series contract allows one exact head per repo): they dock through the issue-BD census.

Owner functions are imported, never copied (AGENTS.md L4):
  bd_queue_wave    GitHubReader.paginate, scan, scan_public, family, utc
  everred/harvest  occurrences_from_job, matches, norm, split_env
  scale_dock       SCHEMA, DOCK_SCHEMAS, PRIORITY, digest, evaluate, require

Reads go through the gh CLI login: no token is read, printed or stored. Private cryoplant data
enters only as aggregate counts; a failed private read is UNKNOWN (None), never zero.
Each pulse is appended to an append-only ledger chained by sha256 (N0, N+1, ...).

Usage:
  python scale_dock_series.py pulse  [--ledger PATH] [--roots roots.yaml] [--record FIXTURE]
  python scale_dock_series.py series [--ledger PATH] --out series.json
  python scale_dock.py --input series.json --out DIR --source-sha <hub sha>
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
HUB = HERE.parents[1]
LEDGER = HERE / 'scale-dock' / 'real' / 'pulses.jsonl'
ROOTS = HUB / 'mission-control/qps-triage-ultra/p-process/everred/roots.yaml'
LEDGER_SCHEMA = 'codepurple.scale-dock.pulse-ledger.v1'
COHORT = 'REAL-DEFAULT-HEADS-THREE-PUBLIC-REPOS'
WINDOW = 12  # scale_dock.evaluate() bounds a series to 12 pulses
CONTROLS = {'authority_transfer': False, 'merge_admission': 'HOLD', 'dispatch_authorized': False,
            'security_waiver': False, 'qps_engineering_acceptance': False}
# Committed producer projections, read at the hub's pulse head SHA and pinned by blob OID.
FILE_DOCKS = {'everred': 'mission-control/qps-triage-ultra/p-process/site/everred/data/everred.json',
              'code_purple': 'mission-control/qps-triage-ultra/p-process/site/code-purple/kit/census.json',
              'p_process': 'mission-control/qps-triage-ultra/p-process/site/data/p_state.json',
              'crosswalk': 'mission-control/gogreen/g5_gap_crosswalk_20261015.json'}
# bd_queue_wave.family() labels -> scale_dock.FAMILIES; a projection, not a root diagnosis.
FAMILY = {'CONFIDENTIALITY': 'GOVERNANCE', 'GOVERNANCE': 'GOVERNANCE', 'SECURITY': 'SECURITY',
          'FORMAT': 'DOCUMENTATION', 'PYTHON_MATRIX': 'COMPATIBILITY', 'V032': 'COMPATIBILITY',
          'EVERRED': 'EVIDENCE', 'DOW': 'EVIDENCE', 'COVERAGE': 'COVERAGE',
          'INTEGRATED_SUITE': 'RUNTIME', 'OTHER': 'OTHER'}
OWNERS = {'scale_dock': HERE / 'scale_dock.py', 'bd_queue_wave': HERE / 'bd_queue_wave.py',
          'harvest': HUB / 'mission-control/qps-triage-ultra/p-process/everred/harvest.py'}
_loaded = {}


def owner(name):
    """Load a canonical owner module by path (harvest lives in a hyphenated directory)."""
    if name not in _loaded:
        spec = importlib.util.spec_from_file_location('scale_dock_series_' + name, OWNERS[name])
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _loaded[name] = mod
    return _loaded[name]


sd, bd = owner('scale_dock'), owner('bd_queue_wave')


class GhReader(bd.GitHubReader):
    """bd_queue_wave.GitHubReader over the gh CLI login; paginate() and its total_count check are inherited."""

    def __init__(self, run=subprocess.run, sleep=time.sleep):
        super().__init__(token='')
        self.run, self.sleep = run, sleep

    def get(self, route):
        if not route.startswith('/') or '..' in route or '\\' in route:
            raise ValueError('noncanonical API path')
        # A stale shell token would override the keyring login; gh alone authenticates.
        env = {k: v for k, v in os.environ.items() if k not in ('GITHUB_TOKEN', 'GH_TOKEN')}
        for attempt in range(3):  # bounded retry on 5xx/transport errors; a 4xx answer is final
            out = self.run(['gh', 'api', route[1:]], capture_output=True, text=True,
                           encoding='utf-8', env=env, timeout=120)
            if out.returncode == 0 or re.search(r'\(HTTP 4\d\d\)', out.stderr or '') or attempt == 2:
                break
            self.sleep(5 * (attempt + 1))
        if out.returncode != 0:
            raise OSError(f"gh api {route.split('?')[0]} exit {out.returncode}")
        return json.loads(out.stdout)


KEEP = {'default_branch', 'sha', 'total_count', 'workflow_runs', 'jobs', 'id', 'name', 'head_sha',
        'status', 'conclusion', 'run_attempt', 'run_id', 'workflow_name', 'steps', 'number',
        'html_url', 'created_at', 'completed_at', 'event'}


def trim(data):
    """Keep only the fields this adapter reads, for recorded API fixtures."""
    if isinstance(data, dict):
        return {k: trim(v) for k, v in data.items() if k in KEEP}
    return [trim(x) for x in data] if isinstance(data, list) else data


class Recorder:
    """Wraps a reader and records each response, trimmed, by route."""
    paginate = bd.GitHubReader.paginate

    def __init__(self, reader):
        self.reader, self.routes = reader, {}

    def get(self, route):
        data = self.reader.get(route)
        self.routes[route] = trim(data)
        return data


def head_of(reader, repo):
    branch = reader.get(f'/repos/{repo}')['default_branch']
    sha = reader.get(f'/repos/{repo}/commits/{branch}')['sha']
    sd.require(isinstance(sha, str) and sd.SHA.fullmatch(sha) is not None, repo + ' head SHA')
    return branch, sha


def job_key(repo, job):
    """Stable job identity across heads: harvest's normalized workflow :: job, environment kept apart."""
    h = owner('harvest')
    name, env = h.split_env(job.get('name') or '?')
    key = f"{repo}::{h.norm(job.get('workflow_name') or '?')} :: {h.norm(name)}"
    return key + (f' [{env}]' if env else '')


def native(job):
    """(run_id, attempt, job_id) only when all three are known; otherwise all None."""
    ids = tuple(job.get(k) for k in ('run_id', 'run_attempt', 'id'))
    return ids if all(type(v) is int and v > 0 for v in ids) else (None, None, None)


def root_of(occurrences, roots):
    """First EVERRED root whose match covers an occurrence, first failed step first (as harvest.main)."""
    h = owner('harvest')
    return next((r for o in occurrences for r in roots for m in r.get('match', []) if h.matches(o, m)), None)


def observe_repo(reader, repo, roots, previous):
    """Every Actions job on one exact default-branch head, latest attempt per job identity."""
    h = owner('harvest')
    branch, head = head_of(reader, repo)
    runs = reader.paginate(f'/repos/{repo}/actions/runs?head_sha={head}', key='workflow_runs')
    chosen, seen, running = {}, 0, 0
    for run in runs:
        sd.require(run.get('head_sha') == head, repo + ' run exact-head mismatch')
        if run.get('status') != 'completed':
            running += 1  # its job list is still growing; none of its jobs is eligible yet
            continue
        for job in reader.paginate(f"/repos/{repo}/actions/runs/{run['id']}/jobs", key='jobs'):
            sd.require(job.get('head_sha') == head, repo + ' job exact-head mismatch')
            job.setdefault('workflow_name', run.get('name'))
            seen += 1
            key = job_key(repo, job)
            rank = tuple(v if type(v) is int else 0 for v in (job.get('run_attempt'), job.get('run_id'), job.get('id')))
            # Highest attempt, then newest run and job, wins one identity slot (bd_queue_wave's rule per workflow).
            if key not in chosen or rank > chosen[key][0]:
                chosen[key] = (rank, job)
    findings, completed = [], 0
    for key, (_, job) in sorted(chosen.items()):
        if job.get('status') != 'completed' or job.get('conclusion') is None:
            continue
        completed += 1
        before = previous.get(key)
        state = ('RED' if job['conclusion'] == 'failure' else
                 'RECOVERED' if job['conclusion'] == 'success' and before and before['state'] == 'RED' else None)
        if state is None:
            continue
        run_id, attempt, job_id = native(job)
        row = {'id': key, 'repo': repo, 'source_sha': head, 'state': state, 'run_id': run_id,
               'attempt': attempt, 'job_id': job_id, 'owner_accepted': False, 'dag_node': repo,
               'mode': 'UNSUPERVISED_READONLY', 'mutation_paths': []}
        if state == 'RED':
            occ = h.occurrences_from_job(repo, job, None, f'{branch}:head')
            failed = sorted((s for s in job.get('steps') or [] if s.get('conclusion') == 'failure'),
                            key=lambda s: s.get('number') or 0)
            root = root_of(occ, roots)
            row.update(first_failed_step=(failed[0].get('name') or None) if failed else None,
                       fingerprint=occ[0]['signature'], root_id=root['id'] if root else None,
                       priority=root.get('severity') if root and root.get('severity') in sd.PRIORITY else 'UNKNOWN',
                       family=FAMILY[bd.family(job.get('workflow_name'))])
        else:
            row.update(first_failed_step=None, fingerprint=before.get('fingerprint'),
                       root_id=before.get('root_id'), priority=before['priority'], family=before['family'])
        findings.append(row)
    return {'branch': branch, 'head': head, 'findings': findings, 'eligible': completed,
            'provenance': {'branch': branch, 'runs': len(runs), 'runs_in_progress': running, 'jobs_seen': seen, 'job_identities': len(chosen),
                           'completed': completed, 'incomplete': len(chosen) - completed}}


def queue_of(reader, repos, at):
    ids, ages = [], []
    for repo in repos:
        for run in reader.paginate(f'/repos/{repo}/actions/runs?status=queued', key='workflow_runs'):
            created = bd.utc(run.get('created_at'))
            sd.require(type(run.get('id')) is int and run['id'] > 0 and created is not None, 'queued run identity')
            ids.append(run['id'])
            ages.append(max(0.0, round((at - created).total_seconds(), 3)))
    return {'queued_run_ids': ids, 'queue_ages_seconds': ages, 'verified_runner_slots': None, 'real_dispatches': 0}


def issue_bd(reader, stamp):
    """Live issue-BD projection: three public repos in full, private QPS as aggregate counts only."""
    summary, _, _ = bd.scan_public(reader)
    try:
        private, _, _ = bd.scan(reader, repos=(bd.PRIVATE_OWNER_REPO,))
        counts = {'private_qps_open_issues': private['open_issues'], 'private_qps_open_prs': private['open_prs'],
                  'private_qps_observation': 'GH_LOGIN_AGGREGATE_COUNT_NOT_OWNER_RECEIPT'}
    except (ValueError, OSError) as exc:
        counts = {'private_qps_open_issues': None, 'private_qps_open_prs': None,
                  'private_qps_observation': 'UNKNOWN_READ_FAILED:' + type(exc).__name__}
    # No private SHA, issue number, title or row leaves this function.
    return {**summary, **counts, 'generated_at': stamp}


def git_reader(cwd=HUB, run=subprocess.run):
    def git(args):
        return run(['git', *args], cwd=cwd, capture_output=True, check=True).stdout
    return git


def pin_file_docks(git, hub_sha):
    """Pin each committed projection at the hub's pulse head: one snapshot, one SHA."""
    pins = {}
    for name, path in FILE_DOCKS.items():
        try:
            oid = git(['rev-parse', f'{hub_sha}:{path}']).decode().strip()
        except subprocess.CalledProcessError as exc:
            raise ValueError(f'SCALE_DOCK_HOLD:{name} not at hub head (git fetch origin first)') from exc
        payload = json.loads(git(['cat-file', 'blob', oid]))
        sd.require(isinstance(payload, dict) and payload.get('schema') == sd.DOCK_SCHEMAS[name], name + ' schema')
        pins[name] = {'path': path, 'blob_oid': oid, 'sha256': sd.digest(payload)}
    return pins


def observe(reader, roots, previous, git, now=None):
    """One pulse record (N0 when previous is None); appended by append(), never rewritten."""
    at = (now or datetime.now(timezone.utc)).replace(microsecond=0)
    stamp = at.strftime('%Y-%m-%dT%H:%M:%SZ')
    before = {f['id']: f for f in previous['pulse']['findings']} if previous else {}
    heads, findings, provenance, eligible = {}, [], {}, 0
    for repo in bd.PUBLIC_REPOS:
        seen = observe_repo(reader, repo, roots, before)
        heads[repo] = seen['head']
        findings += seen['findings']
        provenance[repo] = seen['provenance']
        eligible += seen['eligible']
    sd.positive(eligible, 'no completed job on any observed head')
    hub_sha = heads['GBOGEB/pipeline-automation-hub']
    n = previous['n'] + 1 if previous else 0
    pulse = {'n': n, 'observed_at': stamp, 'source_heads': heads, 'eligible': eligible,
             'findings': findings, 'coverage': [], 'queue': queue_of(reader, bd.PUBLIC_REPOS, at)}
    return {'schema': LEDGER_SCHEMA, 'n': n, 'observed_at': stamp, 'prev_sha256': None,
            'hub_sha': hub_sha, 'pulse': pulse, 'provenance': provenance,
            'file_docks': pin_file_docks(git, hub_sha), 'issue_bd': issue_bd(reader, stamp),
            'authority': 'READ_ONLY_OBSERVATION_NO_ROOT_CLOSURE_NO_DISPATCH'}


def line(record):
    return json.dumps(record, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)


def sha256(text):
    return hashlib.sha256(text.encode('ascii')).hexdigest()


def verify(lines):
    """Ordinals 0..k, sha256 chain, canonical lines and strictly later pulse times."""
    records, prev, last = [], None, None
    for i, text in enumerate(lines):
        try:
            rec = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError('SCALE_DOCK_HOLD:ledger line not JSON') from exc
        sd.require(isinstance(rec, dict) and text == line(rec), 'ledger line not canonical')
        sd.require(rec.get('schema') == LEDGER_SCHEMA and rec.get('n') == i
                   and isinstance(rec.get('pulse'), dict) and rec['pulse'].get('n') == i, 'ledger ordinal')
        sd.require(rec.get('prev_sha256') == prev, 'ledger chain broken')
        at = sd.utc(rec.get('observed_at'))
        sd.require(rec['pulse'].get('observed_at') == rec['observed_at'], 'ledger pulse time')
        sd.require(last is None or at > last, 'ledger time not monotone')
        prev, last = sha256(text), at
        records.append(rec)
    return records


def read_ledger(path):
    if not path.exists():
        return [], []
    raw = path.read_text(encoding='ascii')
    sd.require(raw == '' or raw.endswith('\n'), 'ledger truncated')
    lines = raw.splitlines()
    return verify(lines), lines


def append(path, record):
    records, lines = read_ledger(path)
    sd.require(record.get('n') == len(records), 'ledger append ordinal')
    record = {**record, 'prev_sha256': sha256(lines[-1]) if lines else None}
    verify([*lines, line(record)])
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='ascii', newline='\n') as fh:  # append only; earlier pulses are never rewritten
        fh.write(line(record) + '\n')
    return record


def series(records, git):
    """The last WINDOW pulses as a codepurple.scale-dock.series.v1 doc, docks from the latest pulse."""
    sd.require(bool(records), 'empty ledger')
    latest = records[-1]
    docks = {'issue_bd': latest['issue_bd']}
    for name, pin in latest['file_docks'].items():
        payload = json.loads(git(['cat-file', 'blob', pin['blob_oid']]))
        sd.require(sd.digest(payload) == pin['sha256'], name + ' pinned blob digest')
        docks[name] = payload
    doc = {'schema': sd.SCHEMA, 'observation_class': 'HISTORICAL_REPLAY', 'cohort_id': COHORT,
           'controls': dict(CONTROLS), 'repos': list(bd.PUBLIC_REPOS),
           'dag': {'nodes': list(bd.PUBLIC_REPOS), 'hard_edges': []},
           'gg_math_provider_sha': None, 'gg_math_decision': None,
           'pulses': [r['pulse'] for r in records[-WINDOW:]], 'docks': docks,
           'ledger': {'schema': LEDGER_SCHEMA, 'pulses': len(records), 'window_first_n': records[-WINDOW:][0]['n'],
                      'latest_n': latest['n'], 'latest_hub_sha': latest['hub_sha']}}
    sd.evaluate(doc)  # fail closed before anything is written
    return doc


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest='cmd', required=True)
    a = sub.add_parser('pulse', help='observe live and append one pulse')
    a.add_argument('--ledger', type=Path, default=LEDGER)
    a.add_argument('--roots', type=Path, default=ROOTS)
    a.add_argument('--record', type=Path, help='write trimmed public default-head API responses as a fixture')
    b = sub.add_parser('series', help='build the scale-dock series from the ledger')
    b.add_argument('--ledger', type=Path, default=LEDGER)
    b.add_argument('--out', type=Path, required=True)
    args = p.parse_args(argv)
    git = git_reader()
    records, _ = read_ledger(args.ledger)
    if args.cmd == 'series':
        args.out.write_bytes(sd.encoded(series(records, git)))
        print(json.dumps({'pulses': len(records), 'out': str(args.out)}))
        return 0
    import yaml  # live pulses only; tests and series builds need no PyYAML
    roots = yaml.safe_load(args.roots.read_text(encoding='utf-8'))['roots']
    reader = Recorder(GhReader()) if args.record else GhReader()
    record = append(args.ledger, observe(reader, roots, records[-1] if records else None, git))
    if args.record:
        # Public default-head routes only: never PR, issue-search or private-repo responses.
        keep = {r: v for r, v in reader.routes.items() if '/pulls' not in r and '/search/' not in r
                and 'event=pull_request' not in r and bd.PRIVATE_OWNER_REPO not in r}
        args.record.write_bytes(sd.encoded(keep))
    pulse = record['pulse']
    print(json.dumps({'n': record['n'], 'observed_at': record['observed_at'], 'eligible': pulse['eligible'],
                      'red': sum(f['state'] == 'RED' for f in pulse['findings']),
                      'recovered': sum(f['state'] == 'RECOVERED' for f in pulse['findings']),
                      'queued': len(pulse['queue']['queued_run_ids']),
                      'private_qps': record['issue_bd']['private_qps_observation']}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
