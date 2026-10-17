#!/usr/bin/env python3
"""Source-bound N3 KPI/REX projection over a bounded historical native job cohort.

Authoritative metrics remain PHASE02_KPI_TAXONOMY_v1.json. No fleet KPI,
implicit root closure, duplicate dispatcher, or extra Pages publisher.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import html
import json
import math
import os
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TAXONOMY = ROOT.parent / "PHASE02_KPI_TAXONOMY_v1.json"
RULESET = ROOT / "N3_OWNER_MASTER_RULESET_IMPORT.json"
RUN = 39066797657
PRODUCER_SHA = "bea8d0e7400e1fe50970286987d03b0e508ec212"
REPOSITORY = "GBOGEB/pipeline-automation-hub"
SCHEMA = "missioncontrol.n3.scoped_native_kpi.v1"
IDS = ("QUEUE_P95", "EXACT_HEAD_PROOF_YIELD", "FIRST_RED_COUNT",
       "ACCEPTED_RECEIPT_YIELD", "PREDICTION_VS_ACTUAL", "RUNNER_HEALTH")
SHA = re.compile(r"[0-9a-f]{40}\Z")


def demand(condition, reason):
    if not condition:
        raise ValueError("N3_FAIL_CLOSED: " + reason)


def utc(value):
    demand(isinstance(value, str) and value.endswith("Z"), "UTC timestamp")
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    demand(parsed.utcoffset() == dt.timedelta(0), "UTC offset")
    return parsed


def ruleset_gate(doc):
    demand(doc.get("target") == "branch" and doc.get("enforcement") == "active",
           "admin ruleset target")
    demand(doc.get("conditions", {}).get("ref_name", {}).get("include") ==
           ["~DEFAULT_BRANCH"], "default branch must be targeted")
    demand(doc.get("bypass_actors") == [], "unapproved bypass")
    rules = {x.get("type"): x.get("parameters", {}) for x in doc.get("rules", [])}
    demand(rules.get("pull_request", {}).get("required_approving_review_count", 0) >= 1,
           "independent reviewer requirement")
    contexts = rules.get("required_status_checks", {}).get("required_status_checks", [])
    demand(any(x.get("context") == "First-Pass Closure Gate / first-pass-closure"
               and x.get("integration_id") == 15368 for x in contexts),
           "trusted first-pass status required")
    return {"owner_importable": True, "owner_installed": None,
            "effective_master_enforcement": None,
            "negative_red_canary": None, "independent_review_attested": False}


def classify(payload, taxonomy, checkout_sha, evidence_class):
    demand(SHA.fullmatch(checkout_sha or ""), "exact presentation SHA")
    demand(taxonomy.get("schema") == "missioncontrol.phase02_kpi_taxonomy.v1",
           "canonical KPI taxonomy")
    demand(tuple(x["id"] for x in taxonomy.get("kpis", [])) == IDS,
           "six-KPI governed population")
    kpis = []
    for metric in taxonomy["kpis"]:
        kpis.append({"id": metric["id"], "label": metric["label"],
                     "unit": metric["unit"], "current_value": None,
                     "evidence_state": "UNBOUND", "numerator": None,
                     "denominator": None,
                     "reason": "No eligible native evidence for this metric"})
    jobs = []
    failures = []
    if payload is not None:
        demand(type(payload.get("total_count")) is int, "job census denominator")
        items = payload.get("jobs")
        demand(isinstance(items, list) and len(items) == payload["total_count"]
               and len(items) > 0, "complete nonempty census")
        seen = set()
        for j in items:
            demand(type(j.get("id")) is int and j["id"] not in seen, "distinct job identity")
            seen.add(j["id"])
            demand(j.get("run_id") == RUN and j.get("run_attempt") == 1
                   and j.get("head_sha") == PRODUCER_SHA, "pinned run/attempt/source")
            demand(j.get("status") == "completed"
                   and j.get("conclusion") in ("success", "failure"), "terminal job class")
            demand(type(j.get("runner_id")) is int and j["runner_id"] > 0,
                   "observed runner assignment")
            demand(j.get("labels") == ["ubuntu-24.04"], "matched runner class")
            steps = j.get("steps")
            demand(isinstance(steps, list) and steps, "nonzero native executed steps")
            demand(any(s.get("status") == "completed" for s in steps),
                   "executed step evidence")
            start, created, end = utc(j["started_at"]), utc(j["created_at"]), utc(j["completed_at"])
            demand(created <= start <= end, "time monotonicity")
            queue = (start-created).total_seconds()
            busy = (end-start).total_seconds()
            jobs.append({"id": j["id"], "run_id": RUN, "attempt": 1,
                         "source_head_sha": PRODUCER_SHA,
                         "queue_seconds": queue, "runner_seconds": busy,
                         "runner_id": j["runner_id"], "status": j["conclusion"],
                         "runner_class": "ubuntu-24.04"})
            first = next((s for s in steps if s.get("conclusion") == "failure"), None)
            if first is not None:
                demand(type(first.get("number")) is int
                       and isinstance(first.get("name"), str), "first-red step identity")
                key = {"run": RUN, "job": j["id"], "ordinal": first["number"],
                       "step": first["name"], "sha": PRODUCER_SHA}
                fp = hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()
                failures.append({"job_id": j["id"], "step": first["name"],
                                 "step_number": first["number"], "fingerprint": fp,
                                 "root_id": None, "accepted_root_closure": False})
        queue_values = sorted(x["queue_seconds"] for x in jobs)
        observed_p95 = queue_values[math.ceil(.95 * len(queue_values)) - 1]
        kpis[0].update({"current_value": observed_p95,
                        "evidence_state": "OBSERVED_HISTORICAL",
                        "numerator": None, "denominator": len(jobs),
                        "reason": "Nearest-rank p95 for exactly one pinned run; not fleet queue p95"})
    return {
        "schema": SCHEMA, "presentation_sha": checkout_sha,
        "source_repo": REPOSITORY, "producer_run_id": RUN,
        "producer_attempt": 1, "producer_sha": PRODUCER_SHA,
        "evidence_class": evidence_class,
        "scope": "ONE_HISTORICAL_RUN_MATCHED_UBUNTU_24_04_NOT_FLEET",
        "population": {"jobs": len(jobs), "first_failed_step_manifestations": len(failures),
                       "distinct_accepted_roots": None},
        "queue_p95_method": "NEAREST_RANK_EXACT_TWO_OR_MORE_SOURCE_BOUND_JOBS",
        "jobs": jobs, "manifestations": failures, "kpis": kpis,
        "runner_occupied_seconds_observed": sum(j["runner_seconds"] for j in jobs)
                                            if jobs else None,
        "fleet_runner_capacity": None, "fleet_worker_hours": None,
        "coverage": {"statements": None, "branches": None, "matched_delta": None},
        "statistical_control": {"n_independent_pulses": 1 if jobs else 0,
                                "m1": "STRUCTURAL_SOURCE_ONLY", "m2": "HOLD",
                                "m3": "HOLD", "pca": "NOT_QUALIFIED",
                                "bt": "NOT_QUALIFIED", "six_sigma": "NOT_ATTESTED"},
        "authority": {"merge_admission": "HOLD", "security_waiver": False,
                      "qps_owner_acceptance": None, "remote_dispatch": False}
    }


def native_jobs(token=None):
    url = "https://api.github.com/repos/" + REPOSITORY + "/actions/runs/" + str(RUN) + "/jobs?per_page=100"
    headers = {"Accept": "application/vnd.github+json",
               "User-Agent": "missioncontrol-n3-readonly", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = "Bearer " + token
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers, method="GET"),
                                timeout=15) as res:
        demand(res.status == 200, "native GitHub GET")
        raw = res.read(1000001)
    demand(len(raw) <= 1000000, "bounded API payload")
    return json.loads(raw)


def render(report):
    from plotly import graph_objects as go
    from plotly.io import to_html
    from plotly.offline import get_plotlyjs
    jobs = report["jobs"]
    figures = []
    for key, label in (("queue_seconds", "Runner queue wait · seconds"),
                       ("runner_seconds", "Observed runner occupation · seconds")):
        fig = go.Figure()
        if jobs:
            fig.add_trace(go.Bar(x=[str(j["id"]) for j in jobs],
                                 y=[j[key] for j in jobs],
                                 hovertemplate="Job %{x}: %{y:.1f} s<extra></extra>"))
        else:
            fig.add_annotation(x=0.5, y=0.5, xref="paper", yref="paper",
                               text="No authenticated source receipt", showarrow=False)
        fig.update_layout(height=195, margin=dict(t=22,b=36,l=36,r=12),
                          title=dict(text=label,font=dict(size=12)),
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          font=dict(color="#cce0ed",size=11),
                          yaxis=dict(rangemode="tozero",gridcolor="#3e596a"))
        figures.append(to_html(fig, full_html=False, include_plotlyjs=False,
                               div_id="n3-" + key,
                               config={"responsive": True, "displayModeBar": False}))
    table = "".join("<tr><th>" + html.escape(k["label"]) + "</th><td>" +
                    (html.escape(str(k["current_value"])) if k["current_value"] is not None
                     else "UNKNOWN") + "</td><td>" + html.escape(k["evidence_state"]) +
                    "</td><td>" + html.escape(str(k["denominator"])) + "</td></tr>"
                    for k in report["kpis"])
    page = r"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mission Control N3 · native scoped KPI and REX</title><style>
:root{color-scheme:dark;background:#0b1726;color:#eaf5fa;font-family:system-ui,sans-serif}
*{box-sizing:border-box}body{margin:0}main{max-width:1100px;margin:auto;padding:22px}
h1{font-size:clamp(25px,3.5vw,40px)}p{color:#aec6d9;line-height:1.5}
.notice{border-left:4px solid #e2bb7c;background:#332e27;padding:14px;border-radius:9px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,340px),1fr));gap:12px}
.card{padding:14px;background:#183043;border:1px solid #496479;border-radius:13px;min-width:0}
.plotly-graph-div{max-width:100%}table{width:100%;border-collapse:collapse}
th,td{border-bottom:1px solid #3f5669;text-align:left;padding:8px;font-size:12px;overflow-wrap:anywhere}
.scroller{overflow-x:auto}a{color:#a5e4f4}code{overflow-wrap:anywhere}
button{padding:9px;color:#eaf5fa;background:#25465f;border:1px solid #6290a4;border-radius:8px;cursor:pointer}
button:focus-visible{outline:3px solid #a5e4f4}
</style></head><body><main>
<p>N3 / CODE PURPLE · DMAIC / MIP / gg_MATH source-compatible</p><h1>Native KPI and LDAB evidence boundary</h1>
<div class="notice">Historical two-job cohort, not live fleet capability. M2/M3/PCA/BT/Six Sigma and independent review remain unqualified. No merge, QPS engineering acceptance or worker dispatch.</div>
<p>Source <code>@@SOURCE@@</code> · Run <a href="https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/39066797657">39066797657</a> attempt 1 · Presentation SHA <code>@@PRESENT@@</code></p>
<section class="cards"><article class="card"><h2>Queue wait</h2>@@CHART1@@</article><article class="card"><h2>Worker execution</h2>@@CHART2@@</article></section>
<section class="card"><h2>Six canonical KPI gates</h2><div class="scroller"><table><thead><tr><th>Metric</th><th>Value</th><th>Evidence</th><th>n</th></tr></thead><tbody>@@TABLE@@</tbody></table></div>
<p>Only bounded historical job queue p95 is measured; scope is not compatible with fleet p95. Other values remain unknown.</p></section>
<section class="card"><h2>REX first-red and controls</h2>
<p>@@REX@@ failed-step manifestations, distinct accepted causal roots UNKNOWN, worker-hours across fleet UNKNOWN.</p>
<button id="detailToggle" type="button" aria-controls="details" aria-expanded="false">View source and gate details</button>
<pre id="details" hidden style="white-space:pre-wrap;overflow-wrap:anywhere">@@DETAILS@@</pre>
<p><a href="n3-metrics.json">Typed receipt</a> · <a href="n3-manifest.json">SHA-256 manifest</a></p></section>
</main><script>@@PLOTLY@@</script><script>
document.getElementById("detailToggle").addEventListener("click",function(){
const e=document.getElementById("details");e.hidden=!e.hidden;
this.setAttribute("aria-expanded",String(!e.hidden));});
</script></body></html>"""
    summary = json.dumps({"scope": report["scope"], "producer_run_id": RUN,
                          "producer_sha": PRODUCER_SHA, "first_red": report["manifestations"],
                          "authority": report["authority"]}, indent=2)
    parts = {"@@SOURCE@@": PRODUCER_SHA, "@@PRESENT@@": report["presentation_sha"],
             "@@CHART1@@": figures[0], "@@CHART2@@": figures[1],
             "@@TABLE@@": table,
             "@@REX@@": str(report["population"]["first_failed_step_manifestations"]),
             "@@DETAILS@@": html.escape(summary),
             "@@PLOTLY@@": get_plotlyjs().replace("</script", "<\\/script")}
    for k, v in parts.items():
        demand(page.count(k) == 1, "HTML insertion slot " + k)
        page = page.replace(k, v)
    return page


def build(out, checkout_sha, payload=None, evidence_class="SYNTHETIC_TEST_FIXTURE_NOT_NATIVE"):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    taxonomy = json.loads(TAXONOMY.read_text(encoding="utf-8"))
    gate = ruleset_gate(json.loads(RULESET.read_text(encoding="utf-8")))
    report = classify(payload, taxonomy, checkout_sha, evidence_class)
    report["owner_required_status_gate"] = gate
    (out / "n3-metrics.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                                         encoding="utf-8")
    (out / "n3-metrics.html").write_text(render(report), encoding="utf-8")
    manifest = {"schema": "missioncontrol.n3.readonly_publisher_manifest.v1",
                "presentation_sha": checkout_sha, "producer_sha": PRODUCER_SHA,
                "producer_run_id": RUN, "publisher": "EXISTING_METHOD_ATLAS_PAGES_ONLY",
                "authority_transfer": False, "merge_admission": "HOLD",
                "evidence_class": evidence_class,
                "member_sha256": {name: hashlib.sha256((out / name).read_bytes()).hexdigest()
                                  for name in ("n3-metrics.html", "n3-metrics.json")}}
    (out / "n3-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                                          encoding="utf-8")
    return report, manifest


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--head", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--fixture", default=None)
    p.add_argument("--native-readonly", action="store_true")
    a = p.parse_args()
    demand(not (a.fixture and a.native_readonly), "one evidence mode")
    if a.fixture:
        data = json.loads(Path(a.fixture).read_text())
        kind = "SYNTHETIC_TEST_FIXTURE_NOT_NATIVE"
    elif a.native_readonly:
        try:
            data = native_jobs(os.environ.get("GITHUB_TOKEN"))
            kind = "GITHUB_ACTIONS_REST_READ_ONLY"
        except (OSError, TimeoutError, ValueError) as exc:
            data = None
            kind = "SOURCE_READBACK_UNAVAILABLE_HOLD_" + type(exc).__name__
    else:
        data = None
        kind = "UNKNOWN_NO_NATIVE_SOURCE"
    report, _ = build(a.out, a.head, data, kind)
    print(json.dumps({"n3": "SOURCE_BOUND_WITH_HOLDS", "kpi_observed":
                      sum(x["current_value"] is not None for x in report["kpis"]),
                      "jobs": report["population"]["jobs"],
                      "evidence_class": report["evidence_class"]}, sort_keys=True))
