#!/usr/bin/env python3
"""Source-owned, read-only CODE PURPLE CPQ recensus and review projection.

Do not mutate the canonical CODE_PURPLE_BD_QUEUE_v1.json, credit causal root
closure, infer independent observations from jobs, or launch agents.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import re
from pathlib import Path
import source_freshness

SCHEMA = 'missioncontrol.code_purple.cpq_convergence_n5.v1'
SHA40 = re.compile(r'[0-9a-f]{40}\Z')
KEY = re.compile(r'W([0-9]+)\.C([0-9]+)\.I([0-9]+)\.S([0-9]+)\Z')
OPEN = {'TODO','ACTIVE','UNKNOWN_NEEDS_READER'}
DONE = {'DONE','CONTROL','SUPERSEDED','INVALIDATED'}
ROUTING = {
    'CPQ-003':'NATIVE_BROWSER_PROOF', 'CPQ-005':'FRESHNESS_PROOF',
    'CPQ-009':'EXTERNAL_TELEMETRY', 'CPQ-010':'ABACUS_OWNER_CONTROL',
    'CPQ-011':'TOP7_RECONCILIATION', 'CPQ-013':'DEPENDENCY_CONTROL',
    'CPQ-015':'AUTHENTICATED_DISPATCH_OWNER', 'CPQ-016':'RULESET_OWNER',
    'CPQ-018':'THIRD_HOP_READBACK',
}
# Validated review scheduling (not a second causal-root register).
WAVES = {
    'SCOUT_DISJOINT':['CPQ-003','CPQ-005','CPQ-011','CPQ-018'],
    'SOURCE_OWNER':['CPQ-010'],
    'DEPENDENCY_WAIT':['CPQ-013'],
    'EXTERNAL_RETURN':['CPQ-009','CPQ-015','CPQ-016'],
}


def required(ok, msg):
    if not ok: raise ValueError(msg)


def ordkey(s):
    m = KEY.fullmatch(s) if isinstance(s, str) else None
    required(m is not None, 'non-ordinal history key')
    return tuple(int(n) for n in m.groups())


def identity_sha(source_sha):
    required(isinstance(source_sha,str) and SHA40.fullmatch(source_sha), 'invalid exact-source SHA')
    return source_sha


def _latest(item):
    h=item.get('history')
    required(isinstance(h,list) and h, 'missing lifecycle history')
    keys=[ordkey(row.get('at')) for row in h]
    required(keys == sorted(set(keys)), 'unordered/duplicate history')
    return h[-1]


def check_queue(queue):
    required(isinstance(queue,dict) and queue.get('schema') == 'missioncontrol.code_purple.bd_queue.v1', 'canonical queue schema missing')
    required(queue.get('authority_transfer') is False and queue.get('formal_credit_delta') == 0, 'authority or formal-credit promotion')
    items=queue.get('items')
    required(isinstance(items,list) and len(items)==18, '18-item canonical queue must be complete')
    ids=[x.get('id') for x in items]
    required(len(set(ids))==18 and all(re.fullmatch(r'CPQ-\d{3}',x) for x in ids), 'bad/duplicate IDs')
    for i in items:
        now=_latest(i)
        required(now.get('state') in OPEN|DONE, 'invalid lifecycle state')
        required(isinstance(now.get('flow'), str), 'missing routing state')
        required(isinstance(i.get('title'),str) and i['title'], 'missing item title')
        required(isinstance(i.get('done_when'),str) and i['done_when'], 'missing DoV criterion')
        required(set(i.get('depends_on',[]))<=set(ids)-{i['id']}, 'orphan/self dependency')
    indexed={i['id']:i for i in items}
    visiting,visited=set(),set()
    def visit(k):
        required(k not in visiting,'dependency cycle')
        if k in visited:return
        visiting.add(k)
        for v in indexed[k].get('depends_on',[]):visit(v)
        visiting.remove(k);visited.add(k)
    for k in ids:visit(k)
    return indexed


def check_top7(data):
    required(isinstance(data,dict) and data.get('schema')=='missioncontrol.code_purple.top7_census_pulses.v1', 'wrong Top7 source schema')
    required(data.get('authority_transfer') is False, 'Top7 authority promotion')
    pulses=data.get('pulses')
    required(isinstance(pulses,list) and len(pulses)>=2, 'two observed Top7 pulses required')
    out=[]
    ref_repos=None
    for p in pulses:
        rows=p.get('rows')
        required(isinstance(rows,list) and len(rows)==7, 'Top7 denominator differs from 7')
        repos=[x.get('repo') for x in rows]
        required(len(set(repos))==7 and all(isinstance(z,str) and z for z in repos), 'duplicate/invalid Top7 repo')
        required(ref_repos is None or set(repos)==ref_repos,'Top7 repository population drift')
        ref_repos=set(repos)
        required(isinstance(p.get('pulse'),int), 'missing Top7 pulse number')
        bound=sum(bool(SHA40.fullmatch(x.get('head','')) and
                       type(x.get('run_id')) is int and x['run_id']>0 and
                       type(x.get('job_id')) is int and x['job_id']>0 and
                       type(x.get('attempt')) is int and x['attempt']>0)
                  for x in rows)
        out.append({'pulse':p['pulse'],'as_of':p.get('observed_on'),
                    'repo_count':7,'native_identity_complete':bound,
                    'source':p.get('source')})
    required(all(out[n]['pulse']<out[n+1]['pulse'] for n in range(len(out)-1)), 'Top7 pulse sequence disorder')
    pair_eligible=all(z['native_identity_complete']==7 for z in out[-2:])
    return {'pulses':out,'pair_eligible_for_source_match':pair_eligible,
            'matched_fleet_delta':None,
            'comparison':'SOURCE_MATCHED_FLEET_DELTA_PENDING' if pair_eligible else 'WITHHELD_INCOMPLETE_PREVIOUS_NATIVE_IDENTITIES',
            'top14_promotion':None}


def converge(queue,top7,source_sha,*,observed_on=None):
    identity_sha(source_sha)
    idx=check_queue(queue)
    t=check_top7(top7)
    items=[]
    for k in sorted(idx):
        item=idx[k];last=_latest(item)
        route=ROUTING.get(k) if last['state'] in OPEN else None
        items.append({'id':k,'title':item['title'],'severity':item.get('severity'),
                      'state':last['state'],'flow':last['flow'],
                      'obligation':item['done_when'],
                      'control_when':item.get('control_when'),
                      'route':route,'dependencies':item.get('depends_on',[]),
                      'evidence':last.get('evidence'),'ordinal':last['at'],
                      'source_links':item.get('links',[])})
    open_ids={i['id'] for i in items if i['state'] in OPEN}
    declared=set(sum(WAVES.values(),[]))
    required(open_ids==declared and all(i in idx for i in declared), 'unclassified/open work order drift')
    todo=sum(i['state']=='TODO' for i in items)
    active=sum(i['state']=='ACTIVE' for i in items)
    reader=sum(i['state']=='UNKNOWN_NEEDS_READER' for i in items)
    done=sum(i['state'] in DONE for i in items)
    freshness=source_freshness.annotate(
        [{'name':'Top7 pulse '+str(p['pulse']), 'as_of':p['as_of'], 'as_of_basis':'observed_on'}
         for p in t['pulses']], observed_on=observed_on, ttl_days=14)
    return {'schema':SCHEMA,'source':{'repository':'GBOGEB/pipeline-automation-hub',
             'path':'mission-control/federation-atlas/CODE_PURPLE_BD_QUEUE_v1.json',
             'exact_master_sha':source_sha},
            'observed_on':observed_on,'metrics':{'canonical_rows':len(items),'open':len(open_ids),
             'active':active,'todo':todo,'reader':reader,'done':done,
             'work_orders_with_routes':sum(i['route'] is not None for i in items),
             'source_readback_coverage':{'numerator':len(items),'denominator':18},
             'accepted_causal_root_closures':None,'qualified_changed_line_coverage':None,
             'matched_wave_effect':None},
            'top7':t,'freshness':freshness,'waves':WAVES,'items':items,
            'root_credit':'UNKNOWN','admission':'HOLD','authority_transfer':False,
            'security_waiver':False,'dispatch_authorized':False,'formal_credit_delta':0}


def render_html(report):
    # This generated view is *not* the canonical ledger.
    data=json.dumps(report,sort_keys=True,separators=(',',':'),ensure_ascii=True).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CODE PURPLE | CPQ Convergence N5</title><style>
    :root{color-scheme:dark;font-family:system-ui;background:#10131d;color:#f2f4fc}*{box-sizing:border-box}body{max-width:1320px;margin:auto;padding:24px}h1{font-size:clamp(23px,3vw,34px)}.dim{color:#acb7ca}.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(165px,1fr));gap:12px;margin:20px 0}.metrics>div{padding:18px;background:#202c40;border-radius:10px}.metrics b{display:block;font-size:28px}main{overflow-x:auto}table{border-collapse:collapse;width:100%}th,td{padding:13px;border-bottom:1px solid #39445d;text-align:left;vertical-align:top;font-size:13px}input,select{padding:11px;border-radius:8px;background:#202c40;color:white;border:1px solid #68718b;margin:5px 0}input{min-width:min(100%,350px)}a{color:#85d4ee}.hold{color:#ffcb89}footer{margin-top:24px;color:#acb7ca}.tiny{font-size:12px;overflow-wrap:anywhere}#top7{overflow-wrap:anywhere}@media(max-width:520px){body{padding:12px}table{min-width:720px}}</style></head><body><p class="hold">READ ONLY / NO MERGE / NO DISPATCH</p><h1>CODE PURPLE · N5 CPQ Convergence</h1><p class="dim">Source-bound 18-row ledger projection. N1/N2 receipts are not independent experiment trials. Owner gates remain distinct.</p><div class="tiny" id="source"></div><section class="metrics" id="metrics"></section><label for="search">Search CPQ records</label> <input id="search" type="search" placeholder="ID, title, route, evidence"><label for="status">Status</label> <select id="status"><option value="OPEN">Open</option><option value="ALL">All 18</option><option value="DONE">Done</option><option value="ACTIVE">Active</option><option value="TODO">To do</option><option value="UNKNOWN_NEEDS_READER">Reader</option></select><main><table><thead><tr><th>CPQ</th><th>Finding / native evidence</th><th>Status</th><th>Next proof</th></tr></thead><tbody id="items"></tbody></table></main><p class="dim" id="visible" aria-live="polite"></p><h2>Top7 denominator qualification</h2><p id="top7"></p><footer>Canonical authority: Mission Control CODE_PURPLE_BD_QUEUE_v1.json · Security/reviewer/owner controls never inferred from this review page.</footer><script>
const D='''+data+''';const E=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
document.getElementById('source').textContent=D.source.exact_master_sha+' · '+D.source.path;
const m=D.metrics;document.getElementById('metrics').innerHTML=[['Open',m.open],['Active',m.active],['To do',m.todo],['Reader',m.reader],['Done',m.done],['Reviewed',m.source_readback_coverage.numerator+'/'+m.source_readback_coverage.denominator]].map(x=>'<div><span>'+E(x[0])+'</span><b>'+E(x[1])+'</b></div>').join('');
document.getElementById('top7').textContent=D.top7.comparison+' · source matches '+(D.top7.pair_eligible_for_source_match?'eligible':'WITHHELD')+' · temporal sources '+D.freshness.sources.map(x=>x.name+':'+x.state+'('+String(x.age_days??'UNKNOWN')+'d)').join(', ')+' · matched delta UNKNOWN';
function draw(){const q=document.getElementById('search').value.toLowerCase(),filter=document.getElementById('status').value;let arr=D.items.filter(x=>(filter==='ALL'||(filter==='OPEN'?!['DONE','CONTROL','SUPERSEDED','INVALIDATED'].includes(x.state):x.state===filter))&&[x.id,x.title,x.route,x.evidence].join(' ').toLowerCase().includes(q));document.getElementById('items').innerHTML=arr.map(x=>'<tr><td>'+E(x.id)+'</td><td><strong>'+E(x.title)+'</strong><p class="dim">'+E(x.evidence)+'</p></td><td>'+E(x.state)+'</td><td>'+E(x.route??'NO ACTIVE LEASE')+'<p class="dim">'+E(x.obligation)+'</p></td></tr>').join('');document.getElementById('visible').textContent=arr.length+' of '+D.items.length+' registered records';}
for(const id of ['search','status'])document.getElementById(id).addEventListener('input',draw);draw();</script></body></html>'''


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--queue',type=Path,required=True)
    p.add_argument('--top7',type=Path,required=True)
    p.add_argument('--head',required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--observed-on')
    a=p.parse_args(argv)
    out=converge(json.loads(a.queue.read_text()),json.loads(a.top7.read_text()),a.head,observed_on=a.observed_on)
    a.out.mkdir(parents=True,exist_ok=True)
    (a.out/'cpq-n5.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    (a.out/'cpq-n5.html').write_text(render_html(out),encoding='utf-8')
    print('CPQ_N5=PASS; OPEN='+str(out['metrics']['open'])+'; ROOT_CLOSURES=UNKNOWN')
    return out

if __name__ == '__main__':main()