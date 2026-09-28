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

START HERE: Refresh GBOGEB/cryoplant-project main, GBOGEB/pipeline-automation-hub master, GBOGEB/ABACUS main, owner-wide open issues/PRs and live Actions; read cryoplant-project GLOB.yaml -> SESSION_CLOSE_CURRENT.yaml -> QTG_CURRENT.yaml -> QTG_CURRENT_EXTENSIONS.yaml before any MissionControl lane; preserve #923 CLOSED_COMPLETED_RUNNER_ADMISSION_RECOVERED and GT_BDQ_0..9 PASS/CLOSED; preserve global first-red #943 + SELECTED_SAFETY_SOURCE_SET as HOLD_NONCOMPENSATING_SOURCE_AUTHORITY; then consume only PR #506 exact-head control gates, keeping cryoplant PR1111 SELECTED_NOT_READ and admitted_for_read=false until #506 is review-clean, trusted-gate PASS, merged on the exact proven head and fresh-master read back; ABACUS HIST-BD-038 is CLOSED/DONE via #1466 and #1464/#1465 are superseded/closed; classify unrelated ABACUS CI reds separately by chronological first executed red; keep execution PARTIAL and sequential with authority_transfer=false, formal_credit_delta=0, engineering_credit_delta=0.

Serialized current state:
- owner-wide live issue census: 98 across 8 issue-bearing repositories
- counts: cryoplant-project=50, pipeline-automation-hub=26, ABACUS=13, CODEX=4, GEMINI=2, Q_engineering_tools=1, gg_MATH=1, document-organization-system=1
- open PRs: pipeline-automation-hub#506 plus unrelated GBOGEB/stale#8
- MissionControl master: 7bf52f56a68d2931493f2c244f8627c6f42bef54
- #506 head: 4a8062574723f371ac41785a129add864e306da7
- #506 FPC 36462082282 / job 109062896379: PASS / >0 steps
- #506 core controls: QPS federation, F01/F03, Ring1/Ring2, Capacity, GM-FLEET-02B, W3-16 and GM-IV controls PASS
- #506 Codex review: RUNNING at serialization
- #505 merge 7bf52f56... retains three material Copilot findings and is not clean order-7 authority
- #506 restores order7 HELD, PR1111 SELECTED_NOT_READ, admitted_for_read=false, 6/6/116/951, admitted=128, silent_evictions=0
- canonical QPS #923 CLOSED; Golden Thread GT_BDQ_0..9 PASS/CLOSED; repo-local QPS fix pressure EMPTY
- canonical QTG global first-red remains #943 + SELECTED_SAFETY_SOURCE_SET / HOLD_NONCOMPENSATING_SOURCE_AUTHORITY
- QPS global DoV WITHHELD; runtime GOLD WITHHELD
- ABACUS HIST-BD-038 issue #1459 DONE via PR #1466, exact head 0034d2e58422cacffa0ce9f9bf72ae435e4e9807, run 36455515574/job 109040743778 PASS, merge f6da6b33f49e361fe970caf8728896ac9d43f6c7
- ABACUS #1464/#1465 closed SUPERSEDED; #1313 remains independent substantive Appendix 8.4 source/state completion
- unrelated/generic ABACUS CI must be classified independently by first executed material red
- REX-CM-005 remains merge-admission chronology recurrence; REX-CM-006 refresh before any new semantic root
- raw HTTP 200/201 is not exposed by the GitHub connector; validate writes by connector success + exact readback, never fabricate numeric status

Uncompleted:
1. Consume #506 Codex review.
2. Require #506 ready-state review, Copilot clean, trusted exact-head gate PASS before merge.
3. Merge exact proven #506 head only.
4. Fresh-master readback must retain order7 unread and accounting 6/6/116/951, admitted=128, silent_evictions=0.
5. Create separate order-7 authorization only after that and only if canonical QTG permits.
6. Preserve #943/source/safety priority and all non-compensating return gates.
7. Re-census owner-wide state before every pulse.

Durable handover:
mission-control/qps-triage-ultra/handover/SC_2026-09-28_QPS_TRIAGE_GM_FLEET_03_PARTIAL_LOSSLESS_HANDOVER_v6.md
