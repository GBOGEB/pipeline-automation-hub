"""Mission Control reader for ABACUS's canonical, source-bound CI telemetry.

Never collect a root ledger, reimplement gg_MATH, or grant acceptance.
A hash of supplied bytes proves local reproducibility, not GitHub authenticity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path

SCHEMA = 'abacus.mip.ci-wave-telemetry.v2'
OUT = 'code-purple.mc.abacus-mip-consumer.v1'
SHA40 = re.compile(r'[0-9a-f]{40}\Z')
SHA64 = re.compile(r'[0-9a-f]{64}\Z')
OUTCOMES = {'success', 'failure', 'neutral', 'cancelled', 'skipped', 'timed_out',
            'action_required', 'stale', 'startup_failure'}


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def count(x):
    return type(x) is int and x >= 0


def percent(num, denom):
    return round(100 * num / denom, 3) if denom else None


def validate(projection, expected_sha):
    require(isinstance(expected_sha, str) and SHA40.fullmatch(expected_sha),
            'exact source SHA required')
    require(isinstance(projection, dict) and projection.get('schema') == SCHEMA
            and projection.get('repository') == 'GBOGEB/ABACUS'
            and projection.get('source_sha') == expected_sha,
            'canonical producer/schema/exact SHA mismatch')
    require(projection.get('authority_transfer') is False
            and projection.get('merge_authorized') is False
            and projection.get('security_waiver') is False
            and projection.get('distinct_bd_roots_closed') is None
            and projection.get('first_red_causal_roots_verified') is None
            and projection.get('rex_receipts_accepted') is None,
            'unsupported evidence promotion')
    gates = projection.get('independent_gates')
    require(isinstance(gates, dict) and gates.get('admission') == 'HOLD'
            and gates.get('merge_authorized') is False,
            'independent gates may not be promoted')

    n = projection.get('workflow_records_observed')
    o = projection.get('workflow_terminal_by_outcome')
    pending = projection.get('workflow_nonterminal')
    unclassified = projection.get('workflow_unclassified')
    require(count(n) and isinstance(o, dict) and set(o) == OUTCOMES
            and all(count(v) for v in o.values()) and count(pending)
            and count(unclassified) and sum(o.values()) + pending + unclassified == n,
            'workflow outcome denominator does not reconcile')
    jobs = projection.get('jobs_observed')
    samples = projection.get('queue_samples')
    sources = projection.get('queue_source_counts')
    require(count(jobs) and count(samples) and samples <= jobs
            and isinstance(sources, dict) and set(sources) == {
                'job_created_at', 'workflow_run_created_at_fallback'
            } and all(count(x) for x in sources.values())
            and sum(sources.values()) == samples,
            'job queue provenance does not reconcile')
    p95 = projection.get('queue_seconds_p95')
    require((p95 is None if samples == 0 else
             type(p95) in (int, float) and math.isfinite(p95) and p95 >= 0),
            'queue p95 missing or invalid')
    manifestations = projection.get('first_red_manifestations')
    signatures = projection.get('first_red_signatures')
    require(isinstance(manifestations, list) and isinstance(signatures, list),
            'canonical first-red evidence missing')
    counted = {}
    keys = set()
    for event in manifestations:
        require(isinstance(event, dict), 'invalid first-red event')
        fp = event.get('fingerprint')
        semantic = {k: event.get(k) for k in (
            'workflow_path', 'job_name', 'step_name', 'step_number'
        )}
        require(isinstance(fp, str) and SHA64.fullmatch(fp)
                and all(isinstance(semantic[k], str) and semantic[k]
                        for k in ('workflow_path', 'job_name', 'step_name'))
                and type(semantic['step_number']) is int
                and semantic['step_number'] > 0
                and all(type(event.get(k)) is int and event[k] > 0
                        for k in ('run_id', 'run_attempt', 'job_id')),
                'unbound first-red identity')
        identity = tuple(event[k] for k in ('run_id', 'run_attempt', 'job_id'))
        require(identity not in keys, 'repeated native job identity')
        keys.add(identity)
        calculated = hashlib.sha256(json.dumps(
            semantic, sort_keys=True, separators=(',', ':')
        ).encode('utf-8')).hexdigest()
        require(fp == calculated, 'first-red signature content mismatch')
        counted[fp] = counted.get(fp, 0) + 1
    signature_ids = set()
    for row in signatures:
        require(isinstance(row, dict) and row.get('fingerprint') in counted,
                'signature without native manifestation')
        fp = row['fingerprint']
        require(fp not in signature_ids and count(row.get('manifestations'))
                and row['manifestations'] == counted[fp],
                'first-red signature count mismatch')
        signature_ids.add(fp)
    unbound = projection.get('red_jobs_without_attributed_first_step')
    require(signature_ids == set(counted)
            and projection.get('first_red_unique_signatures') == len(counted)
            and projection.get('first_red_repeated_signatures') == sum(
                n > 1 for n in counted.values())
            and count(unbound) and len(manifestations) + unbound <= jobs,
            'first-red total/unknown denominator invalid')
    return {'n': n, 'outcomes': o, 'pending': pending,
            'unclassified': unclassified, 'jobs': jobs,
            'queue_samples': samples, 'queue_native': sources['job_created_at'],
            'queue_fallback': sources['workflow_run_created_at_fallback'],
            'queue_p95': p95, 'counts': counted, 'unbound': unbound,
            'first_red': signatures}


def project(projection, expected_sha, *, input_sha256):
    stats = validate(projection, expected_sha)
    require(isinstance(input_sha256, str) and SHA64.fullmatch(input_sha256),
            'input byte SHA-256 required')
    n, outcomes = stats['n'], stats['outcomes']
    terminal = sum(outcomes.values())
    fully_observed = terminal == n and n > 0
    clock_native_only = (stats['queue_fallback'] == 0 and
                         stats['queue_samples'] >= 20)
    queue_eligible = fully_observed and clock_native_only
    return {
        'schema': OUT, 'upstream_schema': SCHEMA,
        'upstream_repository': 'GBOGEB/ABACUS', 'source_sha': expected_sha,
        'upstream_input_sha256': input_sha256,
        'byte_custody': 'LOCAL_RECOMPUTED_NOT_NATIVE_ARTIFACT_AUTHENTICATED',
        'metrics': {
            'workflow_records': n, 'workflow_success': outcomes['success'],
            'workflow_failure': outcomes['failure'],
            'workflow_cancelled': outcomes['cancelled'],
            'workflow_terminal': terminal,
            'workflow_pending_or_unclassified': stats['pending']+stats['unclassified'],
            'success_share_of_observed_pct': percent(outcomes['success'], n),
            'success_share_of_terminal_pct': percent(outcomes['success'], terminal),
            'jobs_observed': stats['jobs'],
            'first_red_manifestations_attributed': sum(stats['counts'].values()),
            'first_red_signature_types': len(stats['counts']),
            'first_red_repeated_signature_types': sum(x > 1 for x in stats['counts'].values()),
            'first_red_unattributed_jobs': stats['unbound'],
            'queue_samples': stats['queue_samples'],
            'queue_native_timestamp_samples': stats['queue_native'],
            'queue_fallback_timestamp_samples': stats['queue_fallback'],
            'queue_native_timestamp_share_pct': percent(
                stats['queue_native'], stats['queue_samples']),
            'queue_p95_seconds_observed': stats['queue_p95'],
            'queue_p95_native_clock_and_sample_gate': queue_eligible,
            'queue_p95_cross_wave_comparison_admitted': False,
        },
        'first_red_signatures_readonly': sorted(
            stats['first_red'], key=lambda row: (-row['manifestations'], row['fingerprint'])),
        'statistics': {
            'method_provider': 'GBOGEB/gg_MATH',
            'reference_kernels_not_copied': True,
            'pca': {'status': 'HOLD', 'explained_variance_pct': None,
                    'reason': 'no verified independent matched multivariate wave matrix'},
            'bradley_terry': {'status': 'HOLD', 'win_probability_pct': None,
                              'reason': 'no connected independently compared repair graph'},
            'anova': {'status': 'HOLD', 'p_value': None,
                      'reason': 'no independently replicated matched factor groups'},
            'manova': {'status': 'HOLD', 'p_value': None,
                       'reason': 'no identifiable multivariate group/residual geometry'},
            'intervals_90_95_99': {str(level): None for level in (90, 95, 99)},
            'interval_method': 'NOT_ESTIMATED',
            'interval_reason': 'workflow/job/step manifestations are dependent; independent process trials unproven',
        },
        'root_closures_verified': None,
        'independent_review_admitted': None,
        'rex_accepted': None,
        'qps_acceptance': 'DEFER',
        'merge_admission': 'HOLD',
        'authority_transfer': False, 'security_waiver': False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--projection', required=True, type=Path)
    parser.add_argument('--source-sha', required=True)
    parser.add_argument('--output', required=True, type=Path)
    a = parser.parse_args(argv)
    require(a.projection.resolve() != a.output.resolve(), 'input output alias')
    require(a.projection.is_file() and not a.projection.is_symlink()
            and 0 < a.projection.stat().st_size < 10_000_000, 'unsafe input file')
    raw = a.projection.read_bytes()
    result = project(json.loads(raw), a.source_sha,
                     input_sha256=hashlib.sha256(raw).hexdigest())
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, sort_keys=True, indent=2)+'\n', encoding='utf-8')
    print('supporting_projection_sha256='+hashlib.sha256(a.output.read_bytes()).hexdigest())
    print('merge_admission='+result['merge_admission'])


if __name__ == '__main__':
    main()
