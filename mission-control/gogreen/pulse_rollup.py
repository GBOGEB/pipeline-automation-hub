"""GOGREEN G4: deterministic per-wave evidence and bounded read-only scaling plan.

No worker dispatch, cross-repo mutation, inferred tests, statistical trials or admission.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path
from spine import build

SCHEMA = 'gogreen.pulse-rollup.v1'
SHA = re.compile(r'[0-9a-f]{40}\Z')


def _cells(evidence):
    return evidence['breadth']['observed_cells']


def _ratio(numerator, denominator):
    return round(100 * numerator / denominator, 2) if denominator > 0 else None


def _extract(fleet):
    evidence, plan, _ = build(fleet)
    return evidence, plan


def _validate_breadth(g0, g1):
    base = {r['repository']: (r['head_sha'], tuple(r['target_families'])) for r in g0['repositories']}
    current = {r['repository']: (r['head_sha'], tuple(r['target_families'])) for r in g1['repositories']}
    if base != current or len(g0['repositories']) != len(base):
        raise ValueError('source catalog/scope drift; unable to compare percentages')
    base_rows = {(r['repository'], r['run_id'], r['run_attempt'], r['job_id']): r for r in g0['observations']}
    curr_rows = {(r['repository'], r['run_id'], r['run_attempt'], r['job_id']): r for r in g1['observations']}
    if not all(key in curr_rows and curr_rows[key] == record for key, record in base_rows.items()):
        raise ValueError('G0 historical evidence removed or rewritten')


def bounded_schedule(catalog, evidence, *, workers=2, per_repo=1, packet_budget=12):
    """Plan disjoint repo/family scouts; never launch or mutate remote source."""
    for val, name in ((workers, 'workers'), (per_repo, 'per_repo'), (packet_budget, 'packet_budget')):
        if type(val) is not int or val < 1 or val > 64:
            raise ValueError(f'unsafe {name}')
    seen = {(r['repository'], r['family']) for r in evidence['observations']}
    choices = [(entry['repository'], family, entry['head_sha'])
               for entry in catalog for family in entry['target_families']
               if (entry['repository'], family) not in seen]
    weights = {'security': 0, 'coverage': 1, 'artifact': 2, 'runtime': 3,
               'ci_contract': 4, 'federation': 5, 'qps_triage': 6, 'math_model': 7}
    choices.sort(key=lambda c: (weights[c[1]], c[0]))
    lanes, left, covered_repos = [], list(choices), set()
    while left and len(lanes) < packet_budget:
        wave, used = [], set()
        deferred = []
        for repo, family, source_sha in left:
            if (len(wave) >= workers or repo in used or
                sum(1 for p in lanes if p['repository'] == repo) +
                sum(1 for p in wave if p['repository'] == repo) >= per_repo):
                deferred.append((repo, family, source_sha))
                continue
            used.add(repo)
            covered_repos.add(repo)
            wave.append({'repository': repo, 'family': family, 'source_sha': source_sha,
                         'mode': 'READ_ONLY_SCOUT', 'owner': 'GOGREEN-OBSERVER',
                         'mutation_paths': [], 'dispatch_authorized': False})
        if not wave:
            break
        lanes.extend(wave)
        left = deferred
    return {'contract': 'PLAN_ONLY', 'workers_max_parallel': workers,
            'per_repo_packet_limit': per_repo, 'packet_budget': packet_budget,
            'packets_planned': len(lanes), 'packets_remaining': len(choices) - len(lanes),
            'repositories_covered_by_plan': len(covered_repos), 'packets': lanes,
            'throughput_prediction': None, 'real_worker_capacity': None,
            'dispatch_authorized': False, 'authority_transfer': False}


def rollup(g0, g1, *, source_sha=None, workers=2, per_repo=1, packet_budget=12):
    if source_sha is not None and (not isinstance(source_sha, str) or not SHA.fullmatch(source_sha)):
        raise ValueError('exact source Git SHA required')
    _validate_breadth(g0, g1)
    before, _ = _extract(g0)
    after, _ = _extract(g1)
    b0, b1 = before['breadth'], after['breadth']
    if b0['catalog_repo_family_cells'] != b1['catalog_repo_family_cells']:
        raise ValueError('denominator drift')
    if _cells(after) < _cells(before):
        raise ValueError('observation regression')
    total = b1['catalog_repo_family_cells']
    wave0 = {'wave': 'G0', 'kind': 'INTEGRATED_HISTORICAL_BASELINE',
             'target_cells': total, 'observed_cells': _cells(before),
             'observed_pct': _ratio(_cells(before), total),
             'native_status_only': b0['native_green_status_only_observations'],
             'native_metadata': b0['native_green_metadata_observations'],
             'verified_archive_bytes': b0['native_green_bytes_verified_observations'],
             'test_counts': None, 'scope_coverage_gain_pp': None}
    wave1 = {'wave': 'G1', 'kind': 'SOURCE_BOUND_STATUS_ONLY_EXPANSION',
             'target_cells': total, 'observed_cells': _cells(after),
             'observed_pct': _ratio(_cells(after), total),
             'delta_observed_cells': _cells(after) - _cells(before),
             'unobserved_cells': b1['not_observed_cells'],
             'native_status_only': b1['native_green_status_only_observations'],
             'native_metadata': b1['native_green_metadata_observations'],
             'verified_archive_bytes': b1['native_green_bytes_verified_observations'],
             'test_counts': None, 'scope_coverage_gain_pp': None}
    plan = bounded_schedule(g1['repositories'], after, workers=workers,
                            per_repo=per_repo, packet_budget=packet_budget)
    return {'schema': SCHEMA, 'source_git_sha': source_sha, 'source_scope': 'SIX_REPO_FIXED_CATALOG',
            'waves': [wave0, wave1], 'scale_plan': plan,
            'measurement_boundaries': {
                'unobserved_is_not_failed': True,
                'status_only_is_not_tests': True,
                'status_only_is_not_byte_proof': True,
                'real_child_stress_capacity': None,
                'comparable_repo_coverage_gain': None,
                'independent_trial_count': None,
                'global_root_closure': None,
                'ci_queue_vs_setup_seconds': None},
            'qps_disposition': 'DEFER', 'merge_authorized': False,
            'security_waiver': False, 'authority_transfer': False}


def emit(report, out):
    out.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(report, sort_keys=True, indent=2) + '\n').encode()
    (out / 'pulse_rollup.json').write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    (out / 'pulse_rollup.sha256').write_text(digest + '\n', encoding='ascii')
    rows = report['waves']
    lines = ['# GOGREEN wave metrics', '',
             '| Wave | Cells | Observed | Breadth | Status only | Byte proofs | Comparable coverage |',
             '|---|---:|---:|---:|---:|---:|---|']
    for r in rows:
        lines.append(f"| {r['wave']} | {r['target_cells']} | {r['observed_cells']} | {r['observed_pct']:.2f}% | {r['native_status_only']} | {r['verified_archive_bytes']} | UNKNOWN |")
    lines += ['', 'Planned read-only packets: ' +
              str(report['scale_plan']['packets_planned']) + '; not yet planned: ' +
              str(report['scale_plan']['packets_remaining']) + '; concurrency ceiling: ' +
              str(report['scale_plan']['workers_max_parallel']) + '. No dispatch.',
              '', 'JSON SHA-256: ' + digest, '']
    (out / 'pulse_rollup.md').write_text('\n'.join(lines), encoding='utf-8')
    return digest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--g0', type=Path, required=True)
    p.add_argument('--g1', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--source-sha')
    p.add_argument('--workers', type=int, default=2)
    p.add_argument('--per-repo', type=int, default=1)
    p.add_argument('--packet-budget', type=int, default=12)
    a = p.parse_args()
    report = rollup(json.loads(a.g0.read_text()), json.loads(a.g1.read_text()),
                    source_sha=a.source_sha, workers=a.workers,
                    per_repo=a.per_repo, packet_budget=a.packet_budget)
    emit(report, a.out)
    print(json.dumps({'waves': report['waves'], 'scale_plan_count': report['scale_plan']['packets_planned']}))


if __name__ == '__main__':
    main()
