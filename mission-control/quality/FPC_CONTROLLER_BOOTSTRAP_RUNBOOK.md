# Runbook: landing a change to the First-Pass Closure controller

This is how to merge a PR that touches `protected_control_paths` in `FIRST_PASS_CLOSURE_POLICY_v1.json`, under `controller_maintenance`. It is based on #1139 and its canary #1160 (2026-11-09).

## Why the gate stays red

- The PR's own gate fails with `CONTROL_PLANE_CHANGE_REQUIRES_BOOTSTRAP`, by design: a controller change must not certify itself.
- No code change can turn that check green. Don't try to "fix" it.
- The default-branch ruleset (25789280, "P-BASIC") lists the gate as required and has **no bypass actors** (`current_user_can_bypass: never`). So not even the owner can merge from the PR page until a bypass is added on purpose.

## Before the merge (all on the exact head)

1. **Proof:** the exact-head proof run (First-Pass Closure Proof) succeeds.
2. **Review:** Codex's code review shows `status: completed` with `commit_sha` equal to the full head SHA and zero material P1 or P2 findings.
   - **A master merge into the branch moves the head**, so request a new review afterwards (`@codex review`).
   - **Usage limit:** when Codex hits its review usage limit, the state reads `status: failed`, and the gate reports `CODEX_REVIEW_NOT_COMPLETED_ON_EXACT_HEAD`. Re-request once the quota resets; nothing in the PR needs changing.
3. **Receipt:** run `python scripts/fpc_receipt.py --pr <n> --write`, then read the body back and check that the receipt's `head_sha` equals the head.
4. **Checks:** every other required check is green. The only acceptable red is `first-pass-closure` with exactly `CONTROL_PLANE_CHANGE_REQUIRES_BOOTSTRAP`.
5. **Issues:** the PR closes no issue that the policy's `closure_rule` keeps open until the canary passes.

## The merge (owner only)

1. In the ruleset, add a bypass for **Repository admin**, mode **For pull requests only**, and save.
2. On the PR, tick **Merge without waiting for requirements to be met (bypass rules)**, then **Squash and merge**. Put `[bootstrap]` in the title.
3. Remove the bypass and save.
4. Verify that the bypass is gone:

   ```powershell
   $env:GITHUB_TOKEN=$null; gh api repos/GBOGEB/pipeline-automation-hub/rulesets/25789280 --jq '.bypass_actors, .current_user_can_bypass'
   ```

   It must print `[]` and `never`.

The ruleset history and its rule-suite result `bypass` are the audit trail. #1139 had the bypass open for about one minute.

An agent can't do this step. Ruleset edits are a security setting, and Claude Code's auto mode refuses `gh pr merge --admin`.

## After the merge: canary

- **What to change:** open a separate PR that touches no protected path. By convention it adds metadata only, in this folder:
  - a bootstrap receipt (`FPC_PR<n>_BOOTSTRAP_RECEIPT_<date>_v1.yaml`);
  - a canary record (`FPC_POST_PR<n>_CANARY_<date>_v1.yaml`).
- **Acceptance:** `CANARY_HEAD_BOUND_REQUIRED_STATUS_SUCCESS`. The gate, now running master's new controller, passes on the canary's exact head.
- **Merge:** normally, never with a bypass.
- **Receipt timestamps:** a receipt's `as_of` is the **observation cutoff**. It is never the time of an event it records. It must be at or after every observation in the file, so record event times such as `merged_at` and `verified_at` in their own fields. (Codex P2 on #1160.)

## External risk: `pull_request_target`

- **The brownout:** on 2026-11-09, from 16:28 to 18:00 UTC, GitHub ran a scheduled brownout of the default `pull_request_target` protection for public repositories. During it, every gate run triggered by `pull_request_target` ended in `startup_failure`; runs triggered by `pull_request_review` and `workflow_run` still started. The run page's annotation names the cause. The REST API only says "likely a workflow file issue".
- **When the default becomes permanent:** the required gate will not start on PR opened, synchronize or edited events.
- **Owner decision:** explicitly allow `pull_request_target` in a repository or organisation Actions event policy, or change the gate's triggers. See https://gh.io/securely-using-pull_request_target#default-policy-for-pull_request_target.
