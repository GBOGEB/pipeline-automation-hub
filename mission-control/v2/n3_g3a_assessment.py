"""G3A (G3P evaluation): preissued forecast vs local coverage and native census.

A diagnostic projection, never a native CI outcome or Mission Control SSOT.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path

from n3_workflow_census import project as workflow_project

CORE = ('n3_continuation.py','n3_integrity.py','n3_metrics.py',
        'n3_dashboard.py','n3_native_join.py','n3_wave_federation.py')
EXPANDED = CORE + ('n3_workflow_census.py','n3_g3a_assessment.py')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def scope(coverage, modules):
    require(isinstance(coverage, dict) and isinstance(coverage.get('files'), dict), 'coverage JSON required')
    paths = [Path(k).name for k in coverage['files'] if Path(k).name in modules]
    require(len(paths) == len(set(paths)), 'colliding coverage source basenames')
    chosen = {Path(k).name:v.get('summary') for k,v in coverage['files'].items() if Path(k).name in modules}
    require(set(chosen) == set(modules), 'missing or colliding coverage source modules')
    def sum_stat(k):
        require(all(type(row.get(k)) is int and row[k] >= 0 for row in chosen.values()), 'malformed coverage counter')
        return sum(row[k] for row in chosen.values())
    result = {name:sum_stat(name) for name in ('covered_lines','num_statements','covered_branches','num_branches')}
    require(0 < result['num_statements'] and 0 < result['num_branches'] and
            result['covered_lines'] <= result['num_statements'] and
            result['covered_branches'] <= result['num_branches'],'invalid coverage population')
    result['statement_pct'] = round(100*result['covered_lines']/result['num_statements'], 4)
    result['branch_pct'] = round(100*result['covered_branches']/result['num_branches'], 4)
    result['combined_pct'] = round(100*(result['covered_lines']+result['covered_branches'])/
                                   (result['num_statements']+result['num_branches']), 4)
    return result


def assess(forecast, census, coverage, observations):
    require(forecast.get('schema') == 'missioncontrol.g3a.forecast_preaction.v1', 'unrecognized frozen forecast')
    require(forecast.get('source_start_head') == census.get('source_sha'), 'forecast/census source SHA drift')
    require(forecast.get('authority_transfer') is False and forecast.get('merge_admission') == 'HOLD',
            'forecast authority conflict')
    expected = forecast.get('predictions')
    require(isinstance(expected, list) and [p.get('pulse') for p in expected] == [10,11,12] and
            all(p.get('actual') is None for p in expected), 'forecast mutated or pulse order changed')
    require(observations.get('schema') == 'missioncontrol.g3a.local_test_observations.v1' and
            observations.get('source_start_head') == forecast['source_start_head'] and
            observations.get('provenance') == 'LOCAL_NOT_NATIVE_EXACT_HEAD', 'observation provenance conflict')
    actuals = observations.get('pulses')
    require(isinstance(actuals, list) and [row.get('pulse') for row in actuals] == [10,11,12],
            'actual pulses incomplete/unsorted')
    scored=[]
    for pre, actual in zip(expected, actuals):
        count, failed = actual.get('tests_passed'), actual.get('tests_failed')
        require(type(count) is int and count >= 0 and type(failed) is int and failed >= 0,
                'invalid local test observation denominator')
        require(isinstance(actual.get('source_checkpoint'), str) and len(actual['source_checkpoint']) == 40 and
                all(x in '0123456789abcdef' for x in actual['source_checkpoint']), 'source checkpoint malformed')
        target=pre['expected_cumulative_local_tests_min']
        require(type(target) is int and target >= 0, 'forecast target malformed')
        scored.append({'pulse':pre['pulse'], 'prediction_min_tests':target,
                       'actual_local_tests':count,'local_failed':failed,
                       'forecast_surplus':count-target,'target_met':count>=target and failed==0,
                       'source_checkpoint':actual['source_checkpoint'],
                       'evidence_kind':'LOCAL_ONLY_NOT_NATIVE_CI'})
    native=workflow_project(census)
    six=scope(coverage,CORE)
    require((six['num_statements'],six['num_branches']) ==
            (forecast['scope']['baseline_statement_total'],forecast['scope']['baseline_branch_total']),
            'unmatched core coverage denominator')
    expanded=scope(coverage,EXPANDED)
    delta={'baseline_six_statement_covered':forecast['scope']['baseline_statement_covered'],
           'baseline_six_branch_covered':forecast['scope']['baseline_branch_covered'],
           'current_six_statement_covered':six['covered_lines'],
           'current_six_branch_covered':six['covered_branches'],
           'statement_delta_pp':round(100*(six['covered_lines']-forecast['scope']['baseline_statement_covered'])/
                                      six['num_statements'],4),
           'branch_delta_pp':round(100*(six['covered_branches']-forecast['scope']['baseline_branch_covered'])/
                                   six['num_branches'],4),
           'matched_population':True}
    return {'schema':'missioncontrol.g3a.evaluation.v1','requested_label':'G3A','canonical_envelope':'G3P',
            'mission_id':forecast['mission_id'],'start_ordinal':9,'terminal_ordinal':12,
            'forecast_digest':digest(forecast),'native_census_source_sha':census['source_sha'],
            'local_observations_digest':digest(observations),
            'planned_vs_actual':scored,
            'local_test_growth':scored[-1]['actual_local_tests']-forecast['scope']['baseline_tests_passed_local'],
            'matched_core_coverage':six,'expanded_scope_coverage':expanded,
            'matched_coverage_improvement':delta,
            'native_ci_observation':native['metrics'],
            'native_proof_state':'PENDING_OR_UNVERIFIED_NOT_PASS',
            'native_ci_success_rate':native['metrics']['successful_terminal_workflows']['pct'],
            'independent_trials':None,'statistical_inference':'DEFER_NO_INDEPENDENT_TRIALS',
            'confirmed_root_burndown':None,'measured_run_cost_savings':None,
            'merge_admission':'HOLD','authority_transfer':False}


def render(report):
    require(report.get('schema') == 'missioncontrol.g3a.evaluation.v1' and
            report.get('merge_admission') == 'HOLD' and report.get('authority_transfer') is False,
            'unsafe dashboard authority')
    e=lambda v:html.escape(str(v),quote=True)
    scores=report['planned_vs_actual']
    rows=''.join(f'<tr><th scope="row">N+{p["pulse"]}</th><td>{p["prediction_min_tests"]}</td>'
                 f'<td>{p["actual_local_tests"]}</td><td>{p["local_failed"]}</td>'
                 f'<td>{"MET" if p["target_met"] else "NOT_MET"}</td></tr>' for p in scores)
    bars=''.join(f'<rect x="{120+220*i}" y="{180-int(150*p["actual_local_tests"]/max(1,max(x["actual_local_tests"] for x in scores)))}" '
                 f'width="90" height="{int(150*p["actual_local_tests"]/max(1,max(x["actual_local_tests"] for x in scores)))}" '
                 f'fill="#426ca8"><title>N+{p["pulse"]}: {p["actual_local_tests"]} local test cases</title></rect>'
                 for i,p in enumerate(scores))
    n=report['native_ci_observation']
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>CODE PURPLE G3A: N+10 to N+12</title><style>'
            'body{font:16px system-ui,sans-serif;background:#f7f8fc;color:#243448;max-width:1000px;margin:auto;padding:2rem}'
            'section{background:white;border:1px solid #c3ccdb;border-radius:10px;padding:1rem;margin:1rem 0}'
            'table{width:100%;border-collapse:collapse}th,td{padding:.65rem;text-align:left;border-bottom:1px solid #d0d6de}'
            'svg{max-width:100%;height:auto}.muted{color:#4e576b}code{overflow-wrap:anywhere}</style></head><body>'
            '<h1>G3A / G3P · Three-pulse assessment</h1><p class="muted">Read-only, local tests vs frozen targets; no native CI or admission promotion.</p>'
            '<section><h2>Actual local tests</h2><svg viewBox="0 0 800 220" role="img" aria-label="Bars showing local tests after pulses N+10, N+11, N+12">'
            +bars+'</svg><table><thead><tr><th>Pulse</th><th>Predicted minimum</th><th>Observed local</th><th>Failed</th><th>Threshold</th></tr></thead><tbody>'
            +rows+'</tbody></table></section><section><h2>Matched coverage</h2>'
            f'<p>Original six: statements {e(report["matched_core_coverage"]["covered_lines"])}/{e(report["matched_core_coverage"]["num_statements"])}; '
            f'branches {e(report["matched_core_coverage"]["covered_branches"])}/{e(report["matched_core_coverage"]["num_branches"])}. '
            f'Branch delta {e(report["matched_coverage_improvement"]["branch_delta_pp"])} pp.</p>'
            f'<p>Expanded eight-module scope: {e(report["expanded_scope_coverage"]["combined_pct"])}% combined (not matched to original).</p>'
            '</section><section><h2>GitHub native readback (historical #620 head)</h2>'
            f'<p>Queued workflows: {e(n["queued_or_pending_workflows"]["numerator"])}/{e(n["workflow_runs_observed"])}; '
            f'queued jobs: {e(n["observed_queued_jobs"])}/{e(n["reported_total_jobs_for_known_runs"])}; '
            f'attempt IDs known: {e(n["known_run_attempts"]["numerator"])}/{e(n["workflow_runs_observed"])}. '
            'Native PASS unknown, queue p95 unknown, admission HOLD.</p></section>'
            '<section><h2>Source &amp; proof boundaries</h2><p>Forecast SHA256: <code>'+e(report['forecast_digest'])+'</code></p>'
            '<p>Independent trials UNKNOWN · Confirmed engineering-root burndown UNKNOWN · Runtime cost savings UNKNOWN</p>'
            '<p>Historical upstream source: <code>'+e(report['native_census_source_sha'])+'</code></p></section></body></html>')


def main():
    ap=argparse.ArgumentParser()
    for name in ('forecast','census','coverage','observations'):
        ap.add_argument('--'+name,type=Path,required=True)
    ap.add_argument('--out-dir',type=Path,required=True)
    args=ap.parse_args()
    def load(p):return json.loads(p.read_text(encoding='utf-8'))
    report=assess(load(args.forecast),load(args.census),load(args.coverage),load(args.observations))
    args.out_dir.mkdir(parents=True,exist_ok=True)
    (args.out_dir/'g3a-evaluation.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    (args.out_dir/'g3a-evaluation.html').write_text(render(report)+'\n',encoding='utf-8')
    print(json.dumps({'local_test_growth':report['local_test_growth'],
                      'matched_branch_delta_pp':report['matched_coverage_improvement']['branch_delta_pp'],
                      'native_ci_status':report['native_proof_state'],'merge_admission':'HOLD'},sort_keys=True))


if __name__=='__main__':main()
