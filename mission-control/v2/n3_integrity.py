"""Read-only N3 ledger integrity and evidence-provenance diagnostics.

A SHA in a ledger is a claim, not GitHub authentication. Report missing proof
rather than upgrading SOURCE_COMMITTED or NATIVE_EXACT_HEAD to certified PASS.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from n3_continuation import digest, validate


def inspect(ledger: dict) -> dict:
    state = validate(ledger)
    issues = []
    unknowns = []
    identity_seen = set()
    claims = ledger['receipts']
    for r in claims:
        number = r['ordinal']
        changed = r.get('changed_paths', [])
        if len(set(changed)) != len(changed):
            issues.append(f'PULSE-{number}:DUPLICATE_CHANGED_PATH')
        if r['pulse_id'] in identity_seen:
            issues.append(f'PULSE-{number}:DUPLICATE_PULSE_ID')
        identity_seen.add(r['pulse_id'])
        delta = r.get('coverage_delta')
        if delta is not None and (not isinstance(delta, (float, int))
                                  or isinstance(delta, bool)
                                  or not math.isfinite(delta) or not -100 <= delta <= 100):
            issues.append(f'PULSE-{number}:INVALID_COVERAGE_DELTA')
        if r.get('coverage_matched') is True and delta is not None:
            comparison = r.get('coverage_comparison')
            if not isinstance(comparison, dict) or not all(
                    type(comparison.get(k)) is int and comparison[k] > 0
                    for k in ('baseline_eligible', 'actual_eligible')):
                issues.append(f'PULSE-{number}:COVERAGE_DENOMINATOR_UNBOUND')
        tests = r['tests']
        if tests['kind'] == 'NATIVE_EXACT_HEAD':
            source = tests.get('native_evidence')
            if not isinstance(source, dict) or not all(source.get(k) for k in
                    ('workflow_run_id', 'run_attempt', 'artifact_sha256')) or not (
                    type(source.get('workflow_run_id')) is int
                    and type(source.get('run_attempt')) is int
                    and source['workflow_run_id'] > 0
                    and source['run_attempt'] > 0
                    and isinstance(source['artifact_sha256'], str)
                    and len(source['artifact_sha256']) == 64):
                issues.append(f'PULSE-{number}:UNBOUND_NATIVE_PROOF')
        evidence = r.get('source_evidence')
        if evidence is None:
            unknowns.append(f'PULSE-{number}:SOURCE_AUTHENTICATION_UNBOUND')
        elif not isinstance(evidence, dict) or (
                evidence.get('source_sha') != r['output_source_sha'] or
                evidence.get('class') not in ('GITHUB_COMMIT', 'INDEPENDENT_RECEIPT') or
                not isinstance(evidence.get('locator'), str) or
                not evidence.get('locator')):
            issues.append(f'PULSE-{number}:CONTRADICTORY_SOURCE_PROOF')
        if r.get('planned') is None:
            unknowns.append(f'PULSE-{number}:PREDICTION_BEFORE_ACTION_UNBOUND')
        if r.get('clock') is None:
            unknowns.append(f'PULSE-{number}:WALL_TIME_UNBOUND')
    return {
        'schema': 'missioncontrol.n3_integrity_audit.v1',
        'input_digest': digest(ledger),
        'source_validation': state['disposition'],
        'structural_status': 'FAIL' if issues else 'PASS_WITH_UNKNOWNS' if unknowns else 'PASS',
        'issue_count': len(issues), 'issues': sorted(issues),
        'unknown_count': len(unknowns), 'unknowns': sorted(unknowns),
        'pulse_count': len(claims), 'native_proof_promoted': False,
        'merge_admission': 'HOLD', 'authority_transfer': False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('ledger', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    result = inspect(json.loads(args.ledger.read_text(encoding='utf-8')))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(result, sort_keys=True))
    return 1 if result['issue_count'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
