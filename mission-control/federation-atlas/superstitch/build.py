#!/usr/bin/env python3
"""Read-only W34 Superstitch source -> HTML/SVG/JSON with member SHA256.

QPS engineering truth, native run activity, worker dispatch and acceptance are
outside the authority of this projection. No external JS/CDN at runtime.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from stitch_views import (validate_groups, mermaid, mermaid_group, mermaid_sipoc,
                          mermaid_trigger, sipoc_svg, trigger_svg,
                          summarize_group_edges)

ROOT = Path(__file__).parent
SOURCE = ROOT / 'SUPERSTITCH_SOURCE_v1.json'
SCHEMA = 'missioncontrol.superstitch.source.v1'
SHA40 = re.compile('[0-9a-f]{40}\\Z')
ALLOWED_BINDINGS = {'DECLARED', 'ROLE_ONLY', 'DESIGN_ONLY', 'NATIVE_RECEIPT'}
ALLOWED_STATUS = {'OWNER_ONLY','HOLD','DECLARED','ALIAS','CANONICAL_ROLE',
                  'PROPOSED','HISTORICAL_SOURCE','HISTORICAL_PASS',
                  'DESIGNED_NOT_EXECUTED','NATIVE_REQUIRED'}
LANE_Y = {'qps':20,'dow':115,'keb':210,'mc':305,'math':400,'flight':495}
LANE_COLOR = {'qps':'#ec8298','dow':'#60e2c4','keb':'#82cfff',
              'mc':'#c19aff','math':'#ecaff7','flight':'#f2be72'}


def digest(data: bytes):
    return hashlib.sha256(data).hexdigest()


def canonical_bytes(data):
    return (json.dumps(data, sort_keys=True, indent=2, ensure_ascii=True)+'\n').encode()


def validate(model):
    if model.get('schema') != SCHEMA or model.get('mode') != 'READ_ONLY_PROJECTION':
        raise ValueError('WRONG_SUPERSTITCH_SOURCE_SCHEMA')
    a = model['authority']
    if (a.get('zip_verifier')!='MC-530' or a.get('breadth_producer')!='MC-531'
        or a.get('method_viewer')!='MC-533' or a.get('merge_admission')!='HOLD'
        or a.get('qps_owner_acceptance') is not None or a.get('run_dispatch') is not False
        or a.get('engineering_compliance_credit') is not False):
        raise ValueError('AUTHORITY_PROMOTION_OR_OWNER_TRANSFER')
    o = model['observations']
    if (o['historical_six_repo_breadth']['observed']!=6 or
        o['historical_six_repo_breadth']['eligible']!=42 or
        o['authenticated_codex_qps_pairs']['observed']!=0 or
        o['M2']!='HOLD' or o['M3']!='HOLD' or o['worker_hours'] is not None
        or o['capacity'] is not None):
        raise ValueError('FALSE_BREADTH_MIP_OR_CAPACITY_PROMOTION')
    for src in model['source_refs']:
        if src['classification'].startswith('PRIVATE_'):
            if src['path'] is not None or src['head'] is not None:
                raise ValueError('PRIVATE_SOURCE_LEAK_IN_PUBLIC_VIEW')
        elif not SHA40.fullmatch(src.get('head') or ''):
            raise ValueError('PUBLIC_SOURCE_SHA_REQUIRED')
    srcs = {s['id'] for s in model['source_refs']}
    lanes = {s['id'] for s in model['lanes']}
    nids, canon, nodes = set(),defaultdict(list),{}
    for n in model['nodes']:
        if n['id'] in nids or n['lane'] not in lanes or n['source'] not in srcs:
            raise ValueError('DUPLICATE_NODE_OR_INVALID_LANE_SOURCE')
        if n['col'] not in range(6) or n['level'] not in (1,2,3):
            raise ValueError('BAD_NODE_PLACEMENT')
        if n['status'] not in ALLOWED_STATUS:
            raise ValueError('FABRICATED_LIVE_STATUS')
        if not n.get('canonical_id'):
            raise ValueError('MISSING_CANONICAL_ID')
        nids.add(n['id']);canon[n['canonical_id']].append(n); nodes[n['id']]=n
    for group in canon.values():
        if len(group)>1 and (sum(n['status']=='ALIAS' for n in group)!=len(group)-1):
            raise ValueError('UNLABELLED_DUPLICATE_BLOCK')
    seen = set()
    pairs = []
    for e in model['edges']:
        if e['from'] not in nids or e['to'] not in nids or e['from']==e['to']:
            raise ValueError('EDGE_ENDPOINT_INVALID')
        key=(e['from'],e['to'],e['kind'])
        if key in seen: raise ValueError('DUPLICATE_EDGE')
        seen.add(key)
        if e['binding'] not in ALLOWED_BINDINGS:
            raise ValueError('UNVERIFIED_NATIVE_EDGE')
        if e['binding']=='NATIVE_RECEIPT' and not e.get('source_native_receipt'):
            raise ValueError('NATIVE_EDGE_WITHOUT_SOURCE_RECEIPT')
        if e['kind'] not in {'RETRIGGER','TOUCH'}:
            pairs.append((e['from'],e['to']))
    # Prove the owned source DAG is acyclic; feedback is a distinct NEXT-PULSE edge.
    remaining=set(nids);incoming=defaultdict(set)
    for u,v in pairs:incoming[v].add(u)
    while remaining:
        layer={n for n in remaining if not incoming[n].intersection(remaining)}
        if not layer:raise ValueError('CYCLIC_CORE_DAG_NOT_NEXT_PULSE_FEEDBACK')
        remaining-=layer
    return model


def small(s):return html.escape(str(s),quote=True)


def short_label(text,max_chars=24):
    if len(text)<=max_chars:return [text]
    words=text.split();result=[];line=''
    for word in words:
        if len(line+' '+word)>max_chars and line:
            result.append(line);line=word
        else:line=(line+' '+word).strip()
    if line:result.append(line)
    return (result[:2] if len(result)<3 else [result[0],result[1][:max_chars-1]+'…'])


def pos(node):
    return 195+205*node['col'], LANE_Y[node['lane']]+16


def draw_svg(model):
    nodes={n['id']:n for n in model['nodes']}
    out=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1430 610" width="1430" height="610" role="img" aria-label="Expanded six-lane DOW KEB QPS Mission Control Superstitch DAG, proposed and non-live">',
    '<defs><marker id="arrow" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0 0 L7 3.5 L0 7" fill="none" stroke="#96a6d4" stroke-width="1.2"/></marker></defs>']
    for lane in model['lanes']:
        y=LANE_Y[lane['id']]
        out.extend([f'<rect x="5" y="{y}" width="1420" height="87" rx="12" fill="#111b32" stroke="#243256" opacity=".97"/>',
          f'<rect x="8" y="{y+7}" width="171" height="71" rx="9" fill="#172345" stroke="{lane["color"]}" stroke-opacity=".33"/>',
          f'<text x="19" y="{y+33}" fill="{lane["color"]}" font-size="12.8" font-weight="700">{small(lane["title"])}</text>',
          f'<text x="19" y="{y+52}" fill="#a1b1cf" font-size="10.3">{small(lane["subtitle"])}</text>'])
    for i,e in enumerate(model['edges']):
        a=nodes[e['from']];b=nodes[e['to']]
        ax,ay=pos(a);bx,by=pos(b);aw=185;ah=58
        if e['kind']=='RETRIGGER':
            path=f'M {ax+aw/2:.1f} {ay+ah:.1f} C {ax+aw/2:.1f} 604 {bx+aw/2:.1f} 604 {bx+aw/2:.1f} {by+ah:.1f}'
        elif b['col']>a['col']:
            x1=ax+aw;y1=ay+ah/2;x2=bx;y2=by+ah/2
            gap=max(30,(x2-x1)*0.47)
            path=f'M {x1} {y1:.1f} C {x1+gap:.1f} {y1:.1f}, {x2-gap:.1f} {y2:.1f}, {x2} {y2:.1f}'
        else:
            x1=ax+aw/2;y1=ay+ah;x2=bx+aw/2;y2=by
            path=f'M {x1:.1f} {y1:.1f} C {x1:.1f} {y1+34:.1f}, {x2:.1f} {y2-34:.1f}, {x2:.1f} {y2:.1f}'
        cls='edge' + (' touch' if e['kind']=='TOUCH' else '') + (' retrigger' if e['kind']=='RETRIGGER' else '')
        out.append(f'<path class="{cls}" data-edge="{i}" data-from="{small(e["from"])}" data-to="{small(e["to"])}" data-binding="{small(e["binding"])}" data-kind="{small(e["kind"])}" d="{path}" fill="none" stroke="#718bbd" stroke-width="1.6" stroke-dasharray="{"5 5" if e["binding"] in ("DECLARED","DESIGN_ONLY") or e["kind"] in ("RETRIGGER","TOUCH") else "none"}" marker-end="url(#arrow)"/>')
    for n in model['nodes']:
        x,y=pos(n);color=LANE_COLOR[n['lane']];alias=n['status']=='ALIAS'
        cls='graph-node alias' if alias else 'graph-node'
        labels=short_label(n['label'],23)
        texty=y+22 if len(labels)==2 else y+25
        txt=''.join(f'<text x="{x+11}" y="{texty+idx*13}" fill="#eef2ff" font-weight="650" font-size="12.3">{small(lbl)}</text>' for idx,lbl in enumerate(labels))
        subtitle=n['detail'][:28]+('…' if len(n['detail'])>28 else '')
        out.append(f'<g class="{cls}" data-node="{small(n["id"])}" data-canonical="{small(n["canonical_id"])}" data-level="{n["level"]}" data-lane="{n["lane"]}" role="button" tabindex="0" aria-label="Inspect {small(n["label"])}">'
                   f'<title>{small(n["label"]+" — "+n["status"]+" — "+n["canonical_id"])}</title>'
                   f'<rect x="{x}" y="{y}" width="185" height="58" rx="10" fill="#21183e" stroke="{color}" stroke-width="1.4" stroke-dasharray="{"5 4" if alias else "none"}"/>')
        out.append(txt)
        if len(labels)==1:
            out.append(f'<text x="{x+11}" y="{y+42}" fill="#a9b8d9" font-size="10.4">{small(subtitle)}</text>')
        else:
            out.append(f'<text x="{x+11}" y="{y+52}" fill="#9aaad0" font-size="8.6">{small(n["status"])}</text>')
        if alias:out.append(f'<circle cx="{x+173}" cy="{y+11}" r="5" fill="#e3b6ff"/>')
        elif n['status'] in ('HOLD','NATIVE_REQUIRED'):out.append(f'<circle cx="{x+173}" cy="{y+11}" r="5" fill="#f4b66f"/>')
        out.append('</g>')
    out.append('</svg>')
    return '\n'.join(out)+'\n'


def spline(model):
    # One observed cohort: no interpolated midpoints; unknown forecast is open circle.
    p=model['observations']['historical_six_repo_breadth']
    x=[65,145,225,305]; y=110-65*(p['observed']/p['eligible'])
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 360 150" role="img" aria-label="Historical six-repository observed breadth 6 of 42; no measured future point">
    <path d="M 42 18 V 118 H 344" stroke="#455576" stroke-width="1.2" fill="none"/>
    <path d="M {x[1]} {y:.2f} L {x[2]} {y:.2f}" fill="none" stroke="#bd91ff" stroke-width="3" />
    <!-- Future N+1 has no measured numerator, therefore NO interpolated trend line -->
    <circle cx="{x[1]}" cy="{y:.2f}" r="5" fill="#bd91ff" role="button" tabindex="0" data-pulse="N-1" aria-label="N minus 1 historical breadth 6 of 42"/>
    <circle cx="{x[2]}" cy="{y:.2f}" r="5" fill="#bd91ff" role="button" tabindex="0" data-pulse="N" aria-label="N historical breadth 6 of 42"/>
    <circle cx="{x[3]}" cy="40" r="6" fill="#151d32" stroke="#e8c78f" stroke-dasharray="3 3" stroke-width="1.8" role="button" tabindex="0" data-pulse="N+1" aria-label="N plus 1 future breadth unknown"/>
    <text x="10" y="12" font-size="10" fill="#bbcae7">Observed / 42</text>
    <text x="{x[1]}" y="{y-14:.2f}" font-size="12" text-anchor="middle" fill="#e1c8ff">6 / 42</text>
    <text x="200" y="20" font-size="9" text-anchor="middle" fill="#c0a1eb">36 cells remain unobserved</text>
    <text x="{x[3]}" y="25" font-size="10" text-anchor="middle" fill="#e8c78f">UNKNOWN · no point</text>
    {''.join(f'<text x="{x[i]}" y="139" font-size="11" text-anchor="middle" fill="#9badd0">{name}</text>' for i,name in enumerate(["N−2","N−1","N","N+1"]))}
    </svg>'''


def do_build(source:Path,out:Path,presentation_head:str):
    if not SHA40.fullmatch(presentation_head):raise ValueError('EXACT_40_SHA_REQUIRED')
    raw=source.read_bytes();model=validate(json.loads(raw))
    group_source=ROOT/'SUPERSTITCH_GROUPS_W35.json'
    group_raw=group_source.read_bytes()
    group_contract=validate_groups(json.loads(group_raw),model)
    model['groups']=group_contract['groups']
    model['group_contract']=group_contract
    model['group_topology']={g['id']:summarize_group_edges(model,g) for g in model['groups']}
    model['mermaid']={
        'dag':mermaid(model),
        'sipoc':mermaid_sipoc(model,model['groups']),
        'triggers':mermaid_trigger(model),
        'groups':{g['id']:mermaid_group(model,g) for g in model['groups']}}
    out.mkdir(parents=True,exist_ok=True)
    svg=draw_svg(model)
    model['publication']={"presentation_head":presentation_head,"source_sha256":digest(raw),
      "native_current_attestation":None,"refresh_status":"NOT_AUTO_POLLED","prepush_testflight":None,
      "hosted_pages_attestation":None,"formal_admission":"HOLD"}
    tax=json.loads((ROOT/'SUPERSTITCH_TAXONOMY_v1.json').read_text(encoding='utf-8'))
    gloss=json.loads((ROOT/'SUPERSTITCH_GLOSSARY_v1.json').read_text(encoding='utf-8'))
    if (tax.get('schema')!='missioncontrol.superstitch.taxonomy.v1' or tax.get('authority_transfer') is not False
        or gloss.get('schema')!='missioncontrol.superstitch.glossary.v1' or gloss.get('authority_transfer') is not False):
        raise ValueError('TAXONOMY_OR_GLOSSARY_CONTRACT_DRIFT')
    model['taxonomy']=tax;model['glossary']=gloss
    compiled=canonical_bytes(model)
    template=(ROOT/'template.html').read_text(encoding='utf-8')
    view=(template.replace('__GRAPH_SVG__',svg)
          .replace('__SPLINE_SVG__',spline(model))
          .replace('__SIPOC_SVG__',sipoc_svg(model,model['groups']))
          .replace('__TRIGGER_SVG__',trigger_svg(model,draw_svg)))
    view=view.replace('__MODEL_JSON__',json.dumps(model,ensure_ascii=True).replace('<',r'\u003c'))
    files={'index.html':view.encode('utf-8'),
       'app.js':(ROOT/'app.js').read_bytes(),
       'stitch_interaction.js':(ROOT/'stitch_interaction.js').read_bytes(),
       'style.css':(ROOT/'style.css').read_bytes(),
       'stitch_interaction.css':(ROOT/'stitch_interaction.css').read_bytes(),
       'graph.svg':svg.encode('utf-8'),
       'graph.json':compiled,'spline.svg':spline(model).encode('utf-8'),
       'taxonomy.json':canonical_bytes(tax),'glossary.json':canonical_bytes(gloss),
       'groups.json':group_raw,
       'sipoc-lanes.svg':sipoc_svg(model,model['groups']).encode('utf-8'),
       'trigger-dag.svg':trigger_svg(model,draw_svg).encode('utf-8'),
       'superstitch.mmd':model['mermaid']['dag'].encode('utf-8'),
       'sipoc-lanes.mmd':model['mermaid']['sipoc'].encode('utf-8'),
       'trigger-dag.mmd':model['mermaid']['triggers'].encode('utf-8')}
    for filename,data in files.items():(out/filename).write_bytes(data)
    manifest={'schema':'missioncontrol.superstitch.manifest.v1',
       'presentation_head':presentation_head,'source_sha256':digest(raw),
       'source_file':source.name,'group_source_sha256':digest(group_raw),
       'role':'READ_ONLY_EXISTING_PAGES_CONSUMER',
       'merger_admission':'HOLD','qps_owner_acceptance':None,
       'run_dispatch':False,'native_test_attestation':None,'source_validation':'PASS',
       'member_sha256':{name:digest(data) for name,data in files.items()},
       'member_bytes':{name:len(data) for name,data in files.items()}}
    (out/'manifest.json').write_bytes(canonical_bytes(manifest))
    verify(out,presentation_head)
    return manifest


def verify(out:Path,sha:str):
    out=Path(out);manifest=json.loads((out/'manifest.json').read_bytes())
    if manifest.get('presentation_head')!=sha or manifest.get('merger_admission')!='HOLD' or manifest.get('run_dispatch') is not False:
        raise ValueError('MANIFEST_PROMOTION_OR_STALE_HEAD')
    if set(manifest.get('member_sha256',{})) != {'index.html','app.js','stitch_interaction.js',
            'style.css','stitch_interaction.css','graph.svg','graph.json','spline.svg',
            'taxonomy.json','glossary.json','groups.json','sipoc-lanes.svg',
            'trigger-dag.svg','superstitch.mmd','sipoc-lanes.mmd','trigger-dag.mmd'}:
        raise ValueError('INCOMPLETE_MEMBER_SET')
    for name,expected in manifest['member_sha256'].items():
        data=(out/name).read_bytes()
        if digest(data)!=expected or len(data)!=manifest['member_bytes'][name]:
            raise ValueError('TAMPERED_MEMBER:'+name)
    graph=json.loads((out/'graph.json').read_bytes());validate(graph)
    declared=json.loads((out/'groups.json').read_bytes())
    validate_groups(declared,graph)
    if (manifest.get('group_source_sha256')!=digest((out/'groups.json').read_bytes()) or
            graph.get('group_contract')!=declared or graph.get('groups')!=declared['groups']):
        raise ValueError('GROUP_SOURCE_OR_IDENTITY_MISMATCH')
    if (graph.get('mermaid',{}).get('dag') != (out/'superstitch.mmd').read_text() or
            graph.get('mermaid',{}).get('sipoc') != (out/'sipoc-lanes.mmd').read_text() or
            graph.get('mermaid',{}).get('triggers') != (out/'trigger-dag.mmd').read_text()):
        raise ValueError('MERMAID_MACHINE_PARITY_FAIL')
    if graph['publication']['presentation_head']!=sha or graph['publication']['native_current_attestation'] is not None:
        raise ValueError('FAKE_NATIVE_STATUS')
    return manifest


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,default=SOURCE)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--head',required=True)
    p.add_argument('--verify-only',action='store_true');a=p.parse_args()
    m=verify(a.out,a.head) if a.verify_only else do_build(a.source,a.out,a.head)
    print(json.dumps({'result':'SOURCE_BOUND_PROJECTION','member_bytes':m['member_bytes'],
                      'source_sha256':m['source_sha256'],'admission':'HOLD'},sort_keys=True))
if __name__=='__main__':main()
