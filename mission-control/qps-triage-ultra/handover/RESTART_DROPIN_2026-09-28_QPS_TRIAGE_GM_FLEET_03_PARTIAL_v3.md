NEXT_AGENT_INSTRUCTION

Repository / mission scope:
- MissionControl home: GBOGEB/pipeline-automation-hub
- active mission: GBOGEB/pipeline-automation-hub#426 / GM-FLEET-03
- fleet parents: #153, #372, #76, #85
- recurrent merge-admission control: REX-CM-005 / ABACUS#1278

EXECUTION_WAVE_TYPE = PARTIAL

CURRENT CLOSURE FIRST-RED:
- #491 post-merge review found 2 High + 1 Medium control defects not present on master
- fresh current-master fix-forward = pipeline-automation-hub#498
- #498 exact head = 69096e82388e00b7194a575e59e82905d97e6678
- #498 FPC = 36451359861 / job 109026649426 PASS >0-step
- #498 Codex exact-head review = RUNNING at session close
- #498 state = DRAFT / HOLD / DO_NOT_MERGE
- handover PR #494 = DRAFT / HOLD until #498 merge + fresh-master readback

LIVE STATE:
- current master: c9c4533ed789cf34aee2320cd4642d4fc7b8bf66
- 98 open issues / 8 issue-bearing repos
- MissionControl control PRs at this edge: #492 (independent MC-S2 A4) and #494 (this GM-FLEET publication)
- #494 is CONTROL/publication work; it does not admit order 7 before proof/readback
- active/queued MissionControl workflows: 0
- fresh-master GM-FLEET/QPS controls: GREEN

GM-FLEET-03:
- structural census: 90 repos / 4,486 PRs / 4,211 merged / 272 closed-unmerged / 3 open
- semantic candidates: 2,831
- P0 true cross-repo: 176
- P1: 1,079
- P2: 1,576

P1-S01:
- subset size: 12
- REVIEWED=6
- SELECTED_NOT_READ=6
- ADMITTED_NOT_SELECTED=116
- UNEXPANDED=951
- admitted union=128
- silent_evictions=0
- repaired=5
- clean_without_repair=1
- order_6_read=true
- order_7_read=false

ORDER 6:
- cryoplant-project#1170
- material W175-B defects repaired by QPS #1824
- final repair head ef83a69ce44dd5d61b30f3b2bab87808831bd941
- repair merge ae23418e726d80ecb63b73f8d82eb85767e974ff
- verify-ssot 36432956109 PASS
- qps-canonicalization 36432956166 PASS
- Codex exact-head clean before QPS merge

MISSIONCONTROL CURRENT-STATE CHAIN:
- #490 remains historical NONCOMPLIANT_MERGE_BEFORE_REVIEW_AND_TRUSTED_GATE
- #491 merged head 24fa1e71f05e41f31c0223c26311a0108192af0f with FPC/trusted-gate PASS, but final Copilot review completed after merge with three material control findings
- #491 chronology therefore remains NONCOMPLIANT_MERGE_BEFORE_FINAL_REVIEW_CURRENT_STATE_REPAIR_REQUIRED
- #494 is the current GM-FLEET control/publication fix-forward from master c9c4533ed789cf34aee2320cd4642d4fc7b8bf66
- #494 carries owner-qualified restart authority plus normalized order-7 hold state
- order 7 remains unread until #494 exact-head proof/review/trusted-gate/merge/readback

HISTORICAL PUBLICATION:
- #490 exact head 1e3ed51ae15110b1c0971ff087bd053c8f03c9ae
- ordinary FPC 36448774023 PASS
- trusted gate 36448959151 FAIL
- merged as 181ceabd0f207434b97a86ffba8ab7058a8b6ea0 while Codex was incomplete
- Codex completed only after merge
- chronology remains NONCOMPLIANT_MERGE_BEFORE_CODEX_COMPLETE_AND_WITH_TRUSTED_GATE_RED
- later green push controls do not compensate that chronology; #491 is the current-state fix-forward

CANONICAL QPS GLOBAL PRIORITY:
- read cryoplant GLOB -> SESSION_CLOSE_CURRENT -> QTG_CURRENT first
- QTG_CURRENT global first red = ISSUE_943_AND_SELECTED_SAFETY_SOURCE_SET
- state = HOLD_NONCOMPENSATING_SOURCE_AUTHORITY
- #923 = CLOSED_COMPLETED_RUNNER_ADMISSION_RECOVERED
- Golden Thread GT_BDQ_0..9 = CLOSED/PASS
- newly arrived source/safety/owner/physical returns preempt lower semantic work without compensation

MISSIONCONTROL NEXT CANDIDATE:
- order 7 = GBOGEB/cryoplant-project#1111
- state SELECTED_NOT_READ / UNREAD / HELD
- order 8 must remain unread

ABACUS CARRYOVER:
- #1447 open: 16 broken internal links, 0 missing dashboards, no durable disposition yet
- Session Tuple 36441522270: integration FAIL + black FAIL
- v032 36441522222: Package Artifacts FAIL after prior PASS gates
- Unified CD 36441522024: Ubuntu PASS; RHEL8/RHEL9 CANCELLED zero-step
- do not silently promote these above the governed GM-FLEET order-7 frontier

3PSTAR / MIP:
1. Refresh current master and exact P1-S01/admission identities.
2. Probe only order 7.
3. Stop on first material semantic/identity defect.
4. Repair iff current-main material.
5. Add only negative regression/control evidence required by that defect.
6. Exact-head FPC >0-step + Codex COMPLETE before merge.
7. Trusted gate PASS.
8. Merge exact reviewed head.
9. Fresh-master readback.
10. STOP before order 8.

NON-COMPENSATING:
- authority_transfer=false
- formal_credit_delta=0
- engineering_credit_delta=0
- cryoplant#923
- owner/external/physical returns
- cancelled/zero-step jobs
- issue-count pressure
- statistical ranking versus hard gates

CANONICAL RESTART AUTHORITY:
- GBOGEB/cryoplant-project
- handover/qps_recursive/GLOB.yaml -> SESSION_CLOSE_CURRENT.yaml -> QTG_CURRENT.yaml
- MissionControl #426 is controller
- MissionControl-local SESSION_CLOSE_CURRENT is historical/non-authoritative
- execution remains sequential

EXACT STARTING LINE:
START HERE: Refresh pipeline-automation-hub PR #498 at exact head 69096e82388e00b7194a575e59e82905d97e6678; if Codex exact-head review is still RUNNING, HOLD and do not merge; when review is COMPLETE/clean require trusted First-Pass Closure Gate PASS, merge exact head and fresh-master read back qualified cryoplant restart authority plus 6/6/116/951, admitted=128, silent_evictions=0 and order_7_read=false; then rebase/revalidate handover PR #494 and merge only after exact-head proof/review/trusted-gate; after final closure publication read cryoplant GLOB -> SESSION_CLOSE_CURRENT -> QTG_CURRENT, preserve global #943 + selected safety/source preemption, and only if no higher-priority QTG return is actionable admit/deep-read GM-FLEET order 7 cryoplant-project#1111; STOP before order 8.
