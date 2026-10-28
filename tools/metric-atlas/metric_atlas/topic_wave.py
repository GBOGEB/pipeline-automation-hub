"""W378: source-bound, read-only topic pilot and three-lens graph projection.

Consumes W377 topic_exchange; no GitHub API, cron, dispatch, issue writes or
engineering approval. Input is an externally frozen, explicitly classified pulse.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
import hashlib
import html
import json
from pathlib import Path
import re

from metric_atlas import topic_exchange as exchange

SCHEMA = 'qps.topic-wave.pilot.v1'
OUTPUT = 'qps.topic-wave.receipt.v1'
TYPES = {'SOURCE', 'INPUT', 'PROCESS', 'EVIDENCE', 'CONSUMER', 'CONTROL'}
SIPOC = {'SOURCE': 'S', 'INPUT': 'I', 'PROCESS': 'P', 'EVIDENCE': 'O', 'CONSUMER': 'C', 'CONTROL': 'P'}
STATES = {'PASS', 'FAIL', 'UNKNOWN', 'HOLD'}
EDGES = {'DEPENDS', 'PRODUCES', 'CONSUMES', 'REVIEW', 'NEXT_PULSE'}
LENSES = ('FUNCTION', 'SHA', 'OID')
VIEWS = ('DAG', 'SIPOC', 'SPINE')
NODE = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,95}\Z')
HEX = re.compile(r'[0-9a-f]{40}\Z')


def require(value, message):
    if not value:
        raise ValueError(message)


def canon(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(',', ':'), allow_nan=False)


def digest(obj):
    return hashlib.sha256(canon(obj).encode('utf-8')).hexdigest()


def validate(pulse):
    require(type(pulse) is dict and pulse.get('schema') == SCHEMA, 'INVALID_PILOT_SCHEMA')
    require(pulse.get('authority_transfer') is False and pulse.get('merge_admission') == 'HOLD', 'AUTHORITY_PROMOTION')
    require(pulse.get('mode') == 'READ_ONLY_DECLARED_PILOT', 'UNPROVEN_EXECUTION')
    require(type(pulse.get('max_readers')) is int and 1 <= pulse['max_readers'] <= 2, 'UNBOUNDED_READERS')
    require(type(pulse.get('source_writers')) is int and pulse['source_writers'] == 0, 'UNAUTHORIZED_WRITER')
    require(isinstance(pulse.get('cohort'), str) and bool(NODE.fullmatch(pulse['cohort'])), 'INVALID_COHORT')
    require(isinstance(pulse.get('method_version'), str) and pulse['method_version'], 'INVALID_METHOD')
    exchange.timestamp(pulse.get('observed_at'))
    packets = pulse.get('packets')
    require(type(packets) is list and 1 <= len(packets) <= 3, 'PILOT_PACKET_CAP')
    topics = set()
    for row in packets:
        require(type(row) is dict and set(row) == {'packet', 'recipient', 'current_head',
                'current_source_sha256', 'current_scope_sha256'}, 'INVALID_PACKET_INPUT')
        pkt = exchange.verify_packet(row['packet'])
        require(pkt['topic'] not in topics, 'DUPLICATE_TOPIC_OWNER')
        topics.add(pkt['topic'])
        require(row['recipient'] in pkt['recipients'], 'UNSUBSCRIBED_RECIPIENT')
        for name, length in (('current_head',40),('current_source_sha256',64),('current_scope_sha256',64)):
            require(isinstance(row[name], str) and bool((exchange.SHA40 if length == 40 else exchange.SHA64).fullmatch(row[name])), 'INVALID_CURRENT_IDENTITY')
    nodes = pulse.get('nodes')
    edges = pulse.get('edges')
    require(type(nodes) is list and 3 <= len(nodes) <= 32 and type(edges) is list and len(edges) <= 96, 'GRAPH_BOUNDS')
    ids = set()
    for node in nodes:
        require(type(node) is dict and set(node) == {'id','kind','owner','function','head_sha','blob_oid','state'}, 'INVALID_NODE_SHAPE')
        ident = node['id']
        require(isinstance(ident, str) and bool(NODE.fullmatch(ident)) and ident not in ids, 'DUPLICATE_OR_INVALID_NODE')
        ids.add(ident)
        require(node['kind'] in TYPES and node['state'] in STATES, 'INVALID_NODE_CLASS')
        require(isinstance(node['owner'], str) and node['owner'] and isinstance(node['function'], str) and node['function'], 'MISSING_NODE_OWNER')
        require(node['head_sha'] is None or isinstance(node['head_sha'], str) and bool(HEX.fullmatch(node['head_sha'])), 'INVALID_COMMIT_SHA')
        require(node['blob_oid'] is None or isinstance(node['blob_oid'], str) and bool(HEX.fullmatch(node['blob_oid'])), 'INVALID_GIT_BLOB_OID')
    seen = set()
    next_edges = 0
    indegree = {n: 0 for n in ids}
    children = defaultdict(list)
    for edge in edges:
        require(type(edge) is dict and set(edge) == {'from','to','relation'}, 'INVALID_EDGE_SHAPE')
        key = (edge['from'], edge['to'], edge['relation'])
        require(edge['from'] in ids and edge['to'] in ids and key not in seen, 'FOREIGN_OR_DUPLICATE_EDGE')
        seen.add(key)
        require(edge['relation'] in EDGES, 'INVALID_EDGE_RELATION')
        if edge['relation'] == 'NEXT_PULSE':
            next_edges += 1
        else:
            require(edge['from'] != edge['to'], 'SELF_DEPENDENCY')
            children[edge['from']].append(edge['to'])
            indegree[edge['to']] += 1
    queue = deque(sorted(n for n in ids if indegree[n] == 0))
    order = []
    while queue:
        n = queue.popleft()
        order.append(n)
        for child in sorted(children[n]):
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    require(len(order) == len(ids), 'SAME_PULSE_CYCLE')
    require(next_edges <= 3, 'UNBOUNDED_FEEDBACK')
    require(all(any(node['kind'] == kind for node in nodes) for kind in ('SOURCE','EVIDENCE','CONTROL')), 'MISSING_SPINE_ROLE')
    return order


def label(node, lens):
    if lens == 'FUNCTION':
        return node['function']
    if lens == 'SHA':
        return node['head_sha'][:12] if node['head_sha'] else 'SHA UNKNOWN'
    return node['blob_oid'][:12] if node['blob_oid'] else 'OID UNKNOWN'


def make_mermaid(nodes, edges, lens, view):
    require(lens in LENSES and view in VIEWS, 'UNKNOWN_VIEW')
    out = ['flowchart LR', '%% lens='+lens+' view='+view+'; same source-bound node/edge identities']
    ordered = sorted(nodes, key=lambda n: n['id'])
    aliases = {n['id']: 'N'+str(i) for i,n in enumerate(ordered)}
    for n in ordered:
        prefix = n['kind'] if view == 'DAG' else SIPOC[n['kind']] if view == 'SIPOC' else n['owner']
        value = (prefix + ' | ' + label(n,lens)).replace('"','\'').replace('<','(').replace('>',')')
        out.append('  '+aliases[n['id']]+'["'+value[:115]+'"]')
    for e in sorted(edges,key=lambda x:(x['from'],x['to'],x['relation'])):
        a,b = aliases[e['from']], aliases[e['to']]
        out.append('  '+a+' '+('-.->' if e['relation']=='NEXT_PULSE' else '-->')+' '+b)
    return '\n'.join(out)+'\n'


def pilot(pulse):
    order = validate(pulse)
    plans=[]
    for i,row in enumerate(sorted(pulse['packets'],key=lambda x:x['packet']['topic'])):
        pkt=row['packet']
        decision=exchange.decide(pkt,recipient=row['recipient'],current_head=row['current_head'],
            current_source_sha256=row['current_source_sha256'],current_scope_sha256=row['current_scope_sha256'],
            at=pulse['observed_at'])
        plans.append({'topic':pkt['topic'],'producer_repo':pkt['producer_repo'],
            'packet_sha256':pkt['packet_sha256'],'reader_lane':i%pulse['max_readers'],
            'recipient':row['recipient'],'decision':decision['decision'],
            'source_recensus_required':decision['producer_recensus_required'],
            'recipient_pull_required':decision['recipient_pull_required'],
            'native_worker_id':None,'native_ci_run':None})
    counts = Counter(x['decision'] for x in plans)
    nodes=pulse['nodes'];edges=pulse['edges']
    renders={v:{l:make_mermaid(nodes,edges,l,v) for l in LENSES} for v in VIEWS}
    return {'schema':OUTPUT,'source_pulse_sha256':digest(pulse),'cohort':pulse['cohort'],
        'observed_at':pulse['observed_at'],'method_version':pulse['method_version'],
        'topics':plans,'topic_decisions':dict(sorted(counts.items())),
        'metrics':{'topics':len(plans),'nodes':len(nodes),'within_pulse_edges':sum(x['relation']!='NEXT_PULSE' for x in edges),
            'next_pulse_edges':sum(x['relation']=='NEXT_PULSE' for x in edges),
            'source_recensus_requested':sum(x['source_recensus_required'] for x in plans),
            'recipient_pulls_requested':sum(x['recipient_pull_required'] for x in plans),
            'actual_worker_capacity':None,'queue_wait_p95_seconds':None,'saved_runner_minutes':None,
            'verified_external_acks':0,'native_jobs_dispatched':0,'source_writers':0,
            'known_pr_stock':None,'bd_flow_delta':None,'coverage_delta':None},
        'graph':{'nodes':nodes,'edges':edges,'topological_order':order,'projections':renders},
        'formal_credit_delta':0,'authority_transfer':False,'merge_admission':'HOLD'}


def compare(a,b):
    require(a['schema']==b['schema']==OUTPUT,'INCOMPARABLE_SCHEMA')
    if a['cohort'] != b['cohort'] or a['method_version'] != b['method_version']:
        return {'comparable':False,'reason':'COHORT_OR_METHOD_DRIFT','delta':None}
    aa={x['topic']:(x['packet_sha256'],x['decision']) for x in a['topics']}
    bb={x['topic']:(x['packet_sha256'],x['decision']) for x in b['topics']}
    if set(aa)!=set(bb):
        return {'comparable':False,'reason':'TOPIC_MEMBERSHIP_DRIFT','delta':None}
    return {'comparable':True,'reason':'MATCHED_TOPIC_POPULATION',
            'delta':{'changed_packet_sha':sum(aa[k][0]!=bb[k][0] for k in aa),
                     'changed_decisions':sum(aa[k][1]!=bb[k][1] for k in aa)}}


def render_html(report):
    """Self-contained SVG graph with lens and view toggles; no remote JS or data."""
    payload=json.dumps({'nodes':report['graph']['nodes'],'edges':report['graph']['edges']},separators=(',',':')).replace('</','<\\/')
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>W378 graph pilot</title>
<style>body{font:15px system-ui,sans-serif;margin:1.5rem;max-width:1100px;color:#152b42}header{display:flex;gap:1rem;flex-wrap:wrap;align-items:center}select{padding:.55rem}svg{width:100%;height:auto;border:1px solid #cbd5e1;border-radius:10px;background:#f8fafc;overflow:visible}#detail{white-space:pre-wrap;overflow-wrap:anywhere;word-break:break-word;background:#e9f1f8;padding:1rem}button{cursor:pointer} .panel{overflow-x:auto;overscroll-behavior-x:contain}.panel svg{min-width:1100px} .hint{color:#526477}</style></head><body><h1>W378 · Object identity and evidence graph</h1>
<header><label>Identity <select id="lens"><option>FUNCTION</option><option>SHA</option><option>OID</option></select></label><label>Projection <select id="view"><option>DAG</option><option>SIPOC</option><option>SPINE</option></select></label></header>
<p class="hint">Read-only projection. Unknown OIDs stay unknown; NEXT_PULSE edges are dotted and excluded from same-pulse critical path. Swipe horizontally on phones to inspect every node.</p><div class="panel"><svg id="graph" role="img" aria-label="Typed source-bound graph" viewBox="0 0 1100 640"></svg></div><h2>Node BIOS</h2><pre id="detail" aria-live="polite">Select a graph node for its source and authority binding.</pre>
<script>const model='''+payload+''';const S='http://www.w3.org/2000/svg';const svg=document.getElementById('graph');const detail=document.getElementById('detail');
function elt(tag,attributes,text){const e=document.createElementNS(S,tag);Object.entries(attributes||{}).forEach(([k,v])=>e.setAttribute(k,String(v)));if(text!==undefined)e.textContent=text;return e}
function render(){svg.replaceChildren();let lens=document.getElementById('lens').value,view=document.getElementById('view').value;const nodes=[...model.nodes].sort((a,b)=>a.id.localeCompare(b.id));const coords={};const layers={SOURCE:0,INPUT:1,PROCESS:2,EVIDENCE:3,CONSUMER:4,CONTROL:4};const buckets={};for(const n of nodes){let z=view==='SIPOC'?({SOURCE:0,INPUT:1,PROCESS:2,EVIDENCE:3,CONSUMER:4,CONTROL:2})[n.kind]:view==='SPINE'?({SOURCE:0,INPUT:1,PROCESS:2,EVIDENCE:3,CONSUMER:4,CONTROL:3})[n.kind]:layers[n.kind];(buckets[z]??=[]).push(n)}let max=0;Object.keys(buckets).forEach(z=>{max=Math.max(max,buckets[z].length);buckets[z].forEach((n,i)=>coords[n.id]=[18+Number(z)*215,30+i*98])});svg.setAttribute('viewBox','0 0 1100 '+Math.max(320,80+max*98));for(const e of model.edges){const a=coords[e.from],b=coords[e.to];if(!a||!b)continue;const line=elt('line',{x1:a[0]+188,y1:a[1]+32,x2:b[0],y2:b[1]+32,stroke:e.relation==='NEXT_PULSE'?'#9e768c':'#71859e','stroke-width':2,'stroke-dasharray':e.relation==='NEXT_PULSE'?'5 6':'none'});svg.appendChild(line)}for(const n of nodes){const [x,y]=coords[n.id];const g=elt('g',{role:'button',tabindex:0,'aria-label':n.id});const rect=elt('rect',{x,y,width:188,height:64,rx:7,fill:n.state==='PASS'?'#d8f3e2':n.state==='FAIL'?'#ffdddd':n.state==='HOLD'?'#fff0ce':'#eef2f6',stroke:'#64748b'});g.appendChild(rect);g.appendChild(elt('text',{x:x+8,y:y+19,'font-size':12,'font-weight':700,fill:'#1b3245'},n.id.slice(0,24)));const val=lens==='FUNCTION'?n.function:lens==='SHA'?(n.head_sha||'SHA UNKNOWN'):n.blob_oid||'OID UNKNOWN';g.appendChild(elt('text',{x:x+8,y:y+42,'font-size':11,fill:'#243f59'},val.slice(0,25)));const show=()=>detail.textContent=JSON.stringify(n,null,2);g.addEventListener('click',show);g.addEventListener('keydown',e=>{if(e.key==='Enter')show()});svg.appendChild(g)}}
document.getElementById('lens').addEventListener('change',render);document.getElementById('view').addEventListener('change',render);render();</script></body></html>'''


def emit(pulse,out):
    report=pilot(pulse)
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    blobs={'pilot-receipt.json':json.dumps(report,indent=2,sort_keys=True)+'\n',
           'graph.html':render_html(report)}
    for view,by_lens in report['graph']['projections'].items():
        for lens,content in by_lens.items():
            blobs['graph_'+view.lower()+'_'+lens.lower()+'.mmd']=content
    manifest={'schema':'qps.topic-wave.manifest.v1','source_pulse_sha256':report['source_pulse_sha256'],
              'files_sha256':{k:hashlib.sha256(v.encode('utf-8')).hexdigest() for k,v in sorted(blobs.items())},
              'authority_transfer':False,'merge_admission':'HOLD'}
    for k,v in blobs.items():
        (out/k).write_text(v,encoding='utf-8',newline='\n')
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
    return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    m=emit(json.loads(a.input.read_text(encoding='utf-8')),a.out)
    print(json.dumps({'status':'LOCAL_PILOT_NOT_AUTHORITY','files':len(m['files_sha256'])},sort_keys=True))

if __name__ == '__main__':
    main()
