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
from itertools import pairwise
from pathlib import Path

SCHEMA = 'codepurple.scale-dock.series.v1'
SHA = re.compile(r'^[0-9a-f]{40}$')
PRIORITY = {'P0':0, 'P1':1, 'P2':2, 'P3':3, 'UNKNOWN':4}
STATES = {'RED', 'RECOVERED', 'UNKNOWN', 'BLOCKED'}
FAMILIES = {'GOVERNANCE', 'SECURITY', 'COMPATIBILITY', 'COVERAGE',
            'RUNTIME', 'EVIDENCE', 'FEDERATION', 'DOCUMENTATION', 'OTHER'}
# Read-only producer projections the dock may consume; each keeps its own authority.
DOCK_SCHEMAS = {'everred':'everred.census/1.0', 'code_purple':'code-purple.census/v2',
                'p_process':'p-process.state/1.0', 'issue_bd':'codepurple.bd-queue-wave.v1',
                'crosswalk':'codepurple.g5.discovery-gap-crosswalk.v1'}
CLOSED_ROOT_STATES = {'VERIFIED_FIXED', 'PRODUCER_GREEN'}
P_MODES = {'CODE_PURPLE', 'EVERRED'}
STALE_HOURS = 72


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


def ratio(num, den):
    return round(num/den, 4) if num is not None and den else None


def stamp(value):
    """Producer timestamps: Z or +00:00 only; any other offset fails closed."""
    require(isinstance(value, str), 'dock timestamp')
    return utc(value[:-6]+'Z' if value.endswith('+00:00') else value)


def fraction(value, label):
    require(value is None or type(value) in (int, float) and math.isfinite(value)
            and 0 <= value <= 1, label)
    return value


def red_metrics(series):
    """First-red / root-red accounting per pulse and per N->N+1 transition."""
    pulses = []
    for p in series:
        red = [f for f in p['findings'] if f['state'] == 'RED']
        roots, fp_roots = defaultdict(set), defaultdict(set)
        for f in p['findings']:
            if f['root_id'] is None: continue
            roots[f['root_id']].add(f['state'])
            if f['fingerprint'] is not None: fp_roots[f['fingerprint']].add(f['root_id'])
        step = sum(f['first_red_step_known'] for f in red)
        linked = sum(f['root_id'] is not None for f in red)
        pulses.append({'n':p['n'], 'red':len(red), 'red_rate':ratio(len(red), p['eligible']),
            'red_first_step_known':step, 'red_first_step_known_rate':ratio(step, len(red)),
            'red_native_tuple_complete':sum(f['native_tuple_complete'] for f in red),
            'root_linked_red':linked, 'root_linked_rate':ratio(linked, len(red)),
            'unrooted_red':len(red)-linked,
            'root_red':sorted(r for r, s in roots.items() if 'RED' in s),
            'root_recovered':sorted(r for r, s in roots.items() if s == {'RECOVERED'}),
            # One fingerprint pointing at two candidate roots is a crosswalk defect, not two roots.
            'fingerprint_root_conflicts':sorted(k for k, v in fp_roots.items() if len(v) > 1)})
    moves = []
    for a, b in pairwise(series):
        before = {f['id']:f['state'] for f in a['findings']}
        after = {f['id']:f['state'] for f in b['findings']}
        moves.append({'before_n':a['n'], 'after_n':b['n'],
            'new_first_reds':sorted(i for i, s in after.items() if s == 'RED' and i not in before),
            'recoveries':sorted(i for i, s in after.items() if s == 'RECOVERED' and before.get(i) == 'RED'),
            'regressions':sorted(i for i, s in after.items() if s == 'RED' and before.get(i) == 'RECOVERED'),
            'persisting_reds':sorted(i for i, s in after.items() if s == 'RED' and before.get(i) == 'RED'),
            'unobserved_after':sorted(set(before)-set(after))})
    red_sets = [{f['id'] for f in p['findings'] if f['state'] == 'RED'} for p in series]
    ever_red = set().union(*red_sets)
    recovered = sum(len(m['recoveries']) for m in moves)
    regressed = sum(len(m['regressions']) for m in moves)
    return {'window_pulses':len(series), 'pulses':pulses, 'transitions':moves,
        'everred_in_window':sorted(set.intersection(*red_sets)),
        'ever_red_in_window':len(ever_red),
        'red_burndown':pulses[0]['red']-pulses[-1]['red'],
        'recovery_rate':ratio(recovered, len(ever_red)),
        'regression_rate':ratio(regressed, recovered),
        'authority':'MANIFESTATION_STATE_ONLY_NO_ROOT_CLOSURE_CREDIT'}


def dock_everred(e, candidate_roots):
    m = e.get('metrics')
    require(isinstance(m, dict) and isinstance(e.get('roots'), list)
            and isinstance(e.get('probes'), dict), 'everred census shape')
    for k in ('occurrences_total', 'distinct_signatures', 'unmatched_signatures',
              'roots_independent', 'control_plane_red', 'control_plane_probed'):
        zero_or_more(m.get(k), 'everred '+k)
    require(m['unmatched_signatures'] <= m['distinct_signatures'] and
            m['control_plane_red'] <= m['control_plane_probed'], 'everred numerator > denominator')
    for k in ('root_closure_rate', 'recurrence_rate'): fraction(m.get(k), 'everred '+k)
    roots, resolve, severity = {}, {}, Counter()
    for r in e['roots']:
        require(isinstance(r, dict) and isinstance(r.get('id'), str) and r['id']
                and r['id'] not in roots, 'everred root ID')
        roots[r['id']] = r
        aliases = r.get('aliases') or []
        require(isinstance(aliases, list), 'everred aliases')
        for alias in aliases:
            require(resolve.get(alias, r['id']) == r['id'], 'everred alias collision')
            resolve[alias] = r['id']
    resolve.update({i:i for i in roots})
    open_roots = [i for i, r in roots.items() if r.get('state') not in CLOSED_ROOT_STATES]
    for i in open_roots:
        severity[roots[i].get('severity') if roots[i].get('severity') in PRIORITY else 'UNKNOWN'] += 1
    red_p0 = sorted(k for k, v in e['probes'].items() if isinstance(v, dict) and v.get('red') is True
                    and roots.get(k, {}).get('severity') == 'P0')
    matched = {c:resolve[c] for c in sorted(candidate_roots) if c in resolve}
    return {'generated_at':e.get('generated_at'),
        'occurrences_total':m['occurrences_total'], 'distinct_signatures':m['distinct_signatures'],
        'unmatched_signatures':m['unmatched_signatures'],
        'signature_match_rate':ratio(m['distinct_signatures']-m['unmatched_signatures'],
                                     m['distinct_signatures']),
        'roots_total':len(roots), 'roots_independent':m['roots_independent'],
        'roots_open':len(open_roots), 'roots_open_by_priority':dict(sorted(severity.items())),
        'root_closure_rate':m.get('root_closure_rate'), 'recurrence_rate':m.get('recurrence_rate'),
        'failure_amplification':m.get('failure_amplification'),
        'control_plane_red':m['control_plane_red'], 'control_plane_probed':m['control_plane_probed'],
        'control_plane_red_rate':ratio(m['control_plane_red'], m['control_plane_probed']),
        'e1_red_p0_probes':red_p0,
        'consumer_replay_coverage':m.get('consumer_replay_coverage', 'UNKNOWN'),
        'scale_dock_roots_matched':matched,
        'scale_dock_roots_unmatched':sorted(set(candidate_roots)-set(matched))}


def dock_code_purple(c):
    lift, audit = c.get('lift'), c.get('admission_audit')
    require(isinstance(lift, list) and lift and all(isinstance(x, dict) and isinstance(x.get('id'), str)
            and type(x.get('ok')) is bool for x in lift), 'code purple lift criteria')
    require(type(c.get('lifted')) is bool and isinstance(c.get('incident'), str)
            and c['incident'], 'code purple case')
    require(not c['lifted'] or all(x['ok'] for x in lift), 'lifted with unmet lift criteria')
    require(isinstance(audit, dict), 'code purple admission audit')
    merged = zero_or_more(audit.get('merged'), 'audit merged')
    for k in ('gate_green', 'ungated', 'with_red_checks'):
        require(zero_or_more(audit.get(k), 'audit '+k) <= merged, 'audit numerator > merged')
    repos = c.get('repos') or {}
    require(isinstance(repos, dict), 'code purple repos')
    follow = c.get('follow_ups') or []
    require(isinstance(follow, list), 'code purple follow-ups')
    return {'generated_at':c.get('generated_at'), 'incident':c['incident'], 'lifted':c['lifted'],
        'lift_met':sum(x['ok'] for x in lift), 'lift_total':len(lift),
        'lift_unmet':sorted(x['id'] for x in lift if not x['ok']),
        'merged_since_unblock':merged, 'gate_green':audit['gate_green'],
        'gate_green_rate':ratio(audit['gate_green'], merged),
        'ungated_merges':audit['ungated'], 'merged_with_red_checks':audit['with_red_checks'],
        'red_merge_rate':ratio(audit['with_red_checks'], merged),
        'open_prs':sum(zero_or_more(r.get('open_prs'), 'open PRs') for r in repos.values()),
        'follow_ups_open':sum(str(x.get('state', '')).lower() not in ('closed', 'merged') for x in follow)}


def dock_p_process(s):
    repos = s.get('repos')
    require(isinstance(repos, dict) and repos, 'p-process repos')
    require(type(s.get('lifted')) is bool, 'p-process lifted')
    modes, open_roots, worst, ruleset_red, reasons = Counter(), 0, 'UNKNOWN', [], 0
    for name, r in sorted(repos.items()):
        require(isinstance(r, dict) and r.get('mode') in P_MODES, 'p-process mode')
        modes[r['mode']] += 1
        open_roots += zero_or_more(r.get('open_roots'), 'p-process open roots')
        if r.get('worst') in PRIORITY and PRIORITY[r['worst']] < PRIORITY[worst]: worst = r['worst']
        if r.get('ruleset') == 'RED': ruleset_red.append(name)
        reasons += len(r.get('reasons') or [])
    return {'generated_at':s.get('generated_at'), 'census_at':s.get('census_at'),
        'everred_at':s.get('everred_at'), 'incident':s.get('incident'), 'lifted':s['lifted'],
        'modes':dict(sorted(modes.items())),
        'code_purple_repos':sorted(k for k, r in repos.items() if r['mode'] == 'CODE_PURPLE'),
        'open_roots':open_roots, 'worst_priority':worst, 'ruleset_red':ruleset_red,
        'ruleset_red_rate':ratio(len(ruleset_red), len(repos)), 'escalation_reasons':reasons}


def dock_issue_bd(b):
    keys = ('open_prs', 'open_issues', 'open_items', 'prs_with_failed_workflows',
            'prs_without_observed_failure', 'prs_unknown', 'manifestations')
    for k in keys: zero_or_more(b.get(k), 'BD '+k)
    require(b['open_items'] == b['open_prs']+b['open_issues'], 'BD open item parity')
    require(b['prs_with_failed_workflows']+b['prs_without_observed_failure']+b['prs_unknown']
            == b['open_prs'], 'BD PR status partition')
    require(b.get('authority_transfer') is False and b.get('dispatch_authorized') is False
            and b.get('merge_authorized') is False, 'BD authority')
    groups, issues = b.get('family_groups'), b.get('issues') or []
    require(isinstance(groups, list) and isinstance(issues, list), 'BD groups/issues')
    queue = b.get('queue_latency_workflow_level') or {}
    red, observed = b['prs_with_failed_workflows'], b['open_prs']-b['prs_unknown']
    return {'generated_at':b.get('generated_at'), 'scope':b.get('scope'),
        'full_census':b.get('scope') == 'LIVE_READ_ONLY_API_CENSUS',
        **{k:b[k] for k in keys},
        'red_pr_rate':ratio(red, observed), 'unknown_pr_rate':ratio(b['prs_unknown'], b['open_prs']),
        'manifestations_per_red_pr':ratio(b['manifestations'], red),
        'issue_share_of_open_items':ratio(b['open_issues'], b['open_items']),
        'issues_by_repo':{x.get('repository'):x.get('open_issues') for x in issues},
        'top_families':[{k:g.get(k) for k in ('family', 'affected_prs', 'failed_workflows', 'candidate_owner')}
                        for g in groups[:5]],
        'queue_p50_seconds':queue.get('p50_seconds'), 'queue_p95_seconds':queue.get('p95_seconds'),
        'retry_attempt_excess_proxy':b.get('retry_attempt_excess_proxy'),
        # Absent private QPS counts and causal roots stay UNKNOWN, never zero.
        'private_qps_open_issues':b.get('private_qps_open_issues'),
        'independent_root_count':b.get('independent_root_count')}


def dock_crosswalk(x):
    controls, hist, cohort, packets = (x.get(k) for k in
        ('controls', 'historical_g1', 'current_cohort', 'gap_packets'))
    require(isinstance(controls, dict) and controls.get('merge_authorized') is False
            and controls.get('security_waiver') is False and controls.get('authority_transfer') is False
            and controls.get('qps_owner_acceptance') is False, 'crosswalk authority')
    require(isinstance(hist, dict) and isinstance(cohort, dict) and isinstance(packets, list), 'crosswalk shape')
    eligible = positive(cohort.get('eligible_cells'), 'crosswalk eligible cells')
    h_obs = zero_or_more(hist.get('observed_cells'), 'crosswalk observed')
    h_miss = zero_or_more(hist.get('missing_cells'), 'crosswalk missing')
    require(h_obs+h_miss == hist.get('eligible_cells'), 'crosswalk historical partition')
    valid = cohort.get('validated_observed_cells')
    require(valid is None or type(valid) is int and 0 <= valid <= eligible, 'crosswalk validated cells')
    require(len(packets) <= eligible, 'crosswalk packets > cells')
    ids, native, verified, rooted = set(), 0, 0, 0
    states, families = Counter(), Counter()
    for p in packets:
        require(isinstance(p, dict) and isinstance(p.get('packet_id'), str)
                and p['packet_id'] not in ids, 'crosswalk packet ID')
        ids.add(p['packet_id'])
        require(p.get('dispatch_authorized') is False, 'crosswalk dispatch')
        tup = [p.get(k) for k in ('native_run_id', 'run_attempt', 'job_id')]
        complete = all(type(v) is int and v > 0 for v in tup)
        require(complete or all(v is None for v in tup), 'crosswalk partial native identity')
        native += complete
        verified += p.get('archive_bytes_verified') is True and type(p.get('artifact_id')) is int
        rooted += p.get('root_id') is not None
        states[str(p.get('state'))] += 1; families[str(p.get('family'))] += 1
    return {'classification':x.get('classification'), 'eligible_cells':eligible,
        'historical_observed_cells':h_obs, 'historical_missing_cells':h_miss,
        'historical_breadth':ratio(h_obs, hist['eligible_cells']),
        'current_validated_cells':valid,
        'current_breadth':ratio(valid, eligible) if valid is not None else None,
        'gap_packets':len(packets), 'packets_by_state':dict(sorted(states.items())),
        'packets_by_family':dict(sorted(families.items())),
        'native_identity_complete':native, 'native_identity_rate':ratio(native, len(packets)),
        'archive_bytes_verified':verified, 'root_bound':rooted,
        'repos':len(cohort.get('repos') or [])}


DOCKERS = {'code_purple':dock_code_purple, 'p_process':dock_p_process,
           'issue_bd':dock_issue_bd, 'crosswalk':dock_crosswalk}


def dock_sources(docks, candidate_roots, at):
    docks = {} if docks is None else docks
    require(isinstance(docks, dict) and set(docks) <= set(DOCK_SCHEMAS), 'unknown dock source')
    out = {}
    for name, schema in DOCK_SCHEMAS.items():
        payload = docks.get(name)
        if payload is None:
            out[name] = {'status':'NOT_DOCKED', 'metrics':None}
            continue
        require(isinstance(payload, dict) and payload.get('schema') == schema, name+' schema')
        metrics = (dock_everred(payload, candidate_roots) if name == 'everred'
                   else DOCKERS[name](payload))
        produced = payload.get('generated_at')
        age = round((at-stamp(produced)).total_seconds()/3600, 2) if produced is not None else None
        out[name] = {'status':'DOCKED_READ_ONLY_PROJECTION', 'schema':schema,
            'input_sha256':digest(payload), 'age_hours_at_latest_pulse':age,
            'stale':None if age is None else age > STALE_HOURS, 'metrics':metrics}
    return out


def dock_consistency(docks):
    """Cross-source agreement; a disagreement is reported as HOLD, never repaired here."""
    m = {k:v['metrics'] or {} for k, v in docks.items()}
    ev, cp, pp = m['everred'], m['code_purple'], m['p_process']
    checks = []
    def check(name, left, right, implies=False):
        state = ('UNKNOWN' if left is None or right is None else
                 'AGREE' if (not left or right if implies else left == right) else 'DISAGREE')
        checks.append({'check':name, 'left':left, 'right':right, 'state':state})
    check('incident: code_purple == p_process', cp.get('incident'), pp.get('incident'))
    check('lifted: code_purple == p_process', cp.get('lifted'), pp.get('lifted'))
    check('open roots: everred == p_process', ev.get('roots_open'), pp.get('open_roots'))
    check('snapshot: everred.generated_at == p_process.everred_at',
          ev.get('generated_at'), pp.get('everred_at'))
    check('snapshot: code_purple.generated_at == p_process.census_at',
          cp.get('generated_at'), pp.get('census_at'))
    check('E2: open case => a repo in CODE_PURPLE mode',
          None if cp.get('lifted') is None else not cp['lifted'],
          None if 'code_purple_repos' not in pp else bool(pp['code_purple_repos']), implies=True)
    check('E1: red P0 control-plane probe => a repo in CODE_PURPLE mode',
          None if 'e1_red_p0_probes' not in ev else bool(ev['e1_red_p0_probes']),
          None if 'code_purple_repos' not in pp else bool(pp['code_purple_repos']), implies=True)
    states = {c['state'] for c in checks}
    return {'checks':checks, 'state':'HOLD_SOURCE_DISAGREEMENT' if 'DISAGREE' in states else
            'CONSISTENT_WHERE_OBSERVED' if 'AGREE' in states else 'NOT_COMPARABLE'}


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
    candidate_roots = set().union(*(set(p['candidate_root_ids']) for p in series))
    docks = dock_sources(doc.get('docks'), candidate_roots, utc(now['at']))
    # Additive fields only: red_metrics, docks and dock_consistency never alter the stop decision.
    return {'schema':'codepurple.scale-dock.receipt.v1',
        'red_metrics':red_metrics(series), 'docks':docks,
        'dock_consistency':dock_consistency(docks),
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
        'STOP --> HOLD["HOLD / independent human admission"]']
    for node, label, name, target in (('BD','Issue / PR BD queue','issue_bd','LDAB'),
            ('EVR','EVERRED root census','everred','ROOT'),
            ('CPC','CODE PURPLE lift census','code_purple','QUEUE'),
            ('PPM','P-process mode','p_process','QUEUE'),
            ('XW','G5 gap crosswalk','crosswalk','PROOF')):
        lines.append(f'{node}["{label} - {receipt["docks"][name]["status"]}"] -.-> {target}')
    lines += ['XC{"Dock consistency: '+receipt['dock_consistency']['state']+'"}',
        'EVR -.-> XC', 'CPC -.-> XC', 'PPM -.-> XC', 'XC -.-> STOP',
        'classDef dock fill:#ede9fe,stroke:#7c3aed,color:#4c1d95',
        'class BD,EVR,CPC,PPM,XW,XC dock',
        'classDef obs fill:#dbeafe,stroke:#2563eb,color:#1e3a8a',
        'classDef act fill:#dcfce7,stroke:#16a34a,color:#14532d',
        'classDef gate fill:#fef3c7,stroke:#d97706,color:#78350f',
        'classDef hold fill:#fee2e2,stroke:#dc2626,color:#7f1d1d',
        'class SRC,LDAB,ROOT,DAG obs','class READ,WRITE,MATH,TEST act',
        'class QUEUE,STOP gate','class HOLD hold']
    return '\n'.join(lines)+'\n'


HEADLINES = {
    'everred':('signature_match_rate','roots_open','roots_open_by_priority','root_closure_rate',
               'recurrence_rate','control_plane_red_rate','e1_red_p0_probes','scale_dock_roots_unmatched'),
    'code_purple':('incident','lifted','lift_unmet','gate_green_rate','red_merge_rate',
                   'merged_since_unblock','follow_ups_open'),
    'p_process':('modes','code_purple_repos','open_roots','worst_priority','ruleset_red_rate'),
    'issue_bd':('scope','open_items','open_issues','red_pr_rate','unknown_pr_rate',
                'manifestations_per_red_pr','queue_p95_seconds','private_qps_open_issues'),
    'crosswalk':('eligible_cells','historical_breadth','current_breadth','gap_packets',
                 'native_identity_rate','archive_bytes_verified','root_bound')}


def shown(value, key=''):
    if value is None: return 'UNKNOWN'
    if key.endswith(('_rate','_breadth')) and type(value) in (int, float): return f'{100*value:.1f}%'
    if isinstance(value, dict): return ', '.join(f'{k}={v}' for k, v in value.items()) or 'none'
    if isinstance(value, list): return ', '.join(map(str, value)) or 'none'
    return str(value)


def render_html(r):
    latest = r['pulses'][-1]
    red, last_red = r['red_metrics'], r['red_metrics']['pulses'][-1]
    cols=('id','family','priority','state','native_tuple_complete','declared_descendants')
    body=''.join('<tr>'+''.join('<td>'+html.escape(str(f.get(c) if f.get(c) is not None else 'UNKNOWN'))+'</td>' for c in cols)+'</tr>'
                 for f in r['ranked'])
    cards=[('Manifestations',f"{latest['observed']}/{latest['eligible']}"),
           ('Candidate root IDs',str(len(latest['candidate_root_ids']))),
           ('Distinct fingerprints',str(latest['fingerprints'])),
           ('Repeated occurrences',str(latest['repeated_fingerprint_occurrences'])),
           ('Complete native tuples',str(latest['native_tuple_complete'])),
           ('Queue age p95',str(latest['queue_age_p95_seconds'] if latest['queue_age_p95_seconds'] is not None else 'UNKNOWN')),
           ('Red now',f"{last_red['red']}/{latest['eligible']}"),
           ('Red burndown',str(red['red_burndown'])),
           ('Root-red',str(len(last_red['root_red']))),
           ('Unrooted red',str(last_red['unrooted_red'])),
           ('First-red step known',shown(last_red['red_first_step_known_rate'],'_rate')),
           ('EVERRED in window',f"{len(red['everred_in_window'])}/{red['window_pulses']} pulses"),
           ('Recovery rate',shown(red['recovery_rate'],'_rate')),
           ('Regression rate',shown(red['regression_rate'],'_rate'))]
    tile=''.join(f'<article><span>{html.escape(k)}</span><strong>{html.escape(v)}</strong></article>' for k,v in cards)
    moves=''.join('<tr>'+''.join('<td>'+html.escape(x)+'</td>' for x in (
        f"N{m['before_n']}→N{m['after_n']}", shown(m['new_first_reds']), shown(m['recoveries']),
        shown(m['regressions']), shown(m['persisting_reds'])))+'</tr>' for m in red['transitions'])
    docked=''
    for name, d in r['docks'].items():
        detail=('; '.join(f'{k.replace("_"," ")}: {shown(d["metrics"].get(k),k)}' for k in HEADLINES[name])
                if d['metrics'] else 'not docked: UNKNOWN, never zero')
        age=d.get('age_hours_at_latest_pulse')
        docked+=('<tr>'+''.join('<td>'+html.escape(x)+'</td>' for x in (name, d['status'], detail,
                 shown(age)+(' (stale)' if d.get('stale') else '')))+'</tr>')
    checks=''.join('<tr>'+''.join('<td>'+html.escape(shown(c[k]))+'</td>' for k in ('check','left','right','state'))+'</tr>'
                   for c in r['dock_consistency']['checks'])
    style='''<style>:root{color-scheme:light dark;font:15px system-ui,sans-serif}body{max-width:1140px;margin:auto;padding:20px}h1{font-size:1.6rem}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}article{border:1px solid #7d8ba0;border-radius:12px;padding:14px}article span{display:block;color:#7b8da0}strong{font-size:1.45rem}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:9px;border-bottom:1px solid #7d8ba0}th{font-size:.9rem} .wide{overflow:auto} .hold{color:#b85d18}p{line-height:1.5}</style>'''
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>CODE PURPLE — scale dock</title>'+style+'<body><h1>CODE PURPLE · Scale Dock</h1>'
        '<p>Read-only MIP / SPINE / LDAB · '+html.escape(r['observation_class'])+' · no remote dispatch</p>'
        '<div class="cards">'+tile+'</div><h2>Root-family dependency priority</h2><div class="wide"><table><thead><tr>'
        +''.join('<th>'+c.replace('_',' ').title()+'</th>' for c in cols)+'</tr></thead><tbody>'+body+'</tbody></table></div>'
        '<h2>First-red / root-red transitions</h2><div class="wide"><table><thead><tr><th>Pulse</th><th>New first reds</th>'
        '<th>Recoveries</th><th>Regressions</th><th>Persisting reds</th></tr></thead><tbody>'+moves+'</tbody></table></div>'
        '<h2>Docked metrics</h2><div class="wide"><table><thead><tr><th>Source</th><th>Status</th><th>Metrics</th>'
        '<th>Age (h)</th></tr></thead><tbody>'+docked+'</tbody></table></div>'
        '<h2>Cross-source consistency</h2><p class="hold">'+html.escape(r['dock_consistency']['state'])+'</p>'
        '<div class="wide"><table><thead><tr><th>Check</th><th>Left</th><th>Right</th><th>State</th></tr></thead><tbody>'
        +checks+'</tbody></table></div>'
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
    for name, schema in DOCK_SCHEMAS.items():
        p.add_argument('--'+name.replace('_','-'),type=Path,
                       help=f'read-only {schema} projection to dock')
    args=p.parse_args()
    doc=json.loads(args.input.read_text(encoding='utf-8'))
    for name in DOCK_SCHEMAS:
        path=getattr(args,name)
        if path is not None:
            require(isinstance(doc,dict),'series schema')
            doc.setdefault('docks',{})[name]=json.loads(path.read_text(encoding='utf-8'))
    report=evaluate(doc)
    manifest=emit(report,args.out,args.source_sha)
    print(json.dumps({'stop':report['stop_decision'],'observed':report['pulses'][-1]['observed'],
       'eligible':report['pulses'][-1]['eligible'],'manifest':hashlib.sha256(encoded(manifest)).hexdigest(),
       'docked':sorted(k for k,v in report['docks'].items() if v['metrics']),
       'dock_consistency':report['dock_consistency']['state'],
       'native_dispatch':False},sort_keys=True))

if __name__=='__main__':main()
