# Governed default-branch protection (Mission Control SSOT)

**Scope:** four explicitly allowlisted repositories. TOP7 pilot; TOP14 remains shadow-only and TOP21 remains HOLD. No QPS engineering-SSOT authority transfer. This is an admin-deployment proposal, not an installed protection claim.

## Responsibility and boundary

A pull request can review and merge this policy and its preflight/audit/apply tool. It **cannot itself install GitHub branch rulesets**. Activation uses a separately authenticated repository administrator through `gh api` after independent review. The standard GitHub connector does not expose ruleset PATCH/PUT/POST writes. Never add a GitHub Actions repository-admin token or permanent bypass to make this happen automatically.

**Core stage:** require a PR, at least one independent approval, dismiss stale reviews, require last-pusher-independent approval, resolve review conversations, forbid force pushes and deletion. Zero bypass actors. Existing merge/squash/rebase remain available. Applied to default branch only.

**Full stage:** all core controls plus strict required checks. Checks are repository-specific and remain **candidate/UNVERIFIED** until proven on a live PR exact head. Never promote a path-filtered/manual workflow or an ambiguous check name to a globally required context.

## Initial four-repository map

| Repository | Branch | Ruleset | Full-stage candidates | Special prerequisite |
|---|---|---|---|---|
| ABACUS | main | Reuse #24494381 | PR Feedback Gate; ABACUS compatibility gate | Repair active empty ruleset, validate exact-head check contexts |
| CODEX | main | New CODEX Main Hard Gate | governance-gate; test | Migrate bot's direct-main metrics publisher to PR/artifact; confirm check name uniqueness |
| cryoplant-project (QPS) | main | New QPS Main Hard Gate | None yet (FULL HOLD) | Private repository plan entitlement, independent engineering reviewer, always-present PR check |
| pipeline-automation-hub | master | New Mission Control Master Hard Gate | First-Pass Closure Gate / first-pass-closure | Confirm trusted publisher status on the candidate head and independent review |

Full-stage names are **proposed**, not verified admission settings. At 2026-10-14 readback, all four branches report `protected=false`, ABACUS #24494381 has an empty `rules` array, other rulesets are absent. See `baseline_20261014.json` for SHA-specific measurements.

## Execution - repository owner/admin (not CI)

Prerequisites: `gh auth status`; account with repository rules administration permission; independent eligible reviewer with access (author cannot approve own PR); inventory and migrate every direct push to default from CI publishers. For QPS confirm GitHub plan supports rulesets on private repositories. No blanket bot/owner bypass.

Run from the Mission Control repository root after reviewing the governance PR:

```bash
python -m unittest discover -s governance/branch_protection -p 'test_*.py' -v
python governance/branch_protection/ctl.py --repo GBOGEB/ABACUS --mode plan --stage core
python governance/branch_protection/ctl.py --repo GBOGEB/ABACUS --mode audit --stage core
```

Once the explicit reviewer and PR-safe publisher prerequisites have been verified, an administrator can activate **one repository at a time**:

```bash
python governance/branch_protection/ctl.py --repo GBOGEB/ABACUS --mode apply --stage core --confirm-repo GBOGEB/ABACUS --reviewer-ready --publishers-migrated
python governance/branch_protection/ctl.py --repo GBOGEB/ABACUS --mode audit --stage core
```

Repeat only after fresh, repo-specific validation for CODEX, QPS, and Mission Control. This call **updates** ABACUS ruleset #24494381 instead of creating a competing ruleset. Other repositories use POST only when the named ruleset is absent. Unknown live rules, ID changes, unapproved downgrade, reviewer/publisher prerequisites, insufficient rights, or missing full-stage required checks yield HOLD.

For FULL, provide a recent, representative PR whose head has all contexts in successful terminal state. Example (do not run until PR number and required contexts are validated):

```bash
python governance/branch_protection/ctl.py --repo GBOGEB/ABACUS --mode apply --stage full --confirm-repo GBOGEB/ABACUS --reviewer-ready --publishers-migrated --probe-pr PR_NUMBER
```

A single successfully checked PR cannot establish that context is emitted for every future PR; before full promotion inspect trigger filtering, fork handling, action permissions, name collisions, and GitHub's required-status UI. Never silently remove or rename a required check because it is red. Migrate publishers through PRs/artifacts rather than granting always-on bypass.

## Definition of verification (per repo, exact HEAD)

1. Re-read `GET /repos/{owner}/{repo}/branches/{default}`: `protected=true` and exact head SHA captured.
2. Re-read ruleset by ID: enforcement active, targets default branch, required pull-request approval, non-fast-forward, deletion prevention, no bypass.
3. On a throwaway PR (not main): prove an unapproved PR cannot merge; an unresolved thread cannot merge; exact-head pending/failed required check blocks FULL-stage merge. Capture UI/API result without completing an unauthorized merge.
4. Prove a later distinct SHA with completed native checks and independent approval is eligible, but do not self-approve or merge as part of the probe.
5. Capture before/after ruleset JSON and run/job links. Record effective status only after these receipts; until then protection remains `UNKNOWN` or `HOLD`.

GitHub docs: https://docs.github.com/en/rest/repos/rules ; https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets ; https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks .
