"""Read-only LDAB/SIPOC crosswalk of existing canonical Mission Control outputs.

Input is the existing generated graph and W2 GitHub metadata receipt. This
adaptor does not create a new method registry, dispatcher, or root authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

GRAPH_SCHEMA = 'missioncontrol.makeover.projection.v1'
EVIDENCE_SCHEMA = 'missioncontrol.makeover.w2_native_observation.v1'
OUT_SCHEMA = 'missioncontrol.ldab_dag_sipoc.review.v1'


def require(ok, message):
    if not ok:
        raise ValueError('LDAB_DAG_SIPOC_HOLD:' + message)


def validate(graph, evidence):
    require(graph.get('schema') == GRAPH_SCHEMA, 'canonical graph schema')
    require(evidence.get('schema') == EVIDENCE_SCHEMA, 'source-bound evidence schema')
    require(graph.get('source_sha') == evidence.get('source_head_sha'), 'input SHA parity')
    require(graph.get('gate', {}).get('merge_admission') == 'HOLD'
            and evidence.get('governance', {}).get('merge_admission') == 'HOLD',
            'merge admission not authorized')
    require(graph.get('scheduler', {}).get('dispatch_authorized') is False
            and evidence.get('governance', {}).get('authority_transfer') is False,
            'scheduler or authority promotion')
    require([x.get('key') for x in graph.get('sipoc', [])] == list('SIPOC'),
            'SIPOC source order')
    nodes = graph.get('nodes', [])
    edges = graph.get('edges', [])
    require(isinstance(nodes, list) and isinstance(edges, list), 'graph rows')
    ids = [n.get('id') for n in nodes]
    require(len(ids) == len(set(ids)) and all(isinstance(x, str) and x for x in ids),
            'unique graph atom identity')
    counts = graph.get('population', {})
    require(counts.get('repositories') == 5 and counts.get('lanes') == 10
            and counts.get('process_atoms') == 39 and counts.get('beams') == 10
            and counts.get('nodes') == len(nodes) == 54
            and counts.get('edges') == len(edges) == 51, 'controlled population mismatch')
    require(sum(n.get('kind') == 'REPO' for n in nodes) == 5
            and sum(n.get('kind') == 'STAGE' for n in nodes) == 39
            and sum(n.get('kind') == 'BEAM' for n in nodes) == 10,
            'node-kind mismatch')
    require(any(n.get('lane') == 'LDAB' for n in nodes if n.get('kind') == 'STAGE'),
            'LDAB stage missing')
    kinds = {n['id']: n['kind'] for n in nodes}
    adj = {x: [] for x in ids}
    signatures, types = set(), {'PROCESS': 0, 'FEEDFORWARD': 0, 'FEEDBACK': 0}
    stages = {x for x in ids if kinds[x] == 'STAGE'}
    stages_in = {x: 0 for x in stages}
    stages_out = {x: 0 for x in stages}
    stage_next = {}
    for edge in edges:
        a, b = edge.get('source'), edge.get('target')
        require(a in adj and b in adj, 'unbound edge')
        kind, clock = edge.get('kind'), edge.get('temporal')
        require(kind in types, 'unsupported edge type')
        require(clock == ('NEXT_PULSE' if kind == 'FEEDBACK' else 'SAME_PULSE'),
                'invalid edge clock')
        expected = 'STAGE' if kind == 'PROCESS' else 'BEAM'
        require(kinds[a] == expected and kinds[b] == expected,
                'typed edge endpoint')
        signature = (kind, a, b)
        require(signature not in signatures, 'duplicate typed edge')
        signatures.add(signature)
        types[kind] += 1
        if kind == 'PROCESS':
            stages_out[a] += 1
            stages_in[b] += 1
            stage_next[a] = b
        if clock == 'SAME_PULSE':
            adj[a].append(b)
    require(types == {'PROCESS': 38, 'FEEDFORWARD': 10, 'FEEDBACK': 3},
            'canonical graph edge-type census')
    seen, active = set(), set()
    def visit(node):
        require(node not in active, 'same-pulse DAG cycle')
        if node in seen:
            return
        active.add(node)
        for nxt in adj[node]:
            visit(nxt)
        active.remove(node)
        seen.add(node)
    for nid in ids:
        visit(nid)
    require(all(x <= 1 for x in stages_in.values()) and
            all(x <= 1 for x in stages_out.values()), 'process chain degree')
    starts = [x for x in stages if stages_in[x] == 0]
    ends = [x for x in stages if stages_out[x] == 0]
    require(len(starts) == len(ends) == 1, 'process chain endpoints')
    visited = set()
    cursor = starts[0]
    while cursor not in visited:
        visited.add(cursor)
        if cursor not in stage_next:
            break
        cursor = stage_next[cursor]
    require(len(visited) == len(stages) and cursor == ends[0],
            'process chain connectivity')
    return counts


def build(graph, evidence):
    counts = validate(graph, evidence)
    w1 = evidence.get('w1', {})
    run = w1.get('run')
    jobs = w1.get('jobs')
    status = ('UNKNOWN_RUN_NOT_OBSERVED' if not isinstance(run, dict)
              else 'QUEUED_NOT_EXECUTED' if run.get('status') == 'queued'
              else 'IN_PROGRESS_NOT_TERMINAL' if run.get('status') != 'completed'
              else 'TERMINAL_NATIVE_METADATA_ONLY')
    manifestations = (jobs or {}).get('ldab_step_manifestations') or []
    require(isinstance(manifestations, list), 'LDAB manifestation list')
    require(all(m.get('root_id') is None and m.get('causal_root_accepted') is False
                for m in manifestations), 'unverified causal-root credit')
    return {'schema': OUT_SCHEMA, 'source_sha': graph['source_sha'],
            'population': counts, 'sipoc': graph['sipoc'],
            'diagnostic': {'w1_run_id': (run or {}).get('run_id'),
                           'w1_attempt': (run or {}).get('attempt'),
                           'w1_status': status, 'job_count': (jobs or {}).get('total'),
                           'native_jobs_executed': (jobs or {}).get('terminal_success_with_steps'),
                           'ldab_first_failed_step_manifestations': manifestations,
                           'distinct_causal_root_ids': None,
                           'native_logs_authenticated': False,
                           'native_lldb_session': None,
                           'native_test_count': None,
                           'root_closures_accepted': None},
            'links': {'w1_source': 'GBOGEB/pipeline-automation-hub#669',
                      'method_registry': 'PROCESS_LANES_v1.json',
                      'beam_dag': 'CODE_PURPLE_BEAMS_DAG_v1.json',
                      'owner': 'GBOGEB/pipeline-automation-hub'},
            'authority': {'readonly': True, 'dispatch_authorized': False,
                          'merge_admission': 'HOLD', 'qps_owner_acceptance': None,
                          'security_waiver': False}}


def mermaid(report):
    d = report['diagnostic']
    title = str(d['w1_status']).replace('"', "'")
    return '\n'.join([
        'flowchart LR',
        '  S["S: five source-owned repositories"] --> I["I: pinned SHA and run/job receipts"]',
        '  I --> P["P: canonical 54-node / 51-edge DAG, LDAB step classification"]',
        '  P --> O["O: read-only diagnostic receipt, causal roots UNKNOWN"]',
        '  O --> C["C: repository owner / reviewer / next pulse"]',
        f'  P --> R["W1: {title}"]',
        '  R --> L["LLDB runtime debugger: NO SESSION VERIFIED"]',
        '  R --> H["Merge admission HOLD"]',
        '  C -. "N+1 after fresh source proof" .-> I',
        '  %% Source authority not transferred; feedback is next pulse only.',
        ''
    ])


def emit(graph_path, evidence_path, output):
    gp, ep, output = Path(graph_path), Path(evidence_path), Path(output)
    report = build(json.loads(gp.read_text(encoding='utf-8')),
                   json.loads(ep.read_text(encoding='utf-8')))
    report['input_sha256'] = {
        'graph': hashlib.sha256(gp.read_bytes()).hexdigest(),
        'evidence': hashlib.sha256(ep.read_bytes()).hexdigest()}
    output.mkdir(parents=True, exist_ok=True)
    names = ('ldab-sipoc.json', 'ldab-sipoc.mmd')
    (output / names[0]).write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    (output / names[1]).write_text(mermaid(report), encoding='utf-8')
    receipt = {'schema': 'missioncontrol.ldab_dag_sipoc.manifest.v1',
               'source_sha': report['source_sha'], 'merge_admission': 'HOLD',
               'files_sha256': {name: hashlib.sha256((output / name).read_bytes()).hexdigest()
                                for name in names}}
    (output / 'ldab-sipoc-manifest.json').write_text(json.dumps(receipt, indent=2, sort_keys=True)+'\n')
    return receipt


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--graph', required=True)
    p.add_argument('--evidence', required=True)
    p.add_argument('--out', required=True)
    a = p.parse_args()
    print(json.dumps(emit(a.graph, a.evidence, a.out), sort_keys=True))
