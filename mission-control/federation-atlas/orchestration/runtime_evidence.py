#!/usr/bin/env python3
"""Observe the existing local runner's real products; never dispatch work.

The main/broker owners supply execution and source identity. This consumer adds
current-byte output verification and a replayable account of a bounded run.
It does not turn self-authored receipts into native or independent attestations.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import html
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def owner():
    spec = importlib.util.spec_from_file_location("runtime_evidence_atlas", HERE / "main.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def demand(condition, message):
    if not condition:
        raise ValueError(message)


def load(path):
    def pairs(items):
        result = {}
        for key, value in items:
            demand(key not in result, "duplicate JSON member: " + key)
            result[key] = value
        return result

    def bad_constant(value):
        raise ValueError("non-finite JSON number: " + value)

    return json.loads(Path(path).read_bytes(), object_pairs_hook=pairs,
                      parse_constant=bad_constant)


def file_map(directory):
    """Use the producer owner's exact product-membership definition."""
    return owner().output_files(directory)


def verify_products(atlas, root, run_dir, profile, receipt):
    """Recheck ports, producer->assembly lineage and the sealed local package.

    This is the concrete local artifact outcome. It does not assert application
    domain correctness, served-site identity, owner acceptance or remote reads.
    """
    blocks = {block["id"]: block for block in profile["blocks"]}
    artifacts, ports = {}, []
    task_defs = atlas.tasks(profile)
    for task in task_defs:
        identity = task["id"]
        row = receipt["tasks"][identity]
        if row["state"] == "succeeded" and identity != "validate":
            sealed = row.get("result", {}).get("output_files_sha256")
            demand(isinstance(sealed, dict) and sealed, "complete product seal missing: " + identity)
            atlas.safe_path(run_dir, identity)
            actual = file_map(run_dir / identity)
            demand(actual == sealed, "sealed product membership or bytes changed: " + identity)
    for task in task_defs:
        identity = task["id"]
        row = receipt["tasks"][identity]
        if row["state"] != "succeeded" or identity in {"validate", "assemble"}:
            continue
        block = blocks[task["block_id"]]
        directory = atlas.safe_path(run_dir, identity)
        observed = [atlas.validate_artifact(directory, port) for port in block["outputs"]]
        for port, observation in zip(block["outputs"], observed):
            ports.append({"task": identity, "port": port["id"], "required": port.get("required", True),
                          "observed": observation is not None})
            if observation is not None:
                artifacts[identity + "/" + observation["path"]] = observation["sha256"]
        recorded = row.get("result", {}).get("artifacts")
        if recorded is not None:
            demand(recorded == observed, "recorded producer bytes changed: " + identity)
        if identity == "orchestration":
            atlas.verify_bundle(directory, receipt["source_sha"], source_root=root)
        if identity == "portal":
            manifest = load(directory / "site-manifest.json")
            demand(manifest.get("source_git_sha") == receipt["source_sha"], "packaged source mismatch")
            members = manifest.get("public_files_sha256")
            demand(isinstance(members, dict) and members, "packaged member population missing")
            demand(set(file_map(directory)) == set(members) | {"site-manifest.json"},
                   "packaged manifest population mismatch")
            for name, expected in members.items():
                member = atlas.safe_path(directory, name)
                demand(member.is_file() and digest(member.read_bytes()) == expected,
                       "packaged member changed: " + name)
                artifacts[identity + "/" + name] = expected
    assembly_verified = False
    if receipt["tasks"]["assemble"]["state"] == "succeeded":
        expected = file_map(run_dir / "method")
        # This mirrors the existing assembler's explicit replacement precedence.
        for name, sha in file_map(run_dir / "control").items():
            if "/" not in name:
                expected[name] = sha
        for identity in ("superstitch", "convergence", "orchestration"):
            expected.update({identity + "/" + name: sha
                             for name, sha in file_map(run_dir / identity).items()})
        demand(file_map(run_dir / "assemble") == expected, "assembly did not consume exact producer bytes")
        assembly_verified = True
    return {"declared_output_ports_checked": ports, "output_members_sha256": artifacts,
            "assembly_consumed_exact_producer_bytes": assembly_verified,
            "package_member_verification": receipt["tasks"]["portal"]["state"] == "succeeded"}


def replay_tasks(rows):
    """Keep timings and identities; never publish arbitrary result/error text."""
    fields = ("repo", "needs", "state", "ready_at_seconds", "started_at_seconds",
              "execution_finished_at_seconds", "verify_started_at_seconds", "finished_at_seconds",
              "ready_wait_seconds", "execution_seconds", "verification_seconds")
    result = {}
    for identity, row in rows.items():
        replay = {key: row.get(key) for key in fields}
        replay["events"] = [{key: event[key] for key in ("state", "at_seconds")}
                            for event in row.get("events", [])]
        replay["output_member_count"] = len((row.get("result") or {}).get("output_files_sha256", {}))
        error = row.get("error")
        replay["error"] = ({key: error[key] for key in ("phase", "type", "blocked_by") if key in error}
                           if isinstance(error, dict) else None)
        result[identity] = replay
    return result


def qualify(root, run_dir):
    atlas = owner()
    root, run_dir = atlas.runtime_root(root), Path(run_dir).resolve()
    demand(not run_dir.is_relative_to(root), "runtime evidence must be outside the source checkout")
    receipt_path = run_dir / "local-run.json"
    receipt = load(receipt_path)
    demand(type(receipt.get("source_dirty")) is bool, "execution-time source cleanliness missing")
    started_at = datetime.fromisoformat(receipt["started_at"])
    demand(started_at.utcoffset() is not None, "run time requires an explicit timezone")
    head = atlas.git(root, "rev-parse", "HEAD")
    current_status = atlas.git(root, "status", "--porcelain")
    demand(current_status is not None, "current source cleanliness unavailable")
    profile = atlas.read_json(root, atlas.PROFILE)
    source_hashes = {path: atlas.digest(atlas.safe_path(root, path).read_bytes())
                     for path in atlas.source_snapshot_paths(root, profile)}
    broker = atlas.module("runtime_evidence_broker", HERE / "broker.py")
    policy = atlas.read_json(root, "mission-control/federation-atlas/orchestration/BROKER_POLICY_v1.json")
    planned = broker.plan(atlas.tasks(profile), policy=policy)
    model = {"source": {"head_sha": head, "source_digest": atlas.digest(atlas.canonical(source_hashes))},
             "broker": {"tasks": planned["tasks"]}}
    atlas.validate_local_receipt(receipt, model)
    products = verify_products(atlas, root, run_dir, profile, receipt)
    rows = receipt["tasks"]
    edges = [{"from": parent, "to": identity,
              "observed_verified_order": row["state"] != "blocked" and rows[parent]["state"] == "succeeded"}
             for identity, row in rows.items() for parent in row["needs"]]
    required = [port for port in products["declared_output_ports_checked"] if port["required"]]
    # The task graph's denominator includes blocked/unexecuted tasks. Output-port
    # counts are explicitly the inspected successful-producer subset.
    result = {"schema": "missioncontrol.runtime-outcome.evidence.v1",
              "repository": profile["repository"], "source_sha": head,
              "source_digest": model["source"]["source_digest"],
              "source_dirty": bool(current_status),
              "source_dirty_reported_at_execution": receipt.get("source_dirty"),
              "receipt_sha256": digest(receipt_path.read_bytes()), "started_at": receipt["started_at"],
              "scope": "REGISTERED_LOCAL_GENERATOR_GRAPH", "instrument": "EXISTING_BROKER_AND_ARTIFACT_CONTRACTS",
              # A dirty tree at execution or inspection means the verified bytes are
              # not the bytes of source_sha; never present that as commit-bound.
              "qualification": ("LOCAL_DIRTY_SOURCE_NOT_COMMIT_BOUND"
                                if receipt["source_dirty"] or current_status
                                else "LOCAL_EXECUTION_AND_CURRENT_BYTES_VERIFIED" if receipt["success"]
                                else "LOCAL_FAILED_EXECUTION_RECORD_VERIFIED"),
              "outcome": receipt["outcome"], "success": receipt["success"],
              "counts": {"registered_tasks": len(rows),
                         "started_tasks": sum(row["started_at_seconds"] is not None for row in rows.values()),
                         "successful_tasks": sum(row["state"] == "succeeded" for row in rows.values()),
                         "registered_dependency_edges": len(edges),
                         "observed_verified_dependency_edges": sum(edge["observed_verified_order"] for edge in edges),
                         "required_output_ports_of_successful_producers": len(required),
                         "verified_required_output_ports": sum(port["observed"] for port in required)},
              "bounds": {key: receipt["bounds"][key] for key in ("workers", "max_pending", "task_count")},
              "metrics": {key: receipt["metrics"][key] for key in (
                  "elapsed_seconds", "max_running", "peak_ready", "deferred_ready_count", "peak_deferred_ready",
                  "ready_wait_sample_count", "ready_wait_p50_seconds", "ready_wait_p95_seconds", "succeeded", "failed", "blocked")},
              "metric_validation": {"task_durations": "RECONCILED_WITH_TIMESTAMPS",
                                    "dependency_order": "RECONCILED_WITH_PARENT_TERMINAL_EVENTS",
                                    "max_running": "REPORTED_PEAK_NOT_BELOW_OBSERVED_INTERVAL_PEAK",
                                    "ready_and_deferred_counts": "RECEIPT_REPORTED_BOUNDS_CHECKED"},
              "tasks": replay_tasks(rows), "edges": edges, "products": products,
              "limits": {"code_statement_coverage": None, "code_branch_coverage": None,
                         "whole_repository_runtime_coverage": None, "authenticated_federation_coverage": None,
                         "causal_intervention_qualified": False, "independent_attestation": False,
                         "native_ci_qualified": False, "served_site_verified": False},
              "dispatch_authorized": False, "merge_authorized": False, "authority_transfer": False,
              "interpretation": "Observed dependency order, exact producer-to-assembly bytes and sealed package members support this bounded local path. "
                                "They do not independently establish causal necessity, every domain invariant, remote delivery or authority."}
    return result


def render(report):
    """Offline, source-bound replay. All displayed timestamps are recorded."""
    data = json.dumps(report, sort_keys=True, allow_nan=False).replace("<", "\\u003c").replace("&", "\\u0026")
    head = html.escape(report["source_sha"])
    return """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Runtime outcome evidence</title><style>
:root{font-family:Aptos,Segoe UI,sans-serif;color:#291637;background:#f8f4fa}*{box-sizing:border-box}
body{margin:0 auto;max-width:1180px;padding:32px 22px}header{border-top:8px solid #642c83;padding:16px 0}
h1{font-size:clamp(1.8rem,4vw,3rem);margin:.25em 0}h2{margin-top:1.6em}p{line-height:1.6}code{font-family:Consolas,monospace;overflow-wrap:anywhere}
.label{font-weight:bold;letter-spacing:.12em;color:#773893;font-size:.8rem}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(175px,1fr));gap:14px}
.card{background:white;border:1px solid #e5d4ec;border-radius:12px;padding:18px}.num{display:block;font-size:2rem;color:#642c83;font-weight:bold}
.note{background:#f3e4f1;padding:16px;border-left:4px solid #a73a91}.controls{display:flex;flex-wrap:wrap;gap:12px;align-items:center}
button{font:inherit;padding:9px 14px;background:#642c83;color:white;border:0;border-radius:7px;cursor:pointer}input[type=range]{flex:1;min-width:140px;accent-color:#9a338c}
.row{display:grid;grid-template-columns:125px 1fr 105px;gap:8px;align-items:center;padding:9px 0;border-bottom:1px solid #e4d5e9}.track{background:#e9dfed;height:22px;position:relative;border-radius:4px;overflow:hidden}
.bar{position:absolute;top:0;height:100%;background:#9b50ad}.bar.verifying{background:#d279b5}.row[data-active=true]{font-weight:bold;color:#88336e}
table{border-collapse:collapse;width:100%;font-size:.92rem}td,th{text-align:left;border-bottom:1px solid #e1d2e7;padding:10px;vertical-align:top;overflow-wrap:anywhere}th{background:#edcddf}
.scroll{overflow:auto}details{background:white;padding:16px;border:1px solid #e5d4ec;border-radius:10px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-family:Consolas,monospace;font-size:.8rem}
@media(max-width:520px){body{padding:16px 12px}.row{grid-template-columns:80px 1fr 70px;font-size:.78rem}.cards{grid-template-columns:1fr 1fr}.card{padding:12px}.num{font-size:1.6rem}}
</style><header><span class="label">GBO · EXECUTION EVIDENCE</span><h1>Experience the actual local run</h1>
<p>Eight registered tasks, their dependency order and their generated products. Replay uses recorded events; it does not launch work.</p>
<p>Source <code>HEAD_PLACEHOLDER</code></p></header><div id="cards" class="cards"></div>
<p class="note">Scope: the registered local generator graph. Native CI, hosted federation, domain acceptance and whole-repository coverage remain separate evidence.</p>
<h2>Recorded execution</h2><div class="controls"><button id="play">Replay</button><button id="reset">Reset</button><input id="time" aria-label="Recorded time" type="range" min="0" step="any"><output id="clock"></output></div><div id="timeline"></div>
<h2>What was checked</h2><p>Receipt source identity, dependency completion before successors start, output contracts, exact producer-to-assembly bytes, and package member hashes.</p>
<div class="scroll"><table><thead><tr><th>Task</th><th>Observed outcome</th><th>Prerequisites</th><th>Execution seconds</th></tr></thead><tbody id="tasks"></tbody></table></div>
<h2>Evidence boundary</h2><p id="interpretation"></p><p>“Causal intervention qualified” is false here. A positive trace records what happened. Separate failure injection and recovery runs are needed to establish which checks prevent false success.</p>
<details><summary>Inspect exact receipt and output digests</summary><pre id="source"></pre></details>
<script id="evidence" type="application/json">DATA_PLACEHOLDER</script><script>
const m=JSON.parse(document.getElementById('evidence').textContent),by=id=>document.getElementById(id),end=m.metrics.elapsed_seconds;
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const cards=[['Tasks succeeded',m.counts.successful_tasks+'/'+m.counts.registered_tasks],['Dependency edges',m.counts.observed_verified_dependency_edges+'/'+m.counts.registered_dependency_edges],['Elapsed seconds',end.toFixed(3)],['Peak active workers',m.metrics.max_running+'/'+m.bounds.workers]];
by('cards').innerHTML=cards.map(([k,v])=>'<div class="card"><span class="num">'+esc(v)+'</span>'+esc(k)+'</div>').join('');
const entries=Object.entries(m.tasks).sort((a,b)=>(a[1].started_at_seconds??Infinity)-(b[1].started_at_seconds??Infinity));
by('timeline').innerHTML=entries.map(([k,r])=>'<div class="row" data-id="'+esc(k)+'"><span>'+esc(k)+'</span><div class="track"><span class="bar" style="left:'+((r.started_at_seconds||0)/end*100)+'%;width:'+((r.execution_seconds||0)/end*100)+'%"></span></div><span class="state"></span></div>').join('');
by('tasks').innerHTML=entries.map(([k,r])=>'<tr><td>'+esc(k)+'</td><td>'+esc(r.state)+'</td><td>'+esc(r.needs.join(', ')||'source input')+'</td><td>'+((r.execution_seconds||0).toFixed(4))+'</td></tr>').join('');
by('source').textContent=JSON.stringify(m,null,2);by('interpretation').textContent=m.interpretation;by('time').max=end;let timer=null;
function show(t){by('clock').textContent=t.toFixed(2)+' / '+end.toFixed(2)+' s';document.querySelectorAll('.row').forEach(el=>{const r=m.tasks[el.dataset.id];let state='pending';r.events.forEach(e=>{if(e.at_seconds<=t)state=e.state});el.querySelector('.state').textContent=state;el.dataset.active=String(state==='running'||state==='verifying')})}
by('time').addEventListener('input',()=>show(Number(by('time').value)));by('reset').onclick=()=>{clearInterval(timer);timer=null;by('play').textContent='Replay';by('time').value=0;show(0)};
by('play').onclick=()=>{if(timer){clearInterval(timer);timer=null;by('play').textContent='Replay';return}if(Number(by('time').value)>=end)by('time').value=0;by('play').textContent='Pause';timer=setInterval(()=>{const t=Math.min(end,Number(by('time').value)+Math.max(end/160,.02));by('time').value=t;show(t);if(t>=end){clearInterval(timer);timer=null;by('play').textContent='Replay'}},50)};by('time').value=end;show(end);document.documentElement.dataset.ready='true';
</script></html>""".replace("HEAD_PLACEHOLDER", head).replace("DATA_PLACEHOLDER", data)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=HERE.parents[2])
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        root, out, run_dir = args.root.resolve(), args.out.resolve(), args.run_dir.resolve()
        demand(not out.is_relative_to(root) and not root.is_relative_to(out), "report output overlaps source")
        demand(not out.is_relative_to(run_dir) and not run_dir.is_relative_to(out), "report output overlaps run evidence")
        demand(not out.exists() or not any(out.iterdir()), "report requires a new or empty output directory")
        report = qualify(root, run_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "runtime-evidence.json").write_bytes(canonical(report))
        (out / "runtime-evidence.html").write_text(render(report), encoding="utf-8")
        print(json.dumps({"outcome": report["outcome"], "counts": report["counts"],
                          "qualification": report["qualification"]}, sort_keys=True))
        return 0 if report["success"] else 1
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"outcome": "EVIDENCE_REJECTED", "error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
