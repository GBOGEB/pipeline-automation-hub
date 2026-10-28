# W380 P2 — Finite twelve-topic-ID train, four planning waves

Source-safe additive development on W378 P1 (six topics and two serial waves). Source is the canonical W377 immutable packet exchange, graph is W378, seven-lane lifecycle is W379; this module only composes their readonly plans.

## Train (SIPOC / DAG)
Supplier: source-owning repositories and their frozen W377 packets.
Input: two independently validated W378 P1 six-topic plans.
Process: P1 plan batch 1 -> pause/reconcile -> P1 plan batch 2 -> pause/reconcile -> gate -> NEXT pulse.
Output: deterministic chained partition receipts; DAG Mermaid; SIPOC JSON; SHA256 manifest.
Customers: existing source owners, native CI, Mission Control and reviewer.

This is not a runner launcher: no cron, no source mutation, no open/closed status, no engineering acceptance, no credential or ACK readback.

## Synthetic demonstration (strictly no live coverage)
The CLI --demo-seed-p1 derives a synthetic second partition by re-keying packet topic IDs with w380. Prefix and re-digesting with the **existing W377 creator**. The underlying source/scope evidence hashes, repo heads and historic items remain unchanged. It produces 12 distinct declared topic IDs and **only six distinct underlying source identity fingerprints**. The second partition contains no copied BD targets. These numbers prove parsing, source-disjoint logical routing and fan-in identity guards; they do not prove 12 independent source scans or any real work performed.

## Gates / traceability
- Max two declared reader slots; 1–4 P1 partitions; goal 6..24 bounded.
- Each inner P1 must pass its existing 3-topic wave validations and graph identity.
- Cross-partition repeated topic IDs and duplicate BD targets fail closed.
- Full immutable previous-receipt chain, no same-pulse feedback cycle.
- If declared goal unmet, stop PLAN_EXHAUSTED. If reached, still stop MISSING_NATIVE_QUEUE_AND_CONTROLLER_ACK.
- Native queue p95, actual worker minutes, producer/recipient ACK, saved scans and independent accepted roots remain UNKNOWN until genuine source-owned readback.
- Zero source writes, new cron jobs, mission crew dispatches or merges.

Exact-head Python 3.11/3.12, optimized -O negative tests, >=85% branch-aware combined coverage of the new module and SHA256 artifact verification are the local pilot gates. No LIVE/P2 adoption without independent review, signed source receipts, worker lease proof, controller-attested ACK, queue baseline, required status and owner permissions.

## Commands
Set PYTHONPATH=tools/metric-atlas.

python -m unittest discover -s tools/metric-atlas/tests -p test_topic_wave_train.py -v
python -O -m unittest discover -s tools/metric-atlas/tests -p test_topic_wave_train.py -v
python -m metric_atlas.topic_wave_train --demo-seed-p1 tools/metric-atlas/tests/pilot_6topic.json --out /tmp/w380

## Dependencies
#993 integration -> #999 temporal ACK fix -> this P2 draft. Distinct SIPOC/DAG lane graph work runs on a separate branch with independent path ownership. All merge/production gates remain HOLD.
