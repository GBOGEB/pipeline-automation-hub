# Recursive cross-chat continuity — JADE wrapper over canonical CP.HANDOFF/RESUME

> **Doc** JT-07 · **Status** ACTIVE · **Release** UNNAMED (owner sets SemVer) · **Admission** `MERGE_ADMISSION=HOLD` · **Updated** 2026-10-31

This is a **project-facing protocol**, not a parallel SSOT, API, dispatcher, or new Mission Control process. Canonical: ABACUS `handover/HANDOVER_MESSAGE_TEMPLATE.md`, `tools/handover_v2/process_spec.json`; Mission Control `mission-control/v2/handoff/CP_HANDOFF_RESUME_V1.json`. A local sealed bundle is GitHub-first operational fidelity, NOT canonical V2 schema + replay unless separately verified.

## At every chat beginning

`CP.RESUME(source="GITHUB_FIRST", mode="VERIFY_REFRESH_EXECUTE", horizon="G3P:N_TO_N_PLUS_3")`

1. Read `DROPIN_NEXT_CHAT.md`, active `data/JADE_STATE.json`, `data/SOURCE_REGISTRY.json`, and canonical GitHub pointers. Verify byte manifest if archive supplied.
2. Refresh actual `TOP21_COHORT_ROSTER.json` and first-21 default commits, latest eligible PRs, issues/roots, protection/rulesets, required CI job/attempt/step, security and hosted page/served asset hashes.
3. Compare to previous snapshot as NON-ATOMIC; invalidate stale/changed heads. Do not collapse different metric denominators or mark unknown as zero.
4. Pick one owner-safe slice with explicit dependency lease. If a native P0 gate is blocked, report owner action and stop, not fake an extra wave.

## At milestones AND before ending every chat

`CP.HANDOFF(scope="CURRENT_SESSION", mode="GITHUB_FIRST_OPERATIONAL", horizon="G3P:N_TO_N_PLUS_3")`

- Append a dated checkpoint with objective, activity log, repo SHA crosswalk, PR identity, native proof/status including unknowns, control gates, linked issues, first-red/BD root, baseline vs actual vs qualified forecast, next disjoint action and explicit stop cause.
- Maintain a 1-page `DROPIN_NEXT_CHAT.md` pointing to GitHub (prefer primary discoverable README/pointer); do not require entire chat or large upload to resume when canonical evidence exists online.
- SHA256 every changed artifact; preserve previous manifest root and source archive links. Prior capsules remain immutable. No self-hash recursion; prove ZIP CRC and each manifest entry. A manifest proves integrity, not GitHub provenance/signature.
- Do not suppress dissenting negative evidence or convert a plan to an executed run. Handover fidelity must say exactly what bytes, logs and prior chats were available.

## Minimum checkpoint records

`project_id`, `wave_id`, `obs_utc`, `head_snapshot` array `{repo, branch, sha, read_at}`, `source_registry`, `native_receipts` (run, attempt, job, step, artifact sha), `metric_ledger` (numerator/denominator/instrumentor), `owners_and_leases`, `first_red_roots`, `governance_gates`, `pages_evidence`, `items_open`, `decisions`, `next_admissible_action`, `predecessor_root_hash`, `archive_manifest_hash`.

GitHub-first is preferred; a sealed ZIP supplements indispensable local bytes. The user must create the ChatGPT Project manually because this tooling cannot create a ChatGPT Projects workspace directly.

---

**Nav:** [← 06 Wave plan](06_WAVE_PLAN.md) · [Index](00_START_HERE.md) · [08 Bootstrap PR →](08_PR_READY.md)
