"""Mission Control G3C N+16..N+18 source-bound convergence assessment.

Historical adaptive local coverage is not terminal native CI, stationarity,
Six Sigma process capability, or admitted federation. No network, no mutation.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import re
from pathlib import Path

SHA40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
PULSES = ("N+13", "N+14", "N+15")


def require(ok, msg):
    if not ok:
        raise ValueError("G3C_HOLD: " + msg)


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def project(proof, graph, producer=None):
    require(proof.get("schema") == "missioncontrol.g3a.n13_n15.source_and_local_proof.v1",
            "invalid G3A proof")
    require(proof.get("merge_admission") == "HOLD" and
            proof.get("authority_transfer") is False and
            proof.get("security_waiver") is False, "source admission promotion")
    require(proof.get("native_exact_head_ci") is None and
            proof.get("human_independent_approval") is None and
            proof.get("accepted_n_delta") is None and
            proof.get("formal_root_closures") is None,
            "unqualified native/owner proof promotion")
    require(graph.get("schema") == "code-purple.g3a.master-dags-projection.v1" and
            graph.get("merge_admission") == "HOLD" and
            graph.get("authority_transfer") is False and
            graph.get("accepted_n_delta") is None, "graph admission promotion")
    metrics = graph.get("metrics") or {}
    require((metrics.get("sources"), metrics.get("graph_families"),
             metrics.get("declared_cross_repository_edges")) == (4, 8, 3),
            "graph source population mismatch")
    require(metrics.get("native_verified_edges") is None and
            metrics.get("formal_root_closures") is None, "graph native receipt unverified")
    require(len(graph.get("topological_order") or []) == 8 and
            all(e.get("binding") == "DECLARED" and e.get("accepted") is False and
                e.get("receipt") is None for e in graph.get("edges", [])),
            "graph edges promoted or topology incomplete")
    rows = proof.get("pulse_records")
    require(isinstance(rows, list) and len(rows) == 3, "G3A three pulses incomplete")
    require(tuple(r.get("pulse") for r in rows) == PULSES, "pulse ordinal drift")
    require(proof.get("source_denominator_same") is True, "no matched denominator")
    require(isinstance(proof.get("source_bridge_git_blob"), str) and
            SHA40.fullmatch(proof["source_bridge_git_blob"]),
            "source blob declaration missing")
    require(isinstance(proof.get("source_bridge_sha256"), str) and
            HEX64.fullmatch(proof["source_bridge_sha256"]),
            "source digest declaration missing")
    data = []
    for r in rows:
        keys = ("tests_passed_local", "tests_failed_local", "statement_covered",
                "statement_total", "branch_covered", "branch_total",
                "combined_covered", "combined_total")
        require(all(type(r.get(k)) is int and r[k] >= 0 for k in keys),
                "invalid local numerator/denominator")
        s,t,b,bt = (r[k] for k in ("statement_covered", "statement_total",
                                  "branch_covered", "branch_total"))
        require(t > 0 and bt > 0 and s <= t and b <= bt and
                r["combined_covered"] == s+b and r["combined_total"] == t+bt,
                "combined coverage does not reconcile")
        require(r["tests_failed_local"] == 0 and r["tests_passed_local"] > 0,
                "unqualified local test failure")
        commit = r.get("source_commit")
        require(commit is None or (isinstance(commit, str) and SHA40.fullmatch(commit)),
                "invalid historical commit identity")
        data.append({"pulse": r["pulse"], "covered": s+b, "total": t+bt,
                     "statement": {"covered": s, "total": t},
                     "branch": {"covered": b, "total": bt},
                     "local_tests_passed": r["tests_passed_local"],
                     "source_commit": commit})
    total = data[0]["total"]
    require(all(v["total"] == total for v in data),
            "non-comparable numerator denominator")
    cover = [x["covered"] for x in data]
    require(cover == sorted(cover), "negative matched coverage trend")
    diffs = [cover[i+1]-cover[i] for i in range(2)]
    if diffs[1] > diffs[0]:
        trend = "ACCELERATING_LOCAL_COVERAGE"
    elif diffs == [0,0]:
        trend = "LOCAL_PLATEAU_ONLY"
    elif diffs[1] < diffs[0]:
        trend = "DECELERATING_LOCAL_COVERAGE"
    else:
        trend = "CONSTANT_RATE_LOCAL_COVERAGE"
    require(proof.get("cross_repository_candidate_edges") == 3 and
            proof.get("cross_repo_native_authenticated_edges") is None,
            "federation evidence misclassified")
    if producer is not None:
        require(isinstance(producer, dict) and set(producer) ==
                {"sha", "artifact_id", "workflow_run_id", "status"}, "producer contract")
        require(isinstance(producer["sha"], str) and SHA40.fullmatch(producer["sha"]) and
                type(producer["artifact_id"]) is int and producer["artifact_id"] > 0 and
                type(producer["workflow_run_id"]) is int and producer["workflow_run_id"] > 0,
                "producer native identity")
        require(producer["status"] in ("HISTORICAL_PRODUCER_GREEN", "UNVERIFIED"),
                "producer promotion forbidden")
    return {
        "schema": "missioncontrol.g3c.n16_n18.convergence.v1",
        "evidence": "G3A_HISTORICAL_LOCAL_SOURCE_ONLY",
        "g3a_proof_digest_sha256": digest(proof),
        "g3a_graph_digest_sha256": digest(graph),
        "matched_local_metrics": {
            "numerator_start": cover[0], "numerator_end": cover[-1],
            "denominator": total, "covered_delta": cover[-1]-cover[0],
            "percentage_point_change": round(100*(cover[-1]-cover[0])/total, 5),
            "successive_delta_covered": diffs, "trend": trend, "pulses": data},
        "stability": {
            "status": "NOT_QUALIFIED", "six_sigma": None,
            "independent_trials": None, "stationarity_test": None,
            "reason": "Three adaptive local testflight checkpoints are not independent process trials or current-main telemetry"},
        "source_gap": {
            "last_pulse_commit_missing": data[-1]["source_commit"] is None,
            "native_head_ci": None, "independent_review": None},
        "typed_graph": {"sources": 4, "graph_nodes": 8, "declared_edges": 3,
                        "native_authenticated_edges": None, "binding": "DECLARED_ONLY"},
        "external_producer": producer,
        "pulses": [
            {"id":"N+16","slice":"QUALIFY_MATCHED_HISTORY","state":"SOURCE_PROJECTION_ONLY"},
            {"id":"N+17","slice":"NEGATIVE_CONTROLS_AND_PROOF_DEFICITS","state":"NATIVE_CI_PENDING"},
            {"id":"N+18","slice":"MYCELIUM_FEDERATION_RETURN","state":"CONSUMER_OWNER_PENDING"}],
        "root_closures": None, "accepted_n_delta": None,
        "merge_admission": "HOLD", "authority_transfer": False,
        "security_waiver": False,
        "reentry": "#631 native CI; #701 producer head refresh; CODEX #1089 consumer review; ABACUS #1860 owner ruleset"
    }


def render(r):
    """Static, accessible, whole-count view; never a second SSOT."""
    vals = r["matched_local_metrics"]["pulses"]
    # Leave a real gutter for the first data label; on mobile an SVG shrinks
    # horizontally, so axis labels must never compete for that same space.
    left,right,top,bottom = 126,585,75,295
    denominator = vals[0]["total"]
    tick_step = max(1, 10 * max(1, round(denominator / 40)))
    xs = [left+(right-left)*i/2 for i in range(3)]
    ys = [bottom-(v["covered"]/v["total"])*(bottom-top) for v in vals]
    ticks = "".join(
        f'<g><line x1="{left}" x2="{right}" y1="{bottom-(n/denominator)*(bottom-top):.1f}" y2="{bottom-(n/denominator)*(bottom-top):.1f}" stroke="#dde2ed"/>'
        f'<text x="78" y="{bottom-(n/denominator)*(bottom-top)+5:.1f}" font-size="12" text-anchor="end">{n}</text></g>'
        for n in range(0,denominator+1,tick_step))
    path = " ".join(("M" if i == 0 else "L")+f"{x:.1f},{y:.1f}"
                    for i,(x,y) in enumerate(zip(xs,ys)))
    dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="#247b75"/>'
                   for x,y in zip(xs,ys))
    tags = "".join(
        f'<text x="{x:.1f}" y="{y-13:.1f}" font-size="13" text-anchor="middle">{v["covered"]}/{v["total"]}</text>'
        f'<text x="{x:.1f}" y="{bottom+24}" font-size="13" text-anchor="middle">{html.escape(v["pulse"])}</text>'
        for x,y,v in zip(xs,ys,vals))
    met = r["matched_local_metrics"]
    accessible = html.escape("Whole covered obligations: " +
                             ", ".join(str(v["covered"]) for v in vals) +
                             " of matched denominator " + str(denominator),quote=True)
    data_rows = "".join(
        f'<tr><th scope="row">{html.escape(v["pulse"])}</th><td>{v["covered"]}</td><td>{v["total"]}</td></tr>'
        for v in vals)
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>G3C N16–N18 | Convergence</title><style>body{{font:16px/1.45 system-ui,sans-serif;max-width:900px;margin:35px auto;padding:0 18px;background:#f6f8fb;color:#172338}}.card{{background:white;padding:20px;border:1px solid #d5dce6;border-radius:12px;margin:12px 0}}svg{{max-width:100%;height:auto}}table{{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums;font-size:13px}}th,td{{padding:5px 8px;border-bottom:1px solid #d5dce6;text-align:left}}code{{overflow-wrap:anywhere}}</style></head>
<body><h1>G3C · N+16–N+18</h1><p>Source-bound convergence candidate. NO MERGE, NO SIX-SIGMA CREDIT, NO FEDERATION ACCEPTANCE.</p>
<div class="card"><h2>Matched local G3A coverage trend</h2><svg viewBox="0 0 640 335" role="img" aria-label="{accessible}">
<text x="20" y="28" font-size="14">Covered obligations (whole counts)</text>{ticks}<path d="{path}" fill="none" stroke="#247b75" stroke-width="3"/>{dots}{tags}</svg>
<table aria-label="Exact covered-count table"><thead><tr><th>Pulse</th><th>Covered</th><th>Population</th></tr></thead><tbody>{data_rows}</tbody></table>
<p>Measured: <strong>{met["covered_delta"]} / {met["denominator"]}</strong> additional covered obligations; +{met["percentage_point_change"]} pp; {met["trend"]}.</p></div>
<div class="card"><h2>Control / caveats</h2><p>Terminal native CI and independent approval: UNKNOWN. Third pulse source commit: not source-bound in historical JSON. Eight graph nodes and three federation edges remain DECLARED; no authenticated edges or accepted root closures claimed.</p><p>Stability: <strong>NOT QUALIFIED</strong>. Three adaptive local checkpoints are not independent process samples.</p></div>
<p>Evidence: <code>{r["g3a_proof_digest_sha256"]}</code> · <code>{r["g3a_graph_digest_sha256"]}</code>.</p></body></html>'''


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--proof",type=Path,required=True)
    p.add_argument("--graph",type=Path,required=True)
    p.add_argument("--out-dir",type=Path,required=True)
    p.add_argument("--producer-observation",type=Path)
    a=p.parse_args()
    proof=json.loads(a.proof.read_text())
    graph=json.loads(a.graph.read_text())
    producer=json.loads(a.producer_observation.read_text()) if a.producer_observation else None
    r=project(proof,graph,producer)
    a.out_dir.mkdir(parents=True,exist_ok=True)
    raw=(json.dumps(r,sort_keys=True,indent=2)+"\n").encode()
    h=render(r).encode()
    (a.out_dir/"g3c-convergence.json").write_bytes(raw)
    (a.out_dir/"g3c-convergence.html").write_bytes(h)
    man={"schema":"missioncontrol.g3c.artifact_manifest.v1",
         "files_sha256":{"g3c-convergence.json":hashlib.sha256(raw).hexdigest(),
                         "g3c-convergence.html":hashlib.sha256(h).hexdigest()},
         "admission":"HOLD"}
    (a.out_dir/"manifest.json").write_text(json.dumps(man,indent=2)+"\n")
    print("G3C=SOURCE_PASS; STABILITY=NOT_QUALIFIED; ADMISSION=HOLD")


if __name__=="__main__":
    main()
