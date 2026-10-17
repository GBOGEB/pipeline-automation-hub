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
    gaps = sum(edge['evidence']=='DECLARED_GAP' for edge in edges)
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
        arrow = '-.->' if edge['evidence']=='DECLARED_GAP' else '-->'
        result.append(f'  P{a} {arrow} P{b}')
    return '\n'.join(result)+'\n'


def html_report(data):
    check(data.get('merge_admission')=='HOLD' and data.get('authority_transfer') is False,
          'cannot render escalated authority')
    esc=lambda s: html.escape(str(s),quote=True)
    circles=[]
    for i,node in enumerate(data['nodes']):
        x=105+i*148
        circles.append(f'<g><circle cx="{x}" cy="85" r="30" fill="#e4e8ed" stroke="#253c52" stroke-width="2"/>'
                       f'<text x="{x}" y="90" text-anchor="middle">N+{node["ordinal"]}</text>'
                       f'<title>{esc(node["id"])}</title></g>')
    edge_lines=[]
    for i,edge in enumerate(data['edges']):
        style=' stroke-dasharray="5 5"' if edge['evidence']=='DECLARED_GAP' else ''
        edge_lines.append(f'<path d="M {135+i*148} 85 L {223+i*148} 85" stroke="#35475e"'
                          f' stroke-width="2" marker-end="url(#arr)"{style}/>' )
    rows=''.join(f'<tr><th>N+{n["ordinal"]}</th><td>{esc(n["wave"])}</td>'
                 f'<td><code>{esc(n["source_head_claim"][:12])}</code></td>'
                 f'<td>{esc(n["test_kind"])}</td><td>HOLD</td></tr>' for n in data['nodes'])
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Mission Control G3P lineage</title><style>body{font:16px system-ui,sans-serif;margin:auto;padding:2rem;max-width:1140px;color:#203247}'
            'svg{max-width:100%;height:auto}table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:.55rem;border-bottom:1px solid #cbd2da}'
            'code{overflow-wrap:anywhere} .warning{font-weight:700}</style></head><body><h1>G3P — six-pulse evidence lineage</h1>'
            '<p class="warning">Read-only source claims. Unverified intermediate Git ancestry and native CI cannot grant merge admission.</p>'
            '<svg role="img" aria-label="Six directed pulse nodes; dashed arrows indicate unproven intervening source ancestry" viewBox="0 0 960 180">'
            '<defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0L10 5L0 10z"/></marker></defs>'
            +''.join(edge_lines)+''.join(circles)+'</svg>'
            '<p>Solid arrows: declared intra-wave continuation. Dashed arrow: unproven cross-wave source ancestry.</p>'
            '<h2>SIPOC feeder</h2><p>'+esc(data['sipoc']['supplier'])+' → '+esc(data['sipoc']['inputs'])+' → '
            +esc(data['sipoc']['process'])+' → '+esc(data['sipoc']['outputs'])+' → '+esc(data['sipoc']['customer'])+'</p>'
            '<p>Feed health: UNKNOWN · Confirmed causal roots: 0 · Admission: HOLD</p>'
            '<h2>Pulse ledger</h2><table><thead><tr><th>Pulse</th><th>Wave</th><th>Source SHA claim</th><th>Tests</th><th>Admission</th></tr></thead><tbody>'
            +rows+'</tbody></table><p>Input wave digests: '+', '.join(esc(w['source_digest']) for w in data['waves'])+'</p></body></html>')


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--ledgers',type=Path,nargs='+',required=True)
    p.add_argument('--out-dir',type=Path,required=True)
    args=p.parse_args()
    data=compile_waves([json.loads(f.read_text(encoding='utf-8')) for f in args.ledgers])
    args.out_dir.mkdir(parents=True,exist_ok=True)
    (args.out_dir/'g3p-lineage.json').write_text(json.dumps(data,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    (args.out_dir/'g3p-lineage.mmd').write_text(mermaid(data),encoding='utf-8')
    (args.out_dir/'g3p-lineage.html').write_text(html_report(data)+'\n',encoding='utf-8')
    print(json.dumps(data['metrics'],sort_keys=True))


if __name__=='__main__':
    main()
