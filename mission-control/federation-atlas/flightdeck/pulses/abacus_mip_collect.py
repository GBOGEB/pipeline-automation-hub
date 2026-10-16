"""Acquire GitHub native run/job/attempts; ABACUS remains the metric producer.

Only a bounded, complete pull_request source-SHA cohort is emitted.
Uses the existing Mission Control GitHub read-only transport.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

REPOSITORY = 'GBOGEB/ABACUS'
HEX40 = re.compile(r'[0-9a-f]{40}\Z')
MAX_RUNS = 50
MAX_JOB_PAGES = 10


def require(value, message):
    if not value:
        raise ValueError(message)


def gh_api(repo, path):
    """Use GitHub's authenticated API client, never a shell or arbitrary host."""
    require(repo == REPOSITORY and isinstance(path, str),
            'unexpected native GitHub repository')
    allowed = (
        r'/actions/runs\?head_sha=[0-9a-f]{40}&event=pull_request&per_page=100&page=1',
        r'/actions/runs/[1-9][0-9]*',
        r'/actions/runs/[1-9][0-9]*/attempts/[1-9][0-9]*/jobs\?per_page=100&page=[1-9][0-9]*'
    )
    require(any(re.fullmatch(pattern, path) for pattern in allowed),
            'unsupported native GitHub endpoint')
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    require(bool(token), 'read-only GitHub Actions token required')
    env = dict(os.environ, GH_TOKEN=token)
    command = ['gh', 'api', '--method', 'GET', '/repos/'+REPOSITORY+path]
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                timeout=30, env=env, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError('native GitHub API unavailable') from exc
    require(result.returncode == 0 and 0 < len(result.stdout) <= 8_000_000,
            'native GitHub response unavailable or oversized')
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError('native GitHub response is not JSON') from exc


def acquire(sha, getter):
    require(isinstance(sha, str) and HEX40.fullmatch(sha), 'exact SHA required')
    params = f'/actions/runs?head_sha={sha}&event=pull_request&per_page=100&page=1'
    page = getter(REPOSITORY, params)
    require(isinstance(page, dict)
            and type(page.get('total_count')) is int
            and 0 < page['total_count'] <= MAX_RUNS
            and isinstance(page.get('workflow_runs'), list)
            and len(page['workflow_runs']) == page['total_count'],
            'complete bounded native run population required')
    selection = sorted(page['workflow_runs'], key=lambda r: r.get('id', 0))
    run_ids = set()
    native_runs, jobs = [], []
    for item in selection:
        rid, attempt = item.get('id'), item.get('run_attempt')
        require(type(rid) is int and rid > 0
                and type(attempt) is int and attempt > 0
                and rid not in run_ids and item.get('head_sha') == sha
                and item.get('event') == 'pull_request',
                'source run identity mismatch')
        run_ids.add(rid)
        run = getter(REPOSITORY, f'/actions/runs/{rid}')
        require(isinstance(run, dict) and run.get('id') == rid
                and run.get('head_sha') == sha
                and run.get('run_attempt') == attempt
                and run.get('event') == 'pull_request',
                'run drift during acquisition')
        native_runs.append({k: run.get(k) for k in (
            'id', 'run_attempt', 'head_sha', 'name', 'path',
            'html_url', 'created_at', 'status', 'conclusion'
        )})
        seen_jobs, expected, group = set(), None, []
        for number in range(1, MAX_JOB_PAGES + 1):
            path = (f'/actions/runs/{rid}/attempts/{attempt}/jobs'
                    f'?per_page=100&page={number}')
            results = getter(REPOSITORY, path)
            require(isinstance(results, dict)
                    and type(results.get('total_count')) is int
                    and results['total_count'] >= 0
                    and isinstance(results.get('jobs'), list),
                    'invalid job page')
            if expected is None:
                expected = results['total_count']
                require(expected <= 100*MAX_JOB_PAGES, 'unbounded job pagination')
            require(results['total_count'] == expected
                    and len(results['jobs']) <= 100,
                    'job pagination drift')
            for job in results['jobs']:
                require(isinstance(job, dict) and type(job.get('id')) is int
                        and job['id'] > 0 and job['id'] not in seen_jobs
                        and job.get('run_id') == rid
                        and job.get('run_attempt') == attempt
                        and job.get('head_sha') == sha,
                        'job/run/attempt source mismatch')
                seen_jobs.add(job['id'])
                selected = {k: job.get(k) for k in (
                    'id','run_id','run_attempt','head_sha','name','status','conclusion',
                    'created_at','started_at','completed_at',
                )}
                if 'runner_id' in job:
                    selected['runner_id'] = job['runner_id']
                if 'steps' in job:
                    selected['steps'] = job['steps']
                group.append(selected)
            if len(group) == expected:
                break
            require(results['jobs'], 'short job page')
        require(len(group) == expected, 'native attempt jobs incomplete')
        jobs.extend(group)
    return {'source_sha': sha, 'repository': REPOSITORY,
            'runs': native_runs, 'jobs': jobs,
            'acquisition': 'github-actions-rest-exact-pull-request-cohort',
            'census_complete': True, 'run_attempts_observed': len(native_runs)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-sha', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    result = acquire(args.source_sha, gh_api)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True)+'\n',
                           encoding='utf-8')
    print('native_cohort_sha256='+hashlib.sha256(args.output.read_bytes()).hexdigest())
    print('native_runs='+str(len(result['runs'])))


if __name__ == '__main__':
    main()
