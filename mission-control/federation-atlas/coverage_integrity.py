#!/usr/bin/env python3
"""CODE PURPLE read-only coverage integrity review incubator for the Atlas publisher.

This module never dispatches jobs, changes code, infers QPS acceptance, or turns
historical PR-head results into current-main coverage. It deliberately refuses
to make a comparison across different source file/blob or counter populations.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import re
from pathlib import Path
from xml.etree import ElementTree as ET

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'COVERAGE_INTEGRITY_OBSERVATIONS_v1.json'
SCHEMA = 'codepurple.coverage_integrity.observations.v1'
OUTPUT_SCHEMA = 'codepurple.coverage_integrity.snapshot.v1'
HEX40 = re.compile(r'^[a-f0-9]{40}$')
HEX64 = re.compile(r'^[a-f0-9]{64}$')
FILES = ('index.html', 'snapshot.json', 'dependency.mmd', 'sipoc.mmd',
         'spline.mmd', 'graph-light.svg', 'graph-dark.svg')


def fail(message):
    raise ValueError(message)


def num(value, label):
    if type(value) is not int or value < 0:
        fail('INVALID_COUNTER:' + label)
    return value


def ratio(n, d):
    return round(100 * n / d, 4) if d else None


def sum_axis(rows, axis):
    covered, eligible = 0, 0
    for row in rows:
        c, e = row[axis]
        num(c, axis + '.covered'); num(e, axis + '.eligible')
        if c > e:
            fail('COVERED_EXCEEDS_ELIGIBLE:' + row['path'])
        covered += c; eligible += e
    return [covered, eligible]


def validate(source):
    if not isinstance(source, dict) or source.get('schema') != SCHEMA:
        fail('SCHEMA_DRIFT')
    authority = source.get('authority', {})
    if not (authority.get('merge_admission') == 'HOLD'
            and authority.get('engineering_acceptance') == 'WITHHELD'
            and authority.get('security_waiver') == 'NONE'
            and authority.get('formal_credit_delta') == 0
            and authority.get('is_six_repo_canonical_breadth') is False):
        fail('FALSE_AUTHORITY')
    for repo, head in source.get('repo_heads', {}).items():
        if not repo.startswith('GBOGEB/') or not HEX40.fullmatch(head):
            fail('INVALID_REPO_HEAD')
    observations = source.get('observations', [])
    if not isinstance(observations, list) or not observations:
        fail('NO_HISTORICAL_OBSERVATIONS')
    ids = set()
    for o in observations:
        if o.get('id') in ids:
            fail('DUPLICATE_OBSERVATION')
        ids.add(o.get('id'))
        if not HEX40.fullmatch(o.get('head_sha', '')):
            fail('INVALID_MEASUREMENT_HEAD')
        if o.get('cohort_type') != 'HISTORICAL_PR_HEAD':
            fail('UNSUPPORTED_MEASUREMENT_STATE')
        if not o.get('population_key') or not o.get('repository'):
            fail('UNBOUND_POPULATION')
        rows = o.get('rows')
        if not isinstance(rows, list) or not rows:
            fail('MISSING_FILE_ROWS')
        names = set()
        for r in rows:
            p = r.get('path', '')
            if (not isinstance(p, str) or not p.endswith('.py') or '\\' in p
                    or p.startswith('/') or '..' in p.split('/') or p in names):
                fail('UNSAFE_OR_DUPLICATE_PATH')
            names.add(p)
            if not HEX40.fullmatch(r.get('source_blob', '')):
                fail('MISSING_GIT_BLOB')
        for axis in ('statement', 'branch'):
            sum_axis(rows, axis)
        ev = o.get('lineage', {})
        for key in ('run_id', 'run_attempt', 'job_id', 'artifact_id'):
            if num(ev.get(key), key) <= 0:
                fail('MISSING_NATIVE_ID:' + key)
        if (ev.get('job_status') != 'success' or
                num(ev.get('job_executed_steps'), 'steps') == 0 or
                ev.get('zip_crc_verified') is not True or
                not HEX64.fullmatch(ev.get('artifact_zip_sha256', '')) or
                not HEX64.fullmatch(ev.get('artifact_member_sha256', ''))):
            fail('HISTORICAL_ZIP_EVIDENCE_INCOMPLETE')
    for inv in source.get('inventory_projections', []):
        if not HEX40.fullmatch(inv.get('head_sha', '')):
            fail('INVENTORY_HEAD')
        names = inv.get('candidate_source_paths')
        if not isinstance(names, list) or len(names) != len(set(names)):
            fail('INVALID_INVENTORY')
        if inv.get('measurement_status') == 'CURRENT_MAIN_COVERAGE_UNKNOWN':
            if inv.get('measured_source_paths') is not None:
                fail('INVENTED_CURRENT_MEASURED_COHORT')
    for o in source.get('other_scopes', []):
        for axis in ('statement', 'branch'):
            value = o.get(axis)
            if value is not None:
                if not isinstance(value, list) or len(value) != 2:
                    fail('INVALID_OTHER_SCOPE')
                c, e = (num(x, axis) for x in value)
                if c > e: fail('INVALID_OTHER_SCOPE_DENOMINATOR')
    breadth = source.get('federation_breadth', {})
    if (breadth.get('canonical_pr') != 531 or
        breadth.get('current_validated_breadth') is not None or
        breadth.get('authenticated_fresh') is not None):
        fail('FAKE_FEDERATION_ATTESTATION')
    return source


def measure(o):
    rows = o['rows']
    statements = sum_axis(rows, 'statement')
    branches = sum_axis(rows, 'branch')
    eligible_statement_rows = [r for r in rows if r['statement'][1] > 0]
    eligible_branch_rows = [r for r in rows if r['branch'][1] > 0]
    if not eligible_statement_rows:
        fail('NO_ELIGIBLE_STATEMENT_POPULATION')
    zeros = [r['path'] for r in rows if r['statement'][1] > 0 and r['statement'][0] == 0]
    zeros_branch = [r['path'] for r in rows if r['branch'][1] > 0 and r['branch'][0] == 0]
    return {'id': o['id'], 'repository': o['repository'], 'head_sha': o['head_sha'],
            'population_key': o['population_key'], 'source_file_count': len(rows),
            'covered_statements': statements, 'covered_branches': branches,
            'statement_pct': ratio(*statements), 'branch_pct': ratio(*branches),
            'zero_statement_files': zeros, 'zero_branch_files': zeros_branch,
            'minimum_statement_pct': min(ratio(*r['statement']) for r in eligible_statement_rows),
            'minimum_branch_pct': min((ratio(*r['branch']) for r in eligible_branch_rows), default=None),
            'measured_zero_gate': 'FAIL' if zeros or zeros_branch else 'PASS_MEASURED_COHORT_ONLY',
            'measurement_state': 'HISTORICAL_PR_HEAD_ZIP_VERIFIED',
            'artifact': o['lineage']}


def compare(a, b):
    """Compare exact source module/blob and eligible statement/branch populations.

    A changed test set is allowed and identified; new main is never assumed.
    """
    checks = ('repository', 'population_key', 'tool', 'tool_version', 'python')
    if any(a.get(k) != b.get(k) for k in checks):
        return {'state': 'INCOMPARABLE', 'reason': 'COHORT_METADATA_DRIFT', 'accepted_gain': None}
    left = {r['path']: r for r in a['rows']}
    right = {r['path']: r for r in b['rows']}
    if set(left) != set(right):
        return {'state': 'INCOMPARABLE', 'reason': 'SOURCE_FILE_SET_DRIFT', 'accepted_gain': None}
    for name in left:
        if (left[name]['source_blob'] != right[name]['source_blob'] or
            left[name]['statement'][1] != right[name]['statement'][1] or
            left[name]['branch'][1] != right[name]['branch'][1]):
            return {'state': 'INCOMPARABLE', 'reason': 'BLOB_OR_ELIGIBLE_DENOMINATOR_DRIFT',
                    'accepted_gain': None}
    old, new = measure(a), measure(b)
    per_file = [{'file': name,
                 'statement_delta': right[name]['statement'][0] - left[name]['statement'][0],
                 'branch_delta': right[name]['branch'][0] - left[name]['branch'][0],
                 'source_blob': left[name]['source_blob']}
                for name in sorted(left)]
    return {'state': 'SOURCE_MATCHED_DIFFERENT_TEST_EXECUTION',
            'reason': 'HISTORICAL_PR_HEADS_NOT_CURRENT_MAIN',
            'source_files': len(left),
            'statement_delta': new['covered_statements'][0] - old['covered_statements'][0],
            'branch_delta': new['covered_branches'][0] - old['covered_branches'][0],
            'statement_delta_pp': round(new['statement_pct'] - old['statement_pct'], 4),
            'branch_delta_pp': round(new['branch_pct'] - old['branch_pct'], 4),
            'per_file': per_file, 'accepted_gain': None,
            'formal_credit_delta': 0}


def summarize(source):
    validate(source)
    obs = source['observations']
    comparison = compare(obs[0], obs[1])
    if comparison['state'] != 'SOURCE_MATCHED_DIFFERENT_TEST_EXECUTION':
        fail('EXPECTED_HISTORICAL_PAIR_NO_LONGER_MATCHES')
    inventory = source['inventory_projections'][0]
    historic = {r['path'] for r in obs[1]['rows']}
    latest = set(inventory['candidate_source_paths'])
    added = sorted(latest - historic)
    missing = sorted(historic - latest)
    other = []
    for group in source['other_scopes']:
        c = dict(group)
        c['statement_pct'] = ratio(*c['statement']) if c.get('statement') else None
        c['branch_pct'] = ratio(*c['branch']) if c.get('branch') else None
        if c['id'] == 'abacus-main-historical':
            c['same_denominator_remaining_to_75pct'] = max(0, math.ceil(.75 * c['statement'][1]) - c['statement'][0])
        other.append(c)
    return {'schema': OUTPUT_SCHEMA, 'source_evidence_date': source['source_evidence_date'],
            'observations': [measure(o) for o in obs],
            'comparison': comparison,
            'current_inventory': {'repo': inventory['repository'],
                'head_sha': inventory['head_sha'], 'candidate_file_count': len(latest),
                'introduced_since_historical': added, 'removed_since_historical': missing,
                'introduced_count': len(added),
                'currently_measured_count': None, 'zero_coverage_count': None,
                'current_main_statement': None, 'current_main_branch': None,
                'measurement_state': inventory['measurement_status'],
                'activity_qualification': inventory['active_status']},
            'other_scopes': other,
            'federation_breadth': source['federation_breadth'],
            'current_repo_heads': source['repo_heads'],
            'telemetry': source['telemetry'],
            'authority': source['authority'],
            'portfolio_total_coverage': None, 'portfolio_status': 'INCOMPARABLE_DENOMINATORS',
            'new_roots_confirmed': None, 'accepted_root_closures': None}


NODES = [
    ('source','Source inventory',10,12,'source'),
    ('head','Exact SHA + cohort',255,12,'source'),
    ('runner','Runner > 0 steps',500,12,'gate'),
    ('zip','ZIP bytes + CRC',745,12,'proof'),
    ('measure','Measured files',990,12,'proof'),
    ('zero','Missing / zero gate',990,155,'gate'),
    ('match','Matched N/N+1',745,155,'proof'),
    ('ledger','Metric + BD ledger',500,155,'proof'),
    ('viewer','Method Atlas view',255,155,'viewer'),
    ('hold','Owner / admission HOLD',10,155,'blocked'),
]
EDGES = [('source','head','solid'),('head','runner','solid'),('runner','zip','solid'),
         ('zip','measure','solid'),('measure','zero','solid'),('zero','match','solid'),
         ('match','ledger','solid'),('ledger','viewer','solid'),('viewer','hold','dashed')]
COLORS = {
'light': {'bg':'#F7F9FC','ink':'#1B2B42','line':'#617185','source':('#E4F0FF','#3C68A7'),
 'proof':('#DDF4E4','#258053'),'gate':('#FFF0C6','#9B6A18'),
 'viewer':('#EEE6F9','#7754A2'),'blocked':('#FCE5E8','#B33849')},
'dark': {'bg':'#0D1728','ink':'#F0F4FC','line':'#A1B4C9','source':('#203857','#87B8FC'),
 'proof':('#1C4335','#78D7A2'),'gate':('#4A3921','#F4CE84'),
 'viewer':('#3C2E59','#D4B0FF'),'blocked':('#492B36','#F4A6B0')}}


def svg_graph(theme):
    p = COLORS[theme]
    nodes = {n[0]: n for n in NODES}
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1240" height="270" viewBox="0 0 1240 270" role="img" aria-label="CODE PURPLE source-bound dependency graph ({theme})">',
           f'<rect width="1240" height="270" fill="{p["bg"]}"/>',
           f'<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0 0 L6 3 L0 6 Z" fill="{p["line"]}"/></marker></defs>']
    for src, dest, mode in EDGES:
        a, b = nodes[src], nodes[dest]
        x1, y1 = a[2] + 105, a[3] + 28
        x2, y2 = b[2] + 105, b[3] + 28
        if y1 == y2:
            x1 = a[2] + (210 if a[2] < b[2] else 0)
            x2 = b[2] + (0 if a[2] < b[2] else 210)
        else:
            x1 = a[2] + 105; x2 = b[2] + 105
        dash = ' stroke-dasharray="5 5"' if mode == 'dashed' else ''
        out.append(f'<path data-edge="{src}-{dest}" d="M{x1} {y1} L{x2} {y2}" fill="none" stroke="{p["line"]}" stroke-width="2"{dash} marker-end="url(#arrow)"/>')
    for key, label, x, y, role in NODES:
        fill, stroke = p[role]
        out.extend([f'<g data-node="{key}" data-role="{role}">',
                    f'<rect x="{x}" y="{y}" width="210" height="56" rx="12" fill="{fill}" stroke="{stroke}" stroke-width="2"/>',
                    f'<text x="{x+105}" y="{y+33}" fill="{p["ink"]}" font-size="13" font-weight="600" font-family="system-ui,Arial" text-anchor="middle">{html.escape(label)}</text></g>'])
    out.append('</svg>')
    return ''.join(out)


def mermaid():
    roles = {key: role for key, _, *_pos, role in NODES}
    labels = {key: label for key, label, *_rest in NODES}
    main = ['flowchart LR']
    for key in roles:
        main.append(f'  {key}["{labels[key]}"]')
    for a, b, mode in EDGES:
        main.append(f'  {a} {"-.->" if mode == "dashed" else "-->"} {b}')
    main.extend([f'  class {",".join(k for k,v in roles.items() if v==role)} {role}' for role in ('source','proof','gate','viewer','blocked')])
    palette = COLORS['light']
    for role in ('source','proof','gate','viewer','blocked'):
        fill, stroke = palette[role]
        main.append(f'  classDef {role} fill:{fill},stroke:{stroke},color:#13263A,stroke-width:2px')
    sipoc = '''flowchart LR
  SUP["S | Git owner, archives, exact SHA"] --> IN["I | Inventory, coverage JSON, ZIP, native jobs"]
  IN --> PROC["P | Validate, join, match, classify, measure"]
  PROC --> OUT["O | Ledger, BD queue, source-bound DAG, UNKNOWNs"]
  OUT --> CONS["C | Method Atlas, QPS owner, security reviewer"]
  CONS -.->|typed feedback; not authority transfer| SUP
  classDef owner fill:#E4F0FF,stroke:#3C68A7,color:#163D6C
  classDef process fill:#DDF4E4,stroke:#258053,color:#15482F
  classDef hold fill:#FFF0C6,stroke:#9B6A18,color:#67470F
  class SUP,IN owner
  class PROC,OUT process
  class CONS hold
'''
    spline = '''flowchart LR
  N1["#2016 754/852, 270/304"] --> N2["#2017 763/852, 277/304"]
  N2 -.->|no current-main measurement| N3["Current main: UNKNOWN"]
  N4["#2014 N6: 12-file different cohort"] -.->|incomparable| N3
  classDef measured fill:#DDF4E4,stroke:#258053,color:#15482F
  classDef unknown fill:#FFF0C6,stroke:#9B6A18,color:#67470F
  classDef other fill:#E4F0FF,stroke:#3C68A7,color:#163D6C
  class N1,N2 measured
  class N3 unknown
  class N4 other
'''
    return {'dependency.mmd':'\n'.join(main)+'\n', 'sipoc.mmd':sipoc, 'spline.mmd':spline}


def pct_label(value):
    return 'UNKNOWN' if value is None else f'{value:.2f}%'


def render_html(model):
    from html import escape as e
    a,b = model['observations']; diff = model['comparison']; inv=model['current_inventory']
    rows = []
    for r in diff['per_file']:
        rowa = next(x for x in model['_raw_files_a'] if x['path'] == r['file'])
        rowb = next(x for x in model['_raw_files_b'] if x['path'] == r['file'])
        pct1 = ratio(*rowa['statement']); pct2 = ratio(*rowb['statement'])
        branch1 = ratio(*rowa['branch']); branch2 = ratio(*rowb['branch'])
        delta = r['statement_delta']
        severity = 'warn' if delta < 0 else ('good' if delta > 0 else 'muted')
        rows.append(f'<tr data-repo="GBOGEB/cryoplant-project"><td title="{e(r["source_blob"])}">{e(r["file"].split("/")[-1])}</td><td>{pct_label(pct1)} &rarr; {pct_label(pct2)}</td><td>{pct_label(branch1)} &rarr; {pct_label(branch2)}</td><td class="{severity}">{delta:+d} st / {r["branch_delta"]:+d} br</td><td><code>{e(r["source_blob"][:10])}...</code></td></tr>')
    others=[]
    for x in model['other_scopes']:
        st=x.get('statement'); br=x.get('branch');
        extra = f' · +{x["same_denominator_remaining_to_75pct"]} covered statements needed at fixed denominator' if 'same_denominator_remaining_to_75pct' in x else ''
        others.append(f'<tr data-repo="{e(x["repository"])}"><td>{e(x["repository"])}</td><td>{e(x["scope"])}</td><td>{(str(st[0])+"/"+str(st[1])) if st else "UNKNOWN"}</td><td>{pct_label(x["statement_pct"])}</td><td>{(str(br[0])+"/"+str(br[1])) if br else "UNKNOWN"}</td><td>{pct_label(x["branch_pct"])}</td><td>{e(x["evidence"])}{e(extra)}</td></tr>')
    abacus = next(x for x in model['other_scopes'] if x['id'] == 'abacus-main-historical')
    math = next(x for x in model['other_scopes'] if x['id'] == 'ggmath-w33-historical')
    known_cards = [
        ('GBOGEB/cryoplant-project','QPS #2016 statements',pct_label(a['statement_pct']),f'{a["covered_statements"][0]}/{a["covered_statements"][1]} · 10 files · historical'),
        ('GBOGEB/cryoplant-project','QPS #2017 statements',pct_label(b['statement_pct']),f'{b["covered_statements"][0]}/{b["covered_statements"][1]} · +{diff["statement_delta"]} covered · historical'),
        ('GBOGEB/cryoplant-project','QPS #2017 branches',pct_label(b['branch_pct']),f'{b["covered_branches"][0]}/{b["covered_branches"][1]} · +{diff["branch_delta"]} covered'),
        ('GBOGEB/cryoplant-project','Later QPS source inventory',str(inv['candidate_file_count']),f'{inv["introduced_count"]} added; full current coverage UNKNOWN'),
        ('GBOGEB/cryoplant-project','QPS historical zero files',str(len(b['zero_statement_files'])),f'10-file measured scope · min {pct_label(b["minimum_statement_pct"])}'),
        ('GBOGEB/ABACUS','ABACUS statements',pct_label(abacus['statement_pct']),f'{abacus["statement"][0]}/{abacus["statement"][1]} · historical broad main'),
        ('GBOGEB/ABACUS','ABACUS branches',pct_label(abacus['branch_pct']),f'{abacus["branch"][0]}/{abacus["branch"][1]} · historical broad main'),
        ('GBOGEB/ABACUS','ABACUS 75% gap',str(abacus['same_denominator_remaining_to_75pct']), 'Additional covered statements at same denominator'),
        ('GBOGEB/pipeline-automation-hub','Current federation breadth','UNKNOWN','Historical #531 6/42; no fresh authenticated 42-cell proof'),
        ('GBOGEB/gg_MATH','gg_MATH W33 focused',pct_label(math['statement_pct']),f'{math["statement"][0]}/{math["statement"][1]} · one historical module, not repo total'),
        ('GBOGEB/CODEX','CODEX current coverage','UNKNOWN','No current-main source-bound numerator or denominator')]
    cards=''.join(f'<article class="card" data-repo="{e(repo)}"><div class="eyebrow">{e(label)}</div><strong>{e(value)}</strong><small>{e(note)}</small></article>' for repo,label,value,note in known_cards)
    current=[]
    for name,sha in sorted(model['current_repo_heads'].items()):
        current.append(f'<tr data-repo="{e(name)}"><td>{e(name)}</td><td><code>{e(sha)}</code></td><td>Current head readback, coverage not inferred</td></tr>')
    intro=' · '.join(e(x.split('/')[-1]) for x in inv['introduced_since_historical'])
    d=diff['per_file']; changes='; '.join(f'{x["file"].split("/")[-1]} {x["statement_delta"]:+d}/{x["branch_delta"]:+d}' for x in d if x['statement_delta'] or x['branch_delta'])
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="dark light"><meta name="referrer" content="no-referrer"><title>CODE PURPLE | Coverage Integrity</title><style>
:root{{--bg:#0d1728;--surface:#15263a;--surface2:#1c3048;--ink:#f0f4fa;--muted:#a9c0d6;--line:#36516b;--accent:#b7a2ef;--good:#78daa8;--warn:#ffc98f;--danger:#f3a7b3}}
@media(prefers-color-scheme:light){{:root{{--bg:#f6f8fb;--surface:#fff;--surface2:#ebf1f8;--ink:#1b2b42;--muted:#52647a;--line:#ccd5e1;--accent:#67429e;--good:#176943;--warn:#88620b;--danger:#ae2438}}}}
html[data-theme=light]{{--bg:#f6f8fb;--surface:#fff;--surface2:#ebf1f8;--ink:#1b2b42;--muted:#52647a;--line:#ccd5e1;--accent:#67429e;--good:#176943;--warn:#88620b;--danger:#ae2438}}
html[data-theme=dark]{{--bg:#0d1728;--surface:#15263a;--surface2:#1c3048;--ink:#f0f4fa;--muted:#a9c0d6;--line:#36516b;--accent:#b7a2ef;--good:#78daa8;--warn:#ffc98f;--danger:#f3a7b3}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.55 system-ui,-apple-system,Segoe UI,sans-serif}}main,header{{max-width:1380px;margin:0 auto;padding:22px}}header{{padding-top:38px}}h1{{font-size:clamp(1.85rem,3vw,3rem);margin:5px 0}}h2{{font-size:1.25rem}}h3{{font-size:1rem}}p,.muted,small{{color:var(--muted)}}a{{color:var(--accent)}}code{{overflow-wrap:anywhere;font-size:12px}}.eyebrow{{font-size:11px;text-transform:uppercase;letter-spacing:.075em;color:var(--muted)}}.toolbar{{display:flex;flex-wrap:wrap;gap:10px;margin:20px 0}}button,select{{border:1px solid var(--line);background:var(--surface);color:var(--ink);padding:9px 12px;border-radius:8px;font:inherit}}button:focus-visible,select:focus-visible,a:focus-visible{{outline:3px solid var(--accent);outline-offset:3px}}.cards{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}}.card,.panel{{background:var(--surface);border:1px solid var(--line);border-radius:13px;padding:19px}}.card strong{{display:block;font-size:1.8rem;margin:3px 0}}.card small{{display:block}}.panel{{margin:20px 0}}.note{{border-left:4px solid var(--warn);padding-left:15px}}.good{{color:var(--good)}}.warn{{color:var(--warn)}}.danger{{color:var(--danger)}}.scroll{{overflow:auto;max-width:100%}}table{{width:100%;border-collapse:collapse;font-size:12px;min-width:800px}}th,td{{padding:10px 12px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}th{{background:var(--surface2)}}tr[hidden],article[hidden]{{display:none}}.graph{{width:100%;overflow:auto;background:var(--surface2);border-radius:10px;padding:8px}}.graph img{{width:100%;min-width:860px}}.legend{{display:flex;flex-wrap:wrap;gap:14px;font-size:12px}}.dot{{display:inline-block;width:10px;height:10px;margin-right:5px;border-radius:50%}}.source{{background:#538fd3}}.proof{{background:#4aae80}}.gate{{background:#d9a843}}.blocked{{background:#db6477}}.viewer{{background:#9f82d3}}.fine{{font-size:12px}}footer{{padding:20px 0;border-top:1px solid var(--line);color:var(--muted)}}@media(max-width:850px){{.cards{{grid-template-columns:repeat(2,1fr)}}}}@media(max-width:520px){{.cards{{grid-template-columns:1fr}}}}
</style></head><body><header><div class="eyebrow">CODE PURPLE / BREAD &amp; BUTTER / JADE / Method Atlas</div><h1>Coverage integrity &amp; federation ledger</h1><p>Read-only, exact-source historical observations. Portfolio sums and current-main uplift are intentionally withheld when scopes are incompatible.</p><div class="toolbar"><label for="repo">Repository</label><select id="repo"><option value="ALL">All repositories</option><option value="GBOGEB/cryoplant-project">QPS</option><option value="GBOGEB/ABACUS">ABACUS</option><option value="GBOGEB/pipeline-automation-hub">Mission Control</option><option value="GBOGEB/CODEX">CODEX</option><option value="GBOGEB/gg_MATH">gg_MATH</option></select><label for="theme">Appearance</label><select id="theme"><option value="system">System</option><option value="light">Light</option><option value="dark">Dark</option></select></div></header><main><section class="cards">{cards}</section><section class="panel"><h2>Scope-bound progress, not mixed denominators</h2><p>Historical #2016 &rarr; #2017: <strong>+{diff['statement_delta']} statements ({diff['statement_delta_pp']:+.2f} pp), +{diff['branch_delta']} branches ({diff['branch_delta_pp']:+.2f} pp)</strong> with ten identical production Git blobs and denominators. Different PR-head test executions: <strong>not current-main coverage</strong>.</p><p class="note">Compensating drift: {e(changes)}. A global increase does not override a declining module.</p><p>Current QPS inventory candidates: <strong>{inv['candidate_file_count']}</strong>, newly introduced since these historical heads: {intro}. Measured source count and zero-covered source count on current main: <strong>UNKNOWN</strong>.</p><div class="scroll"><table><thead><tr><th>Module</th><th>Statement % N &rarr; N+1</th><th>Branch % N &rarr; N+1</th><th>Delta</th><th>Source blob</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div></section><section class="panel"><h2>Independent source populations</h2><p>QPS N6, ABACUS broad main, gg_MATH focused source and CODEX are deliberately not aggregated.</p><div class="scroll"><table><thead><tr><th>Repository</th><th>Population key</th><th>Statement n/d</th><th>Statement %</th><th>Branch n/d</th><th>Branch %</th><th>Evidence class</th></tr></thead><tbody>{''.join(others)}</tbody></table></div></section><section class="panel"><h2>Typed dependency DAG</h2><div class="legend"><span><i class="dot source"></i>Source</span><span><i class="dot proof"></i>Measurement</span><span><i class="dot gate"></i>Gate requires proof</span><span><i class="dot blocked"></i>HOLD</span><span><i class="dot viewer"></i>View only</span><span>Dashed edge = supporting, not authority</span></div><div class="graph"><img id="graph" src="graph-dark.svg" alt="Ten-node source verification and coverage-integrity DAG, with evidence and owner gates"></div><p class="fine">Source: <a href="dependency.mmd">Dependency Mermaid</a> · <a href="sipoc.mmd">SIPOC Mermaid</a> · <a href="spline.mmd">N/N+1 SPLINE</a>. Both SVG themes are generated from the same typed graph.</p></section><section class="panel"><h2>Current heads &amp; telemetry</h2><div class="scroll"><table><thead><tr><th>Repository</th><th>Readback head SHA</th><th>Coverage interpretation</th></tr></thead><tbody>{''.join(current)}</tbody></table></div><p class="note">QPS <a href="https://github.com/GBOGEB/cryoplant-project/pull/2030">#2030</a> merged despite 0 submitted reviews. Prior exact-head <a href="https://github.com/GBOGEB/cryoplant-project/actions/runs/39265626258">qualification run</a> has 0 executed steps in 4 failed jobs. Runner root cause still UNKNOWN; gate source publication is not native verification.</p><p>Canonical #531 historical breadth <strong>6/42</strong>; authenticated current 42-cell proof <strong>UNKNOWN</strong>. Worker-hours UNKNOWN. M1 PARTIAL, M2/M3 HOLD. PCA and BT not qualified.</p><p class="fine"><a href="snapshot.json">Machine-readable source-typed ledger</a> · <a href="manifest.json">Verified rendered-member SHA-256 manifest</a></p></section><footer>Publisher role: EXISTING_METHOD_ATLAS_ONLY. No dispatch or source authority transfer. MERGE_ADMISSION=HOLD; ENGINEERING_ACCEPTANCE=WITHHELD; SECURITY_WAIVER=NONE; FORMAL_CREDIT_DELTA=0.</footer></main><script>
(function(){{'use strict';var root=document.documentElement,theme=document.getElementById('theme'),repo=document.getElementById('repo'),graph=document.getElementById('graph');function applyTheme(){{var t=theme.value;root.dataset.theme=t==='system'?'':t;var dark=(t==='dark'||(t==='system'&&window.matchMedia&&window.matchMedia('(prefers-color-scheme: dark)').matches));graph.src=dark?'graph-dark.svg':'graph-light.svg'}}function applyRepo(){{var r=repo.value;document.querySelectorAll('[data-repo]').forEach(function(n){{n.hidden=r!=='ALL'&&n.dataset.repo!==r}})}}theme.addEventListener('change',applyTheme);repo.addEventListener('change',applyRepo);if(window.matchMedia)window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change',applyTheme);applyTheme();applyRepo()}})();
</script></body></html>'''


def build(source=SOURCE, out=None, presentation_head=None):
    if out is None:
        fail('OUTPUT_REQUIRED')
    if not isinstance(presentation_head, str) or not HEX40.fullmatch(presentation_head):
        fail('PUBLISHER_EXACT_HEAD_REQUIRED')
    source = Path(source); out = Path(out)
    raw = source.read_bytes()
    data = json.loads(raw)
    model = summarize(data)
    model['presentation_head_sha'] = presentation_head
    model['source_json_sha256'] = hashlib.sha256(raw).hexdigest()
    model['authority'] = {'merge_admission':'HOLD','engineering_acceptance':'WITHHELD',
                          'security_waiver':'NONE','formal_credit_delta':0,
                          'is_native_current_attestation':False,'run_dispatch':False}
    # Only for HTML rendering; these file rows are historical, never presented as main.
    render_model = dict(model, _raw_files_a=data['observations'][0]['rows'],
                        _raw_files_b=data['observations'][1]['rows'])
    out.mkdir(parents=True, exist_ok=True)
    content={'index.html':render_html(render_model),
             'snapshot.json':json.dumps(model,indent=2,sort_keys=True)+'\n',
             'graph-light.svg':svg_graph('light'), 'graph-dark.svg':svg_graph('dark')}
    content.update(mermaid())
    for name in FILES:
        (out/name).write_text(content[name],encoding='utf-8')
    hashes = {name:hashlib.sha256((out/name).read_bytes()).hexdigest() for name in FILES}
    sizes = {name:(out/name).stat().st_size for name in FILES}
    manifest = {'schema':'codepurple.coverage_integrity.manifest.v1',
                'presentation_head_sha':presentation_head,'source_json_sha256':model['source_json_sha256'],
                'member_sha256':hashes,'member_bytes':sizes,'merge_admission':'HOLD',
                'authority_transfer':False,'formal_credit_delta':0,
                'current_main_coverage_attestation':None}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    verify(out,presentation_head)
    return manifest


def verify(out, presentation_head):
    out=Path(out)
    manifest=json.loads((out/'manifest.json').read_text(encoding='utf-8'))
    if (manifest.get('presentation_head_sha') != presentation_head or
            manifest.get('merge_admission') != 'HOLD' or
            manifest.get('current_main_coverage_attestation') is not None or
            set(manifest.get('member_sha256',{})) != set(FILES)):
        fail('MANIFEST_PROVENANCE_DRIFT')
    for name in FILES:
        raw=(out/name).read_bytes()
        if (hashlib.sha256(raw).hexdigest()!=manifest['member_sha256'][name] or
                len(raw)!=manifest['member_bytes'][name]):
            fail('TAMPERED_COVERAGE_MEMBER:' + name)
    for name in ('graph-light.svg','graph-dark.svg'):
        ET.fromstring((out/name).read_bytes())
    doc=json.loads((out/'snapshot.json').read_text(encoding='utf-8'))
    if doc['portfolio_total_coverage'] is not None or doc['authority']['formal_credit_delta']!=0:
        fail('PORTFOLIO_OR_AUTHORITY_PROMOTION')
    return manifest


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,default=SOURCE)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--head',required=True)
    p.add_argument('--verify-only',action='store_true')
    args=p.parse_args(argv)
    out=verify(args.out,args.head) if args.verify_only else build(args.source,args.out,args.head)
    print(json.dumps({'state':'SOURCE_BOUND_HISTORICAL_VIEW','head':args.head,
                      'members':len(out['member_sha256']),'admission':'HOLD'},sort_keys=True))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
