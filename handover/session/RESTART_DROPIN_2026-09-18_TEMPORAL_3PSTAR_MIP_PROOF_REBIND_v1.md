# Temporal 3PSTAR + MIP session restart pointer — superseded

The earlier restart instruction that expected 3/5 CONTROL is superseded.

Restart from the repository-native temporal current pointer:
`mission-control/qps-triage-ultra/crew/measured/frontier/temporal/TEMPORAL_FRONTIER_CURRENT_v1.json`.

Expected current state unless live authority has advanced:
- effective CONTROL: 2/5
- P0 short_compute CONTROL regression
- P1 long_compute regime reversal
- P2 human_dependency_wait_proxy weak/noisy
- short_compute re-earn requires a later genuine schedule receipt passing every frozen gate.

No manual/synthetic/PR/push CONTROL credit. authority_transfer=false.
