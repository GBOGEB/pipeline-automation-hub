#!/usr/bin/env python3
import argparse
import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def parse_ts(value):
    if not value:
        return None
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def get_json(url, token):
    req = urllib.request.Request(url)
    req.add_header('Accept', 'application/vnd.github+json')
    req.add_header('Authorization', f'Bearer {token}')
    req.add_header('X-GitHub-Api-Version', '2022-11-28')
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode('utf-8'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    token = os.environ.get('GITHUB_TOKEN', '')
    repo = os.environ.get('GITHUB_REPOSITORY', '')
    run_id = os.environ.get('GITHUB_RUN_ID', '')
    if not token or '/' not in repo or not run_id:
        raise SystemExit('FAIL GITHUB_TOKEN/GITHUB_REPOSITORY/GITHUB_RUN_ID required')

    run = get_json(f'https://api.github.com/repos/{repo}/actions/runs/{run_id}', token)
    jobs = get_json(f'https://api.github.com/repos/{repo}/actions/runs/{run_id}/jobs?per_page=100', token).get('jobs', [])
    created = parse_ts(run.get('created_at'))
    gate = next((j for j in jobs if j.get('name') == 'held-admission-gate'), None)
    gate_completed = parse_ts(gate.get('completed_at')) if gate else None
    rows = []

    for job in jobs:
        name = job.get('name', '')
        low = name.lower()
        if not low.startswith('collect-'):
            continue
        habitat = next((h for h in ('linux', 'windows', 'macos') if h in low), None)
        lane = 'held' if 'held' in low else ('baseline' if 'baseline' in low else None)
        if not habitat or not lane:
            continue
        started = parse_ts(job.get('started_at'))
        completed = parse_ts(job.get('completed_at'))
        admission = max(0.0, (started - created).total_seconds()) if created and started else None
        execute = max(0.0, (completed - started).total_seconds()) if started and completed else None
        post_gate = max(0.0, (started - gate_completed).total_seconds()) if lane == 'held' and started and gate_completed else None
        rows.append({
            'cell_id': f'{habitat}-{lane}',
            'habitat': habitat,
            'lane': lane,
            'job_id': job.get('id'),
            'job_name': name,
            'status': job.get('status'),
            'conclusion': job.get('conclusion'),
            'runner_name': job.get('runner_name'),
            'runner_group_name': job.get('runner_group_name'),
            'runner_labels': job.get('labels', []),
            'run_created_at': run.get('created_at'),
            'job_started_at': job.get('started_at'),
            'job_completed_at': job.get('completed_at'),
            'admission_proxy_seconds_from_run_creation': admission,
            'post_gate_admission_seconds': post_gate,
            'job_execute_seconds': execute,
            'designed_gate_wait_seconds': 8.0 if lane == 'held' else 0.0
        })

    expected = {f'{h}-{l}' for h in ('linux', 'windows', 'macos') for l in ('baseline', 'held')}
    actual = {r['cell_id'] for r in rows}
    if actual != expected:
        raise SystemExit(f'FAIL PC3 queue cells actual={sorted(actual)} expected={sorted(expected)}')
    if any(r['conclusion'] != 'success' for r in rows):
        raise SystemExit('FAIL one or more PC3 collection cells not successful')

    out = {
        'schema': 'missioncontrol.crew_frontier_pc3_admission_telemetry.v2',
        'source_sha': run.get('head_sha'),
        'run_id': str(run_id),
        'captured_at': datetime.now(timezone.utc).isoformat(),
        'held_gate': {
            'job_id': gate.get('id') if gate else None,
            'started_at': gate.get('started_at') if gate else None,
            'completed_at': gate.get('completed_at') if gate else None,
            'designed_wait_seconds': 8.0
        },
        'rows': sorted(rows, key=lambda x: x['cell_id']),
        'measurement_contract': {
            'admission_proxy_seconds_from_run_creation': 'Observed run-created to job-start delay. Includes deliberate held-lane dependency and scheduler/runner admission effects; it is not labeled as pure GitHub scheduler queue time.',
            'post_gate_admission_seconds': 'Observed delay from completion of held-admission-gate to held collector start.',
            'designed_gate_wait_seconds': 'Experimentally imposed dependency gate only; not a measured scheduler delay.'
        }
    }
    Path(args.out).write_text(json.dumps(out, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({'status': 'PASS_PC3_ADMISSION_TELEMETRY', 'cells': len(rows), 'source_sha': out['source_sha']}, sort_keys=True))

if __name__ == '__main__':
    main()
