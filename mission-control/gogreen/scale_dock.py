#!/usr/bin/env python3
"""CODE PURPLE N+1..N+i read-only MIP/LLDB/LDAB/DAG scale dock.

Consumes evidence projections; neither authenticates GitHub nor dispatches workers.
Production causal roots and math inference remain with their source owners.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import math
import re
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = 'codepurple.scale-dock.series.v1'
SHA = re.compile(r'^[0-9a-f]{40}$')
PRIORITY = {'P0':0, 'P1':1, 'P2':2, 'P3':3, 'UNKNOWN':4}
STATES = {'RED', 'RECOVERED', 'UNKNOWN', 'BLOCKED'}
FAMILIES = {'GOVERNANCE', 'SECURITY', 'COMPATIBILITY', 'COVERAGE',
            'RUNTIME', 'EVIDENCE', 'FEDERATION', 'DOCUMENTATION', 'OTHER'}


def require(ok, message):
    if not ok:
        raise ValueError('SCALE_DOCK_HOLD:' + message)


def encoded(data):
    return (json.dumps(data, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False)+'\n').encode('ascii')


def digest(data):
    return hashlib.sha256(encoded(data)).hexdigest()


def utc(value):
    require(isinstance(value, str) and value.endswith('Z'), 'UTC Z required')
    try:
        d = datetime.fromisoformat(value[:-1] + '+00:00')
    except ValueError as exc:
        raise ValueError('SCALE_DOCK_HOLD:invalid UTC') from exc
    require(d.utcoffset().total_seconds() == 0, 'UTC offset')
    return d


def positive(value, label):
    require(type(value) is int and value > 0, label)
    return value


def zero_or_more(value, label):
    require(type(value) is int and value >= 0, label)
    return value


def safe_path(path):
    require(isinstance(path, str) and path and len(path) <= 512 and not path.startswith('/')
            and '\\' not in path and ':' not in path and '\x00' not in path
            and all(bit not in ('', '.', '..', '.git') for bit in path.split('/')),
            'unsafe mutation lease')
    return path


def collides(a, b):
    return any(x == y or x.startswith(y+'/') or y.startswith(x+'/')
               for x in a for y in b)


def graph(data):
    nodes = data.get('nodes')
    edges = data.get('hard_edges')
    require(isinstance(nodes, list) and 0 < len(nodes) <= 512
            and all(isinstance(x, str) and x for x in nodes)
            and len(set(nodes)) == len(nodes), 'DAG node identities')
    require(isinstance(edges, list) and len(edges) <= 4096, 'DAG edges')
    adj = {n: set() for n in nodes}
    indeg = {n: 0 for n in nodes}
    observed = set()
    for e in edges:
        require(isinstance(e, list) and len(e) == 2 and
                e[0] in indeg and e[1] in indeg and e[0] != e[1], 'DAG edge')
        key = tuple(e)
        require(key not in observed, 'duplicate DAG edge')
        observed.add(key)
        adj[e[0]].add(e[1]); indeg[e[1]] += 1
    queue = deque(n for n in nodes if indeg[n] == 0)
    topo = []
    while queue:
        n = queue.popleft(); topo.append(n)
        for child in sorted(adj[n]):
            indeg[child] -= 1
            if indeg[child] == 0:
                queue.append(child)
    require(len(topo) == len(nodes), 'hard DAG cycle')
    downstream = {n: set() for n in nodes}
    for n in reversed(topo):
        for child in adj[n]:
            downstream[n].add(child)
            downstream[n].update(downstream[child])
    return {'nodes': len(nodes), 'hard_edges': len(edges),
            'topological_order': topo,
            'downstream_declared': {k: len(v) for k, v in downstream.items()},
            'runtime_verified_edges': None,
            'authority': 'DECLARED_TOPOLOGY_ONLY_NO_CROSS_REPO_EDGE_CREDIT'}


def coverage(row, heads):
    require(isinstance(row, dict) and row.get('repo') in heads
            and row.get('source_sha') == heads[row['repo']], 'coverage source')
    for key in ('population', 'tool', 'selection', 'scope'):
        require(isinstance(row.get(key), str) and row[key], 'coverage ' + key)
    for kind in ('statements', 'branches'):
        x = row.get(kind)
        require(isinstance(x, dict), 'coverage ' + kind)
        covered = zero_or_more(x.get('covered'), 'covered')
        eligible = positive(x.get('eligible'), 'eligible')
        require(covered <= eligible, 'coverage numerator > denominator')
    return row


def observation(p, repos, topology):
    require(isinstance(p, dict), 'pulse row')
    n = zero_or_more(p.get('n'), 'pulse ordinal')
    utc(p.get('observed_at'))
    heads = p.get('source_heads')
    require(isinstance(heads, dict) and set(heads) == set(repos)
            and all(SHA.fullmatch(v or '') for v in heads.values()), 'exact source heads')
    eligible = positive(p.get('eligible'), 'eligible observation population')
    findings = p.get('findings')
    require(isinstance(findings, list) and len(findings) <= eligible, 'manifestation denominator')
    seen, jobs, fingerprints, roots = set(), set(), Counter(), set()
    summarized = []
    for f in findings:
        require(isinstance(f, dict) and f.get('id') not in seen and
                isinstance(f.get('id'), str) and f['id'], 'manifestation ID')
        seen.add(f['id'])
        require(f.get('repo') in heads and f.get('source_sha') == heads[f['repo']], 'manifestation source')
        require(f.get('family') in FAMILIES and f.get('priority') in PRIORITY
                and f.get('state') in STATES, 'family/priority/state')
        r, a, j = (f.get(k) for k in ('run_id', 'attempt', 'job_id'))
        complete = all(type(v) is int and v > 0 for v in (r, a, j))
        require(complete or all(v is None for v in (r, a, j)), 'partial native identity')
        if complete:
            key = (f['repo'], r, a, j)
            require(key not in jobs, 'duplicate native job identity')
            jobs.add(key)
        step = f.get('first_failed_step')
        require(step is None or isinstance(step, str) and bool(step), 'first-red step')
        fingerprint = f.get('fingerprint')
        require(fingerprint is None or isinstance(fingerprint, str) and bool(fingerprint), 'fingerprint')
        if fingerprint is not None: fingerprints[fingerprint] += 1
        root = f.get('root_id')
        require(root is None or isinstance(root, str) and bool(root), 'root ID')
        if root is not None: roots.add(root)
        require(f.get('owner_accepted') is False, 'owner approval not imported')
        depend = f.get('dag_node')
        require(depend is None or depend in topology['downstream_declared'], 'unknown DAG node')
        paths = f.get('mutation_paths', [])
        require(isinstance(paths, list) and len(paths) == len(set(paths)), 'mutation leases')
        for path in paths: safe_path(path)
        require(f.get('mode') in ('UNSUPERVISED_READONLY', 'SUPERVISED_REPAIR'), 'supervision mode')
        if f['mode'] == 'SUPERVISED_REPAIR': require(bool(paths), 'missing source lease')
        summarized.append({'id':f['id'], 'repo':f['repo'], 'state':f['state'],
            'family':f['family'], 'priority':f['priority'], 'fingerprint':fingerprint,
            'root_id':root, 'root_accepted':False, 'native_tuple_complete':complete,
            'run_id':r, 'attempt':a, 'job_id':j,
            'first_red_step_known':bool(step), 'dag_node':depend,
            'declared_descendants':topology['downstream_declared'].get(depend) if depend else None,
            'mode':f['mode'], 'mutation_paths':paths})
    cover = p.get('coverage', [])
    require(isinstance(cover, list), 'coverage population')
    ckeys = set()
    for row in cover:
        coverage(row, heads)
        k = (row['repo'], row['population'], row['scope'], row['tool'], row['selection'])
        require(k not in ckeys, 'duplicate coverage scope')
        ckeys.add(k)
    queue = p.get('queue')
    require(isinstance(queue, dict), 'queue snapshot')
    qids = queue.get('queued_run_ids')
    if qids is not None:
        require(isinstance(qids, list) and len(qids) == len(set(qids)) and
                all(type(x) is int and x > 0 for x in qids), 'queue run identities')
    ages = queue.get('queue_ages_seconds')
    if ages is not None:
        require(isinstance(ages, list) and all(type(x) in (int, float)
            and math.isfinite(x) and x >= 0 for x in ages), 'queue age samples')
        require(qids is not None and len(ages) == len(qids), 'queue ages not population-matched')
    slots = queue.get('verified_runner_slots')
    require(slots is None or type(slots) is int and slots >= 0, 'runner capacity')
    require(queue.get('real_dispatches') == 0, 'no native remote dispatch')
    return {'n': n, 'at': p['observed_at'], 'heads': heads, 'eligible': eligible,
      'observed': len(findings), 'findings': summarized, 'fingerprints':len(fingerprints),
      'repeated_fingerprint_occurrences':sum(v-1 for v in fingerprints.values()),
      'candidate_root_ids':sorted(roots), 'accepted_root_ids':[],
      'native_tuple_complete':len(jobs),
      'first_red_steps_known':sum(x['first_red_step_known'] for x in summarized),
      'queue_length':len(qids) if qids is not None else None,
      'queue_ids':sorted(qids) if qids is not None else None,
      'queue_age_p95_seconds':sorted(ages)[math.ceil(.95*len(ages))-1] if ages else None,
      'runner_slots':slots, 'coverage': cover}


def compared_coverage(a, b):
    left = {(r['repo'], r['population'], r['scope'], r['tool'], r['selection']):r
            for r in a['coverage']}
    right = {(r['repo'], r['population'], r['scope'], r['tool'], r['selection']):r
             for r in b['coverage']}
    deltas = []
    for key in sorted(left.keys() & right.keys()):
        x, y = left[key], right[key]
        matched = all(x[z]['eligible'] == y[z]['eligible'] for z in ('statements','branches'))
        # Different exact SHAs are allowed only when explicit same population, selection and denominators.
        deltas.append({'key':list(key), 'matched_denominators':matched,
            'statement_delta_pp':round(100*(y['statements']['covered']-x['statements']['covered'])/
                x['statements']['eligible'], 4) if matched else None,
            'branch_delta_pp':round(100*(y['branches']['covered']-x['branches']['covered'])/
                x['branches']['eligible'], 4) if matched else None})
    return deltas


def _signature(p):
    return digest({'eligible':p['eligible'],
      'findings':[(f['id'], f['repo'], f['state'], f['root_id'], f['fingerprint'],
                   f['run_id'], f['attempt'], f['job_id'], f['first_red_step_known'])
                  for f in sorted(p['findings'],key=lambda x:x['id'])],
      'coverage':p['coverage'], 'queue_ids':p['queue_ids'],
      'queue_length':p['queue_length'], 'queue_heads':p['heads']})


def validate_math_provider(payload, provider_sha):
    if payload is None: return {'status':'NOT_DOCKED', 'forecast_mae':None,
                                'pca':'UNKNOWN', 'bt':'UNKNOWN'}
    require(isinstance(payload, dict) and
       payload.get('schema') == 'gg_math.g3a_pulse_decision.v1', 'canonical gg_MATH schema')
    require(payload.get('provider_sha') == provider_sha and SHA.fullmatch(provider_sha or ''),
            'math provider source binding')
    require(payload.get('merge_admission') == 'HOLD' and
            payload.get('authority_transfer') is False and
            payload.get('qps_acceptance') is False and
            payload.get('six_sigma_verified') is False, 'math authority')
    require(payload.get('root_closure_credit') is None and
            payload.get('pca_readiness') == 'DEFER_UNMATCHED_JOINT_ROWS' and
            payload.get('bt_readiness') == 'DEFER_NO_OBSERVED_PAIRWISE_COMPARISONS',
            'math qualification')
    cp = dict(payload)
    actual_digest = cp.pop('receipt_sha256', None)
    # gg_MATH canonical digest uses compact JSON without terminal newline.
    expected_digest = hashlib.sha256(json.dumps(cp,sort_keys=True,separators=(',',':'),
                                     allow_nan=False).encode('utf-8')).hexdigest()
    require(actual_digest == expected_digest, 'math receipt digest')
    return {'status':'PROVIDER_SCHEMA_AND_DIGEST_CHECKED_NOT_NATIVE_ATTESTED',
      'forecast_mae':payload.get('forecast_mae'), 'pca':'HOLD','bt':'HOLD',
      'provider_sha':provider_sha}


def evaluate(doc):
    require(isinstance(doc, dict) and doc.get('schema') == SCHEMA, 'series schema')
    require(doc.get('observation_class') in ('SYNTHETIC_REFERENCE','HISTORICAL_REPLAY'),
            'data cannot self-attest native authority')
    controls = doc.get('controls')
    require(controls == {'authority_transfer':False, 'merge_admission':'HOLD',
                         'dispatch_authorized':False, 'security_waiver':False,
                         'qps_engineering_acceptance':False}, 'admission boundary')
    repos = doc.get('repos')
    require(isinstance(repos, list) and 0 < len(repos) <= 12 and len(set(repos))==len(repos)
            and all(isinstance(r,str) and r.count('/')==1 for r in repos),'source catalogue')
    require(isinstance(doc.get('cohort_id'),str) and bool(doc['cohort_id']), 'population ID')
    topology = graph(doc.get('dag'))
    pulses = doc.get('pulses')
    require(isinstance(pulses,list) and 1 <= len(pulses) <= 12, 'bounded pulse series')
    series = [observation(x, repos, topology) for x in pulses]
    for a,b in zip(series,series[1:]):
        require(b['n'] > a['n'] and utc(b['at']) > utc(a['at']), 'monotone pulse time')
    source_math = doc.get('gg_math_provider_sha')
    require(source_math is None or SHA.fullmatch(source_math or ''), 'math SHA')
    math_dock = validate_math_provider(doc.get('gg_math_decision'), source_math)
    now = series[-1]
    # Shadow-broker regime follows observed queue pressure, never a clock-time capacity guess.
    qlen, age = now['queue_length'], now['queue_age_p95_seconds']
    if qlen is None: regime, read_cap, write_cap = 'UNKNOWN_HOLD',0,0
    elif qlen > 16 or age is not None and age > 600: regime, read_cap, write_cap = 'CONGESTED_HOLD',0,0
    elif qlen: regime, read_cap, write_cap = 'RECOVERING',2,1
    else: regime, read_cap, write_cap = 'STABLE_OBSERVED_CAPACITY_UNKNOWN',4,2
    ordered = sorted(now['findings'], key=lambda f:
        (PRIORITY[f['priority']], -int(f['declared_descendants'] or 0), f['family'],f['id']))
    # Shadow packet proposals only: no worker lease, no dispatch, no reviewer authority.
    readers, writers, leased = [], [], defaultdict(list)
    for f in ordered:
        if f['state'] in ('RECOVERED',) or f['native_tuple_complete'] is False:
            continue
        if f['mode'] == 'UNSUPERVISED_READONLY' and len(readers)<read_cap:
            readers.append(f['id'])
        if f['mode'] == 'SUPERVISED_REPAIR' and len(writers)<write_cap and f['first_red_step_known'] and not collides(
            f['mutation_paths'],leased[f['repo']]):
            writers.append(f['id']); leased[f['repo']].extend(f['mutation_paths'])
    pairs=[{'before_n':a['n'], 'after_n':b['n'], 'matched_coverage':compared_coverage(a,b),
            'same_observed_population':a['eligible']==b['eligible'] and
              {f['id'] for f in a['findings']}=={f['id'] for f in b['findings']},
            'queue_run_arrivals':sorted(set(b['queue_ids'])-set(a['queue_ids'])) if a['queue_ids'] is not None and b['queue_ids'] is not None else None,
            'queue_run_exits':sorted(set(a['queue_ids'])-set(b['queue_ids'])) if a['queue_ids'] is not None and b['queue_ids'] is not None else None,
            'unchanged_normalized_state':_signature(a)==_signature(b)}
           for a,b in zip(series,series[1:])]
    fixed = bool(pairs and pairs[-1]['same_observed_population'] and
                 pairs[-1]['unchanged_normalized_state'] and
                 now['observed'] == now['eligible'] and
                 now['queue_length'] == 0)
    unresolved = sum(f['state'] not in ('RECOVERED',) for f in now['findings'])
    stop = ('STOP_SCALING_DIAGNOSE_RESIDUAL' if fixed and unresolved else
            'CANDIDATE_FIXED_POINT_ADMISSION_HOLD' if fixed else
            'HOLD_INCOMPARABLE_OR_NEW_STATE' if pairs and not pairs[-1]['same_observed_population'] else
            'CONTINUE_BOUNDED_OBSERVATION')
    return {'schema':'codepurple.scale-dock.receipt.v1',
        'observation_class':doc['observation_class'],'cohort_id':doc['cohort_id'],
        'pulses':series,'comparisons':pairs,'dag':topology,
        'ranked':ordered, 'shadow_proposals':{'regime':regime,'proposal_caps':{'readers':read_cap,'writers':write_cap},
             'read_only':readers,'supervised_source_writers':writers,
             'real_dispatches':0,'real_writer_leases':0,'capacity_qualified':False},
        'gg_math_dock':math_dock,'stop_decision':stop,
        'latest_unresolved_manifestations':unresolved,
        'source_bound_breadth':{'observed':now['observed'],'eligible':now['eligible'],
                                'canonical_six_repo_42_cell_credit':None},
        'worker_hours':None,'independent_worker_slots':None,
        'm1':'PARTIAL_REFERENCE_ONLY','m2':'HOLD','m3':'HOLD',
        'll_db_real_debugger_sessions':None,'ldab_causal_root_closures':0,
        'security_waiver':False,'authority_transfer':False,
        'dispatch_authorized':False,'merge_admission':'HOLD',
        'qps_engineering_acceptance':False,'cross_repo_coverage_uplift':None}


def mermaid(receipt):
    lines=['flowchart LR','SRC["Native run/attempt/job provenance"] --> LDAB["LDAB manifestation"]',
        'LDAB --> ROOT["Fingerprint != accepted causal root"]',
        'ROOT --> DAG["Hard DAG / dependency fanout"]',
        'DAG --> QUEUE{"Adaptive queue + supervision gate"}',
        'QUEUE --> READ["Unsupervised read-only proposal"]',
        'QUEUE --> WRITE["Supervised owner repair proposal - no dispatch"]',
        'READ --> MATH["gg_MATH forecast/plateau dock - descriptive"]',
        'WRITE --> TEST["Native tests / independent security"]',
        'TEST --> PROOF["#530 ZIP bytes / #531 breadth / #533 viewer"]',
        'MATH --> STOP{"N+1 = N?"}', 'PROOF --> STOP',
        'STOP --> HOLD["HOLD / independent human admission"]',
        'classDef obs fill:#dbeafe,stroke:#2563eb,color:#1e3a8a',
        'classDef act fill:#dcfce7,stroke:#16a34a,color:#14532d',
        'classDef gate fill:#fef3c7,stroke:#d97706,color:#78350f',
        'classDef hold fill:#fee2e2,stroke:#dc2626,color:#7f1d1d',
        'class SRC,LDAB,ROOT,DAG obs','class READ,WRITE,MATH,TEST act',
        'class QUEUE,STOP gate','class HOLD hold']
    return '\n'.join(lines)+'\n'


def render_html(r):
    latest = r['pulses'][-1]
    cols=('id','family','priority','state','native_tuple_complete','declared_descendants')
    body=''.join('<tr>'+''.join('<td>'+html.escape(str(f.get(c) if f.get(c) is not None else 'UNKNOWN'))+'</td>' for c in cols)+'</tr>'
                 for f in r['ranked'])
    cards=[('Manifestations',f"{latest['observed']}/{latest['eligible']}"),
           ('Candidate root IDs',str(len(latest['candidate_root_ids']))),
           ('Distinct fingerprints',str(latest['fingerprints'])),
           ('Repeated occurrences',str(latest['repeated_fingerprint_occurrences'])),
           ('Complete native tuples',str(latest['native_tuple_complete'])),
           ('Queue age p95',str(latest['queue_age_p95_seconds'] if latest['queue_age_p95_seconds'] is not None else 'UNKNOWN'))]
    tile=''.join(f'<article><span>{html.escape(k)}</span><strong>{html.escape(v)}</strong></article>' for k,v in cards)
    style='''<style>:root{color-scheme:light dark;font:15px system-ui,sans-serif}body{max-width:1140px;margin:auto;padding:20px}h1{font-size:1.6rem}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}article{border:1px solid #7d8ba0;border-radius:12px;padding:14px}article span{display:block;color:#7b8da0}strong{font-size:1.45rem}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:9px;border-bottom:1px solid #7d8ba0}th{font-size:.9rem} .wide{overflow:auto} .hold{color:#b85d18}p{line-height:1.5}</style>'''
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>CODE PURPLE — scale dock</title>'+style+'<body><h1>CODE PURPLE · Scale Dock</h1>'
        '<p>Read-only MIP / SPINE / LDAB · '+html.escape(r['observation_class'])+' · no remote dispatch</p>'
        '<div class="cards">'+tile+'</div><h2>Root-family dependency priority</h2><div class="wide"><table><thead><tr>'
        +''.join('<th>'+c.replace('_',' ').title()+'</th>' for c in cols)+'</tr></thead><tbody>'+body+'</tbody></table></div>'
        '<h2>Fixed-point decision</h2><p class="hold">'+html.escape(r['stop_decision'])+'</p>'
        '<p>gg_MATH: '+html.escape(r['gg_math_dock']['status'])+' · M1 '+r['m1']+' · M2/M3 HOLD. '
        'Synthetic or historical state is not native attestation, root closure, or QPS acceptance.</p>'
        '</body></html>')


def emit(report, output, source_sha):
    require(isinstance(source_sha,str) and SHA.fullmatch(source_sha),'exact generator checkout')
    output.mkdir(parents=True, exist_ok=True)
    files={'scale-dock.json':encoded(report), 'scale-dock.mmd':mermaid(report).encode(),
           'scale-dock.html':render_html(report).encode()}
    for name,raw in files.items(): (output/name).write_bytes(raw)
    manifest={'schema':'codepurple.scale-dock.manifest.v1','generator_source_sha':source_sha,
       'members':{name:{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
                  for name,raw in files.items()}, 'native_artifact_id':None,
       'externally_verified_zip_bytes':None,'supervision':'SHADOW_READONLY',
       'authority_transfer':False,'merge_admission':'HOLD'}
    (output/'scale-dock-manifest.json').write_bytes(encoded(manifest))
    return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--source-sha',required=True)
    args=p.parse_args()
    report=evaluate(json.loads(args.input.read_text(encoding='utf-8')))
    manifest=emit(report,args.out,args.source_sha)
    print(json.dumps({'stop':report['stop_decision'],'observed':report['pulses'][-1]['observed'],
       'eligible':report['pulses'][-1]['eligible'],'manifest':hashlib.sha256(encoded(manifest)).hexdigest(),
       'native_dispatch':False},sort_keys=True))

if __name__=='__main__':main()
