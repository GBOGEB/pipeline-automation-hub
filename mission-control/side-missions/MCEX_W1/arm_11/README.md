# MCEX-W1 arm 11 — combined

**Side mission / experiment only.** Independent sibling branch from hub `master@0b6a6f1a062ecdcba4e532aa101735b54ab09911`. PR targets master; no other arm's branch is a parent or peer dependency.

Factorial factors: `simulate_local_shadow=true` and `stage_remote_readonly_return=true`. Both only affect **offers in a pure in-memory simulation**, not any GitHub/CODEX gateway setting. The real owner gateway remains `mutation_enabled:false`, `enabled_mutation_transports:[]`; no repo write, merge, force push, privilege grant, or remotely executed dispatch is possible in this workflow.

Fixed population: two synthetic positives + twenty adversarial controls; exact same `probe.mjs` and `test.mjs` text across all arms. This intentional branch-local duplication avoids cross-branch imports during the trial. It should be pruned to one canonical winner after comparison, not kept as a second execution stack.

Read-only CI: `node --test test.mjs` and `node emit.mjs receipt.json`. Native runner status can be promoted only after an exact-head terminal GitHub run/job/attempt + artifact digest. The emitted receipt itself is a **synthetic fixture** with no real approval, no external-run authentication, no persisted replay ledger, no QPS engineering acceptance, and no Pages publication proof.

Source facts: CODEX main `493145eea784d39f57ea64a730af9f3e85586714`, [bounded apply planner](https://github.com/GBOGEB/CODEX/blob/493145eea784d39f57ea64a730af9f3e85586714/scripts/missioncontrol_bounded_apply.py), [gateway contract](https://github.com/GBOGEB/CODEX/blob/493145eea784d39f57ea64a730af9f3e85586714/mission_control/mycelium/execution_gateway_contract.yaml); hub baseline `0b6a6f1a062ecdcba4e532aa101735b54ab09911`. These are observation pins, not applied changes.

Acceptance: compare same input cohort, negative guard yield, false-green rate, simulated offers and native test result; then select a preferred design. **No arm grants or requests merge admission**. Each root gate (native CI, independent review, security, owner acceptance) retains an independent decision.
