"""PR intervention ledger: eligibility, deterministic arms, guarded writes, effect estimate, butterflies, chain."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import tempfile
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

# No PyYAML stub here: nothing this module imports needs it, and a stub without __spec__ planted
# before test_scale_dock_series makes its own find_spec('yaml') raise (gogreen CI, 2026-11-11).

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('pr_intervention', HERE.parent / 'pr_intervention.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

REPO = 'GBOGEB/pipeline-automation-hub'
T0 = datetime(2026, 11, 11, 8, 0, 0, tzinfo=timezone.utc)


def sha(name):
    return hashlib.sha1(name.encode('ascii')).hexdigest()


BASE0, BASE1, MB = sha('base0'), sha('base1'), sha('merge-base')
FIX_OTHER, FIX_SHARED = sha('fix-other'), sha('fix-shared')


def check(name, conclusion, started='2026-11-10T00:00:00Z', workflow='CI', status='COMPLETED'):
    return {'__typename': 'CheckRun', 'workflowName': workflow, 'name': name, 'status': status,
            'conclusion': conclusion, 'startedAt': started}


def pr(n, head, *, created='2026-10-01T00:00:00Z', base='master', draft=False, fork=False, labels=(),
       merge='BLOCKED', mergeable='MERGEABLE', ci='SUCCESS', state='OPEN', gate='SUCCESS'):
    return {'number': n, 'state': state, 'headRefOid': head, 'headRefName': f'b{n}', 'baseRefName': base,
            'isDraft': draft, 'isCrossRepository': fork, 'createdAt': created, 'mergeStateStatus': merge,
            'mergeable': mergeable, 'labels': [{'name': x} for x in labels], 'mergedAt': None,
            'statusCheckRollup': [check('unit', ci), check('first-pass-closure', gate, workflow='First-Pass Closure Gate')]}


def cmp(head, behind=3, ahead=2, committed='2026-10-20T00:00:00Z', merge_base=MB):
    return {'behind_by': behind, 'ahead_by': ahead, 'merge_base_commit': {'sha': merge_base},
            'commits': [{'sha': head, 'commit': {'committer': {'date': committed}, 'message': 'work'}}]}


class FakeClient:
    """Answers the reads pr_intervention makes; records every call."""

    def __init__(self, prs, heads=None, compares=None):
        self.open = {REPO: prs}
        self.views = {(REPO, p['number']): p for p in prs}
        self.heads = heads or {'master': BASE0}
        self.compares = compares or {}
        self.windows = {}
        self.commit_files = {}
        self.parents = {}
        self.pr_files = {}
        self.runs = {}       # head SHA -> workflow runs on that head
        self.jobs = {}       # run id -> latest-attempt jobs
        self.run_state = {}  # run id -> /actions/runs/{id}
        self.calls = []

    def get(self, route):
        self.calls.append(('get', route))
        if route == f'/repos/{REPO}':
            return {'default_branch': 'master'}
        if '/actions/runs/' in route:
            return copy.deepcopy(self.run_state[int(route.rsplit('/', 1)[1])])
        prefix = f'/repos/{REPO}/commits/'
        if route.startswith(prefix):
            ref = route[len(prefix):]
            if ref in self.heads:
                return {'sha': self.heads[ref]}
            return {'sha': ref, 'files': [{'filename': f} for f in self.commit_files.get(ref, [])],
                    'parents': [{'sha': p} for p in self.parents.get(ref, [])]}
        raise AssertionError('unexpected route ' + route)

    def paginate(self, route, key=None):
        self.calls.append(('paginate', route))
        if '/actions/runs?head_sha=' in route:
            return copy.deepcopy(self.runs.get(route.split('head_sha=')[1], []))
        if route.endswith('/jobs'):
            return copy.deepcopy(self.jobs.get(int(route.split('/actions/runs/')[1].split('/')[0]), []))
        n = int(route.split('/pulls/')[1].split('/')[0])
        return [{'filename': f} for f in self.pr_files.get(n, [])]

    def prs(self, repo):
        self.calls.append(('prs', repo))
        return [{k: p[k] for k in mod.LIST_FIELDS.split(',')} for p in self.open[repo]]

    def pr(self, repo, number):
        self.calls.append(('pr', number))
        return copy.deepcopy(self.views[(repo, number)])

    def compare(self, repo, base, head):
        self.calls.append(('compare', base, head))
        if (base, head) in self.windows:
            return self.windows[(base, head)]
        if (base, head) in self.compares:
            return self.compares[(base, head)]
        return cmp(head)


class FakeWriter:
    """With a client, behaves like GitHub's merge update: a new head whose first parent is the old head."""

    def __init__(self, client=None, answer=('ACCEPTED', None)):
        self.client, self.calls, self.answer = client, [], answer

    def update_branch(self, repo, number, expected_head, method):
        self.calls.append((repo, number, expected_head, method))
        if self.client is not None and self.answer[0] == 'ACCEPTED':
            new = sha(f'u{number}')
            self.client.views[(repo, number)]['headRefOid'] = new
            self.client.parents[new] = [expected_head, self.client.heads['master']]
        return self.answer

    def rerun_failed(self, repo, run_id, debug):
        self.calls.append((repo, run_id, debug))
        if self.client is not None and self.answer[0] == 'ACCEPTED':
            state = self.client.run_state[run_id]
            state.update(run_attempt=state['run_attempt'] + 1, status='queued', conclusion=None)
        return self.answer


def no_sleep(seconds):
    pass


def failed_run(fc, n, kind):
    """Give PR n's head one completed run whose failed job matches a classifier case."""
    head, rid = sha(f'h{n}'), 1000 + n
    steps = {'runner_lost': [], 'thin_logs': [{'name': 'Run tests', 'conclusion': 'success'}],
             'failed_step': [{'name': 'Run tests', 'conclusion': 'failure'}],
             'green': [{'name': 'Run tests', 'conclusion': 'success'}]}[kind]
    conclusion = 'success' if kind == 'green' else 'failure'
    run = {'id': rid, 'head_sha': head, 'status': 'completed', 'conclusion': conclusion, 'run_attempt': 1,
           'name': 'CI', 'updated_at': '2026-11-10T00:00:00Z'}
    fc.runs[head] = [run]
    fc.jobs[rid] = [{'id': 5000 + n, 'name': 'unit', 'conclusion': conclusion, 'steps': steps}]
    fc.run_state[rid] = dict(run)
    fc.compares[(BASE0, head)] = cmp(head, behind=0)


def policy(**kw):
    return {**mod.POLICY, **kw}


class Snapshot(unittest.TestCase):
    def test_checks_latest_per_identity_and_gate_apart(self):
        rollup = [check('unit', 'FAILURE', '2026-11-01T00:00:00Z'), check('unit', 'SUCCESS', '2026-11-02T00:00:00Z'),
                  check('lint', 'CANCELLED'), check('first-pass-closure', 'FAILURE', workflow='FPC'),
                  {'__typename': 'StatusContext', 'context': 'ext', 'state': 'PENDING'}]
        lanes = mod.checks(rollup, {'first-pass-closure'})
        self.assertEqual(lanes['ci'], {'fail': [], 'pending': ['CI :: lint', 'status :: ext'], 'pass': 1})
        self.assertEqual(mod.state_of(lanes['ci']), 'PENDING')
        self.assertEqual(mod.state_of(lanes['gate']), 'RED')  # a red gate never makes CI red
        self.assertEqual(mod.state_of({'fail': [], 'pending': [], 'pass': 0}), 'NO_CHECKS')
        # The gate's commit status ('<workflow> / <job>') is a gate too, not a CI failure (seen live 2026-11-11).
        status = {'__typename': 'StatusContext', 'context': 'First-Pass Closure Gate / first-pass-closure',
                  'state': 'FAILURE'}
        lanes = mod.checks([check('unit', 'SUCCESS'), status], {'first-pass-closure'})
        self.assertEqual((mod.state_of(lanes['ci']), lanes['gate']['fail']),
                         ('GREEN', ['status :: First-Pass Closure Gate / first-pass-closure']))

    def test_latest_cancelled_check_is_never_green(self):
        lanes = mod.checks([check('unit', 'SUCCESS'), check('lint', 'CANCELLED')], set())
        self.assertEqual(mod.state_of(lanes['ci']), 'PENDING')
        later = [check('lint', 'CANCELLED', '2026-11-01T00:00:00Z'), check('lint', 'SUCCESS', '2026-11-02T00:00:00Z')]
        self.assertEqual(mod.state_of(mod.checks(later, set())['ci']), 'GREEN')  # superseded by a later run

    def test_reasons_cover_every_guard(self):
        row = mod.pr_row(FakeClient([]), REPO, pr(1, sha('h1')), BASE0, policy(), T0)
        self.assertEqual(mod.reasons(row, 'master', policy(), T0), [])
        cases = {'DRAFT': {'draft': True}, 'FORK': {'cross_repo': True}, 'STACKED': {'base_ref': 'feat'},
                 'YOUNG': {'age_days': 1.0}, 'CURRENT': {'behind_by': 0}, 'BEHIND_UNKNOWN': {'behind_by': None},
                 'CONFLICT': {'mergeable': 'CONFLICTING'}, 'RECENT_PUSH': {'head_committed_at': '2026-11-11T07:00:00Z'},
                 'PUSH_TIME_UNKNOWN': {'head_committed_at': None}, 'OPT_OUT_LABEL': {'labels': ['do-not-rebase']}}
        for reason, change in cases.items():
            with self.subTest(reason=reason):
                self.assertEqual(mod.reasons({**row, **change}, 'master', policy(), T0), [reason])

    def test_unreadable_compare_is_unknown_not_zero(self):
        class Broken(FakeClient):
            def compare(self, repo, base, head):
                raise OSError('gh api exit 1')
        row = mod.pr_row(Broken([]), REPO, pr(1, sha('h1')), BASE0, policy(), T0)
        self.assertIsNone(row['behind_by'])
        self.assertIn('BEHIND_UNKNOWN', mod.reasons(row, 'master', policy(), T0))

    def test_arms_are_deterministic_and_near_the_holdout_fraction(self):
        arms = [mod.arm_of('PRX-T', REPO, n, sha(str(n)), 0.2) for n in range(2000)]
        self.assertEqual(arms, [mod.arm_of('PRX-T', REPO, n, sha(str(n)), 0.2) for n in range(2000)])
        self.assertTrue(0.17 < arms.count('HOLDOUT') / 2000 < 0.23)

    def test_before_reads_each_base_head_once(self):
        prs = [pr(1, sha('h1')), pr(2, sha('h2'), draft=True), pr(3, sha('h3'), base='feat'), pr(4, sha('h4'))]
        fc = FakeClient(prs, heads={'master': BASE0, 'feat': sha('feat')})
        rec = mod.before(fc, [REPO], policy(holdout=0.5), 'PRX-T', T0, {'status': 'UNKNOWN_EMPTY'})
        base_reads = [c for c in fc.calls if c[0] == 'get' and '/commits/' in c[1]]
        self.assertEqual(sorted(c[1] for c in base_reads), [f'/repos/{REPO}/commits/feat', f'/repos/{REPO}/commits/master'])
        self.assertEqual(rec['counts']['open'], 4)
        self.assertEqual(rec['counts']['eligible'], 2)
        self.assertEqual({r['number']: r['skip'] for r in rec['prs']}, {1: [], 2: ['DRAFT'], 3: ['STACKED'], 4: []})
        self.assertEqual(rec['pulse'][REPO]['base_heads'], {'feat': sha('feat'), 'master': BASE0})

    def test_repo_and_experiment_ids_are_validated(self):
        with self.assertRaises(ValueError):
            mod.before(FakeClient([]), ['someone/else'], policy(), 'PRX-T', T0, {})
        with self.assertRaises(ValueError):
            mod.before(FakeClient([]), [REPO], policy(), 'bad id', T0, {})


class Act(unittest.TestCase):
    def setUp(self):
        self.prs = [pr(n, sha(f'h{n}')) for n in range(1, 9)]
        self.fc = FakeClient(self.prs)
        self.b = mod.before(self.fc, [REPO], policy(holdout=0.3), 'PRX-T', T0, {})
        self.treated = [r['number'] for r in self.b['prs'] if r['arm'] == 'TREATED']
        self.assertGreaterEqual(len(self.treated), 2)

    def test_dry_run_writes_nothing(self):
        w = FakeWriter()
        rec = mod.act(self.fc, w, self.b, False, T0, sleep=no_sleep)
        self.assertEqual(w.calls, [])
        self.assertEqual(rec['counts']['PLANNED'], len(self.treated))
        self.assertEqual(rec['fpc_receipts_invalidated'], 0)

    def test_apply_is_guarded_by_the_recorded_head(self):
        moved = self.treated[0]
        self.fc.views[(REPO, moved)]['headRefOid'] = sha('moved')
        w = FakeWriter(self.fc)
        rec = mod.act(self.fc, w, self.b, True, T0, sleep=no_sleep)
        self.assertEqual([c[1] for c in w.calls], self.treated[1:])
        self.assertTrue(all(c[2] == sha(f'h{c[1]}') and c[3] == 'MERGE' for c in w.calls))
        by = {r['number']: r for r in rec['results']}
        self.assertEqual((by[moved]['result'], by[moved]['detail']), ('SKIPPED', 'HEAD_MOVED'))
        self.assertEqual(rec['fpc_receipts_invalidated'], len(self.treated) - 1)
        # The exact head the update produced is read back (first parent = recorded head).
        self.assertTrue(all(by[n]['new_head'] == sha(f'u{n}') for n in self.treated[1:]))

    def test_guards_are_reread_before_each_write(self):
        """Labels, draft, base and conflicts can change after `before` without moving the head."""
        changes = {'OPT_OUT_LABEL': {'labels': [{'name': 'no-auto-update'}]}, 'DRAFT': {'isDraft': True},
                   'BASE_CHANGED': {'baseRefName': 'release'}, 'CONFLICT': {'mergeable': 'CONFLICTING'},
                   'NOT_OPEN': {'state': 'CLOSED'}}
        for reason, change in changes.items():
            with self.subTest(reason=reason):
                fc = FakeClient(copy.deepcopy(self.prs))
                fc.views[(REPO, self.treated[0])].update(change)
                w = FakeWriter(fc)
                rec = mod.act(fc, w, self.b, True, T0, sleep=no_sleep)
                self.assertNotIn(self.treated[0], [c[1] for c in w.calls])
                first = next(r for r in rec['results'] if r['number'] == self.treated[0])
                self.assertEqual((first['result'], first['detail']), ('SKIPPED', reason))

    def test_unconfirmed_update_head_is_not_recorded(self):
        sleeps = []
        rec = mod.act(self.fc, FakeWriter(), self.b, True, T0, sleep=sleeps.append)  # GitHub never moved the head
        self.assertTrue(all(r['new_head'] is None for r in rec['results']))
        self.assertEqual(len(sleeps), 5 * len(self.treated))  # bounded: six reads, five waits per PR
        fc = FakeClient(copy.deepcopy(self.prs))
        n = self.treated[0]
        fc.views[(REPO, n)]['headRefOid'] = sha('stranger')
        fc.parents[sha('stranger')] = [sha('other'), BASE0]  # a head that is not our merge commit
        self.assertIsNone(mod.updated_head(fc, {'repo': REPO, 'number': n, 'head_sha': sha(f'h{n}')}, 'MERGE', no_sleep))


class Evaluate(unittest.TestCase):
    """Treated PRs turn green after a merge update; holdout PRs stay red, except one external recovery."""

    def build(self, min_arm=2):
        prs = [pr(n, sha(f'h{n}'), ci='FAILURE') for n in range(1, 13)]
        prs.append(pr(20, sha('h20'), mergeable='CONFLICTING', merge='DIRTY'))  # ineligible: conflict
        fc = FakeClient(prs)
        b = mod.before(fc, [REPO], policy(holdout=0.5, min_arm=min_arm), 'PRX-E', T0, {'status': 'UNKNOWN_EMPTY'})
        treated = [r['number'] for r in b['prs'] if r['arm'] == 'TREATED']
        holdout = [r['number'] for r in b['prs'] if r['arm'] == 'HOLDOUT']
        self.assertGreaterEqual(min(len(treated), len(holdout)), 3)
        a = mod.act(fc, FakeWriter(fc), b, True, T0, sleep=no_sleep)
        # After: base moved; treated heads are the update's merge commits and green.
        fc.heads['master'] = BASE1
        for n in treated:
            new = sha(f'u{n}')
            fc.views[(REPO, n)] = pr(n, new, ci='SUCCESS')
            fc.compares[(BASE1, new)] = cmp(new, behind=0, ahead=3)
        lucky = holdout[0]
        fc.views[(REPO, lucky)] = pr(lucky, sha(f'h{lucky}'), ci='SUCCESS')  # head unchanged, green: external
        fc.views[(REPO, 20)] = pr(20, sha('h20'))  # conflict cleared without a push
        fc.windows[(MB, BASE1)] = {'commits': [
            {'sha': FIX_SHARED, 'commit': {'message': 'fix(ci): pin runner (#42)\n\nbody'}},
            {'sha': FIX_OTHER, 'commit': {'message': 'docs: tidy'}}]}
        fc.windows[(BASE0, BASE1)] = {'commits': [{'sha': FIX_OTHER, 'commit': {'message': 'docs: tidy'}}]}
        fc.commit_files = {FIX_SHARED: ['ci/runner.yml'], FIX_OTHER: ['README.md']}
        fc.pr_files = {n: ['ci/runner.yml'] for n in range(1, 21)}
        rows = [fc.pr(REPO, r['number']) for r in b['prs']]
        after_rows = [mod.pr_row(fc, REPO, live, BASE1, b['policy'], T0 + timedelta(hours=6)) for live in rows]
        return b, a, mod.evaluate(fc, b, a, after_rows), treated, holdout, lucky

    def test_effect_and_transitions(self):
        b, a, ev, treated, holdout, lucky = self.build()
        t, h = ev['arms']['TREATED'], ev['arms']['HOLDOUT']
        self.assertEqual((t['success'], t['known'], t['unblocked'], t['red_before']), (len(treated),) * 2 + (len(treated),) * 2)
        self.assertEqual((h['success'], h['known']), (1, len(holdout)))
        e = ev['effect_green_or_merged']
        self.assertEqual(e['status'], 'OK')
        self.assertAlmostEqual(e['diff'], round(1 - 1 / len(holdout), 4))
        self.assertLess(e['ci95'][0], e['diff'])
        self.assertLessEqual(e['ci95'][1], 1.0)
        by = {r['number']: r for r in ev['rows']}
        self.assertTrue(all(by[n]['head_change'] == 'UPDATE_ONLY' for n in treated))
        self.assertEqual(by[lucky]['head_change'], 'HEAD_UNCHANGED')
        self.assertEqual(by[treated[0]]['recovered_checks'], ['CI :: unit'])

    def test_butterflies_are_attributed_and_ranked(self):
        b, a, ev, treated, holdout, lucky = self.build()
        pos = {p['number']: p for p in ev['positives']}
        self.assertEqual(set(pos), set(treated) | {lucky, 20})
        delivered = pos[treated[0]]
        self.assertEqual(delivered['attribution'], 'DELIVERED_BY_UPDATE')
        self.assertEqual(delivered['base_window']['from'], MB)  # an update delivers everything since the merge base
        self.assertEqual([c['sha'] for c in delivered['candidates']], [FIX_SHARED, FIX_OTHER])
        self.assertEqual((delivered['candidates'][0]['pr'], delivered['candidates'][0]['shared_files']), (42, 1))
        self.assertEqual(delivered['proof'], 'CANDIDATE_NOT_PROVEN')
        self.assertEqual(pos[lucky]['attribution'], 'EXTERNAL')
        self.assertEqual(pos[lucky]['base_window']['from'], BASE0)
        self.assertEqual((pos[20]['arm'], pos[20]['signals'], pos[20]['attribution']), (None, ['CONFLICT_CLEARED'], 'EXTERNAL'))

    def test_small_arm_is_unknown(self):
        ev = self.build(min_arm=50)[2]
        self.assertEqual(ev['effect_green_or_merged']['status'], 'UNKNOWN_SMALL_ARM')
        self.assertIsNone(ev['effect_green_or_merged']['diff'])

    def test_regression_and_author_push(self):
        b = {'merge_base': MB, 'base_sha': BASE0, 'head_sha': sha('x'), 'ahead_by': 2}
        self.assertEqual(mod.transition('GREEN', 'RED'), 'REGRESSED')
        self.assertEqual(mod.transition('RED', 'PENDING'), 'UNKNOWN')
        self.assertEqual(mod.transition('RED', 'MERGED'), 'UNBLOCKED')
        ours = {'result': 'ACCEPTED', 'new_head': sha('ours')}
        self.assertEqual(mod.head_change(b, {'head_sha': sha('ours')}, ours, 'MERGE'), 'UPDATE_ONLY')
        # A force-push after the update keeps the ahead count but not the SHA: it is the author's head.
        self.assertEqual(mod.head_change(b, {'head_sha': sha('forced'), 'ahead_by': 3}, ours, 'MERGE'), 'AUTHOR_PUSH')
        self.assertEqual(mod.head_change(b, {'head_sha': sha('y')}, None, 'MERGE'), 'AUTHOR_PUSH')
        self.assertEqual(mod.head_change(b, None, ours, 'MERGE'), 'HEAD_UNCHANGED')
        unread = {'result': 'ACCEPTED', 'new_head': None}
        self.assertEqual(mod.head_change(b, {'head_sha': sha('y')}, unread, 'MERGE', [sha('x'), BASE1]), 'UPDATE_ONLY')
        self.assertEqual(mod.head_change(b, {'head_sha': sha('y')}, unread, 'MERGE', [sha('z')]), 'UNVERIFIED_HEAD')
        self.assertEqual(mod.head_change(b, {'head_sha': sha('y')}, unread, 'REBASE'), 'UNVERIFIED_HEAD')

    def test_closed_unmerged_is_a_known_non_success(self):
        self.assertIs(mod.success('CLOSED'), False)
        self.assertEqual(mod.transition('GREEN', 'CLOSED'), 'CLOSED_UNMERGED')
        rows = [{'arm': 'TREATED', 'success': False, 'before_ci': 'GREEN', 'transition': 'CLOSED_UNMERGED',
                 'head_change': 'HEAD_UNCHANGED', 'gate_regressed': False},
                {'arm': 'TREATED', 'success': True, 'before_ci': 'RED', 'transition': 'UNBLOCKED',
                 'head_change': 'UPDATE_ONLY', 'gate_regressed': False}]
        s = mod.arm_stats(rows, 'TREATED')
        self.assertEqual((s['known'], s['success'], s['closed_unmerged'], s['regressed']), (2, 1, 1, 0))


class Statistics(unittest.TestCase):
    def test_wilson_and_newcombe_reference_values(self):
        lo, hi = mod.wilson(5, 10)
        self.assertAlmostEqual(lo, 0.2366, places=4)
        self.assertAlmostEqual(hi, 0.7634, places=4)
        # Newcombe (1998), Stat Med 17:873, Table II, method 10: (a) 56/70 vs 48/80, (e) 9/10 vs 3/10
        for (x1, n1, x2, n2), (diff, lo_ref, hi_ref) in {(56, 70, 48, 80): (0.2, 0.0524, 0.3339),
                                                          (9, 10, 3, 10): (0.6, 0.1705, 0.8090)}.items():
            d, (lo, hi) = mod.newcombe(x1, n1, x2, n2)
            self.assertAlmostEqual(d, diff, places=4)
            self.assertAlmostEqual(lo, lo_ref, places=4)
            self.assertAlmostEqual(hi, hi_ref, places=4)
        self.assertIsNone(mod.wilson(0, 0))

    def test_census_delta(self):
        ok = {'status': 'OK', 'n': 3, 'red_by_repo': {'A': 2, 'B': 1}}
        self.assertEqual(mod.census_delta(ok, ok)['status'], 'SAME_PULSE')
        self.assertEqual(mod.census_delta(ok, {'status': 'UNKNOWN_EMPTY'})['status'], 'UNKNOWN')
        later = {'status': 'OK', 'n': 4, 'red_by_repo': {'A': 1, 'C': 1}}
        self.assertEqual(mod.census_delta(ok, later)['red_delta'], {'A': -1, 'B': -1, 'C': 1})

    def test_census_ref_reads_the_committed_scale_dock_ledger(self):
        ref = mod.census_ref(mod.sds.LEDGER)
        self.assertEqual(ref['status'], 'OK')
        self.assertEqual(ref['ledger_schema'], mod.sds.LEDGER_SCHEMA)
        self.assertEqual(mod.census_ref(Path(tempfile.gettempdir()) / 'no-such-ledger.jsonl')['status'], 'UNKNOWN_EMPTY')


class Ledger(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / 'l.jsonl'

    def tearDown(self):
        self.dir.cleanup()

    def rec(self, kind, exp='PRX-A', at=T0):
        return {'kind': kind, 'experiment': exp, 'recorded_at': mod.stamp(at)}

    def test_order_and_chain(self):
        mod.append(self.path, self.rec('before'))
        with self.assertRaises(ValueError):
            mod.append(self.path, self.rec('before'))  # id reused
        with self.assertRaises(ValueError):
            mod.append(self.path, self.rec('act', exp='PRX-B'))  # act without before
        mod.append(self.path, self.rec('act'))
        with self.assertRaises(ValueError):
            mod.append(self.path, self.rec('act'))  # act twice
        mod.append(self.path, self.rec('after', at=T0 + timedelta(hours=3)))
        with self.assertRaises(ValueError):
            mod.append(self.path, self.rec('after', at=T0))  # time goes backwards
        records, lines = mod.read_ledger(self.path)
        self.assertEqual([r['kind'] for r in records], ['before', 'act', 'after'])
        tampered = lines[1].replace('"act"', '"after"')
        with self.assertRaises(ValueError):
            mod.verify([lines[0], tampered, lines[2]])

    def test_truncated_ledger_is_refused(self):
        mod.append(self.path, self.rec('before'))
        self.path.write_text(self.path.read_text(encoding='ascii').rstrip('\n'), encoding='ascii', newline='\n')
        with self.assertRaises(ValueError):
            mod.read_ledger(self.path)


class Transport(unittest.TestCase):
    class Run:
        def __init__(self, code=0, stdout='{}', stderr=''):
            self.code, self.stdout, self.stderr, self.calls = code, stdout, stderr, []

        def __call__(self, args, **kw):
            self.calls.append((args, kw))
            return types.SimpleNamespace(returncode=self.code, stdout=self.stdout, stderr=self.stderr)

    def test_writer_merge_carries_the_head_guard_and_no_token(self):
        run = self.Run()
        with patch.dict(os.environ, {'GITHUB_TOKEN': 'dead', 'GH_TOKEN': 'dead'}):
            self.assertEqual(mod.Writer(run).update_branch(REPO, 7, sha('h'), 'MERGE'), ('ACCEPTED', None))
        args, kw = run.calls[0]
        self.assertEqual(args[:5], ['gh', 'api', '-X', 'PUT', f'repos/{REPO}/pulls/7/update-branch'])
        self.assertIn('expected_head_sha=' + sha('h'), args)
        self.assertNotIn('GITHUB_TOKEN', kw['env'])
        self.assertNotIn('GH_TOKEN', kw['env'])

    def test_writer_failure_and_rebase(self):
        run = self.Run(code=1, stderr='gh: Update branch failed (HTTP 422)')
        self.assertEqual(mod.Writer(run).update_branch(REPO, 7, sha('h'), 'MERGE'), ('FAILED', 'HTTP_422'))
        run = self.Run()
        mod.Writer(run).update_branch(REPO, 7, sha('h'), 'REBASE')
        self.assertEqual(run.calls[0][0], ['gh', 'pr', 'update-branch', '7', '-R', REPO, '--rebase'])

    def test_gh_retries_5xx_but_not_4xx(self):
        class Flaky:
            def __init__(self, codes):
                self.codes, self.calls = list(codes), 0

            def __call__(self, args, **kw):
                self.calls += 1
                code, err = self.codes.pop(0)
                return types.SimpleNamespace(returncode=code, stdout='[]', stderr=err)
        run, sleeps = Flaky([(1, 'HTTP 502: Bad Gateway'), (0, '')]), []
        self.assertEqual(mod.Client(run, sleep=sleeps.append).prs(REPO), [])
        self.assertEqual((run.calls, sleeps), (2, [5]))
        run = Flaky([(1, 'gh: Not Found (HTTP 404)')])
        with self.assertRaisesRegex(OSError, 'HTTP 404'):
            mod.Client(run, sleep=sleeps.append).prs(REPO)
        self.assertEqual(run.calls, 1)

    def test_compare_needs_exact_shas(self):
        run = self.Run(stdout=json.dumps({'behind_by': 1}))
        c = mod.Client(run)
        self.assertEqual(c.compare(REPO, BASE0, BASE1), {'behind_by': 1})
        self.assertEqual(run.calls[0][0], ['gh', 'api', f'repos/{REPO}/compare/{BASE0}...{BASE1}'])
        with self.assertRaises(ValueError):
            c.compare(REPO, 'master', BASE1)


class Reruns(unittest.TestCase):
    """Slice 2: rerun_triage decides, act reruns failed jobs, debug reruns become LDAB observations."""

    KINDS = {1: 'runner_lost', 2: 'thin_logs', 3: 'failed_step', 4: 'green', 5: 'runner_lost'}

    def client(self):
        fc = FakeClient([pr(n, sha(f'h{n}'), ci='SUCCESS' if k == 'green' else 'FAILURE')
                         for n, k in self.KINDS.items()])
        for n, k in self.KINDS.items():
            failed_run(fc, n, k)
        fc.compares[(BASE0, sha('h5'))] = cmp(sha('h5'), behind=4)  # behind main: RECONCILE_MAIN
        return fc

    def test_classifier(self):
        run = {'conclusion': 'failure'}
        self.assertEqual(mod.classify(run, [{'id': 1, 'conclusion': 'failure', 'steps': []}])[:3],
                         ('TRANSIENT', 'runner_lost', False))
        self.assertEqual(mod.classify(run, [{'id': 1, 'conclusion': 'failure',
                                             'steps': [{'conclusion': 'success'}]}])[:3], ('UNCLASSIFIED', None, True))
        self.assertEqual(mod.classify(run, [{'id': 1, 'conclusion': 'failure',
                                             'steps': [{'conclusion': 'failure'}]}])[:3], ('UNCLASSIFIED', None, False))
        self.assertEqual(mod.classify({'conclusion': 'success'}, [{'id': 1}])[:3], ('NONE', None, False))
        # `rerun --failed` reruns every failed job: one actionable failed step anywhere means inspect first.
        lost = {'id': 1, 'conclusion': 'failure', 'steps': []}
        red = {'id': 2, 'conclusion': 'failure', 'steps': [{'conclusion': 'failure'}]}
        thin = {'id': 3, 'conclusion': 'failure', 'steps': [{'conclusion': 'success'}]}
        kind, cause, insufficient, job = mod.classify(run, [lost, red, thin])
        self.assertEqual((kind, cause, insufficient, job['id']), ('UNCLASSIFIED', None, False, 2))
        self.assertEqual(mod.classify(run, [lost, thin])[:3], ('UNCLASSIFIED', None, True))
        self.assertEqual(mod.classify(run, [lost, {**lost, 'id': 4}])[:3], ('TRANSIENT', 'runner_lost', False))

    def test_triage_owner_decides_eligibility(self):
        decisions = {}
        for level, wanted in (('RERUN', 1), ('DEBUG_RERUN', 2)):
            b = mod.before(self.client(), [REPO], policy(intervention=level, holdout=0.5), 'PRX-R', T0, {})
            rows = {r['number']: r for r in b['prs']}
            decisions = {n: r['triage']['decision'] for n, r in rows.items()}
            self.assertEqual([n for n, r in rows.items() if not r['skip']], [wanted])
        self.assertEqual(decisions, {1: 'RERUN_FAILED_JOBS_CANDIDATE', 2: 'DEBUG_RERUN_CANDIDATE',
                                     3: 'INSPECT_FIRSTRED', 4: 'EVALUATE_INDEPENDENT_GATES', 5: 'RECONCILE_MAIN'})
        self.assertEqual(rows[3]['skip'], ['TRIAGE_INSPECT_FIRSTRED'])
        self.assertEqual(b['pulse'][REPO]['triage_counts']['RECONCILE_MAIN'], 1)
        self.assertEqual(rows[1]['triage']['run_id'], 1001)

    def test_act_reruns_only_the_judged_attempt(self):
        fc = self.client()
        b = mod.before(fc, [REPO], policy(intervention='DEBUG_RERUN', holdout=0.01), 'PRX-D', T0, {})
        w = FakeWriter(fc)
        rec = mod.act(fc, w, b, True, T0, sleep=no_sleep)
        self.assertEqual(w.calls, [(REPO, 1002, True)])
        self.assertEqual((rec['intervention'], rec['fpc_receipts_invalidated']), ('DEBUG_RERUN', 0))
        self.assertEqual((rec['results'][0]['run_id'], rec['results'][0]['run_attempt']), (1002, 1))
        fc2 = self.client()
        fc2.run_state[1002]['run_attempt'] = 2  # someone already reran it
        w2 = FakeWriter(fc2)
        rec2 = mod.act(fc2, w2, b, True, T0, sleep=no_sleep)
        self.assertEqual((w2.calls, rec2['results'][0]['detail']), ([], 'RUN_MOVED'))

    def test_debug_rerun_ldab_observation(self):
        abacus = 'GBOGEB/ABACUS'
        fc = FakeClient([])
        fc.run_state[77] = {'run_attempt': 2, 'status': 'completed', 'conclusion': 'success'}
        fc.jobs[77] = [{'id': 901, 'name': 'other'}, {'id': 902, 'name': 'unit'}]
        b = {'prs': [{'repo': abacus, 'number': 9, 'triage': {'job_name': 'unit'}},
                     {'repo': REPO, 'number': 8, 'triage': {'job_name': 'unit'}}]}
        act_rec = {'intervention': 'DEBUG_RERUN', 'results': [
            {'repo': abacus, 'number': 9, 'head_sha': sha('h9'), 'result': 'ACCEPTED', 'run_id': 77, 'run_attempt': 1},
            {'repo': REPO, 'number': 8, 'head_sha': sha('h8'), 'result': 'ACCEPTED', 'run_id': 77, 'run_attempt': 1}]}
        out = {r['number']: r for r in mod.reruns(fc, b, act_rec)}
        obs = out[9]['ldab']
        self.assertEqual((obs['job_id'], obs['proof_level'], obs['real_probe_steps']), (902, 'REPORTED_UNVERIFIED', 0))
        self.assertEqual(obs['evidence_url'], 'https://github.com/GBOGEB/ABACUS/actions/runs/77')
        self.assertEqual(out[8]['ldab'], 'NOT_IN_LDAB_SCOPE')
        self.assertEqual((out[9]['attempt_before'], out[9]['attempt_after'], out[9]['conclusion']), (1, 2, 'success'))
        self.assertIn(('paginate', f'/repos/{abacus}/actions/runs/77/attempts/2/jobs'), fc.calls)  # our attempt's jobs
        fc.run_state[77]['run_attempt'] = 3  # someone reran again after us: attempt 3 is not our evidence
        later = {r['number']: r for r in mod.reruns(fc, b, act_rec)}
        self.assertEqual((later[9]['ldab'], later[9]['conclusion']), ('DISPATCHED_ATTEMPT_UNIDENTIFIABLE', None))
        fc.run_state[77]['run_attempt'] = 1
        self.assertEqual(mod.reruns(fc, b, act_rec)[0]['ldab'], 'NO_NEW_ATTEMPT')
        self.assertEqual(mod.reruns(fc, b, {**act_rec, 'intervention': 'RERUN'})[0]['ldab'], 'NOT_A_DEBUG_RERUN')
        with self.assertRaises(ValueError):  # the LDAB consumer refuses evidence outside ABACUS / CODEX
            mod.ldab_observation(REPO, sha('h8'), 77, 902)

    def test_green_after_our_rerun_is_delivered_by_rerun(self):
        kinds = {n: 'runner_lost' for n in range(1, 13)}
        fc = FakeClient([pr(n, sha(f'h{n}'), ci='FAILURE') for n in kinds])
        for n in kinds:
            failed_run(fc, n, 'runner_lost')
        b = mod.before(fc, [REPO], policy(intervention='RERUN', holdout=0.5, min_arm=2), 'PRX-G', T0, {})
        treated = [r['number'] for r in b['prs'] if r['arm'] == 'TREATED']
        holdout = [r['number'] for r in b['prs'] if r['arm'] == 'HOLDOUT']
        self.assertTrue(treated and holdout)
        a = mod.act(fc, FakeWriter(fc), b, True, T0, sleep=no_sleep)
        for n in treated + holdout[:1]:
            fc.views[(REPO, n)] = pr(n, sha(f'h{n}'), ci='SUCCESS')
        rows = [mod.pr_row(fc, REPO, fc.pr(REPO, r['number']), BASE0, b['policy'], T0) for r in b['prs']]
        ev = mod.evaluate(fc, b, a, rows)
        attribution = {p['number']: p['attribution'] for p in ev['positives']}
        self.assertTrue(all(attribution[n] == 'DELIVERED_BY_RERUN' for n in treated))
        self.assertEqual(attribution[holdout[0]], 'EXTERNAL')
        # Rerun again by someone else after us: the green is not credited to our rerun.
        ev2 = mod.evaluate(fc, b, a, rows, foreign={(REPO, treated[0])})
        self.assertEqual({p['number']: p['attribution'] for p in ev2['positives']}[treated[0]], 'UNVERIFIED')

    def test_writer_rerun_args_and_policy_flags(self):
        run = Transport.Run()
        mod.Writer(run).rerun_failed(REPO, 42, True)
        self.assertEqual(run.calls[0][0], ['gh', 'run', 'rerun', '42', '--failed', '-R', REPO, '--debug'])
        mod.Writer(run).rerun_failed(REPO, 42, False)
        self.assertNotIn('--debug', run.calls[1][0])
        with tempfile.TemporaryDirectory() as d:
            with patch('builtins.print'):
                mod.main(['before', '--ledger', str(Path(d) / 'l.jsonl'), '--experiment', 'PRX-F',
                          '--intervention', 'debug-rerun', '--gate-check', 'PR Feedback Gate',
                          '--gate-check', 'first-pass-closure', '--census-ledger', str(Path(d) / 'none.jsonl')],
                         client=self.client(), now=T0)
            p = mod.read_ledger(Path(d) / 'l.jsonl')[0][0]['policy']
        self.assertEqual((p['intervention'], p['gate_checks']), ('DEBUG_RERUN', ['PR Feedback Gate', 'first-pass-closure']))


class Cli(unittest.TestCase):
    def test_before_act_after_report(self):
        with tempfile.TemporaryDirectory() as d:
            ledger, out = Path(d) / 'l.jsonl', Path(d) / 'r.md'
            none = str(Path(d) / 'no-census.jsonl')
            fc = FakeClient([pr(n, sha(f'h{n}'), ci='FAILURE') for n in range(1, 7)])
            common = ['--ledger', str(ledger)]
            with patch('builtins.print'):
                mod.main(['before', *common, '--experiment', 'PRX-CLI', '--holdout', '0.5', '--min-arm', '1',
                          '--census-ledger', none], client=fc, now=T0)
                mod.main(['act', *common, '--experiment', 'PRX-CLI'], client=fc, writer=FakeWriter(), now=T0)
                self.assertEqual(len(mod.read_ledger(ledger)[0]), 1)  # a dry run appends nothing
                w = FakeWriter()
                mod.main(['act', *common, '--experiment', 'PRX-CLI', '--apply'], client=fc, writer=w, now=T0,
                         sleep=no_sleep)
                with self.assertRaises(ValueError):  # too early to measure
                    mod.main(['after', *common, '--experiment', 'PRX-CLI', '--census-ledger', none],
                             client=fc, now=T0 + timedelta(minutes=30))
                mod.main(['after', *common, '--experiment', 'PRX-CLI', '--census-ledger', none],
                         client=fc, now=T0 + timedelta(hours=3))
                mod.main(['report', *common, '--experiment', 'PRX-CLI', '--out', str(out)])
            records = mod.read_ledger(ledger)[0]
            self.assertEqual([r['kind'] for r in records], ['before', 'act', 'after'])
            self.assertEqual(len(w.calls), records[0]['counts']['TREATED'])
            text = out.read_text(encoding='utf-8')
            self.assertIn('# PR intervention PRX-CLI', text)
            self.assertIn('| TREATED |', text)
            self.assertIn('Census (scale-dock pulses): UNKNOWN', text)


if __name__ == '__main__':
    unittest.main()
