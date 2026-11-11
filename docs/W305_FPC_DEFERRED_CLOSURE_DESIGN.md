# W305 First-Pass Closure: governed deferred closure (design)

Status: **design proposal, nothing installed.** It needs owner decisions (listed at the end) before
any code. Written 2026-11-11 against `origin/master` at `45e87ac9`.

## Problem

The First-Pass Closure gate (`docs/W305_FIRST_PASS_CLOSURE_GATE.md`) goes red for a reason no commit
can fix when the Codex review quota runs out (`CODEX_REVIEW_NOT_COMPLETED_ON_EXACT_HEAD`, zero
findings). Today there is one way past it: the **"Merge without waiting for requirements (bypass
rules)"** checkbox. That checkbox is the admin bypass of ruleset `P-SOFT first-pass gate (owner
bypass on pull request)` (id 26995106). The ruleset went live on 2026-11-11 01:16, following
#1174's rollout steps 2 and 3. A merge through that checkbox:

- leaves no record in the repository. The only trace is a `bypass` rule suite in GitHub's rule-insights
  API and the audit log;
- creates no follow-up. Nothing re-reviews the change once quota returns;
- is counted nowhere. CODE MAROON, CODE PURPLE and GOGREEN don't read rule suites.

The bypass does not mean "failing but fixed elsewhere". It means "merged red, reason unrecorded".
The owner's rule stays **red means stop**. This design gives a red gate a third outcome besides
"fix it" and "bypass it": **defer it on the record**, with an owner, an expiry and a follow-up that
closes itself.

## What already exists (do not duplicate)

| Piece | Where | Relation to this design |
|---|---|---|
| Owner head-bound waiver by comment (`FPC_WAIVER_V1 head=<sha> waives=CODEX_REVIEW reason=...`) | PR #1172 (open) | Authorisation shape reused in (a) |
| Owner waiver by label `fpc:codex-unavailable`, with forbidden-path and Codex-evidence checks, `clean_first_pass: false` | PR #1173 (open) | Evidence checks and cohort rule reused in (a) |
| Soft-gate tiers and the allowed-red register | PR #1174 (open); `P-SOFT` is **live** | This design adds the record and the follow-up to tiers 2 and 3 |
| Merged-with-red classifier (`POSSIBLE_ENFORCEMENT_FAILURE_REQUIRES_MERGE_API_AND_BYPASS_AUDIT`) | `mission-control/issue_rank/taxonomy_admission_audit.py` `audit()` | Imported by the scan in (d) (AGENTS.md L4) |
| Thread resolution reader | `scripts/first_pass_closure_gate.py` `resolved_thread_roots()` | Imported by (c) and (e) |
| Review- and security-debt receipt with `closed` / `deferred` / `outstanding` | `mission-control/maroon/` | Counts the debt in (e) |
| Codex rationing (draft, ask once, batch) | PR #1194 (open) | Constrains how (c) spends quota |

Neither #1172 nor #1173 creates a follow-up. #1172 records `post_merge_review_owed: true` in the
receipt, and its own body says "CODE MAROON does not read it yet". This design is the missing half: the
owed review gets an owner, an expiry, an issue and a controller. **It is not a third waiver.** The
recommendation is to merge #1172 and #1173 into one tier-2 rule and extend it as in (a).

## Design

```
red gate (Codex quota)            red gate (anything else)
        |                                  |
 (a) FPC_DEFERRAL_V1 request +             |
     owner authorisation                   |
        |                                  |
 (b) gate: PASS_WITH_DEFERRAL       P-SOFT bypass checkbox (tier 3)
     debt issue already open               |
        |                                  |
      merge                              merge
        |                                  |
        |                       (d) bypass scan opens a debt issue
        |                                  |
        +---------------> fpc-debt issue <-+
                               |
              (c) post-merge controller: exact-content Codex review
                  when quota returns -> close (clean) or escalate
                               |
              (e) CODE MAROON source `fpc_debt`: deferred / outstanding / closed
```

### (a) The `FPC_DEFERRAL_V1` request and its authorisation

The request and the authority are two separate objects. The PR body carries the **request**. Anyone
who can edit the body can write a request, so the request alone grants nothing:

```html
<!-- FPC_DEFERRAL_V1
{
  "schema": "first_pass_closure_deferral/v1",
  "head_sha": "<40-char PR head>",
  "reason_code": "CODEX_QUOTA_EXHAUSTED",
  "defers": ["CODEX_REVIEW"],
  "owner": "GBOGEB",
  "expires": "2026-11-25",
  "followup_issue": 1234
}
-->
```

The **authorisation** is a comment by a login in the policy's `owner_logins`, posted after the head
commit's committer date. It is #1172's line, extended to bind the request's content:

```
FPC_DEFERRAL_AUTH_V1 head=<40-char sha> request=<sha256 of the canonical JSON request>
```

Binding the digest means that editing the reason, the expiry or the follow-up issue after
authorisation voids the authorisation, and so does a new push (new head). #1173's label carries no
content, so it can't bind the expiry or the issue. That is why the comment shape is preferred, with
#1173's checks kept.

The trusted-base gate (still run from the PR base SHA, R6) accepts the deferral only when **all** of
these hold:

1. `head_sha` equals the live head, and the authorisation comment names the same head and the digest
   of the request as it is in the body now.
2. `reason_code` is in the policy's closed list. Version 1 has one code, `CODEX_QUOTA_EXHAUSTED`. It
   is machine-checked as in #1173: Codex's own summary reports the review `failed` on the exact head
   **and** a later Codex comment carries the usage-limit phrase. A code the gate cannot check from
   evidence is not added to the list.
3. `defers` is a subset of the policy's `deferrable` list. Version 1 has only `CODEX_REVIEW`.
4. `expires` is in the future and at most `max_deferral_days` (proposed 14) after the authorisation.
5. `followup_issue` is open, carries the `fpc-debt` label, and its body has an `FPC_DEBT_V1` marker
   naming this PR (format in (d)). The gate reads it and doesn't write it.
6. Nothing changed matches #1173's forbidden paths (workflows, actions, dependabot, CODEOWNERS,
   SECURITY, quality policy, gate scripts). The control-plane bootstrap rule is unchanged, so those PRs
   still go through tier 3 and are caught by (d).
7. No open Codex finding of any priority on the exact head (#1173's stricter rule).

Never deferred: the exact-head proof runs, open P0/P1 findings, and the control-plane bootstrap rule.
These are the same lists as #1172 and #1173.

**Identity caveat (owner decision D1).** Every agent session in this repository acts as `GBOGEB`
through the same `gh` login. GitHub can't tell the owner's comment from an agent's comment under the
owner's login. So an `owner_logins` check proves "the GBOGEB account", not "the human owner". Options:

- **D1-a (proposed for v1):** accept the account check, and add an AGENTS.md rule that agents never
  post `FPC_DEFERRAL_AUTH_V1` or apply deferral labels. The scan in (d) and the MAROON count make any
  breach visible.
- **D1-b:** authorise through a GitHub Environment `fpc-deferral` with the owner as required reviewer.
  The approval is clicked in the UI, but the same token can approve through the REST API, so this
  is still not a hard human-only proof.
- **D1-c:** a signed authorisation (an SSH-signed tag or commit on a `fpc-auth/<pr>` ref) with a key
  only the human holds (hardware or passphrase-protected), verified by the gate. This is the only
  option that separates human from agent, at a real usability cost.

### (b) What the gate publishes

The required context `First-Pass Closure Gate / first-pass-closure` is a **commit status**. Commit
statuses have four states only: `pending`, `success`, `failure` and `error`. There is no neutral, and
a required status passes only on `success`. So "PASS_WITH_DEFERRAL" can't be a fifth state of the
same context. Proposal:

- **Receipt:** a distinct status `PASS_WITH_DEFERRAL_FIRST_PASS_CLOSURE_GATE`, with `clean_first_pass:
  false`, a `deferral` block (request, digest, authorisation comment id, follow-up issue, expiry) and
  `post_merge_review_owed: true`. `validate_pass_receipt()` accepts it only with a complete `deferral`
  block, so a bare PASS can never be mistaken for a deferred one, and the reverse can't happen either.
- **Required status:** `success`, description `PASS_WITH_DEFERRAL debt #<issue> until <date>`
  (fits the 140-character limit). It has to be `success` or the merge stays blocked, which would make
  the deferral pointless.
- **Visible marker:** an extra, **non-required** check run `First-Pass Closure Gate / deferral` with
  conclusion `neutral` and the receipt summary. The PR's check list then shows grey next to the green,
  so nobody reads it as a clean pass. This needs `checks: write` on the gate job (owner decision D2).
- **Cohort:** a deferred PR never counts toward the prospective 7/8 clean first-pass cohort. This is
  #1173's `clean_first_pass: false` rule.

Auto-merge: the existing hold keeps disabling auto-merge unless the final predicate passes. Proposal:
keep the hold for deferred PRs too, so the merge of a deferred PR is always a deliberate human
click (D2).

### (c) Post-merge controller `fpc-debt-controller.yml`

Triggers: `schedule` (proposed every 6 h) and `workflow_dispatch` (`issue_number`, optional). It runs
from the default branch only. Per the privileged-job rule it checks out `github.sha` and asserts it.
It never checks out candidate content.

For each open `fpc-debt` issue, oldest first, **at most one review in flight** (#1194 rationing):

1. Read the `FPC_DEBT_V1` marker: PR number, merge commit SHA, deferred items, expiry.
2. **Exact-content review target.** Codex reviews pull requests, not commits. The controller creates
   two refs through the API, with no checkout: `fpc-debt/<pr>/base` at the merge commit's first
   parent, and `fpc-debt/<pr>/head` at the merge commit. It then opens a **review-only PR** from head
   to base, titled `[fpc-debt #<issue>] post-merge review of #<pr> (never merge)`, labelled
   `fpc-debt-review`. Its diff is exactly what landed. Its head SHA is the merge commit, so "exact
   head" in the Codex contract means the merged content.
3. **Ask once.** Automatic Codex review is off since 2026-11-11 (#1194), so the controller posts
   `@codex review` once. Whether Codex answers a request from `github-actions[bot]` is **unverified**
   (D3). If it doesn't, the request needs an owner-held token, or the controller posts a checklist
   comment and a session asks.
4. **Read the outcome** with the gate's own functions (`review_is_completed_for_head`,
   `codex_blocking_findings`, imported). Then:
   - **Clean** (summary completed on the merge SHA, zero P0/P1): comment the receipt on the issue,
     close the review-only PR, delete both refs, close the issue as completed.
   - **Usage-limit reply again:** record the attempt in the issue (comment), back off to the next
     window, and ask nowhere else in that window.
   - **Findings:** label the issue `fpc-debt:findings`, link the threads, and keep the review-only PR
     **open** until the threads are resolved. MAROON counts a thread on a PR closed without merging
     as `deferred`, so closing it early would hide the findings. Fixes land in normal PRs.
   - **Expired** with no clean review: label `fpc-debt:expired`, assign the owner, and from then on
     count it as outstanding in (e).
5. Write `output/fpc-debt/CONTROLLER_RECEIPT.json` (artifact) with every issue it touched and why.

Permissions: `contents: write` (refs only), `pull-requests: write` and `issues: write`. The job closes
issues and review-only PRs **only**. It never merges, never pushes content and never edits a ruleset.
The review-only PR gets a body line saying it must not be merged. A fail-closed check (D4) can enforce
that, for example the gate refusing any PR whose head ref starts with `fpc-debt/`.

### (d) Bypass scan `fpc-bypass-scan` (in the same workflow)

This scan catches merges that skipped (a): tier-3 bypasses, control-plane bootstraps, and anything
merged while the gate was red.

- **Source of truth:** `GET /repos/{repo}/rulesets/rule-suites?ref=refs/heads/master&rule_suite_result=bypass`,
  then `GET .../rule-suites/{id}` for each suite. A suite whose `rule_evaluations` has a
  `required_status_checks` result `fail` with details naming `First-Pass Closure Gate /
  first-pass-closure` is an FPC bypass. `after_sha` is the merge commit, and
  `GET /commits/{after_sha}/pulls` gives the PR. On 2026-11-11 this returned 5 bypass suites in the
  last month, for example suite 5000767803 (2026-11-09, #1139, a bootstrap merge).
- **Token:** per GitHub's REST docs, rule suites need repository **Administration: read**, which
  `GITHUB_TOKEN` can't be granted. The full scan therefore needs a read-only fine-grained token secret
  (proposed `FPC_AUDIT_TOKEN`, Administration: read, Metadata: read), or it runs owner-side from a
  workstation (D5). This is unverified in Actions; probe it in phase 1.
- **Degraded mode without the token:** list PRs merged into master in the window. For each, read the
  head's last `First-Pass Closure Gate / first-pass-closure` status before `merged_at` and classify it
  with `taxonomy_admission_audit.audit()` (imported). A red merge becomes
  `POSSIBLE_ENFORCEMENT_FAILURE_REQUIRES_MERGE_API_AND_BYPASS_AUDIT`, recorded as
  `evidence: status_only`, never as a proven bypass. This follows that module's rule: "Never claim a
  configured required check was bypassed from timing alone".
- **Output:** for each FPC bypass with no `fpc-debt` issue yet, open one with
  `reason: BYPASS_WITHOUT_DEFERRAL` and the marker:

```html
<!-- FPC_DEBT_V1
{"schema":"fpc_debt/v1","pr":1139,"merge_sha":"401c5731...","source":"rule_suite_bypass",
 "rule_suite_id":5000767803,"actor":"GBOGEB","deferred":["CODEX_REVIEW"],"expires":null}
-->
```

  Deduplicate on `(pr, merge_sha)`. A bootstrap merge carries the bootstrap's own debt (the
  non-controller canary) as well. The issue names it, and the canary PR closes it, not the controller.
- **Backfill (D6):** decide whether to backfill the 5 bypasses already in the 30-day rule-suite
  window, or start from the day the scan is installed.

The issue text must not use GitHub closing keywords (`closes`, `fixes` or `resolves` followed by a
PR reference), per #1192.

### (e) Where the debt is counted

**Recommended: CODE MAROON, as a fifth source `fpc_debt`. GOGREEN reads MAROON's public counts and
does not recount** (AGENTS.md L4, one owner per metric).

| `fpc-debt` issue state | MAROON disposition |
|---|---|
| open, authorised deferral, not expired | `deferred` |
| open, `BYPASS_WITHOUT_DEFERRAL` (no owner plan on record) | `outstanding` |
| open, `fpc-debt:expired` or `fpc-debt:findings` | `outstanding` |
| closed as completed by the controller (clean exact-content review) | `closed` |
| closed as not planned by the owner | `deferred` (counts, never as fixed) |

- Root: one PR (one merge commit). Lane: `<repo>:fpc-debt`. Severity: `high` for bypasses without
  deferral, `medium` for authorised deferrals, and the worst Codex badge once findings exist.
- Coverage: `ok`, `not_readable` (issues API refused), or `bypass_scan_degraded` when (d) ran without
  the audit token. That last one is a gap and is never reported as zero.
- **MAROON's contract holds:** it reads `fpc-debt` issues and writes counts. It closes nothing and has
  no merge authority. All closing authority sits in the controller (c), and that authority is limited
  to its own issues and review-only PRs.
- This also settles #1174's MAROON caveat: a review thread resolved to pass the ruleset with an
  `FPC_DEBT` id in its reply counts as `deferred` under that root, not as `closed`.

The alternative is a GOGREEN pulse that counts `fpc-debt` itself. It would put a second counter on
the same debt. It is better for GOGREEN to read MAROON's `MAROON_PUBLIC.json` count for the
`fpc_debt` source and turn red when an expired item exists.

## Rollout (each step reversible)

1. **Owner decisions D1 to D7** (below), recorded on this PR.
2. **Merge #1172 and #1173** into one tier-2 rule with the (a) extensions: request block, digest-bound
   authorisation, expiry, follow-up issue. This is a control-plane change, so it is a bootstrap through
   `P-SOFT`, followed by a distinct non-controller canary. The bypass scan, once installed, records
   that bootstrap as debt too.
3. **Controller and scan workflow** in a separate PR. It is not a protected FPC path, so it gets a
   normal gate. Probe D3 (does Codex answer the bot?) and D5 (rule suites from Actions) on a canary
   first.
4. **MAROON `fpc_debt` source** in its own PR, with tests over a fixture of issue states.
5. **AGENTS.md:** agents never post the authorisation line (D1-a), and the deferral path is the
   documented alternative to the bypass checkbox.

Rollback: remove the `fpc_deferral` block from the policy (the gate falls back to plain red), disable
the controller workflow, and drop the MAROON source. Existing `fpc-debt` issues stay as a record.

## Owner decisions

| # | Decision | Proposed |
|---|---|---|
| D1 | Who may authorise, given that agents share the `GBOGEB` login | D1-a for v1 (account check plus AGENTS.md rule), with D1-c as the hardening path |
| D2 | Distinct published state: `success` with a `PASS_WITH_DEFERRAL` description, plus a neutral non-required `deferral` check run (`checks: write`); keep the auto-merge hold for deferred PRs | Yes to all three |
| D3 | How the controller asks Codex: `@codex review` as `github-actions[bot]` (unverified), an owner-held token, or a session prompted by the issue | Probe the bot first; fall back to the session prompt, no new token |
| D4 | Hard refusal of any PR whose head ref is `fpc-debt/*` | Yes, in the same bootstrap as step 2 |
| D5 | Read-only `FPC_AUDIT_TOKEN` (Administration: read) for rule suites, or an owner-side scan only | Token, fine-grained, this repo only, read-only |
| D6 | Backfill the 5 bypasses in the current 30-day window | Yes, as `BYPASS_WITHOUT_DEFERRAL`, so the count starts honest |
| D7 | Maximum deferral (`max_deferral_days`) and controller cadence | 14 days; every 6 h, one review in flight |

## Non-compensation

A deferral is not a pass. It grants no engineering, R3, runtime-GOLD, GT, procurement, acceptance or
formal credit. A deferred PR is never a clean first pass, and closing its debt issue doesn't make it
one after the fact.
