# CP.CLOSE — GitHub-first lossless session closeout

**Command:** CP.CLOSE() | **Compatibility:** CP.HANDOFF() + CP.RESUME() | **G3P:** governed three-pulse wave, not three PRs. | **Authority:** Mission Control v2.

## Copy/paste moniker

Use this in the chat being closed:

    CP.CLOSE(scope="CURRENT_SESSION",
             target="GBOGEB/pipeline-automation-hub:master",
             mode="GITHUB_FIRST_LOSSLESS",
             outputs="PR+STATE+STATS+INTENTS+BD+REX+TODO+DROPIN+MANIFEST",
             admission="GOVERNED")

Meaning: stop adding new unrelated features; gather all accessible intent, rationale, original user requests (where visible), decisions, actual GitHub source evidence, metrics, owner work orders, outstanding BD/REX, regressions, current CI/test status, the last valid N ordinal, the future N+3 bounded wave, and an unambiguous restart instruction. Freeze a sanitized record, run validation, commit to a source-owner branch, open a PR to master, and pursue authorized admission if independently qualified. If main merge is blocked, return the PR URL and a lossless HOLD continuation instead. Do not silently merge or waive required review.

Related established commands:
- CP.HANDOFF(): independent archived handover transport including ZIP and hashes when actual source bytes exist
- CP.RESUME(): cross-chat restart from committed record or supplied archived ZIP, with fresh GitHub source/readback verification
- G3P.EXECUTE(N,N+3): one bounded three-pulse development wave; unrelated to the closeout command
- CP.CLOSE(scope="EXPORTED_CHATS", mode="LOSSLESS_CORPUS_REVIEW"): requires an explicit authorized export of those chats and cannot infer inaccessible transcripts

No command is an installed tool, automatic background process, source permission, or review exemption.

## Exact deliverables and useful questions

| Closeout question | Persisted answer / source class |
|---|---|
| What was the user's original intent and how did it evolve? | Reconstructed intent IDs linked to actions, decisions and evidence, with original ChatGPT IDs UNKNOWN |
| How many user prompts/messages, words and which days? | CHAT_STATS.json: UNKNOWN for entire chat by default; count only a supplied transcript sample with explicit completeness label |
| How many actions, which DONE/HOLD/TODO? | ACTION ledger, separate from canonical BD lifecycle |
| What changed in code and why? | Exact GitHub PR/head/merge observations, scope-qualified metrics and rationale |
| What's the native and postmerge CI state? | Reference exact source SHA, run/job/attempt separately; refresh before continuing |
| What remains red or not measured? | Every residual gate and owner-scoped TODO, including unknown denominators |
| What BD queue and REX? | Read-only projection from CODE_PURPLE_BD_QUEUE_v1 and explicit owner issues; no new CPQ IDs |
| Where can next chat start? | START_HERE, machine STATE, next-chat drop-in and manifest hashes |
| Has the handover reached master? | Distinct check: branch commit, native QA, eligible review, authorized merge, exact-master readback |

## Repo paths

Engine: mission-control/v2/handoff/closeout/cp_close.py
Contract: mission-control/v2/handoff/closeout/CP_CLOSE_GITHUB_v1.json
Frozen input: mission-control/v2/handoff/closeout/intakes/CP-G3P-HTMLQA-20261017.json
Generated files: mission-control/v2/handoff/closeout/records/CP-G3P-HTMLQA-20261017/
Canonical queue: mission-control/federation-atlas/CODE_PURPLE_BD_QUEUE_v1.json
Golden Thread: mission-control/golden-thread/session_hook/
Workflow: .github/workflows/cp-close-github-qa.yml

## CLI / VS Code / PowerShell

At an authorized clone with Python 3.10 or newer (standard library only):

    python mission-control/v2/handoff/closeout/cp_close.py --intake mission-control/v2/handoff/closeout/intakes/CP-G3P-HTMLQA-20261017.json --bd mission-control/federation-atlas/CODE_PURPLE_BD_QUEUE_v1.json --out mission-control/v2/handoff/closeout/records/CP-G3P-HTMLQA-20261017

Reproduce the committed checkpoint and fail on drift:

    python mission-control/v2/handoff/closeout/cp_close.py --intake mission-control/v2/handoff/closeout/intakes/CP-G3P-HTMLQA-20261017.json --bd mission-control/federation-atlas/CODE_PURPLE_BD_QUEUE_v1.json --out mission-control/v2/handoff/closeout/records/CP-G3P-HTMLQA-20261017 --check

Create a private portable ZIP if needed (do NOT check binary into the source repo):

    python mission-control/v2/handoff/closeout/cp_close.py --intake mission-control/v2/handoff/closeout/intakes/CP-G3P-HTMLQA-20261017.json --bd mission-control/federation-atlas/CODE_PURPLE_BD_QUEUE_v1.json --out .cp-close-review --zip .cp-close-review/CP-G3P-HTMLQA-20261017.zip

Optional message-count input must be supplied locally with schema missioncontrol.user_supplied_messages.v1, each item role/text and optional original timestamp. The generator outputs aggregate counts only and never embeds the message text in the public repo; the caller's assertion of completeness is *not* ChatGPT provider attestation.

## Statistics model

Keep populations distinct:
- User prompts = number of user-role messages in supplied population; the full-chat population remains NULL if no complete provider-backed export.
- Reconstructed intents = manually curated, source-classed semantic entities; never the same as prompt count.
- Action records = owned outcomes with unique SC-A### identifiers; not automatically GitHub issues or canonical BD items.
- Canonical BD counts = the last history state of existing CPQ records under a frozen source SHA; not refreshed issue census.
- PR status counts = exact GitHub observations at one non-atomic readback; not security/review acceptance.
- Test pass counts, statement/branch coverage, browser checks and source lines require separate scope+denominator and comparable clocks.
- Time and token statistics are NULL unless their actual source fields exist. P95 word length requires at least 20 supplied user prompts.
- No PCA, ANOVA or composite KPI may be inferred from a single reconstructed chat without valid independent populations.

The intake intentionally records six reconstructed intents and seven owner-scoped actions for the G3P/HTML-QA session. They are **not** six user prompts. Raw conversation text, credentials, hidden chain of thought and private vendor input are not approved for source control.

## Acceptance ladder

CAPTURED -> PR_COMMITTED -> CI_QUALIFIED -> MAIN_MERGED -> MAIN_READBACK.

One step cannot be inferred from its predecessor. On a red or unknown required gate, report SESSION_CLOSED_WITH_HOLD; retain all previous evidence and issue links. A successful main merge is an observed Git operation, not independently proven secure review or engineering approval. Pages hosting is a separate proof.

## SIPOC and dependency logic

Supplier: user-supplied sanitized session + native GitHub + canonical BD/GT.
Input: source identity, intents, action/decision evidence, metrics, scoped chat optional export.
Process: schema validation -> lossless semantic projection -> deterministic SHA256/ZIP -> negative tests -> exact-head CI -> independent review -> approved PR to master -> postmerge readback.
Outputs: README, STATE, STATS, intent/action, BD projection, TODO, narrative, drop-in and manifest.
Consumer: Mission Control and successive chat, independent domain source owners.

DoD: 100% recorded intent/action relationships in the captured subset, stable machine hashes, no private leakage, no fictitious chat count, CI and source-owner evidence.
DoV: another session can continue the next legal action from GitHub without the original chat; future pulses preserve lineage, unclosed reds and noncompensating gates.

## Stop / restart

Pause after three to five substantial pulses, context loss, changing source heads, human reviewer block, or canonical source conflict. Always issue a final GitHub state and lossless drop-in. To continue:

    CP.RESUME(source="GBOGEB/pipeline-automation-hub:mission-control/v2/handoff/closeout/records/CP-G3P-HTMLQA-20261017", mode="VERIFY_REFRESH_EXECUTE")

Keep all source history historical. Never rewrite prior Golden Thread/BD state from a handover or infer a PR approval.
