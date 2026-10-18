#!/usr/bin/env python3
"""G12 read-only incubation of pinned native evidence, not a GitHub controller.

G11 owns prior exact-ID convergence. G12 compares independently declared wave
cohorts without treating changing denominators, head revisions, or successful
workflows as root closures or governance admission.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from collections import Counter
from pathlib import Path

SCHEMA = "gogreen.g12.incubator_input.v1"
OUTPUT = "gogreen.g12.native_convergence.v1"
SHA = re.compile(r"[a-f0-9]{40}\Z")
DIGEST = re.compile(r"[a-f0-9]{64}\Z")
OUTCOMES = frozenset({"success", "failure", "cancelled", "skipped", "timed_out"})
OWNERS = {
    "ZIP_VERIFIER": "GBOGEB/pipeline-automation-hub#530",
    "CENSUS_PRODUCER": "GBOGEB/pipeline-automation-hub#531",
    "METHOD_VIEWER": "GBOGEB/pipeline-automation-hub#533",
    "CONVERGENCE_CONSUMER": "mission-control/gogreen/convergence_bridge/reconcile.py",
}


def need(condition, message):
    if not condition:
        raise ValueError("G12_HOLD: " + message)


def integer(n, name, *, positive=False):
    need(type(n) is int and (n > 0 if positive else n >= 0),
         "invalid integer " + name)
    return n


def canonical(payload):
    return (json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) +
            "\n").encode("ascii")


def ratio(covered, eligible):
    return round(100 * covered / eligible, 6) if eligible else None


def validate(data):
    need(isinstance(data, dict) and data.get("schema") == SCHEMA, "input schema")
    for control in ("authority_transfer", "dispatch_authorized",
                    "merge_authorized", "security_waiver"):
        need(data.get(control) is False, "forbidden " + control)
    need(data.get("qps_owner_acceptance") == "WITHHELD" and
         data.get("evidence_class") ==
         "FROZEN_NATIVE_API_AND_JOB_LOG_OBSERVATIONS", "false external authority")
    need(data.get("legacy_ownership") == OWNERS, "canonical owner drift")
    census = data.get("census")
    need(isinstance(census, dict), "census absent")
    obs, eligible = integer(census.get("observed"), "census observed"), integer(
        census.get("eligible"), "census eligible", positive=True)
    need(obs <= eligible and census.get("fresh_observed") is None and
         census.get("source_class") == "HISTORICAL_METADATA_ONLY",
         "stale census promoted to fresh")
    ledger = data.get("historical_root_ledger")
    need(isinstance(ledger, dict), "historical roots absent")
    root_n = integer(ledger.get("independent_root_count"), "historical roots")
    signatures = integer(ledger.get("signature_count"), "fingerprints")
    occurrences = integer(ledger.get("occurrences"), "occurrences")
    need(root_n <= signatures <= occurrences and
         ledger.get("evidence_class") ==
         "HISTORICAL_NOT_CURRENT_CAUSAL_ROOT_PROOF" and
         ledger.get("accepted_closed_root_ids") == [], "fabricated causal closure")
    need(data.get("worker_hours") is None and
         data.get("runner_capacity_slots") is None, "unknown capacity is not zero")
    waves = data.get("waves")
    need(isinstance(waves, list) and len(waves) >= 2, "two waves required")
    all_jobs, heads, last_ord = set(), set(), -1
    for wave in waves:
        need(isinstance(wave, dict), "wave object")
        n = integer(wave.get("ordinal"), "wave ordinal")
        need(n > last_ord, "nonmonotone waves")
        last_ord = n
        need(isinstance(wave.get("wave"), str) and wave["wave"], "wave label")
        head = wave.get("source_sha")
        need(isinstance(head, str) and SHA.fullmatch(head) and
             head not in heads, "wave source SHA identity")
        heads.add(head)
        jobs = wave.get("observations")
        need(isinstance(jobs, list) and jobs, "native observation population")
        families = set()
        for row in jobs:
            need(isinstance(row, dict), "native job object")
            repo = row.get("repository")
            workflow = row.get("workflow")
            need(isinstance(repo, str) and repo.startswith("GBOGEB/") and
                 isinstance(workflow, str) and workflow.strip(), "job source owner")
            family = (repo, workflow)
            need(family not in families, "duplicate workflow family in wave")
            families.add(family)
            run = integer(row.get("run_id"), "run", positive=True)
            attempt = integer(row.get("attempt"), "attempt", positive=True)
            job = integer(row.get("job_id"), "job", positive=True)
            identity = (repo, run, attempt, job)
            need(identity not in all_jobs, "duplicate native run/attempt/job")
            all_jobs.add(identity)
            need(row.get("conclusion") in OUTCOMES, "nonterminal observation")
            tests = row.get("tests")
            if tests is not None:
                need(isinstance(tests, dict) and set(tests) ==
                     {"executed", "passed", "failed", "skipped"}, "test schema")
                values = {key: integer(value, key) for key, value in tests.items()}
                need(values["executed"] == values["passed"] + values["failed"] +
                     values["skipped"] and values["executed"] > 0,
                     "test denominator integrity")
                need(row["conclusion"] != "success" or values["failed"] == 0,
                     "false-green test result")
            red = row.get("first_red_fingerprint")
            need(red is None or (isinstance(red, str) and len(red.strip()) >= 8 and
                 row["conclusion"] == "failure"), "first red attribution")
            artifact = row.get("artifact")
            if artifact is not None:
                need(isinstance(artifact, dict) and
                     integer(artifact.get("id"), "artifact ID", positive=True) and
                     integer(artifact.get("reported_size_bytes"), "ZIP reported bytes",
                             positive=True) and
                     isinstance(artifact.get("reported_sha256"), str) and
                     DIGEST.fullmatch(artifact["reported_sha256"]) and
                     artifact.get("verified_in_this_wave") is False,
                     "unverified archive promoted to byte custody")
    receipts = data.get("coverage")
    need(isinstance(receipts, list) and len(receipts) >= 2, "coverage provenance")
    for receipt in receipts:
        need(isinstance(receipt, dict) and
             isinstance(receipt.get("repository"), str) and
             receipt["repository"].startswith("GBOGEB/") and
             isinstance(receipt.get("source_sha"), str) and
             SHA.fullmatch(receipt["source_sha"]) and
             integer(receipt.get("run_id"), "coverage run", positive=True) and
             isinstance(receipt.get("scope"), str) and receipt["scope"] and
             isinstance(receipt.get("tool"), str) and receipt["tool"] and
             receipt.get("evidence_class") in
             {"PRIOR_TERMINAL_FOCUSED", "CURRENT_TERMINAL_FOCUSED"},
             "coverage source identity")
        for kind in ("statements", "branches"):
            c = receipt.get(kind)
            need(isinstance(c, dict), "coverage section " + kind)
            total = integer(c.get("eligible"), kind+" eligible", positive=True)
            covered = integer(c.get("covered"), kind+" covered")
            need(covered <= total, "coverage numerator exceeds denominator")
    return data


def compare_coverage(old, new, metric):
    a, b = old[metric], new[metric]
    matched = (old["repository"] == new["repository"] and
               old["scope"] == new["scope"] and old["tool"] == new["tool"] and
               a["eligible"] == b["eligible"])
    return {
        "scope": new["scope"],
        "baseline": [a["covered"], a["eligible"]],
        "current": [b["covered"], b["eligible"]],
        "scope_matched": matched,
        "delta_percentage_points": (round(ratio(b["covered"], b["eligible"]) -
                                          ratio(a["covered"], a["eligible"]), 6)
                                    if matched else None),
        "note": ("COMPARABLE_SCOPE_AND_DENOMINATOR" if matched else
                 "INCOMPARABLE_SOURCE_POPULATION_NO_UPLIFT_CREDIT"),
    }


def summarize(data):
    validate(data)
    waves = data["waves"]
    series = []
    for w in waves:
        counts = Counter(row["conclusion"] for row in w["observations"])
        red = sorted(set(row["first_red_fingerprint"] for row in w["observations"]
                         if row["first_red_fingerprint"] is not None))
        series.append({
            "wave": w["wave"], "source_sha": w["source_sha"],
            "native_workflow_families": len(w["observations"]),
            "terminal_success": counts["success"], "terminal_failure": counts["failure"],
            "terminal_cancelled": counts["cancelled"],
            "first_red_fingerprints": red,
            "test_methods_with_known_denominator": sum(
                o["tests"]["executed"] for o in w["observations"]
                if o["tests"] is not None),
            "unknown_test_denominator_workflows": sum(
                o["tests"] is None for o in w["observations"]),
        })
    p = {(o["repository"], o["workflow"]): o for o in waves[-2]["observations"]}
    q = {(o["repository"], o["workflow"]): o for o in waves[-1]["observations"]}
    common = sorted(set(p) & set(q))
    transitions = [{
        "repository": key[0], "workflow": key[1],
        "prior": p[key]["conclusion"], "current": q[key]["conclusion"],
        "source_sha_prior": waves[-2]["source_sha"],
        "source_sha_current": waves[-1]["source_sha"],
    } for key in common]
    recovered = sum(p[x]["conclusion"] == "failure" and
                    q[x]["conclusion"] == "success" for x in common)
    regressed = sum(p[x]["conclusion"] == "success" and
                    q[x]["conclusion"] == "failure" for x in common)
    cov = data["coverage"]
    result = {
        "schema": OUTPUT,
        "source_population": data["evidence_class"],
        "snapshots": series,
        "matched_workflow_family_count": len(common),
        "matched_success_recoveries": recovered,
        "matched_success_regressions": regressed,
        "workflow_transitions": transitions,
        "same_head_repeat_trials": 0,
        "matched_workflow_rate_delta": None,
        "interpretation": "DESCRIPTIVE_TRANSITIONS_NOT_INDEPENDENT_TRIALS",
        "coverage_comparison": {
            kind: compare_coverage(cov[-2], cov[-1], kind)
            for kind in ("statements", "branches")
        },
        "census": {
            "historical_observed": data["census"]["observed"],
            "historical_eligible": data["census"]["eligible"],
            "fresh_source_bound_breadth": None,
            "new_breadth_credit": 0,
        },
        "roots": {
            "historical_distinct_root_count":
                data["historical_root_ledger"]["independent_root_count"],
            "historical_distinct_fingerprints":
                data["historical_root_ledger"]["signature_count"],
            "historical_occurrences":
                data["historical_root_ledger"]["occurrences"],
            "new_accepted_root_closures": 0,
            "observed_red_fingerprint_displacement": (
                len(series[-2]["first_red_fingerprints"]) -
                len(series[-1]["first_red_fingerprints"])),
            "causal_root_disposition": "UNKNOWN_NOT_CREDITED",
        },
        "capacity": {"worker_hours": None, "runner_slots": None,
                     "throughput_per_worker_hour": None},
        "maturity": {"M1": "PARTIAL_SOURCE_BOUND",
                     "M2": "HOLD_NO_INDEPENDENT_TRIAL_SERIES",
                     "M3": "HOLD_NO_CAPABILITY_POPULATION"},
        "statistical_readiness": {
            "PCA": "NOT_QUALIFIED", "Bradley_Terry": "NOT_QUALIFIED",
            "Six_Sigma": "NOT_QUALIFIED",
            "independent_observations": None,
        },
        "next_wave": {
            "scenario_only": True, "forecast_failure_count": None,
            "forecast_confidence_interval": None,
            "gate": "FRESH_NATIVE_HEADS_ARTIFACT_BYTES_OWNER_RULES",
        },
        "preview_deployment": "ACTIONS_ARTIFACT_CANDIDATE_ONLY",
        "public_pages_deployed": False,
        "authority_transfer": False, "merge_authorized": False,
        "security_waiver": False, "qps_owner_acceptance": "WITHHELD",
        "formal_credit_delta": 0,
    }
    return result


def spine(report):
    nodes = [
        ("SOURCE", "Native exact head / run / attempt / job", "OBSERVED_METADATA"),
        ("NORMALIZE", "Type, population and fingerprint guards", "DETERMINISTIC"),
        ("MATCH", "Workflow-family exact join", "DETERMINISTIC"),
        ("METRICS", "Scope-matched M1 / M2 / M3", "ANALYSIS"),
        ("PREVIEW", "Offline JSON / HTML / SVG / manifest", "REVIEW_ONLY"),
        ("OWNER", "Owner rules + review + byte proof", "HOLD"),
    ]
    return {
        "schema": "gogreen.g12.incubator_spine.v1",
        "nodes": [{"id": i, "label": label, "evidence": e}
                  for i, label, e in nodes],
        "edges": [{"from": a, "to": b, "type": "FEEDFORWARD_DECLARED"}
                  for a, b in zip([n[0] for n in nodes],
                                  [n[0] for n in nodes][1:])] +
                 [{"from": "PREVIEW", "to": "SOURCE",
                   "type": "NEXT_PULSE_FEEDBACK_NOT_SAME_PULSE"}],
        "sipoc": {
            "supplier": "Native GitHub plus existing #530/#531/#533/G11 owners",
            "input": "Frozen authenticated run/job identity observations",
            "process": "Validate, deduplicate, compare matched denominators",
            "output": "Read-only evidence and preview candidate",
            "customer": "Governance owner and independent reviewer",
        },
        "merge_authorized": False, "formal_credit_delta": 0,
    }


def render_html(report):
    cells = []
    for snap in report["snapshots"]:
        width = round(100 * snap["terminal_success"] /
                      snap["native_workflow_families"])
        cells.append(
            '<article><h2>' + html.escape(snap["wave"]) + '</h2><p><code>' +
            html.escape(snap["source_sha"]) +
            '</code></p><p>Terminal successful families: <strong>' +
            str(snap["terminal_success"]) + '/' +
            str(snap["native_workflow_families"]) +
            '</strong></p><div class="bar"><i style="width:' + str(width) +
            '%"></i></div><p>Observed first-red fingerprints: ' +
            str(len(snap["first_red_fingerprints"])) + '</p></article>'
        )
    sections = ''.join(cells)
    roots = report["roots"]
    labels = '<p>Exact matched workflow families: ' + str(
        report["matched_workflow_family_count"]) + '. Fail-to-pass transitions: ' + str(
        report["matched_success_recoveries"]) + '. Separate root closures: <strong>0</strong>.</p>'
    return ('''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>G12 CODE PURPLE incubation · native evidence</title>
<style>
:root{color-scheme:dark;background:#0a1828;color:#edf5ff;font:16px system-ui}
*{box-sizing:border-box}body{max-width:1100px;margin:auto;padding:22px}
header,article,section{border:1px solid #52677d;border-radius:12px;padding:17px;margin:9px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}
code{overflow-wrap:anywhere;color:#bde6ff}strong{color:#83e1b8}
.bar{height:11px;border-radius:10px;background:#46586d;overflow:hidden}
.bar i{display:block;height:100%;background:#42c6aa}
small{color:#d8e4f4}a{color:#9ad5ff}
</style><body><header><h1>GOGREEN G12 · SOURCE-BOUND INCUBATOR</h1>
<p>Frozen native observations. No live API polling, fleet rate, causal root closure,
QPS owner acceptance, merge permission or Pages deployment.</p></header>
<main><div class="grid">''' + sections + '''</div><section><h2>Convergence</h2>''' +
            labels + '<p>Historical root IDs: ' +
            str(roots["historical_distinct_root_count"]) +
            '; signatures: ' + str(roots["historical_distinct_fingerprints"]) +
            '; repeated occurrences: ' + str(roots["historical_occurrences"]) +
            ' — no current root acceptance inferred.</p><p>Coverage statement ' +
            report["coverage_comparison"]["statements"]["note"] +
            '; branch ' + report["coverage_comparison"]["branches"]["note"] +
            '''.</p></section><section><h2>Readiness</h2><p>M1 partial · M2/M3 HOLD · PCA/BT
not qualified · worker hours/capacity UNKNOWN · N+1 forecast UNKNOWN.</p>
<p>Canon: #530 ZIP verifier · #531 six-repo breadth producer · #533 method viewer.
Artifact is an incubation preview only.</p></section></main></body></html>
''')


def render_svg(dag):
    labels = [(i, html.escape(n["label"])) for i, n in enumerate(dag["nodes"])]
    rectangles = []
    for i, label in labels:
        x = 25 + (i % 3) * 355
        y = 28 + (i // 3) * 110
        rectangles.append(
            f'<rect x="{x}" y="{y}" width="333" height="74" rx="12" '
            f'fill="#162d44" stroke="#88bed5"/><text x="{x+11}" '
            f'y="{y+29}" fill="#f1f6fd" font-size="12">{label}</text>')
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1110 245" '
            'role="img"><title>G12 read-only native incubation DAG stages</title>' +
            ''.join(rectangles) + '</svg>\n')


def render_mermaid(dag):
    lines = ["flowchart TD"]
    for n in dag["nodes"]:
        lines.append("  " + n["id"] + '["' +
                     n["label"].replace('"', "'") + '"]')
    for e in dag["edges"]:
        if e["type"] == "FEEDFORWARD_DECLARED":
            lines.append("  " + e["from"] + " --> " + e["to"])
        else:
            lines.append("  " + e["from"] + " -. next pulse .-> " + e["to"])
    return "\n".join(lines) + "\n"


def build(data, source_sha, out, *, check=False):
    need(isinstance(source_sha, str) and SHA.fullmatch(source_sha),
         "incubator exact-head identity")
    report = summarize(data)
    graph = spine(report)
    files = {
        "metrics.json": canonical(report),
        "spine.json": canonical(graph),
        "spine.mmd": render_mermaid(graph).encode("utf-8"),
        "spine.svg": render_svg(graph).encode("utf-8"),
        "index.html": render_html(report).encode("utf-8"),
    }
    manifest = {
        "schema": "gogreen.g12.incubation_artifact.v1",
        "generator_source_sha": source_sha,
        "file_sha256": {name: hashlib.sha256(raw).hexdigest()
                        for name, raw in sorted(files.items())},
        "preview_deployment": "ACTIONS_ARTIFACT_CANDIDATE_ONLY",
        "external_zip_member_bytes_verified": False,
        "merge_authorized": False, "formal_credit_delta": 0,
    }
    files["manifest.json"] = canonical(manifest)
    if check:
        need(out.is_dir(), "preview candidate absent")
        for name, raw in files.items():
            need((out / name).is_file() and (out / name).read_bytes() == raw,
                 "generated preview drift: " + name)
    else:
        out.mkdir(parents=True, exist_ok=True)
        for name, raw in files.items():
            (out / name).write_bytes(raw)
    return report, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    report, manifest = build(data, args.source_sha, args.out, check=args.check)
    print(json.dumps({"result": "CHECK_PASS" if args.check else "BUILT",
                      "observed_matched": report["matched_workflow_family_count"],
                      "new_root_credit": report["roots"]["new_accepted_root_closures"],
                      "manifest_files": len(manifest["file_sha256"]),
                      "merge_authorized": False}, sort_keys=True))


if __name__ == "__main__":
    main()
