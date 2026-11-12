#!/usr/bin/env python3
"""PR intervention ledger: act on a randomized part of the eligible PRs, keep a holdout, then measure.

Interventions (one per experiment, `--intervention`):
  UPDATE       bring the PR branch up to date with its base (GitHub update-branch)       slice 1
  RERUN        rerun the failed jobs of the newest failed run on the exact head           slice 2
  DEBUG_RERUN  the same rerun with step debug logging (an LDAB debug_receipt observation) slice 2
For the rerun levels, rerun_triage.plan() decides per PR and only its RERUN_FAILED_JOBS_CANDIDATE /
DEBUG_RERUN_CANDIDATE PRs are eligible. A PR behind its base is RECONCILE_MAIN there, so the rerun
levels and UPDATE never act on the same PR.

An experiment is three kinds of record in one append-only ledger, chained by sha256:
  before  one pulse: each base branch head read once (AGENTS.md L6), a snapshot of every open PR,
          the reasons a PR is not eligible, and a deterministic TREATED / HOLDOUT arm per eligible PR
  act     the writes for the TREATED arm (GitHub is written only with --apply)
  after   the same PRs re-read: per-PR transitions, the effect estimate (treated minus holdout,
          intention to treat), positive transitions with their candidate causes ("butterflies")
          and, for DEBUG_RERUN on ABACUS / CODEX, LDAB debug_receipt observations

A PR that turns green or loses its conflict is a positive transition. Its attribution is
DELIVERED_BY_UPDATE (its head is exactly the one our update produced), DELIVERED_BY_RERUN (head
unchanged, our rerun was accepted), EXTERNAL (head unchanged, nothing of ours: a rerun by someone
else, a base change or another repository), AUTHOR_PUSH or UNVERIFIED. The base-window commits are
ranked by how many files they share with the PR. They are candidates, never proven root fixes.

The census context is the latest scale-dock pulse (scale_dock_series ledger) at before and after;
when both name the same pulse the delta is SAME_PULSE, not zero. Actions minutes and
cross-repository attribution stay UNKNOWN.

Owner functions are imported, never copied (AGENTS.md L4):
  scale_dock_series  GhReader (gh login, bounded retry), line, sha256, read_ledger, LEDGER, LEDGER_SCHEMA
  bd_queue_wave      utc
  rerun_triage       plan, SCHEMA, TRANSIENT_CAUSES (rerun / debug-rerun decisions)
  bd_ldab_consumer   check_observation (LDAB debug_receipt contract, ABACUS-owned schema)

GitHub writes go through the operator's gh login only. Commits pushed with an Actions GITHUB_TOKEN do
not start pull_request workflows, so an update made from Actions would never be measured.

Usage:
  python pr_intervention.py before --repo GBOGEB/pipeline-automation-hub [--min-age-days 7] [--holdout 0.2]
  python pr_intervention.py act    --experiment PRX-... [--apply]
  python pr_intervention.py after  --experiment PRX-... [--min-hours 2]
  python pr_intervention.py report --experiment PRX-... [--out report.md]
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
HUB = HERE.parents[1]
LEDGER = HUB / 'out' / 'pr_intervention' / 'ledger.jsonl'  # out/ is gitignored: local evidence
SCHEMA = 'gogreen.pr-intervention.ledger.v1'
KINDS = ('before', 'act', 'after')
METHODS = ('MERGE', 'REBASE')
ARMS = ('TREATED', 'HOLDOUT')
INTERVENTIONS = ('UPDATE', 'RERUN', 'DEBUG_RERUN')
# The rerun_triage decision that makes a PR eligible for each rerun level.
TRIAGE_WANTED = {'RERUN': 'RERUN_FAILED_JOBS_CANDIDATE', 'DEBUG_RERUN': 'DEBUG_RERUN_CANDIDATE'}
POLICY = {'min_age_days': 7.0, 'min_behind': 1, 'holdout': 0.2, 'quiet_hours': 24.0, 'method': 'MERGE',
          'intervention': 'UPDATE', 'opt_out_labels': ['no-auto-update', 'do-not-rebase'],
          'gate_checks': ['first-pass-closure'], 'min_arm': 5}
LDAB_REPOS = ('GBOGEB/ABACUS', 'GBOGEB/CODEX')  # bd_ldab_consumer accepts native evidence from these only
CONTROLS = {'authority_transfer': False, 'merge_admission': 'HOLD', 'root_closure': False,
            'ldab': 'DEBUG_RECEIPTS_REPORTED_UNVERIFIED', 'actions_minutes': 'UNKNOWN',
            'cross_repo_attribution': 'UNKNOWN_SLICE_3'}
PASS = {'SUCCESS', 'NEUTRAL', 'SKIPPED'}
FAIL = {'FAILURE', 'TIMED_OUT', 'ACTION_REQUIRED', 'STARTUP_FAILURE', 'ERROR'}
PR_FIELDS = ('number,state,headRefOid,headRefName,baseRefName,isDraft,isCrossRepository,createdAt,'
             'mergeStateStatus,mergeable,labels,statusCheckRollup,mergedAt')
# Listing every open PR with its check rollup in one GraphQL query answered HTTP 502 three times running
# (hub, 2026-11-11). The list carries no rollup; each PR's rollup is read on its own with `gh pr view`.
LIST_FIELDS = 'number,baseRefName'
SHA = re.compile(r'[0-9a-f]{40}')
REPO = re.compile(r'GBOGEB/[A-Za-z0-9._-]+')
EXPERIMENT = re.compile(r'PRX-[0-9A-Za-z-]{1,40}')
PR_REF = re.compile(r'\(#(\d+)\)\s*$')
WINDOW_COMMITS = 50
Z95 = 1.959963984540054


def _load(name, path):
    spec = importlib.util.spec_from_file_location('pr_intervention_' + name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sds = _load('scale_dock_series', HERE / 'scale_dock_series.py')
bd = sds.bd
rt = _load('rerun_triage', HERE / 'rerun_triage.py')
ldab = _load('bd_ldab_consumer', HUB / 'mission-control' / 'federation-atlas' / 'bd_ldab_consumer.py')


def require(ok, message):
    if not ok:
        raise ValueError('PRX_HOLD:' + message)


def stamp(at):
    return at.astimezone(timezone.utc).replace(microsecond=0).strftime('%Y-%m-%dT%H:%M:%SZ')


def when(value):
    t = bd.utc(value)
    require(t is not None, 'timestamp ' + repr(value))
    return t


def _env():
    # A stale shell token would override the keyring login; gh alone authenticates.
    return {k: v for k, v in os.environ.items() if k not in ('GITHUB_TOKEN', 'GH_TOKEN')}


class Client:
    """Reads: REST through scale_dock_series.GhReader, PR check rollups and compares through gh."""

    def __init__(self, run=subprocess.run, sleep=time.sleep):
        self.rest, self.run, self.sleep = sds.GhReader(run=run, sleep=sleep), run, sleep

    def get(self, route):
        return self.rest.get(route)

    def paginate(self, route, key=None):
        return self.rest.paginate(route, key=key)

    def _gh(self, args):
        for attempt in range(3):  # bounded retry on 5xx/transport errors, as GhReader.get; a 4xx answer is final
            out = self.run(['gh', *args], capture_output=True, text=True, encoding='utf-8', env=_env(), timeout=180)
            if out.returncode == 0 or re.search(r'\(HTTP 4\d\d\)', out.stderr or '') or attempt == 2:
                break
            self.sleep(5 * (attempt + 1))
        if out.returncode != 0:
            first = ((out.stderr or '').strip().splitlines() or [''])[0][:160]
            raise OSError(f'gh {args[0]} {args[1]} exit {out.returncode}: {first}')
        return json.loads(out.stdout)

    def prs(self, repo):
        return self._gh(['pr', 'list', '-R', repo, '--state', 'open', '--limit', '1000', '--json', LIST_FIELDS])

    def pr(self, repo, number):
        return self._gh(['pr', 'view', str(number), '-R', repo, '--json', PR_FIELDS])

    def compare(self, repo, base, head):
        # GhReader refuses '..' in a route (path traversal guard); a compare of two exact SHAs is safe.
        require(SHA.fullmatch(base or '') and SHA.fullmatch(head or ''), 'compare needs two exact SHAs')
        return self._gh(['api', f'repos/{repo}/compare/{base}...{head}'])


class Writer:
    """The only GitHub writes: update one PR branch, or rerun one run's failed jobs. act() guards both."""

    def __init__(self, run=subprocess.run):
        self.run = run

    def _call(self, args):
        return self.run(args, capture_output=True, text=True, encoding='utf-8', env=_env(), timeout=120)

    @staticmethod
    def _failed(out):
        code = re.search(r'\(HTTP (\d{3})\)', out.stderr or '')
        return 'FAILED', ('HTTP_' + code.group(1)) if code else f'EXIT_{out.returncode}'

    def update_branch(self, repo, number, expected_head, method):
        """Both methods are atomic on the recorded head: GitHub refuses the write if the head moved."""
        if method == 'MERGE':
            out = self._call(['gh', 'api', '-X', 'PUT', f'repos/{repo}/pulls/{number}/update-branch',
                              '-f', f'expected_head_sha={expected_head}'])
            return ('ACCEPTED', None) if out.returncode == 0 else self._failed(out)
        # `gh pr update-branch --rebase` has no head guard; GraphQL updatePullRequestBranch takes expectedHeadOid.
        node = self._call(['gh', 'pr', 'view', str(number), '-R', repo, '--json', 'id', '--jq', '.id'])
        if node.returncode != 0 or not node.stdout.strip():
            return self._failed(node)
        out = self._call(['gh', 'api', 'graphql',
                          '-f', 'query=mutation($id:ID!,$oid:GitObjectID!){updatePullRequestBranch(input:'
                                '{pullRequestId:$id,expectedHeadOid:$oid,updateMethod:REBASE}){pullRequest{headRefOid}}}',
                          '-f', f'id={node.stdout.strip()}', '-f', f'oid={expected_head}'])
        if out.returncode != 0 or '"errors"' in (out.stdout or ''):
            return self._failed(out) if out.returncode != 0 else ('FAILED', 'GRAPHQL_ERROR')
        return 'ACCEPTED', None

    def rerun_failed(self, repo, run_id, debug):
        # Failed jobs only (bounded CI spend); --debug turns on runner and step debug logging.
        out = self._call(['gh', 'run', 'rerun', str(run_id), '--failed', '-R', repo, *(['--debug'] if debug else [])])
        return ('ACCEPTED', None) if out.returncode == 0 else self._failed(out)


# ---------------------------------------------------------------- snapshot

def check_id(c):
    if c.get('__typename') == 'StatusContext':
        return 'status :: ' + (c.get('context') or '?')
    return f"{c.get('workflowName') or '?'} :: {c.get('name') or '?'}"


def verdict(c):
    if c.get('__typename') == 'StatusContext':
        s = (c.get('state') or '').upper()
        return 'pass' if s == 'SUCCESS' else 'fail' if s in ('FAILURE', 'ERROR') else 'pending'
    if (c.get('status') or '').upper() != 'COMPLETED':
        return 'pending'
    k = (c.get('conclusion') or '').upper()
    # The latest run of this identity was cancelled or went stale: nothing later superseded it, so it is
    # not evidence of success. It stays non-green (pending) instead of dropping out of the count.
    return 'pass' if k in PASS else 'fail' if k in FAIL else 'pending'


def checks(rollup, gates):
    """Latest check per identity. CI and gate checks are judged apart: a red gate is a missing receipt, not code."""
    latest = {}
    for c in rollup or []:
        key = check_id(c)
        order = c.get('startedAt') or c.get('completedAt') or c.get('createdAt') or ''
        if key not in latest or order >= latest[key][0]:
            latest[key] = (order, c)
    lanes = {lane: {'fail': [], 'pending': [], 'pass': 0} for lane in ('ci', 'gate')}
    for key, (_, c) in sorted(latest.items()):
        # A gate reports twice: a check run named 'first-pass-closure' and a commit status whose context
        # is '<workflow> / first-pass-closure'. Both belong to the gate lane.
        label = c.get('name') or c.get('context') or ''
        lane = lanes['gate' if label in gates or label.rsplit(' / ', 1)[-1] in gates else 'ci']
        v = verdict(c)
        if v == 'fail':
            lane['fail'].append(key)
        elif v == 'pending':
            lane['pending'].append(key)
        elif v == 'pass':
            lane['pass'] += 1
    return lanes


def state_of(lane):
    return 'RED' if lane['fail'] else 'PENDING' if lane['pending'] else 'GREEN' if lane['pass'] else 'NO_CHECKS'


def pr_row(client, repo, pr, base_sha, policy, now):
    head = pr.get('headRefOid')
    require(isinstance(head, str) and SHA.fullmatch(head) is not None, f'{repo}#{pr.get("number")} head SHA')
    try:
        cmp = client.compare(repo, base_sha, head)
    except (OSError, ValueError):
        cmp = {}  # UNKNOWN, never zero
    commits = cmp.get('commits') or []
    head_at = ((commits[-1].get('commit') or {}).get('committer') or {}).get('date') if commits else None
    lanes = checks(pr.get('statusCheckRollup'), set(policy['gate_checks']))
    created = when(pr.get('createdAt'))
    return {'repo': repo, 'number': pr['number'], 'state': pr.get('state') or 'OPEN',
            'head_ref': pr.get('headRefName'), 'head_sha': head, 'base_ref': pr.get('baseRefName'),
            'base_sha': base_sha, 'merge_base': (cmp.get('merge_base_commit') or {}).get('sha'),
            'created_at': pr.get('createdAt'), 'age_days': round((now - created).total_seconds() / 86400, 3),
            'draft': bool(pr.get('isDraft')), 'cross_repo': bool(pr.get('isCrossRepository')),
            'labels': sorted(lb.get('name', '') for lb in pr.get('labels') or []),
            'merge_state': pr.get('mergeStateStatus'), 'mergeable': pr.get('mergeable'),
            'behind_by': cmp.get('behind_by'), 'ahead_by': cmp.get('ahead_by'), 'head_committed_at': head_at,
            'ci_state': state_of(lanes['ci']), 'ci_failing': lanes['ci']['fail'],
            'gate_state': state_of(lanes['gate']), 'gate_failing': lanes['gate']['fail'],
            'merged_at': pr.get('mergedAt')}


def reasons(row, default_branch, policy, now):
    """Every reason a PR is not eligible; an empty list means eligible."""
    r = []
    if row['draft']:
        r.append('DRAFT')
    if row['cross_repo']:
        r.append('FORK')
    if row['base_ref'] != default_branch:
        r.append('STACKED')
    if row['age_days'] < policy['min_age_days']:
        r.append('YOUNG')
    if policy['intervention'] == 'UPDATE':
        if row['behind_by'] is None:
            r.append('BEHIND_UNKNOWN')
        elif row['behind_by'] < policy['min_behind']:
            r.append('CURRENT')
    else:  # rerun levels: rerun_triage decides; only its candidate decision for this level is eligible
        t = row.get('triage') or {}
        if t.get('decision') != TRIAGE_WANTED[policy['intervention']]:
            r.append('TRIAGE_' + (t.get('decision') or t.get('reason') or 'UNKNOWN'))
    if row['mergeable'] == 'CONFLICTING' or row['merge_state'] == 'DIRTY':
        r.append('CONFLICT')  # update-branch cannot resolve it; the PR_CONFLICT_RUNBOOK owns that path
    pushed = bd.utc(row['head_committed_at'])
    if pushed is None:
        r.append('PUSH_TIME_UNKNOWN')
    elif (now - pushed).total_seconds() < policy['quiet_hours'] * 3600:
        r.append('RECENT_PUSH')  # head commit time: a proxy for a live session on the branch
    if set(row['labels']) & set(policy['opt_out_labels']):
        r.append('OPT_OUT_LABEL')
    return r


def newest_run(client, repo, head):
    """Newest completed run on the exact head, failed runs first, with its latest-attempt jobs; None if none."""
    runs = [r for r in client.paginate(f'/repos/{repo}/actions/runs?head_sha={head}', key='workflow_runs')
            if r.get('head_sha') == head and r.get('status') == 'completed']
    if not runs:
        return None
    run = max(runs, key=lambda r: (r.get('conclusion') == 'failure', r.get('updated_at') or '', r.get('id') or 0))
    return run, client.paginate(f"/repos/{repo}/actions/runs/{run['id']}/jobs", key='jobs')


def classify(run, jobs):
    """Job-metadata classifier over ALL failed jobs, no log download: (failure_kind, cause, logs_insufficient, job).

    `gh run rerun --failed` reruns every failed job of the run, so the run is judged by its most
    actionable failed job, conservatively:
    - any failed job with a failed step: UNCLASSIFIED, logs sufficient -> rerun_triage INSPECT_FIRSTRED;
    - else every failed job ran no step (lost its runner): TRANSIENT runner_lost -> rerun candidate;
    - else (a failed job ran steps but none failed): UNCLASSIFIED, logs insufficient -> debug candidate.
    """
    if run.get('conclusion') != 'failure':
        return 'NONE', None, False, (jobs[0] if jobs else None)
    failed = sorted((j for j in jobs if j.get('conclusion') == 'failure'), key=lambda j: j.get('id') or 0)
    if not failed:
        return 'UNCLASSIFIED', None, True, (jobs[0] if jobs else None)
    stepped = [j for j in failed if j.get('steps')]
    red = [j for j in stepped if any(s.get('conclusion') == 'failure' for s in j['steps'])]
    if red:
        return 'UNCLASSIFIED', None, False, red[0]
    if not stepped:
        return 'TRANSIENT', 'runner_lost', False, failed[0]
    return 'UNCLASSIFIED', None, True, stepped[0]


def triage(client, repo, rows, main_sha, now):
    """rerun_triage.plan() over this repo's PRs; its decision and the run it judged go on each row."""
    items, runs = [], {}
    for row in rows:
        if row['behind_by'] is None:
            row['triage'] = {'decision': None, 'reason': 'BEHIND_UNKNOWN'}
            continue
        try:
            found = newest_run(client, repo, row['head_sha'])
        except (OSError, ValueError):
            row['triage'] = {'decision': None, 'reason': 'RUNS_UNREADABLE'}
            continue
        run = None
        if found:
            r, jobs = found
            kind, cause, thin, job = classify(r, jobs)
            if job is not None:
                run = {'id': r['id'], 'attempt': r.get('run_attempt') or 1, 'job_id': job['id'],
                       'head_sha': r['head_sha'], 'status': 'completed', 'conclusion': r['conclusion'],
                       'failure_kind': kind, 'logs_insufficient': thin, 'cause': cause}
                runs[row['number']] = {**run, 'job_name': job.get('name'), 'workflow': r.get('name')}
        items.append({'pr': row['number'], 'head_sha': row['head_sha'], 'behind_main': row['behind_by'],
                      'created_at': row['created_at'], 'run': run, 'root_id': None})
    if not items:
        return None
    receipt = rt.plan({'schema': rt.SCHEMA, 'authority_transfer': False, 'observed_at': stamp(now),
                       'main_sha': main_sha, 'items': items})
    by_number = {row['number']: row for row in rows}
    for out in receipt['rows']:
        run = runs.get(out['pr']) or {}
        by_number[out['pr']]['triage'] = {
            'decision': out['decision'], 'reason': out['reason'], 'run_id': run.get('id'),
            'run_attempt': run.get('attempt'), 'job_id': run.get('job_id'), 'job_name': run.get('job_name'),
            'workflow': run.get('workflow'), 'failure_kind': run.get('failure_kind'),
            'cause': run.get('cause'), 'logs_insufficient': run.get('logs_insufficient'),
            'classifier': 'job_metadata_v1'}
    return receipt['kpi']['counts']


def arm_of(experiment, repo, number, head, holdout):
    """Deterministic, auditable assignment: anyone can recompute it from the ledger."""
    h = hashlib.sha256(f'{experiment}|{repo}#{number}|{head}'.encode('ascii')).hexdigest()
    return 'HOLDOUT' if int(h[:13], 16) / 16 ** 13 < holdout else 'TREATED'


def base_head(client, repo, ref, cache):
    if (repo, ref) not in cache:
        sha = client.get(f'/repos/{repo}/commits/{ref}').get('sha')
        require(isinstance(sha, str) and SHA.fullmatch(sha) is not None, f'{repo}:{ref} head SHA')
        cache[(repo, ref)] = sha
    return cache[(repo, ref)]


def census_ref(path):
    """The latest scale-dock pulse as census context; unreadable or empty is UNKNOWN, never zero."""
    try:
        records, lines = sds.read_ledger(Path(path))
    except (ValueError, OSError) as exc:
        return {'status': 'UNKNOWN_UNREADABLE:' + type(exc).__name__}
    if not records:
        return {'status': 'UNKNOWN_EMPTY'}
    last, red = records[-1], {}
    for f in last['pulse']['findings']:
        if f['state'] == 'RED':
            red[f['repo']] = red.get(f['repo'], 0) + 1
    return {'status': 'OK', 'ledger_schema': sds.LEDGER_SCHEMA, 'n': last['n'], 'observed_at': last['observed_at'],
            'hub_sha': last['hub_sha'], 'line_sha256': sds.sha256(lines[-1]), 'red_by_repo': red}


def before(client, repos, policy, experiment, now, census):
    require(EXPERIMENT.fullmatch(experiment) is not None, 'experiment id')
    pulse, rows, cache = {}, [], {}
    for repo in repos:
        require(REPO.fullmatch(repo) is not None, 'repo ' + repr(repo))
        default = client.get(f'/repos/{repo}')['default_branch']
        prs = sorted(client.prs(repo), key=lambda p: p['number'])
        for ref in sorted({default, *(p['baseRefName'] for p in prs)}):
            base_head(client, repo, ref, cache)  # each base head read once per pulse (L6)
        pulse[repo] = {'default_branch': default,
                       'base_heads': {ref: sha for (r, ref), sha in sorted(cache.items()) if r == repo}}
        mine = []
        for listed in prs:
            pr = client.pr(repo, listed['number'])
            mine.append(pr_row(client, repo, pr, base_head(client, repo, pr['baseRefName'], cache), policy, now))
        if policy['intervention'] != 'UPDATE':
            pulse[repo]['triage_counts'] = triage(client, repo, mine, cache[(repo, default)], now)
        for row in mine:
            row['skip'] = reasons(row, default, policy, now)
            row['arm'] = None if row['skip'] else arm_of(experiment, repo, row['number'], row['head_sha'],
                                                         policy['holdout'])
        rows += mine
    arms = {a: sum(r['arm'] == a for r in rows) for a in ARMS}
    return {'kind': 'before', 'experiment': experiment, 'recorded_at': stamp(now), 'policy': policy,
            'controls': CONTROLS, 'pulse': pulse, 'census': census, 'prs': rows,
            'counts': {'open': len(rows), 'eligible': arms['TREATED'] + arms['HOLDOUT'], **arms}}


# ---------------------------------------------------------------- act

def live_guard(row, live, opt_out):
    """Mutation safety re-read immediately before the write: labels, draft and base change without moving the head."""
    if live.get('state') != 'OPEN':
        return 'NOT_OPEN'
    if live.get('headRefOid') != row['head_sha']:
        return 'HEAD_MOVED'
    if live.get('isDraft'):
        return 'DRAFT'
    if live.get('baseRefName') != row['base_ref']:
        return 'BASE_CHANGED'
    if {lb.get('name') for lb in live.get('labels') or []} & opt_out:
        return 'OPT_OUT_LABEL'
    if live.get('mergeable') == 'CONFLICTING' or live.get('mergeStateStatus') == 'DIRTY':
        return 'CONFLICT'
    return None


def updated_head(client, row, method, sleep, tries=6):
    """The exact head the update produced, read back so `after` compares SHAs; None when not confirmed."""
    for attempt in range(tries):
        try:
            head = client.pr(row['repo'], row['number']).get('headRefOid')
        except (OSError, ValueError):
            head = None
        if head and head != row['head_sha']:
            if method != 'MERGE':
                return head  # a rebase rewrites every commit: the first new head seen is the best evidence
            try:  # a merge update's commit has the recorded head as its first parent; anything else is not ours
                parents = [p.get('sha') for p in client.get(f"/repos/{row['repo']}/commits/{head}").get('parents') or []]
            except (OSError, ValueError):
                return None
            return head if parents[:1] == [row['head_sha']] else None
        if attempt < tries - 1:
            sleep(5)
    return None


def run_guard(client, row):
    """The run triage judged must still be the same completed, failed attempt: anyone's rerun moves it."""
    t = row.get('triage') or {}
    try:
        run = client.get(f"/repos/{row['repo']}/actions/runs/{t['run_id']}")
    except (OSError, ValueError, KeyError):
        return 'RUN_UNREADABLE'
    if (run.get('run_attempt') != t.get('run_attempt') or run.get('status') != 'completed'
            or run.get('conclusion') != 'failure'):
        return 'RUN_MOVED'
    return None


def act(client, writer, b, apply, now, sleep=time.sleep):
    method, results = b['policy']['method'], []
    intervention = b['policy'].get('intervention', 'UPDATE')
    opt_out = set(b['policy']['opt_out_labels'])
    for row in b['prs']:
        if row['arm'] != 'TREATED':
            continue
        new_head, wrote = None, False
        # One PR's failure never loses the others: every result, including writes already made, reaches the
        # act record. An error after the write was issued is UNKNOWN (it may have landed), never a skip.
        try:
            reason = live_guard(row, client.pr(row['repo'], row['number']), opt_out)
            if not reason and intervention != 'UPDATE':
                reason = run_guard(client, row)
            if reason:
                res = ('SKIPPED', reason)
            elif not apply:
                res = ('PLANNED', None)
            elif intervention == 'UPDATE':
                wrote = True
                res = writer.update_branch(row['repo'], row['number'], row['head_sha'], method)
                if res[0] == 'ACCEPTED':
                    new_head = updated_head(client, row, method, sleep)
            else:
                wrote = True
                res = writer.rerun_failed(row['repo'], row['triage']['run_id'], intervention == 'DEBUG_RERUN')
        except Exception as exc:  # noqa: BLE001 - recorded per PR, never swallowed silently
            res = ('UNKNOWN' if wrote else 'ERROR', type(exc).__name__)
        out = {'repo': row['repo'], 'number': row['number'], 'head_sha': row['head_sha'],
               'result': res[0], 'detail': res[1], 'new_head': new_head}
        if intervention != 'UPDATE':
            out.update(run_id=row['triage']['run_id'], run_attempt=row['triage']['run_attempt'])
        results.append(out)
    accepted = sum(r['result'] == 'ACCEPTED' for r in results)
    return {'kind': 'act', 'experiment': b['experiment'], 'recorded_at': stamp(now), 'method': method,
            'intervention': intervention, 'applied': bool(apply), 'results': results,
            'counts': {k: sum(r['result'] == k for r in results)
                       for k in ('PLANNED', 'ACCEPTED', 'FAILED', 'SKIPPED', 'ERROR', 'UNKNOWN')},
            # An accepted update moves the head, so its First-Pass Closure receipt must be written again.
            # A rerun keeps the head: the receipt stays bound to it.
            'fpc_receipts_invalidated': accepted if intervention == 'UPDATE' else 0}


# ---------------------------------------------------------------- after / evaluate

def wilson(x, n, z=Z95):
    if n == 0:
        return None
    p, den = x / n, 1 + z * z / n
    c, h = (p + z * z / (2 * n)) / den, z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, c - h), min(1.0, c + h)


def newcombe(x1, n1, x2, n2):
    """Difference of two proportions with Newcombe's hybrid score interval (method 10)."""
    p1, p2 = x1 / n1, x2 / n2
    (l1, u1), (l2, u2) = wilson(x1, n1), wilson(x2, n2)
    d = p1 - p2
    return d, (d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2), d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2))


def outcome(a):
    if a is None:
        return 'UNREADABLE'
    if a['state'] == 'MERGED':
        return 'MERGED'
    if a['state'] == 'CLOSED':
        return 'CLOSED'
    return a['ci_state']


def success(o):
    # Closed without merging is a known non-success: dropping it would shrink the intention-to-treat denominator.
    return True if o in ('GREEN', 'MERGED') else False if o in ('RED', 'CLOSED') else None


def transition(before_ci, o):
    if o == 'CLOSED':
        return 'CLOSED_UNMERGED'
    s = success(o)
    if s is None:
        return 'UNKNOWN'
    if s:
        return 'UNBLOCKED' if before_ci == 'RED' else 'STAYED_GREEN' if before_ci == 'GREEN' else 'SETTLED_GREEN'
    return 'REGRESSED' if before_ci == 'GREEN' else 'STILL_RED' if before_ci == 'RED' else 'SETTLED_RED'


def head_change(b, a, act_row, method, parents=None):
    """Exact identity, never inferred from commit counts: a force-push can keep the ahead count unchanged."""
    if a is None or a['head_sha'] == b['head_sha']:
        return 'HEAD_UNCHANGED'
    if act_row and act_row['result'] == 'UNKNOWN':
        return 'UNVERIFIED_HEAD'  # our write may have landed: neither ours nor the author's is provable
    if not act_row or act_row['result'] != 'ACCEPTED':
        return 'AUTHOR_PUSH'
    if act_row.get('new_head'):
        return 'UPDATE_ONLY' if a['head_sha'] == act_row['new_head'] else 'AUTHOR_PUSH'
    # Head not read back at act time: a merge update's commit has two parents, the first being the recorded head.
    if method == 'MERGE' and parents is not None and len(parents) == 2 and parents[0] == b['head_sha']:
        return 'UPDATE_ONLY'
    return 'UNVERIFIED_HEAD'


def arm_stats(rows, arm):
    mine = [r for r in rows if r['arm'] == arm]
    known = [r for r in mine if r['success'] is not None]
    x = sum(r['success'] for r in known)
    red = [r for r in known if r['before_ci'] == 'RED']
    green = [r for r in known if r['before_ci'] == 'GREEN']
    ci = wilson(x, len(known))
    return {'assigned': len(mine), 'known': len(known), 'unknown': len(mine) - len(known), 'success': x,
            'rate': round(x / len(known), 4) if known else None, 'ci95': [round(v, 4) for v in ci] if ci else None,
            'red_before': len(red), 'unblocked': sum(r['success'] for r in red),
            'green_before': len(green), 'regressed': sum(r['transition'] == 'REGRESSED' for r in green),
            'closed_unmerged': sum(r['transition'] == 'CLOSED_UNMERGED' for r in mine),
            'author_push': sum(r['head_change'] == 'AUTHOR_PUSH' for r in mine),
            'gate_regressed': sum(r['gate_regressed'] for r in mine)}


def effect(xt, nt, xh, nh, min_arm):
    if nt < min_arm or nh < min_arm:
        return {'status': 'UNKNOWN_SMALL_ARM', 'min_arm': min_arm, 'diff': None, 'ci95': None}
    d, (lo, hi) = newcombe(xt, nt, xh, nh)
    return {'status': 'OK', 'method': 'newcombe_hybrid_score', 'diff': round(d, 4), 'ci95': [round(lo, 4), round(hi, 4)]}


def base_window(client, repo, start, end, cache):
    key = (repo, start, end)
    if key not in cache:
        if not start or not end or start == end:
            cache[key] = {'from': start, 'to': end, 'commits': [], 'truncated': False}
        else:
            try:
                commits = client.compare(repo, start, end).get('commits') or []
            except (OSError, ValueError):
                commits = None
            cache[key] = {'from': start, 'to': end, 'commits': None if commits is None else commits[-WINDOW_COMMITS:][::-1],
                          'truncated': commits is not None and len(commits) > WINDOW_COMMITS}
    return cache[key]


def commit_files(client, repo, sha, cache):
    if (repo, sha) not in cache:
        cache[(repo, sha)] = {f.get('filename') for f in client.get(f'/repos/{repo}/commits/{sha}').get('files') or []}
    return cache[(repo, sha)]


def butterfly(client, b, a, row, cache):
    """Candidate causes of one positive transition: base-window commits ranked by files shared with the PR."""
    repo = b['repo']
    start = b['merge_base'] if row['attribution'] == 'DELIVERED_BY_UPDATE' else b['base_sha']
    window = base_window(client, repo, start, a['base_sha'], cache)
    candidates = []
    if window['commits']:
        pr_files = {f.get('filename') for f in client.paginate(f'/repos/{repo}/pulls/{b["number"]}/files')}
        for c in window['commits']:
            title = ((c.get('commit') or {}).get('message') or '').splitlines()[0] if c.get('commit') else ''
            ref = PR_REF.search(title)
            shared = sorted(commit_files(client, repo, c['sha'], cache) & pr_files)
            candidates.append({'sha': c['sha'], 'title': title[:120], 'pr': int(ref.group(1)) if ref else None,
                               'shared_files': len(shared), 'files': shared[:10]})
        candidates.sort(key=lambda c: -c['shared_files'])  # stable: newest first within equal overlap
    return {'base_window': {k: window[k] for k in ('from', 'to', 'truncated')},
            'window_commits': None if window['commits'] is None else len(window['commits']),
            'candidates': candidates[:10], 'cross_repo': CONTROLS['cross_repo_attribution'],
            'proof': 'CANDIDATE_NOT_PROVEN'}


def census_delta(cb, ca):
    if cb.get('status') != 'OK' or ca.get('status') != 'OK':
        return {'status': 'UNKNOWN'}
    if cb['n'] == ca['n']:
        return {'status': 'SAME_PULSE', 'n': ca['n'], 'hint': 'run scale_dock_series.py pulse before after'}
    repos = sorted(set(cb['red_by_repo']) | set(ca['red_by_repo']))
    return {'status': 'OK', 'from_n': cb['n'], 'to_n': ca['n'],
            'red_delta': {r: ca['red_by_repo'].get(r, 0) - cb['red_by_repo'].get(r, 0) for r in repos}}


def evaluate(client, b, act_rec, after_rows, foreign=None):
    method = b['policy']['method']
    acts = {(r['repo'], r['number']): r for r in (act_rec or {}).get('results', [])}
    rows, positives, cache = [], [], {}
    rerun_level = b['policy'].get('intervention', 'UPDATE') != 'UPDATE'
    for br, ar in zip(b['prs'], after_rows):
        o = outcome(ar)
        act_row = acts.get((br['repo'], br['number']))
        parents = None
        if (ar and ar['head_sha'] != br['head_sha'] and act_row and act_row['result'] == 'ACCEPTED'
                and not act_row.get('new_head') and method == 'MERGE'):
            try:
                parents = [p.get('sha') for p in
                           client.get(f"/repos/{br['repo']}/commits/{ar['head_sha']}").get('parents') or []]
            except (OSError, ValueError):
                parents = None
        change = head_change(br, ar, act_row, method, parents)
        row = {'repo': br['repo'], 'number': br['number'], 'arm': br['arm'], 'skip': br['skip'],
               'act': act_row['result'] if act_row else None, 'before_ci': br['ci_state'], 'outcome': o,
               'success': success(o),
               'transition': transition(br['ci_state'], o), 'head_change': change,
               'gate_regressed': bool(ar) and br['gate_state'] == 'GREEN' and ar['gate_state'] == 'RED',
               'recovered_checks': sorted(set(br['ci_failing']) - set(ar['ci_failing'])) if ar else []}
        signals = []
        if row['transition'] in ('UNBLOCKED', 'SETTLED_GREEN') or (o == 'MERGED' and br['ci_state'] != 'GREEN'):
            signals.append('CI_GREENED' if o != 'MERGED' else 'MERGED')
        if ar and (br['mergeable'] == 'CONFLICTING' or br['merge_state'] == 'DIRTY') \
                and ar['mergeable'] == 'MERGEABLE' and ar['merge_state'] != 'DIRTY':
            signals.append('CONFLICT_CLEARED')
        rows.append(row)
        if signals:
            row['attribution'] = {'UPDATE_ONLY': 'DELIVERED_BY_UPDATE', 'HEAD_UNCHANGED': 'EXTERNAL',
                                  'AUTHOR_PUSH': 'AUTHOR_PUSH', 'UNVERIFIED_HEAD': 'UNVERIFIED'}[change]
            if change == 'HEAD_UNCHANGED' and rerun_level and act_row and act_row['result'] == 'ACCEPTED':
                # Same head, our rerun was the change we made, unless someone reran it again after us.
                row['attribution'] = ('UNVERIFIED' if (br['repo'], br['number']) in (foreign or set())
                                      else 'DELIVERED_BY_RERUN')
            positives.append({'repo': br['repo'], 'number': br['number'], 'arm': br['arm'], 'signals': signals,
                              'attribution': row['attribution'], 'recovered_checks': row['recovered_checks'],
                              **butterfly(client, br, ar, row, cache)})
    eligible = [r for r in rows if r['arm']]
    stats = {arm: arm_stats(eligible, arm) for arm in ARMS}
    t, h, min_arm = stats['TREATED'], stats['HOLDOUT'], b['policy']['min_arm']
    return {'design': 'intention_to_treat', 'arms': stats,
            'effect_green_or_merged': effect(t['success'], t['known'], h['success'], h['known'], min_arm),
            'effect_unblock_given_red': effect(t['unblocked'], t['red_before'], h['unblocked'], h['red_before'],
                                               min_arm),
            'positives': positives, 'rows': rows}


def after(client, records, experiment, now, census, min_hours):
    b, act_rec, _ = experiment_records(records, experiment)
    t0 = when((act_rec or b)['recorded_at'])
    hours = (now - t0).total_seconds() / 3600
    require(hours >= min_hours, f'only {hours:.2f} h since {(act_rec or b)["kind"]}; CI needs time (--min-hours)')
    cache, rows = {}, []
    for br in b['prs']:
        try:
            live = client.pr(br['repo'], br['number'])
            base = base_head(client, br['repo'], live['baseRefName'], cache)
            rows.append(pr_row(client, br['repo'], live, base, b['policy'], now))
        except (OSError, ValueError, KeyError):
            rows.append(None)  # UNREADABLE: an unknown outcome, never a failure or a success
    rr = reruns(client, b, act_rec)
    foreign = {(r['repo'], r['number']) for r in rr if r['ldab'] == 'DISPATCHED_ATTEMPT_UNIDENTIFIABLE'}
    return {'kind': 'after', 'experiment': experiment, 'recorded_at': stamp(now), 'hours_since': round(hours, 3),
            'acted': act_rec is not None and act_rec['applied'], 'prs': rows, 'census': census,
            'census_delta': census_delta(b['census'], census),
            'evaluation': evaluate(client, b, act_rec, rows, foreign), 'reruns': rr}


def ldab_observation(repo, head, run_id, job_id):
    """One LDAB debug_receipt observation, validated by the hub's own bd_ldab_consumer.

    Actions step debug logging is not a debugger session: real_probe_steps is 0 and the proof level stays
    REPORTED_UNVERIFIED, as the ABACUS BD-LDAB join contract requires.
    """
    o = {'repository': repo, 'source_sha': head, 'run_id': run_id, 'job_id': job_id,
         'evidence_url': f'https://github.com/{repo}/actions/runs/{run_id}', 'source': 'debug_receipt',
         'proof_level': 'REPORTED_UNVERIFIED', 'real_probe_steps': 0}
    ldab.check_observation(o, debug=True)
    return o


def reruns(client, b, act_rec):
    """For each accepted rerun: the run's attempt and conclusion now, and its LDAB observation if any."""
    if not act_rec or act_rec.get('intervention', 'UPDATE') == 'UPDATE':
        return []
    debug, out = act_rec['intervention'] == 'DEBUG_RERUN', []
    triaged = {(r['repo'], r['number']): r.get('triage') or {} for r in b['prs']}
    for a in act_rec['results']:
        if a['result'] != 'ACCEPTED':
            continue
        ours = a['run_attempt'] + 1  # the attempt our rerun dispatched; a later rerun by anyone is not ours
        row = {'repo': a['repo'], 'number': a['number'], 'run_id': a['run_id'], 'attempt_before': a['run_attempt'],
               'attempt_dispatched': ours, 'attempt_after': None, 'status': None, 'conclusion': None, 'ldab': None}
        try:
            run = client.get(f"/repos/{a['repo']}/actions/runs/{a['run_id']}")
            row['attempt_after'] = run.get('run_attempt')
        except (OSError, ValueError):
            row['ldab'] = 'RUN_UNREADABLE'
            run = {}
        if row['attempt_after'] == ours:
            row.update(status=run.get('status'), conclusion=run.get('conclusion'))
        elif row['ldab'] is None and isinstance(row['attempt_after'], int) and row['attempt_after'] > ours:
            # Someone reran it again: the run's current conclusion and jobs belong to their attempt, not ours.
            row['ldab'] = 'DISPATCHED_ATTEMPT_UNIDENTIFIABLE'
        if row['ldab'] is None:
            if not debug:
                row['ldab'] = 'NOT_A_DEBUG_RERUN'
            elif a['repo'] not in LDAB_REPOS:
                row['ldab'] = 'NOT_IN_LDAB_SCOPE'
            elif row['attempt_after'] != ours:
                row['ldab'] = 'NO_NEW_ATTEMPT'
            else:
                name = triaged[(a['repo'], a['number'])].get('job_name')
                try:  # the dispatched attempt's own jobs, never the run's latest attempt
                    jobs = client.paginate(f"/repos/{a['repo']}/actions/runs/{a['run_id']}/attempts/{ours}/jobs",
                                           key='jobs')
                except (OSError, ValueError):
                    jobs = []
                job = next((j for j in jobs if j.get('name') == name), jobs[0] if jobs else None)
                row['ldab'] = (ldab_observation(a['repo'], a['head_sha'], a['run_id'], job['id'])
                               if job and type(job.get('id')) is int else 'NO_JOB')
        out.append(row)
    return out


# ---------------------------------------------------------------- ledger

def verify(lines):
    """Canonical lines, ordinals 0..k, sha256 chain, time order, and before -> act (once) -> after per experiment."""
    records, prev, last, seen = [], None, None, {}
    for i, text in enumerate(lines):
        try:
            rec = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError('PRX_HOLD:ledger line not JSON') from exc
        require(isinstance(rec, dict) and text == sds.line(rec), 'ledger line not canonical')
        require(rec.get('schema') == SCHEMA and rec.get('n') == i and rec.get('kind') in KINDS, 'ledger ordinal or kind')
        require(rec.get('prev_sha256') == prev, 'ledger chain broken')
        at = when(rec.get('recorded_at'))
        require(last is None or at >= last, 'ledger time not monotone')
        kinds = seen.setdefault(rec.get('experiment'), [])
        if rec['kind'] == 'before':
            require(not kinds, 'experiment id reused')
        else:
            require(bool(kinds), rec['kind'] + ' without before')
        if rec['kind'] == 'act':
            require('act' not in kinds and 'after' not in kinds, 'act comes once, before any after')
        kinds.append(rec['kind'])
        prev, last = sds.sha256(text), at
        records.append(rec)
    return records


def read_ledger(path):
    if not path.exists():
        return [], []
    raw = path.read_text(encoding='ascii')
    require(raw == '' or raw.endswith('\n'), 'ledger truncated')
    lines = raw.splitlines()
    return verify(lines), lines


def append(path, record):
    records, lines = read_ledger(path)
    record = {**record, 'schema': SCHEMA, 'n': len(records), 'prev_sha256': sds.sha256(lines[-1]) if lines else None}
    verify([*lines, sds.line(record)])
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='ascii', newline='\n') as fh:  # append only
        fh.write(sds.line(record) + '\n')
    return record


def experiment_records(records, experiment):
    mine = [r for r in records if r['experiment'] == experiment]
    require(bool(mine) and mine[0]['kind'] == 'before', 'unknown experiment ' + repr(experiment))
    return mine[0], next((r for r in mine if r['kind'] == 'act'), None), [r for r in mine if r['kind'] == 'after']


# ---------------------------------------------------------------- report

def _pct(v):
    return '-' if v is None else f'{100 * v:.0f}%'


def _effect(e):
    if e['status'] != 'OK':
        return f"UNKNOWN (an arm has fewer than {e['min_arm']} known outcomes)"
    lo, hi = e['ci95']
    return f"{100 * e['diff']:+.0f} points (95% CI {100 * lo:+.0f} to {100 * hi:+.0f})"


def report(records, experiment):
    b, act_rec, afters = experiment_records(records, experiment)
    out = [f'# PR intervention {experiment}', '',
           f"Before: {b['recorded_at']}, {b['counts']['open']} open PRs, {b['counts']['eligible']} eligible "
           f"({b['counts']['TREATED']} treated, {b['counts']['HOLDOUT']} holdout). "
           f"Intervention: {b['policy'].get('intervention', 'UPDATE')}"
           + (f" ({b['policy']['method']})." if b['policy'].get('intervention', 'UPDATE') == 'UPDATE' else '.')]
    for repo, p in b['pulse'].items():
        if p.get('triage_counts'):
            out.append(f"rerun_triage on {repo}: " + ', '.join(
                f'{k} {v}' for k, v in sorted(p['triage_counts'].items()) if v) + '.')
    if act_rec:
        c = act_rec['counts']
        out.append(f"Act: {act_rec['recorded_at']}, applied={act_rec['applied']}: {c['ACCEPTED']} accepted, "
                   f"{c['FAILED']} failed, {c['SKIPPED']} skipped, {c['PLANNED']} planned, "
                   f"{c.get('ERROR', 0)} errors, {c.get('UNKNOWN', 0)} unknown. "
                   f"FPC receipts to rewrite: {act_rec['fpc_receipts_invalidated']}.")
    skips = {}
    for r in b['prs']:
        for s in r['skip']:
            skips[s] = skips.get(s, 0) + 1
    out.append('Not eligible: ' + (', '.join(f'{k} {v}' for k, v in sorted(skips.items())) or 'none') + '.')
    if not afters:
        out += ['', 'No `after` record yet.']
        return '\n'.join(out) + '\n'
    a = afters[-1]
    ev, cd = a['evaluation'], a['census_delta']
    out += ['', f"## After ({a['recorded_at']}, {a['hours_since']} h later)", '',
            'Census (scale-dock pulses): ' + (
                f"pulse {cd['from_n']} to {cd['to_n']}, RED jobs delta {cd['red_delta']}" if cd['status'] == 'OK'
                else cd['status']) + '.', '',
            '| Arm | Assigned | Known | Green or merged | Rate (95% CI) | Unblocked of red | Regressed of green '
            '| Closed unmerged | Author pushes | Gate turned red |',
            '|---|---|---|---|---|---|---|---|---|---|']
    for arm in ARMS:
        s = ev['arms'][arm]
        ci = f" ({_pct(s['ci95'][0])} to {_pct(s['ci95'][1])})" if s['ci95'] else ''
        out.append(f"| {arm} | {s['assigned']} | {s['known']} | {s['success']} | {_pct(s['rate'])}{ci} | "
                   f"{s['unblocked']} of {s['red_before']} | {s['regressed']} of {s['green_before']} | "
                   f"{s['closed_unmerged']} | {s['author_push']} | {s['gate_regressed']} |")
    out += ['', f"Effect, green or merged (treated minus holdout): {_effect(ev['effect_green_or_merged'])}.",
            f"Effect, unblocked given red before: {_effect(ev['effect_unblock_given_red'])}.", '',
            '## Positive transitions (candidate causes, not proven)', '']
    if not ev['positives']:
        out.append('None.')
    else:
        out += ['| PR | Arm | Signals | Attribution | Top candidate commits |', '|---|---|---|---|---|']
        for p in ev['positives']:
            top = '; '.join(f"{c['sha'][:8]}{' #' + str(c['pr']) if c['pr'] else ''} ({c['shared_files']} shared)"
                            for c in p['candidates'][:3]) or ('window unreadable' if p['window_commits'] is None else 'no base commits')
            out.append(f"| {p['repo']}#{p['number']} | {p['arm'] or 'not eligible'} | {', '.join(p['signals'])} | "
                       f"{p['attribution']} | {top} |")
    if a.get('reruns'):
        out += ['', '## Reruns', '', '| PR | Run | Attempt before / now | Conclusion now | LDAB |', '|---|---|---|---|---|']
        for r in a['reruns']:
            obs = r['ldab'] if isinstance(r['ldab'], str) else f"debug_receipt {r['ldab']['proof_level']}"
            out.append(f"| {r['repo']}#{r['number']} | {r['run_id']} | {r['attempt_before']} / {r['attempt_after']} | "
                       f"{r['conclusion']} | {obs} |")
    out += ['', 'Actions minutes and cross-repository attribution: UNKNOWN.']
    return '\n'.join(out) + '\n'


# ---------------------------------------------------------------- CLI

def policy_of(args):
    p = {**POLICY, 'min_age_days': args.min_age_days, 'min_behind': args.min_behind, 'holdout': args.holdout,
         'quiet_hours': args.quiet_hours, 'method': args.method.upper(), 'min_arm': args.min_arm,
         'intervention': args.intervention.upper().replace('-', '_'),
         'gate_checks': sorted(set(args.gate_check)) if args.gate_check else list(POLICY['gate_checks'])}
    require(p['min_age_days'] >= 0 and p['quiet_hours'] >= 0 and p['min_behind'] >= 1, 'policy bounds')
    require(0 < p['holdout'] < 1, 'holdout must be strictly between 0 and 1')
    require(p['method'] in METHODS and p['min_arm'] >= 1, 'policy method or min_arm')
    require(p['intervention'] in INTERVENTIONS and all(isinstance(g, str) and g.strip() for g in p['gate_checks']),
            'policy intervention or gate checks')
    return p


def main(argv=None, client=None, writer=None, now=None, sleep=time.sleep):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name in ('before', 'act', 'after', 'report'):
        s = sub.add_parser(name)
        s.add_argument('--ledger', type=Path, default=LEDGER)
        if name != 'before':
            s.add_argument('--experiment', required=True)
        if name in ('before', 'after'):
            s.add_argument('--census-ledger', type=Path, default=sds.LEDGER)
    s = sub.choices['before']
    s.add_argument('--repo', action='append', help='GBOGEB/<name>; repeat for several (default: the hub)')
    s.add_argument('--experiment')
    s.add_argument('--min-age-days', type=float, default=POLICY['min_age_days'])
    s.add_argument('--min-behind', type=int, default=POLICY['min_behind'])
    s.add_argument('--holdout', type=float, default=POLICY['holdout'])
    s.add_argument('--quiet-hours', type=float, default=POLICY['quiet_hours'])
    s.add_argument('--method', choices=['merge', 'rebase'], default='merge')
    s.add_argument('--min-arm', type=int, default=POLICY['min_arm'])
    s.add_argument('--intervention', choices=['update', 'rerun', 'debug-rerun'], default='update')
    s.add_argument('--gate-check', action='append',
                   help='check name judged as a gate, not CI; repeat (default: first-pass-closure)')
    sub.choices['act'].add_argument('--apply', action='store_true', help='write to GitHub (default: dry run)')
    sub.choices['after'].add_argument('--min-hours', type=float, default=2.0)
    sub.choices['report'].add_argument('--out', type=Path)
    args = ap.parse_args(argv)
    now = now or datetime.now(timezone.utc)
    records, _ = read_ledger(args.ledger)
    if args.cmd == 'report':
        text = report(records, args.experiment)
        if args.out:
            args.out.write_text(text, encoding='utf-8', newline='\n')
        print(text, end='')
        return 0
    client = client or Client()
    if args.cmd == 'before':
        experiment = args.experiment or 'PRX-' + now.strftime('%Y%m%dT%H%M%SZ')
        rec = append(args.ledger, before(client, args.repo or ['GBOGEB/pipeline-automation-hub'], policy_of(args),
                                         experiment, now, census_ref(args.census_ledger)))
        print(json.dumps({'experiment': experiment, 'n': rec['n'], **rec['counts']}, sort_keys=True))
    elif args.cmd == 'act':
        b, act_rec, afters = experiment_records(records, args.experiment)
        require(act_rec is None and not afters, 'experiment already acted on or measured')
        rec = act(client, writer or Writer(), b, args.apply, now, sleep=sleep)
        if args.apply:
            rec = append(args.ledger, rec)
        else:
            print('DRY RUN: nothing written to GitHub or the ledger. Re-run with --apply to write.')
        print(json.dumps({'experiment': args.experiment, 'applied': args.apply, **rec['counts'],
                          'results': [f"{r['repo']}#{r['number']} {r['result']}" for r in rec['results']]},
                         sort_keys=True))
    else:
        rec = append(args.ledger, after(client, records, args.experiment, now,
                                        census_ref(args.census_ledger), args.min_hours))
        ev = rec['evaluation']
        print(json.dumps({'experiment': args.experiment, 'n': rec['n'], 'census': rec['census_delta']['status'],
                          'effect': ev['effect_green_or_merged'], 'positives': len(ev['positives'])}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
