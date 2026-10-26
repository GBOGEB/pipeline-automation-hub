"""Isolated bounded asyncio queue/back-pressure preflight, never real-system load.

Synthetic observations qualify the local GOGREEN probe only, not any child repo.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import time
from pathlib import Path


def require_int(n, low, high, name):
    if type(n) is not int or not low <= n <= high:
        raise ValueError(f"{name} outside safe synthetic test envelope [{low},{high}]")


def percentile_ns(values, percentile):
    if not values:
        return None
    return sorted(values)[min(len(values)-1, (len(values)*percentile + 99)//100 - 1)]


async def one_cycle(total: int, queue_depth: int, workers: int, inject_failure: int | None):
    queue = asyncio.Queue(maxsize=queue_depth)
    done, errors, wait_ns = [], [], []
    started = time.perf_counter_ns()
    peak_queue, peak_active, active, producer_blocked = 0, 0, 0, 0

    async def producer():
        nonlocal peak_queue, producer_blocked
        for item in range(total):
            if queue.full():
                producer_blocked += 1
            await queue.put((item, time.perf_counter_ns()))
            peak_queue = max(peak_queue, queue.qsize())
        for _ in range(workers):
            await queue.put(None)

    async def worker():
        nonlocal active, peak_active
        while True:
            row = await queue.get()
            if row is None:
                queue.task_done()
                return
            item, enqueued_at_ns = row
            wait_ns.append(max(0, time.perf_counter_ns() - enqueued_at_ns))
            active += 1
            peak_active = max(active, peak_active)
            try:
                await asyncio.sleep(0)  # cooperative scheduling only; no I/O
                if inject_failure is not None and item == inject_failure:
                    errors.append(item)
                else:
                    done.append(item)
            finally:
                active -= 1
                queue.task_done()

    await asyncio.gather(producer(), *(worker() for _ in range(workers)))
    if len(done) + len(errors) != total or len(wait_ns) != total:
        raise AssertionError("lost or duplicated queue items")
    elapsed = max(time.perf_counter_ns() - started, 1)
    return {"processed": len(done), "faults": len(errors), "max_queue": peak_queue,
            "peak_in_flight": peak_active, "producer_block_observations": producer_blocked,
            "processed_digest": hashlib.sha256(",".join(map(str, sorted(done))).encode()).hexdigest(),
            "elapsed_ns": elapsed, "queue_wait_p50_ns": percentile_ns(wait_ns, 50),
            "queue_wait_p95_ns": percentile_ns(wait_ns, 95),
            "synthetic_throughput_tasks_per_s": round(total*1e9/elapsed, 2)}


def run(total=32, queue_depth=4, workers=2, cycles=2, inject_failure=None) -> dict:
    require_int(total, 1, 64, "total")
    require_int(queue_depth, 1, 8, "queue depth")
    require_int(workers, 1, 4, "workers")
    require_int(cycles, 1, 3, "cycles")
    if inject_failure is not None:
        require_int(inject_failure, 0, total - 1, "inject-failure")

    async def bounded():
        return await asyncio.wait_for(
            asyncio.gather(*(one_cycle(total, queue_depth, workers, inject_failure)
                             for _ in range(cycles))), timeout=5)
    trials = asyncio.run(bounded())
    if any(t["max_queue"] > queue_depth or t["peak_in_flight"] > workers for t in trials):
        raise AssertionError("probe exceeded bounded resource envelope")
    expected_faults = cycles if inject_failure is not None else 0
    if sum(t["faults"] for t in trials) != expected_faults:
        raise AssertionError("fault-injection detector failed")
    return {"schema": "gogreen.synthetic-queue.v1", "synthetic": True,
            "evidence_class": "LOCAL_CONTROL_PROBE_NOT_CHILD_RESILIENCE",
            "cycles_same_process": cycles, "independent_trials": None,
            "bounds": {"total_per_cycle": total, "queue_depth": queue_depth, "workers": workers},
            "iterations": trials,
            "outcome": "EXPECTED_FAULT_OBSERVED" if inject_failure is not None else "LOCAL_PROBE_PASS",
            "child_stress_admitted": False, "merge_authorized": False,
            "authority_transfer": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--total", type=int, default=32)
    parser.add_argument("--queue-depth", type=int, default=4)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--cycles", type=int, default=2)
    parser.add_argument("--inject-failure", type=int)
    parser.add_argument("--output", type=Path, required=True)
    a = parser.parse_args()
    result = run(a.total, a.queue_depth, a.workers, a.cycles, a.inject_failure)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"outcome": result["outcome"], "synthetic": True}))


if __name__ == "__main__":
    main()
