"""Real-pulse adapter: recorded API fixtures, ledger chain, private boundary and the scale-dock series contract."""
from __future__ import annotations

import copy
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

# harvest.py imports PyYAML for its own CLI only; the gogreen CI lanes do not install it.
if importlib.util.find_spec('yaml') is None:
    sys.modules['yaml'] = types.ModuleType('yaml')

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('scale_dock_series', HERE.parent / 'scale_dock_series.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
sd, bd = mod.sd, mod.bd
FIXTURE = json.loads((HERE.parent / 'samples' / 'scale_dock_series_api_fixture_20261024.json').read_text(encoding='utf-8'))
CODEX, HUB_REPO, ABACUS = 'GBOGEB/CODEX', 'GBOGEB/pipeline-automation-hub', 'GBOGEB/ABACUS'
CODEX_HEAD = '4f1a0025181eab8b4fca219b7647f38abb12959a'
HUB_HEAD = 'c7e2fb38e5c3471263ac1da578439d2bfb6427ae'
ABACUS_HEAD = 'a' * 40
PRIVATE_HEAD = 'f' * 40
ROOTS = [{'id': 'CODEX-RC-2026-0001', 'severity': 'P2',
          'match': [{'repo': CODEX, 'workflow': 'OSV-Scanner', 'step': 'Run osv-scanner-reporter'}]},
         {'id': 'ABACUS-RC-2026-0001', 'severity': 'P0', 'match': [{'probe': 'ruleset_drift', 'repo': ABACUS}]}]
OSV = 'GBOGEB/CODEX::OSV-Scanner :: scan-scheduled / osv-scan'
T0 = datetime(2026, 10, 24, 16, 53, 22, tzinfo=timezone.utc)
T1 = datetime(2026, 10, 24, 17, 53, 22, tzinfo=timezone.utc)


def abacus_routes(conclusion='success', head=ABACUS_HEAD):
    """Minimal synthetic ABACUS default head (one run, one job) to complete the three-repo pulse."""
    job = {'id': 9001, 'run_id': 801, 'run_attempt': 1, 'head_sha': head, 'name': 'unit (py3.12)',
           'workflow_name': 'CI', 'status': 'completed', 'conclusion': conclusion,
           'html_url': 'https://github.com/GBOGEB/ABACUS/actions/runs/801/job/9001',
           'steps': [{'name': 'pytest', 'number': 3, 'conclusion': conclusion}]}
    return {f'/repos/{ABACUS}': {'default_branch': 'main'},
            f'/repos/{ABACUS}/commits/main': {'sha': head},
            f'/repos/{ABACUS}/actions/runs?head_sha={head}&per_page=100&page=1':
                {'total_count': 1, 'workflow_runs': [{'id': 801, 'head_sha': head, 'name': 'CI', 'status': 'completed'}]},
            f'/repos/{ABACUS}/actions/runs/801/jobs?per_page=100&page=1': {'total_count': 1, 'jobs': [job]},
            f'/repos/{ABACUS}/actions/runs?status=queued&per_page=100&page=1': {'total_count': 0, 'workflow_runs': []}}


class FakeReader:
    """Answers recorded routes; the BD census routes are empty pages; the private repo can fail."""
    paginate = bd.GitHubReader.paginate

    def __init__(self, routes, private_fails=False):
        self.routes, self.private_fails, self.calls = routes, private_fails, []

    def get(self, route):
        self.calls.append(route)
        if bd.PRIVATE_OWNER_REPO in route or 'cryoplant' in route:
            if self.private_fails:
                raise OSError('gh api exit 1')
            if '/pulls?' in route:
                return [{'number': 7, 'state': 'open', 'head': {'sha': PRIVATE_HEAD}, 'base': {'ref': 'main'}}]
            if '/actions/runs?' in route:
                return {'total_count': 0, 'workflow_runs': []}
        if '/pulls?' in route:
            return []
        if route.startswith('/search/issues'):
            return ({'total_count': 2, 'items': [{'number': 70, 'state': 'open'}, {'number': 71, 'state': 'open'}]}
                    if 'cryoplant' in route else {'total_count': 0, 'items': []})
        if route not in self.routes:
            raise OSError('unrecorded route ' + route)
        return copy.deepcopy(self.routes[route])


def reader(**kw):
    return FakeReader({**FIXTURE['routes'], **abacus_routes(**kw)})


DOCK_FILES = {name: mod.HUB / path for name, path in mod.FILE_DOCKS.items()}


def fake_git(missing=False, tamper=None):
    """git rev-parse <sha>:<path> -> fake OID; git cat-file blob <oid> -> the committed projection."""
    def git(args):
        if args[0] == 'rev-parse':
            if missing:
                raise subprocess.CalledProcessError(128, ['git', *args])
            name = next(n for n, p in mod.FILE_DOCKS.items() if args[1].endswith(':' + p))
            return ('oid-' + name + '\n').encode()
        name = args[2][len('oid-'):]
        raw = DOCK_FILES[name].read_bytes()
        return raw.replace(b'"schema"', b'"tampered": 1, "schema"', 1) if tamper == name else raw
    return git


def first_pulse(conclusion='success'):
    return mod.observe(reader(conclusion=conclusion), ROOTS, None, fake_git(), now=T0)


class GhReaderTests(unittest.TestCase):
    def run_with(self, *results):
        calls = []

        def run(args, **kw):
            calls.append((args, kw))
            rc, out, err = results[min(len(calls), len(results)) - 1]
            return subprocess.CompletedProcess(args, rc, out, err)
        self.waits = []
        return mod.GhReader(run=run, sleep=self.waits.append), calls

    def test_uses_gh_login_without_shell_tokens(self):
        gh, calls = self.run_with((0, '{"sha": "x"}', ''))
        with patch.dict(os.environ, {'GITHUB_TOKEN': 'dead', 'GH_TOKEN': 'dead'}):
            self.assertEqual(gh.get('/repos/GBOGEB/CODEX/commits/main'), {'sha': 'x'})
        args, kw = calls[0]
        self.assertEqual(args, ['gh', 'api', 'repos/GBOGEB/CODEX/commits/main'])
        self.assertNotIn('GITHUB_TOKEN', kw['env'])
        self.assertNotIn('GH_TOKEN', kw['env'])
        self.assertEqual(gh.token, '')

    def test_retries_5xx_then_fails_closed(self):
        gh, calls = self.run_with((1, '', 'gh: Server Error (HTTP 502)'))
        with self.assertRaises(OSError):
            gh.get('/repos/x/y')
        self.assertEqual((len(calls), self.waits), (3, [5, 10]))

    def test_recovers_after_one_transport_error(self):
        gh, calls = self.run_with((1, '', 'Get "https://api.github.com/x": dial tcp: i/o timeout'), (0, '[]', ''))
        self.assertEqual(gh.get('/repos/x/y'), [])
        self.assertEqual((len(calls), self.waits), (2, [5]))

    def test_no_retry_on_4xx(self):
        gh, calls = self.run_with((1, '', 'gh: Not Found (HTTP 404)'))
        with self.assertRaises(OSError):
            gh.get('/repos/x/y')
        self.assertEqual(len(calls), 1)

    def test_noncanonical_route(self):
        gh, calls = self.run_with((0, '{}', ''))
        for route in ('repos/x', '/repos/../x', '/repos\\x'):
            with self.assertRaises(ValueError):
                gh.get(route)
        self.assertEqual(calls, [])

    def test_paginate_is_the_owner_total_count_check(self):
        gh, _ = self.run_with((0, '{"total_count": 3, "jobs": [{"id": 1}]}', ''))
        with self.assertRaises(ValueError):
            gh.paginate('/repos/x/y/actions/runs/1/jobs', key='jobs')

    def test_recorder_trims_to_read_fields(self):
        rec = mod.Recorder(FakeReader({'/r': {'sha': 'x', 'author': {'login': 'me'}, 'jobs': [{'id': 1, 'labels': []}]}}))
        rec.get('/r')
        self.assertEqual(rec.routes['/r'], {'sha': 'x', 'jobs': [{'id': 1}]})


class GitReaderTests(unittest.TestCase):
    def test_git_reader_runs_in_hub_and_checks(self):
        calls = []

        def run(args, **kw):
            calls.append((args, kw))
            return subprocess.CompletedProcess(args, 0, b'oid\n', b'')
        self.assertEqual(mod.git_reader(cwd='hub', run=run)(['rev-parse', 'HEAD']), b'oid\n')
        self.assertEqual(calls, [(['git', 'rev-parse', 'HEAD'], {'cwd': 'hub', 'capture_output': True, 'check': True})])


class ObserveRepoTests(unittest.TestCase):
    def test_recorded_codex_head(self):
        seen = mod.observe_repo(reader(), CODEX, ROOTS, {})
        self.assertEqual(seen['head'], CODEX_HEAD)
        self.assertEqual(seen['eligible'], 46)
        self.assertEqual(seen['provenance'], {'branch': 'main', 'runs': 24, 'runs_in_progress': 0, 'jobs_seen': 46,
                                              'job_identities': 46, 'completed': 46, 'incomplete': 0})
        red = {f['id']: f for f in seen['findings']}
        self.assertEqual(len(red), 2)
        osv = red[OSV]
        self.assertEqual((osv['state'], osv['root_id'], osv['priority'], osv['family']),
                         ('RED', 'CODEX-RC-2026-0001', 'P2', 'SECURITY'))
        self.assertEqual(osv['first_failed_step'], 'Run osv-scanner-reporter')
        self.assertTrue(all(type(osv[k]) is int for k in ('run_id', 'attempt', 'job_id')))
        self.assertEqual(osv['fingerprint'], 'OSV-Scanner :: scan-scheduled / osv-scan :: Run osv-scanner-reporter')
        other = next(f for f in seen['findings'] if f['id'] != OSV)
        self.assertEqual((other['root_id'], other['priority'], other['family']), (None, 'UNKNOWN', 'OTHER'))

    def test_recorded_hub_head_is_green(self):
        seen = mod.observe_repo(reader(), HUB_REPO, ROOTS, {})
        self.assertEqual((seen['head'], seen['eligible'], seen['findings']), (HUB_HEAD, 16, []))

    def test_partial_native_identity_is_null(self):
        routes = copy.deepcopy(FIXTURE['routes'])
        for v in routes.values():
            for j in v.get('jobs') or [] if isinstance(v, dict) else []:
                if j['conclusion'] == 'failure':
                    j['run_attempt'] = None
        seen = mod.observe_repo(FakeReader(routes), CODEX, ROOTS, {})
        for f in seen['findings']:
            self.assertEqual((f['run_id'], f['attempt'], f['job_id']), (None, None, None))

    def test_recovered_carries_previous_root(self):
        before = {'GBOGEB/ABACUS::CI :: unit [py3.12]': {'state': 'RED', 'fingerprint': 'fp', 'root_id': 'R1',
                                                       'priority': 'P1', 'family': 'COMPATIBILITY'}}
        seen = mod.observe_repo(reader(), ABACUS, ROOTS, before)
        (f,) = seen['findings']
        self.assertEqual((f['state'], f['root_id'], f['priority'], f['first_failed_step']),
                         ('RECOVERED', 'R1', 'P1', None))

    def test_green_without_prior_red_is_not_a_finding(self):
        seen = mod.observe_repo(reader(), ABACUS, ROOTS, {'other': {'state': 'RED'}})
        self.assertEqual((seen['findings'], seen['eligible']), ([], 1))

    def test_latest_attempt_wins_one_identity(self):
        routes = abacus_routes('failure')
        runs = routes[f'/repos/{ABACUS}/actions/runs?head_sha={ABACUS_HEAD}&per_page=100&page=1']
        runs['workflow_runs'].append({'id': 802, 'head_sha': ABACUS_HEAD, 'name': 'CI', 'status': 'completed'})
        runs['total_count'] = 2
        retry = copy.deepcopy(routes[f'/repos/{ABACUS}/actions/runs/801/jobs?per_page=100&page=1'])
        retry['jobs'][0].update(id=9002, run_id=802, run_attempt=2, conclusion='success')
        routes[f'/repos/{ABACUS}/actions/runs/802/jobs?per_page=100&page=1'] = retry
        seen = mod.observe_repo(FakeReader(routes), ABACUS, ROOTS, {})
        self.assertEqual(seen['provenance']['jobs_seen'], 2)
        self.assertEqual(seen['provenance']['job_identities'], 1)
        self.assertEqual(seen['findings'], [])
        runs['workflow_runs'].reverse()  # an older attempt listed after the retry still loses
        seen = mod.observe_repo(FakeReader(routes), ABACUS, ROOTS, {})
        self.assertEqual((seen['provenance']['job_identities'], seen['findings']), (1, []))

    def test_in_progress_run_is_not_read(self):
        routes = abacus_routes()
        routes[f'/repos/{ABACUS}/actions/runs?head_sha={ABACUS_HEAD}&per_page=100&page=1']['workflow_runs'][0]['status'] = 'in_progress'
        fake = FakeReader(routes)
        seen = mod.observe_repo(fake, ABACUS, ROOTS, {})
        self.assertEqual((seen['eligible'], seen['provenance']['runs_in_progress'], seen['provenance']['jobs_seen']), (0, 1, 0))
        self.assertFalse([r for r in fake.calls if '/jobs' in r])

    def test_incomplete_job_not_eligible(self):
        routes = abacus_routes()
        routes[f'/repos/{ABACUS}/actions/runs/801/jobs?per_page=100&page=1']['jobs'][0].update(
            status='in_progress', conclusion=None)
        seen = mod.observe_repo(FakeReader(routes), ABACUS, ROOTS, {})
        self.assertEqual((seen['eligible'], seen['provenance']['incomplete']), (0, 1))

    def test_failed_job_without_failed_step(self):
        routes = abacus_routes('failure')
        routes[f'/repos/{ABACUS}/actions/runs/801/jobs?per_page=100&page=1']['jobs'][0]['steps'] = []
        (f,) = mod.observe_repo(FakeReader(routes), ABACUS, ROOTS, {})['findings']
        self.assertIsNone(f['first_failed_step'])
        self.assertEqual(f['family'], 'OTHER')

    def test_exact_head_mismatch_holds(self):
        routes = abacus_routes()
        routes[f'/repos/{ABACUS}/actions/runs/801/jobs?per_page=100&page=1']['jobs'][0]['head_sha'] = 'b' * 40
        with self.assertRaisesRegex(ValueError, 'job exact-head'):
            mod.observe_repo(FakeReader(routes), ABACUS, ROOTS, {})
        routes = abacus_routes()
        routes[f'/repos/{ABACUS}/actions/runs?head_sha={ABACUS_HEAD}&per_page=100&page=1']['workflow_runs'][0]['head_sha'] = 'b' * 40
        with self.assertRaisesRegex(ValueError, 'run exact-head'):
            mod.observe_repo(FakeReader(routes), ABACUS, ROOTS, {})

    def test_head_must_be_full_sha(self):
        with self.assertRaisesRegex(ValueError, 'head SHA'):
            mod.observe_repo(FakeReader(abacus_routes(head='abc')), ABACUS, ROOTS, {})


class IssueBdAndQueueTests(unittest.TestCase):
    def test_private_counts_are_aggregate_only(self):
        out = mod.issue_bd(reader(), '2026-10-24T16:53:22Z')
        self.assertEqual((out['private_qps_open_issues'], out['private_qps_open_prs']), (2, 1))
        self.assertEqual(out['private_qps_observation'], 'GH_LOGIN_AGGREGATE_COUNT_NOT_OWNER_RECEIPT')
        self.assertEqual(out['private_receipt_status'], 'HOLD_OWNER_PRIVATE_RECEIPT_REQUIRED')
        text = json.dumps(out)
        self.assertNotIn(PRIVATE_HEAD, text)
        self.assertEqual({x['repository'] for x in out['issues']}, set(bd.PUBLIC_REPOS))
        self.assertEqual(sd.dock_issue_bd(out)['private_qps_open_issues'], 2)

    def test_private_read_failure_is_unknown_not_zero(self):
        out = mod.issue_bd(FakeReader({}, private_fails=True), '2026-10-24T16:53:22Z')
        self.assertIsNone(out['private_qps_open_issues'])
        self.assertIsNone(out['private_qps_open_prs'])
        self.assertEqual(out['private_qps_observation'], 'UNKNOWN_READ_FAILED:OSError')

    def test_queue_ages_from_recorded_runs(self):
        q = mod.queue_of(reader(), bd.PUBLIC_REPOS, T0)
        self.assertEqual(len(q['queued_run_ids']), len(q['queue_ages_seconds']))
        self.assertEqual(len(q['queued_run_ids']), 4)
        self.assertTrue(all(a >= 0 for a in q['queue_ages_seconds']))
        self.assertEqual((q['real_dispatches'], q['verified_runner_slots']), (0, None))

    def test_queued_run_without_time_holds(self):
        routes = abacus_routes()
        routes[f'/repos/{ABACUS}/actions/runs?status=queued&per_page=100&page=1'] = {
            'total_count': 1, 'workflow_runs': [{'id': 5}]}
        with self.assertRaisesRegex(ValueError, 'queued run identity'):
            mod.queue_of(FakeReader(routes), (ABACUS,), T0)


class PulseLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'real' / 'pulses.jsonl'

    def tearDown(self):
        self.tmp.cleanup()

    def test_n0_pulse_shape(self):
        rec = first_pulse('failure')
        p = rec['pulse']
        self.assertEqual((rec['n'], p['n'], rec['observed_at']), (0, 0, '2026-10-24T16:53:22Z'))
        self.assertEqual(p['source_heads'], {ABACUS: ABACUS_HEAD, CODEX: CODEX_HEAD, HUB_REPO: HUB_HEAD})
        self.assertEqual(rec['hub_sha'], HUB_HEAD)
        self.assertEqual(p['eligible'], 63)
        self.assertEqual(sum(f['state'] == 'RED' for f in p['findings']), 3)
        self.assertEqual(set(rec['file_docks']), set(mod.FILE_DOCKS))
        self.assertEqual(rec['file_docks']['everred']['blob_oid'], 'oid-everred')
        self.assertNotIn(PRIVATE_HEAD, mod.line(rec))

    def test_no_completed_job_holds(self):
        routes = {**FIXTURE['routes'], **abacus_routes()}
        routes.update({r: {'total_count': 0, 'workflow_runs': []} for r in routes if 'actions/runs?' in r})
        with self.assertRaisesRegex(ValueError, 'no completed job'):
            mod.observe(FakeReader(routes), ROOTS, None, fake_git(), now=T0)

    def test_file_docks_must_exist_at_hub_head(self):
        with self.assertRaisesRegex(ValueError, 'git fetch origin first'):
            mod.observe(reader(), ROOTS, None, fake_git(missing=True), now=T0)

    def test_append_chain_and_recovery(self):
        n0 = mod.append(self.path, first_pulse('failure'))
        self.assertIsNone(n0['prev_sha256'])
        first_bytes = self.path.read_bytes()
        n1 = mod.append(self.path, mod.observe(reader(), ROOTS, n0, fake_git(), now=T1))
        self.assertTrue(self.path.read_bytes().startswith(first_bytes))  # never rewritten
        self.assertEqual(n1['prev_sha256'], mod.sha256(first_bytes.decode().rstrip('\n')))
        records, _ = mod.read_ledger(self.path)
        self.assertEqual([r['n'] for r in records], [0, 1])
        doc = mod.series(records, fake_git())
        receipt = sd.evaluate(doc)
        (move,) = receipt['red_metrics']['transitions']
        self.assertEqual(move['recoveries'], ['GBOGEB/ABACUS::CI :: unit [py3.12]'])
        self.assertIn(OSV, move['persisting_reds'])

    def test_append_rejects_wrong_ordinal_and_old_time(self):
        n0 = mod.append(self.path, first_pulse())
        with self.assertRaisesRegex(ValueError, 'append ordinal'):
            mod.append(self.path, first_pulse())
        later = mod.observe(reader(), ROOTS, n0, fake_git(), now=T0)
        with self.assertRaisesRegex(ValueError, 'monotone'):
            mod.append(self.path, later)

    def test_tampered_ledger_holds(self):
        n0 = mod.append(self.path, first_pulse())
        mod.append(self.path, mod.observe(reader(), ROOTS, n0, fake_git(), now=T1))
        lines = self.path.read_text().splitlines()
        cases = {'chain broken': [mod.line({**json.loads(lines[0]), 'hub_sha': 'b' * 40}), lines[1]],
                 'not canonical': [lines[0].replace('{', '{ ', 1), lines[1]],
                 'not JSON': ['{', lines[1]],
                 'ordinal': [lines[1]]}
        for message, broken in cases.items():
            with self.subTest(message), self.assertRaisesRegex(ValueError, message):
                mod.verify(broken)
        self.path.write_text(lines[0])  # no trailing newline: an interrupted write
        with self.assertRaisesRegex(ValueError, 'truncated'):
            mod.read_ledger(self.path)

    def test_pulse_time_must_match_record(self):
        rec = {**first_pulse(), 'prev_sha256': None}
        rec['pulse'] = {**rec['pulse'], 'observed_at': '2026-10-24T16:53:23Z'}
        with self.assertRaisesRegex(ValueError, 'pulse time'):
            mod.verify([mod.line(rec)])


class SeriesTests(unittest.TestCase):
    def records(self):
        rec = {**first_pulse('failure'), 'prev_sha256': None}
        return mod.verify([mod.line(rec)])

    def test_series_is_a_valid_historical_replay(self):
        doc = mod.series(self.records(), fake_git())
        self.assertEqual((doc['schema'], doc['observation_class']), (sd.SCHEMA, 'HISTORICAL_REPLAY'))
        self.assertEqual(doc['controls'], mod.CONTROLS)
        receipt = sd.evaluate(doc)
        self.assertEqual({k for k, v in receipt['docks'].items() if v['metrics']}, set(sd.DOCK_SCHEMAS))
        self.assertEqual(receipt['docks']['issue_bd']['age_hours_at_latest_pulse'], 0.0)
        self.assertEqual(receipt['red_metrics']['pulses'][0]['root_red'], ['CODEX-RC-2026-0001'])
        self.assertEqual(receipt['merge_admission'], 'HOLD')

    def test_pinned_blob_digest_mismatch_holds(self):
        with self.assertRaisesRegex(ValueError, 'everred pinned blob digest'):
            mod.series(self.records(), fake_git(tamper='everred'))

    def test_empty_ledger_holds(self):
        with self.assertRaisesRegex(ValueError, 'empty ledger'):
            mod.series([], fake_git())

    def test_window_is_bounded(self):
        rec = self.records()[0]
        many = []
        for i in range(mod.WINDOW + 2):
            r = copy.deepcopy(rec)
            stamp = f'2026-10-24T{i:02d}:00:00Z'
            r.update(n=i, observed_at=stamp)
            r['pulse'].update(n=i, observed_at=stamp)
            many.append(r)
        doc = mod.series(many, fake_git())
        self.assertEqual(len(doc['pulses']), mod.WINDOW)
        self.assertEqual((doc['ledger']['window_first_n'], doc['ledger']['latest_n']), (2, mod.WINDOW + 1))


class CliTests(unittest.TestCase):
    def test_pulse_then_series(self):
        yaml_stub = types.SimpleNamespace(safe_load=lambda text: {'roots': ROOTS})
        with tempfile.TemporaryDirectory() as tmp:
            ledger, roots, fixture, out = (Path(tmp) / n for n in ('p.jsonl', 'roots.yaml', 'fx.json', 's.json'))
            roots.write_text('roots: []\n')
            with patch.dict(sys.modules, {'yaml': yaml_stub}), patch.object(mod, 'GhReader', lambda: reader()), \
                    patch.object(mod, 'git_reader', lambda: fake_git()), patch('sys.stdout'):
                self.assertEqual(mod.main(['pulse', '--ledger', str(ledger), '--roots', str(roots),
                                           '--record', str(fixture)]), 0)
                self.assertEqual(mod.main(['series', '--ledger', str(ledger), '--out', str(out)]), 0)
            recorded = json.loads(fixture.read_text())
            self.assertTrue(recorded)
            self.assertFalse([r for r in recorded if '/pulls' in r or '/search/' in r or 'cryoplant' in r])
            self.assertEqual(json.loads(out.read_text())['observation_class'], 'HISTORICAL_REPLAY')


class CommittedLedgerTests(unittest.TestCase):
    def test_committed_ledger_verifies_and_stays_public(self):
        if not mod.LEDGER.exists():
            self.skipTest('no committed ledger')
        records, _ = mod.read_ledger(mod.LEDGER)
        self.assertGreaterEqual(len(records), 1)
        for r in records:
            self.assertEqual(set(r['pulse']['source_heads']), set(bd.PUBLIC_REPOS))
            self.assertEqual({x['repository'] for x in r['issue_bd']['issues']}, set(bd.PUBLIC_REPOS))
            self.assertEqual(r['issue_bd']['private_receipt_status'], 'HOLD_OWNER_PRIVATE_RECEIPT_REQUIRED')
            self.assertEqual(r['hub_sha'], r['pulse']['source_heads'][HUB_REPO])


if __name__ == '__main__':
    unittest.main()
