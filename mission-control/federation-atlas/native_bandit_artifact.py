#!/usr/bin/env python3
"""Strict read-only custody adapter for *historical* native Bandit Disjoint ZIP.

Not ABACUS's joined producer: do NOT generate BD-* causal/root IDs or closure.
Artifact authenticity requires independent GitHub run/artifact metadata readback.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import re
import stat
import zipfile
from collections import Counter
from pathlib import Path

HEX40=re.compile(r'[0-9a-f]{40}\Z')
HEX64=re.compile(r'[0-9a-f]{64}\Z')
LANES=('B2-source','B3-subprocess','B4-files-secrets','B5-tests')
MAX_FILE=30_000_000
MAX_TOTAL=50_000_000


def demand(cond,why):
    if not cond: raise ValueError(why)


def digest(data): return hashlib.sha256(data).hexdigest()


def inspect_archive(archive, *, archive_digest, expected_sha, run_id, job_id):
    archive=Path(archive)
    demand(archive.is_file() and not archive.is_symlink() and archive.stat().st_size<=MAX_FILE, 'archive file unsafe')
    demand(bool(HEX40.fullmatch(expected_sha)) and bool(HEX64.fullmatch(archive_digest)), 'invalid pinned identity')
    demand(type(run_id) is int and run_id>0 and type(job_id) is int and job_id>0,'invalid run/job identity')
    raw=archive.read_bytes()
    demand(digest(raw)==archive_digest, 'external archive digest mismatch')
    with zipfile.ZipFile(archive) as z:
        entries=z.infolist();names=[i.filename for i in entries]
        demand(len(entries)<100 and len(names)==len(set(names)),'duplicate/oversize zip entries')
        for info in entries:
            path=info.filename.replace('\\','/')
            demand(path and not path.startswith('/') and '..' not in path.split('/') and ':' not in path,
                   'unsafe zip member path')
            demand(info.file_size<=MAX_FILE and stat.S_IFMT(info.external_attr>>16) != stat.S_IFLNK,
                   'zip member too large or symlink')
        demand(sum(i.file_size for i in entries)<MAX_TOTAL,'uncompressed archive too large')
        demand('disjoint.json' in names and 'SHA256SUMS' in names and 'full.json' in names,
               'required source members missing')
        demand(z.testzip() is None,'zip CRC failure')
        sums={}
        for line in z.read('SHA256SUMS').decode().splitlines():
            parts=line.split('  ')
            demand(len(parts)==2 and HEX64.fullmatch(parts[0]),'bad nested sha256 manifest')
            name=parts[1].removeprefix('bandit-evidence/')
            demand(name in names and name not in sums, 'manifest references missing/duplicate member')
            sums[name]=parts[0]
        demand('disjoint.json' in sums and 'full.json' in sums,'missing required member hashes')
        for name,sha in sums.items(): demand(digest(z.read(name))==sha, 'nested member digest mismatch: '+name)
        d=json.loads(z.read('disjoint.json'))
        full=json.loads(z.read('full.json'))
        demand(d.get('schema')=='bandit.disjoint.census.v1' and d.get('exact_sha')==expected_sha,
               'wrong scanner schema / exact source SHA')
        demand(d.get('authority_transfer') is False,'source authority escalation')
        lanes=d.get('lanes')
        demand(isinstance(lanes,dict) and set(lanes)==set(LANES),'unknown/missing lane')
        demand(isinstance(full.get('results'),list),'missing full scan results')
        total=0;unique=set();fileowners={};per_lane={};rules=Counter();findings=[]
        for lane in LANES:
            block=lanes[lane];items=block.get('items')
            demand(isinstance(items,list),'lane item array missing')
            paths=set()
            for item in items:
                fp=item.get('fingerprint');path=item.get('path');code=item.get('rule');lineno=item.get('line')
                demand(isinstance(fp,str) and HEX64.fullmatch(fp),'bad fingerprint')
                demand(isinstance(path,str) and path and not path.startswith('/') and
                       '..' not in path.replace('\\','/').split('/') and '\\' not in path,
                       'unsafe source path')
                demand(isinstance(code,str) and bool(re.fullmatch(r'B[0-9]{3}',code)) and
                       type(lineno) is int and lineno>0,'bad rule or line')
                demand(fp not in unique,'duplicate fingerprint across lanes')
                demand(path not in fileowners or fileowners[path]==lane,'multiple disjoint owners')
                unique.add(fp); paths.add(path);fileowners[path]=lane;rules[code]+=1
                findings.append({'fingerprint':fp,'path':path,'line':lineno,'rule':code,'lane':lane})
            demand(type(block.get('findings')) is int and block['findings']==len(items) and
                   type(block.get('files')) is int and block['files']==len(paths),
                   'native lane numerator/denominator mismatch')
            per_lane[lane]={'findings':len(items),'files':len(paths)};total+=len(items)
        demand(type(d.get('total_unique')) is int and d['total_unique']==total,
               'total unique native denominator mismatch')
        demand(len(full['results'])==total,'disjoint total differs from original full scan')
        return {'schema':'missioncontrol.native-bandit-custody.v1',
                'evidence_class':'NATIVE_SCANNER_ARCHIVE_BYTES_VERIFIED_NOT_JOINED_CENSUS',
                'repository':'GBOGEB/ABACUS','source_sha':expected_sha,
                'run_id':run_id,'job_id':job_id,
                'run_url':f'https://github.com/GBOGEB/ABACUS/actions/runs/{run_id}',
                'artifact_sha256':archive_digest,'disjoint_member_sha256':sums['disjoint.json'],
                'member_sha256_verified':len(sums),'native_fingerprints':total,
                'unique_source_files':len(fileowners),'lanes':per_lane,
                'rules':dict(sorted(rules.items(),key=lambda v:(-v[1],v[0]))),
                'findings':findings,
                'current_main_proof':None,'native_joined_receipt':None,
                'causal_roots_confirmed':None,'root_closures':None,
                'independent_trials':None,'scan_configuration_equivalence':None,
                'merge_admission':'HOLD','dispatch_authorized':False,
                'security_waiver':False,'authority_transfer':False}


def render(report):
    lines=[]
    for f in report['findings']:
        meta=' '.join([f['fingerprint'],f['path'],f['rule'],f['lane']]).lower()
        lines.append('<tr data-text="'+html.escape(meta,quote=True)+'"><td>'+html.escape(f['lane'])+
          '</td><td><code>'+html.escape(f['rule'])+'</code></td><td>'+html.escape(f['path'])+
          ' : '+str(f['line'])+'</td><td class="finger">'+html.escape(f['fingerprint'][:20])+'...</td></tr>')
    cells=''.join('<article><span>'+html.escape(lane)+'</span><strong>'+str(report['lanes'][lane]['findings'])+
      '</strong><small>'+str(report['lanes'][lane]['files'])+' unique files</small></article>' for lane in LANES)
    template='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CODE PURPLE N+3 | native Bandit proof</title>
<style>:root{color-scheme:dark;font-family:system-ui;background:#071523;color:#ecf5fc}body{max-width:1440px;margin:auto;padding:24px}h1{font-size:clamp(22px,3vw,36px)}p{color:#bacad8}article{padding:18px;background:#112a3d;border-radius:12px;border:1px solid #28465a}article span,article strong,article small{display:block}article strong{font-size:29px}article small{color:#b7c9d9}.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}.warn{color:#ffcc9e;font-weight:700}code,.finger{font-family:monospace;overflow-wrap:anywhere}a{color:#8de8fd}input{width:100%;padding:13px;background:#0c2739;border:1px solid #50768f;border-radius:7px;color:white}table{border-collapse:collapse;table-layout:fixed;width:100%;font-size:13px}td,th{text-align:left;word-break:break-word;padding:10px;border-bottom:1px solid #30475a;overflow-wrap:anywhere}.sheet{max-height:630px;overflow:auto}tr[hidden]{display:none}footer{margin-top:25px}@media(max-width:420px){body{padding:10px}.finger{display:none}table{font-size:11px}}</style></head><body>
<p class="warn">HISTORICAL SCANNER EVIDENCE • NO NATIVE JOINED OUTPUT • ADMISSION HOLD</p><h1>MYCELIUM / Golden Thread · Native Bandit census</h1><p>Exact input commit <code>__SHA__</code>, run <a href="__RUN__">__RUN_ID__</a>. Verified archive hash: <code>__DIGEST__</code>. No causal roots are inferred from scanner fingerprints.</p><div class="stats">__STATS__</div><h2>Search native fingerprints (not accepted roots)</h2><input id="query" type="search" aria-label="Search fingerprints" placeholder="Filter rule, lane, path or fingerprint" oninput="filterRows()"><p id="counter" aria-live="polite"></p><div class="sheet"><table><thead><tr><th>Owner</th><th>Rule</th><th>Path / line</th><th>Fingerprint</th></tr></thead><tbody id="rows">__ROWS__</tbody></table></div><footer><p>This is a locally rendered review of a native, digest-verified historical Bandit artifact. ABACUS #1929 retains causal ownership. Current-main scan, independently authenticated joined receipt, debugger lineage, comparable temporal delta, root closure and dispatch remain UNKNOWN/HOLD.</p></footer><script>function filterRows(){const q=document.getElementById('query').value.toLowerCase();let n=0;for(const r of document.querySelectorAll('#rows tr')){const match=r.dataset.text.includes(q);r.hidden=!match;if(match)n++;}document.getElementById('counter').textContent=n+' of __COUNT__ native fingerprint records';}filterRows();</script></body></html>'''
    return (template.replace('__SHA__',report['source_sha']).replace('__RUN__',report['run_url'])
             .replace('__RUN_ID__',str(report['run_id'])).replace('__DIGEST__',report['artifact_sha256'])
             .replace('__STATS__',cells).replace('__ROWS__',''.join(lines))
             .replace('__COUNT__',str(report['native_fingerprints'])))


def main(argv=None):
    p=argparse.ArgumentParser()
    for flag in ('archive','archive-sha256','source-sha','out'):p.add_argument('--'+flag,required=True)
    p.add_argument('--run-id',required=True,type=int);p.add_argument('--job-id',required=True,type=int)
    a=p.parse_args(argv)
    report=inspect_archive(a.archive,archive_digest=a.archive_sha256,
            expected_sha=a.source_sha,run_id=a.run_id,job_id=a.job_id)
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    (out/'native-bandit-custody.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    (out/'native-bandit-census.html').write_text(render(report),encoding='utf-8')
    print('HISTORICAL_NATIVE_BANDIT_ARCHIVE_VERIFY=PASS; CURRENT_JOIN=UNKNOWN; ADMISSION=HOLD')
    return report

if __name__=='__main__':main()