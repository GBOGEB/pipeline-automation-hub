#!/usr/bin/env python3
"""Read-only consumer of ABACUS-owned bd.ldab.joined.census.v1.

No downloader, root register, debugger launcher, dispatch, or merge controls.
The input SHA-256 is *local byte custody*, not producer authenticity.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import re
from pathlib import Path

SHA40 = re.compile(r"[0-9a-f]{40}\Z")
URL = re.compile(r"https://github\.com/GBOGEB/(ABACUS|CODEX)/actions/runs/[1-9][0-9]*\Z")
KNOWN_SOURCES = {"bandit_disjoint", "ci_failure", "debug_receipt"}
CATEGORIES = {"BANDIT", "CI"}
LEVELS = {"REPORTED_UNVERIFIED", "PARTIAL"}


def require(ok, why):
    if not ok:
        raise ValueError(why)


def valid_sha(value):
    return isinstance(value, str) and SHA40.fullmatch(value) is not None


def check_observation(o, *, debug=False):
    require(isinstance(o, dict), "observation must be object")
    require(o.get("repository") in ("GBOGEB/ABACUS", "GBOGEB/CODEX") and
            valid_sha(o.get("source_sha")), "invalid observation source identity")
    require(type(o.get("run_id")) is int and o["run_id"] > 0 and
            type(o.get("job_id")) is int and o["job_id"] > 0,
            "unbound native run/job")
    require(isinstance(o.get("evidence_url"), str) and
            URL.fullmatch(o["evidence_url"]) and
            o["evidence_url"] == ("https://github.com/"+o["repository"]+
                                  "/actions/runs/"+str(o["run_id"])),
            "invalid or mismatched native evidence URL")
    if debug:
        require(o.get("source") == "debug_receipt" and o.get("proof_level") in LEVELS,
                "debugger evidence must remain reported or partial")
        require(type(o.get("real_probe_steps")) is int and
                o["real_probe_steps"] >= 0, "invalid debugger probe steps")
    else:
        require(o.get("source") in KNOWN_SOURCES, "unknown observation family")
        if o["source"] == "debug_receipt":
            check_observation(o, debug=True)


def consume(joined, *, expected_sha, input_sha256):
    require(isinstance(joined, dict) and joined.get("schema") == "bd.ldab.joined.census.v1",
            "canonical BD-LDAB join schema required")
    require(valid_sha(expected_sha) and isinstance(input_sha256, str) and
            re.fullmatch(r"[0-9a-f]{64}", input_sha256), "exact SHA and input digest required")
    scope = joined.get("scope")
    require(isinstance(scope, dict) and scope.get("repository") == "GBOGEB/ABACUS" and
            scope.get("head_sha") == expected_sha and
            isinstance(scope.get("scan_configuration"), str) and
            bool(scope["scan_configuration"].strip()), "wrong source SHA or scanner identity")
    require(joined.get("merge_admission") == "HOLD" and
            joined.get("authority_transfer") is False and
            joined.get("security_waiver") is False and
            joined.get("formal_credit_delta") == 0 and
            joined.get("engineering_credit_delta") == 0,
            "producer attempted authority/credit promotion")
    roots = joined.get("roots")
    unlinked = joined.get("unlinked_debug_receipts")
    m = joined.get("metrics")
    require(isinstance(roots, list) and isinstance(unlinked, list) and
            isinstance(m, dict), "missing canonical root/receipt arrays")
    ids = set(); known = set(); ci_n = 0; debug_n = 0; debugger_reported = 0
    root_rows = []; graph_edges = []
    for r in roots:
        require(isinstance(r, dict) and isinstance(r.get("root_id"), str) and
                r["root_id"].startswith(("BD-", "CI-")) and
                r["root_id"] not in ids and r.get("category") in CATEGORIES,
                "duplicate/invalid canonical root")
        ids.add(r["root_id"])
        require(r.get("disposition") in ("OPEN_UNREVIEWED", "UNCLASSIFIED_FIRST_RED"),
                "root closure cannot be inferred")
        observations = r.get("observations")
        require(isinstance(observations, list) and observations, "orphan canonical root")
        for o in observations:
            check_observation(o)
            identity = (o["repository"], o["source_sha"], o["run_id"], o["job_id"], o["source"])
            require(identity not in known, "duplicate source observation identity")
            known.add(identity)
            ci_n += (o["source"] == "ci_failure")
            debug_n += (o["source"] == "debug_receipt")
            if o["source"] == "debug_receipt":
                debugger_reported += (o["proof_level"] == "REPORTED_UNVERIFIED")
            graph_edges.append({"root": r["root_id"], "kind": o["source"],
                                "url": o["evidence_url"], "repo": o["repository"],
                                "source_sha": o["source_sha"]})
        root_rows.append({"id": r["root_id"], "category": r["category"],
                          "disposition": r["disposition"], "observations": len(observations),
                          "owner_lane": r.get("owner_lane"),
                          "source_path": r.get("source_path")})
    for o in unlinked:
        check_observation(o, debug=True)
        identity = (o["repository"], o["source_sha"], o["run_id"], o["job_id"], o["source"])
        require(identity not in known, "repeated unlinked native receipt")
        known.add(identity); debug_n += 1
        debugger_reported += (o["proof_level"] == "REPORTED_UNVERIFIED")
    require(type(m.get("full_bandit_unique")) is int and
            m["full_bandit_unique"] == sum(r["category"] == "BANDIT" for r in roots),
            "Bandit unique count/root denominator mismatch")
    require(type(m.get("ci_observations")) is int and m["ci_observations"] == ci_n and
            type(m.get("debug_receipts")) is int and m["debug_receipts"] == debug_n and
            type(m.get("debug_reported_sessions")) is int and
            m["debug_reported_sessions"] == debugger_reported,
            "native observation counts not reconcilable")
    require(m.get("active_workers") is None and m.get("changed_line_coverage") is None,
            "unsupported live worker or coverage credit")
    delta = m.get("comparable_delta")
    if delta is not None:
        require(isinstance(delta, dict) and
                delta.get("status") == "FINGERPRINT_DELTA_ONLY_REVIEW_REQUIRED" and
                delta.get("after_sha") == expected_sha and
                delta.get("scan_configuration") == scope["scan_configuration"] and
                all(type(delta.get(k)) is int and delta[k] >= 0 for k in
                    ("new", "resolved", "before_unique", "after_unique")) and
                delta["after_unique"] == m["full_bandit_unique"] and
                delta["new"] - delta["resolved"] ==
                delta["after_unique"] - delta["before_unique"],
                "unqualified historical fingerprint comparison")
    return {
        "schema": "missioncontrol.bd-ldab-readonly-consumer.v1",
        "producer": "GBOGEB/ABACUS:scripts/bd_ldab_join_census.py",
        "owner_register": "https://github.com/GBOGEB/ABACUS/issues/1929",
        "source_sha": expected_sha,
        "scan_configuration": scope["scan_configuration"],
        "input_sha256": input_sha256,
        "custody": "LOCAL_INPUT_HASH_NOT_AUTHENTICATED_GITHUB_ARTIFACT",
        "metrics": {"roots_observed": len(roots), "bandit_fingerprints": m["full_bandit_unique"],
                    "ci_manifestations": ci_n, "debug_receipts_reported": debug_n,
                    "debug_sessions_requiring_authentication": debugger_reported,
                    "unlinked_debug": len(unlinked), "linked_observations": len(graph_edges),
                    "formal_root_closures": None, "active_workers": None,
                    "changed_line_coverage": None, "comparable_fingerprint_delta": delta,
                    "independent_wave_repeats": None},
        "roots_readonly": sorted(root_rows, key=lambda x: x["id"]),
        "evidence_edges": sorted(graph_edges, key=lambda x:(x["root"],x["repo"],x["url"])),
        "unlinked_debug_readonly": sorted(unlinked, key=lambda x:
                  (x["repository"],x["source_sha"],x["run_id"],x["job_id"])),
        "debugger_dag": ["RECEIPT_REPORTED", "SESSION_AUTHENTICATION_PENDING",
                         "HYPOTHESIS_NOT_CONFIRMED", "REPRODUCTION_NOT_PROVEN",
                         "ROOT_FIX_NOT_ADMITTED"],
        "merge_admission":"HOLD", "authority_transfer":False,
        "security_waiver":False, "dispatch_authorized":False,
        "independent_review_admitted":None,
    }


def render(data):
    rows=[]
    edges_by_root={}
    for e in data["evidence_edges"]:
        edges_by_root.setdefault(e["root"], []).append(e)
    for r in data["roots_readonly"]:
        edges = " ".join('<a target="_blank" rel="noopener noreferrer" href="' +
                html.escape(e["url"], quote=True) + '">' +
                html.escape(e["kind"])+"</a>" for e in edges_by_root.get(r["id"],[]))
        rows.append('<tr data-text="'+html.escape((r["id"]+" "+r["category"]+" "+
                    str(r["source_path"])),quote=True).lower()+'"><td><code>'+html.escape(r["id"])+
                    '</code></td><td>'+html.escape(r["category"])+
                    '</td><td>'+html.escape(r["disposition"])+
                    '</td><td>'+edges+'</td></tr>')
    metrics=data["metrics"]
    cards="".join('<article><small>'+html.escape(k.replace('_',' '))+'</small><strong>'+html.escape(
        'UNKNOWN' if v is None else str(v))+'</strong></article>' for k,v in metrics.items()
        if k!="comparable_fingerprint_delta")
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>CODE PURPLE · Golden Thread BD–LDAB Consumer</title><style>
:root{color-scheme:dark;font-family:Inter,system-ui,sans-serif;background:#081322;color:#eef5ff}*{box-sizing:border-box}body{max-width:1320px;margin:auto;padding:28px}header{border-bottom:1px solid #253d51;padding-bottom:20px}h1{font-size:clamp(23px,3vw,34px)}.sub{color:#a6bed0}section{margin:28px 0}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(165px,1fr));gap:12px}.cards article{background:#132638;border:1px solid #29485d;border-radius:11px;padding:15px}.cards small{display:block;color:#acc6d8;margin-bottom:10px}.cards strong{font-size:25px}input{width:100%;padding:13px;border:1px solid #536a83;background:#14283a;color:#fff;border-radius:8px;font-size:15px}table{width:100%;border-collapse:collapse;font-size:13px}td,th{text-align:left;vertical-align:top;border-bottom:1px solid #274054;padding:12px;overflow-wrap:anywhere}th{color:#a6bed0}a{color:#75dafa}.hold{color:#ffbe82;font-weight:700}.scroll{overflow-x:auto}.mono{font-family:monospace;overflow-wrap:anywhere}footer{color:#a6bed0;border-top:1px solid #29485d;padding-top:18px}@media(max-width:500px){body{padding:14px}table{font-size:12px}}
</style></head><body><header><p class="hold">GOVERNED / READ-ONLY / ADMISSION HOLD</p><h1>Golden Thread · BD–LDAB source consumer</h1><p class="sub">ABACUS owns the causal root register. This projection cannot authenticate native receipts, dispatch agents, approve security, or merge code.</p><p class="mono">Source SHA: '''+html.escape(data["source_sha"])+'''<br>Local input SHA-256: '''+html.escape(data["input_sha256"])+'''</p></header><section class="cards">'''+cards+'''</section><section><h2>Canonical roots · evidence lineage</h2><p class="sub">Every link opens its producer run; debug proof remains unverified unless separately authenticated.</p><label for="find">Search root / category / path</label><input id="find" type="search" placeholder="Filter source-linked roots" oninput="filterRows()"><div class="scroll"><table><thead><tr><th>Canonical ID</th><th>Family</th><th>State</th><th>Native links</th></tr></thead><tbody id="rows">'''+"".join(rows)+'''</tbody></table></div><p id="visible" aria-live="polite"></p></section><section><h2>Debugger evidence ladder</h2><p class="sub">Reported receipt → authentication required → hypothesis → reproduced failure → independently verified fix. None may be skipped.</p></section><footer>Owned by <a href="https://github.com/GBOGEB/ABACUS/issues/1929">ABACUS #1929</a> · Consumer only · No fabricated source data</footer><script>function filterRows(){let q=document.getElementById('find').value.toLowerCase();let n=0;for(const row of document.querySelectorAll('#rows tr')){let yes=row.dataset.text.includes(q);row.hidden=!yes;n+=yes}document.getElementById('visible').textContent=n+' roots displayed'}filterRows()</script></body></html>'''


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--joined',required=True,type=Path)
    p.add_argument('--expected-sha',required=True)
    p.add_argument('--out',required=True,type=Path)
    a=p.parse_args(argv)
    require(a.joined.is_file() and not a.joined.is_symlink() and
            0<a.joined.stat().st_size<=10_000_000,"safe canonical source file required")
    require(a.joined.resolve()!=a.out.resolve(),"no input/output alias")
    raw=a.joined.read_bytes()
    result=consume(json.loads(raw),expected_sha=a.expected_sha,
                   input_sha256=hashlib.sha256(raw).hexdigest())
    a.out.mkdir(parents=True,exist_ok=True)
    (a.out/'bd-ldab-consumer.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    (a.out/'bd-ldab-consumer.html').write_text(render(result),encoding='utf-8')
    print('BD_LDAB_CONSUMER=LOCAL_REPRODUCIBILITY_ONLY; ADMISSION=HOLD')
    return result

if __name__=='__main__':
    main()
