#!/usr/bin/env python3
"""MissionControl Golden Thread v1: append-only hash chain + deterministic replay."""
from __future__ import annotations
import argparse, copy, datetime as dt, hashlib, json, re, sys
from pathlib import Path

LEDGER_SCHEMA='missioncontrol.golden_thread_ledger.v1'
PROJ_SCHEMA='missioncontrol.golden_thread_projection.v1'
GENESIS='GENESIS'
SHA_RE=re.compile(r'^[0-9a-f]{7,40}$',re.I)
EVENT_TYPES={
'OBSERVED','BOOTSTRAP_RECONSTRUCTED','CLASSIFIED','ROOT_CREATED','ATTACHED_TO_ROOT',
'WORK_ORDER_CREATED','CAMPAIGN_ATTACHED','MERGED_INTO','SPLIT_FROM','SUPERSEDED_BY',
'INVALIDATED','REOPENED','STATE_CHANGED','CONTROL_PROMOTED','EVIDENCE_ADDED',
'AUTHORITY_BOUNDARY_ASSERTED','NON_COMPENSATING_GATE_SET','RETIREMENT_CANDIDATE'}

class GoldenThreadError(ValueError): pass

def cjson(v): return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def digest(v): return 'sha256:'+hashlib.sha256(cjson(v).encode()).hexdigest()
def event_digest(e): return digest({k:v for k,v in e.items() if k!='this_event_digest'})
def ts(v):
    if v.endswith('Z'): v=v[:-1]+'+00:00'
    try: x=dt.datetime.fromisoformat(v)
    except ValueError as exc: raise GoldenThreadError(f'invalid timestamp {v}') from exc
    if x.tzinfo is None: raise GoldenThreadError(f'timestamp must be timezone-aware: {v}')
    return x.astimezone(dt.timezone.utc)
def load(p):
    v=json.loads(Path(p).read_text(encoding='utf-8'))
    if not isinstance(v,dict): raise GoldenThreadError('ledger must be object')
    return v
def dump(v,out=None):
    s=json.dumps(v,indent=2,sort_keys=True,ensure_ascii=False)+'\n'
    if out: Path(out).write_text(s,encoding='utf-8')
    else: sys.stdout.write(s)
def req(e,k):
    if k not in e: raise GoldenThreadError(f"event {e.get('event_id','?')} missing {k}")
    return e[k]
def check_shape(e):
    if req(e,'event_type') not in EVENT_TYPES: raise GoldenThreadError(f"bad event_type {e['event_type']}")
    for k in ('occurred_at','recorded_at'): ts(req(e,k))
    for k in ('event_id','actor','subject_ref','authority_domain'): 
        if not isinstance(req(e,k),str): raise GoldenThreadError(f'{k} must be string')
    if not isinstance(req(e,'evidence_refs'),list): raise GoldenThreadError('evidence_refs must be list')
    if not isinstance(req(e,'non_compensating_preserved'),bool): raise GoldenThreadError('non_compensating_preserved must be bool')
    if e.get('projection_schema_version')!=1: raise GoldenThreadError('projection_schema_version must be 1')
    if e['event_type']=='BOOTSTRAP_RECONSTRUCTED':
        for k in ('observed_source_timestamp','reconstruction_timestamp','reconstruction_method'): req(e,k)
        ts(e['observed_source_timestamp']); ts(e['reconstruction_timestamp'])

def seal(ledger):
    x=copy.deepcopy(ledger); x.setdefault('schema',LEDGER_SCHEMA); x.setdefault('projection_schema_version',1); x.setdefault('authority_transfer',False)
    prev=GENESIS
    for i,e in enumerate(x.get('events',[]),1):
        e['seq']=i; e['previous_event_digest']=prev; e['projection_schema_version']=1; e.pop('this_event_digest',None); check_shape(e); e['this_event_digest']=event_digest(e); prev=e['this_event_digest']
    x['head_event_digest']=prev; return x

def verify(ledger):
    if ledger.get('schema')!=LEDGER_SCHEMA or ledger.get('projection_schema_version')!=1 or ledger.get('authority_transfer') is not False: raise GoldenThreadError('ledger control fields invalid')
    prev=GENESIS; ids=set(); events=ledger.get('events')
    if not isinstance(events,list): raise GoldenThreadError('events must be list')
    for i,e in enumerate(events,1):
        check_shape(e)
        if e.get('seq')!=i: raise GoldenThreadError(f"seq mismatch {e.get('event_id')}")
        if e['event_id'] in ids: raise GoldenThreadError(f"duplicate event_id {e['event_id']}")
        ids.add(e['event_id'])
        if e.get('previous_event_digest')!=prev: raise GoldenThreadError(f"chain mismatch {e['event_id']}")
        if e.get('this_event_digest')!=event_digest(e): raise GoldenThreadError(f"digest mismatch {e['event_id']}")
        prev=e['this_event_digest']
    if ledger.get('head_event_digest')!=prev: raise GoldenThreadError('head digest mismatch')
    return {'status':'PASS','event_count':len(events),'head_event_digest':prev,'authority_transfer':False}

def projection(): return {'schema':PROJ_SCHEMA,'projection_schema_version':1,'authority_transfer':False,'occurrences':{},'roots':{},'work_orders':{},'campaigns':{},'evidence':{},'lineage_edges':[],'events_applied':[]}
def bucket(p,t): return p[{'occurrence':'occurrences','root':'roots','work_order':'work_orders','campaign':'campaigns','evidence':'evidence'}[t]]
def ensure(p,ref,t,seed=None):
    b=bucket(p,t); b.setdefault(ref,{'ref':ref,'object_type':t}); b[ref].update(copy.deepcopy(seed or {})); return b[ref]
def find(p,ref):
    for k in ('occurrences','roots','work_orders','campaigns','evidence'):
        if ref in p[k]: return p[k][ref]
def edge(p,e,t,a,b): p['lineage_edges'].append({'event_id':e['event_id'],'seq':e['seq'],'type':t,'from_ref':a,'to_ref':b,'authority_domain':e['authority_domain'],'non_compensating_preserved':e['non_compensating_preserved']})

def apply(p,e):
    t=e['event_type']; q=copy.deepcopy(e.get('payload') or {}); s=e['subject_ref']; a=e.get('from_ref'); b=e.get('to_ref')
    if t in {'OBSERVED','BOOTSTRAP_RECONSTRUCTED'}:
        typ=q.pop('object_type','occurrence'); o=ensure(p,s,typ,q); o.setdefault('first_event_id',e['event_id']); o['last_event_id']=e['event_id']; o['authority_domain']=e['authority_domain']; o.setdefault('evidence_refs',[])
        for r in e['evidence_refs']:
            if r not in o['evidence_refs']: o['evidence_refs'].append(r)
        if t=='BOOTSTRAP_RECONSTRUCTED': o['bootstrap']={k:e[k] for k in ('observed_source_timestamp','reconstruction_timestamp','reconstruction_method')}
    elif t=='ROOT_CREATED': ensure(p,s,'root',q).setdefault('occurrence_refs',[])
    elif t=='CLASSIFIED':
        o=find(p,s) or ensure(p,s,q.pop('object_type','occurrence')); o.setdefault('classification_history',[]).append({'event_id':e['event_id'],**q}); o.update({k:q[k] for k in ('routing_disposition','bd_state','historian_state','canonical_root') if k in q})
    elif t=='ATTACHED_TO_ROOT':
        if not a or not b: raise GoldenThreadError('ATTACHED_TO_ROOT requires from_ref/to_ref')
        o=ensure(p,a,'occurrence'); r=ensure(p,b,'root'); o['root_ref']=b; r.setdefault('occurrence_refs',[])
        if a not in r['occurrence_refs']: r['occurrence_refs'].append(a)
        edge(p,e,t,a,b)
    elif t=='WORK_ORDER_CREATED':
        w=ensure(p,s,'work_order',q); w['parent_ref']=a
        if a:
            o=find(p,a)
            if o: o.setdefault('work_order_refs',[]).append(s)
        edge(p,e,t,a,s)
    elif t=='CAMPAIGN_ATTACHED':
        m=a or s; c=ensure(p,b,'campaign'); c.setdefault('member_refs',[]).append(m); edge(p,e,t,m,b)
    elif t=='EVIDENCE_ADDED':
        r=a or s; ensure(p,r,'evidence',q.get('evidence') or {}); o=find(p,b) if b else None
        if o: o.setdefault('evidence_refs',[]).append(r)
        edge(p,e,t,r,b)
    elif t=='AUTHORITY_BOUNDARY_ASSERTED':
        o=find(p,s);
        if o: o['authority_domain']=q.get('authority_domain',e['authority_domain'])
    elif t=='NON_COMPENSATING_GATE_SET':
        o=find(p,s)
        if o: o.update({'non_compensating':True,'blocking_predicate':q.get('blocking_predicate'),'reentry_trigger':q.get('reentry_trigger')})
    elif t in {'STATE_CHANGED','CONTROL_PROMOTED','INVALIDATED','REOPENED','RETIREMENT_CANDIDATE'}:
        o=find(p,s) or ensure(p,s,q.pop('object_type','occurrence'))
        if t=='STATE_CHANGED': o['state']=q.get('state')
        elif t=='CONTROL_PROMOTED': o['state']='CONTROL'
        elif t=='INVALIDATED': o['state']='INVALIDATED'
        elif t=='REOPENED': o['state']=q.get('state','ACTIVE')
        else: o.update({'retirement_candidate':True,'retirement_withheld':q.get('withheld',True),'retirement_predicate':q.get('victory_predicate')})
    elif t in {'MERGED_INTO','SPLIT_FROM','SUPERSEDED_BY'}:
        if not a or not b: raise GoldenThreadError(f'{t} requires from_ref/to_ref')
        edge(p,e,t,a,b)
    p['events_applied'].append(e['event_id'])

def select(ledger,boundary=None):
    ev=ledger['events']
    if boundary is None: return ev
    for i,e in enumerate(ev):
        if e['event_id']==boundary: return ev[:i+1]
    if SHA_RE.match(boundary):
        ix=[i for i,e in enumerate(ev) if boundary in (e.get('source_sha'),(e.get('payload') or {}).get('source_sha'))]
        if not ix: raise GoldenThreadError(f'no event binds source SHA {boundary}')
        return ev[:max(ix)+1]
    cut=ts(boundary); return [e for e in ev if ts(e['occurred_at'])<=cut]

def _rebuild_events(ledger,ev,boundary):
    p=projection()
    for e in ev: apply(p,e)
    for k in ('occurrences','roots','work_orders','campaigns','evidence'): p[k]=dict(sorted(p[k].items()))
    p['lineage_edges']=sorted(p['lineage_edges'],key=lambda x:(x['seq'],x['event_id']))
    terminal={'SUPERSEDED_WITH_REPLACEMENT','INVALIDATED','CONTROL_ORCHESTRATION','EVIDENCE_ONLY','WORK_ORDER_CHILD','ROOT_EXISTING','ROOT_NEW','CAMPAIGN_MEMBER_ONLY','UNKNOWN_NEEDS_READER'}
    orphan=[r for r,o in p['occurrences'].items() if not o.get('root_ref') and o.get('routing_disposition') not in terminal]
    unknown=[r for r,o in p['occurrences'].items() if 'UNKNOWN_NEEDS_READER' in (o.get('historian_state'),o.get('bd_state'))]
    p['metrics']={'event_count':len(ev),'occurrence_count':len(p['occurrences']),'root_count':len(p['roots']),'work_order_count':len(p['work_orders']),'campaign_count':len(p['campaigns']),'evidence_count':len(p['evidence']),'lineage_edge_count':len(p['lineage_edges']),'orphan_occurrence_count':len(orphan),'orphan_occurrences':orphan,'unknown_needs_reader_count':len(unknown),'unknown_needs_reader':unknown,'lineage_retention_coverage':1.0 if not p['occurrences'] else round((len(p['occurrences'])-len(orphan))/len(p['occurrences']),6)}
    p['boundary']=boundary or 'CURRENT'; p['head_event_digest']=ev[-1]['this_event_digest'] if ev else GENESIS; p['projection_digest']=digest(p); return p


def rebuild(ledger,boundary=None):
    """Verify full source chain and rebuild an existing v1 boundary unchanged."""
    verify(ledger)
    return _rebuild_events(ledger,select(ledger,boundary),boundary)

def _utc(v):
    """Normalize a governed instant without using host-local timezone."""
    return ts(v).isoformat().replace('+00:00','Z')

def rebuild_known_at(ledger,known_at,occurred_by=None):
    """Bitemporal read: what was knowable by K about events through O?

    Unlike rebuild-as-of (event occurrence time), this explicitly excludes
    evidence recorded AFTER K even if its observed source time was earlier.
    The complete sealed ledger is verified first, and sparse projections
    remain marked as selections rather than an independently sealed chain.
    """
    verify(ledger)
    known=ts(known_at)
    occurred=ts(occurred_by) if occurred_by is not None else None
    events=[e for e in ledger['events']
            if ts(e['recorded_at'])<=known
            and (occurred is None or ts(e['occurred_at'])<=occurred)]
    p=_rebuild_events(ledger,events,'BITEMPORAL_READ_ONLY')
    seqs=[e['seq'] for e in events]
    p['temporal_selection']={
        'kind':'RECORDED_KNOWLEDGE_AND_OBSERVED_EVENT_WINDOW',
        'known_at_utc':_utc(known_at),
        'occurred_by_utc':_utc(occurred_by) if occurred_by is not None else None,
        'selected_event_ids':[e['event_id'] for e in events],
        'selected_event_count':len(events),
        'excluded_event_count':len(ledger['events'])-len(events),
        'chain_prefix':seqs==list(range(1,len(seqs)+1)),
        'full_ledger_verified':True,
        'full_ledger_head_event_digest':ledger['head_event_digest'],
        'partial_selection_is_new_authority':False,
    }
    p.pop('projection_digest',None)
    p['projection_digest']=digest(p)
    return p

def diff_known_at(ledger,before_known_at,after_known_at,occurred_by=None):
    """Immutable N-1 -> N knowledge delta; no inferred causal root closure."""
    if ts(before_known_at)>ts(after_known_at):
        raise GoldenThreadError('known-at windows must be chronological')
    a=rebuild_known_at(ledger,before_known_at,occurred_by)
    b=rebuild_known_at(ledger,after_known_at,occurred_by)
    seen=set(a['events_applied'])
    added=set(b['events_applied'])-seen
    keys=('event_count','occurrence_count','root_count','work_order_count',
          'campaign_count','evidence_count','lineage_edge_count',
          'orphan_occurrence_count','unknown_needs_reader_count')
    return {
        'schema':'missioncontrol.golden_thread_known_diff.v1',
        'before_known_at_utc':a['temporal_selection']['known_at_utc'],
        'after_known_at_utc':b['temporal_selection']['known_at_utc'],
        'occurred_by_utc':b['temporal_selection']['occurred_by_utc'],
        'source_ledger_head_digest':ledger['head_event_digest'],
        'before_projection_digest':a['projection_digest'],
        'after_projection_digest':b['projection_digest'],
        'events_added':[{'seq':e['seq'],'event_id':e['event_id'],
                         'event_type':e['event_type'],'subject_ref':e['subject_ref']}
                        for e in ledger['events'] if e['event_id'] in added],
        'metric_delta':{k:b['metrics'][k]-a['metrics'][k] for k in keys},
        'formal_root_closure_credit':None,
        'authority_transfer':False,
    }

def expand_root(ledger,root,boundary=None):
    p=rebuild(ledger,boundary)
    if root not in p['roots']: raise GoldenThreadError(f'root not found: {root}')
    roots={root}; occ=set(); wo=set(); evid=set(); camps=set(); edges=[]
    for e in p['lineage_edges']:
        if e['type']=='ATTACHED_TO_ROOT' and e['to_ref'] in roots: occ.add(e['from_ref']); edges.append(e)
    for e in p['lineage_edges']:
        if e['type']=='WORK_ORDER_CREATED' and e['from_ref'] in roots|occ: wo.add(e['to_ref']); edges.append(e)
        elif e['type']=='EVIDENCE_ADDED' and e['to_ref'] in roots|occ|wo: evid.add(e['from_ref']); edges.append(e)
        elif e['type']=='CAMPAIGN_ATTACHED' and e['from_ref'] in roots|wo: camps.add(e['to_ref']); edges.append(e)
        elif e['type'] in {'MERGED_INTO','SPLIT_FROM','SUPERSEDED_BY'} and (e['from_ref'] in roots or e['to_ref'] in roots): edges.append(e)
    out={'schema':'missioncontrol.golden_thread_expansion.v1','root_ref':root,'boundary':boundary or 'CURRENT','roots':{k:p['roots'][k] for k in sorted(roots) if k in p['roots']},'occurrences':{k:p['occurrences'][k] for k in sorted(occ)},'work_orders':{k:p['work_orders'][k] for k in sorted(wo)},'evidence':{k:p['evidence'][k] for k in sorted(evid)},'campaigns':{k:p['campaigns'][k] for k in sorted(camps)},'lineage_edges':edges}
    out['recovery_metrics']={'occurrence_recovery_count':len(occ),'evidence_recovery_count':len(evid),'root_recovery_count':len(roots),'lineage_edge_count':len(edges)}; out['expansion_digest']=digest(out); return out

def diff(ledger,a,b):
    ea,eb=select(ledger,a),select(ledger,b); ids={e['event_id'] for e in ea}; delta=[e for e in eb if e['event_id'] not in ids]; pa,pb=rebuild(ledger,a),rebuild(ledger,b)
    keys=('event_count','occurrence_count','root_count','work_order_count','campaign_count','evidence_count','lineage_edge_count','orphan_occurrence_count','unknown_needs_reader_count')
    return {'schema':'missioncontrol.golden_thread_diff.v1','from':a,'to':b,'from_projection_digest':pa['projection_digest'],'to_projection_digest':pb['projection_digest'],'events_added':[{'seq':e['seq'],'event_id':e['event_id'],'event_type':e['event_type'],'subject_ref':e['subject_ref'],'from_ref':e.get('from_ref'),'to_ref':e.get('to_ref')} for e in delta],'metric_delta':{k:pb['metrics'][k]-pa['metrics'][k] for k in keys},'authority_transfer':False}

def main(argv=None):
    ap=argparse.ArgumentParser(); sp=ap.add_subparsers(dest='cmd',required=True)
    for n in ('verify','rebuild-current'): p=sp.add_parser(n); p.add_argument('ledger'); p.add_argument('--out')
    p=sp.add_parser('seal'); p.add_argument('ledger'); p.add_argument('--out',required=True)
    p=sp.add_parser('rebuild-as-of'); p.add_argument('ledger'); p.add_argument('boundary'); p.add_argument('--out')
    p=sp.add_parser('expand-root'); p.add_argument('ledger'); p.add_argument('root'); p.add_argument('--as-of'); p.add_argument('--out')
    p=sp.add_parser('diff'); p.add_argument('ledger'); p.add_argument('a'); p.add_argument('b'); p.add_argument('--out')
    p=sp.add_parser('rebuild-known-at'); p.add_argument('ledger'); p.add_argument('known_at'); p.add_argument('--occurred-by'); p.add_argument('--out')
    p=sp.add_parser('diff-known-at'); p.add_argument('ledger'); p.add_argument('before_known_at'); p.add_argument('after_known_at'); p.add_argument('--occurred-by'); p.add_argument('--out')
    a=ap.parse_args(argv)
    try:
        l=load(a.ledger)
        if a.cmd=='verify': v=verify(l)
        elif a.cmd=='seal': v=seal(l)
        elif a.cmd=='rebuild-current': v=rebuild(l)
        elif a.cmd=='rebuild-as-of': v=rebuild(l,a.boundary)
        elif a.cmd=='expand-root': v=expand_root(l,a.root,a.as_of)
        elif a.cmd=='rebuild-known-at': v=rebuild_known_at(l,a.known_at,a.occurred_by)
        elif a.cmd=='diff-known-at': v=diff_known_at(l,a.before_known_at,a.after_known_at,a.occurred_by)
        else: v=diff(l,a.a,a.b)
        dump(v,a.out); return 0
    except GoldenThreadError as exc: print('FAIL:',exc,file=sys.stderr); return 2
if __name__=='__main__': raise SystemExit(main())

# Compatibility names used by tests and future callers.
verify_ledger = verify
diff_boundaries = diff
