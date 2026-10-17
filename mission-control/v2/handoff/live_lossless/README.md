# CODE PURPLE — Live Lossless (rolling in-chat source control)

**Canonical session closeout:** CP.CLOSEOUT() (Mission Control owner, no new SSOT).
**Current-chat rolling checkpoint:** CP.LIVE() (additive instruction moniker, not a background agent).
**Next chat:** CP.RESUME(). **Pulse envelope:** G3P.EXECUTE(N,N+3).

## Call while continuing the same chat

    CP.LIVE(scope="CURRENT_CHAT",mode="GITHUB_REFRESH_APPEND",
            target="GOVERNED_PR_TO_MASTER",
            view="SUMMARY_PLUS_SELECTABLE_DETAILS",continue_chat=true)

Actions: refresh exact GitHub source and PR/CI state, preserve the frozen checkpoint byte-for-byte, append only newly visible intents/subrequests and source-owned TODO, rebuild the deterministic HTML/JSON/hash manifest, run native and browser QA, commit to an owned PR, and seek only authorized main admission. Return a compact status/insights snapshot in this chat. Do NOT retire this chat or claim an always-on ChatGPT automation.

This moniker's machine contract is LIVE_LOSSLESS_PROFILE_v1.json. It does not replace CP.CLOSEOUT, CP.CLOSE, CP.HANDOFF, CP.RESUME, the canonical Code Purple BD queue, or Golden Thread session hook.

## Sources and evidence ladder

- Frozen original checkpoint: ../closeout/records/CP-G3P-HTMLQA-20261017/ — SHA-bound 6 historical intents, 7 historical actions, 3 BD focus rows and no complete ChatGPT prompt count.
- Current chat's additional intent: FOLLOWUP_DELTA_20261017.json — one separately identified intent, four owner actions and six nested subrequests, all explicitly USER_VISIBLE_RECONSTRUCTED, never original message-ID-attested.
- Native source observation: GITHUB_OBSERVED_20261017.json — selected non-atomic Mission Control master/PR/issue readback, date precision, exact SHA, one matched CP.CLOSE 34/34 test cohort; **not global CI statistics or G3P accepted-N**.
- Machine projection: published/snapshot.json generated from these inputs and existing CHAT_CLOSEOUT_PROFILE_v1.json. Preserves source hashes and all open/HOLD controls.
- Browser-only live overlay: public GitHub REST main SHA, selected PR and issue states. Request on load and optional 15/60-minute refresh while the page is open. No credentials, local writes or durable GitHub mutations; source rate limit/API failure is LIVE_PARTIAL or LIVE_UNAVAILABLE with the last frozen evidence left intact.
- Public release: the EXISTING Method Atlas Pages publisher packs /live-lossless/ only after the reviewed source is merged into master. QA screenshots on PR do not establish a hosted URL.
- Admission: independent required checks, security and eligible reviewer / merge-gate provenance remain separate from browser, code source, and CI results.

## Read first, drill on demand

Main **Overview** shows captured intent count, owned action count, canonical BD subset, exact-main **scoped** tests, observed SHA and UNKNOWN full prompt count, plus lifecycle bars and two-clock source lineage.

The four remaining sections (five tabs total including Overview) are user-selectable:
- Intents and subrequests — expandable parent and linked action IDs, current vs historical capture, search and expand/collapse.
- Actions and canonical BD — owner/state filters, DoD, dependencies and source links.
- GitHub and evidence — frozen-vs-browser readback PR statuses, source confidence, scoped metrics, full file links.
- Monikers and resume — copyable CP.CLOSEOUT, CP.LIVE, CP.CLOSE, CP.HANDOFF, CP.RESUME and G3P.EXECUTE instructions.

No UI element may turn UNKNOWN into zero, pass a security gate, or promote a locally observed merge to independently verified review.

## CLI / IDE / PowerShell

Standard library: Python 3.10+ (CI uses 3.12). From repository root:

    python -m unittest discover -s mission-control/v2/handoff/live_lossless -p "test_live_lossless.py" -v
    node --check mission-control/v2/handoff/live_lossless/app.js
    python mission-control/v2/handoff/live_lossless/build_live_lossless.py
    python mission-control/v2/handoff/live_lossless/build_live_lossless.py --check

For local Chromium visual QA, install pinned playwright==1.57.0, run python -m playwright install chromium, then:

    python mission-control/v2/handoff/live_lossless/browser_qa.py \
      --site mission-control/v2/handoff/live_lossless/published \
      --out .local-live-lossless-qa

The Actions worker uses a controlled GitHub API fixture for functional/visual tests and always records that remote/native authority was **not** proven. The returned actual browser screenshot and digest receipt are source-bound to that PR head.

## CI and release gates

- Native separate QA: .github/workflows/live-lossless-qa.yml — 39+ Python negative/structural cases, JS syntax, desktop/laptop/mobile Chromium QA, screenshot SHA and existing portal byte parity.
- Production source build: .github/workflows/code-purple-method-atlas.yml — same single owner; no second Pages publisher.
- Published candidate: /live-lossless/index.html after the linked PR enters main and Pages deploys. Do not advertise this as live until exact-main Pages HTTP/status and SHA256 are independently rechecked.
- Any new observation commits a new dated source overlay/PR, not replacement of the original historical SHA-bound handover.

## SIPOC and source graph

User-visible request + exact GitHub/Git Actions + frozen handover + existing BD/Golden Thread → validate identities/source hashes and append-only edges → derive snapshot, full detail HTML, context UI and QA → output 5 source-controlled browser files and receipt → governed review, existing Pages publisher, continuing current chat.

For operational provenance, a GitHub source observation can have a new SHA while the old user prompt count remains null. Never join source-event clock and ChatGPT-turn clock without actual attested timestamps, or compute PCA/ANOVA from incomparable test populations.

### Roll-forward / fail-close

On a major blocker, keep partial artifact/PR and explicit OWNER/HOLD; don't skip pulse ordinals. On GitHub API 403/rate limit, show stale/bounded status; no fake success. Source authority remains in canonical owner repositories. The user may continue this same chat with CP.LIVE again or execute CP.RESUME later with a verified checkpoint.
