"""W379: read-only seven-lane by ten-stage DevOps evidence crosswalk.

The JADE lifecycle module is the only owner of stage keys, probes and L0-L5.
W378 owns the three-topic pilot. This adapter does not rescore repositories,
authenticate GitHub, dispatch workers, publish, approve or authorize merging.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import io
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from metric_atlas import topic_exchange, topic_wave

SCHEMA = "jade.w379.lane-stage.input.v1"
OUTPUT = "jade.w379.lane-stage.receipt.v1"
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SHA64 = re.compile(r"[0-9a-f]{64}\Z")
COHORT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{1,79}\Z")
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
RESULTS = frozenset(("PASS", "FAIL", "UNKNOWN"))

# Keep the SSOT in JADE. The hyphenated metric-atlas directory cannot
# package-import mission-control, hence this explicit file-location adapter.
_ROOT = Path(__file__).resolve().parents[3]
_OWNER_FILE = _ROOT / "mission-control/jade_temple/devops/lifecycle.py"


def lifecycle_owner():
    spec = importlib.util.spec_from_file_location("jade_lifecycle_w379_owner", _OWNER_FILE)
    if spec is None or spec.loader is None:
        raise ValueError("CANONICAL_LIFECYCLE_MISSING")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


OWNER = lifecycle_owner()
STAGES = tuple(OWNER.STAGE_KEYS)
if len(STAGES) != 10 or len(set(STAGES)) != 10:
    raise ValueError("CANONICAL_STAGE_POPULATION_DRIFT")

# Seven source-disjoint contracts, each position bound to OWNER.STAGE_KEYS.
# The cells describe required lane work; they confer no maturity credit.
LANES = {
    "A": ("Census", "Metric Atlas / registry", (
        "Scope and source ownership", "Fingerprint delta detector",
        "Freeze commit and source IDs", "Test cache and targeted drift",
        "Reject forged or stale OIDs", "Build topic-bound packet",
        "Hand off read-only census", "Reuse or pull with valid ACK",
        "Measure queue and scan costs", "Tune partial invalidation")),
    "B": ("CI roots", "GOGREEN / EVERRED", (
        "Define causal-root policy", "Trace first-red source hooks",
        "Bundle exact-run diagnostics", "Test recurrence negatives",
        "Protect secrets and tokens", "Produce source-bound root receipt",
        "Hand off guarded repair", "Triage owner-controlled roots",
        "Measure recurring failures", "Install prevention tests")),
    "C": ("Backlog / BD", "issue_rank / title_taxonomy", (
        "Set priority and WIP", "Parse title-family vocabulary",
        "Build issue and blocker DAG", "Test stable rank and edges",
        "Check conflicting repair leases", "Receipt for qualified flow",
        "Hand off downstream unblock", "Operate queue-drain lanes",
        "Measure aging and arrivals", "MIP re-rank and closure")),
    "D": ("Object graph", "JADE DAG / SPINE", (
        "Agree typed graph schema", "Bind source OIDs and functions",
        "Build one canonical graph", "Test DAG and view parity",
        "Verify SHA/OID provenance", "Publish deterministic graph digest",
        "Deploy read-only viewer", "Navigate object relationships",
        "Detect stale edges and cycles", "Regenerate on source drift")),
    "E": ("Engineering", "cryoplant-project owner", (
        "Define source/owner boundary", "Crosswalk feeders and KKS",
        "Bind restricted evidence hashes", "Test Annex/SLD reconciliation",
        "Preserve restricted-access rules", "Record owner disposition",
        "Handoff to PUB-R07", "Manage owner review and RFIs",
        "Post-merge source QA", "Close documented discrepancies")),
    "F": ("Publication / ACK", "W377 exchange / PUB-R07", (
        "Define recipients and routes", "Integrate W377 packet exchange",
        "Stage immutable packet outbox", "Test replay and ACK negatives",
        "Verify controller HMAC readback", "Record delivery provenance",
        "Handoff to exclusive publisher", "Operate recipient state",
        "Monitor TTL/ACK and staleness", "Invalidate targeted recipients")),
    "G": ("Assurance", "CI / governance owners", (
        "Declare admission gates", "Apply test and lint contracts",
        "Reproduce digest-bound builds", "Run exact-head native tests",
        "Check action pins and least privilege", "Verify release provenance",
        "Require protected deploy receipt", "Prove rollback and health",
        "Exercise negative red canary", "DMAIC recurrence control")),
}


def require(condition, code):
    if not condition:
        raise ValueError(code)


def _digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True, allow_nan=False).encode("utf-8")).hexdigest()


def _source_binding(row, heads, observed_at):
    require(type(row) is dict and set(row) == {
        "lane", "stage", "repo", "head_sha", "receipt_sha256",
        "result", "observed_at", "evidence_url"}, "INVALID_OBSERVATION_FIELDS")
    require(row["lane"] in LANES and row["stage"] in STAGES, "UNKNOWN_LANE_OR_STAGE")
    repo = row["repo"]
    require(type(repo) is str and REPOSITORY.fullmatch(repo), "INVALID_EVIDENCE_REPOSITORY")
    require(repo in heads and row["head_sha"] == heads[repo], "SOURCE_HEAD_MISMATCH")
    require(type(row["receipt_sha256"]) is str and SHA64.fullmatch(row["receipt_sha256"]),
            "INVALID_EVIDENCE_DIGEST")
    require(row["result"] in RESULTS, "INVALID_EVIDENCE_RESULT")
    require(topic_exchange.timestamp(row["observed_at"]) <= topic_exchange.timestamp(observed_at),
            "FUTURE_EVIDENCE")
    url = row["evidence_url"]
    require(type(url) is str and len(url) <= 2000, "INVALID_EVIDENCE_URL")
    parts = urlsplit(url)
    require(parts.scheme == "https" and parts.hostname == "github.com" and not parts.username
            and not parts.password and parts.port is None and
            parts.path.startswith("/" + repo + "/") and
            not parts.query and not parts.fragment, "CROSS_SOURCE_OR_UNTRUSTED_URL")


def validate(snapshot):
    require(type(snapshot) is dict and set(snapshot) == {
        "schema", "cohort", "observed_at", "mode", "source_heads",
        "observations", "authority_transfer", "merge_admission"}, "INVALID_SNAPSHOT_FIELDS")
    require(snapshot["schema"] == SCHEMA and snapshot["mode"] == "READ_ONLY_SOURCE_DECLARED",
            "INVALID_SNAPSHOT_SCHEMA_OR_MODE")
    require(snapshot["authority_transfer"] is False and snapshot["merge_admission"] == "HOLD",
            "AUTHORITY_ESCALATION")
    require(type(snapshot["cohort"]) is str and COHORT.fullmatch(snapshot["cohort"]),
            "INVALID_COHORT")
    topic_exchange.timestamp(snapshot["observed_at"])
    heads = snapshot["source_heads"]
    require(type(heads) is dict and len(heads) <= 25, "INVALID_SOURCE_HEADS")
    for repo, sha in heads.items():
        require(type(repo) is str and REPOSITORY.fullmatch(repo) and
                type(sha) is str and SHA40.fullmatch(sha), "INVALID_SOURCE_HEAD")
    rows = snapshot["observations"]
    require(type(rows) is list and len(rows) <= len(LANES)*len(STAGES), "INVALID_EVIDENCE_COUNT")
    seen = set()
    for row in rows:
        _source_binding(row, heads, snapshot["observed_at"])
        key = (row["lane"], row["stage"])
        require(key not in seen, "DUPLICATE_LANE_STAGE_OBSERVATION")
        seen.add(key)
    return True


def project(snapshot, pilot_input=None):
    """Render source-declared evidence; an observed green is NOT a verified PASS."""
    validate(snapshot)
    for code, (_, _, tasks) in LANES.items():
        require(len(tasks) == len(STAGES), "LANE_STAGE_DRIFT_" + code)
    rows = {(r["lane"], r["stage"]): r for r in snapshot["observations"]}
    stages_by_name = {s[0]: s for s in OWNER.STAGES}
    cells = []
    for lane, (name, owner, activities) in LANES.items():
        for stage, activity in zip(STAGES, activities):
            observed = rows.get((lane, stage))
            status = ("UNKNOWN" if observed is None else
                      "OBSERVED_PASS_UNVERIFIED" if observed["result"] == "PASS" else
                      "OBSERVED_FAIL_HOLD" if observed["result"] == "FAIL" else "UNKNOWN")
            cells.append({
                "lane": lane, "lane_name": name, "owner": owner,
                "stage": stage, "stage_title": stages_by_name[stage][1],
                "activity": activity,
                "canonical_probe_ids": [p[0] for p in OWNER.PROBES if p[1] == stage],
                "status": status, "maturity_level": None,
                "evidence_url": observed["evidence_url"] if observed else None,
                "source_head": observed["head_sha"] if observed else None,
                "receipt_sha256": observed["receipt_sha256"] if observed else None})
    pilot = None
    if pilot_input is not None:
        wave = topic_wave.pilot(pilot_input)
        require(wave["authority_transfer"] is False and wave["merge_admission"] == "HOLD",
                "W378_AUTHORITY_ESCALATION")
        require(wave["metrics"]["source_writers"] == 0 and
                wave["metrics"]["native_jobs_dispatched"] == 0, "W378_NATIVE_WRITE_CLAIM")
        pilot = {"schema": wave["schema"],
                 "declared_source_pulse_sha256": wave["source_pulse_sha256"],
                 "declared_topics": wave["metrics"]["topics"],
                 "declared_planner_readers": pilot_input["max_readers"],
                 "classification": "SYNTHETIC_PILOT_NOT_LIVE_EVIDENCE",
                 "verified_external_acks": 0, "measured_queue_p95_seconds": None,
                 "measured_saved_runner_minutes": None}
    counts = {s: sum(c["status"] == s for c in cells)
              for s in ("UNKNOWN", "OBSERVED_PASS_UNVERIFIED", "OBSERVED_FAIL_HOLD")}
    report = {
        "schema": OUTPUT, "cohort": snapshot["cohort"], "observed_at": snapshot["observed_at"],
        "source_heads": dict(sorted(snapshot["source_heads"].items())),
        "stage_owner": "mission-control/jade_temple/devops/lifecycle.py",
        "stage_keys": list(STAGES), "maturity_levels": {str(k):v for k,v in OWNER.LEVELS.items()},
        "maturity_scope": "REPO_CENSUS_ONLY_NOT_TRANSFERABLE_TO_LANES",
        "lanes": [{"code":code, "name":data[0], "owner":data[1]} for code,data in LANES.items()],
        "cells": cells, "counts": counts, "pilot": pilot,
        "same_pulse_stages_acyclic": True if OWNER.topo_layers(
            list(STAGES), OWNER.EDGES) else False,
        "next_pulse_feedback_only": [list(e) for e in OWNER.EDGES if e[2].startswith("FEEDBACK")],
        "real_lane_maturity_verified": False, "source_writers": 0,
        "merges_performed": 0, "deployments_performed": 0,
        "scale_admission": "HOLD_PENDING_NATIVE_READBACK_AND_CONTROLLER_ACK",
        "authority_transfer": False, "merge_admission": "HOLD"}
    report["digest_sha256"] = _digest(report)
    return report


def render_markdown(report):
    stages = report["stage_keys"]
    by_key = {(c["lane"], c["stage"]): c for c in report["cells"]}
    labels = {"UNKNOWN": "?", "OBSERVED_PASS_UNVERIFIED": "o+",
              "OBSERVED_FAIL_HOLD": "o-"}
    out = ["# W379 lane by DevOps stage matrix", "",
           "Read-only declared evidence. Cells are NOT repo maturity levels or merge gates.",
           "?: unknown; o+: observed PASS not independently verified; o-: observed FAIL/HOLD.", "",
           "| Lane | " + " | ".join(x.split("_")[0] for x in stages) + " |",
           "|" + "---|" * (len(stages)+1)]
    for lane, name, _ in report["lanes_as_tuples"] if False else [
            (x["code"], x["name"], x["owner"]) for x in report["lanes"]]:
        out.append("| " + lane + " " + name + " | " +
                   " | ".join(labels[by_key[(lane,stage)]["status"]] for stage in stages) + " |")
    out += ["", "## Per-cell activity and canonical JADE probes", "",
            "| Lane | Stage | Required activity | Canonical probes | Observed status |",
            "|---|---|---|---|---|"]
    for c in report["cells"]:
        out.append("| " + " | ".join((c["lane"], c["stage"], c["activity"],
                       ", ".join(c["canonical_probe_ids"]), c["status"])) + " |")
    out += ["", "## Governance and bounded scaling", "",
            "W377 #985 -> W378 #986 -> W379: predecessor exact-head CI and independent",
            "review remain mandatory; a green unit test is not merge admission.",
            "",
            "P0: three synthetic topics, two read-only planners, zero source writes.",
            "P1: six source-disjoint topics only with source identity and lease evidence.",
            "P2: twelve-plus only after native queue p95, controller ACK and owner acceptance.",
            "",
            "S9 CONTROL feeds S0 PLAN of the NEXT pulse, never a same-pulse cycle.",
            "No real fleet recensus, production ACK, savings, deploy or merge is claimed.", ""]
    return "\n".join(out)


def render_csv(report):
    out = io.StringIO(newline="")
    writer = csv.writer(out, lineterminator="\n")
    keys = ("lane", "stage", "activity", "owner", "status", "maturity_level",
            "source_head", "receipt_sha256", "evidence_url")
    writer.writerow(keys)
    for cell in report["cells"]:
        writer.writerow([cell[k] for k in keys])
    return out.getvalue()


def emit(report, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    assets = {
        "lane-stage.json": json.dumps(report, sort_keys=True, indent=2) + "\n",
        "lane-stage.md": render_markdown(report),
        "lane-stage.csv": render_csv(report)}
    hashes = {}
    for name, content in assets.items():
        blob = content.encode("utf-8")
        (output / name).write_bytes(blob)
        hashes[name] = hashlib.sha256(blob).hexdigest()
    manifest = {"schema": "jade.w379.lane-stage.manifest.v1",
                "source_report_sha256": report["digest_sha256"],
                "files_sha256": dict(sorted(hashes.items())),
                "authority_transfer": False, "merge_admission": "HOLD"}
    (output / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--w378-input", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    wave = json.loads(args.w378_input.read_text(encoding="utf-8")) if args.w378_input else None
    r = project(snapshot, wave)
    m = emit(r, args.out)
    print(json.dumps({"cells": len(r["cells"]), "observed": len(snapshot["observations"]),
                      "manifest_files": len(m["files_sha256"]), "merge_admission": "HOLD"},
                     sort_keys=True))


if __name__ == "__main__":
    main()
