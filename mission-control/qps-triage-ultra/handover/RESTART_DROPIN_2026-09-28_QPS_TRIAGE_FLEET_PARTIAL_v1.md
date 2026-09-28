AUTHORITY-CHAIN CORRECTION
This drop-in is historical evidence only. Canonical restart authority is `GBOGEB/cryoplant-project` `handover/qps_recursive/GLOB.yaml` -> `SESSION_CLOSE_CURRENT.yaml` -> `QTG_CURRENT.yaml` plus current GM-FLEET-03 controller `GBOGEB/pipeline-automation-hub#426`. `execution_mode=sequential`. Do not use this file as a standalone restart root.

NEXT_AGENT_INSTRUCTION

Repository / mission scope:
- MissionControl home: GBOGEB/pipeline-automation-hub
- QPS queue controller: GBOGEB/cryoplant-project#481
- Fleet parents: pipeline-automation-hub#153, #372, #76, #85
- GM-FLEET-03 parent: pipeline-automation-hub#426
- RETURN controller: pipeline-automation-hub#418
- Merge-admission recurrence: REX-CM-005 / ABACUS#1278

EXECUTION_WAVE_TYPE = PARTIAL

WHY:
- FULL is not justified: most estate debt remains CONTROL/RETURN/HOLD; no broad coding wave is authorized.
- NONE is not justified: merged MissionControl #483 has two unresolved post-merge control findings; ABACUS has current-SHA CI reds plus one queued cross-platform CD run; live fleet denominator has changed.
- authority_transfer=false
- formal_credit_delta=0
- engineering_credit_delta=0

LIVE SNAPSHOT:
- 98 open issues across 8 issue-bearing repos.
- Counts:
  - cryoplant-project 50
  - pipeline-automation-hub 26
  - ABACUS 13
  - CODEX 4
  - GEMINI 2
  - Q_engineering_tools 1
  - gg_MATH 1
  - document-organization-system 1
- canonical fleet SSOT is stale at 94 / 7 repos.
- owner-wide open PR search found only GBOGEB/stale#8; unrelated to QPS TRIAGE.

CURRENT HEADS:
- pipeline-automation-hub cc19351780f17cc3c1219ffe53e293b44995e0fe
- cryoplant-project b8fcfc19f9b0a399951573faac36ec848d6acdf1
- ABACUS 982473623f68ee0ce7f6de39fe5eae124722d1c1
  - meaningful source head d371d7971ed0653171a9eee65d77cf80219df28d
- CODEX 645f836eb8b49be746a154bfe4f0987be7e50b43
  - meaningful source head 5f3570583b805c0ce61de6a523bd1fbcd81099b5
- GEMINI 9e2be9c5e66d4e3a00e6f3dfd6c59319d2274049
- Q_engineering_tools 593b24ff1c878924537b3ca65c40b15bb015f423
- gg_MATH a0882beadc6b4630e7c3545fcf8614e426709994
- document-organization-system f238ebfaaa129ed13bd912fea67f6d16fed4bd6e

MISSIONCONTROL #483:
- head ec71c8cded6c2313325d2343587a4fb78db082df
- merged as cc19351780f17cc3c1219ffe53e293b44995e0fe
- ordinary FPC run 36440915600 / job 108990840786 PASS >0-step
- trusted pre-review gate 36441239012 failed only because CODEX_REVIEW_NOT_COMPLETED_ON_EXACT_HEAD
- post-merge Copilot review found 2 unresolved material control defects:
  1. synchronize mirrored control receipt states;
  2. restore explicit admission union + no-silent-eviction invariant.
- preserve 5 REVIEWED / 7 SELECTED_NOT_READ / 116 ADMITTED_NOT_SELECTED / 951 UNEXPANDED = 1,079.
- admitted = 128.
- order 6 / cryoplant#1170 remains UNREAD / HELD.
- DO NOT read order 7.

ABACUS:
- queue SSOT dated 2026-09-26 says zero EXECUTE_NOW / PROVE and 12 open.
- live ABACUS = 13 due new #1447 dashboard-health issue.
- #1447 reports 16 broken internal links, 0 missing dashboards.
- current meaningful SHA d371d797...
- Session Tuple CI/CD 36441522270:
  - DOW tests PASS
  - Integration Tests FAIL on 3.10 and 3.11
  - flake8 PASS
  - black check FAIL
- ABACUS v032 36441522222:
  - all earlier gates PASS
  - Package Artifacts FAIL
- Unified CD 36441522024:
  - lint PASS
  - Ubuntu PASS
  - RHEL8 job 108993624142 QUEUED
  - RHEL9 job 108993624623 QUEUED
- queued != failure; require >0-step return before classification.

OWNER/RETURN HOLDS:
- CODEX#753 Pages Source -> GitHub Actions
- Q_engineering_tools#104 Pages Source -> GitHub Actions
- cryoplant#923 owner/runtime admission
- GEMINI#12/#16 external/physical/identity returns
- no compensating coding workaround.

3PSTAR / MIP PARTIAL CONTINUATION:
1. 3PR Refresh: #483 state + ABACUS exact runs + live fleet census.
2. 3PR Probe: repair only material #483 findings; consume RHEL jobs; reproduce ABACUS current-SHA first red.
3. 3PR Rank: #483 control integrity first; ABACUS chronological material red second; recensus third.
4. MIP Modernize: bounded control/CI repair only.
5. MIP Innovate: negative regressions only; no architecture expansion.
6. MIP Perpetuate: exact-head review, >0-step proof, fresh-main recurrence, SSOT recensus.
7. 3PC: merge only after proof; merge != proof.

NON-COMPENSATING:
- authority_transfer=false
- formal_credit_delta=0
- engineering_credit_delta=0
- cryoplant#923
- CODEX#753
- Q_engineering_tools#104
- queued/zero-step evidence
- issue-count pressure

EXACT STARTING LINE:
START HERE: Refresh canonical QPS restart authority in GBOGEB/cryoplant-project (handover/qps_recursive/GLOB.yaml -> SESSION_CLOSE_CURRENT.yaml -> QTG_CURRENT.yaml), then current pipeline-automation-hub master and GM-FLEET-03 controller #426. Preserve 6/6/116/951 and keep order 7 / cryoplant#1111 unread while the post-#490 control-integrity fix-forward is exact-head proven, Codex/Copilot clean, trusted-gate PASS, merged and read back. Only then, sequentially, consume ABACUS observations and recensus before selecting any new EXECUTE_NOW root.
