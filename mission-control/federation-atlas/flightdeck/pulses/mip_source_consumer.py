"""Read-only ABACUS MIP v2 consumer; never creates a competing source of truth.

Input is an externally acquired exact-head ABACUS producer projection plus
an explicit source identity envelope. No GitHub API call or artifact download
is performed here; byte authentication remains separately governed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path

SOURCE_SCHEMA = "abacus.mip.ci-wave-telemetry.v2"
OUTPUT_SCHEMA = "code-purple.mission-control.mip-consumer.v1"
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SHA64 = re.compile(r"[0-9a-f]{64}\Z")
OUTCOMES = ("success", "failure", "neutral", "cancelled", "skipped",
            "timed_out", "action_required", "stale", "startup_failure")
CONFIDENCE = (90, 95, 99)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def number(value):
    return type(value) is int and value >= 0


def first_red_digest(row):
    """Match the canonical ABACUS workflow/job/step source signature."""
    keys = ("workflow_path", "job_name", "step_name")
    require(isinstance(row, dict)
            and all(isinstance(row.get(k), str) and row[k].strip()
                    for k in keys)
            and type(row.get("step_number")) is int
            and row["step_number"] > 0,
            "invalid native first-red semantic identity")
    semantic = {k: row[k] for k in keys}
    semantic["step_number"] = row["step_number"]
    return hashlib.sha256(json.dumps(
        semantic, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()


def consume(envelope, producer):
    """Deterministic projection; descriptive only, no pseudo-independent CI."""
    require(isinstance(envelope, dict) and isinstance(producer, dict),
            "two explicit input documents required")
    require(envelope.get("schema") == "code-purple.mip-input-binding.v1",
            "binding schema mismatch")
    require(envelope.get("repository") == "GBOGEB/ABACUS",
            "unexpected source repository")
    sha = envelope.get("head_sha")
    require(isinstance(sha, str) and SHA40.fullmatch(sha),
            "exact source head required")
    digest = envelope.get("producer_sha256")
    require(isinstance(digest, str) and SHA64.fullmatch(digest),
            "canonical producer artifact digest required")
    require(envelope.get("producer_path") == "tools/mip_ci_wave_telemetry.py",
            "canonical producer path required")
    require(envelope.get("authority_transfer") is False
            and envelope.get("artifact_bytes_authenticated") is False,
            "cannot promote authority or claim byte authentication")
    require(producer.get("schema") == SOURCE_SCHEMA
            and producer.get("repository") == "GBOGEB/ABACUS"
            and producer.get("source_sha") == sha,
            "producer schema/source mismatch")
    require(producer.get("merge_authorized") is False
            and producer.get("authority_transfer") is False
            and producer.get("security_waiver") is False,
            "producer cannot authorize governance")
    counts = producer.get("workflow_terminal_by_outcome")
    require(isinstance(counts, dict) and set(counts) == set(OUTCOMES)
            and all(number(v) for v in counts.values()),
            "complete terminal outcome census required")
    pending = producer.get("workflow_nonterminal")
    unclassified = producer.get("workflow_unclassified")
    total = producer.get("workflow_records_observed")
    require(all(number(v) for v in (pending, unclassified, total))
            and sum(counts.values()) + pending + unclassified == total,
            "workflow denominator inconsistent")
    queue = producer.get("queue_source_counts")
    require(isinstance(queue, dict) and set(queue) == {
        "job_created_at", "workflow_run_created_at_fallback"
    } and all(number(v) for v in queue.values())
            and number(producer.get("queue_samples"))
            and sum(queue.values()) == producer["queue_samples"],
            "queue provenance denominator inconsistent")
    samples = producer["queue_samples"]
    p95 = producer.get("queue_seconds_p95")
    require((p95 is None if samples == 0 else
             type(p95) in (int, float) and math.isfinite(p95) and p95 >= 0),
            "queue p95 must match nonempty measured sample basis")
    signatures = producer.get("first_red_signatures")
    require(isinstance(signatures, list), "missing first-red signatures")
    require(number(producer.get("first_red_unique_signatures"))
            and len(signatures) == producer["first_red_unique_signatures"],
            "first-red signature denominator inconsistent")
    seen = set()
    repeated = 0
    manifested = 0
    for row in signatures:
        require(isinstance(row, dict)
                and isinstance(row.get("fingerprint"), str)
                and SHA64.fullmatch(row["fingerprint"])
                and row["fingerprint"] not in seen
                and row["fingerprint"] == first_red_digest(row)
                and number(row.get("manifestations"))
                and row["manifestations"] > 0,
                "invalid or duplicated first-red group")
        seen.add(row["fingerprint"])
        manifested += row["manifestations"]
        repeated += row["manifestations"] > 1
    events = producer.get("first_red_manifestations")
    require(isinstance(events, list) and manifested == len(events),
            "first-red manifestation count mismatch")
    identities = set()
    event_counts = {key: 0 for key in seen}
    for event in events:
        require(isinstance(event, dict)
                and event.get("fingerprint") in seen
                and event["fingerprint"] == first_red_digest(event)
                and all(type(event.get(k)) is int and event[k] > 0
                        for k in ("run_id", "run_attempt", "job_id")),
                "first-red manifestation source identity invalid")
        identity = (event["run_id"], event["run_attempt"], event["job_id"])
        require(identity not in identities, "duplicate native first-red job")
        identities.add(identity)
        event_counts[event["fingerprint"]] += 1
    require(all(event_counts[row["fingerprint"]] == row["manifestations"]
                for row in signatures)
            and repeated == producer.get("first_red_repeated_signatures"),
            "first-red signature/event totals inconsistent")

    job_outcomes = producer.get("terminal_by_outcome")
    require(isinstance(job_outcomes, dict)
            and set(job_outcomes) == set(OUTCOMES)
            and all(number(v) for v in job_outcomes.values())
            and number(producer.get("jobs_observed"))
            and number(producer.get("nonterminal"))
            and sum(job_outcomes.values()) + producer["nonterminal"]
            == producer["jobs_observed"], "native job denominator inconsistent")
    red_jobs = sum(job_outcomes[key] for key in (
        "failure", "timed_out", "startup_failure"))
    unattributed = producer.get("red_jobs_without_attributed_first_step")
    require(number(unattributed) and red_jobs == manifested + unattributed,
            "red job first-step attribution denominator inconsistent")
    require(producer.get("first_red_causal_roots_verified") is None
            and producer.get("independent_process_observations") is None,
            "causal/independent claims cannot be imported")
    stats = {
        "workflow_terminal_n": sum(counts.values()),
        "workflow_total_n": total,
        "workflow_success_n": counts["success"],
        "workflow_failure_n": counts["failure"],
        "workflow_pending_n": pending + unclassified,
        "workflow_success_fraction_descriptive": (
            round(counts["success"] / total, 9) if total and not (
                pending or unclassified) else None
        ),
        "first_red_unique_signatures": len(signatures),
        "first_red_repeated_signatures": repeated,
        "first_red_manifestations": manifested,
        "red_jobs_total": red_jobs,
        "red_jobs_unattributed": unattributed,
        "first_red_attribution_fraction": (
            round(manifested / red_jobs, 9) if red_jobs else None
        ),
        "first_red_signature_compression_fraction": (
            round(1 - len(signatures) / manifested, 9) if manifested else None
        ),
        "job_total_n": producer["jobs_observed"],
        "queue_samples": producer["queue_samples"],
        "queue_native_n": queue["job_created_at"],
        "queue_fallback_n": queue["workflow_run_created_at_fallback"],
        "queue_native_fraction": (
            round(queue["job_created_at"] / samples, 9) if samples else None
        ),
        "queue_p95_seconds_source_reported": producer.get("queue_seconds_p95"),
        "queue_cross_wave_comparable": None,
    }
    return {
        "schema": OUTPUT_SCHEMA,
        "source": {"repository": envelope["repository"], "head_sha": sha,
                   "producer_path": envelope["producer_path"],
                   "producer_sha256_claim": digest,
                   "original_binary_authenticated": False},
        "observed": stats,
        "confidence_intervals": {
            str(level): {"level_percent": level, "estimate": None,
                         "reason": "NO_INDEPENDENT_MATCHED_PROCESS_TRIALS"}
            for level in CONFIDENCE
        },
        "methods": {
            "descriptive": "SUPPORTED_SOURCE_BOUND_PROJECTION",
            "wilson_binomial": "HOLD_INDEPENDENCE_AND_COHORT",
            "pca": "HOLD_N_INDEPENDENT_AND_STABLE_COVARIANCE",
            "bradley_terry": "HOLD_CONNECTED_PAIRED_COMPARISONS",
            "anova": "HOLD_REPLICATES_RESIDUAL_AND_GROUP_DESIGN",
            "manova": "HOLD_MULTIVARIATE_REPLICATES_AND_RANK",
            "canonical_math_provider": "GBOGEB/gg_MATH",
            "temporal_pca_alignment": "NOT_APPLICABLE_UNQUALIFIED",
        },
        "first_red_groups": sorted(signatures, key=lambda x: x["fingerprint"]),
        "root_register_created": False,
        "html_truth_store_created": False,
        "accepted_bd_root_closures": None,
        "qps_engineering_acceptance": "DEFER",
        "native_four_hop": "UNKNOWN",
        "authority_transfer": False,
        "merge_authorized": False,
        "admission": "HOLD",
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--binding", type=Path, required=True)
    parser.add_argument("--producer", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    for p in (args.binding, args.producer):
        require(p.is_file() and not p.is_symlink()
                and 0 < p.stat().st_size <= 5_000_000,
                "missing, symlinked or oversized input")
    require(args.out.resolve() not in (
        args.binding.resolve(), args.producer.resolve()),
        "output aliases input")
    raw = args.producer.read_bytes()
    binding = json.loads(args.binding.read_text(encoding="utf-8"))
    require(hashlib.sha256(raw).hexdigest() == binding.get("producer_sha256"),
            "producer bytes do not match binding digest")
    projected = consume(binding, json.loads(raw))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(projected, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
