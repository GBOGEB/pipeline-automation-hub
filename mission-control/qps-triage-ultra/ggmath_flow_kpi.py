#!/usr/bin/env python3
"""Queueing / flow KPIs over measured runner jobs (GM-I-A pulses, fleet ledger).

Per job: flow efficiency = execute / (queue + execute) and queue/execute ratio.
Per pulse window: a Little's-law consistency field comparing lambda*W with the
time-averaged number-in-system obtained by an independent event sweep over the
measured created/started/completed timestamps.  Both sides are computed from the
same closed window, so agreement is an arithmetic identity
(threshold_kind EXACT_IDENTITY); a residual exposes inconsistent timestamps,
not a queueing-theory finding.  No steady state is claimed and missing values
are never imputed.
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime
from typing import Iterable, Sequence

SCHEMA = "qps-ggmath-flow-kpi/v1"
IDENTITY_TOLERANCE = 1e-9


class FlowHold(ValueError):
    pass


def _epoch(value: str) -> float:
    if not isinstance(value, str) or not value:
        raise FlowHold("DEFER_MISSING_MEASUREMENT_NO_IMPUTATION: timestamp")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise FlowHold(f"DEFER_TIMESTAMP_INVALID: {value}") from exc
    if dt.tzinfo is None:
        raise FlowHold(f"DEFER_TIMESTAMP_INVALID: {value} lacks timezone")
    return dt.timestamp()


def _seconds(value, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or value < 0:
        raise FlowHold(f"DEFER_MISSING_MEASUREMENT_NO_IMPUTATION: {label}")
    return float(value)


def jobs_from_gm_i_a(pulses: dict) -> list[dict]:
    """Normalise GM-I-A multi-clock rows into one job per lane per pulse."""
    if pulses.get("authority_transfer") is not False:
        raise FlowHold("DEFER_AUTHORITY_PROMOTION_REJECTED")
    lanes = sorted(f[: -len("_queue_seconds")] for f in pulses["features"] if f.endswith("_queue_seconds"))
    jobs = []
    for row in pulses["rows"]:
        if row.get("evidence_class") != "MEASURED":
            raise FlowHold(f"DEFER_NON_MEASURED_ROW: {row.get('pulse_id')}")
        for lane in lanes:
            ev = row["evidence"][lane]
            execute = row.get(f"{lane}_execute_seconds")
            jobs.append({
                "window": row["pulse_id"], "lane": lane, "repo": ev["repo"], "run_id": ev["run_id"],
                "job_id": ev["job_id"], "created": ev["created_at"], "started": ev["started_at"],
                "completed": ev["completed_at"], "queue_seconds": row[f"{lane}_queue_seconds"],
                "execute_seconds": execute,
                "execute_source": "MEASURED_FEATURE" if execute is not None else "TIMESTAMP_DERIVED",
            })
    return jobs


def jobs_from_fleet_ledger(ledger: dict) -> list[dict]:
    """Normalise completed iterations of the QPS expedition ledger; lanes are comparability groups.

    Iterations without a completed runner job (QUEUED, local/static outcomes) are
    not jobs; they are listed by ``excluded_from_fleet_ledger``, never imputed.
    """
    jobs = []
    for it in ledger["iterations"]:
        if not _completed_runner_job(it):
            continue
        jobs.append({
            "window": "FLEET_LEDGER", "lane": it["comparability_group"], "repo": it["repo"],
            "run_id": it["run_id"], "job_id": it["job_id"], "created": it["created_utc"],
            "started": it["started_utc"], "completed": it["completed_utc"],
            "queue_seconds": it["queue_seconds"], "execute_seconds": it["runtime_seconds"],
            "execute_source": "MEASURED_FEATURE",
        })
    return jobs


def _completed_runner_job(it: dict) -> bool:
    return it.get("result") == "SUCCESS" and all(
        it.get(k) is not None for k in ("created_utc", "started_utc", "completed_utc", "runner_id"))


def excluded_from_fleet_ledger(ledger: dict) -> list[dict]:
    return [{"mission_id": it.get("mission_id"), "result": it.get("result"),
             "reason": "NO_COMPLETED_RUNNER_JOB_NOT_IMPUTED"}
            for it in ledger["iterations"] if not _completed_runner_job(it)]


def _job_kpi(job: dict) -> dict:
    created, started, completed = (_epoch(job[k]) for k in ("created", "started", "completed"))
    if not created <= started <= completed:
        raise FlowHold(f"DEFER_TIMESTAMP_ORDER_INVALID: job {job['job_id']}")
    queue = _seconds(job["queue_seconds"], f"{job['job_id']} queue")
    ts_queue, ts_execute = started - created, completed - started
    execute = ts_execute if job["execute_seconds"] is None else _seconds(job["execute_seconds"], f"{job['job_id']} execute")
    total = queue + execute
    return {
        "window": job["window"], "lane": job["lane"], "repo": job["repo"], "run_id": job["run_id"],
        "job_id": job["job_id"], "queue_seconds": queue, "execute_seconds": execute,
        "execute_source": job["execute_source"],
        "flow_efficiency": None if total == 0 else execute / total,
        "queue_execute_ratio": None if execute == 0 else queue / execute,
        "timestamp_queue_seconds": ts_queue, "timestamp_execute_seconds": ts_execute,
        "feature_timestamp_reconciled": abs(ts_queue - queue) < 1.0 and abs(ts_execute - execute) < 1.0,
        "_interval": (created, started, completed),
    }


def _occupancy_integral(intervals: Sequence[tuple[float, float]]) -> float:
    """Integrate number-in-state over time by sweeping +1/-1 events."""
    events = sorted([(a, 1) for a, _ in intervals] + [(b, -1) for _, b in intervals])
    area, level, last = 0.0, 0, None
    for t, step in events:
        if last is not None:
            area += level * (t - last)
        level += step
        last = t
    return area


def littles_law(kpis: Sequence[dict]) -> dict:
    """Closed-window Little's-law consistency for one window of completed jobs."""
    if len(kpis) < 2:
        return {"status": "DEFER_INSUFFICIENT_JOBS", "jobs": len(kpis)}
    start = min(k["_interval"][0] for k in kpis)
    end = max(k["_interval"][2] for k in kpis)
    horizon = end - start
    if horizon <= 0:
        return {"status": "DEFER_ZERO_WINDOW", "jobs": len(kpis)}
    lam = len(kpis) / horizon
    sojourn = [k["_interval"][2] - k["_interval"][0] for k in kpis]
    waits = [k["_interval"][1] - k["_interval"][0] for k in kpis]
    w, wq = sum(sojourn) / len(kpis), sum(waits) / len(kpis)
    l_sweep = _occupancy_integral([(k["_interval"][0], k["_interval"][2]) for k in kpis]) / horizon
    lq_sweep = _occupancy_integral([(k["_interval"][0], k["_interval"][1]) for k in kpis]) / horizon
    residual = abs(l_sweep - lam * w) / (lam * w) if lam * w else None
    residual_q = abs(lq_sweep - lam * wq) / (lam * wq) if lam * wq else None
    consistent = residual is not None and residual <= IDENTITY_TOLERANCE and (
        residual_q is None or residual_q <= IDENTITY_TOLERANCE)
    return {
        "status": "PASS_LITTLES_LAW_CONSISTENT" if consistent else "DEFER_LITTLES_LAW_INCONSISTENT",
        "jobs": len(kpis), "window_seconds": horizon, "arrival_rate_per_second": lam,
        "mean_sojourn_seconds": w, "mean_queue_wait_seconds": wq,
        "L_time_average_sweep": l_sweep, "lambda_times_W": lam * w, "relative_residual": residual,
        "Lq_time_average_sweep": lq_sweep, "lambda_times_Wq": lam * wq, "relative_residual_queue": residual_q,
        "tolerance": IDENTITY_TOLERANCE, "steady_state_claimed": False,
        "interpretation": "closed-window accounting identity over measured timestamps; not a stationary queue model",
    }


def flow_kpi(jobs: Iterable[dict], *, source: str, source_sha: str | None,
             excluded: Sequence[dict] = ()) -> dict:
    """Flow KPIs per job, pooled per lane and per window, with Little's-law consistency."""
    try:
        kpis = [_job_kpi(j) for j in jobs]
    except (FlowHold, KeyError) as exc:
        return {"schema": SCHEMA, "adapter": "flow_kpi", "status": str(exc).split(":")[0] if isinstance(exc, FlowHold)
                else "DEFER_MISSING_MEASUREMENT_NO_IMPUTATION", "detail": str(exc), "source": source,
                "authority_transfer": False, "engineering_acceptance": False}
    if not kpis:
        return {"schema": SCHEMA, "adapter": "flow_kpi", "status": "DEFER_NO_MEASURED_JOBS", "source": source,
                "authority_transfer": False, "engineering_acceptance": False}
    lanes, windows = defaultdict(list), defaultdict(list)
    for k in kpis:
        lanes[k["lane"]].append(k)
        windows[k["window"]].append(k)
    pooled = {}
    for lane, rows in sorted(lanes.items()):
        q, e = sum(r["queue_seconds"] for r in rows), sum(r["execute_seconds"] for r in rows)
        pooled[lane] = {"jobs": len(rows), "queue_seconds": q, "execute_seconds": e,
                        "flow_efficiency": None if q + e == 0 else e / (q + e),
                        "queue_execute_ratio": None if e == 0 else q / e}
    total_q = sum(k["queue_seconds"] for k in kpis)
    total_e = sum(k["execute_seconds"] for k in kpis)
    little = {w: littles_law(rows) for w, rows in sorted(windows.items())}
    reconciled = all(k["feature_timestamp_reconciled"] for k in kpis)
    status = "PASS_FLOW_KPI" if reconciled and all(
        v["status"] != "DEFER_LITTLES_LAW_INCONSISTENT" for v in little.values()) else "DEFER_FLOW_KPI_INCONSISTENT"
    return {
        "schema": SCHEMA, "adapter": "flow_kpi", "status": status, "source": source, "source_sha": source_sha,
        "threshold_kind": {"flow_efficiency": "EXACT_IDENTITY", "queue_execute_ratio": "EXACT_IDENTITY",
                           "littles_law_consistency": "EXACT_IDENTITY"},
        "jobs": [{k: v for k, v in row.items() if not k.startswith("_")} for row in kpis],
        "lanes": pooled,
        "fleet": {"queue_seconds": total_q, "execute_seconds": total_e,
                  "flow_efficiency": None if total_q + total_e == 0 else total_e / (total_q + total_e),
                  "queue_execute_ratio": None if total_e == 0 else total_q / total_e,
                  "dominant_component": "QUEUE_ADMISSION" if total_q > total_e else "EXECUTION"},
        "littles_law_consistency": little,
        "feature_timestamp_reconciled": reconciled,
        "excluded": list(excluded),
        "authority_transfer": False, "engineering_acceptance": False,
    }
