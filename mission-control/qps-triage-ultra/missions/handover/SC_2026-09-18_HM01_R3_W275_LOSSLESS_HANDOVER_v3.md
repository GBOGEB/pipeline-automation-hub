# HM-01 R3 / W275 — MissionControl Lossless Federation Handover v3

## Canonical restart

QPS #1465 is the current W275 reconciliation authority for this lane and merged
at `8ae7d5ca9b010b6c2978a03b7b16898e172c8918`.

Read:
1. `triage/w275/QPS_W275_R3_3PSTAR_MIP_RECURSIVE_CONTROL_v0.2.yaml`
2. `handover/session/SC_2026-09-18_W275_R3_3PSTAR_MIP_LOSSLESS_HANDOVER_v2.md`
3. `handover/session/RESTART_DROPIN_2026-09-18_W275_R3_v2.md`

MissionControl #204 and #207 remain immutable earlier federation states. This
v3 corrects forward to the QPS capsule-v2 evidence.

## Current exact environment

Capsule v1 from GEMINI #17 is historical: producer tests passed, but independent
external relocation exposed a missing runtime library path.

Current accepted environment proof is GEMINI #18/#19:
- #18 merge `8b8e72400bb6860789b11b1fca3b809fc8ca6524`
- exact producer head `1192e030d76bc88dbfb6c735f0f11d02528a7b4e`
- run `35339129647`
- artifact `10544103232`
- artifact ZIP SHA-256
  `64c363cfeaded7fc6b156b28fe344166e3c560aac3ea43f50b2695220cffd912`
- inner archive SHA-256
  `c77566e6c6aa261034f86303ef1be7b033622f357333e3d474d3bde8fb3ec44e`
- manifest `gmi.r3_successor.exact_env_capsule.v2`
- launcher `r3-python/run-python`
- external clean-`LD_LIBRARY_PATH` relocation PASS
- Python 3.12.14 + exact six-package lock PASS
- #19 validator-hygiene merge
  `9faeb10cd57395538eb163791c7c56ba90be711b`

## ABACUS support

ABACUS support proof remains bound only to exact tested SHA
`f55876e4d7985dd672304ff6e3945f24de9b9194`, run `35272680285`.
Fix-forward PR #1267 merged at
`421d70842da08876d882bf16a9a8cfa2eb07baee`, explicitly preventing later
floating main from inheriting that PASS.

## Current first red

Only one physical R3 prerequisite remains:
`SUCCESSOR_GIT_OBJECT_HANDOFF_1248290C`.

Accept a genuine `QPS_R3_1248290c.bundle` plus matching SHA-256 sidecar from
an authentic private QPS clone, or an equivalent clean clone archive containing
`.git` and exact commit
`1248290ca0a9d55ec83d0efa0235ed1a45a88eeb`.

Reject source-only archives, connector reconstruction, predecessor bundles and
capsule v1.

## Execution after return

Verify the Git object, pair it with the exact capsule-v2 bytes, and run the
current QPS consumer unchanged. Bind worktree SHA, product hashes, structural
QA, projection-aware parity, render evidence, hash-bound human visual
inspection and successor acceptance.

Only `PASS_R3_RELEASE_PRODUCTION_DOV` releases R4.

3PC Prepare = PASS.
3PC Prove = HOLD_WAIT_SUCCESSOR_GIT_OBJECT.
3PC Commit = HOLD_WAIT_PROVE.
3P3 = NOT_AUTHORIZED.
R4 = BLOCKED_NOT_NEXT.

#923 and GT_BDQ_0 remain RED/non-compensating. Runtime GOLD is withheld.
Canonical GT_BDQ_4–7 credit is NONE. Authority transfer=false; engineering,
negotiation and formal credit deltas remain zero.
