#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

AXES = {
    'execution_reuse_pressure': {
        'features': {'log_execute_ms', 'cache_reused', 'artifact_reused', 'contention_processes', 'log_workload_units'},
        'control_threshold': 0.50
    },
    'admission_human_dependency_pressure': {
        'features': {'admission_proxy_seconds', 'post_gate_admission_seconds', 'human_dependency_wait_seconds', 'lane_held'},
        'control_threshold': 0.40
    },
    'rex_difficulty_workload': {
        'features': {'rex_exposure_count', 'task_level', 'log_workload_units'},
        'control_threshold': 0.35
    },
    'parallelism_crew_scale': {
        'features': {'worker_count', 'crew_size'},
        'control_threshold': 0.35
    }
}


def component_share(component, features):
    absolute = {k: abs(float(v)) for k, v in component['loadings'].items()}
    total = sum(absolute.values()) or 1.0
    return sum(absolute.get(k, 0.0) for k in features) / total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--analysis', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    source = json.loads(Path(args.analysis).read_text(encoding='utf-8'))
    components = source['pca']['components']
    if len(components) < 5:
        raise SystemExit('FAIL component migration scan requires PC1-PC5')

    axes = {}
    for axis, cfg in AXES.items():
        rows = []
        for component in components:
            share = component_share(component, cfg['features'])
            top5 = [x['feature'] for x in component['top_absolute_loadings'][:5]]
            rows.append({
                'component': component['component'],
                'explained_variance_ratio': component['explained_variance_ratio'],
                'absolute_loading_share': share,
                'features_in_top5': [f for f in top5 if f in cfg['features']]
            })
        rows.sort(key=lambda x: x['absolute_loading_share'], reverse=True)
        best = rows[0]
        axes[axis] = {
            'status': 'DETECTED' if best['absolute_loading_share'] >= cfg['control_threshold'] else 'DIFFUSE',
            'detected_component': best['component'],
            'absolute_loading_share': best['absolute_loading_share'],
            'explained_variance_ratio': best['explained_variance_ratio'],
            'features_in_top5': best['features_in_top5'],
            'threshold': cfg['control_threshold'],
            'component_scan': rows
        }

    pressure = axes['admission_human_dependency_pressure']
    pc3_hypothesis = source['pca']['pc3_pressure_hypothesis']
    if pressure['status'] == 'DETECTED' and pressure['detected_component'] != 'PC3':
        pressure_disposition = f"DETECTED_{pressure['detected_component']}_NOT_PC3"
    elif pressure['status'] == 'DETECTED':
        pressure_disposition = 'DETECTED_PC3'
    else:
        pressure_disposition = 'NO_DOMINANT_PRESSURE_COMPONENT_PC1_PC5'

    out = {
        'schema': 'missioncontrol.crew_frontier_component_migration.v1',
        'source_sha': source['source_sha'],
        'run_id': source['run_id'],
        'basis': 'Measured absolute loading share across PC1-PC5. Component signs are ignored because eigenvector signs are arbitrary.',
        'axes': axes,
        'pressure_disposition': pressure_disposition,
        'pc3_pressure_hypothesis': pc3_hypothesis,
        'interpretation_guard': 'A latent semantic axis may change component rank when new measured features are introduced. Rank migration is evidence, not a reason to relabel PC3 or rotate components post hoc.',
        'authority_transfer': False,
        'competency_promotions': 0
    }
    Path(args.out).write_text(json.dumps(out, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({
        'status': 'PASS_COMPONENT_MIGRATION_SCAN',
        'source_sha': out['source_sha'],
        'pressure_disposition': pressure_disposition,
        'pressure_component': pressure['detected_component'],
        'pressure_share': pressure['absolute_loading_share'],
        'execution_reuse_component': axes['execution_reuse_pressure']['detected_component'],
        'rex_difficulty_component': axes['rex_difficulty_workload']['detected_component'],
        'parallelism_component': axes['parallelism_crew_scale']['detected_component']
    }, sort_keys=True))

if __name__ == '__main__':
    main()
