"""CODE PURPLE recovery evolution: source-bound, no authority or CI bypass.

Works alongside existing G4 fleet evidence breadth; never combines denominators.
Only terminal GitHub run/job metadata is represented; archive bytes are separate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

SCHEMA = "codepurple.recovery-wave.v1"
INPUT = "codepurple.recovery-pulse-input.v1"
HEX_SHA = re.compile(r"[0-9a-f]{40}\Z")
STATES = {"PASS", "FAIL", "UNKNOWN"}
COUNT_FIELDS = ("success", "failure", "cancelled", "pending")


def _positive_int(value, field):
    if type(value) is not int or value < 1:
        raise ValueError(f"invalid {field}")


def _validate(record):
    if record.get("schema") != INPUT or record.get("authority_transfer") is not False:
        raise ValueError("invalid input schema or authority boundary")
    observations = record.get("observations")
    if not isinstance(observations, list) or len(observations) < 2:
        raise ValueError("at least two revision observations required")
    fingerprints = record.get("fingerprints")
    if not isinstance(fingerprints, list) or len(set(fingerprints)) != len(fingerprints) or not fingerprints:
        raise ValueError("unique fixed root fingerprint population required")
    if any(not isinstance(f, str) or not f.strip() for f in fingerprints):
        raise ValueError("invalid fingerprint")
    for i, wave in enumerate(observations):
        if wave.get("revision") != i or wave.get("source_repo") != "GBOGEB/CODEX":
            raise ValueError("revision order or source repository changed")
        if not HEX_SHA.fullmatch(wave.get("head_sha", "")):
            raise ValueError("exact 40-character source SHA required")
        if i and observations[i - 1]["head_sha"] == wave["head_sha"]:
            raise ValueError("repeated SHA is not an independent revision")
        counts = wave.get("workflow_counts")
        if not isinstance(counts, dict) or set(counts) != set(COUNT_FIELDS):
            raise ValueError("workflow count contract")
        if any(type(v) is not int or v < 0 for v in counts.values()):
            raise ValueError("unknown cannot be encoded as zero workflow count")
        if sum(counts.values()) == 0:
            raise ValueError("zero-workflow denominator")
        roots = wave.get("root_observations")
        if not isinstance(roots, dict) or set(roots) != set(fingerprints):
            raise ValueError("fixed root population changed")
        for key, detail in roots.items():
            if detail.get("state") not in STATES:
                raise ValueError("invalid root state")
            if detail.get("fingerprint") != key:
                raise ValueError("root identity not stable")
            if detail["state"] == "UNKNOWN":
                if detail.get("run_id") is not None or detail.get("job_id") is not None:
                    raise ValueError("unknown root cannot carry fabricated run/job")
            else:
                _positive_int(detail.get("run_id"), "run ID")
                _positive_int(detail.get("job_id"), "job ID")
                if detail.get("evidence_class") != "GITHUB_NATIVE_JOB_STATUS":
                    raise ValueError("root outcome requires native job status evidence")
                if detail.get("archive_bytes_verified") is not False:
                    raise ValueError("metadata is not archive-byte proof")
    if record.get("admission") != "HOLD" or record.get("qps_disposition") != "DEFER":
        raise ValueError("no automatic admission or QPS acceptance")
    if record.get("comparability") != {"same_fingerprints": True, "same_job_predicates": True}:
        raise ValueError("comparable root predicates must be explicitly affirmed")


def _pct(num, den):
    return round(100 * num / den, 4)


def rollup(record):
    _validate(record)
    observations = record["observations"]
    fixed = record["fingerprints"]
    waves = []
    for wave in observations:
        cnt = wave["workflow_counts"]
        n = sum(cnt.values())
        roots = wave["root_observations"]
        waves.append({
            "revision": wave["revision"],
            "label": wave["label"],
            "source_repo": wave["source_repo"],
            "head_sha": wave["head_sha"],
            "pr_number": wave["pr_number"],
            "workflow_denominator": n,
            "workflow_success": cnt["success"],
            "workflow_failure": cnt["failure"],
            "workflow_cancelled": cnt["cancelled"],
            "workflow_pending": cnt["pending"],
            "workflow_pass_pct_descriptive_only": _pct(cnt["success"], n),
            "comparable_workflow_pass_gain_pp": None,
            "root_observed": sum(roots[k]["state"] != "UNKNOWN" for k in fixed),
            "root_pass": sum(roots[k]["state"] == "PASS" for k in fixed),
            "root_fail": sum(roots[k]["state"] == "FAIL" for k in fixed),
            "root_unknown": sum(roots[k]["state"] == "UNKNOWN" for k in fixed),
            "root_population": len(fixed),
        })
    before = observations[-2]["root_observations"]
    after = observations[-1]["root_observations"]
    transitions = []
    resolved = reopened = comparable = 0
    for key in fixed:
        b, a = before[key], after[key]
        ok = b["state"] != "UNKNOWN" and a["state"] != "UNKNOWN"
        if ok:
            comparable += 1
        one = ok and b["state"] == "FAIL" and a["state"] == "PASS"
        two = ok and b["state"] == "PASS" and a["state"] == "FAIL"
        resolved += one
        reopened += two
        transitions.append({
            "fingerprint": key, "before": b["state"], "after": a["state"],
            "comparable": ok, "verified_first_red_recovered_on_pr_head": one,
            "reopened_on_pr_head": two,
            "before_job_id": b.get("job_id"), "after_job_id": a.get("job_id"),
            "root_id": None,
            "global_causal_root_closed": None,
        })
    return {
        "schema": SCHEMA, "authority_transfer": False,
        "source_scope": record["cohort"], "root_population": fixed,
        "wave_clock": "IMMUTABLE_GIT_REVISION_ORDER_NOT_WALL_TIME",
        "waves": waves,
        "last_comparison": {
            "from_head_sha": observations[-2]["head_sha"],
            "to_head_sha": observations[-1]["head_sha"],
            "root_predicates_comparable": comparable,
            "root_fingerprint_population": len(fixed),
            "repaired_first_reds_on_pr_head": resolved,
            "reopened_first_reds_on_pr_head": reopened,
            "transitions": transitions,
            "cross_pr_workflow_success_pp_gain": None,
        },
        "scale": {"fixed_repositories": 1, "fleet_coverage_gain": None,
                  "real_workers_launched": None,
                  "native_LLDB_sessions": None,
                  "LDAB_debug_receipts": None,
                  "four_hop_evidence_completion": None},
        "methods": {
            "mip_phase": "MEASURE_ANALYZE_IMPROVE_DONE_CONTROL_HOLD",
            "dmaic_control_stable": None,
            "selected_3p_adapter": "3PC_CANDIDATE_PENDING_ADMISSION",
            "pca_eligible": False, "pca_reason": "NO_INDEPENDENT_MULTIVARIATE_TRIAL_POPULATION",
            "bradley_terry_eligible": False,
            "bradley_terry_reason": "NO_RANDOMIZED_PAIRED_TRIALS",
            "rex_retrospective": "PR_HEAD_FIRST_RED_PREVENTION_CANDIDATE",
            "rolling_n_plus_2_forecast": None,
        },
        "independent_approved_review": False,
        "effective_main_branch_protection": False,
        "governed_merge_admitted": False,
        "qps_disposition": "DEFER",
        "merge_authorized": False,
        "global_root_closure": None,
        "coverage_gain_pp_fleetwide": None,
    }


def emit(report, out):
    out.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(report, sort_keys=True, indent=2) + "\n").encode()
    digest = hashlib.sha256(raw).hexdigest()
    (out / "recovery_wave.json").write_bytes(raw)
    (out / "recovery_wave.sha256").write_text(digest + "\n", encoding="ascii")
    lines = [
        "# CODE PURPLE root recovery: revision pulses", "",
        "| Revision | PR | Terminal workflow PASS | Failed | Cancelled | Attributed roots PASS |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for w in report["waves"]:
        lines.append(f"| {w['label']} | {w['pr_number']} | {w['workflow_success']}/{w['workflow_denominator']} | "
                     f"{w['workflow_failure']} | {w['workflow_cancelled']} | "
                     f"{w['root_pass']}/{w['root_population']} |")
    lines.extend(["", "Workflow denominators differ: percentage-point deltas are UNKNOWN.",
                  "Root comparison: " + str(report["last_comparison"]["repaired_first_reds_on_pr_head"]) +
                  " first-red recoveries on candidate head; global causal root closure UNKNOWN.",
                  "Fleet coverage, independent review, effective protection and QPS admission: HOLD/UNKNOWN.",
                  "No PCA or Bradley-Terry inference is supported.",
                  "SHA-256: " + digest, ""])
    (out / "recovery_wave.md").write_text("\n".join(lines), encoding="utf-8")
    return digest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = rollup(json.loads(args.input.read_text()))
    emit(report, args.out)
    print(json.dumps({"pulse_count": len(report["waves"]),
                      "source_root_recoveries": report["last_comparison"]["repaired_first_reds_on_pr_head"],
                      "merge_authorized": False}))


if __name__ == "__main__":
    main()
