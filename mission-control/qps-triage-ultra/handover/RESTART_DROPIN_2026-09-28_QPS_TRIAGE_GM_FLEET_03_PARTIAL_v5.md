# NEXT_AGENT_INSTRUCTION

repository_focus:
  canonical_qps: GBOGEB/cryoplant-project
  missioncontrol: GBOGEB/pipeline-automation-hub
  runtime_analysis: GBOGEB/ABACUS

EXECUTION_WAVE_TYPE: PARTIAL
execution_mode: sequential
strict_mode: true
authority_transfer: false
formal_credit_delta: 0
engineering_credit_delta: 0
global_project_DoV: WITHHELD
runtime_GOLD: WITHHELD

START HERE: Refresh GBOGEB/cryoplant-project main, GBOGEB/pipeline-automation-hub master and GBOGEB/ABACUS main; recensus owner-wide open issues, open PRs and live Actions; read cryoplant-project handover/qps_recursive/GLOB.yaml -> SESSION_CLOSE_CURRENT.yaml -> QTG_CURRENT.yaml before any MissionControl lane; preserve #923 CLOSED_COMPLETED_RUNNER_ADMISSION_RECOVERED and GT_BDQ_0..9 PASS/CLOSED unless contradictory executed evidence appears; preserve global first-red #943 + SELECTED_SAFETY_SOURCE_SET and all higher-priority source/safety/release returns as non-compensating; refresh MissionControl Historian/REX state at current master, then consume only the chronologically first material executed red; do not promote GM-FLEET order 7 / QPS#1111 while canonical QTG preemption remains actionable; keep execution PARTIAL and sequential with authority_transfer=false, formal_credit_delta=0, engineering_credit_delta=0.

Current serialized facts:
- live issue census at closure: 99 open issues / 8 issue-bearing repos
- issue counts: cryoplant-project=50, pipeline-automation-hub=26, ABACUS=14, CODEX=4, GEMINI=2, Q_engineering_tools=1, gg_MATH=1, document-organization-system=1
- owner-wide open PR census: only unrelated GBOGEB/stale#8 (Dependabot lodash)
- MissionControl master at serialization: 49471d43285776ba4df24e644c5c756ab2221c8f
- current-head MissionControl PASS: QPS TRIAGE Federation, Capacity, Ring1, Ring2, F01, Historian, W3-11, W3-13, W3-14, W3-16, GM-FLEET-02B
- current-head MissionControl still executing at serialization: GM-FLEET-03 F03 run 36453292486; aggregate Push-on-master run 36453287823
- current-head Pages PASS
- ABACUS had active/queued CI on recent head a0d153cd08a30ce5777301ec5f54a815f5a780d6; latest head e4f7164e34b050589bd6cf0d9bca052c2ee6376b had no head-bound Actions yet at snapshot
- #502 merged handover v4; #499 merged Historian reconciliation and current master 49471d finalizes its post-merge content receipt
- #498 closed SUPERSEDED; #500 merged bounded mirror fix-forward
- merge-admission recurrence remains explicit REX-CM-005 debt; do not rewrite historical noncompliance as clean
- canonical QPS SESSION_CLOSE_CURRENT still says execution_wave_type=PARTIAL, qps_open_issues=50, #923 closed, GT_BDQ_0..9 PASS/CLOSED, global DoV WITHHELD
- canonical QTG global first-red remains ISSUE_943_AND_SELECTED_SAFETY_SOURCE_SET / HOLD_NONCOMPENSATING_SOURCE_AUTHORITY
- canonical QTG next remains ISSUE_943_PLUS_SELECTED_SAFETY_SOURCE_SET_THEN_SOURCE_PREEMPTION_AND_RELEASE
- formal guards remain engineering=70/90, strict_numerical=4/5, negotiation=0/20, global_project_DoV=WITHHELD, runtime_GOLD=WITHHELD

Uncompleted / re-entry work:
1. Read back F03 run 36453292486 and Push-on-master 36453287823; repair only if an executed material current-master red appears.
2. Refresh current Historian REX-CM-005/006 receipts before admitting any new semantic root.
3. Preserve canonical QPS source/safety/release ordering from QTG_CURRENT; #943 + selected source/safety set preempts MissionControl issue-count pressure.
4. Keep GM-FLEET order 7 / QPS#1111 HELD/UNREAD until canonical QTG permits.
5. Re-census owner-wide issues/PRs/Actions before each new pulse; raw issue count alone never triggers FULL.
6. Treat GBOGEB/stale#8 as unrelated dependency-maintenance PR unless explicitly selected.
7. Do not infer authority, formal credit, engineering credit, runtime GOLD or global DoV from provider/federation PASS.

Read full durable handover:
mission-control/qps-triage-ultra/handover/SC_2026-09-28_QPS_TRIAGE_GM_FLEET_03_PARTIAL_LOSSLESS_HANDOVER_v5.md
