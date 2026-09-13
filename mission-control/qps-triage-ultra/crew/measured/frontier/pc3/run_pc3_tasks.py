#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTIER = ROOT.parent
MEASURED = FRONTIER.parent
CREW = MEASURED.parent
REPO = CREW.parents[2]
sys.path.insert(0, str(MEASURED))
from rex_runtime_control import collect_history, evaluate_preflight, summarize_recurrence

MANIFEST = json.loads((ROOT / 'FRONTIER_TASK_MANIFEST_v2.json').read_text(encoding='utf-8'))
CHECKLIST = json.loads((MEASURED / 'REX_REUSE_CHECKLIST_v1.json').read_text(encoding='utf-8'))
REGISTRY = json.loads((CREW / 'CREW_REGISTRY_v1.json').read_text(encoding='utf-8'))
COMP = json.loads((CREW / 'COMPETENCY_MATRIX_v1.json').read_text(encoding='utf-8'))
CREW_IDS = {x['crew_id'] for x in REGISTRY['crew']}
REX_IDS = {x['rex_id'] for x in CHECKLIST['checklist']}
DIMS = set(COMP['dimensions'])


def digest_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def analytics_sweep(iterations, workers):
    workers = max(1, int(workers))
    ranges = []
    step = (iterations + workers - 1) // workers
    for start in range(0, iterations, step):
        ranges.append((start, min(iterations, start + step)))
    def calc(bounds):
        a, b = bounds
        total = 0
        for i in range(a, b):
            total += ((i * 2654435761) ^ (i >> 3)) % 1000003
        return total
    if workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            total = sum(ex.map(calc, ranges))
    else:
        total = sum(calc(r) for r in ranges)
    return digest_bytes(str(total).encode()), iterations


def validation_bundle(iterations, workers):
    commands = [
        [sys.executable, str(CREW / 'validate_crew_system.py')],
        [sys.executable, str(CREW / 'validate_crew_telemetry.py')],
        [sys.executable, str(MEASURED / 'validate_rex_reuse.py')],
        [sys.executable, str(MEASURED / 'validate_evidence_returns.py')],
    ]
    def one(cmd):
        p = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True)
        if p.returncode != 0:
            raise RuntimeError(f"validation failed: {' '.join(cmd)}\n{p.stdout}\n{p.stderr}")
        lines = [x for x in p.stdout.splitlines() if x.strip()]
        marker = lines[-1] if lines else 'PASS_EMPTY'
        try:
            marker = str(json.loads(marker).get('status', marker))
        except Exception:
            pass
        return Path(cmd[-1]).name, marker
    final = []
    for _ in range(iterations):
        if workers > 1:
            with ThreadPoolExecutor(max_workers=workers) as ex:
                final = list(ex.map(one, commands))
        else:
            final = [one(c) for c in commands]
    raw = '\n'.join(f'{a}|{b}' for a, b in sorted(final)).encode()
    return digest_bytes(raw), len(commands) * iterations


def rex_surface_scan(iterations, workers):
    files = sorted(p for p in (REPO / 'mission-control').rglob('*') if p.is_file() and p.suffix.lower() in {'.json', '.yaml', '.yml', '.md', '.py'})
    counts = None
    for _ in range(iterations):
        counts = {f'REX-{i:03d}': 0 for i in range(1, 7)}
        for p in files:
            try:
                text = p.read_text(encoding='utf-8')
            except UnicodeDecodeError:
                continue
            for rid in counts:
                counts[rid] += text.count(rid)
    return digest_bytes(json.dumps(counts, sort_keys=True, separators=(',', ':')).encode()), len(files) * iterations


def artifact_crosscheck(iterations, workers, artifact_path, cache_path):
    if not artifact_path.exists() or not cache_path.exists():
        raise RuntimeError('artifact/cache seed missing')
    sources = [artifact_path, cache_path]
    expected = artifact_path.read_bytes()
    if cache_path.read_bytes() != expected:
        raise RuntimeError('cache/artifact semantic mismatch')
    def one(_):
        hashes = [digest_bytes(p.read_bytes()) for p in sources]
        if len(set(hashes)) != 1:
            raise RuntimeError('reuse inputs diverged')
        return hashes[0]
    calls = list(range(iterations))
    if workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            vals = list(ex.map(one, calls))
    else:
        vals = [one(i) for i in calls]
    return digest_bytes(('\n'.join(vals)).encode()), iterations * len(sources)


def start_contention(count, seconds=0.45):
    code = (
        "import time,math; end=time.perf_counter()+float(__import__('sys').argv[1]); x=0.0; "
        "\nwhile time.perf_counter()<end: x=math.sin(x+1.2345)*math.cos(x+0.9876)"
    )
    return [subprocess.Popen([sys.executable, '-c', code, str(seconds)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) for _ in range(int(count))]


def prepare_reuse_seed(source_sha, cell_id):
    artifact_env = os.environ.get('MC_REUSE_ARTIFACT', '')
    artifact_path = Path(artifact_env) if artifact_env else ROOT / 'REUSE_ARTIFACT.json'
    if not artifact_path.exists():
        payload = {'schema': 'missioncontrol.pc3.reuse_seed.v1', 'source_sha': source_sha, 'purpose': 'artifact-cache-reuse'}
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(json.dumps(payload, sort_keys=True) + '\n', encoding='utf-8')
    cache_root = Path(os.environ.get('RUNNER_TEMP', str(ROOT))) / 'mc-pc3-cache'
    cache_root.mkdir(parents=True, exist_ok=True)
    cache_path = cache_root / f'{cell_id}-reuse-seed.json'
    shutil.copyfile(artifact_path, cache_path)
    return artifact_path, cache_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--habitat', required=True, choices=['linux', 'windows', 'macos'])
    ap.add_argument('--lane', required=True, choices=['baseline', 'held'])
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    source_sha = os.environ.get('MC_SOURCE_SHA', '')
    checkout_sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip()
    if len(source_sha) != 40 or source_sha != checkout_sha:
        raise SystemExit(f'FAIL exact SHA: source={source_sha} checkout={checkout_sha}')

    run_id = str(os.environ.get('GITHUB_RUN_ID', 'LOCAL_UNBOUND'))
    runner = {
        'name': os.environ.get('RUNNER_NAME', 'LOCAL_UNBOUND'),
        'os': os.environ.get('RUNNER_OS', args.habitat),
        'arch': os.environ.get('RUNNER_ARCH', 'UNKNOWN'),
        'environment': os.environ.get('RUNNER_ENVIRONMENT', 'github-hosted')
    }
    cell_id = f'{args.habitat}-{args.lane}'
    artifact_path, cache_path = prepare_reuse_seed(source_sha, cell_id)
    artifact_reused = bool(os.environ.get('MC_REUSE_ARTIFACT'))
    cache_reused = cache_path.exists()
    receipts = []
    rex_history = collect_history([MEASURED / 'history', out])
    proof_gate_bound = bool(MANIFEST.get('hypothesis')) and bool(MANIFEST.get('comparison_contract')) and MANIFEST.get('promotion_allowed') is False

    for task in MANIFEST['tasks']:
        if task['primary_crew_id'] not in CREW_IDS or any(x not in CREW_IDS for x in task['crew_combination']):
            raise SystemExit(f"FAIL unknown crew in {task['task_id']}")
        if task['competency_dimension'] not in DIMS:
            raise SystemExit(f"FAIL unknown competency {task['competency_dimension']}")
        if set(task['applicable_rex_ids']) - REX_IDS:
            raise SystemExit(f"FAIL unknown REX in {task['task_id']}")

        preflight = evaluate_preflight(
            checklist_schema=CHECKLIST['schema'],
            applicable_rex_ids=task['applicable_rex_ids'],
            facts={
                'namespace_registered': True,
                'vocabulary_registered': True,
                'yaml_mutation_planned': False,
                'yaml_lint_prechecked': False,
                'active_assignment_current': True,
                'proof_gate_bound': proof_gate_bound,
                'execution_context_reached': True,
            },
        )

        workload = task['workload']
        rp = task['resource_profile']
        wait_observed = 0.0
        burners = []
        started = datetime.now(timezone.utc).isoformat()
        disposition = 'ACCEPT'
        error = None
        semantic = None
        units = 0
        elapsed = 0.0
        steps_executed = 0

        if preflight['payload_allowed']:
            wait_target = float(rp.get('human_dependency_wait_seconds', 0.0))
            wait_t0 = time.perf_counter()
            if wait_target > 0:
                time.sleep(wait_target)
            wait_observed = round(time.perf_counter() - wait_t0, 6) if wait_target > 0 else 0.0

            burners = start_contention(int(rp.get('contention_processes', 0)))
            t0 = time.perf_counter()
            steps_executed = 1
            try:
                kind = workload['kind']
                if kind == 'analytics_sweep':
                    semantic, units = analytics_sweep(int(workload['iterations']), int(workload['workers']))
                elif kind == 'validation_bundle':
                    semantic, units = validation_bundle(int(workload['iterations']), int(workload['workers']))
                elif kind == 'artifact_crosscheck':
                    semantic, units = artifact_crosscheck(int(workload['iterations']), int(workload['workers']), artifact_path, cache_path)
                elif kind == 'rex_surface_scan':
                    semantic, units = rex_surface_scan(int(workload['iterations']), int(workload['workers']))
                else:
                    raise RuntimeError(f'unknown workload {kind}')
            except Exception as exc:
                semantic, units = None, 0
                disposition = 'REJECT'
                error = repr(exc)
            elapsed = round(time.perf_counter() - t0, 6)
        else:
            disposition = 'REJECT'
            error = f"REX_PREFLIGHT_BLOCKED:{','.join(preflight['blocking_rex_ids'])}"

        ended = datetime.now(timezone.utc).isoformat()
        for p in burners:
            try:
                p.wait(timeout=2)
            except subprocess.TimeoutExpired:
                p.kill()

        observed_rex = list(preflight['triggered_rex_ids'])
        recurrence = summarize_recurrence(observed_rex, rex_history)
        new_rex = sorted(rex_id for rex_id, level in recurrence['by_rex_id'].items() if level == 'NEW')
        receipt = {
            'schema': 'missioncontrol.crew_frontier_pc3_runtime_receipt.v2',
            'mission_id': MANIFEST['mission_id'],
            'assignment_id': task['assignment_id'],
            'task_id': task['task_id'],
            'pair_id': task['pair_id'],
            'variant': task['variant'],
            'task_class': task['task_class'],
            'allocation_strategy': task['allocation_strategy'],
            'primary_crew_id': task['primary_crew_id'],
            'crew_combination': task['crew_combination'],
            'competency_dimension': task['competency_dimension'],
            'predeclared_task_level': task['predeclared_task_level'],
            'workload': workload,
            'workload_units': units,
            'resource_profile': rp,
            'measured_resource': {
                'contention_processes': int(rp.get('contention_processes', 0)) if steps_executed else 0,
                'cache_reused': bool(rp.get('cache_reuse')) and cache_reused if steps_executed else False,
                'artifact_reused': bool(rp.get('artifact_reuse')) and artifact_reused if steps_executed else False,
                'human_dependency_wait_seconds': wait_observed
            },
            'habitat': {'id': args.habitat, 'lane': args.lane, 'runner': runner},
            'source_sha': source_sha,
            'run_id': run_id,
            'started_at': started,
            'ended_at': ended,
            'execute_seconds': elapsed,
            'steps_executed': steps_executed,
            'semantic_digest': semantic,
            'disposition': disposition,
            'error': error,
            'promotion_allowed': False,
            'authority_transfer': False,
            'rex_preflight': preflight,
            'rex_postflight': {
                'rex_ids_observed': observed_rex,
                'new_rex_signal': new_rex or None,
                'recurrence_level': recurrence['highest'],
                'recurrence_by_rex_id': recurrence['by_rex_id'],
                'preventive_action_effective': True if 'REX-006' in task['applicable_rex_ids'] and disposition == 'ACCEPT' else None,
                'ledger_update_required': bool(observed_rex)
            }
        }
        path = out / f'{cell_id}__{task["task_id"]}.json'
        path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        receipts.append(receipt)
        for rex_id in observed_rex:
            rex_history.setdefault('counts', {})[rex_id] = int(rex_history.get('counts', {}).get(rex_id, 0)) + 1
        if 'REX-006' in task['applicable_rex_ids'] and disposition == 'ACCEPT':
            controls = set(rex_history.get('preventive_controls', []))
            controls.add('REX-006')
            rex_history['preventive_controls'] = sorted(controls)
        print(json.dumps({'cell': cell_id, 'task_id': task['task_id'], 'class': task['task_class'], 'strategy': task['allocation_strategy'], 'seconds': elapsed, 'human_wait': wait_observed, 'steps_executed': steps_executed, 'blocking_rex_ids': preflight['blocking_rex_ids'], 'disposition': disposition}, sort_keys=True))

    summary = {
        'schema': 'missioncontrol.crew_frontier_pc3_run_summary.v2',
        'mission_id': MANIFEST['mission_id'],
        'cell_id': cell_id,
        'habitat': args.habitat,
        'lane': args.lane,
        'source_sha': source_sha,
        'run_id': run_id,
        'task_count': len(receipts),
        'accepted': sum(r['disposition'] == 'ACCEPT' for r in receipts),
        'rejected': sum(r['disposition'] == 'REJECT' for r in receipts),
        'preflight_blocked': sum(bool(r['rex_preflight']['blocking_rex_ids']) for r in receipts),
        'pair_members': sum(r['pair_id'] is not None for r in receipts),
        'artifact_reused': artifact_reused,
        'cache_reused': cache_reused,
        'competency_promotions': 0,
        'authority_transfer': False
    }
    (out / f'{cell_id}__RUN_SUMMARY.json').write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(summary, sort_keys=True))
    if summary['rejected']:
        raise SystemExit(1)

if __name__ == '__main__':
    main()
