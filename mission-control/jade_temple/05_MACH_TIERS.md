# MACH IIb / III / IV — proposed control profiles, not deployed rules

> **Doc** JT-05 · **Status** PROPOSAL · **Release** UNNAMED (owner sets SemVer) · **Admission** `MERGE_ADMISSION=HOLD` · **Updated** 2026-10-31

| Profile | Candidate scope | Must retain | Additional expectation |
|---|---|---|---|
| MACH IIb (diagnostic / pilot) | Upstream forks, reference repos, early doc pilots | No privilege bypass, security non-relaxation, immutable evidence, owner/applicability decision; **cannot claim governed admission** without full independent gates | Collect gap baseline, first-red identities and workflow names before proposing adoption |
| MACH III (normal qualified) | Active Top21 first-party source/release lanes | Exact SHA native required jobs; security; stale-dismiss; last-push approval; review thread resolution; up-to-date branch, no force-push/deletion, eligible human approval, negative RED canary | Proposed default J4 qualification control only after actual admin enactment/readback |
| MACH IV (high-consequence) | QPS engineering/source-control critical and cross-repo release-critical fan-in | Everything in MACH III; domain owner acceptance and no authority transfer | Independent release evidence, 2nd eligible approval where practical, cross-repo provenance handshakes, artifact provenance/rollback and release/host page readback |

**P0 factual guard:** ABACUS `24494381` was read back on 2026-10-18 as active, but its pull_request rule still specified **0 required approvals**, **no required last-push approval** and **no required resolved threads**. No required status-check rule was observed in the returned ruleset. Protected branch flag alone does not establish effective protection. Therefore MERGE_ADMISSION=HOLD until an eligible admin restores the independently required protections and a rejected RED canary is evidenced.

Do not treat `MACH III` proposals, GitHub ruleset names, labels, or human checklist ticks as equivalent to effective active server-side protection. No unilateral waiver, no short-term break-glass implicitly enabled, and no B0/CodeQL/A10/Safety gate suppression.

---

**Nav:** [← 04 Root SPINE contract](04_REPO_ROOT_SPINE_CONTRACT.md) · [Index](00_START_HERE.md) · [06 Wave plan →](06_WAVE_PLAN.md)
