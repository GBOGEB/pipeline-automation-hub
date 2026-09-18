# HM-01 R3 / W275 — MissionControl Lossless Federation Handover v2

## Why v2 exists

MissionControl #204 merged v1 at
`70840fb944dd7cc2a6d2593a58e6d7d33fe56230`. Its review identified one
temporal-provenance wording defect: the ABACUS release-support proof at
`f55876e4...` must not be described as floating/current main after later ABACUS
commits exist.

v1 remains immutable provenance. v2 corrects forward.

## Exact restart truth

R3 predecessor source:
`70964e5f1577231512f4104b26f5f6649ad8cb39`.

Active production successor:
`1248290ca0a9d55ec83d0efa0235ed1a45a88eeb`.

QPS execution/control lineage:
#1451 → #1452 → #1453 → #1460.

MissionControl selector:
#199.

GEMINI producer:
#17.

The exact portable environment is already proven:
run `35338333168`, job `105578279671`, artifact `10543767484`,
digest
`sha256:9a961d69becd02bac3c2c16146f29ced1a9185204cce2e1f381eddfb6465aaa5`,
Python 3.12.14, relocated self-test PASS, exact six-package lock PASS.

Therefore the only missing physical R3 input is genuine Git objects carrying
exact successor `1248290ca0a9d55ec83d0efa0235ed1a45a88eeb`.

## ABACUS provenance correction

The QPS-facing support evidence is an immutable exact proof at
`f55876e4d7985dd672304ff6e3945f24de9b9194`, run `35272680285`.

It is not a claim that current ABACUS main equals that SHA, and later ABACUS
main commits do not inherit the PASS.

The proof contains five target-job PASS results, pytest 402 passed / 0 failed
from 415 collected, and artifact `10518602763` with SHA-256
`2904d3cc2ef3f359b98db0b75bd2613436b94395b975ccf807c08a8c1d793b7f`.

#1263 merged the v0.2 receipt. #1265 is unmerged race provenance. #1267 merged
at `421d70842da08876d882bf16a9a8cfa2eb07baee` and makes
exact-proof-vs-floating-current semantics explicit. Legacy Deploy Artifacts failure remains separate governance debt.

## 3P* state

3PR Refresh / Probe / Rank: PASS for the bounded control transaction.

MIP:
- Modernize: QPS #1451.
- Innovate: QPS #1452 + GEMINI exact environment.
- Perpetuate: QPS #1453 + #1460 + this MissionControl v2 fix-forward.

3PC:
- Prepare = PASS.
- Prove = HOLD_WAIT_SUCCESSOR_GIT_OBJECT.
- Commit = HOLD_WAIT_PROVE.

3P3 remains unauthorized.

## Next execution

Obtain a genuine bundle/clone carrying exact `1248290c...`. Verify the Git
object, pair it with the already-proven exact-environment capsule, and run the
existing QPS portable-capsule consumer unchanged. Bind exact input hashes,
worktree SHA, five product hashes, structural QA, projection-aware parity,
render evidence, explicit hash-bound visual inspection and successor acceptance.

Only actual `PASS_R3_RELEASE_PRODUCTION_DOV` permits R4.

## Guards

#923 remains RED_OWNER_ACTION.
GT_BDQ_0 remains RED_BLOCKED_ON_923_INFRA_PREEXECUTION.
R3 does not inherit/burn canonical GT_BDQ_4–7.
Runtime GOLD remains withheld.
Authority transfer=false.
Engineering, negotiation and formal credit deltas remain zero.
