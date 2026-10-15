"""GOGREEN G0: read-only, source-bound positive-evidence census and scout planner.

No network, subprocess execution, CI dispatch, mutation or merge authority.
A successful run is not a test, a statistical trial, or an admission decision.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

INPUT_SCHEMA = "gogreen.fleet.intake.v1"
OUTPUT_SCHEMA = "gogreen.fleet.positive-evidence.v1"
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
FAMILIES = (
    "ci_contract", "security", "coverage", "runtime", "artifact",
    "federation", "qps_triage", "math_model",
)
ROLE_PLATERS = (
    "SCOUT", "READER", "PROBE_PLANNER", "TEST_PILOT", "RELIABILITY",
    "GOLDEN_THREAD", "MYCELIUM", "TRIAGE", "GATE_KEEPER",
)
OUTPUTS = ("evidence.json", "scout_packets.json", "federation_hooks.json", "summary.md")


def canonical(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _strict_count(value: object, label: str, *, positive: bool = False) -> int:
    if type(value) is not int or value < (1 if positive else 0):
        raise ValueError(f"{label}: nonnegative integer required" if not positive else f"{label}: positive integer required")
    return value


def _sha(value: object, label: str) -> str:
    if not isinstance(value, str) or SHA40.fullmatch(value) is None:
        raise ValueError(f"{label}: exact 40-byte Git SHA required")
    return value


def _check_catalog(catalog: object) -> dict[str, dict]:
    if not isinstance(catalog, list) or not catalog:
        raise ValueError("nonempty repository catalog required")
    found = {}
    for entry in catalog:
        if not isinstance(entry, dict):
            raise ValueError("invalid catalog entry")
        repo = entry.get("repository")
        if not isinstance(repo, str) or REPO.fullmatch(repo) is None or repo in found:
            raise ValueError("duplicate/invalid repository identity")
        _sha(entry.get("head_sha"), "catalog head")
        if entry.get("ref_kind") not in ("MAIN", "PR_HEAD"):
            raise ValueError("catalog must distinguish current-main and PR-head samples")
        fam = entry.get("target_families")
        if not isinstance(fam, list) or not fam or len(set(fam)) != len(fam) or any(f not in FAMILIES for f in fam):
            raise ValueError("invalid/duplicated target families")
        if entry.get("authority_transfer") is not False:
            raise ValueError("cross-repository authority transfer prohibited")
        found[repo] = entry
    return found


def _check_observation(row: dict, catalog: dict[str, dict]) -> dict:
    if not isinstance(row, dict):
        raise ValueError("invalid observation")
    repo, family = row.get("repository"), row.get("family")
    if repo not in catalog or family not in catalog[repo]["target_families"]:
        raise ValueError("observation outside declared repo/family census")
    sha = _sha(row.get("source_sha"), "observation source")
    _sha(row.get("base_sha"), "observation baseline")
    if sha != catalog[repo]["head_sha"]:
        raise ValueError("observation not matched to declared exact head")
    if not isinstance(row.get("suite_id"), str) or not row["suite_id"]:
        raise ValueError("missing test/suite identity")
    for key in ("run_id", "run_number", "run_attempt", "job_id"):
        _strict_count(row.get(key), key, positive=True)
    for key in ("workflow_status", "workflow_conclusion", "job_status", "job_conclusion"):
        if row.get(key) not in ("completed", "queued", "in_progress", "pending", "success", "failure", "cancelled", "skipped", None):
            raise ValueError("invalid workflow/job state")
    if row.get("workflow_status") != "completed" and row.get("workflow_conclusion") is not None:
        raise ValueError("nonterminal workflow has conclusion")
    if row.get("job_status") != "completed" and row.get("job_conclusion") is not None:
        raise ValueError("nonterminal job has conclusion")
    if not isinstance(row.get("config_identity"), str) or not row["config_identity"]:
        raise ValueError("missing tool/config identity")
    if row.get("run_url") != f"https://github.com/{repo}/actions/runs/{row['run_id']}":
        raise ValueError("native run URL does not match repository/run")
    evidence_class = row.get("evidence_class")
    if evidence_class != "GITHUB_NATIVE_METADATA":
        raise ValueError("unapproved or implicit evidence class")
    artifact = row.get("artifact")
    bytes_verified = False
    if artifact is not None:
        if not isinstance(artifact, dict) or not isinstance(artifact.get("id"), int) or artifact["id"] < 1:
            raise ValueError("invalid artifact identity")
        digest = artifact.get("archive_sha256")
        if not isinstance(digest, str) or not SHA256.fullmatch(digest):
            raise ValueError("artifact SHA-256 required")
        if type(artifact.get("bytes_verified")) is not bool:
            raise ValueError("artifact verification status required")
        bytes_verified = artifact["bytes_verified"]
        if bytes_verified and not isinstance(artifact.get("verifier_receipt"), str):
            raise ValueError("verified-byte claim requires independent receipt")
    counts = row.get("test_counts")
    if counts is not None:
        if not isinstance(counts, dict):
            raise ValueError("invalid test counts")
        for key in ("executed", "passed", "failed", "skipped"):
            _strict_count(counts.get(key), key)
        if counts["executed"] != sum(counts[k] for k in ("passed", "failed", "skipped")):
            raise ValueError("test denominator does not reconcile")
    burndown = row.get("scoped_burndown")
    if burndown is not None:
        if not isinstance(burndown, dict):
            raise ValueError("invalid burndown")
        for key in ("before", "after", "resolved", "introduced"):
            _strict_count(burndown.get(key), key)
        if burndown["after"] != burndown["before"] - burndown["resolved"] + burndown["introduced"]:
            raise ValueError("nonreconciling burndown")
        if not isinstance(burndown.get("scope_id"), str) or not burndown["scope_id"]:
            raise ValueError("unbound measurement scope")
        if not isinstance(burndown.get("tool_version"), str) or not burndown["tool_version"]:
            raise ValueError("unbound tool version")
    run_pass = all(row.get(k) == v for k, v in (
        ("workflow_status", "completed"), ("workflow_conclusion", "success"),
        ("job_status", "completed"), ("job_conclusion", "success")))
    if counts is not None and (counts["failed"] > 0 or (counts["executed"] and counts["passed"] == 0)):
        run_pass = False
    return {
        "repository": repo, "source_sha": sha, "family": family,
        "suite_id": row["suite_id"], "run_id": row["run_id"],
        "run_number": row["run_number"], "run_attempt": row["run_attempt"],
        "job_id": row["job_id"], "run_url": row.get("run_url"),
        "test_counts": counts, "scoped_burndown": burndown,
        "artifact_id": artifact["id"] if artifact else None,
        "status": "NATIVE_PASS_BYTES_VERIFIED" if run_pass and bytes_verified else (
            "NATIVE_PASS_METADATA" if run_pass else "NON_GREEN_OR_NONTERMINAL"),
        "artifact_bytes_verified": bytes_verified,
        "stress_limits_observed": None, "coverage_delta": None,
        "independent_trial_count": None, "merge_admitted": False,
        "root_closed": False, "source_class": evidence_class,
    }


def build(intake: dict) -> tuple[dict, dict, dict]:
    if not isinstance(intake, dict) or intake.get("schema") != INPUT_SCHEMA:
        raise ValueError("invalid GOGREEN input schema")
    catalog = _check_catalog(intake.get("repositories"))
    raw = intake.get("observations")
    if not isinstance(raw, list):
        raise ValueError("observations array required, even if empty")
    seen = set()
    normalized = []
    for item in raw:
        v = _check_observation(item, catalog)
        key = (v["repository"], v["run_id"], v["run_attempt"], v["job_id"])
        if key in seen:
            raise ValueError("duplicated run/attempt/job observation")
        seen.add(key)
        normalized.append(v)
    normalized.sort(key=lambda r: (r["repository"], r["run_id"], r["run_attempt"], r["job_id"]))
    cells = {(repo, f) for repo, entry in catalog.items() for f in entry["target_families"]}
    observed_cells = {(r["repository"], r["family"]) for r in normalized}
    native_metadata = [r for r in normalized if r["status"] == "NATIVE_PASS_METADATA"]
    verified_bytes = [r for r in normalized if r["status"] == "NATIVE_PASS_BYTES_VERIFIED"]
    qualified_cells = {(r["repository"], r["family"]) for r in native_metadata + verified_bytes}
    tested_repos = {r["repository"] for r in normalized}
    tested_families = {r["family"] for r in normalized}
    run_groups = defaultdict(set)
    for r in normalized:
        if r["status"].startswith("NATIVE_PASS"):
            run_groups[(r["repository"], r["suite_id"], r["source_sha"])].add(r["run_id"])
    repeat = [{"repo": repo, "suite_id": suite, "sha": sha,
               "distinct_pass_run_ids": len(ids), "statistically_independent": None,
               "repeatability_qualified": None}
              for (repo, suite, sha), ids in sorted(run_groups.items())]
    evidence = {
        "schema": OUTPUT_SCHEMA,
        "classification": "OBSERVATIONAL_NOT_ENGINEERING_ADMISSION",
        "authority_transfer": False, "remote_mutation": False,
        "merge_authorized": False, "security_waiver": False,
        "observations": normalized,
        "breadth": {
            "catalog_repositories": len(catalog),
            "catalog_repo_family_cells": len(cells),
            "observed_repositories": len(tested_repos),
            "observed_families": len(tested_families),
            "observed_cells": len(observed_cells),
            "native_green_metadata_observations": len(native_metadata),
            "native_green_bytes_verified_observations": len(verified_bytes),
            "native_green_cells": len(qualified_cells),
            "not_observed_cells": len(cells - observed_cells),
            "coverage_gain_percentage_points": None,
            "verified_root_closures": None,
            "stress_capacity": None,
            "independent_green_trials": None,
            "fleet_release_admission": "HOLD",
        },
        "repeatability": repeat,
        "method": "One workflow run number is not an independent trial; no extrapolation from a successful lint run to stress/coverage or security acceptance.",
    }
    packets = []
    for repo, family in sorted(cells - observed_cells):
        profile = catalog[repo]
        packets.append({"packet_id": f"GG-G0-{len(packets)+1:03d}",
                        "repository": repo, "family": family,
                        "source_sha": profile["head_sha"],
                        "role_platers": ["SCOUT", "READER", "GATE_KEEPER"],
                        "mode": "READ_ONLY_DISCOVERY", "worker_state": "STAGED_NOT_LAUNCHED",
                        "path_lease": None, "dispatch_authorized": False,
                        "next_receipt": "Native exact-SHA run/job and measured test/coverage/environment contract; UNKNOWN until produced"})
    for r in native_metadata:
        packets.append({"packet_id": f"GG-G1-{len(packets)+1:03d}",
                        "repository": r["repository"], "family": r["family"],
                        "source_sha": r["source_sha"],
                        "role_platers": ["TEST_PILOT", "RELIABILITY", "GATE_KEEPER"],
                        "mode": "CANDIDATE_REPEAT_AND_ARTIFACT_BYTE_PROOF",
                        "worker_state": "STAGED_NOT_LAUNCHED", "path_lease": None,
                        "dispatch_authorized": False,
                        "next_receipt": "Independently verify artifact bytes; then compare source-matched trials and scoped coverage"})
    plan = {"schema": "gogreen.scout-plan.v1", "mode": "PLAN_ONLY",
            "target_repositories": sorted(catalog), "packets": packets,
            "role_platers": list(ROLE_PLATERS),
            "experiment_limit_defaults": {"max_parallel_workers": 2, "max_runtime_seconds": 120,
                                          "max_queue_depth": 8, "max_async_tasks": 16,
                                          "stress_isolation": "SYNTHETIC_ONLY_UNTIL_APPROVED"},
            "execution_authorized": False, "mutation_authorized": False,
            "red_feedback": "Route material new failures to canonical EVERRED root-owner intake; do not auto-fix or override admission"}
    hooks = {"schema": "gogreen.federation-hooks.v1", "mode": "PROPOSALS_ONLY",
             "authority_transfer": False, "child_acceptance": "DEFER",
             "mycelium": {"producer": "GBOGEB/CODEX:mission_control/mycelium",
                           "projection": "positive-evidence candidate; proof edge required"},
             "golden_thread": {"producer": "GBOGEB/pipeline-automation-hub:mission-control/golden-thread",
                               "mechanism": "ADAPTER", "source_truth_mutation": False},
             "everred": {"producer": "GBOGEB/ABACUS:tools/everred_v3",
                         "use": "link read-only typed first-red/burndown evidence"},
             "qps_triage": {"consumer": "GBOGEB/pipeline-automation-hub:mission-control/qps-triage-ultra",
                            "suggested_disposition": "DEFER", "admission_evidence": False},
             "math": {"provider": "GBOGEB/gg_MATH", "mode": "OPTIONAL_PROVIDER_NOT_PROMOTED"},
             "catalog": [
                 {"repository": repo, "source_sha": c["head_sha"], "ref_kind": c["ref_kind"], "target_families": c["target_families"],
                  "authority_transfer": False} for repo, c in sorted(catalog.items())
             ]}
    return evidence, plan, hooks


def emit(intake: dict, output: Path) -> dict:
    evidence, plan, hooks = build(intake)
    output.mkdir(parents=True, exist_ok=True)
    b = evidence["breadth"]
    summary = (
        "# GOGREEN G0 — Wide-first positive evidence census\n\n"
        f"- Target repositories: **{b['catalog_repositories']}**; repo-family cells: **{b['catalog_repo_family_cells']}**.\n"
        f"- Observed cells: **{b['observed_cells']}**; native metadata-PASS observations: **{b['native_green_metadata_observations']}**.\n"
        f"- Independently artifact-byte verified PASS: **{b['native_green_bytes_verified_observations']}**.\n"
        f"- Not yet observed cells: **{b['not_observed_cells']}** (UNKNOWN, not failed).\n"
        "- Comparable coverage gain, stress capacity and independent trial quality: **UNKNOWN**.\n"
        "- Execution, external acceptance, merge and security waiver: **NOT AUTHORIZED**.\n\n"
        "## Next operating sequence\n"
        "Scout breadth -> verify native producer/bytes -> propose disjoint bounded experiments -> compare matched trials -> governed consumer reentry.\n"
    )
    payloads = {"evidence.json": json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                "scout_packets.json": json.dumps(plan, indent=2, sort_keys=True) + "\n",
                "federation_hooks.json": json.dumps(hooks, indent=2, sort_keys=True) + "\n",
                "summary.md": summary}
    for name, content in payloads.items():
        (output / name).write_text(content, encoding="utf-8")
    manifest = {"schema": "gogreen.manifest.v1", "authority_transfer": False,
                "sha256": {k: hashlib.sha256(payloads[k].encode("utf-8")).hexdigest() for k in sorted(payloads)}}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return evidence


def verify_output(output: Path) -> dict:
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema") != "gogreen.manifest.v1" or manifest.get("authority_transfer") is not False or set(manifest.get("sha256", {})) != set(OUTPUTS):
        raise ValueError("invalid output manifest")
    for name, digest in manifest["sha256"].items():
        if not SHA256.fullmatch(digest) or hashlib.sha256((output / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"artifact bytes mismatch: {name}")
    evidence = json.loads((output / "evidence.json").read_text(encoding="utf-8"))
    if evidence.get("merge_authorized") is not False or evidence.get("authority_transfer") is not False:
        raise ValueError("unauthorized promotion")
    plan = json.loads((output / "scout_packets.json").read_text(encoding="utf-8"))
    if plan.get("execution_authorized") is not False or any(p["dispatch_authorized"] for p in plan["packets"]):
        raise ValueError("unauthorized dispatch")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)
    if args.verify:
        print(canonical(verify_output(args.out)))
        return
    if args.input is None:
        parser.error("--input required for generation")
    report = emit(json.loads(args.input.read_text(encoding="utf-8")), args.out)
    verify_output(args.out)
    print(canonical(report["breadth"]))


if __name__ == "__main__":
    main()
