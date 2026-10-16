#!/usr/bin/env python3
"""Immutable HTML projection: proposed disjoint workers and source-bound P3 observations."""
from __future__ import annotations
import argparse
import hashlib
import html
import json
from pathlib import Path
import re

SCHEMA='code-purple.scale.source-observation.v1'
SHA=re.compile(r'^[a-f0-9]{40}$')

def validate(plan,obs):
    # No import side effects; reuse the strict worker manifest contract.
    from worker_devkit import validate_plan
    validate_plan(plan)
    a=obs.get('authority',{})
    if obs.get('schema')!=SCHEMA or a.get('merge_admission')!='HOLD' or a.get('security_waiver') is not False or a.get('authority_transfer') is not False or a.get('accepted_rex') is not None or a.get('root_closed') is not None:
        raise ValueError('observation authority inversion')
    for v in obs.get('source_heads',{}).values():
        if not isinstance(v,str) or not SHA.fullmatch(v):raise ValueError('observation full SHA required')
    prs=obs.get('prs',[])
    if not prs:raise ValueError('missing PR census')
    seen=set()
    for p in prs:
        key=(p.get('repo'),p.get('number'))
        if key in seen:raise ValueError('duplicate PR')
        seen.add(key)
        if p.get('source')!='https://github.com/'+str(p['repo'])+'/pull/'+str(p['number']):raise ValueError('invalid PR URL')
        if not isinstance(p.get('head_sha'),str) or not SHA.fullmatch(p['head_sha']):raise ValueError('invalid PR head')
        if any(type(p.get(k)) is not int or p[k]<0 for k in ('success','failure','cancelled','pending')):raise ValueError('invalid workflow count')
        if p.get('state') not in ('MERGED_MAIN','MERGED_FEATURE','OPEN_DRAFT'):raise ValueError('unknown PR state')
    return obs


def page(plan,obs,source_digest,plan_digest):
    validate(plan,obs)
    esc=lambda x:html.escape(str(x),quote=True)
    rows=''.join('<tr data-type="'+esc(t['type'])+'"><td>'+esc(t['id'])+'</td><td>'+esc(t['type'])+'</td><td>'+esc(t['priority'])+'</td><td>'+esc(','.join(t['depends_on']) or 'none')+'</td><td>'+esc(', '.join(t['path_leases']))+'</td><td>'+('LOCAL READ ONLY' if t['read_only'] else 'STAGED OWNER GATE')+'</td></tr>' for t in plan['tasks'])
    prs=''.join('<tr><td><a href="'+esc(p['source'])+'" rel="noopener noreferrer">'+esc(p['repo'])+' #'+str(p['number'])+'</a></td><td>'+esc(p['state'])+'</td><td>'+str(p['success'])+'</td><td>'+esc(p['base'])+'</td><td><code>'+esc(p['head_sha'][:12])+'</code></td></tr>' for p in obs['prs'])
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="referrer" content="no-referrer"><meta name="source-sha256" content="%s"><title>CODE PURPLE · Worker and IDE P3</title><style>
:root{color-scheme:dark;--bg:#0c1526;--panel:#192c42;--ink:#f0f7ff;--muted:#b5c8dc;--mint:#5ae1b5;--amber:#ffd091;--line:#3f607d}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 system-ui,sans-serif}main{max-width:1200px;margin:auto;padding:28px}a{color:#9ed0ff}h1{font-size:clamp(26px,4vw,45px);letter-spacing:-.03em;margin:6px 0}h2{margin:0 0 14px;font-size:20px}p{color:var(--muted)}.top{letter-spacing:.12em;font-size:12px;color:var(--mint);font-weight:800}.warn{border-left:3px solid var(--amber);color:var(--amber);background:#42332e;padding:12px 16px;margin:18px 0}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.card,section{background:var(--panel);border:1px solid var(--line);padding:17px;border-radius:14px;margin:12px 0}.card b{display:block;font-size:30px;color:var(--mint)}.card small{font-size:12px;color:var(--muted)}.scroll{overflow-x:auto}table{width:100%%;min-width:670px;border-collapse:collapse}th,td{padding:10px;text-align:left;vertical-align:top;border-bottom:1px solid var(--line)}th{font-size:12px;color:var(--muted)}code{font-family:Consolas,monospace;color:#b0e9dd;overflow-wrap:anywhere}input{padding:10px;border-radius:7px;background:var(--bg);border:1px solid var(--line);color:var(--ink)}details{margin:10px 0;padding:8px;border-bottom:1px solid var(--line)}summary{cursor:pointer;color:#a9cffa;font-weight:650}.flow{display:flex;gap:7px;flex-wrap:wrap}.flow span{padding:7px;border:1px solid var(--line);border-radius:7px}.flow i{color:var(--mint)}.links{display:flex;gap:9px;flex-wrap:wrap}@media(max-width:760px){main{padding:14px}.grid{grid-template-columns:repeat(2,1fr)}}
</style></head><body><main><div class="top">SFED / CODE PURPLE / MISSIONCONTROL</div><h1>Multi-worker scaling and local developer path</h1><p>Supporting P3 projection from existing merged-PR H1 and new worker-proposal manifest. Not a new root register or dispatch controller.</p><div class="warn">Admission HOLD · 2 workers proposed / 4 conditional · Actual Crew/REX UNKNOWN · Security/A10 independent.</div><div class="grid"><div class="card"><small>Selected PRs</small><b>%d</b><small>Mixed feature/main/draft</small></div><div class="card"><small>Selected PASS runs</small><b>%d</b><small>PR associated, not main</small></div><div class="card"><small>Proposed worker nodes</small><b>%d</b><small>No launches credited</small></div><div class="card"><small>Formal closed roots</small><b>?</b><small>UNKNOWN / not zero</small></div></div>
<section><h2>1. The evidence DAG</h2><div class="flow"><span>Scout</span><i>→</i><span>Full SHA</span><i>→</i><span>BD ownership</span><i>→</i><span>Leased tasks</span><i>→</i><span>Local cold</span><i>→</i><span>Native exact-head</span><i>→</i><span>Independent admission</span><i>→</i><span>REX/recurrence</span></div><p>Proposed waves have no native run IDs. Cold static is non-blocking, but missing native proof cannot be overridden.</p></section>
<section><h2>2. Skills, type, dependency and path leases</h2><label for="q">Filter work packages:</label> <input id="q" placeholder="P3-04, metric, path" aria-label="Filter tasks"><div class="scroll"><table id="tasks"><thead><tr><th>Task</th><th>Type</th><th>Priority</th><th>Dependencies</th><th>Source lease</th><th>Mode</th></tr></thead><tbody>%s</tbody></table></div></section>
<section><h2>3. Native PR lineage — selected cohort</h2><div class="scroll"><table><thead><tr><th>PR</th><th>Outcome type</th><th>PASS</th><th>Target</th><th>Head</th></tr></thead><tbody>%s</tbody></table></div><p>Repo × run × attempt × job is the desired clock identity; unavailable attempt/start timestamps stay UNKNOWN. Use existing H1 native collector as the canonical implementation.</p></section>
<section><h2>4. User's editor, shell and agent-scout route</h2><details open><summary>VS Code / Python Debugger</summary><p>Open repository root; select project virtual environment; merge provided <code>.vscode/tasks.json</code> and <code>launch.json</code> templates. Use read-only cold probe task. Do not overwrite project-level canonical policy.</p></details><details><summary>PyCharm</summary><p>Project root; configure venv interpreter. Python script <code>worker_devkit.py</code>, arguments <code>--repo . --out .local-code-purple/receipt.json</code>; separate unittest run/debug configuration. Exclude credentials from shared settings.</p></details><details><summary>PowerShell 7 and Bash</summary><p>From repo root: <code>pwsh -NoProfile -File Cold-Probe.ps1 -RepoRoot .</code> or <code>bash cold_probe.sh .</code> using the relative <code>mission-control/federation-atlas/flightdeck/pulses/devkit</code> script directory.</p></details><details><summary>CLI / skills / schedules</summary><p>PATH detection of <code>codex</code>, <code>claude</code>, <code>gemini</code>, <code>aider</code>, <code>opencode</code>, <code>gh</code> does not grant authentication. <code>runner.toml</code> remains a local overlay and <code>SCHEDULE_TEMPLATE.json</code> defaults to manual-only. gg_MATH remains the canonical math provider.</p></details></section>
<section><h2>5. User-facing evidence views</h2><div class="links"><a href="../bd-char/index.html">BD/CHAR P2</a><a href="../pr-history/index.html">Merged-PR H1 chronology</a><a href="../atlas/index.html">Method Atlas</a><a href="https://github.com/GBOGEB/ABACUS/issues/1929">BD root register</a></div><p>Offline HTML can link to source-native PDFs, Word, Excel and PPTX if those are separately released. It does not assert such binaries were published by this PR.</p></section><section><h2>Source and qualification</h2><p>Observation SHA-256 <code>%s</code></p><p>Worker proposal SHA-256 <code>%s</code></p><p>Root accepted = UNKNOWN. Cached worker counts = UNKNOWN. Public Pages hosted hash = UNVERIFIED.</p></section></main><script>let input=document.getElementById('q');input.addEventListener('input',()=>{let q=input.value.toLowerCase();document.querySelectorAll('#tasks tbody tr').forEach(x=>x.hidden=!x.textContent.toLowerCase().includes(q))})</script></body></html>''' % (source_digest,len(obs['prs']),sum(x['success'] for x in obs['prs']),len(plan['tasks']),rows,prs,source_digest,plan_digest)


def build(plan_file,obs_file,out):
    plan_raw=Path(plan_file).read_bytes();obs_raw=Path(obs_file).read_bytes()
    plan=json.loads(plan_raw);obs=json.loads(obs_raw)
    validate(plan,obs)
    output=Path(out);output.mkdir(parents=True,exist_ok=True)
    (output/'index.html').write_text(page(plan,obs,hashlib.sha256(obs_raw).hexdigest(),hashlib.sha256(plan_raw).hexdigest()),encoding='utf-8')
    (output/'worker-plan.json').write_bytes(plan_raw)
    (output/'observed.json').write_bytes(obs_raw)
    result={'schema':'code-purple.worker-viewer.receipt.v1','source_sha256':hashlib.sha256(obs_raw).hexdigest(),
            'worker_plan_sha256':hashlib.sha256(plan_raw).hexdigest(),
            'artifacts':{n:hashlib.sha256((output/n).read_bytes()).hexdigest() for n in ('index.html','worker-plan.json','observed.json')},
            'merge_admission':'HOLD','authority_transfer':False,'native_worker_launch':None}
    (output/'manifest.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();base=Path(__file__).parent
    p.add_argument('--plan',type=Path,default=base/'worker_plan.json');p.add_argument('--observed',type=Path,default=base/'OBSERVED_P3_20261016.json');p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();print(json.dumps(build(a.plan,a.observed,a.out),sort_keys=True))
