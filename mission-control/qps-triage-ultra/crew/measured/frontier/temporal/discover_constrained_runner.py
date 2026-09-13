#!/usr/bin/env python3
import argparse
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def get_json(url, token):
    req = urllib.request.Request(url)
    req.add_header('Accept', 'application/vnd.github+json')
    req.add_header('Authorization', f'Bearer {token}')
    req.add_header('X-GitHub-Api-Version', '2022-11-28')
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode('utf-8'))


def write_output(enabled, labels, habitat):
    output = os.environ.get('GITHUB_OUTPUT')
    if not output:
        return
    with open(output, 'a', encoding='utf-8') as fh:
        fh.write(f'enabled={str(enabled).lower()}\n')
        fh.write('labels=' + json.dumps(labels, separators=(',', ':')) + '\n')
        fh.write(f'habitat={habitat}\n')


def normalize_habitat(os_name):
    value = str(os_name or '').strip().lower()
    if value == 'linux':
        return 'linux'
    if value == 'windows':
        return 'windows'
    if value in {'macos', 'osx'}:
        return 'macos'
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    repo = os.environ.get('GITHUB_REPOSITORY', '')
    token = os.environ.get('GITHUB_TOKEN', '')
    declared_raw = os.environ.get('MC_CONSTRAINED_RUNNER_LABELS_JSON', '').strip()
    receipt = {
        'schema': 'missioncontrol.constrained_runner_discovery.v1',
        'captured_at': datetime.now(timezone.utc).isoformat(),
        'repository': repo,
        'authority_transfer': False,
        'eligible_for_policy_only_after_real_assignment': True,
        'enabled': False,
        'declared_labels': [],
        'matched_runner': None,
        'habitat': None,
        'status': 'DEFERRED_NO_DECLARED_CONSTRAINED_RUNNER'
    }
    labels = ['self-hosted']
    habitat = 'linux'
    if declared_raw:
        try:
            labels = json.loads(declared_raw)
            if not isinstance(labels, list) or not labels or any(not isinstance(x, str) or not x for x in labels):
                raise ValueError('labels must be non-empty string list')
            if 'self-hosted' not in labels:
                raise ValueError('self-hosted label required')
            receipt['declared_labels'] = labels
            if not token or '/' not in repo:
                receipt['status'] = 'DEFERRED_RUNNER_DISCOVERY_CONTEXT_UNAVAILABLE'
            else:
                try:
                    payload = get_json(f'https://api.github.com/repos/{repo}/actions/runners?per_page=100', token)
                    runners = payload.get('runners', [])
                    wanted = set(labels)
                    matches = []
                    for runner in runners:
                        have = {x.get('name') for x in runner.get('labels', []) if x.get('name')}
                        if wanted.issubset(have) and runner.get('status') == 'online':
                            matches.append(runner)
                    if matches:
                        chosen = sorted(matches, key=lambda r: (bool(r.get('busy')), str(r.get('name'))))[0]
                        habitat = normalize_habitat(chosen.get('os'))
                        receipt['matched_runner'] = {
                            'id': chosen.get('id'),
                            'name': chosen.get('name'),
                            'os': chosen.get('os'),
                            'status': chosen.get('status'),
                            'busy': chosen.get('busy'),
                            'labels': sorted(x.get('name') for x in chosen.get('labels', []) if x.get('name'))
                        }
                        receipt['habitat'] = habitat
                        if habitat:
                            receipt['enabled'] = True
                            receipt['status'] = 'READY_DECLARED_CONSTRAINED_RUNNER'
                        else:
                            receipt['status'] = 'DEFERRED_UNSUPPORTED_RUNNER_OS'
                            habitat = 'linux'
                    else:
                        receipt['status'] = 'DEFERRED_DECLARED_RUNNER_NOT_ONLINE'
                except urllib.error.HTTPError as exc:
                    receipt['status'] = f'DEFERRED_RUNNER_DISCOVERY_HTTP_{exc.code}'
                except urllib.error.URLError:
                    receipt['status'] = 'DEFERRED_RUNNER_DISCOVERY_NETWORK'
        except (ValueError, json.JSONDecodeError) as exc:
            receipt['status'] = 'DEFERRED_INVALID_DECLARED_RUNNER_LABELS'
            receipt['validation_error'] = str(exc)
            labels = ['self-hosted']
    Path(args.out).write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    write_output(receipt['enabled'], labels, habitat)
    print(json.dumps({'status': receipt['status'], 'enabled': receipt['enabled'], 'declared_labels': receipt['declared_labels'], 'habitat': receipt['habitat']}, sort_keys=True))


if __name__ == '__main__':
    main()
