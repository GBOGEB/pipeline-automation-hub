from __future__ import annotations

import asyncio
import copy
import importlib.util
import json
import tempfile
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / 'sipoc_instances.py'
SPEC = importlib.util.spec_from_file_location('sipoc_instances', MODULE)
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MOD)
SHA = 'a' * 40


def atlas():
    return {'schema': 'missioncontrol.federation_atlas.process_lanes.v1',
            'observer_authority': 'READ_ONLY',
            'sipoc': [{'key': k} for k in 'SIPOC'],
            'lanes': [{'id': 'SUPPLY', 'stages': [['DISCOVER', 'find', 'I', 'O', 'K', 'H']]},
                      {'id': 'TRUST', 'stages': [['PIN', 'bind', 'I', 'O', 'K', 'H']]},
                      {'id': 'DMAIC', 'stages': [['ANALYZE', 'study', 'I', 'O', 'K', 'H']]},
                      {'id': 'CENSUS', 'stages': [['ENUMERATE', 'count', 'I', 'O', 'K', 'H']]},
                      {'id': 'GATE', 'stages': [['P5', 'gate', 'I', 'O', 'K', 'H']]}]}


def node(ident, role='P', dep=None, repo='GBOGEB/ABACUS', stage='DMAIC:ANALYZE',
         state='READY', mode='OBSERVE', paths=None, root=None):
    return {'id': ident, 'incarnation': ident, 'sipoc_role': role,
            'stage_ref': stage, 'source_sha': SHA, 'repo': repo,
            'owner_issue': 561, 'state': state, 'mode': mode,
            'execution': 'ASYNCIO' if role == 'P' else 'SYNC',
            'success_predicate': 'observed exact-source proof',
            'mutation_paths': paths or [], 'root_id': root,
            'depends_on': dep or [],
            'blockers': ['REVIEW_REQUIRED'] if state == 'BLOCKED' else []}


def sample():
    nodes = [node('S', 'S', stage='SUPPLY:DISCOVER', repo='GBOGEB/pipeline-automation-hub'),
             node('I', 'I', ['S'], stage='TRUST:PIN', repo='GBOGEB/pipeline-automation-hub'),
             node('B3', dep=['I']), node('B4', dep=['I']),
             node('O', 'O', ['B3', 'B4'], stage='CENSUS:ENUMERATE', repo='GBOGEB/pipeline-automation-hub'),
             node('C', 'C', ['O'], stage='GATE:P5', repo='GBOGEB/pipeline-automation-hub', state='PROOF_PENDING')]
    return {'schema': MOD.SCHEMA, 'authority_transfer': False,
            'dispatch_authorized': False, 'cohort': 'test', 'max_parallel': 3,
            'max_parallel_per_repo': 2, 'instances': nodes,
            'next_pulse_feedback': [{'from': 'O', 'to_stage_ref': 'DMAIC:ANALYZE',
                                     'phase': 'NEXT_PULSE'}]}


class SipocInstancePlannerTests(unittest.TestCase):
    def test_fanin_after_parallel_process_incarnations(self):
        r = MOD.plan_instances(sample(), atlas())
        waves = [[n['id'] for n in wave] for wave in r['schedule']['waves']]
        self.assertEqual(waves, [['S'], ['I'], ['B3', 'B4'], ['O']])
        self.assertEqual(r['kpi']['incarnations_by_role']['P'], 2)
        self.assertEqual(r['kpi']['held_or_blocked'], 1)
        self.assertEqual(r['kpi']['asyncio_proposals'], 2)
        self.assertFalse(r['dispatch_authorized'])
        self.assertIsNone(r['kpi']['actual_worker_runs'])

    def test_asyncio_success_is_explicitly_synthetic(self):
        r = MOD.plan_instances(sample(), atlas())
        replay = asyncio.run(MOD.synthetic_asyncio_replay(r))
        self.assertEqual(replay['completed_simulated'], 5)
        self.assertTrue(replay['synthetic'])
        self.assertFalse(replay['native_proof'])

    def test_synthetic_fault_stops_next_wave(self):
        r = MOD.plan_instances(sample(), atlas())
        replay = asyncio.run(MOD.synthetic_asyncio_replay(r, inject_failure='B3'))
        self.assertEqual(replay['result'], 'EXPECTED_FAILURE')
        self.assertNotEqual(replay['completed_simulated'], 5)
        self.assertEqual(replay['faults_simulated'], ['B3'])

    def test_missing_injected_id_rejected(self):
        with self.assertRaisesRegex(ValueError, 'injected ID'):
            asyncio.run(MOD.synthetic_asyncio_replay(MOD.plan_instances(sample(), atlas()), 'ABSENT'))

    def test_same_wave_cycle_rejected(self):
        data = sample()
        data['instances'][0]['depends_on'] = ['O']
        with self.assertRaisesRegex(ValueError, 'DAG cycle'):
            MOD.plan_instances(data, atlas())

    def test_cross_wave_dependency_on_held_stays_held(self):
        data = sample()
        data['instances'][-1]['state'] = 'BLOCKED'
        data['instances'][-1]['blockers'] = ['A10']
        data['instances'].append(node('AFTER', 'P', ['C']))
        out = MOD.plan_instances(data, atlas())
        reasons = {x['id']: x['reasons'] for x in out['held']}
        self.assertIn('UPSTREAM_NOT_READY', reasons['AFTER'])
        self.assertEqual(out['kpi']['accepted_root_closures'], 0)

    def test_mutation_path_parent_child_cannot_share_wave(self):
        data = sample()
        for i in (2, 3):
            data['instances'][i]['mode'] = 'MUTATION_PROPOSAL'
        data['instances'][2]['mutation_paths'] = ['src/module.py']
        data['instances'][3]['mutation_paths'] = ['src']
        out = MOD.plan_instances(data, atlas())
        waves = [[n['id'] for n in wave] for wave in out['schedule']['waves']]
        self.assertEqual(waves[2:4], [['B3'], ['B4']])

    def test_disjoint_mutations_may_share_wave_with_owner(self):
        data = sample()
        for i in (2, 3):
            data['instances'][i]['mode'] = 'MUTATION_PROPOSAL'
        data['instances'][2]['mutation_paths'] = ['src/a.py']
        data['instances'][3]['mutation_paths'] = ['src/b.py']
        waves = MOD.plan_instances(data, atlas())['schedule']['waves']
        self.assertEqual({n['id'] for n in waves[2]}, {'B3', 'B4'})

    def test_same_causal_root_mutation_is_serialized(self):
        data = sample()
        for i in (2, 3):
            data['instances'][i]['mode'] = 'MUTATION_PROPOSAL'
            data['instances'][i]['root_id'] = 'ROOT-1'
        data['instances'][2]['mutation_paths'] = ['src/a.py']
        data['instances'][3]['mutation_paths'] = ['src/b.py']
        waves = MOD.plan_instances(data, atlas())['schedule']['waves']
        self.assertEqual([len(w) for w in waves], [1, 1, 1, 1, 1])

    def test_path_traversal_and_windows_separator_rejected(self):
        for path in ('../top', 'src/../other', 'src\\module.py', '/absolute'):
            data = sample()
            data['instances'][2]['mode'] = 'MUTATION_PROPOSAL'
            data['instances'][2]['mutation_paths'] = [path]
            with self.subTest(path=path), self.assertRaises(ValueError):
                MOD.plan_instances(data, atlas())

    def test_unsafe_parallelism_or_boolean_rejected(self):
        for cap in (True, 0, 7, '3'):
            data = sample()
            data['max_parallel'] = cap
            with self.subTest(cap=cap), self.assertRaises(ValueError):
                MOD.plan_instances(data, atlas())

    def test_owner_and_source_identity_not_swappable(self):
        data = sample()
        data['instances'][2]['source_sha'] = 'bad'
        with self.assertRaisesRegex(ValueError, 'source SHA'):
            MOD.plan_instances(data, atlas())
        data = sample()
        data['instances'][2]['root_id'] = 'R'
        data['instances'][3]['root_id'] = 'R'
        data['instances'][3]['owner_issue'] = 999
        with self.assertRaisesRegex(ValueError, 'root owner'):
            MOD.plan_instances(data, atlas())

    def test_ambiguous_cycle_in_feedback_rejected(self):
        data = sample()
        data['next_pulse_feedback'][0]['phase'] = 'SAME_PULSE'
        with self.assertRaisesRegex(ValueError, 'next pulse'):
            MOD.plan_instances(data, atlas())

    def test_noncanonical_process_source_rejected(self):
        bad = atlas()
        bad['observer_authority'] = 'WRITE'
        with self.assertRaisesRegex(ValueError, 'canonical Method Atlas'):
            MOD.plan_instances(sample(), bad)

    def test_zero_or_absent_inputs_fail_closed(self):
        for plan in ({}, {'schema': MOD.SCHEMA, 'authority_transfer': False,
                          'dispatch_authorized': False, 'max_parallel': 2,
                          'max_parallel_per_repo': 1, 'instances': []}):
            with self.assertRaises(ValueError):
                MOD.plan_instances(plan, atlas())

    def test_duplicate_incarnation_detected_even_with_distinct_ids(self):
        data = sample()
        data['instances'][3]['incarnation'] = 'B3'
        with self.assertRaisesRegex(ValueError, 'duplicate process incarnation'):
            MOD.plan_instances(data, atlas())

    def test_invalid_dependency_payload_rejected_without_type_error(self):
        data = sample()
        data['instances'][2]['depends_on'] = [{}]
        with self.assertRaisesRegex(ValueError, 'dependency identity'):
            MOD.plan_instances(data, atlas())

    def test_duplicate_instance_identity(self):
        data = sample()
        data['instances'].append(copy.deepcopy(data['instances'][2]))
        with self.assertRaisesRegex(ValueError, 'duplicate instance'):
            MOD.plan_instances(data, atlas())

    def test_cli_emits_source_and_atlas_digests_without_admission(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            inp, contract, out = root / 'input.json', root / 'atlas.json', root / 'out'
            inp.write_text(json.dumps(sample()), encoding='utf-8')
            contract.write_text(json.dumps(atlas()), encoding='utf-8')
            argv = ['sipoc_instances.py', '--input', str(inp), '--atlas', str(contract),
                    '--out', str(out), '--synthetic-replay']
            with patch('sys.argv', argv), redirect_stdout(StringIO()):
                MOD.main()
            receipt = json.loads((out / 'sipoc_instance_receipt.json').read_text())
            replay = json.loads((out / 'asyncio_synthetic_only.json').read_text())
            self.assertEqual(len(receipt['input_sha256']), 64)
            self.assertEqual(len(receipt['canonical_atlas_sha256']), 64)
            self.assertFalse(receipt['dispatch_authorized'])
            self.assertFalse(replay['native_proof'])
            self.assertEqual(len((out / 'sipoc_instance_receipt.sha256').read_text().strip()), 64)

    def test_validator_negative_surface_no_false_green(self):
        modifiers = [
            (lambda d: d['instances'][2].update(id='*'), 'instance id'),
            (lambda d: d['instances'][2].update(sipoc_role='Q'), 'SIPOC role'),
            (lambda d: d['instances'][2].update(stage_ref='DAG:UNDEFINED'), 'SIPOC role'),
            (lambda d: d['instances'][2].update(state='VERIFIED'), 'state or mode'),
            (lambda d: d['instances'][2].update(mode='UNAUTHORIZED'), 'state or mode'),
            (lambda d: d['instances'][2].update(execution='REMOTE_EXEC'), 'execution kind'),
            (lambda d: d['instances'][2].update(repo='bad'), 'source repository'),
            (lambda d: d['instances'][2].update(success_predicate=''), 'success predicate'),
            (lambda d: d['instances'][2].update(depends_on=['I', 'I']), 'duplicate dependencies'),
            (lambda d: d['instances'][2].update(depends_on=['UNKNOWN']), 'unknown or self'),
            (lambda d: d['instances'][2].update(depends_on=['B3']), 'unknown or self'),
            (lambda d: d['instances'][2].update(mutation_paths=['src/a.py']), 'read-only instance'),
            (lambda d: d['instances'][2].update(mode='MUTATION_PROPOSAL'), 'source path lease'),
            (lambda d: d['instances'][2].update(blockers=['REVIEW']), 'ready instance'),
            (lambda d: d['instances'][2].update(state='BLOCKED', blockers=[]), 'blocked instance'),
            (lambda d: d['instances'][2].update(blockers=['', 1]), 'invalid blockers'),
            (lambda d: d['instances'][2].update(mutation_paths='bad'), 'mutation paths'),
            (lambda d: d['instances'][2].update(owner_issue=True), 'owner issue'),
            (lambda d: d['instances'][2].update(root_id='!'), 'root id'),
        ]
        for modify, message in modifiers:
            data = sample()
            modify(data)
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                MOD.plan_instances(data, atlas())

    def test_canonical_atlas_negative_controls(self):
        mutations = [
            lambda d: d.update(sipoc=[{'key': 'P'}]),
            lambda d: d['lanes'].append({'not_id': 'missing'}),
            lambda d: d['lanes'][0].update(stages=[['bad', 'missing']]),
            lambda d: d['lanes'][0]['stages'].append(d['lanes'][0]['stages'][0]),
            lambda d: d.update(lanes=[]),
        ]
        for change in mutations:
            a = atlas()
            change(a)
            with self.subTest(change=change), self.assertRaises(ValueError):
                MOD.plan_instances(sample(), a)

    def test_global_and_repository_bounds_are_independent(self):
        data = sample()
        data['instances'].append(node('B5', dep=['I'], repo='GBOGEB/CODEX'))
        data['max_parallel'] = 3
        wave = MOD.plan_instances(data, atlas())['schedule']['waves'][2]
        self.assertEqual(len(wave), 3)
        self.assertEqual(sum(n['repo'] == 'GBOGEB/ABACUS' for n in wave), 2)
        self.assertEqual(sum(n['repo'] == 'GBOGEB/CODEX' for n in wave), 1)

    def test_next_pulse_feedback_rejects_unknown_target(self):
        data = sample()
        data['next_pulse_feedback'][0]['to_stage_ref'] = 'DMAIC:MAGIC'
        with self.assertRaisesRegex(ValueError, 'next pulse'):
            MOD.plan_instances(data, atlas())


if __name__ == '__main__':
    unittest.main()
