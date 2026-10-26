"""Source-bound *descriptive* run/job/attempt join for G3P telemetry.

Input is untrusted JSON until authenticated by a separate native GitHub reader.
Run or job symptoms never become causal roots or merge-admission credit.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from n3_continuation import digest, head, check

STATUSES = {'queued', 'in_progress', 'completed'}
CONCLUSIONS = {'success', 'failure', 'cancelled', 'skipped', 'timed_out', 'neutral', 'action_required'}


def stamp(value):
    check(isinstance(value, str), 'timestamp missing')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as error:
        raise ValueError('invalid timestamp') from error
    check(parsed.utcoffset() is not None, 'timezone required')
    return parsed


def integer(value):
    return type(value) is int and value > 0


def outcome(record):
    status, conclusion = record.get('status'), record.get('conclusion')
    check(status in STATUSES, 'bad native status')
    check((status == 'completed' and conclusion in CONCLUSIONS) or
          (status != 'completed' and conclusion is None), 'status/conclusion contradiction')


def project(source):
    check(isinstance(source, dict) and source.get('schema') == 'missioncontrol.native_ci_observations.v1',
          'native input schema mismatch')
    repo, sha = source.get('repository'), source.get('source_sha')
    check(repo == 'GBOGEB/pipeline-automation-hub' and head(sha), 'unbound native source')
    observed_at = stamp(source.get('observed_at'))
    runs = source.get('runs')
    check(isinstance(runs, list), 'native runs must be a list')
    seen_runs, seen_jobs, completed_runs, queued_runs, failures = set(), set(), set(), set(), []
    observed_jobs, declared_jobs, completed_jobs, observed_failed_steps = 0, 0, 0, 0
    completed_attempts, queued_attempts = 0, 0
    attempts, attempts_per_run = set(), {}
    for run in runs:
        check(isinstance(run, dict), 'invalid run')
        rid, attempt = run.get('run_id'), run.get('run_attempt')
        check(integer(rid) and integer(attempt) and (rid, attempt) not in attempts,
              'invalid or duplicate run identity/attempt')
        seen_runs.add(rid)
        attempts.add((rid, attempt))
        attempts_per_run.setdefault(rid, set()).add(attempt)
        check(run.get('head_sha') == sha, 'run head SHA drift')
        outcome(run)
        created = stamp(run.get('created_at'))
        started = stamp(run.get('run_started_at')) if run.get('run_started_at') else None
        check(created <= observed_at and (started is None or created <= started <= observed_at),
              'run time order drift')
        if run['status'] == 'queued':
            queued_runs.add(rid)
            queued_attempts += 1
            check(started is None, 'queued run cannot have a start time')
        if run['status'] == 'completed':
            completed_runs.add(rid)
            completed_attempts += 1
            check(started is not None, 'completed run without a start')
        jobs = run.get('jobs')
        total = run.get('job_total')
        check(isinstance(jobs, list) and type(total) is int and total >= len(jobs) >= 0,
              'invalid job observation denominator')
        observed_jobs += len(jobs)
        declared_jobs += total
        for job in jobs:
            check(isinstance(job, dict), 'invalid job record')
            jid = job.get('job_id')
            check(integer(jid) and jid not in seen_jobs, 'duplicate/invalid native job ID')
            seen_jobs.add(jid)
            check(job.get('head_sha') == sha and integer(job.get('run_id'))
                  and integer(job.get('run_attempt')) and job.get('run_id') == rid
                  and job.get('run_attempt') == attempt, 'job identity/head/run-attempt conflict')
            outcome(job)
            steps = job.get('failed_steps')
            check(isinstance(steps, list), 'missing failed-step census')
            if job['conclusion'] == 'failure':
                check(all(isinstance(s, dict) and integer(s.get('step_number'))
                          and isinstance(s.get('step_name'), str) and s['step_name'].strip() for s in steps),
                      'invalid failed-step identity')
                check(len(set(s['step_number'] for s in steps)) == len(steps), 'duplicate failed steps')
                observed_failed_steps += len(steps)
                failures.append({'run_id': rid, 'run_attempt': attempt,
                                 'job_id': jid, 'failed_step_count': len(steps),
                                 'causal_root': None})
            else:
                check(not steps, 'failed steps attached to nonfailed job')
            completed_jobs += int(job['status'] == 'completed')
    return {
        'schema': 'missioncontrol.native_ci_projection.v1',
        'source_digest': digest(source), 'repository': repo, 'source_sha': sha,
        'observation_scope': 'USER_SUPPLIED_UNAUTHENTICATED_NATIVE_SNAPSHOT',
        'observed_runs': len(seen_runs), 'completed_runs': len(completed_runs),
        'queued_runs': len(queued_runs), 'distinct_run_attempts': len(attempts),
        'completed_attempts': completed_attempts, 'queued_attempts': queued_attempts,
        'run_attempt_aliases': len(attempts) - len(seen_runs),
        'run_ids_with_multiple_observed_attempts': sum(
            len(v) > 1 for v in attempts_per_run.values()
        ),
        'attempt_history_complete': None,
        'observed_jobs': observed_jobs, 'declared_job_total': declared_jobs,
        'unobserved_job_slots': declared_jobs - observed_jobs,
        'completed_jobs': completed_jobs, 'observed_failed_steps': observed_failed_steps,
        'first_red_symptoms': failures,
        'native_exact_head_authenticated': False, 'causal_roots_confirmed': 0,
        'independent_run_trials': None, 'source_delivery_latency_ms': None,
        'merge_admission': 'HOLD', 'authority_transfer': False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('snapshot', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    result = project(json.loads(args.snapshot.read_text(encoding='utf-8')))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, sort_keys=True, indent=2) + '\n', encoding='utf-8', newline="\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
