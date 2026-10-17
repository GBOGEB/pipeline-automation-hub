#!/usr/bin/env python3
"""Deterministic zero-network W18 communication projections from one JSON master.

Source inputs are frozen observations; no GitHub API call, no admission or issue mutation.
Every output HTML embeds the exact same canonical snapshot JSON and SHA-256.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SNAPSHOT = HERE / 'snapshot.json'
RENDERED = ('index.html', 'cards.html', 'deck.html', 'metrics.csv')


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fail(msg: str):
    raise ValueError('CP_W18_FAIL_CLOSED: ' + msg)


def load_contract():
    raw = SNAPSHOT.read_bytes()
    d = json.loads(raw)
    if d.get('schema') != 'code-purple.communication-master.v1' or d.get('slug') != 'cp-w18-fleet-dov-20261017':
        fail('schema or immutable slug changed')
    c = d['census']
    if c['incomplete_results'] is not False or c['latest_observed_open'] != sum(x['open'] for x in c['repos']):
        fail('repository count mismatch or incomplete search')
    if sum(x['open'] for x in c['age_utc_date_windows']) != c['latest_observed_open']:
        fail('age window count mismatch')
    if c['latest_observed_open'] - c['first_observed_open'] != c['net_change']:
        fail('non-reproducible issue delta')
    if sum(x['count'] for x in c['verified_closure_categories']) != -c['net_change']:
        fail('closure categories no longer reconcile; recensus required')
    if sum(x['count'] * x['engineering_root_credit'] for x in c['verified_closure_categories']) != 0:
        fail('ticket closings cannot grant engineering-root control')
    cov=d['coverage']['four_module']
    if cov['covered'] + cov['uncovered'] != cov['eligible'] or cov['eligible'] != 444:
        fail('source epoch coverage arithmetic')
    if d['coverage']['historical_n14']['comparable_with_w16'] is not False:
        fail('cross-epoch comparison forbidden')
    if d['coverage']['phase8_same_blob']['after_covered'] - d['coverage']['phase8_same_blob']['before_covered'] != d['coverage']['phase8_same_blob']['new_covered']:
        fail('same-source Phase8 increment not matched')
    if d['controls']['merge_admission'] != 'HOLD' or d['controls']['security_waiver'] is not False or d['controls']['authority_transfer'] is not False:
        fail('admission / authority can only change with separate acceptance')
    if len(d['session_dod']) != 8 or len(d['global_dov']) != 8 or len(d['bd_queue']) != 8:
        fail('frozen cardinality is not explicitly revised')
    for k in ('session_dod','global_dov','bd_queue','metrics'):
        if len({x['id'] for x in d[k]}) != len(d[k]):
            fail('duplicate identity in ' + k)
    if any(x['value'] is not None and x['kind'] == 'ratio' and (x['n'] is None or x['d'] is None) for x in d['metrics']):
        fail('invented known ratio')
    for x in d['metrics']:
        if x['value'] is None and x['n'] == 0:
            fail('UNKNOWN cannot be rendered as numerator zero')
    if d['controls']['original_conversation_message_count'] is not None:
        fail('no complete original conversation export to establish total')
    return d, raw


def html_page(d: dict, raw: bytes, mode: str) -> bytes:
    h = digest(raw)
    style=(HERE/'theme.css').read_text(encoding='utf-8')
    js=(HERE/'runtime.js').read_text(encoding='utf-8')
    # Escaping for a raw script element prevents an untrusted </script> terminator.
    payload=json.dumps(d,ensure_ascii=True,sort_keys=True,separators=(',', ':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    headline={'dashboard':'Live evidence and decision control','cards':'Leaf cards and root-owner decisions','deck':'Briefing deck from exactly one evidence master'}[mode]
    if mode == 'dashboard':
        middle='<nav id="view-nav" class="topnav" aria-label="Dashboard views"></nav><main><div id="content" aria-live="polite"></div></main>'
    elif mode == 'cards':
        middle='<main><div class="sectionhead"><h2>BD queue / granular leaf cards</h2><p class="muted">Filter by priority and root. Expand for exact exit condition.</p></div><div id="content"></div></main>'
    else:
        middle='<main class="slide-outer"><div id="slides"></div><div class="decknav"><button id="prev" type="button">Previous</button><strong id="slide-index">1 / 6</strong><button id="next" type="button">Next</button><span class="hint">Arrow keys, PageUp/PageDown, browser Print</span></div></main>'
    src='https://github.com/GBOGEB/pipeline-automation-hub/issues/153'
    doc=f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer"><meta name="master-sha256" content="{h}">
<title>{d['slug']} | {mode}</title><style>{style}</style></head>
<body data-mode="{mode}"><header><div class="headrow"><p class="eyebrow">MISSION CONTROL / CODE PURPLE / W18</p><span class="tag HOLD">MERGE ADMISSION: HOLD</span></div>
<h1>{headline}</h1><p class="lede">{d['title']}. Frozen read-only observations; separate exact-head proof, root closure and human security gates.</p>
<div class="headrow"><span class="stamp">SLUG: {d['slug']}</span><span class="stamp">SOURCE SNAPSHOT: {d['measured_as_of_utc']}</span><a href="{src}" target="_blank" rel="noopener noreferrer">Global issue register</a></div></header>
{middle}<footer class="foot">SOURCE MASTER: <code>snapshot.json</code> | SHA-256 <code id="master-hash">pending</code> | Mode: {mode} | This view does not create GitHub Actions runs or grant acceptance.
GitHub Pages publication remains <strong>UNVERIFIED</strong>; locally packaged pages work without a web server. Plotly is an optional online upgrade for the two-point chart; the SVG fallback is offline. Material raw chat totals, queue p95 and unverified DOV remain UNKNOWN.</footer>
<script id="source-master" type="application/json">{payload}</script><script>{js}</script></body></html>
'''
    return doc.encode('utf-8')


def metric_csv(d: dict) -> bytes:
    s=io.StringIO(newline='')
    w=csv.writer(s,lineterminator='\n')
    w.writerow(['slug','metric_id','name','numerator','denominator','value','evidence_class','decision','source_url'])
    for x in d['metrics']:
        w.writerow([d['slug'],x['id'],x['name'],'' if x['n'] is None else x['n'],'' if x['d'] is None else x['d'],'' if x['value'] is None else x['value'],x['proof'],x['decision'],x['source']])
    return s.getvalue().encode('utf-8')


def run():
    d,raw=load_contract()
    generated={
       'index.html':html_page(d,raw,'dashboard'),
       'cards.html':html_page(d,raw,'cards'),
       'deck.html':html_page(d,raw,'deck'),
       'metrics.csv':metric_csv(d),
    }
    for k,v in generated.items(): (HERE/k).write_bytes(v)
    manifest={
       'schema':'code-purple.communication-render-manifest.v1',
       'slug':d['slug'],
       'master_sha256':digest(raw),
       'generated_sha256':{k:digest(v) for k,v in sorted(generated.items())},
       'source_sha256':{k:digest((HERE/k).read_bytes()) for k in ('runtime.js','theme.css','render.py')},
       'authority_transfer':False,
       'merge_admission':'HOLD',
       'publication':'SOURCE_ONLY_NOT_HOSTED',
    }
    (HERE/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print('Rendered '+d['slug']+' from '+manifest['master_sha256'][:16]+' to '+', '.join(generated))


if __name__=='__main__': run()
