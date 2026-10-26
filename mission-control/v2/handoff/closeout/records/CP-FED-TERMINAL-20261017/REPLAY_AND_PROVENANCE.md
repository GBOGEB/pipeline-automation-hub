# Provenance, rebuild and known restrictions

- Parent MC master: `383961ca0588830ef3a81b8c3713e64dd6a5957b`; observed source queue Git blob: `bf3d6d25e87ae47d6629e97b7cacb112994483e8`; SHA256 of queue raw UTF8: `0b4b2606d556878c40af1488d7fba5eaba3cea601177704486171fbd2a24adee`.
- Existing canonical implementation (unchanged): `mission-control/v2/handoff/closeout/cp_close.py`, `CP_CLOSE_GITHUB_v1.json`, `cp-close-github-qa.yml`.
- The nine handover files in this draft are source-bound handover **projections**, not independently native-certified output. Their SHA256 manifest was generated for this proposal. **Do not mark generator parity PASS before running the canonical Python replay**. Such replay may require regenerating the nine files for exact byte conformity.
- Intake: `mission-control/v2/handoff/closeout/intakes/CP-FED-TERMINAL-20261017.json`.
- In an authorized local checkout of this PR, first run `python mission-control/v2/handoff/closeout/cp_close.py --intake mission-control/v2/handoff/closeout/intakes/CP-FED-TERMINAL-20261017.json --bd mission-control/federation-atlas/CODE_PURPLE_BD_QUEUE_v1.json --out mission-control/v2/handoff/closeout/records/CP-FED-TERMINAL-20261017` to regenerate canonical nine files, then rerun the same command with `--check` and execute existing native test workflow. Record any changed member digests as a new revision. Never mutate canonical BD queue.
- To generate a private offline ZIP use the existing producer `--zip .cp-close-review/CP-FED-TERMINAL-20261017.zip` locally; no archive/ZIP authenticity or original private QPS message bytes is claimed here.
- Native exact-head CI, reviewer approval, main merge, postmerge readback and QPS engineering acceptance remain **HOLD/UNKNOWN**.
