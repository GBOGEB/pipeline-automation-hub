NEXT_AGENT_INSTRUCTION

directive_type: agent_instruction
execution_mode: sequential
strict_mode: true

project: QPS TRIAGE / MissionControl
primary_repository: GBOGEB/cryoplant-project
primary_controller: GBOGEB/cryoplant-project#481
runtime_gate: GBOGEB/cryoplant-project#923
fleet_controls:
  - GBOGEB/pipeline-automation-hub#372
  - GBOGEB/pipeline-automation-hub#76
  - GBOGEB/pipeline-automation-hub#85

EXECUTION_WAVE_TYPE = "PARTIAL"
FINAL_CONTROL_STATE = "LOCAL_ZERO_ROOT_EXTERNAL_RETURN_FRONTIER"

EXACT_STARTING_LINE:
START HERE: Refresh all seven issue-bearing repository heads and confirm no newer active PR or authoritative source/owner/private return supersedes this handover. Serialized state is 94 open issues / 0 open PRs; cryoplant is 55/55 classified with BDQ4=0; CODEX is 4 open control/external-gate items. Do not reopen cryoplant#1617 or #1635 without a new exact current-code first-red.

SERIALIZED_HEADS:
- cryoplant-project: f6cc2833400011fe2838fbec3234e33a0b1c8279
- pipeline-automation-hub: 11339eab9f002df6b02e63ca024dcca772a4ead9
- ABACUS: b590334137d0878ff9ee9dc5cb0f62e56468825d
- CODEX: 12f177ce006f48216e1e3a8fcf61df8eac5a53f6
- GEMINI: 949f03c22ec3fada0cbf7c18a3bf56ded5f74fc7
- gg_MATH: 2b27f4a6d70a11324d9a7c81d9c88995888b3d74
- document-organization-system: 3c57b9ed674f50af7650ba9aa306d6b182caee28

FLEET_CENSUS:
- cryoplant-project: 55 open / 0 PR
- pipeline-automation-hub: 19 / 0
- ABACUS: 12 / 0
- CODEX: 4 / 0
- GEMINI: 2 / 0
- gg_MATH: 1 / 0
- document-organization-system: 1 / 0
- TOTAL: 94 open / 0 PR

3PR_FINAL:
- QPS child #1663 head ffe279cf2483c94e208b37ae11264bbdca293f8e merge 9f6b38c951d25e09eca5c6f90bc0d086ba86e2b8, review clean.
- Independent executable proof Q_engineering_tools#101 head 8060cd53e266d6544305fe93978edb415716c29f, run 35738152179 / job 106780614008 SUCCESS; artifact 10698440724; sha256 9728770ca9e6d6025df9fd322c99a79aec62f3ab7dd6ca5985db936db9cb5b61.
- CODEX KEB #828 merge 923e4b9023143724912e7790bcd70719a58c44c5, exact-head review clean, W003/Runtime Federation/Validate Federation/qps-canonicalization PASS.
- ABACUS DOW #1357 merge 877cabc47169fd78f2ae81bbc857fbab33aded02, exact-head review clean, core pointer validation checks PASS.

MIP_FINAL:
- Modernize PASS.
- Innovate PASS.
- Perpetuate PASS for repository-local semantic/proof control.
- cryoplant#1617 CLOSED.
- cryoplant#1635 CLOSED.
- cryoplant queue 55/55, unclassified=0, multi_lane=0, BDQ4=0.
- authority_transfer=false.
- formal_credit_delta=0.
- physical_conversion_credit=0.
- runtime_GOLD=WITHHELD_ISSUE_923.

CODEX_PROOF_CLOSE:
- #811 CLOSED after run 35733656932 / job 106765263132 SUCCESS, raw JSON + SARIF + artifact + publication PASS.
- #812 CLOSED after run 35734083493 / job 106766705878 SUCCESS, deterministic docs + stable branch PASS, owner PR-policy denial non-failing, no command-substitution noise.
- CODEX remaining: #319/#324 CONTROL; #500/#753 EXTERNAL_GATE.

NEXT_PRODUCTIVE_FRONTIER:
1. #923 owner/private runner admission return.
2. #663 W57 real HEPAK/Line-B/B-flow/thermal/PLOC/CC source packet.
3. #1186 W191 real Windows/OneDrive Master_Input return.
4. #1593 LOOP/QCELL peer/owner decision return.
5. CODEX #500 production ZERO_DELTA return.
6. CODEX #753 owner Pages source configuration return.
7. GEMINI #12 external GCP configuration return.
8. GEMINI #16 landing-zone successor bundle/checksum/receipt return.

STOP_RULE:
Do not create repo-local framework/code work merely to consume WIP. Re-enter only on a genuine named return or a fresh reproducible current-main first-red. Reuse the existing causal root; open one bounded repair; require exact-head review plus executable proof; recensus after disposition.

END_NEXT_AGENT_INSTRUCTION
