# CP.CLOSEOUT — MissionControl GitHub-first handover / chat retirement

**Snapshot:** 17 October 2026 · `CP-HUB-HANDOFF-20261017` · `VISIBLE_CONTEXT_PARTIAL` · **non-atomic** · engineering admission `HOLD`. Canonical source is the linked GitHub PR and repository code; this is a **consumer closeout receipt**, not a substitute SSOT or verbatim chat export. Its machine-readable counterpart is `RECEIPT.json`.

## 1. Narrative and original intention

The first accessible user request supplied the MissionControl Actions screenshot showing an N3 failure and asked for a complete *GitHub-first* lossless-intent handover, reusable moniker and only necessary continuation artifacts. The previous closeout pass read the canonical `CP.HANDOFF / CP.RESUME` files, fetched live GitHub PR/CI metadata and implemented [draft #640](https://github.com/GBOGEB/pipeline-automation-hub/pull/640) as an additive, non-authoritative extension of [merged handover #634](https://github.com/GBOGEB/pipeline-automation-hub/pull/634).

The present follow-up explicitly requests a reusable **chat retirement moniker**, stronger session accounting (total prompts, intent categories, prompt/response narrative, decisions, insights), completed versus pending work, a deduplicated TODO/BD queue, and a path from GitHub PR artifacts to **authorized exact-main custody**.

Decision: implement `CP.CLOSEOUT!` as an instruction macro on the **same owner PR #640**, not a new controller, shadow ledger, forced merge or mandatory ZIP. All safety, independent review, security and child/QPS authority boundaries remain unchanged.

## 2. What actually happened / key source events

| Event | Source identity | Actual outcome |
|---|---|---|
| Original handover source | [Hub #634](https://github.com/GBOGEB/pipeline-automation-hub/pull/634), merge `b56a92ec9b58ffaaf7e274978543d68e21327dbc` | MERGED to `master`; **transport only**, not G3A engineering acceptance |
| Original handover native N3 | [Run #39041480567](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/39041480567), original head `dcf11a8c475ac7a6c420f919e08a82df7cfcbdc6` | Python 3.11 and 3.12 each ran 146 tests with one failure; focused coverage/export downstream skipped |
| Reused canonical fix | [Hub #630](https://github.com/GBOGEB/pipeline-automation-hub/pull/630) | Seven-module contract fix integrated into **intermediate #620 branch**, not into the failed #634 head or master |
| Candidate G3P ancestry | [#620](https://github.com/GBOGEB/pipeline-automation-hub/pull/620) → [#621](https://github.com/GBOGEB/pipeline-automation-hub/pull/621) → [#631](https://github.com/GBOGEB/pipeline-automation-hub/pull/631) | Open stack; #631 FPC MISSING_RECEIPT historical; no accepted N15 credit |
| Additive transport and closeout work | [Hub #640](https://github.com/GBOGEB/pipeline-automation-hub/pull/640) | Committed to draft PR; main merge and independent native verification **not established** at this frozen cutoff |

The two N3 job failures are two **manifestations** of a shared old `assert len(s)==6` fixture versus seven-module source, **not two independent causal roots**. The six-module repair is already owner-assigned. A green fragment or passing 11 handover guard tests cannot override the failing overall native workflow or independent FPC.

## 3. Session statistics: scope and measurement integrity

| Field | Available result | Evidence / limitation |
|---|---|---|
| User prompts observed in the visible bounded excerpt | **2** | Local accessible conversation fragment, not a complete exported chat |
| Full-session user prompts | **UNKNOWN** | No complete normalized original export supplied |
| Full-session assistant replies | **UNKNOWN** | Partial answers and tool calls cannot be enumerated historically |
| Total model/tool invocations | **UNKNOWN** | No authenticated complete tool-event export |
| Input/output tokens, full word/character counts | **UNKNOWN** | No verified complete text bytes and tokenizer identity |
| Actual elapsed session time | **UNKNOWN** | No verified first/last full-session timestamp population |
| Intent category share or trends | **QUALITATIVE ONLY** | Visible subset too small for total frequencies |
| New CP.CLOSEOUT regression cases authored | **20 cases** | Source committed to PR #640; native result must be read back, not asserted here |
| Old N3 Python matrix | **2 jobs, 146 executed per environment, 1 failure each** | Same 146-test population repeated across versions; not 292 independent test methods |

Qualitative prompt themes: GitHub-first lossless-intent custody; reusable closeout/resume; source ownership and admission; prompt/session analytics; narrative and key decisions; TODO and root-owned BD queue. These are **not** complete-chat topic frequencies.

**What would make full counts admissible?** A complete original export, explicit normalization to `code_purple.normalized_chat_export.v1`, SHA-256 of the exact normalized bytes, source boundary statement, and verification with `validate_chat_closeout.py --receipt ... --export ...`. Raw messages remain outside GitHub by default. The validator can verify the supplied bytes' counts and digest but cannot authenticate that the export includes every unseen conversation event.

## 4. Implemented versus merely planned

**Committed to PR:** opt-in GitHub-first transport moniker; append-only post-merge delta; new `CP.CLOSEOUT` declaration, reporting profile, operator guide, source-scoped receipt, 20 regression tests and native test-discovery bridge. This is new governance *source and test design*, not measured new technical coverage.

**Still due:** exact-head focused Testflight of all new tests, observed native workflow results, reviewer/branch-ruleset readback, master source admission if authorized, exact-main verification, and any full-session prompt census based on original export. No chat was automatically deleted. The independent #620/#621/#631 engineering queue remains unaffected.

## 5. Insights and actionable improvements

1. **Separate accountabilities:** chat custody is not engineering admission, which is not child-owned QPS acceptance. Represent independent stages rather than global green/red.
2. **Measure eligible denominators:** two matrix jobs over the same 146 methods, partial excerpt prompt count 2, and N15 branch/line coverage all describe different populations.
3. **Minimize duplicate repair:** compare source-owned #630 against current stack before touching the N3 contract. Treat dependent false-reds as manifestations.
4. **Use GitHub as durable memory:** commit a *sanitized* narrative, state, BD pointers and a copy-ready drop-in, not repeated ZIP snapshots or full private conversations.
5. **Practice DMAIC Control:** close out with named DoV, actual native telemetry and a next owner. Keep old receipts append-only even after source or default head advances.

## 6. Owner queue, DoV and completion rules

See the five machine-identifiable entries in `RECEIPT.json`: `CP-CLOSEOUT-01`, `BD-N3-01`, `BD-FPC-02`, `BD-STACK-03`, `CP-STAT-05`. Do **not** close them on the basis of this document. Actual owner PR/issue receipts are the governing records. Their work is:

- Verify this new CP.CLOSEOUT source/tests on #640 exact head, then satisfy effective review/security before any eligible integration.
- Reconcile #630's already-implemented shared fix through its owner branch and source-accurate N3 testflight.
- Repair #631's independent FPC missing trusted receipt and preserve negative controls.
- Refresh the now-divergent stacked-source ancestry before serial admission.
- If desired, privately export the full chat and establish eligible prompt/time/token populations, otherwise keep those metrics UNKNOWN.

**Closeout stage:** `COMMITTED_TO_PR`, target `GOVERNED_MAIN`; not `MERGED_TO_DEFAULT` or `EXACT_MAIN_VERIFIED`. Global `MERGE_ADMISSION=HOLD` for engineering/N15. A later GitHub merge of the transport code would prove **transport-source custody** only, not acceptance of other candidate repairs.

## 7. Standalone continuation

Use the sibling `DROPIN.md`. The receiver independently refreshes PR #640, default SHAs, latest native jobs/review and the BD owners before action. An absent full export does not prevent operational GitHub-first continuation; it prevents claims of complete message history and exact session totals.
