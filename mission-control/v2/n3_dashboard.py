"""Deterministic offline human projection of governed pulse metrics.

HTML/SVG are never evidence authority. All text values escaped and explicit
UNKNOWN/HOLD shown; no external scripts, fonts or network dependencies.
"""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from n3_metrics import collect


def render(data: dict) -> str:
    if data.get('schema') != 'missioncontrol.n3_metrics.v1':
        raise ValueError('wrong metrics schema')
    if data.get('merge_admission') != 'HOLD' or data.get('authority_transfer') is not False:
        raise ValueError('cannot render escalated authority')
    esc = lambda x: html.escape(str(x), quote=True)
    m = data['metrics']
    rows = []
    circles = []
    for index, r in enumerate(data['pulses']):
        n, x = r['ordinal'], 120+index*260
        title = f"Pulse N+{n}; source SHA claim {r['output_source_sha_claim']}; native proof UNKNOWN"
        circles.append(f'<a href="#pulse-{n}" aria-label="{esc(title)}">'
                       f'<circle cx="{x}" cy="95" r="31" fill="#d5dae4" stroke="#27374d" stroke-width="3">'
                       f'<title>{esc(title)}</title></circle></a>'
                       f'<text x="{x}" y="101" text-anchor="middle" fill="#192b43">N+{n}</text>')
        rows.append('<tr id="pulse-'+esc(n)+'"><th scope="row">N+'+esc(n)+'</th><td>'+esc(r['action_description'] or 'UNKNOWN')+'</td>'
                    '<td><code>'+esc(r['output_source_sha_claim'][:12])+'</code></td>'
                    '<td>'+esc(r['test_provenance'])+'</td>'
                    '<td>'+esc(r['declared_changed_path_count'])+'</td><td>HOLD</td></tr>')
    edges = ''.join(f'<path d="M {151+i*260} 95 L {349+i*260} 95" stroke="#27374d" stroke-width="2" marker-end="url(#arrow)"/>'
                    for i in range(max(0, len(circles)-1)))
    denom = m['measurement_completeness']
    return ('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Mission Control N3 Evidence Pulse Dashboard</title><style>'
        'body{font:16px system-ui,sans-serif;background:#f7f9fc;color:#192b43;max-width:1100px;margin:auto;padding:2rem}'
        'section{background:#fff;border:1px solid #c6ced8;border-radius:12px;padding:1rem;margin:1rem 0}'
        '.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:1rem}.num{font-size:2rem;font-weight:750}'
        'svg{width:100%;height:auto;max-height:210px}table{width:100%;border-collapse:collapse;display:block;overflow-x:auto}'
        'th,td{text-align:left;padding:.6rem;border-bottom:1px solid #ccd3dc}.unknown{font-weight:bold}code{word-break:break-all}'
        '@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}'
        '</style></head><body><header><h1>CODE PURPLE · N+3 Evidence Dashboard</h1>'
        '<p>Read-only, deterministic rendering. No admission, causality, or deployment credit.</p></header>'
        '<section class="grid" aria-label="Denominator-defined metrics">'
        '<article><p>Pulse receipts</p><div class="num">'+esc(m['pulse_receipts'])+'</div></article>'
        '<article><p>Evidence completeness</p><div class="num">'+esc(denom['numerator'])+'/'+esc(denom['denominator'])+'</div></article>'
        '<article><p>Historical unknowns</p><div class="num">'+esc(m['unknown_evidence_fields'])+'</div></article>'
        '<article><p>Native exact-head evidence</p><div class="num">'+esc(m['native_attested_receipts']['numerator'])+'/'+esc(m['native_attested_receipts']['denominator'])+'</div></article>'
        '</section><section><h2>Directed pulse lineage (source claims)</h2>'
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 190" role="img" aria-label="Ordered continuation pulses; arrows indicate claimed source lineage">'
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10z"/></marker></defs>'
        +edges+''.join(circles)+'</svg><p>Arrows represent validated ledger order, not independently authenticated GitHub executions.</p></section>'
        '<section><h2>Per-pulse evidence</h2><table><caption>Provenance and admission controls</caption>'
        '<thead><tr><th>Pulse</th><th>Action claim</th><th>Output SHA claim</th><th>Test type</th><th>Changed paths</th><th>Admission</th></tr></thead>'
        '<tbody>'+''.join(rows)+'</tbody></table></section>'
        '<section><h2>Missing or unqualified evidence</h2><p class="unknown">Coverage improvement: UNKNOWN; backlog burndown: UNKNOWN; elapsed-time saving: UNKNOWN.</p>'
        '<p>Statistical inference: '+esc(data['statistical_inference'])+'</p>'
        '<p>Merge admission: HOLD · Security waiver: false · Authority transfer: false.</p>'
        '<p>Source digest: <code>'+esc(data['source_ledger_digest'])+'</code></p></section></body></html>')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ledger', type=Path)
    ap.add_argument('--html', type=Path, required=True)
    ap.add_argument('--metrics', type=Path)
    a = ap.parse_args()
    data = collect(json.loads(a.ledger.read_text(encoding='utf-8')))
    a.html.parent.mkdir(parents=True, exist_ok=True)
    a.html.write_text(render(data)+'\n', encoding='utf-8', newline="\n")
    if a.metrics:
        a.metrics.write_text(json.dumps(data, indent=2, sort_keys=True)+'\n', encoding='utf-8', newline="\n")
    print(json.dumps({'html':str(a.html),'metric_digest':data['source_ledger_digest'],'pulse_count':len(data['pulses'])}))


if __name__ == '__main__':
    main()
