# CODE PURPLE governed landing — N3 read-only admission probe

This module is a **non-authoritative, GET-only audit of the external GitHub governance surface**, not another metric producer, not a replacement for `mission-control/gogreen/required_gate/gate.py`, and never a merge/release action.

## What it measures

It freezes a candidate PR's exact head twice, reads active hub ruleset #25789280 and its default-branch target, checks approval requirements and bypass actors, tests strict up-to-date/status context policy, filters exact-head native completed check runs, and rejects bot/self/stale/non-APPROVED reviews. It reports 14 explicit noncompensating gates with PASS/HOLD states and incomplete populations shown as HOLD.

**Critical evidence absences:** GitHub REST cannot prove GraphQL review-thread resolution or actual platform rejection of a RED canary in this bounded collector. Both remain HOLD unconditionally, even if the repository's latest native CI is all green. A human-supplied JSON result or a green automation is **not** a verified approval. The result sets `merge_allowed=false`, `authority_transfer=false`, `formal_engineering_credit_delta=0` by construction.

The read-only workflow runs offline adversarial tests and (where token permissions permit) collects bounded actual GitHub GET data into a private Actions artifact. It does not change a ruleset, queue, PR, reviewer, secret, CODE PURPLE watch, or QPS engineering source.

## Local/native usage

```bash
python -m unittest discover -s mission-control/gogreen/tests -p 'test_governed_landing_probe.py' -v
GITHUB_TOKEN="<repo-read-token>" python mission-control/gogreen/required_gate/governed_landing_probe.py --pr 881 --out /tmp/governed-881.json
```

For native Actions run, use the `CODE PURPLE Governed Landing Readback` workflow, selecting a candidate PR number. The workflow emits `GOVERNED_READBACK_HOLD_IS_CORRECT=PASS` if it correctly refuses unproven admission. **Do not interpret a green workflow as a green merge gate.** Missing token or restricted ruleset reads remain explicit `UNKNOWN_ACCESS_OR_RUNTIME`, never zero.

## Actual blockers as of 26 Oct 2026 census

Hub ruleset #25789280 is active with named checks and zero bypass actors, but `required_approving_review_count=0`, `require_last_push_approval=false`, and `strict_required_status_checks_policy=false`. Independent human approval and platform-blocked RED canary are not established. Protected branch access through the installed integration returned HTTP 403. CODE PURPLE watch stack #881 → #882 → #890 → #891 and the separate #894 advisory-lock and #893 dashboard lanes therefore remain `MERGE_ADMISSION=HOLD` until actual governing evidence exists.

**Safety**: No private cryoplant project PR/run/issue identifiers, vendor originals, auth credentials or protected QPS data are exported. No QPS owner acceptance is granted. After ruleset remediation by an authorized owner, independently validate current exact-head CI, final head human review, GraphQL resolved threads, actual blocked RED canary, then run the probe again; only a separate authorized merge decision can land the stack.
