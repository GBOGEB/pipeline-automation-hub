#!/usr/bin/env python3
import argparse
import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def parse_ts(s):
    if not s:
        return None
    return datetime.fromisoformat(s.replace('Z', '+00:00'))


def get_json(url, token):
    req = urllib.request.Request(url)
    req.add_header('Accept', 'application/vnd.github+json')
    req.add_header('Authorization', f'Bearer {token}')
    req.add_header('X-GitHub-Api-Version', '2022-11-28')
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode('utf-8'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    token = os.environ.get('GITHUB_TOKEN', '')
    repo = os.environ.get('GITHUB_REPOSITORY', '')
    run_id = os.environ.get('GITHUB_RUN_ID', '')
    if not token or '/' not in repo or not run_id:
        raise SystemExit('FAIL: GITHUB_TOKEN/GITHUB_REPOSITORY/GITHUB_RUN_ID required')
    run = get_json(f'https://api.github.com/repos/{repo}/actions/runs/{run_id}', token)
    jobs = get_json(f'https://api.github.com/repos/{repo}/actions/runs/{run_id}/jobs?per_page=100', token).get('jobs', [])
    created = parse_ts(run.get('created_at'))
    rows = []
    for job in jobs:
        name = job.get('name', '')
        habitat = None
        low = name.lower()
        if 'linux' in low:
            habitat = 'linux'
        elif 'windows' in low:
            habitat = 'windows'
        if not habitat:
            continue
        started = parse_ts(job.get('started_at'))
        completed = parse_ts(job.get('completed_at'))
        queue_seconds = max(0.0, (started - created).total_seconds()) if created and started else None
        execute_seconds = max(0.0, (completed - started).total_seconds()) if started and completed else None
        rows.append({
            'habitat': habitat,
            'job_id': job.get('id'),
            'job_name': name,
            'status': job.get('status'),
            'conclusion': job.get('conclusion'),
            'run_created_at': run.get('created_at'),
            'job_started_at': job.get('started_at'),
            'job_completed_at': job.get('completed_at'),
            'queue_seconds_from_run_creation': queue_seconds,
            'job_execute_seconds': execute_seconds
        })
    out = {
        'schema': 'missioncontrol.crew_frontier_queue_telemetry.v1',
        'source_sha': run.get('head_sha'),
        'run_id': str(run_id),
        'captured_at': datetime.now(timezone.utc).isoformat(),
        'rows': sorted(rows, key=lambda x: (x['habitat'], x['job_id'] or 0)),
        'note': 'queue_seconds_from_run_creation is an admission-delay proxy, not GitHub internal scheduler queue time.'
    }
    Path(args.out).write_text(json.dumps(out, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({'status': 'PASS_FRONTIER_QUEUE_TELEMETRY', 'rows': len(rows), 'source_sha': out['source_sha']}, sort_keys=True))

if __name__ == '__main__':
    main()
