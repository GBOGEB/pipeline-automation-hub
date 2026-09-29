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

START HERE: Refresh GBOGEB/ABACUS main, GBOGEB/cryoplant-project main, GBOGEB/pipeline-automation-hub master, owner-wide open issues/PRs and live Actions; preserve cryoplant #923 CLOSED_COMPLETED and #943 OPEN/HOLD_NONCOMPENSATING_SOURCE_AUTHORITY; consume ABACUS DOW + Recursive DMAIC run 36539442396 on SHA a5b40b04a992f8aa98bfcb63e15b9610944e4edf to terminal state, then inspect ABACUS#1469 run 36531590731 and enumerate the 16 broken internal links; repair only if material + repo-local, otherwise classify/close with evidence; keep GM-FLEET-03#426 census-only unless a named executable defect emerges; execution remains PARTIAL, sequential, authority_transfer=false, formal_credit_delta=0, engineering_credit_delta=0.

Serialized current state:
- 100 open issues across 8 issue-bearing repositories
- counts: cryoplant-project=50, pipeline-automation-hub=26, ABACUS=15, CODEX=4, GEMINI=2, Q_engineering_tools=1, gg_MATH=1, document-organization-system=1
- one open PR owner-wide: GBOGEB/stale#8, unrelated Dependabot maintenance
- no open normal work PR in core QPS/MissionControl/ABACUS/CODEX/GEMINI/gg_MATH/document-organization-system
- MissionControl master: 7452d40c82c03280c8e0eace96d6bd9a92d044e2
- predecessor handover: pipeline-automation-hub#507 / v6 merged
- ABACUS active run: 36539442396, DOW + Recursive DMAIC - Unified CD Pipeline, SHA a5b40b04a992f8aa98bfcb63e15b9610944e4edf
- ABACUS run status: Lint & Validate PASS; CI Ubuntu PASS; CI RHEL8 QUEUED; CI RHEL9 QUEUED
- ABACUS#1469 OPEN fresh dashboard-health defect candidate
- ABACUS#1469 source run 36531590731: missing dashboards=0, broken internal links=16
- cryoplant#923 CLOSED/completed; do not reopen absent contradictory executed evidence
- cryoplant#943 OPEN non-compensating source/authority gate; selected architecture + explicit QPS disposition + FAT/L5/SAT route required
- pipeline-automation-hub#426 GM-FLEET-03 remains historical PR-lineage census/control; no GM-V/VI and no runner surge from census alone
- raw GitHub HTTP numeric status is not exposed by the connector; validate writes by connector success + exact readback

Uncompleted:
1. Consume ABACUS run 36539442396 to terminal.
2. Inspect #1469 broken-link report; enumerate 16 links.
3. Repair only material repo-local defect; otherwise evidence-backed reclassification/closure.
4. Recensus before selecting any further ACTIVE root.
5. Preserve #943/source/authority priority and #923 closed state.
6. Preserve PARTIAL/sequential/no-authority-transfer/no-credit state.

Durable handover:
mission-control/qps-triage-ultra/handover/SC_2026-09-29_QPS_TRIAGE_FLEET_PARTIAL_LOSSLESS_HANDOVER_v7.md
