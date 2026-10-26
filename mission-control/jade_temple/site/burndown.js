'use strict';
// Frozen, offline JADE_CASTE evidence projection. It never grants admission.
(function(){
const d=window.JADE_NPLUS2;
if(!d||d.schema!=='jade.temple.burndown_projection.v2'||d.merge_admission!=='HOLD'||d.authority_transfer!==false||d.security_waiver!==false)throw Error('JADE_N2_AUTHORITY');
const rows=d.rows;if(rows.length!==21||new Set(rows.map(r=>r.repo)).size!==21)throw Error('JADE_N2_POPULATION');
const by=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const gh=r=>`https://github.com/${r.repo.split('/').map(encodeURIComponent).join('/')}/tree/${r.current_head}`;
const safeGh=url=>typeof url==='string'&&/^https:\/\/github\.com\/GBOGEB\/[\w.-]+\/(issues\/\d+|actions\/runs\/\d+|pull\/\d+)$/.test(url)?url:null;
const cls=s=>s==='POSITIVE_OBSERVED_HISTORICAL'?'green':s==='HISTORICAL_RED_OBSERVED'?'red-text':'amber';
const label={POSITIVE_OBSERVED_HISTORICAL:'Historical positive',HISTORICAL_RED_OBSERVED:'Historical RED',COHORT_NOT_SAMPLED:'No sampled GoGREEN',NO_NATIVE_CHECK_EVIDENCE:'No native check sample'};
const metrics=d.metrics;
by('heads').textContent=`${metrics.heads_observed}/21`;
by('drift').textContent=`${metrics.heads_changed}/21`;
by('tasks').textContent=`${metrics.owner_actions_open} OPEN`;
by('roots').textContent=String(metrics.owner_causal_roots_qualified);
by('checkmix').textContent=`${metrics.main_check_runs.success} / ${metrics.main_check_runs.total}`;
by('hosted').textContent=metrics.hosted_jade_qualified===null?'UNKNOWN':'SEE HOSTED RECEIPT';
by('stop-action').textContent=d.controller.action;
by('stop-reason').textContent=d.controller.reason;
by('baseline-head').textContent=d.source_main_head;
by('gate-table').innerHTML=Object.entries(d.gates).map(([k,v])=>`<div class="gate"><span>${esc(k.replaceAll('_',' '))}</span><b class="${esc(v.toLowerCase())}">${esc(v)}</b></div>`).join('');
function selected(){const q=by('search').value.toLowerCase().trim(),p=by('priority').value,h=by('drift-only').value;return rows.filter(r=>(p==='ALL'||p===r.priority)&&(h==='ALL'||(h==='CHANGED'&&r.head_changed)||(h==='STABLE'&&!r.head_changed))&&[r.repo,r.technical_need,r.next_release_todo].join(' ').toLowerCase().includes(q));}
function render(){const s=selected();by('count').textContent=`${s.length}/21 repositories`;by('repos-tbody').innerHTML=s.map(r=>{
 const last=r.latest_two_branch_runs[0], latest=last?`${last.status}${last.conclusion?'/'+last.conclusion:''}`:'UNKNOWN (no recent run)';
 const recentClass=last?.conclusion==='failure'?'red-text':last?.conclusion==='success'?'green':'amber';
 return `<tr tabindex="0" role="button" data-repo="${esc(r.repo)}" aria-label="Inspect ${esc(r.repo)}"><td><a class="repo" href="${gh(r)}" target="_blank" rel="noopener noreferrer">${esc(r.repo.split('/')[1])} ↗</a><span class="sub">${esc(r.current_head.slice(0,11))} · ${esc(r.default_branch)}</span></td><td><span class="tag ${esc(r.priority.toLowerCase())}">${esc(r.priority)}</span></td><td class="${r.head_changed?'amber':'muted'}">${r.head_changed?'CHANGED':'Unchanged'}</td><td class="${cls(r.green_classification_20261017)}">${esc(label[r.green_classification_20261017]||'UNKNOWN')}</td><td class="${recentClass}">${esc(latest)}<span class="sub">${last?'#'+last.id:'No bounded run'}</span></td><td>${esc(r.technical_need)}</td></tr>`;}).join('')||'<tr><td colspan="6">No matching repositories</td></tr>';
 for(const tr of by('repos-tbody').querySelectorAll('tr[data-repo]')){
  const inspect=()=>{const row=rows.find(x=>x.repo===tr.dataset.repo);if(row)showDetails(row);by('repos-tbody').querySelectorAll('tr').forEach(x=>x.classList.toggle('selected',x===tr));};
  tr.addEventListener('click',e=>{if(!e.target.closest('a'))inspect();});tr.addEventListener('keydown',e=>{if((e.key==='Enter'||e.key===' ')&&!e.target.closest('a')){e.preventDefault();inspect();}});
 }
}
function showDetails(r){
 const runs=r.latest_two_branch_runs.map(z=>{const u=safeGh(z.url);return `<div><a href="${esc(u||'#')}" target="_blank" rel="noopener noreferrer">${esc(z.name)} ↗</a> · ${esc(z.status)}/${esc(z.conclusion||'UNKNOWN')} · attempt ${esc(z.attempt)}${z.head_matches_default?'':' · DIFFERS FROM CURRENT SOURCE'}</div>`;}).join('')||'<span class="amber">No bounded recent Actions sample; UNKNOWN, not zero</span>';
 const issues=(r.issue_links||[]).filter(safeGh).map(u=>`<a href="${esc(u)}" target="_blank" rel="noopener noreferrer">Issue #${esc(u.split('/').pop())} ↗</a>`).join('');
 by('details').innerHTML=`<div class="section-kicker">${esc(r.priority)} · OWNER ACTION NOT QUALIFIED</div><h3>${esc(r.repo)}</h3><div class="details-grid"><div><p><b>Next point-release TODO</b><br>${esc(r.next_release_todo)}</p><p><b>Current source</b><br><code>${esc(r.current_head)}</code><br>Historical head: <code>${esc(r.nplus1_sha)}</code><br>${r.head_changed?'HEAD DRIFT: inherited positive proof requires replay':'Unchanged head: native result still must be checked for freshness'}</p><p><b>Root review suggestions</b> ${esc(r.root_candidates_n11)} filename/path candidates, not verified defects</p></div><div><p><b>Recent Actions sample</b></p>${runs}<p><b>Qualified release gates</b><br><span class="amber">Owner J1/J2/J3/J4/J5: UNKNOWN / UNQUALIFIED</span></p><p><b>Historical GoGREEN classification</b><br>${esc(label[r.green_classification_20261017]||'UNKNOWN')}</p></div></div><div class="linklist"><a href="${gh(r)}" target="_blank" rel="noopener noreferrer">Exact source ↗</a><a href="https://github.com/${esc(r.repo)}/actions" target="_blank" rel="noopener noreferrer">Actions ↗</a><a href="https://github.com/${esc(r.repo)}/issues" target="_blank" rel="noopener noreferrer">Issues ↗</a>${issues}</div>`;
 by('details').focus({preventScroll:true});
}
for(const id of ['search','priority','drift-only'])by(id).addEventListener(id==='search'?'input':'change',render);
by('reset').addEventListener('click',()=>{by('search').value='';by('priority').value='ALL';by('drift-only').value='ALL';render();});
render();
})();
