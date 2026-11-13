# JADE OG five: release-readiness follow-up, 12 November 2026

Status: source-bound follow-up; MERGE_ADMISSION=HOLD; no gate promotion or release credit.
This note extends the existing JADE owners. It is not a new score ledger or scheduler.

## Evidence and progress

The original five are **cryoplant-project, DOCX_RTM_Automation, yaml-grammar,
gg_MATH and pipeline-automation-hub**. ABACUS and CODEX are important DOW/KEB
providers but are not substitutes in this 60-cell denominator.

The latest committed gate observation is [P0005, 4 November](../data/FOCUS5_POINT_RELEASE_P0005.json).
It records **25/60 PASS (41.67%), zero FAIL, 35 UNKNOWN**, with all five tied at
5/12. P0001 recorded 14/60 PASS; P0003 21/60; P0004 24/60. An observation moving
from FAIL to UNKNOWN does not prove a repair. P0005 is eight days old at this
follow-up; these counts describe that checkpoint, not verified 12 November heads.

| Original criterion | P0005 result across five | Next closure work |
|---|---|---|
| H01 exact default SHA | 5 PASS | Read each default head once in the next pulse; pin every proof to it |
| H02 root/entrypoint | 5 PASS | Keep entrypoint and test/build scope explicit |
| H03 scope/applicability signed | 5 UNKNOWN | Owner defines release surface and version; record ACCEPT/HOLD with scope |
| H04 reproducible build | 5 PASS | Re-run declared build contract at the new head; preserve narrow scope |
| H05 native primary test | 5 PASS | Re-read terminal native job/attempt; repair actual first-red only |
| H06 independent smoke | 5 PASS | Re-read declared independent smoke on the same head |
| H07 security/supply chain accepted | 5 UNKNOWN | Drain current findings and obtain source-bound security disposition |
| H08 effective protection + RED canary | 5 UNKNOWN | Verify effective rules live and reverify actual rejected-RED receipt |
| H09 eligible independent approval | 5 UNKNOWN | Obtain exact-head eligible review; zero required approvals proves no review |
| H10 matched coverage + negatives | 5 UNKNOWN | Agree scope/floor; retain numerator, denominator, branch and negative proof |
| H11 artifact/site QA + hashes | 5 UNKNOWN | Build exact-source artifacts; negative paths, browser QA and served-byte parity |
| H12 owner tag/assets/rollback | 5 UNKNOWN | Join H03/H06–H11, demonstrate rollback and obtain owner release decision |

The frozen [Gate12 cockpit](../site/gate12_hub.html) still describes its original
historical source. Use [rolling5.json](../site/rolling5.json) for the latest committed
pulse; do not combine historical and rolling counts.

## Fresh source-owner observations

Hub source for this follow-up: `c66feef5c886ebc359bf38d4ea832e23b5ec5c46`.
Supplemental 12 November reads are non-atomic and do not constitute P0006.
Public [ruleset receipts](JADE_OG_FOLLOWUP_20261112_RULESETS.json) retain full
connector readbacks. The connector rejects the effective branch-rule endpoint;
the ruleset union is a derived observation, not that endpoint's proof.

| Repo / pinned public default head | Current evidence and next action |
|---|---|
| gg_MATH `dab93572628bc9ac7b0a9d9d323d6e2616dbbacf` | [#130 hardening](https://github.com/GBOGEB/gg_MATH/pull/130) and [#131 path confinement](https://github.com/GBOGEB/gg_MATH/pull/131) are already open. Drain review and combined-source proof. [#109](https://github.com/GBOGEB/gg_MATH/issues/109) owns Pages-root selection and first release. No GitHub Release returned. |
| DOCX `d1ae2b651d7dee6e18c27fb95ae3215a52c86a1c` | [#110](https://github.com/GBOGEB/DOCX_RTM_Automation/pull/110) verifier merged. [Current-main policy run](https://github.com/GBOGEB/DOCX_RTM_Automation/actions/runs/42916367799) is red on missing effective policy; eight other workflows succeed. Existing [#86](https://github.com/GBOGEB/DOCX_RTM_Automation/issues/86) owns settings closure. No GitHub Release returned. |
| yaml-grammar `d6988d00f0b25ac3df75eea9e2535b7b15d838a7` | [Build](https://github.com/GBOGEB/yaml-grammar/actions/runs/40585699667), [offline smoke](https://github.com/GBOGEB/yaml-grammar/actions/runs/40585699771), [user smoke](https://github.com/GBOGEB/yaml-grammar/actions/runs/40585699817) succeed. Contract qualifies stdlib validation; upstream Perl/Node regeneration is outside that contract. No open source work or GitHub Release returned. |
| Hub `c66feef5c886ebc359bf38d4ea832e23b5ec5c46` | Existing [#336](https://github.com/GBOGEB/pipeline-automation-hub/issues/336) owns required-barrier closure. P-BASIC now has no bypass, but P-SOFT FPC still permits owner PR bypass. Independent approval remains unproven. |
| QPS / cryoplant-project | Private source remains with its owner. Public JADE carries aggregate statuses only; public owner/proof workers must not ingest private SHA, PR, run or engineering content. |

H08 readiness has evolved since the 8 November handover:

- **gg_MATH:** two active default-branch rulesets have no bypass and five required
  checks. The existing [canary receipt registry](../data/FOCUS5_H08_CANARY_RECEIPTS.json)
  records a rejected RED merge on 11 November. PR107 is still unmerged at the receipt
  head and latest `first-kernel` remains failed. Canonical receipt verification with
  a derived active-ruleset union returns PASS, but live effective-rule verification
  remains required before a new authoritative H08 PASS observation.
- **DOCX:** Main_Protect2 still has neither PR nor required-status rules. Its merged
  verifier correctly exposes that gap. Apply the existing #86 settings contract,
  then prove positive and negative admission.
- **yaml:** Main_Protect has a PR rule but no required-status rule. Add the
  owner-designated native contexts, then run the existing canary protocol.
- **Hub:** P-BASIC has six required contexts and no bypass. P-SOFT separately allows
  owner bypass of FPC; the current H08 verifier rejects that configuration. Follow #336.

Do not interpret `protected=true`, a green workflow or a ruleset list as H08/H09 PASS.

## Parallel DMAIC execution fronts

Use the existing [stabilization contract #372](https://github.com/GBOGEB/pipeline-automation-hub/issues/372)
and [BD/REX owner #85](https://github.com/GBOGEB/pipeline-automation-hub/issues/85).
Each repo gets at most one active repair root and one proof root. Different repos,
disjoint files and owner decisions can proceed asynchronously; shared publication
and final admission remain ordered.

1. **DEFINE — H03, all five:** prepare one scope/version decision per repo using its
   current build contract. Hub JADE-only is different from whole-hub release;
   yaml validation is different from upstream regeneration. Owner signs the exact scope.
2. **MEASURE/ANALYZE — H08/H09:** prioritize gg_MATH receipt re-verification, DOCX #86
   policy return, yaml required contexts and Hub #336. These are separate owner work
   fronts. No application repair is assigned for a settings or review-capacity wait.
3. **IMPROVE — H07/H10/H11:** consume gg_MATH #130/#131 without duplicating their code.
   In parallel, package per-repo security dispositions, matched coverage/negative
   reports and exact-source artifact manifests. Private QPS executes in its own lane.
4. **PROVE — H04–H06/H11:** after a material source or owner-evidence change, take one
   fresh same-head observation per repo, inspect native attempts and compare artifact
   hashes. Reconcile changed heads before carrying proof forward.
5. **CONTROL — H12/NIRVANA:** owner release acceptance joins its prerequisites.
   Append the next pulse only after source evidence is qualified. A second qualifying
   observation establishes sustained NIRVANA; unchanged UNKNOWN polls earn no progress.

Every transaction returns first-red, owner, disposition
(`EXECUTE_NOW | PROVE | RETURN | HOLD | CONTROL | CLOSE | READ`), exact evidence,
next predicate and a REX candidate to the existing owner. Unknown or inaccessible
proof remains UNKNOWN. Progress on one gate never compensates another gate.

## Race placement and REX transfer

The canonical [rolling5.py](../tools/rolling5.py) remains the single owner.
Live readiness ties are explicit and separate from cohort display order. Earned
NIRVANA badges include placement, qualifying pulse IDs, observed date and source
SHA. Repositories qualifying in the same pulse share placement because within-pulse
finish order is unobserved. Historical badges do not prove current health or grant
release authority. **No badge is earned at P0005.**

NIRVANA still requires all twelve gates PASS on one exact SHA across two consecutive
observed pulses. H12 requires the separate owner decision specified by its criterion;
the badge cannot supply that decision.

| Leading implementation / lesson | Transfer to trailing repos | Acceptance at receiver |
|---|---|---|
| DOCX effective-policy verifier detects settings gaps | H08: inspect effective rules and provider/context identities | Native verifier + rejected RED canary; never branch boolean alone |
| gg_MATH required checks and recorded RED refusal | H08: use existing h08_canary receipt protocol | Reverify current rules and canary head; local replay alone insufficient |
| yaml narrow stdlib build contract | H03/H04: define reproducible release surface before expanding | Clean exact-source run within approved scope |
| gg_MATH #131 traversal/symlink + Windows matrix | H11: artifact-root confinement and hostile paths | Receiver-specific negative tests and manifest QA |
| Shared tied-placement correction | Fair race reporting across all future cohorts | Same-pulse ties, no badge with missing/unknown/changed-head evidence |

Promote a recurring repair to CONTROL only after a later distinct-source observation
shows the receiver's prevention/detection control works. Transfer method and tests;
each receiver must earn its own gate proof.
