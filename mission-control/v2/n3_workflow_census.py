"""Fail-closed descriptive GitHub workflow/run/job observation telemetry.

The input is a source-bound readback *claim*, not an independently signed
native CI proof. Do not upgrade workflows/queued jobs to release admission.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from datetime import datetime
from pathlib import Path

# Nearest-rank percentile is owned by gogreen/bd_queue_wave.py; import, never copy.
_BD_QUEUE_WAVE = Path(__file__).resolve().parents[1] / 'gogreen' / 'bd_queue_wave.py'
_spec = importlib.util.spec_from_file_location('n3_workflow_census_bd_queue_wave', _BD_QUEUE_WAVE)
bd_queue_wave = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bd_queue_wave)

SHA = re.compile(r'[0-9a-f]{40}\Z')
RUN_STATUS = {'queued', 'pending', 'waiting', 'requested', 'in_progress', 'completed'}
JOB_CONCLUSION = {'success', 'failure', 'cancelled', 'skipped', 'timed_out', 'neutral', 'action_required', 'stale'}
RUN_CONCLUSION = JOB_CONCLUSION | {'startup_failure'}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def timestamp(value):
    if value is None:
        return None
    require(isinstance(value, str) and value, 'invalid time type')
    try:
        out = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError('invalid time value') from exc
    require(out.utcoffset() is not None, 'timezone required for time metrics')
    return out


def state(record, conclusions=JOB_CONCLUSION):
    status, conclusion = record.get('status'), record.get('conclusion')
    require(status in RUN_STATUS, 'unknown workflow/job status')
    if status == 'completed':
        require(conclusion in conclusions, 'inconsistent terminal status/conclusion')
    else:
        require(conclusion is None, 'inconsistent terminal status/conclusion')
    return status


def metric(num, den):
    return {'numerator': num, 'denominator': den, 'pct': round(100*num/den, 4) if den else None}


def p95(values):
    # Nearest rank is descriptive only; do not imply independent observations.
    return bd_queue_wave.percentile(values, .95)


def project(snapshot):
    require(isinstance(snapshot, dict) and snapshot.get('schema') == 'missioncontrol.github_workflow_census.v1',
            'workflow census schema mismatch')
    repo = snapshot.get('repository')
    sha = snapshot.get('source_sha')
    require(repo == 'GBOGEB/pipeline-automation-hub' and isinstance(sha, str) and SHA.fullmatch(sha),
            'source repository/SHA mismatch')
    require(snapshot.get('retrieval_scope') == 'FIRST_PAGE_PR_HEAD', 'uncertified population scope')
    runs = snapshot.get('workflow_runs')
    require(isinstance(runs, list), 'workflow_runs must be a list')
    checked = snapshot.get('artifact_check_run_ids', [])
    require(isinstance(checked, list) and len(checked) == len(set(checked)), 'duplicate artifact checks')
    seen_runs, seen_jobs = set(), set()
    terminal, queued, in_progress, success, failed, attempts_known = 0, 0, 0, 0, 0, 0
    jobs_seen, jobs_completed, jobs_queued, jobs_total_known, jobs_total_censored = 0, 0, 0, 0, 0
    job_attempts_bound = 0
    queue_samples, execution_samples, artifact_checked = [], [], 0
    summaries = []
    for r in runs:
        require(isinstance(r, dict), 'invalid workflow record')
        rid = r.get('run_id')
        require(type(rid) is int and rid > 0 and rid not in seen_runs, 'invalid/duplicate workflow ID')
        seen_runs.add(rid)
        require(r.get('head_sha') == sha, 'workflow exact-head mismatch')
        require(isinstance(r.get('name'), str) and r['name'].strip(), 'workflow name missing')
        status = state(r, RUN_CONCLUSION)
        attempt = r.get('run_attempt')
        require(attempt is None or (type(attempt) is int and attempt > 0), 'run attempt invalid')
        attempts_known += (attempt is not None)
        start = timestamp(r.get('started_at'))
        created = timestamp(r.get('created_at'))
        finished = timestamp(r.get('completed_at'))
        require(not (created and start and created > start), 'run start precedes creation')
        require(not (start and finished and start > finished), 'run completion precedes start')
        require(status != 'queued' or start is None, 'queued run falsely started')
        require(status == 'completed' or finished is None, 'nonterminal run falsely completed')
        if created is not None and start is not None:
            queue_samples.append(round((start - created).total_seconds() * 1000))
        if start is not None and finished is not None:
            execution_samples.append(round((finished - start).total_seconds() * 1000))
        terminal += status == 'completed'
        queued += status in ('queued', 'pending', 'waiting', 'requested')
        in_progress += status == 'in_progress'
        success += r.get('conclusion') == 'success'
        failed += r.get('conclusion') in {'failure', 'timed_out', 'startup_failure'}
        jobs = r.get('jobs')
        require(jobs is None or isinstance(jobs, list), 'jobs must be list or unknown')
        reported = r.get('reported_job_total')
        require(reported is None or (type(reported) is int and reported >= (len(jobs) if jobs else 0)),
                'invalid declared job total')
        if reported is not None:
            jobs_total_known += reported
        else:
            jobs_total_censored += 1
        if jobs is not None:
            job_attempts = []
            for j in jobs:
                require(isinstance(j, dict), 'invalid job')
                jid = j.get('job_id')
                require(type(jid) is int and jid > 0 and jid not in seen_jobs, 'duplicate/invalid job')
                seen_jobs.add(jid)
                require(j.get('run_id') == rid and j.get('head_sha') == sha, 'job run/head mismatch')
                job_attempt = j.get('run_attempt')
                require(job_attempt is None or (type(job_attempt) is int and job_attempt > 0),
                        'job run attempt invalid')
                if attempt is not None and job_attempt is not None:
                    require(job_attempt == attempt, 'job run-attempt mismatch')
                attempt_binding = 'MATCHED' if attempt is not None and job_attempt is not None else 'UNKNOWN'
                job_attempts_bound += attempt_binding == 'MATCHED'
                job_attempts.append({'job_id':jid, 'run_attempt':job_attempt,
                                     'attempt_binding':attempt_binding})
                js = state(j)
                jobs_seen += 1
                jobs_completed += js == 'completed'
                jobs_queued += js in ('queued', 'pending', 'waiting', 'requested')
        artifact_count = r.get('artifact_count')
        if rid in checked:
            require(type(artifact_count) is int and artifact_count >= 0, 'checked artifact count missing')
            artifact_checked += 1
        else:
            require(artifact_count is None, 'uncorroborated artifact count')
        summaries.append({'id':rid, 'name':r['name'], 'status':status,
                          'conclusion':r.get('conclusion'), 'run_attempt':attempt,
                          'observed_jobs':len(jobs) if jobs is not None else None,
                          'job_attempts':job_attempts if jobs is not None else None,
                          'reported_job_total':reported,
                          'artifact_count_if_checked':artifact_count})
    require(set(checked) <= seen_runs, 'artifact check does not belong to observed runs')
    return {'schema':'missioncontrol.github_workflow_telemetry.v1',
            'source_sha':sha, 'repository':repo,
            'observation_class':'GITHUB_CONNECTOR_READBACK_UNATTESTED_ARTIFACT',
            'population':'PR_HEAD_FIRST_PAGE_NOT_ENTIRE_REPOSITORY',
            'metrics':{
                'workflow_runs_observed':len(runs),
                'queued_or_pending_workflows':metric(queued,len(runs)),
                'terminal_workflows':metric(terminal,len(runs)),
                'successful_terminal_workflows':metric(success,terminal),
                'failed_terminal_workflows':metric(failed,terminal),
                'running_workflows':in_progress,
                'known_run_attempts':metric(attempts_known,len(runs)),
                'observed_jobs':jobs_seen,
                'known_job_attempt_bindings':metric(job_attempts_bound,jobs_seen),
                'observed_queued_jobs':jobs_queued,
                'observed_completed_jobs':jobs_completed,
                'reported_total_jobs_for_known_runs':jobs_total_known if jobs_total_censored == 0 else None,
                'runs_with_unknown_job_denominator':jobs_total_censored,
                'observed_artifact_checks':artifact_checked,
                'unchecked_artifact_runs':len(runs)-artifact_checked,
                'queue_latency_p95_ms':p95(queue_samples),
                'queue_latency_sample_count':len(queue_samples),
                'run_duration_p95_ms':p95(execution_samples),
                'run_duration_sample_count':len(execution_samples),
                'causal_root_closures':None,
                'matched_coverage_delta':None,
            },
            'workflows':summaries,
            'native_exact_head_pass':False,
            'merge_admission':'HOLD',
            'authority_transfer':False}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('snapshot',type=Path)
    ap.add_argument('--out',type=Path)
    args=ap.parse_args()
    result=project(json.loads(args.snapshot.read_text(encoding='utf-8')))
    if args.out:
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result['metrics'],sort_keys=True))


if __name__=='__main__':
    main()
