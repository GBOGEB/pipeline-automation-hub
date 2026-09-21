# RESTART DROP-IN — Temporal frontier after short_compute re-earn

Refresh `GBOGEB/pipeline-automation-hub master` first.

Read in order:

1. `TEMPORAL_FRONTIER_CURRENT_v1.json`
2. `TEMPORAL_3PSTAR_MIP_ITERATION_v4.json`
3. `TEMPORAL_SHORT_COMPUTE_REEARN_RECEIPT_20260921_v1.json`
4. `TEMPORAL_SHORT_COMPUTE_REEARN_GATE_v1.json`
5. `TEMPORAL_CONTROL_REGRESSION_v1.json` as history
6. `TEMPORAL_POLICY_CONFIG_v1.json`
7. the 2026-09-21 lossless handover.

Expected state unless a later genuine schedule has changed it:

`CONTROL_3_OF_5_SHORT_COMPUTE_REEARNED_TWO_CLASS_FRONTIER_ACTIVE`

CONTROL:
- cache_artifact_reuse
- short_compute
- validation_bundle

Latest short_compute re-earn proof:
- run `35574196822`
- job `106252442714`
- SHA `aad7c4ee3b464307365d55cb7d30999282b01838`
- artifact `10626843286`
- digest `sha256:5da6859bfcb0fad43c4339dc8ac7795dce052dbd177e6c90eaad04817a222020`
- pooled winner strength 0.7098869126
- direction consistency 0.9523809524
- 21 directional windows
- latest-two agree
- 25 scheduled windows / 10 source SHAs / 519001 s
- runner classes linux+macos+windows
- baseline+held
- REX veto false.

Remaining frontier:
- P0 long_compute_contended
- P1 human_dependency_wait_proxy

Full CONTROL is false. H3 7-day persistence remains not mature at 519001 s.

Only genuine schedule evidence may promote or revoke CONTROL. Preserve authority_transfer=false and formal_credit_delta=0.
