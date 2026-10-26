"""Strictly descriptive and deterministic Mission Control pulse telemetry.

No inferred effect size, pseudo-replicated trial, or synthetic native CI credit.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from n3_continuation import digest
from n3_integrity import inspect


def ratio(num: int, den: int):
    return {'numerator': num, 'denominator': den, 'fraction': round(num/den, 6) if den else None}


def collect(ledger: dict) -> dict:
    audit = inspect(ledger)
    if audit['issue_count']:
        raise ValueError('cannot publish metrics from invalid receipt evidence')
    rows = []
    for receipt in ledger['receipts']:
        tests = receipt['tests']
        action = receipt.get('action')
        rows.append({
            'ordinal': receipt['ordinal'],
            'pulse_id': receipt['pulse_id'],
            'output_source_sha_claim': receipt['output_source_sha'],
            'action_description': action if isinstance(action, str) else None,
            'declared_changed_path_count': len(set(receipt.get('changed_paths', []))),
            'test_provenance': tests['kind'],
            'locally_reported_tests_passed': tests['passed'] if tests['kind'] == 'LOCAL' else None,
            'locally_reported_tests_failed': tests['failed'] if tests['kind'] == 'LOCAL' else None,
            'native_exact_head_attested': False,
            'source_authentication_attested': False,
            'prediction_preissued': receipt.get('planned') is not None,
            'wall_time_measured': receipt.get('clock') is not None,
            'coverage_delta_pp_matched': receipt.get('coverage_delta') if receipt.get('coverage_matched') is True else None,
            'merge_admission': 'HOLD',
        })
    n = len(rows)
    local = [r for r in rows if r['test_provenance'] == 'LOCAL']
    metrics = {
        'pulse_receipts': n,
        'source_sha_claims': n,
        'described_actions': ratio(sum(r['action_description'] is not None for r in rows), n),
        'test_record_presence': ratio(n, n),
        'local_test_receipts': ratio(len(local), n),
        'native_attested_receipts': ratio(0, n),
        'authenticated_source_receipts': ratio(0, n),
        'preissued_predictions': ratio(sum(r['prediction_preissued'] for r in rows), n),
        'measured_wall_time': ratio(sum(r['wall_time_measured'] for r in rows), n),
        'matched_coverage_delta': ratio(sum(r['coverage_delta_pp_matched'] is not None for r in rows), n),
        'locally_reported_test_passes': sum(r['locally_reported_tests_passed'] or 0 for r in local),
        'locally_reported_test_failures': sum(r['locally_reported_tests_failed'] or 0 for r in local),
        'declared_changed_paths_sum': sum(r['declared_changed_path_count'] for r in rows),
        'unknown_evidence_fields': audit['unknown_count'],
        'measurement_completeness': ratio(sum(
            r['prediction_preissued'] + r['wall_time_measured'] +
            r['source_authentication_attested'] for r in rows), 3*n),
        'backlog_burndown': None,
        'matched_code_coverage_improvement_pp': None,
        'time_saved_ms': None,
        'first_red_closure_count': None,
        'independent_trials': None,
    }
    return {'schema': 'missioncontrol.n3_metrics.v1',
            'source_ledger_digest': digest(ledger),
            'audit_digest': digest(audit),
            'population': 'N3_LEDGER_RECEIPTS_NOT_INDEPENDENT_TRIALS',
            'scope': ledger['mission']['repo']+'::'+ledger['mission']['id'],
            'units': {'coverage':'percentage_points','time':'milliseconds',
                      'changed_paths':'per_pulse_nonunique_across_pulses',
                      'pulse_receipts':'receipts'},
            'metrics': metrics, 'pulses': rows,
            'statistical_inference': 'DEFER_NO_INDEPENDENT_COMPARABLE_TRIALS',
            'merge_admission': 'HOLD', 'authority_transfer': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('ledger', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    result = collect(json.loads(args.ledger.read_text(encoding='utf-8')))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, sort_keys=True, indent=2) + '\n', encoding='utf-8', newline="\n")
    print(json.dumps(result['metrics'], sort_keys=True))


if __name__ == '__main__':
    main()
