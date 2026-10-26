# CODE PURPLE W+2 — six-repo ruleset owner preflight

This document is an **owner/admin action queue**. Neither this PR nor its
read-only probe applies rulesets, deletes protection, grants bypass, marks
an unobserved rule missing or declares merge admission.

## Observed baseline (historical, NOT a current probe)

P-process snapshot `2026-10-18T13:29:50Z` recorded six repositories as RED.
The previous implementation collapsed inaccessible API responses into synthetic
"missing" rules. The new `verify_rulesets.probe_status` distinguishes
`CONFIRMED_DRIFT` from `UNKNOWN_API_READBACK`; both remain fail closed.

| Repo | Handover candidate | Owner evidence needed |
|---|---|---|
| ABACUS | `ABACUS.hard.json` and existing 24494381 | Confirm all required checks are unconditionally reported by **GitHub Actions integration 15368**; then restore rules, one independent approval, dismiss stale, last-push approval, required review-thread resolution and strict checks |
| CODEX | `CODEX.basic.json` | Confirm exact default branch/effective rules and authorized maintainer disposition |
| cryoplant-project | `cryoplant-project.basic.json` | Private read authority; no inferred QPS engineering acceptance |
| gg_MATH | `gg_MATH.basic.json` | Confirm exact check producers and branch scope |
| Q_engineering_tools | `Q_engineering_tools.basic.json` | Confirm effective check/run identity |
| pipeline-automation-hub | `pipeline-automation-hub.basic.json` | Retarget/reconcile ruleset 25252917; do not require path-filtered `audit` |

### Critical ABACUS safety distinction

**`ABACUS.basic.json` is NOT the same as the required one-approval hard gate.**
Its review approval count is **0** and it does not request a strict up-to-date
status-check policy. It cannot by itself establish the independent approval
or strict main requirements. The proposed `ABACUS.hard.json` specifies one
approval, last-push review, resolved threads, strict required checks; it must be
reviewed against actual GitHub check providers and existing authorization before
an owner PUT/POST.

### Read-only command examples for an authorized PowerShell terminal

```powershell
# If gh is missing: winget install --id GitHub.cli --exact
gh auth login
gh api repos/GBOGEB/ABACUS/rulesets/24494381
gh api repos/GBOGEB/ABACUS/rules/branches/main
gh api repos/GBOGEB/pipeline-automation-hub/rulesets/25252917
pwsh -File ./regenerate.ps1    # P-process repo directory, live readback with gh login
```

Do **not** create or update any ruleset as an automated side effect of refresh.
After an owner applies and validates a reviewed rule set, rerun the live probe
and capture the exact effective `(context,integration_id)` pairs and both
positive and negative merge canaries. The negative RED canary must be denied;
GREEN requires required CI, independent eligible approval, security and thread
resolution. Repository native ruleset state—not an HTML badge—makes this decision.

**Until such evidence exists:** `CODE_PURPLE=NOT_LIFTED`,
`MERGE_ADMISSION=HOLD`; historical #701 merge does not receive gated-admission
credit simply because main advanced.
