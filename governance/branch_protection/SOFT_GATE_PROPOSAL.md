# Soft-gate ruleset proposal: a governed way to merge with an allowed red

Status: **proposal, not installed.** It needs an owner decision, because it overrides two existing statements in this directory (see "Conflicts with the current policy"). Written 2026-11-10 after ten PRs went red on First-Pass Closure only because Codex reached its usage limit (`CODEX_REVIEW_NOT_COMPLETED_ON_EXACT_HEAD`, no findings).

## Problem

`P-BASIC pipeline-automation-hub default branch` (ruleset 25789280) requires `First-Pass Closure Gate / first-pass-closure` and has no bypass actors, so `current_user_can_bypass` is `never`. The gate assumes a working Codex review on every head. Codex review quota is finite, so the gate goes red for a reason no commit can fix. The only escapes today are a "do not merge" tag, an ad hoc bypass, or a red merge that teaches everyone to ignore red.

## Design: three tiers

| Tier | Mechanism | Who decides | Leaves the check red? | Audit trail |
|---|---|---|---|---|
| 1. Hard core | Ruleset `P-BASIC` (no bypass): PR, thread resolution, linear history, `validate-ultra-control`, `canonical-self-test-and-mutation`, `frozen-head-census`, `Launcher outputs current and tests`, `GOGREEN required gate`, `CodeQL` | nobody | n/a | n/a |
| 2. In-gate waiver | `codex_unavailable_waiver` in the First-Pass policy (docs/W305, section "Codex-unavailable waiver") | owner, by label, machine-verified | No: the gate passes and the receipt says `clean_first_pass: false` | label event, receipt, PR timeline |
| 3. Soft ruleset | Ruleset `P-SOFT` holds only the First-Pass context. Repository admin may bypass it, in pull-request mode only | owner, per merge | Yes: red stays red, merge records "bypassed rules" | GitHub audit log, PR timeline, ledger line |

Why three tiers:
- **Tier 2 handles the common case without any bypass.** Quota exhaustion is machine-detectable (Codex's own failed summary plus its limit comment), so the gate can accept it with a narrow label instead of a human overriding a red check.
- **Tier 3 is the emergency path** for what tier 2 refuses: PRs that touch workflows or policy, a gate that itself is broken, an outage. It is also the one-time unlock for merging the tier-2 change, because the gate files are protected control paths that only merge as an explicit bootstrap.
- **Split rulesets are the only way to scope a bypass.** A GitHub ruleset bypass waives every rule in that ruleset and nothing outside it. A per-check bypass inside one ruleset does not exist. Rulesets on the same branch aggregate, so moving one context into its own ruleset gives the "allowed red" list as a list: it is exactly the contexts in `P-SOFT`.

## Allowed-red register

| Check | Tier | May be red at merge? | Condition |
|---|---|---|---|
| `First-Pass Closure Gate / first-pass-closure` | 2 then 3 | Yes | Tier 2 if Codex quota is the only cause and no forbidden path changed; tier 3 otherwise, with a ledger line giving the reason |
| Codex review completion | 2 | Waived by label | Same as above |
| Open Codex P0/P1 | never | No | Fix, or resolve the thread with a reason |
| Any proof run (self-test, mutation, exact-head CI) | never | No | Waiver does not skip them |
| `CodeQL`, `validate-ultra-control`, `canonical-self-test-and-mutation`, `frozen-head-census`, `Launcher outputs current and tests`, `GOGREEN required gate` | 1 | No | Fix the cause |
| Unresolved review threads | 1 | No | A deferred thread needs a ledger id in its reply (see MAROON note) |

## Rollout order (each step reversible)

1. Owner reads this proposal and records the decision in the PR (see conflicts below).
2. Create `P-SOFT` first (`POST`, file `proposals/hub_soft_ruleset.json`). Both rulesets then require the context, so nothing is weaker yet.
3. Update `P-BASIC` (`PUT .../25789280`, file `proposals/hub_core_ruleset.json`) to drop the First-Pass context. Read both back and compare with the files.
4. Merge the tier-2 bootstrap PR (feat/fpc-codex-unavailable-waiver-20261110) using the tier-3 bypass. It carries no clean gate by design (`CONTROL_PLANE_CHANGE_REQUIRES_BOOTSTRAP`).
5. Run the distinct non-controller canary the policy requires: a docs-only PR with a failed Codex summary plus the label must pass.
6. Roll back by re-adding the context to `P-BASIC` and deleting `P-SOFT`.

```powershell
Set-Location "C:\DEV\REPOS\pipeline-automation-hub"
# Remove the _comment key from each file first, then:
gh api --method POST repos/GBOGEB/pipeline-automation-hub/rulesets --input governance/branch_protection/proposals/hub_soft_ruleset.json
gh api --method PUT  repos/GBOGEB/pipeline-automation-hub/rulesets/25789280 --input governance/branch_protection/proposals/hub_core_ruleset.json
gh api repos/GBOGEB/pipeline-automation-hub/rulesets --jq '.[] | "\(.id) \(.name) \(.enforcement)"'
```

## Conflicts with the current policy

- `README.md` in this directory says "No blanket bot/owner bypass" and "Never add ... permanent bypass".
- `ctl.py` `load_policy()` raises `Hold` when `bypass_actors != []`, so `ctl.py` cannot render or audit `P-SOFT`.

The proposal is narrower than a blanket bypass: one role, one ruleset, one context, pull-request mode only, no app or bot actor. It still departs from the written rule, so the owner records the exception. Until `ctl.py` learns a `soft` stage in a follow-up PR, the payloads are applied by hand and read back by hand.

## Reducing quota burn (not verified, measure first)

Likely contributors: `review_on_push` in both rulesets, empty `ci:` commits that re-trigger workflows (#1135), repeated `@codex review` retries across 15 PRs (#1135 hit the limit three times). Batch related PRs (as #1164 does), keep PRs draft until ready (`review_draft_pull_requests` is already false), and re-trigger CI with a workflow dispatch rather than a commit.

## CODE MAROON caveat

`mission-control/maroon/review_threads.py` ledgers threads left on closed PRs and counts resolved as `closed`. A thread resolved only to pass the ruleset therefore disappears from the debt count. Deferral needs a visible marker (reply carrying the ledger id) and a MAROON rule that treats "resolved with deferral marker" as `deferred`. Not implemented here.
