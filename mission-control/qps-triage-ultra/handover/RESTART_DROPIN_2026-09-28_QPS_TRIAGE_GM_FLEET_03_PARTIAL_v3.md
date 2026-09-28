NEXT_AGENT_INSTRUCTION

Repository / mission scope:
- MissionControl home: GBOGEB/pipeline-automation-hub
- active mission: GBOGEB/pipeline-automation-hub#426 / GM-FLEET-03
- fleet parents: #153, #372, #76, #85
- recurrent merge-admission control: REX-CM-005 / ABACUS#1278

EXECUTION_WAVE_TYPE = PARTIAL

LIVE STATE:
- current master: c9c4533ed789cf34aee2320cd4642d4fc7b8bf66
- 98 open issues / 8 issue-bearing repos
- owner-wide open PRs: only unrelated GBOGEB/stale#8
- operational MissionControl open PRs: 0
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
- #491 final head 24fa1e71f05e41f31c0223c26311a0108192af0f
- #491 FPC 36449725960 PASS >0-step
- #491 Codex exact-head COMPLETE / no threads
- #491 trusted gate 36449961020 PASS
- #491 merge/current master c9c4533ed789cf34aee2320cd4642d4fc7b8bf66
- fresh-master QPS TRIAGE Federation Control + GM-FLEET F01/Ring1/Ring2/Capacity controls PASS

HISTORICAL PUBLICATION:
- #490 exact head 1e3ed51ae15110b1c0971ff087bd053c8f03c9ae
- FPC 36448774023 PASS
- merged as c9c4533ed789cf34aee2320cd4642d4fc7b8bf66
- Codex completed after merge, no threads
- chronology remains NONCOMPLIANT_MERGE_BEFORE_REVIEW_CURRENT_STATE_VALIDATED
- fresh-master QPS TRIAGE Federation Control 36449029760 PASS

NEXT CANDIDATE:
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
START HERE: Read the canonical cryoplant restart chain handover/qps_recursive/GLOB.yaml -> SESSION_CLOSE_CURRENT.yaml -> QTG_CURRENT.yaml, then refresh GBOGEB/pipeline-automation-hub@c9c4533ed789cf34aee2320cd4642d4fc7b8bf66; verify current P1-S01 readback remains REVIEWED=6 / SELECTED_NOT_READ=6 / ADMITTED_NOT_SELECTED=116 / UNEXPANDED=951 with admitted union=128, silent_evictions=0 and order_7_read=false; then admit/deep-read only order 7 GBOGEB/cryoplant-project#1111, repair iff a material semantic/identity defect survives current-main lineage, publish/prove/review before merge, fresh-main readback, and STOP before order 8.
