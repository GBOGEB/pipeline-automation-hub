#!/usr/bin/env python3
"""MissionControl read-only federation flight deck: preflight, build, verify, refresh-heads.

SSOT: committed GOGREEN fleet_g1.json and controlled flightdeck_contract.json.
Built HTML, SVG, JSON, MD and Office outputs are projections, never authority.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import html
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request

SHA40 = re.compile(r"[0-9a-f]{40}\Z")
FAMILIES = ("ci_contract", "security", "coverage", "runtime", "artifact", "federation", "qps_triage", "math_model")
SCHEMA = "missioncontrol.federation-flightdeck.v1"
DEFAULT_ISSUE = "https://github.com/GBOGEB/pipeline-automation-hub/issues/529"


def encoded(data):
    return (json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def sha(data: bytes):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, obj):
    Path(path).write_bytes(encoded(obj))


def esc(s):
    return html.escape(str(s), quote=True)


def ssot_digest(paths):
    return sha(b"".join(Path(p).name.encode("utf-8") + b"\0" + sha(Path(p).read_bytes()).encode("ascii") + b"\n" for p in paths))


def validate(fleet, snap, contract):
    if fleet.get("schema") != "gogreen.fleet.intake.v1":
        raise ValueError("Unsupported GOGREEN fleet schema")
    if snap.get("schema") != "gogreen.anchor-readback.v1":
        raise ValueError("Invalid historical head snapshot schema")
    if contract.get("schema") != SCHEMA or contract.get("authority") != "SOURCE_CONTROLLED_INPUT; HUMAN_AND_REPOSITORY_GATES_SEPARATE":
        raise ValueError("Invalid document control or SSOT contract")
    repos = fleet.get("repositories")
    if not isinstance(repos, list) or len(repos) != 6:
        raise ValueError("Fixed G4 cohort must include exactly six repositories")
    names = [r.get("repository") for r in repos]
    if len(set(names)) != 6 or set(names) != set(x.get("name") for x in contract.get("repositories", [])):
        raise ValueError("Repository identities disagree across contracts")
    if set(contract.get("families", {})) != set(FAMILIES):
        raise ValueError("Evidence family taxonomy drift")
    cells = []
    for repo in repos:
        rname, src = repo.get("repository"), repo.get("head_sha")
        if not isinstance(src, str) or not SHA40.fullmatch(src):
            raise ValueError("Missing repository source anchor: " + str(rname))
        fs = repo.get("target_families", [])
        if not fs or len(fs) != len(set(fs)) or any(x not in FAMILIES for x in fs):
            raise ValueError("Invalid or duplicate family: " + rname)
        if repo.get("ref_kind") not in ("MAIN", "PR_HEAD"):
            raise ValueError("Unknown ref kind")
        cells.extend((rname, f) for f in fs)
    if len(cells) != 42 or len(cells) != len(set(cells)):
        raise ValueError("Cohort 42-cell denominator drift")
    observations = fleet.get("observations", [])
    observed = set()
    for o in observations:
        key = (o.get("repository"), o.get("family"))
        if key not in cells or key in observed:
            raise ValueError("Duplicate or off-catalog evidence observation")
        if o.get("workflow_conclusion") != "success" or o.get("job_conclusion") != "success":
            raise ValueError("G4 positive evidence must have terminal success")
        if type(o.get("run_id")) is not int or type(o.get("job_id")) is not int:
            raise ValueError("A native run and job identity are required")
        if o.get("source_sha") != next(r["head_sha"] for r in repos if r["repository"] == key[0]):
            raise ValueError("Observed evidence SHA mismatches source anchor")
        if o.get("artifact") and o["artifact"].get("bytes_verified") is True:
            raise ValueError("Cannot self-attest archive-byte verification")
        observed.add(key)
    if len(observed) < 6 or len(observed) > len(cells):
        raise ValueError("G4 minimum six observation anchors are required")
    main = [r for r in repos if r["ref_kind"] == "MAIN"]
    if len(main) != 5:
        raise ValueError("Historic PR anchor incorrectly included in current-main denominator")
    for item in main:
        rr = snap.get("branches", {}).get(item["repository"])
        if not rr or not SHA40.fullmatch(rr.get("sha", "")):
            raise ValueError("Snapshot missing branch SHA for " + item["repository"])
        if rr.get("branch") not in ("main", "master"):
            raise ValueError("Branch name invalid")
        if type(rr.get("protected")) is not bool:
            raise ValueError("Unknown branch-protection measurement")
    if not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", snap.get("observed_at_utc", "")):
        raise ValueError("Snapshot needs explicit capture time")
    if len(contract.get("pipeline", [])) != 8 or len(set(x["id"] for x in contract["pipeline"])) != 8:
        raise ValueError("Pipeline DAG step identity drift")
    if len(contract.get("controls", [])) != 8:
        raise ValueError("Safeguard registry drift")
    if contract.get("presentation", {}).get("corporate_approval") is not None or contract["presentation"].get("corporate_document_number") is not None:
        raise ValueError("Corporate authorization cannot be invented by renderer")
    return True


def build_census(fleet, snapshot, contract, source_digest, exact_git_sha=None):
    validate(fleet, snapshot, contract)
    if exact_git_sha is not None and not SHA40.fullmatch(exact_git_sha):
        raise ValueError("Exact Git checkout SHA must be 40 lowercase hex")
    evidence = {(x["repository"], x["family"]): x for x in fleet["observations"]}
    catalog = {x["name"]: x for x in contract["repositories"]}
    leaf = []
    for repo in fleet["repositories"]:
        name = repo["repository"]
        for family in repo["target_families"]:
            observation = evidence.get((name, family))
            fam = contract["families"][family]
            row = {
                "id": "G4-" + name.split("/")[-1].upper().replace("-", "_") + "-" + family.upper(),
                "repository": name, "repo_name": catalog[name]["short"],
                "family": family, "family_label": fam["label"],
                "source_sha": repo["head_sha"], "ref_kind": repo["ref_kind"],
                "status": "OBSERVED_STATUS_ONLY" if observation else "UNKNOWN_NOT_OBSERVED",
                "run_id": observation.get("run_id") if observation else None,
                "job_id": observation.get("job_id") if observation else None,
                "run_url": observation.get("run_url") if observation else None,
                "bytes_independently_verified": False,
                "root_id": None, "bd_disposition": "SCOUT_REQUIRED" if observation is None else "EVIDENCE_CONSUME_ONLY",
                "bd_authority": contract["source_control"]["primary_issue"],
                "owner_role": fam["owner"], "next_action": fam["next"], "victory_predicate": fam["proof"],
                "repo_url": "https://github.com/" + name,
                "code_url": "https://github.com/" + name + "/tree/" + repo["head_sha"],
            }
            leaf.append(row)
    assert len(leaf) == 42
    anchors = []
    for repo in fleet["repositories"]:
        if repo["ref_kind"] != "MAIN":
            continue
        x = snapshot["branches"][repo["repository"]]
        current = x["sha"]
        anchors.append({
            "repository": repo["repository"], "branch": x["branch"],
            "source_anchor": repo["head_sha"], "observed_main_sha": current,
            "status": "MATCHES_SNAPSHOT" if current == repo["head_sha"] else "STALE_ANCHOR",
            "protected_on_snapshot": x["protected"],
            "next_action": "Preserve prior G4 receipt; collect source-matched terminal run on observed main SHA" if current != repo["head_sha"] else "Keep provenance; refresh branch head at next wave",
            "observed_main_url": f"https://github.com/{repo['repository']}/commit/{current}",
            "source_anchor_url": f"https://github.com/{repo['repository']}/commit/{repo['head_sha']}",
            "repo_branch_url": f"https://github.com/{repo['repository']}/tree/{x['branch']}",
            "bd_authority": DEFAULT_ISSUE,
        })
    metrics = {
        "catalog_repositories": 6, "families_possible": 8,
        "eligible_cells": len(leaf), "observed_cells": len(evidence),
        "unobserved_cells": len(leaf) - len(evidence), "verified_archive_cells": 0,
        "source_main_anchors": 5,
        "main_anchor_matches": sum(a["status"] == "MATCHES_SNAPSHOT" for a in anchors),
        "stale_main_anchors": sum(a["status"] == "STALE_ANCHOR" for a in anchors),
        "leaf_bds_planned": len(leaf)-len(evidence), "verified_roots_closed": None,
        "cross_repo_native_chain": None, "qps_owner_disposition": "DEFER",
        "pca_m2_m3_eligible": False,
        "unit":"repo-family cell; not code coverage and not independent root"
    }
    return {
        "schema":"missioncontrol.flightdeck.census.v1", "version":contract["version"],
        "source_semantic_sha256":source_digest, "exact_checkout_sha":exact_git_sha,
        "snapshot_observed_at_utc": snapshot["observed_at_utc"],
        "snapshot_is_live":False, "status":"READ_ONLY_PROJECTION",
        "authority_transfer":False,"merge_authorized":False,"engineering_accepted":False,
        "metrics":metrics,"cells":leaf,"anchors":anchors,
        "repositories":contract["repositories"],"pipeline":contract["pipeline"],
        "controls":contract["controls"],"waves":contract["wave_definitions"],
        "corporate_doc_control": contract["presentation"],
        "reference_paths":contract["source_control"],
    }


def flow_svg(data):
    stages = data["pipeline"]
    width, height = 1460, 450
    q = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="ftitle fdesc">',
         '<title id="ftitle">MissionControl source-to-release flow</title><desc id="fdesc">Eight guarded steps from owner inputs to preflight, census, REX/LDAB, UI, documents, QA and release; feedback is next-wave only.</desc>',
         f'<metadata id="source-semantic-sha256">{esc(data["source_semantic_sha256"])}</metadata>',
         '<defs><marker id="a" viewBox="0 0 12 12" refX="10" refY="6" markerWidth="7" markerHeight="7" orient="auto"><path d="M 1 1 L 11 6 L 1 11" stroke="#74d7e8" stroke-width="2" fill="none"/></marker></defs>',
         '<rect width="100%" height="100%" rx="18" fill="#0b1727"/>']
    for i, step in enumerate(stages):
        col, row = i % 4, i // 4
        x = 32 + col * 358
        y = 48 + row * 185
        label, name = step["group"], step["name"]
        q.append(f'<a href="#step-{esc(step["id"])}"><rect x="{x}" y="{y}" width="318" height="123" rx="13" fill="#172841" stroke="#3b5169"/><text x="{x+19}" y="{y+26}" font-size="14" font-weight="700" fill="#74d7e8">{esc(step["id"])} · {esc(label)}</text><text x="{x+19}" y="{y+56}" font-size="19" font-weight="600" fill="#ecf3fb">{esc(name[:31])}</text><text x="{x+19}" y="{y+84}" font-size="13" fill="#b9cadd">{esc(step["outputs"][:45])}</text><text x="{x+19}" y="{y+103}" font-size="12" fill="#a8bbce">Open step →</text></a>')
        if col < 3:
            q.append(f'<path d="M{x+320},{y+63} H{x+355}" stroke="#74d7e8" stroke-width="2" fill="none" marker-end="url(#a)"/>')
    q.append('<path d="M1370 178 V219 H192 V233" fill="none" stroke="#a991e8" stroke-width="2" marker-end="url(#a)"/>')
    q.append('<text x="26" y="429" font-size="14" fill="#b4c6dc">CONTROL and recensus feed the next measured pulse. Lines do not imply cross-repository dispatch.</text>')
    q.append('</svg>')
    return ''.join(q) + '\n'


def percent(n, d):
    return f"{n*100/d:.1f}%" if d else "UNKNOWN"


def site_html(data):
    m = data["metrics"]
    repo_cards = []
    for r in data["repositories"]:
        name = r["name"]
        n = sum(c["repository"] == name for c in data["cells"])
        observed = sum(c["repository"] == name and c["status"] == "OBSERVED_STATUS_ONLY" for c in data["cells"])
        repo_cards.append(f'''<article class="repo-card"><div class="repo-head"><span class="repo-symbol" aria-hidden="true">{esc(r["short"][:2].upper())}</span><span class="mini">{observed}/{n} observed</span></div><h3>{esc(r["short"])}</h3><p>{esc(r["role"])}</p><dl><dt>Input</dt><dd>{esc(r["inputs"])}</dd><dt>Output</dt><dd>{esc(r["outputs"])}</dd><dt>Guardrail</dt><dd>{esc(r["boundaries"])}</dd></dl><a href="https://github.com/{esc(name)}" target="_blank" rel="noopener">Source repository ↗</a></article>''')
    rows = []
    for c in data["cells"]:
        obs=c["status"] == "OBSERVED_STATUS_ONLY"
        cls="pass" if obs else "unknown"
        detail = f'''<details><summary>Evidence and next action</summary><div class="leaf"><p><strong>BD leaf:</strong> <code>{esc(c["id"])}</code> · root ID not yet assigned</p><p><strong>Next:</strong> {esc(c["next_action"])}</p><p><strong>Definition of verification:</strong> {esc(c["victory_predicate"])}</p><p><strong>Historical SHA:</strong> <code>{esc(c["source_sha"])}</code></p><p><strong>Owner:</strong> {esc(c["owner_role"])}</p><p><a href="{esc(c["code_url"])}" target="_blank" rel="noopener">Pinned code ↗</a> · <a href="{esc(c["bd_authority"])}" target="_blank" rel="noopener">G4 work register ↗</a>{' · <a href="' + esc(c["run_url"]) + '" target="_blank" rel="noopener">Native run ↗</a>' if c["run_url"] else ''}</p></div></details>'''
        rows.append(f'<tr data-repo="{esc(c["repository"])}" data-family="{esc(c["family"])}" data-status="{esc(c["status"])}" data-search="{esc((c["repository"]+" "+c["family"]+" "+c["id"]+" "+c["next_action"]).lower())}"><td><code>{esc(c["id"])}</code></td><td>{esc(c["repo_name"])}</td><td>{esc(c["family_label"])}</td><td><span class="chip {cls}">{'OBSERVED / METADATA' if obs else 'UNKNOWN · SCOUT'}</span></td><td>{detail}</td></tr>')
    anchors=[]
    for a in data["anchors"]:
        status = 'ok' if a["status"] == "MATCHES_SNAPSHOT" else 'stale'
        anchors.append(f'<tr><td><strong>{esc(a["repository"].split("/")[-1])}</strong><div class="mini">{esc(a["branch"])}</div></td><td><code>{esc(a["source_anchor"][:12])}</code></td><td><a href="{esc(a["observed_main_url"])}" target="_blank" rel="noopener"><code>{esc(a["observed_main_sha"][:12])}</code> ↗</a></td><td><span class="chip {status}">{"MATCHED AT SNAPSHOT" if status=="ok" else "REFRESH REQUIRED"}</span></td><td>{esc(a["next_action"])} · <a href="{esc(a["repo_branch_url"])}" target="_blank" rel="noopener">Branch ↗</a></td></tr>')
    steps=[]
    for p in data["pipeline"]:
        steps.append(f'''<article class="step" id="step-{esc(p["id"])}"><div class="step-top"><strong>{esc(p["id"])} · {esc(p["name"])}</strong><span class="mini">{esc(p["group"])}</span></div><p><b>Trigger:</b> {esc(p["trigger"])}</p><p><b>User / machine input:</b> {esc(p["inputs"])}</p><p class="command"><code>{esc(p["command"])}</code></p><p><b>Emits:</b> {esc(p["outputs"])}</p><p><b>DMAIC stop:</b> {esc(p["gate"])}</p></article>''')
    ctrls=''.join(f'<tr><td><code>{esc(x["id"])}</code></td><td><strong>{esc(x["name"])}</strong></td><td>{esc(x["threshold"])}</td><td>{esc(x["response"])}</td></tr>' for x in data["controls"])
    waves=''.join(f'<article class="wave"><span class="wave-id">{esc(w["wave"])}</span><h3>{esc(w["name"])}</h3><p>{esc(w["victory"])}</p><span class="mini">{esc(w["state"])}</span></article>' for w in data["waves"])
    css='''
:root{color-scheme:dark;--bg:#091321;--panel:#14243a;--surface:#172b44;--line:#324860;--fg:#edf4fb;--muted:#b2c2d3;--cyan:#75d9e8;--violet:#b49af2;--orange:#edbc83;--good:#86e0b2}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.6 Inter,Segoe UI,Arial,sans-serif}a{color:#8fe6f0;text-underline-offset:3px}a:hover{color:#fff}button,input,select,textarea{font:inherit}button{cursor:pointer}.wrap{width:min(1320px,calc(100% - 42px));margin:auto}header{background:linear-gradient(130deg,#0c1d33,#172340 60%,#271d3a);border-bottom:1px solid #354d6c}nav{display:flex;justify-content:space-between;gap:16px;align-items:center;padding:18px 0;flex-wrap:wrap}.mark{display:flex;align-items:center;gap:12px;font-weight:750;letter-spacing:.12em;font-size:14px}.mark i{display:inline-block;width:30px;height:30px;border:3px solid var(--cyan);border-left-color:var(--violet);border-radius:8px;transform:rotate(-13deg)}.navlinks{display:flex;flex-wrap:wrap;gap:15px;font-size:13px}.navlinks a{color:#d5e4f2;text-decoration:none}.hero{padding:60px 0 45px;display:grid;grid-template-columns:1.25fr .75fr;gap:28px;align-items:center}.eyebrow{text-transform:uppercase;letter-spacing:.23em;color:var(--cyan);font-weight:750;font-size:12px}.hero h1{font-size:clamp(40px,5vw,76px);letter-spacing:-.048em;line-height:1.06;margin:14px 0}.hero h1 em{font-style:normal;color:var(--cyan)}.lead{font-size:18px;max-width:690px;color:#c2d3e1}.hero-actions{display:flex;gap:12px;flex-wrap:wrap;margin-top:26px}.cta{display:inline-block;text-decoration:none;background:var(--cyan);color:#091726;padding:12px 17px;border-radius:8px;font-weight:750}.cta.secondary{background:#263651;color:#eff7fd;border:1px solid #51718b}.hero-side{background:#13243bbd;border:1px solid #3c5571;border-radius:17px;padding:24px}.stacked{display:grid;gap:11px}.audit-line{display:flex;justify-content:space-between;border-bottom:1px solid #364b61;padding-bottom:11px;font-size:13px}.audit-line strong{color:var(--cyan)}.section{padding:46px 0 5px}.section h2{font-size:clamp(26px,3vw,38px);letter-spacing:-.03em;line-height:1.15;margin:0 0 12px}.sub{color:var(--muted);max-width:860px;margin:0 0 25px}.metric-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:28px}.metric{display:block;border:1px solid #3a526e;background:#17263e;padding:21px 22px;border-radius:13px;text-decoration:none;color:inherit}.metric:hover{background:#203752;border-color:var(--cyan)}.metric .n{display:block;font-weight:760;font-size:38px;line-height:1.22;margin:8px 0}.metric p{color:var(--muted);font-size:12px;margin:0}.mini{font-size:12px;color:#bed0df}.kicker{font-size:12px;color:var(--muted)}.track{height:12px;background:#334761;border-radius:99px;overflow:hidden;margin:18px 0}.fill{height:100%;background:linear-gradient(90deg,#5ad9e6,#bba0fb)}.repo-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:15px}.repo-card{border:1px solid #334b67;background:var(--panel);padding:21px;border-radius:14px;display:flex;flex-direction:column}.repo-card h3{margin:15px 0 5px;font-size:20px}.repo-card p{color:#c7d6e3;margin:0 0 15px}.repo-card dl{display:grid;grid-template-columns:62px 1fr;gap:7px 11px;font-size:12px;margin:5px 0 15px}.repo-card dt{color:#8facbe;text-transform:uppercase;letter-spacing:.04em}.repo-card dd{margin:0}.repo-card a{margin-top:auto;font-size:13px}.repo-head{display:flex;justify-content:space-between;align-items:center}.repo-symbol{border:1px solid #7388ac;background:#243855;color:var(--cyan);border-radius:9px;padding:8px 11px;font-size:14px;font-weight:800}.pane{border:1px solid #364f6b;background:var(--panel);border-radius:13px;padding:22px;margin:17px 0}.filterbar{display:flex;gap:12px;flex-wrap:wrap;margin:15px 0 22px}.filterbar input{flex:2 1 260px}.filterbar select{flex:1 1 170px}.filterbar input,.filterbar select,.review-input{background:#0f1d30;border:1px solid #4b637e;color:#eff4ff;border-radius:7px;padding:10px 12px}.table-scroll{overflow-x:auto}table{width:100%;border-collapse:collapse;min-width:720px}th{text-align:left;color:#98ddea;font-size:11px;text-transform:uppercase;letter-spacing:.06em;padding:12px;border-bottom:2px solid #44617b}td{vertical-align:top;padding:12px;font-size:13px;border-bottom:1px solid #2e435b}td code,code{font-family:Cascadia Code,Consolas,monospace;font-size:12px;overflow-wrap:anywhere}details summary{cursor:pointer;color:#9ce7f1;font-weight:600}.leaf{border-left:2px solid #8368bb;margin:10px 0;padding:4px 0 4px 14px;max-width:470px}.leaf p{margin:6px 0;color:#cfdeeb}.chip{display:inline-block;border-radius:999px;padding:4px 10px;background:#2c3b51;color:#d7e7f4;font-size:11px;font-weight:750;white-space:nowrap}.chip.pass,.chip.ok{background:#1c403e;color:#8df0cf}.chip.unknown{background:#493b28;color:#ffd9a1}.chip.stale{background:#513141;color:#ffbad0}.statrow{display:flex;justify-content:space-between;gap:15px;flex-wrap:wrap;font-size:13px;color:var(--muted)}.diagram{overflow-x:auto;border-radius:13px}.diagram svg{max-width:100%;min-width:900px;height:auto}.step-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.step{border:1px solid #38536d;background:#142439;border-radius:12px;padding:21px;scroll-margin-top:20px}.step-top{display:flex;justify-content:space-between;gap:10px}.step p{font-size:13px;color:#cbd9e6}.command{background:#091829;border-left:3px solid #6cc5d5;padding:10px;overflow-wrap:anywhere}.wave-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.wave{background:#192c46;border:1px solid #3b5171;border-radius:12px;padding:20px}.wave-id{font-size:12px;color:#7fe0ef;font-weight:800}.wave h3{margin:10px 0}.wave p{min-height:82px;color:#bdd1df;font-size:13px}.foot{border-top:1px solid #3f5370;color:#b7c8d8;font-size:12px;padding:30px 0 50px;margin-top:55px}.note{border-left:3px solid var(--violet);padding:10px 15px;background:#1b273d;color:#d1dceb}.review-controls{display:flex;gap:12px;align-items:center;flex-wrap:wrap}.review-input{width:min(650px,100%)}.review-note{font-size:12px;color:#a6bccb}.statusline{color:#8de0bd;font-size:13px}#rowcount{font-weight:800;color:var(--cyan)}
@media(max-width:980px){.hero{grid-template-columns:1fr}.metric-grid{grid-template-columns:repeat(2,1fr)}.repo-grid{grid-template-columns:repeat(2,1fr)}.step-grid{grid-template-columns:1fr}}
@media(max-width:640px){.wrap{width:calc(100% - 25px)}.hero{padding-top:38px}.metric-grid{grid-template-columns:1fr 1fr;gap:9px}.metric{padding:15px}.metric .n{font-size:30px}.repo-grid,.wave-grid{grid-template-columns:1fr}.section{padding-top:33px}.hero h1{font-size:41px}.filterbar{gap:7px}.navlinks{gap:9px}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}@media print{body{background:white;color:black}.navlinks,.filterbar,.review-controls{display:none}.pane,.repo-card,.metric{background:white;color:black;border:1px solid #999}a{color:#000}details{display:block}}
'''
    js='''
(function(){const trs=[...document.querySelectorAll('#evidence-table tbody tr')],q=document.getElementById('find'),repo=document.getElementById('repoFilter'),family=document.getElementById('familyFilter'),state=document.getElementById('stateFilter');function refresh(){const needle=q.value.trim().toLowerCase();let count=0;for(const tr of trs){const show=(!needle||tr.dataset.search.includes(needle))&&(!repo.value||tr.dataset.repo===repo.value)&&(!family.value||tr.dataset.family===family.value)&&(!state.value||tr.dataset.status===state.value);tr.hidden=!show;if(show)count++}document.getElementById('rowcount').textContent=count+' / '+trs.length;}for(const x of [q,repo,family,state])x.addEventListener('input',refresh);document.getElementById('missingOnly').addEventListener('click',()=>{state.value='UNKNOWN_NOT_OBSERVED';document.getElementById('evidence-register').scrollIntoView();refresh()});document.getElementById('clearFilters').addEventListener('click',()=>{q.value='';repo.value='';family.value='';state.value='';refresh()});document.getElementById('exportReview').addEventListener('click',()=>{const selected=trs.filter(tr=>!tr.hidden).map(tr=>tr.querySelector('td code').textContent);const payload={schema:'missioncontrol.flightdeck.user-review.v1',source_semantic_sha256:document.body.dataset.source,selected_bd_leaves:selected,notes:document.getElementById('reviewNotes').value,disposition:'LOCAL_USER_NOTES_ONLY_NOT_SAVED_TO_GITHUB',created_at_local:new Date().toISOString()};const blob=new Blob([JSON.stringify(payload,null,2)+'\\n'],{type:'application/json'}),url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='flightdeck_review_notes.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)});for(const box of document.querySelectorAll('details'))box.addEventListener('toggle',()=>{});refresh();})();
'''
    opts_repo = '<option value="">All repositories</option>' + ''.join(f'<option value="{esc(r["name"])}">{esc(r["short"])}</option>' for r in data["repositories"])
    opts_family = '<option value="">All evidence families</option>'+''.join(f'<option value="{esc(c["family"])}">{esc(c["family_label"])}</option>' for c in data["cells"] if c["repository"]==data["repositories"][0]["name"])
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Read-only source-traceable MissionControl federation evidence explorer"><title>Mission Control — Federation Flight Deck · W1/W2</title><style>{css}</style></head><body data-source="{esc(data["source_semantic_sha256"])}">
<header><div class="wrap"><nav><div class="mark"><i aria-hidden="true"></i><span>PURPLE / MISSION CONTROL</span></div><div class="navlinks"><a href="#mission">Mission</a><a href="#portfolio">Repositories</a><a href="#evidence-register">42-cell census</a><a href="#head-register">Main anchors</a><a href="#pipeline">Python pipeline</a><a href="#controls">DMAIC controls</a><a href="#documents">Outputs</a></div></nav><div class="hero" id="mission"><div><div class="eyebrow">CODE PURPLE · W1 + W2 · governed preview</div><h1>Engineering intelligence.<br><em>Traceable by design.</em></h1><p class="lead">One source-controlled spine for six collaborating repositories, actionable evidence gaps, executable Python, human-friendly review, and controlled output artifacts. We make the invisible engineering work inspectable—without inventing approval.</p><div class="hero-actions"><a class="cta" href="#evidence-register">Explore {m['unobserved_cells']} missing leaves ↘</a><a class="cta secondary" href="#pipeline">See executable code ↗</a></div></div><aside class="hero-side"><div class="eyebrow">Flight status / factual boundaries</div><h2 style="font-size:25px;margin:12px 0">READY TO REVIEW.<br>NOT READY TO ADMIT.</h2><div class="stacked"><div class="audit-line"><span>G4 scope</span><strong>6 repositories · 42 cells</strong></div><div class="audit-line"><span>Native byte proofs in original G4</span><strong>0 recorded</strong></div><div class="audit-line"><span>Engineering QPS acceptance</span><strong>DEFER</strong></div><div class="audit-line"><span>Cross-repo authentication</span><strong>UNKNOWN</strong></div><div class="audit-line"><span>Publisher / GitHub Pages</span><strong>NOT CONFIRMED</strong></div><div class="mini">Source snapshot: {esc(data["snapshot_observed_at_utc"])} UTC · not a live API feed</div></div></aside></div></div></header>
<main class="wrap"><section class="section" id="scorecard"><div class="eyebrow">01 / Measured scope</div><h2>From headline numbers to accountable details.</h2><p class="sub">Cells, coverage and root closure use distinct denominators. The evidence table is the direct continuation of these counters; no metric hides its missing leaves.</p><div class="metric-grid"><a class="metric" href="#evidence-register"><span class="kicker">G4 observed cells</span><span class="n">{m["observed_cells"]} <span style="font-size:23px;color:#a7b8cb">/ {m["eligible_cells"]}</span></span><p>Native run/job metadata only. Inspect all 42 leaves →</p></a><a class="metric" href="#evidence-register"><span class="kicker">BD scout candidates</span><span class="n">{m["unobserved_cells"]}</span><p>UNKNOWN, not 36 broken systems. Open next action →</p></a><a class="metric" href="#head-register"><span class="kicker">Historical main anchors</span><span class="n">{m["main_anchor_matches"]} <span style="font-size:23px;color:#a7b8cb">/ {m["source_main_anchors"]}</span></span><p>{m["stale_main_anchors"]} need source-matched refresh. Open five anchors →</p></a><a class="metric" href="#documents"><span class="kicker">Generated project outputs</span><span class="n">8+</span><p>JSON / HTML / SVG / Markdown / XLSX / DOCX / PPTX / linked PDF →</p></a></div><div class="track" role="img" aria-label="{percent(m["observed_cells"],42)} G4 observation breadth"><div class="fill" style="width:{percent(m["observed_cells"],42)}"></div></div><div class="statrow"><span>Observed {percent(m["observed_cells"],42)}</span><span>Unobserved {percent(m["unobserved_cells"],42)} · no independent byte-credit in original G4</span></div></section>
<section class="section" id="portfolio"><div class="eyebrow">02 / Who we are</div><h2>Six specialist repositories. One visible mission.</h2><p class="sub">Each repository has an explicit role, input/output boundary, test purpose and next consumer. These are source-derived project role descriptions, not external certification.</p><div class="repo-grid">{''.join(repo_cards)}</div></section>
<section class="section" id="evidence-register"><div class="eyebrow">03 / Source-bound backlog</div><h2>42 inspectable evidence leaves.</h2><p class="sub">{m["observed_cells"]} terminal metadata observations, {m["unobserved_cells"]} targeted scout packets. No new GitHub issues are created: every leaf links to the existing <a href="{DEFAULT_ISSUE}" target="_blank" rel="noopener">GOGREEN #529 work register</a> for owner classification and root mapping.</p><div class="filterbar"><label><span class="mini">Text / BD ID</span><br><input id="find" type="search" placeholder="Search repo, family, action…" aria-label="Search evidence leaves"></label><label><span class="mini">Repository</span><br><select id="repoFilter" aria-label="Filter repository">{opts_repo}</select></label><label><span class="mini">Family</span><br><select id="familyFilter" aria-label="Filter evidence family">{opts_family}</select></label><label><span class="mini">State</span><br><select id="stateFilter" aria-label="Filter status"><option value="">All states</option><option value="UNKNOWN_NOT_OBSERVED">UNKNOWN</option><option value="OBSERVED_STATUS_ONLY">OBSERVED</option></select></label></div><div class="review-controls"><button id="missingOnly" class="cta secondary" type="button">Show {m["unobserved_cells"]} missing</button><button id="clearFilters" class="cta secondary" type="button">Reset filters</button><span class="mini">Showing <span id="rowcount">42 / 42</span></span></div><div class="table-scroll"><table id="evidence-table"><thead><tr><th>Typed work leaf</th><th>Repo</th><th>Proof family</th><th>Observed state</th><th>Evidence / BD / victory</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div></section>
<section class="section" id="head-register"><div class="eyebrow">04 / No stale-head adoption</div><h2>Five historical main anchors.</h2><p class="sub">This is a snapshot comparison, not a live HEAD API view. ABACUS's source is a PR-head row and intentionally excluded from this denominator. A red anchor here is stale for *comparison*, not an allegation of a failing current main.</p><div class="table-scroll"><table><thead><tr><th>Repository</th><th>G4 anchor</th><th>Observed main</th><th>Condition</th><th>Next exact-source step</th></tr></thead><tbody>{''.join(anchors)}</tbody></table></div><p class="note">Refresh via <code>python flightdeck.py refresh-heads --fleet ... --snapshot ...</code>, then regenerate all projections and retain both old/new snapshot hashes.</p></section>
<section class="section" id="pipeline"><div class="eyebrow">05 / What Python actually does</div><h2>One CLI. Eight controlled stages.</h2><p class="sub">Python reads source-control JSON, validates IDs and denominators, derives the 42 typed leaves, renders views, exports optional binaries and computes release hashes. Its stdout is a command receipt—not an engineering acceptance.</p><div class="diagram">{flow_svg(data)}</div><div class="step-grid">{''.join(steps)}</div></section>
<section class="section" id="controls"><div class="eyebrow">06 / DMAIC & safeguards</div><h2>Fail closed where it matters.</h2><p class="sub">Higher thresholds must apply to *matching* populations. Local unit checks and generated-file integrity cannot replace exact-head review, verified security, native cross-repo consumption or engineering acceptance.</p><div class="table-scroll"><table><thead><tr><th>ID</th><th>Control</th><th>Target / rule</th><th>Response to failure</th></tr></thead><tbody>{ctrls}</tbody></table></div><div class="wave-grid" style="margin-top:23px">{waves}</div></section>
<section class="section" id="documents"><div class="eyebrow">07 / Documents & user I/O</div><h2>Knowledge outputs that can be inspected.</h2><p class="sub">The same SSOT-derived census drives the HTML, SVG, read-only data, printable evidence book and editable Office derivatives. The interactive HTML is the operational interface; the linked PDF supports navigational and external clickable references, not dynamic application logic.</p><div class="pane"><div class="table-scroll"><table><thead><tr><th>Artifact</th><th>What users gain</th><th>Authority</th></tr></thead><tbody>
<tr><td><a href="index.html">HTML</a></td><td>Search/filter, drill down to each BD leaf, local note export</td><td>Generated review projection</td></tr>
<tr><td><a href="flightdeck.svg">SVG</a></td><td>Editable/vector system flow for reuse in slides or docs</td><td>Derived diagram</td></tr>
<tr><td><a href="census.json">JSON / SSOT export</a></td><td>Machine-readable 42-cell register, five anchors, evidence SHA</td><td>Derived from controlled inputs</td></tr>
<tr><td><a href="GUIDE.md">Markdown</a></td><td>Operator sequence, command/outputs, references</td><td>Controlled explanatory documentation</td></tr>
<tr><td><a href="evidence_register.xlsx">XLSX ↗</a></td><td>Filtered cell/anchor register and document-control sheet</td><td>Generated; approval left blank</td></tr>
<tr><td><a href="federation_report.docx">DOCX ↗</a></td><td>Printable review report; corporate doc-control placeholders</td><td>Generated, not approved</td></tr>
<tr><td><a href="mission_brief.pptx">PPTX ↗</a></td><td>Portfolio/leadership presentation</td><td>Generated briefing, not adopted policy</td></tr>
<tr><td><a href="linked_evidence_book.pdf">Linked PDF ↗</a></td><td>Readable evidence book with internal and source hyperlinks</td><td>Snapshot of release, not interactive database</td></tr></tbody></table></div></div><h3>User review notes (local only)</h3><p class="sub">Type observations, filter the table above, then export a JSON review packet. Nothing is posted to GitHub, stored as authoritative source or sent to an external endpoint.</p><div class="review-controls"><textarea class="review-input" id="reviewNotes" rows="3" aria-label="Local reviewer observations" placeholder="Reviewer observations, candidate BD ownership, document-control references…"></textarea><button class="cta" type="button" id="exportReview">Export selected rows + notes</button></div><p class="review-note">Corporate references such as ALX or SCK CEN document-control numbers must be supplied by their document owners. None are invented or assigned here.</p></section></main>
<footer class="foot"><div class="wrap"><strong>MISSION CONTROL • CODE PURPLE</strong><p>Source semantic SHA-256 <code>{esc(data["source_semantic_sha256"])}</code> · historical GitHub snapshot {esc(data["snapshot_observed_at_utc"])} UTC · exact checkout <code>{esc(data["exact_checkout_sha"] or "LOCAL_UNBOUND")}</code>.</p><p>No hosted Pages deployment, authorized merge, independent signed attestation, corporate approval or QPS engineering ACCEPT is inferred from this generated view. Wave 3 publication is a separate owner gate.</p></div></footer><script>{js}</script></body></html>'''


def operator_guide(data):
    m=data["metrics"]
    txt=["# Mission Control — Federation Flight Deck / operator guide", "", "**W1/W2 generated read-only projection.** Corporate approval, QPS acceptance and GitHub Pages publication are independent gates.", "", f"Source semantic SHA-256: `{data['source_semantic_sha256']}`", f"Historical head snapshot: `{data['snapshot_observed_at_utc']}` UTC", "", "## What runs, and what Python outputs", ""]
    for p in data["pipeline"]:
        txt.extend([f"### {p['id']} — {p['name']}",f"- **Trigger:** {p['trigger']}",f"- **Inputs:** {p['inputs']}",f"- **Command:** `{p['command']}`",f"- **Outputs:** {p['outputs']}",f"- **Stop:** {p['gate']}",""])
    txt.extend(["## Observed breadth and backlog", "", f"- Observed native metadata cells: **{m['observed_cells']}/{m['eligible_cells']}**", f"- Missing observation work leaves: **{m['unobserved_cells']}**, not proven failures", f"- Snapshot-matching historical main anchors: **{m['main_anchor_matches']}/{m['source_main_anchors']}**, stale = {m['stale_main_anchors']}", "- No verified archive bytes counted in the original G4 catalog; root closure is UNKNOWN.", "", "## Supporting docs", "", "- `README.md`: local and CI quickstart", "- `RUNBOOK.md`: operator flight sequence", "- `DOC_CONTROL.md`: ALX/SCK CEN document-control boundary", "- `census.json`: machine-generated full leaf registry", "- `manifest.json`: generated file hashes", "", "## Canonical sources", "", "- https://github.com/GBOGEB/pipeline-automation-hub/tree/master/mission-control/gogreen", "- https://github.com/GBOGEB/pipeline-automation-hub/tree/master/mission-control/federation-atlas", "- https://github.com/GBOGEB/pipeline-automation-hub/issues/529", "- https://github.com/GBOGEB/pipeline-automation-hub/pull/536", "", "## Authority", "", "No HTML/SVG/PDF/Office file is the engineering source of truth. An accepted review change must return to source-controlled JSON or the official corporate document-control system, then regenerate outward.", ""])
    return "\n".join(txt)


def seal(out):
    out=Path(out)
    if not (out/'census.json').is_file():
        raise ValueError("Missing census for seal")
    content={}
    for p in sorted(out.iterdir()):
        if p.is_file() and p.name not in ("manifest.json", "qa_receipt.json"):
            content[p.name]={"sha256":sha(p.read_bytes()),"bytes":p.stat().st_size}
    c=read(out/'census.json')
    manifest={"schema":"missioncontrol.flightdeck.manifest.v1","source_semantic_sha256":c["source_semantic_sha256"],"exact_checkout_sha":c.get("exact_checkout_sha"),"content":content,"authority_transfer":False,"merge_authorized":False}
    write_json(out/'manifest.json',manifest)
    return manifest


def verify(out):
    out=Path(out)
    manifest=read(out/'manifest.json')
    census=read(out/'census.json')
    if manifest["source_semantic_sha256"]!=census["source_semantic_sha256"]:
        raise ValueError("Manifest source identity mismatch")
    if len(census["cells"]) !=42 or len(set(x["id"] for x in census["cells"])) !=42:
        raise ValueError("BD leaf cardinality/uniqueness failure")
    if sum(x["status"]=="UNKNOWN_NOT_OBSERVED" for x in census["cells"])!=census["metrics"]["unobserved_cells"] or census["metrics"]["observed_cells"] + census["metrics"]["unobserved_cells"] != 42:
        raise ValueError("Missing evidence count mismatch")
    if len(census["anchors"])!=5 or sum(x["status"]=="STALE_ANCHOR" for x in census["anchors"])!=census["metrics"]["stale_main_anchors"]:
        raise ValueError("Historical anchor snapshot parity drift")
    assert census["merge_authorized"] is False
    assert census["engineering_accepted"] is False
    for name,entry in manifest["content"].items():
        p=out/name
        if not p.is_file() or sha(p.read_bytes())!=entry["sha256"] or p.stat().st_size!=entry["bytes"]:
            raise ValueError("Artifact hash mismatch: " + name)
    if f"{census['metrics']['observed_cells']} <span" not in (out/'index.html').read_text(encoding="utf-8"):
        raise ValueError("HTML observation card missing")
    return {"status":"PASS","validated_files":len(manifest["content"]),"cells":42,"unknown":census["metrics"]["unobserved_cells"],"anchors":5,"stale":census["metrics"]["stale_main_anchors"],"source_sha256":census["source_semantic_sha256"]}


def build(args):
    paths=[Path(args.fleet),Path(args.snapshot),Path(args.contract)]
    if not all(x.is_file() for x in paths):
        raise ValueError("One or more SSOT inputs are missing")
    fleet,snap,contract=map(read,paths)
    source=ssot_digest(paths)
    data=build_census(fleet,snap,contract,source,args.exact_git_sha)
    out=Path(args.out)
    out.mkdir(parents=True,exist_ok=True)
    write_json(out/'census.json',data)
    (out/'index.html').write_text(site_html(data),encoding="utf-8")
    (out/'flightdeck.svg').write_text(flow_svg(data),encoding="utf-8")
    (out/'GUIDE.md').write_text(operator_guide(data),encoding="utf-8")
    write_json(out/'bd_leaves.json',{"schema":"missioncontrol.flightdeck.bd-scout.v1","source_semantic_sha256":source,"root_ids_assigned":0,"leaves":[c for c in data["cells"] if c["status"]=="UNKNOWN_NOT_OBSERVED"]})
    write_json(out/'anchors.json',{"schema":"missioncontrol.flightdeck.anchors.v1","source_semantic_sha256":source,"snapshot_observed_at_utc":data["snapshot_observed_at_utc"],"anchors":data["anchors"]})
    seal(out)
    return verify(out)


def refresh_heads(args):
    fleet=read(args.fleet)
    existing=read(args.snapshot)
    new=dict(existing)
    new["branches"]=dict(existing["branches"])
    new["observed_at_utc"]=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z")
    new["basis"]="Read-only GitHub /branches API observed now; frozen response, not a continuous feed"
    for repo in fleet["repositories"]:
        name=repo["repository"]
        if repo["ref_kind"]!="MAIN":continue
        branch=(existing["branches"].get(name) or {}).get("branch","main")
        request=urllib.request.Request(f"https://api.github.com/repos/{name}/branches/{branch}",headers={"Accept":"application/vnd.github+json","User-Agent":"missioncontrol-flightdeck/1"})
        token=os.getenv("GITHUB_TOKEN")
        if token:request.add_header("Authorization","Bearer "+token)
        with urllib.request.urlopen(request,timeout=12) as response:
            row=json.load(response)
        head=row.get("commit",{}).get("sha")
        if not isinstance(head,str) or not SHA40.fullmatch(head):raise ValueError("Invalid live GitHub branch SHA for "+name)
        new["branches"][name]={"branch":branch,"sha":head,"protected":bool(row.get("protected",False))}
    write_json(args.snapshot,new)
    return {"status":"REFRESHED_READ_ONLY","captured_at":new["observed_at_utc"],"branches":len(new["branches"])}


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    sp=ap.add_subparsers(dest="mode",required=True)
    for mode in ("preflight","build","refresh-heads"):
        c=sp.add_parser(mode)
        c.add_argument('--fleet',required=True)
        c.add_argument('--snapshot',required=True)
        if mode!="refresh-heads":c.add_argument('--contract',required=True)
        if mode=="build":
            c.add_argument('--out',required=True)
            c.add_argument('--exact-git-sha')
    check=sp.add_parser('verify')
    check.add_argument('--out',required=True)
    pack=sp.add_parser('seal')
    pack.add_argument('--out',required=True)
    args=ap.parse_args(argv)
    try:
        if args.mode=='preflight':
            paths=[args.fleet,args.snapshot,args.contract]
            fleet,snap,contract=map(read,paths)
            validate(fleet,snap,contract)
            result={"status":"PASS","source_semantic_sha256":ssot_digest(paths),"repo_count":6,"target_cells":42,"observed":6,"unobserved":36}
        elif args.mode=='build':result=build(args)
        elif args.mode=='refresh-heads':result=refresh_heads(args)
        elif args.mode=='seal':result={"status":"SEALED","files":len(seal(args.out)["content"])}
        else:result=verify(args.out)
    except (ValueError,KeyError,IndexError,TypeError,FileNotFoundError,urllib.error.URLError) as exc:
        print(json.dumps({"status":"FAIL_CLOSED","reason":str(exc)},sort_keys=True),file=sys.stderr)
        return 2
    print(json.dumps(result,sort_keys=True))
    return 0

if __name__=='__main__':raise SystemExit(main())