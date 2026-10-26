# Owner kit: import the BASIC branch rulesets

Branch protection is red in every focus repo, and only a repo admin can fix it.
This folder turns that fix into one command. Agents only run the read-only
modes; the write (`--apply`) is yours.

## The one-liner

From a checkout of `pipeline-automation-hub` at `master`, logged in with `gh` as the owner:

```powershell
python scripts/owner/apply_rulesets.py --apply
```

If `gh` answers `401 Bad credentials`, a stale token in the environment is
overriding your keyring login. Clear it first, then rerun the command:
`Remove-Item Env:GITHUB_TOKEN, Env:GH_TOKEN -ErrorAction SilentlyContinue`
(PowerShell) or `unset GITHUB_TOKEN GH_TOKEN` (bash).

Run the command without `--apply` first to see the plan. That dry run is the
default and never writes anything.

| Command | Effect |
|---|---|
| `python scripts/owner/apply_rulesets.py` | Dry run. Prints CREATE / UPDATE / NOOP per repo, with a field diff for updates. |
| `... --apply` | Makes the POST/PUT calls, then reads the result back and verifies it. |
| `... --verify` | Read-only recurring check: is the BASIC ruleset active and effective? Exits 1 if any repo is red. |
| `... --repo ABACUS` | Only that repo (`OWNER/NAME` or `NAME`). You can repeat the flag. |
| `... --tier hard` | Uses `hard_file` from the manifest (today only `ABACUS.hard.json`). Repos without one are skipped. |
| `... --json` | Machine-readable output, for use in CI or in a PR body. |

## What `--apply` changes

The script reads `mission-control/qps-triage-ultra/p-process/rulesets/manifest.json`
and the `*.basic.json` files it lists. It never writes to that folder. For each of the
six repos (ABACUS, CODEX, cryoplant-project, gg_MATH, pipeline-automation-hub,
Q_engineering_tools):

- If no ruleset named `P-BASIC <repo> default branch` exists, it POSTs (creates) one.
- If one with that name exists and differs from the file, it PUTs (updates) it by id.
  The PUT replaces the whole rule list, and the dry run shows any rule it will drop.
- Each ruleset targets `~DEFAULT_BRANCH` and is `active` with no bypass actors. It adds
  these rules: block deletion, block force-push, require a PR (0 approvals, stale reviews
  dismissed, review threads resolved), and require the status checks listed in the
  manifest, pinned to GitHub Actions (integration 15368) and not strict. The hub also gets
  linear history and Copilot review.
- Other rulesets are never deleted or edited. The script has no delete path, and its
  `gh` wrapper refuses `DELETE`.

The dry run on 2026-10-23 showed 6 CREATEs (no repo has a `P-BASIC` ruleset yet). Each
repo already has one older ruleset, and in CODEX, cryoplant-project, gg_MATH and
pipeline-automation-hub that ruleset is **active but targets no branch**, so it enforces
nothing. After the apply, `--verify` turns green for the BASIC ruleset. The EVERRED drift
probe (`verify_rulesets.py`, shown as `drift-probe=`) stays `CONFIRMED_DRIFT` until you
disable or retarget those empty rulesets (see Rollback below for the disable command).
Both checks reuse `verify_rulesets.gaps`/`probe_status` and do not copy them.

## Rollback (disable, never delete)

Get the ruleset id from the `--apply` or `--verify` output, then run:

```powershell
gh api -X PUT repos/GBOGEB/<REPO>/rulesets/<ID> -f enforcement=disabled
```

or open Settings -> Rules -> Rulesets -> the ruleset -> Enforcement status: Disabled.
A disabled ruleset keeps its configuration. Running `--apply` again turns it back on
(the dry run shows this as `enforcement: "disabled" -> "active"`). For a one-off
emergency merge, add yourself as a bypass actor in the UI. Do not delete rules.

## Should BASIC require `First-Pass Closure Gate / first-pass-closure`?

**What the JSON does today:** no BASIC file lists it. For the hub, the required checks are
`validate-ultra-control`, `canonical-self-test-and-mutation` and `GOGREEN required gate`. The
gate is not in `manifest.json` either.

`GOGREEN required gate` is the one owner-approved exception to the 90% bar below. On the last 12
merged PRs (#814-#831) it ran on all 12 and passed 9. The three failures (#815, #820, #821) were
true reds that merged with the JADE suite red, not flakes. It is the MACH-II compensating check
for the solo-owner review waiver, so it has to be enforced by the platform.

**Recommendation: do not require it yet.** Add it only after the PR template carries the
first-pass-closure receipt. Another worker is adding that receipt in a separate PR. The
reasons:

- The gate fails closed on PRs whose body does not contain the receipt. Until the template
  includes the receipt, requiring the check would block almost every PR.
- The gate reports through a **commit status** that the workflow posts (`gh api .../statuses`).
  It is not a plain check run. The job also skips draft PRs. Before you require it, confirm
  which integration id GitHub records for that status context, and pin the requirement to
  that id. Otherwise the requirement either never matches or can be satisfied by another
  app posting the same context.
- BASIC deliberately requires only checks that run on every PR and passed on at least 90%
  of the last 12 merged PRs (see `build_rulesets.py`). Once the receipt is in the template
  and the gate meets that bar, add it in `build_rulesets.py` (the p-process folder has its
  own review flow), regenerate the files, and rerun this script. The plan will show it as
  an UPDATE.

## Tests

```bash
python scripts/owner/tests/test_apply_rulesets.py
```

All `gh` calls are mocked. The tests cover the plan (create, update by name, noop, and
error on duplicate names), confirm that a dry run never writes, check that apply makes
exactly one POST or PUT and then reads the result back, and confirm that `--verify` is
read-only and reports UNKNOWN (not missing) when the API is unavailable.
