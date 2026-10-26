"""Source-preserving, read-only G3P wave lineage, SIPOC and HTML/SVG projection.

Intervening branches are not inferred as exact-source continuity; only Git
ancestry comparisons performed by an independent source reader may bind them.
"""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from n3_continuation import digest, validate, check


def is_unproven_boundary(edge):
    return (edge.get('relationship') == 'inter_wave_source_lineage'
            and edge.get('source_ancestry_proven') is not True)


def compile_waves(ledgers):
    check(isinstance(ledgers, list) and len(ledgers) >= 2, 'at least two wave ledgers required')
    nodes, edges, waves = [], [], []
    last_ordinal, last_head = None, None
    seen = set()
    for wave_no, ledger in enumerate(ledgers):
        state = validate(ledger)
        check(state['disposition'] == 'THREE_PULSES_RECORDED_NON_ADMITTED',
              'partial or blocked wave cannot imply complete lineage')
        mission = ledger['mission']
        key = (mission['repo'], mission['id'], mission['wave'])
        check(key not in seen, 'duplicate wave identity')
        seen.add(key)
        check(key[:2] == (ledgers[0]['mission']['repo'], ledgers[0]['mission']['id']),
              'foreign mission cannot be coalesced')
        if last_ordinal is not None:
            check(ledger['start_ordinal'] == last_ordinal, 'skipped or repeated cross-wave ordinal')
            edges.append({'source': nodes[-1]['id'],
                          'target': ledger['receipts'][0]['pulse_id'],
                          'relationship': 'inter_wave_source_lineage',
                          'evidence': 'DECLARED_GAP' if last_head != mission['start_sha']
                                      else 'LEDGER_HEAD_EQUALITY',
                          'causal_confirmed': False,
                          'source_ancestry_proven': False})
        for idx, receipt in enumerate(ledger['receipts']):
            check(receipt['pulse_id'] not in {n['id'] for n in nodes}, 'duplicate pulse identity')
            nodes.append({'id':receipt['pulse_id'], 'ordinal':receipt['ordinal'],
                          'wave':mission['wave'], 'source_head_claim':receipt['output_source_sha'],
                          'test_kind':receipt['tests']['kind'], 'passed_test_claim':receipt['tests']['passed'],
                          'merge_admission':'HOLD', 'source_authenticated':False})
            if idx:
                edges.append({'source':ledger['receipts'][idx-1]['pulse_id'],
                              'target':receipt['pulse_id'],
                              'relationship':'next_ledger_pulse', 'evidence':'LEDGER_SOURCE_CLAIM',
                              'causal_confirmed':False, 'source_ancestry_proven':False})
        last_ordinal = ledger['start_ordinal'] + len(ledger['receipts'])
        last_head = ledger['receipts'][-1]['output_source_sha']
        waves.append({'wave':mission['wave'], 'initial_sha':mission['start_sha'],
                      'last_pulse_sha':last_head, 'source_digest':digest(ledger),
                      'pulse_count':3, 'native_proof_status':'UNKNOWN'})
    gaps = sum(is_unproven_boundary(edge) for edge in edges)
    return {'schema':'missioncontrol.g3p.wave_lineage.v1',
            'repository':ledgers[0]['mission']['repo'], 'mission_id':ledgers[0]['mission']['id'],
            'waves':waves, 'nodes':nodes, 'edges':edges,
            'metrics':{'waves':len(waves), 'pulses':len(nodes), 'edge_count':len(edges),
                       'intervening_unproven_source_boundaries':gaps,
                       'authenticated_native_pulse_receipts':0,
                       'confirmed_causal_roots':0,
                       'matched_backlog_delta':None,
                       'matched_coverage_delta':None,
                       'execution_time_ms':None},
            'sipoc':{'supplier':'source-owning GitHub repository + native CI',
                     'inputs':'immutable ledgers, exact commit evidence, native run/job/attempt receipts',
                     'process':'validate ledgers -> classify source gaps -> build noncausal DAG -> QA',
                     'outputs':'read-only graph/telemetry and explicit unknown flags',
                     'customer':'Mission Control G3P / independent owner review',
                     'feeder_health':'UNKNOWN_EXTERNAL_NATIVE_AUTHENTICATION'},
            'authority_transfer':False, 'merge_admission':'HOLD'}


def mermaid(data):
    check(data.get('schema') == 'missioncontrol.g3p.wave_lineage.v1', 'bad lineage schema')
    result = ['flowchart LR']
    for idx, node in enumerate(data['nodes']):
        result.append(f'  P{idx}["Pulse {node["ordinal"]}: source claim"]')
    index = {n['id']:i for i,n in enumerate(data['nodes'])}
    for edge in data['edges']:
        a,b = index[edge['source']],index[edge['target']]
        arrow = '-.->' if is_unproven_boundary(edge) else '-->'
        result.append(f'  P{a} {arrow} P{b}')
    return '\n'.join(result)+'\n'


def html_report(data):
    """Self-contained, interactive N-index replay; source data remain read-only.

    The bundled page is usable offline; same-origin cyclic reload and push
    updates activate when served by g3p_live_dashboard.py.
    """
    from g3p_live_dashboard import render_html
    return render_html(data)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--ledgers',type=Path,nargs='+',required=True)
    p.add_argument('--out-dir',type=Path,required=True)
    args=p.parse_args()
    data=compile_waves([json.loads(f.read_text(encoding='utf-8')) for f in args.ledgers])
    args.out_dir.mkdir(parents=True,exist_ok=True)
    (args.out_dir/'g3p-lineage.json').write_text(json.dumps(data,sort_keys=True,indent=2)+'\n',encoding='utf-8',newline="\n")
    (args.out_dir/'g3p-lineage.mmd').write_text(mermaid(data),encoding='utf-8',newline="\n")
    (args.out_dir/'g3p-lineage.html').write_text(html_report(data)+'\n',encoding='utf-8',newline="\n")
    print(json.dumps(data['metrics'],sort_keys=True))


if __name__=='__main__':
    main()
