# W5 — Operational GitHub-first lossless telemetry

**Extends, never replaces:** [CP.CLOSE W4 canonical handover](../closeout/records/CP-FED-CENSUS-W4-20261018/START_HERE.md), [CP.RESUME contract](../CP_HANDOFF_RESUME_V1.json), [CENSUS_PULL routing](../CENSUS_PULL_ROUTING_V2.md) and canonical [BD queue](../../../federation-atlas/CODE_PURPLE_BD_QUEUE_v1.json).

- [Handover, actual N−1→N metrics, Mermaid and owner TODO](HANDOVER_20261018.md)
- [Frozen public-safe four-repo GitHub telemetry](W5_CENSUS_TELEMETRY_20261018.json)
- [Typed 25-node/33-edge dependency, scheduler and 5-row SIPOC](W5_FEDERATION_DAG_20261018.json)
- [Lossless CP.RESUME next-chat drop-in](NEXT_CHAT_DROPIN_20261018.md)

Validate with native stdlib tests:
~~~bash
python -m unittest discover -s mission-control/v2/handoff/w5 -p 'test_w5_handover.py' -v
python mission-control/v2/handoff/closeout/cp_close.py --intake mission-control/v2/handoff/closeout/intakes/CP-FED-CENSUS-W4-20261018.json --bd mission-control/federation-atlas/CODE_PURPLE_BD_QUEUE_v1.json --out mission-control/v2/handoff/closeout/records/CP-FED-CENSUS-W4-20261018 --check
~~~

Recorded source SHA/census is date-only non-atomic and historical on restart. The W5 workflow must prove the exact PR source head and publish SHA-256 file receipts; static proof cannot approve a merge, create an engineering closure, or dispatch a remote worker.

## Post-capture evidence, separate source populations

After the frozen W5 readback, [N+1 exact-SHA native evidence](POST_CAPTURE_NATIVE_PULSE_20261018.md) and [machine metrics](W5_POST_CAPTURE_NATIVE_PULSE_20261018.json) proved B0 and coverage on earlier ABACUS main SHA 97a8… (4,168 PASS/2 SKIP, 35.00% statements and 30.33% branches), then identified G3CS collection first-red on newer 1122… main. Do not overwrite prior snapshot or claim the two coverage populations are matched.
