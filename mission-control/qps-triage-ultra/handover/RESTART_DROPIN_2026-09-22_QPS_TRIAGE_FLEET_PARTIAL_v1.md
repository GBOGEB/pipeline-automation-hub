NEXT_AGENT_INSTRUCTION

Repository / mission scope:
- Primary semantic root: GBOGEB/cryoplant-project#1617 (HIST-BD-034)
- QPS queue controller: GBOGEB/cryoplant-project#481
- MissionControl home: GBOGEB/pipeline-automation-hub
- Fleet parents: #153, #372, #76, #85
- REX recurrence control: REX-CM-005

EXECUTION_WAVE_TYPE = PARTIAL

WHY:
- FULL is not justified: most fleet debt is CONTROL/RETURN/HOLD and six of seven issue-bearing repos have no selected semantic EXECUTE_NOW root.
- NONE is not justified: #1617 is a genuine current-code semantic PROVE root; CODEX #814 and #813 carry bounded review/proof debt.
- authority_transfer=false
- formal_credit_delta=0

LIVE SNAPSHOT:
- 95 open issues across 7 issue-bearing repos.
- Counts: cryoplant 56; pipeline 19; ABACUS 12; CODEX 4; GEMINI 2; gg_MATH 1; document-organization-system 1.
- Prior canonical fleet SSOT is stale at 94 = 31 CONTROL + 0 ACTIVE + 63 BLOCKED.
- Provisional live overlay = 95 = 31 CONTROL + 1 ACTIVE (#1617) + 63 BLOCKED.
- cryoplant local queue is stale at 55 vs live 56 and must be recensused.
- Do not create extra semantic roots for reviews, retry jobs, jobs=0, or steps=null.

CURRENT HEADS:
- pipeline-automation-hub 216e13914c0fd9d559f6fdc50c0f2a3df3f42cf1
- cryoplant-project df84ddc293efd3c9fdb2e8cb098c745d26bdac3a
- CODEX b20184a0c496d65daba8c98256513261c5e36e50
- ABACUS 2c35a41e9cf9ecde1ca45abd8afc5f6382a901f9
- GEMINI 949f03c22ec3fada0cbf7c18a3bf56ded5f74fc7
- gg_MATH 2b27f4a6d70a11324d9a7c81d9c88995888b3d74
- document-organization-system 3c57b9ed674f50af7650ba9aa306d6b182caee28

CURRENT OPEN QPS-RELEVANT PRS:
- CODEX#814 W328-R1 semantic runtime fix-forward; review running at snapshot.
- CODEX#813 workflow registration/zero-job repair; review running at snapshot.
- cryoplant#1632 is already merged at df84ddc293efd3c9fdb2e8cb098c745d26bdac3a.

HIST-BD-034:
- One semantic PROVE root only.
- #1632 repaired BT1 metadata inheritance.
- Exact repair head 6f9902fc5d5410cd77c11ca5acf80edbbcb30041.
- Original bypass: {"Cv":{"value":null,"source_page":3}} could use metadata numeric as engineering value.
- Repair limits semantic wrappers to explicit value/magnitude members while preserving direct zero and true engineering-key recursion.
- #923 remains independent owner/runner RETURN.
- No engineering/formal/runtime-GOLD credit.

CODEX W328:
- #809 merged at a1db385f4070c53fb7dec24a8efdbfc45d5c1e30.
- #814 fixes semantic runtime key, ruff import, and governance-header first-reds from #809.
- #813 fixes workflows that registered with jobs=0.
- Treat #813 as proof/admission debt, not a new semantic root.

3PSTAR / MIP CONTINUATION:
1. Refresh #1617, #1632, #814, #813 and exact workflow/review results.
2. Repair only a material current-code finding.
3. Keep one semantic root; retry/proof children do not increase BD count.
4. Require clean exact-head review.
5. Require >0-step proof where runtime is claimed and runner admits execution.
6. Preserve source-defined tolerance, semantic-value guards, zero handling, and exact provenance.
7. Recensus cryoplant queue and fleet SSOT after current proof returns.
8. Reopen/activate new work only from an observed current first-red.

NON-COMPENSATING:
- cryoplant#923
- external/owner/physical/source returns
- formal_credit_delta=0
- authority_transfer=false

EXACT STARTING LINE:
START HERE: Refresh GBOGEB/cryoplant-project#1617 and the exact-head review/proof returns for cryoplant#1632 plus CODEX#814/#813; keep HIST-BD-034 as the sole semantic PROVE root unless a distinct current-code cause is proven, then recensus cryoplant and fleet SSOTs before selecting any new EXECUTE_NOW work.
