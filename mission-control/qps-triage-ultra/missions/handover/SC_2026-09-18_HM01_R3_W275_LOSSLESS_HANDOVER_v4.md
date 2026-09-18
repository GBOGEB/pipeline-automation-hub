# HM-01 R3 / W275 — MissionControl Lossless Federation Handover v4

## Current governed position

QPS #1470 is the current W275 restart authority for this lane. It consumes the
merged Windows-native successor-object producer from GEMINI #20 and makes that
producer discoverable from `SESSION_CLOSE_CURRENT.yaml`.

The dependency cone is now reduced to one physical return:

`PHYSICAL_SUCCESSOR_GIT_BUNDLE_RETURN_1248290C`

Required exact successor:

`1248290ca0a9d55ec83d0efa0235ed1a45a88eeb`

## What is already PASS

- R3 application evidence: PASS.
- Capsule-v2 exact environment: PASS and independently relocation-reproved.
- QPS capsule-v2 validator alignment: PASS via #1468.
- Windows-native Git-object producer capability: PASS/MERGED via GEMINI #20.
- QPS producer-readiness consumption: PASS via #1469.
- QPS restart discoverability of producer path: PASS via #1470.
- 3PC Prepare: PASS.

The producer path is worktree-neutral: it fetches and proves the exact object
without checkout/reset, preserves the user's historical branch and untracked
files, creates a temporary namespaced ref, verifies the bundle, emits a SHA-256
sidecar and machine receipt, then removes the temporary ref.

## Physical first red

The following three files must physically return from the authentic Windows QPS clone:

- `QPS_R3_1248290c.bundle`
- `QPS_R3_1248290c.bundle.sha256`
- `QPS_R3_1248290c.bundle.receipt.json`

Latest connected Drive scan of `Handover_Bundle_QPLANT` found no qualifying bundle.
Do not substitute a source ZIP, connector reconstruction, predecessor bundle,
release pack, or capsule artifact.

Operator command preserved by QPS #1470:

`powershell -ExecutionPolicy Bypass -File .\scripts\build_qps_r3_successor_handoff.ps1 -QpsClone "C:\Users\gbonthuy\cryoplant-project" -OutDir ".\output\r3_successor_handoff"`

## After physical return

1. Verify sidecar SHA-256 against the bundle bytes.
2. Run `git bundle verify`.
3. Verify the advertised object is exact successor `1248290c...`.
4. Import/materialize the exact detached worktree.
5. Pair it with the already-proven capsule-v2 bytes.
6. Run the merged QPS portable-capsule consumer.
7. Regenerate all five products.
8. Run structural QA and projection-aware parity.
9. Produce render evidence.
10. Complete explicit hash-bound human visual inspection.
11. Run the successor acceptance validator.
12. Only `PASS_R3_RELEASE_PRODUCTION_DOV` releases R4.

## Append-only correction

MissionControl #208/#212 and federation receipt v0.3 remain immutable predecessor
history. v0.3 contains a future-dated `as_of` metadata defect. This v4 receipt
does not rewrite that evidence; it uses exact Git merge/commit anchors for ordering
and records the defect explicitly.

## Non-compensation

`#923=RED_OWNER_ACTION`

`GT_BDQ_0=RED_BLOCKED_ON_923_INFRA_PREEXECUTION`

Runtime GOLD remains WITHHELD. Canonical GT credit remains NONE.
`authority_transfer=false`; engineering, negotiation and formal credit deltas remain zero.

3PC Prove remains `HOLD_WAIT_PHYSICAL_SUCCESSOR_GIT_BUNDLE`.
3PC Commit remains `HOLD_WAIT_PROVE`.
3P3 remains NOT AUTHORIZED.
R4 remains BLOCKED_NOT_NEXT.
