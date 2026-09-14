#!/usr/bin/env python3
import argparse
import hashlib
import io
import json
import os
import urllib.error
import urllib.request
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
CONFIG = json.loads((ROOT / 'TEMPORAL_POLICY_CONFIG_v1.json').read_text(encoding='utf-8'))


def parse_ts(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')) if value else None


class CrossHostAuthStrippingRedirect(urllib.request.HTTPRedirectHandler):
    """Follow GitHub artifact redirects without forwarding GitHub auth to SAS blob storage."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected and urlparse(newurl).netloc != urlparse(req.full_url).netloc:
            redirected.remove_header('Authorization')
            redirected.remove_header('X-GitHub-Api-Version')
        return redirected


def api_request(url, token, binary=False):
    req = urllib.request.Request(url)
    req.add_header('Accept', 'application/vnd.github+json')
    req.add_header('Authorization', f'Bearer {token}')
    req.add_header('X-GitHub-Api-Version', '2022-11-28')
    opener = urllib.request.build_opener(CrossHostAuthStrippingRedirect()) if binary else urllib.request.build_opener()
    with opener.open(req, timeout=45) as response:
        raw = response.read()
    return raw if binary else json.loads(raw.decode('utf-8'))


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def zip_json(raw, basename):
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = [n for n in zf.namelist() if n.endswith('/' + basename) or n == basename]
        if not names:
            return None
        data = zf.read(sorted(names)[0])
        return json.loads(data.decode('utf-8')), sha256(data)


def direction_from_bt(bt):
    nodes = {n['strategy']: n for n in bt['nodes']}
    single = float(nodes['ALLOC_SINGLE_CELL']['normalized_strength'])
    dc = CONFIG['direction_contract']
    if single >= float(dc['single_if_normalized_strength_gte']):
        direction = 'ALLOC_SINGLE_CELL'
    elif single <= float(dc['paired_if_normalized_strength_lte']):
        direction = 'ALLOC_PAIRED_CELL'
    else:
        direction = 'INDETERMINATE'
    return direction, single


def scarcity_from_admission(admission):
    threshold = float(CONFIG['natural_scarcity_extension']['scarcity_threshold_seconds'])
    eligible = []
    for row in admission.get('rows', []):
        if row.get('lane') == 'baseline':
            value = row.get('admission_proxy_seconds_from_run_creation')
            metric = 'baseline_admission_proxy_seconds_from_run_creation'
        else:
            value = row.get('post_gate_admission_seconds')
            metric = 'held_post_gate_admission_seconds'
        if value is not None:
            eligible.append({'cell_id': row.get('cell_id'), 'metric': metric, 'seconds': float(value)})
    peak = max((x['seconds'] for x in eligible), default=0.0)
    return {
        'status': 'SCARCITY_OBSERVED' if peak >= threshold else 'SCARCITY_UNPROVEN',
        'threshold_seconds': threshold,
        'peak_eligible_seconds': peak,
        'measurements': eligible,
        'designed_held_gate_excluded': True,
    }


def make_window(run, analysis, admission, analysis_digest, source_kind):
    source_sha = analysis.get('source_sha')
    if len(source_sha or '') != 40:
        raise ValueError('invalid source sha')
    if admission.get('source_sha') != source_sha:
        raise ValueError('analysis/admission source mismatch')
    if run.get('head_sha') and run.get('head_sha') != source_sha:
        raise ValueError('workflow head/source mismatch')
    if analysis.get('task_receipts') != 72 or analysis.get('accepted') != 72 or analysis.get('rejected') != 0:
        raise ValueError('window is not 72/72 accepted')
    rex_veto = analysis.get('rex', {}).get('persistent_or_regression_count') != 0
    classes = {}
    for task_class in CONFIG['task_classes']:
        bt = analysis['bt_conditional_by_task_class'][task_class]
        if bt.get('status') != 'READY_CONDITIONAL_OBSERVED' or bt.get('observed_pairs') != 6:
            raise ValueError(f'conditional BT not ready for {task_class}')
        direction, single_strength = direction_from_bt(bt)
        classes[task_class] = {
            'direction': direction,
            'single_normalized_strength': single_strength,
            'paired_normalized_strength': 1.0 - single_strength,
            'observed_pairs': int(bt['observed_pairs']),
        }
    created_at = run.get('created_at') or datetime.now(timezone.utc).isoformat()
    return {
        'window_id': str(run['id']),
        'run_attempt': int(run.get('run_attempt') or 1),
        'workflow_name': run.get('name'),
        'workflow_path': run.get('path'),
        'event': run.get('event'),
        'head_branch': run.get('head_branch'),
        'source_sha': source_sha,
        'created_at': created_at,
        'source_kind': source_kind,
        'analysis_digest_sha256': analysis_digest,
        'hosted_runner_classes': sorted({r.get('habitat') for r in admission.get('rows', []) if r.get('habitat')}),
        'lanes': sorted({r.get('lane') for r in admission.get('rows', []) if r.get('lane')}),
        'scarcity': scarcity_from_admission(admission),
        'rex_veto': rex_veto,
        'task_classes': classes,
    }


def collect_historical(repo, token, current_run_id):
    wanted_paths = {
        '.github/workflows/crew-pc3-conditional-bt.yml',
        '.github/workflows/crew-temporal-allocation-policy.yml',
    }
    runs = []
    for page in range(1, 6):
        payload = api_request(f'https://api.github.com/repos/{repo}/actions/runs?per_page=100&page={page}', token)
        batch = payload.get('workflow_runs', [])
        runs.extend(batch)
        if len(batch) < 100:
            break
    selected = []
    for run in runs:
        if str(run.get('id')) == str(current_run_id):
            continue
        if run.get('status') != 'completed' or run.get('conclusion') != 'success':
            continue
        if run.get('path') not in wanted_paths:
            continue
        selected.append(run)
    selected.sort(key=lambda r: r.get('created_at', ''))
    return selected[-24:]


def window_from_artifact(repo, token, run):
    artifacts = api_request(
        f'https://api.github.com/repos/{repo}/actions/runs/{run["id"]}/artifacts?per_page=100', token
    ).get('artifacts', [])
    candidates = [
        a for a in artifacts
        if a.get('name', '').startswith(('crew-pc3-conditional-bt-', 'crew-temporal-pc3-')) and not a.get('expired')
    ]
    if not candidates:
        return None
    artifact = sorted(candidates, key=lambda a: a.get('created_at', ''))[-1]
    raw = api_request(artifact['archive_download_url'], token, binary=True)
    analysis_pair = zip_json(raw, 'PC3_CONDITIONAL_BT_RECEIPT.json')
    admission_pair = zip_json(raw, 'PC3_ADMISSION_TELEMETRY.json')
    if not analysis_pair or not admission_pair:
        return None
    analysis, digest = analysis_pair
    admission, _ = admission_pair
    return make_window(run, analysis, admission, digest, 'HISTORICAL_ACTION_ARTIFACT')


def window_metrics(windows):
    windows = sorted(windows, key=lambda w: (w['created_at'], int(w['window_id'])))
    distinct_shas = len({w['source_sha'] for w in windows})
    first = parse_ts(windows[0]['created_at']) if windows else None
    last = parse_ts(windows[-1]['created_at']) if windows else None
    temporal_span = max(0.0, (last - first).total_seconds()) if first and last else 0.0
    return {
        'independent_windows': len(windows),
        'distinct_source_shas': distinct_shas,
        'temporal_span_seconds': temporal_span,
        'hosted_runner_classes': sorted({h for w in windows for h in w['hosted_runner_classes']}),
        'lanes': sorted({l for w in windows for l in w['lanes']}),
        'window_ids': [w['window_id'] for w in windows],
        'rex_veto': any(w['rex_veto'] for w in windows),
    }


def class_metrics(windows, task_class):
    records = [
        {
            'window_id': w['window_id'],
            'source_sha': w['source_sha'],
            'created_at': w['created_at'],
            **w['task_classes'][task_class],
        }
        for w in windows
    ]
    directional = [r for r in records if r['direction'] != 'INDETERMINATE']
    counts = Counter(r['direction'] for r in directional)
    dominant, dominant_count = counts.most_common(1)[0] if counts else ('INDETERMINATE', 0)
    consistency = (dominant_count / len(directional)) if directional else 0.0
    latest_two = [r['direction'] for r in directional[-2:]]
    latest_two_agree = len(latest_two) >= 2 and len(set(latest_two)) == 1
    total_pairs = sum(r['observed_pairs'] for r in records)
    pooled_single = (
        sum(r['single_normalized_strength'] * r['observed_pairs'] for r in records) / total_pairs
        if total_pairs else 0.5
    )
    return {
        'records': records,
        'directional_windows': len(directional),
        'direction_counts': dict(sorted(counts.items())),
        'dominant_direction': dominant,
        'direction_consistency': consistency,
        'latest_two_directional_windows_agree': latest_two_agree,
        'pooled_single_strength': pooled_single,
        'pooled_winner_strength': max(pooled_single, 1.0 - pooled_single),
        'observed_pairs_total': total_pairs,
    }


def gate_pass(policy, gate, distinct_shas, temporal_span, directional_count, consistency, pooled_winner,
              latest_two_agree, runner_classes, lanes):
    return (
        policy['independent_windows'] >= int(gate['min_independent_windows'])
        and distinct_shas >= int(gate['min_distinct_source_shas'])
        and temporal_span >= float(gate['min_temporal_span_seconds'])
        and directional_count >= int(gate['min_directional_windows'])
        and consistency >= float(gate['min_direction_consistency'])
        and pooled_winner >= float(gate['min_pooled_winner_strength'])
        and (not gate.get('latest_two_directional_windows_must_agree') or latest_two_agree)
        and len(runner_classes) >= int(gate.get('min_hosted_runner_classes', 0))
        and (not gate.get('requires_baseline_and_held_lanes') or {'baseline', 'held'}.issubset(lanes))
    )


def build_policy(windows):
    windows = sorted(windows, key=lambda w: (w['created_at'], int(w['window_id'])))
    all_metrics = window_metrics(windows)
    contract = CONFIG['window_contract']
    scheduled_windows = [
        w for w in windows
        if w.get('event') == contract['control_eligible_event']
        and w.get('workflow_path') == contract['control_eligible_workflow_path']
    ]
    scheduled_metrics = window_metrics(scheduled_windows)
    runner_classes = all_metrics['hosted_runner_classes']
    lanes = set(all_metrics['lanes'])
    scheduled_runner_classes = scheduled_metrics['hosted_runner_classes']
    scheduled_lanes = set(scheduled_metrics['lanes'])
    scarcity_windows = [w['window_id'] for w in windows if w['scarcity']['status'] == 'SCARCITY_OBSERVED']
    any_rex_veto = all_metrics['rex_veto']

    policies = {}
    for task_class in CONFIG['task_classes']:
        aggregate = class_metrics(windows, task_class)
        scheduled = class_metrics(scheduled_windows, task_class)
        policy = {
            'task_class': task_class,
            'independent_windows': all_metrics['independent_windows'],
            'directional_windows': aggregate['directional_windows'],
            'distinct_source_shas': all_metrics['distinct_source_shas'],
            'temporal_span_seconds': all_metrics['temporal_span_seconds'],
            'direction_counts': aggregate['direction_counts'],
            'dominant_direction': aggregate['dominant_direction'],
            'direction_consistency': aggregate['direction_consistency'],
            'latest_two_directional_windows_agree': aggregate['latest_two_directional_windows_agree'],
            'pooled_single_strength': aggregate['pooled_single_strength'],
            'pooled_winner_strength': aggregate['pooled_winner_strength'],
            'observed_pairs_total': aggregate['observed_pairs_total'],
            'scarcity_windows': len(scarcity_windows),
            'window_evidence': aggregate['records'],
            'control_frontier': {
                'eligibility_event': contract['control_eligible_event'],
                'eligibility_workflow_path': contract['control_eligible_workflow_path'],
                'independent_windows': scheduled_metrics['independent_windows'],
                'directional_windows': scheduled['directional_windows'],
                'distinct_source_shas': scheduled_metrics['distinct_source_shas'],
                'temporal_span_seconds': scheduled_metrics['temporal_span_seconds'],
                'direction_counts': scheduled['direction_counts'],
                'dominant_direction': scheduled['dominant_direction'],
                'direction_consistency': scheduled['direction_consistency'],
                'latest_two_directional_windows_agree': scheduled['latest_two_directional_windows_agree'],
                'pooled_single_strength': scheduled['pooled_single_strength'],
                'pooled_winner_strength': scheduled['pooled_winner_strength'],
                'observed_pairs_total': scheduled['observed_pairs_total'],
                'hosted_runner_classes': scheduled_runner_classes,
                'lanes': sorted(scheduled_lanes),
                'window_ids': scheduled_metrics['window_ids'],
            },
            'policy_status': 'LEARNING',
            'allocation_recommendation': 'NO_POLICY',
            'allocation_policy_promotion': False,
            'competency_promotion': False,
            'authority_transfer': False,
        }
        if any_rex_veto:
            policy['policy_status'] = 'VETO_REX'
        else:
            control_policy = {'independent_windows': scheduled_metrics['independent_windows']}
            control = gate_pass(
                control_policy,
                CONFIG['control_policy_gate'],
                scheduled_metrics['distinct_source_shas'],
                scheduled_metrics['temporal_span_seconds'],
                scheduled['directional_windows'],
                scheduled['direction_consistency'],
                scheduled['pooled_winner_strength'],
                scheduled['latest_two_directional_windows_agree'],
                scheduled_runner_classes,
                scheduled_lanes,
            )
            stable = gate_pass(
                policy,
                CONFIG['recommend_repeat_stable_gate'],
                all_metrics['distinct_source_shas'],
                all_metrics['temporal_span_seconds'],
                aggregate['directional_windows'],
                aggregate['direction_consistency'],
                aggregate['pooled_winner_strength'],
                aggregate['latest_two_directional_windows_agree'],
                runner_classes,
                lanes,
            )
            if control and scheduled['dominant_direction'] != 'INDETERMINATE':
                policy['policy_status'] = 'CONTROL_POLICY'
                policy['allocation_recommendation'] = scheduled['dominant_direction']
                policy['allocation_policy_promotion'] = True
            elif stable and aggregate['dominant_direction'] != 'INDETERMINATE':
                policy['policy_status'] = 'RECOMMEND_REPEAT_STABLE'
                policy['allocation_recommendation'] = aggregate['dominant_direction']
            elif (
                policy['independent_windows'] >= CONFIG['recommend_repeat_stable_gate']['min_independent_windows']
                and aggregate['directional_windows'] >= 2
                and aggregate['direction_consistency'] < CONFIG['recommend_repeat_stable_gate']['min_direction_consistency']
            ):
                policy['policy_status'] = 'LEARNING_DIRECTION_UNSTABLE'
        policies[task_class] = policy

    return {
        'schema': 'missioncontrol.temporal_allocation_policy_receipt.v1',
        'mission_id': CONFIG['mission_id'],
        'status': 'PASS_TEMPORAL_POLICY_LEARNING',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'independent_windows': all_metrics['independent_windows'],
        'distinct_source_shas': all_metrics['distinct_source_shas'],
        'temporal_span_seconds': all_metrics['temporal_span_seconds'],
        'hosted_runner_classes': runner_classes,
        'lanes': sorted(lanes),
        'scheduled_control_frontier': {
            'eligibility_event': contract['control_eligible_event'],
            'eligibility_workflow_path': contract['control_eligible_workflow_path'],
            'independent_windows': scheduled_metrics['independent_windows'],
            'distinct_source_shas': scheduled_metrics['distinct_source_shas'],
            'temporal_span_seconds': scheduled_metrics['temporal_span_seconds'],
            'hosted_runner_classes': scheduled_runner_classes,
            'lanes': sorted(scheduled_lanes),
            'window_ids': scheduled_metrics['window_ids'],
            'rex_veto': scheduled_metrics['rex_veto'],
        },
        'natural_scarcity': {
            'status': 'SCARCITY_OBSERVED' if scarcity_windows else 'SCARCITY_UNPROVEN',
            'window_ids': scarcity_windows,
            'designed_held_gate_excluded': True,
        },
        'rex_veto': any_rex_veto,
        'windows': windows,
        'policies': policies,
        'competency_promotions': 0,
        'authority_transfer': False,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--current-analysis', required=True)
    ap.add_argument('--current-admission', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    token = os.environ.get('GITHUB_TOKEN', '')
    repo = os.environ.get('GITHUB_REPOSITORY', '')
    run_id = os.environ.get('GITHUB_RUN_ID', '')
    if not token or '/' not in repo or not run_id:
        raise SystemExit('FAIL GITHUB_TOKEN/GITHUB_REPOSITORY/GITHUB_RUN_ID required')

    current_run = api_request(f'https://api.github.com/repos/{repo}/actions/runs/{run_id}', token)
    analysis_raw = Path(args.current_analysis).read_bytes()
    analysis = json.loads(analysis_raw.decode('utf-8'))
    admission = json.loads(Path(args.current_admission).read_text(encoding='utf-8'))
    windows = []
    errors = []
    for run in collect_historical(repo, token, run_id):
        try:
            window = window_from_artifact(repo, token, run)
            if window:
                windows.append(window)
        except (urllib.error.HTTPError, urllib.error.URLError, ValueError, KeyError, zipfile.BadZipFile) as exc:
            errors.append({
                'run_id': str(run.get('id')),
                'error': type(exc).__name__,
                'http_code': getattr(exc, 'code', None),
                'detail': str(exc)[:240],
            })

    windows.append(make_window(current_run, analysis, admission, sha256(analysis_raw), 'CURRENT_EXACT_SHA'))
    dedup = {w['window_id']: w for w in windows}
    receipt = build_policy(list(dedup.values()))
    receipt['historical_collection_errors'] = errors
    receipt['config_schema'] = CONFIG['schema']
    Path(args.out).write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    summary = {
        'status': receipt['status'],
        'windows': receipt['independent_windows'],
        'distinct_shas': receipt['distinct_source_shas'],
        'span_seconds': receipt['temporal_span_seconds'],
        'scheduled_control_frontier': receipt['scheduled_control_frontier'],
        'scarcity': receipt['natural_scarcity']['status'],
        'historical_errors': len(errors),
        'policies': {k: v['policy_status'] for k, v in receipt['policies'].items()},
        'recommendations': {k: v['allocation_recommendation'] for k, v in receipt['policies'].items()},
        'promoted_rules': sum(v['allocation_policy_promotion'] for v in receipt['policies'].values()),
    }
    print(json.dumps(summary, sort_keys=True))


if __name__ == '__main__':
    main()
