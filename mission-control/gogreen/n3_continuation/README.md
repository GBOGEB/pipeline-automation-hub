# CODE PURPLE / GoGREEN — 3PSTAR governed N→N+3 continuation

**Canonical owner:** Mission Control's [global glossary/taxonomy v2](../../v2/MC_GLOSSARY_TAXONOMY_v2.json), extension `n3_continuation_extension`. This is a read-only method/receipt projection, not a new BD/REX/engineering SSOT.

## Definitions and monikers

| Human call | Machine token | Meaning |
|---|---|---|
| **3P*** | `3PSTAR` | Three **successive measured pulses**: N→N+1→N+2→N+3 |
| **3W*** | `3WSTAR` | Three coordinated waves, possibly overlapping and containing multiple pulses |
| **N3!** | `N3_CONTINUE` | One bounded active invocation of 3PSTAR using the currently bound N |
| Historical 3PR | `3PR` | Refresh → Probe → Rank, unchanged |
| Historical 3PC | `3PC` | Prepare → Prove → Commit, unchanged; not an automatic merge |

A **pulse** is one bounded evidence→decision→action→measurement feedback cycle with an append-only source-bound checkpoint. A **wave** is a work-scheduling group with independent worker/PR lanes and integration barriers. **3 waves ≠ 3 pulses**, just as 3 green runs, 3 PRs or 3 commits ≠ three N+i checkpoints.

Identity grammar is fully qualified: `owner/repo::mission_id::N3-<execution_id>::PULSE-<1|2|3>`; bare `W3`, `P3` and PR numbers are not global IDs. Historical `3PR`, `3PC`, `3P3` and `W###` context is not rewritten.

## How the N3! run operates

| Pulse checkpoint | Aim | Bounded autonomous action | Required proof |
|---|---|---|---|
| P1 → N+1: RECONCILE/MEASURE | Fresh source census, positive code capabilities, root-first-red attribution and denominator | Parallel **read-only** scouts, join exact run/attempt/SHA and rank admissible repairs | Observed native run/job/step, UTC, baseline, first-red or PASS |
| P2 → N+2: ENHANCE/PROVE | Improve **what already works**, add negative/reverse tests, fix highest-leverage root | Disjoint owned-path code/test commits, new PR if permitted, targeted exact-head CI | Tests actually executed, statement+branch source scope, unchanged/changed blob classification |
| P3 → N+3: STABILIZE/RECHECK | Independent recurrence probe, source re-census, bounded fan-in and lossless handover | Serial exact-head validation barrier; update current GoGREEN ledger, SIPOC/DAG/REX view | Three monotonic terminal receipts, hashes, N→N+3 planned vs actual, blockers and open debt |

**Wave policy inside 3PSTAR:** `SERIAL` for one causal chain; `PARALLEL_DISJOINT` for independently leased source paths; `HYBRID_DEPENDENCY_BARRIER` for simultaneous read-only scouts and disjoint code changes followed by **one** integrated exact-head proof. There is no equivalence between a green wave and a governance-admitted pulse.

## Minimum input required

[N3_CHARTER_TEMPLATE.json](N3_CHARTER_TEMPLATE.json) deliberately contains **null source and denominator fields**. Bind them from a *fresh* native/owner readback before executing. The charter includes mission/repository, one primary goal, exact baseline source+UTC, metric numerator/denominator, instrument and module Git blob, source owner/path leases, disjoint worker limit, retry limit, security/admission stops, and expected return artifacts. The evidence template is [N3_OBSERVATION_TEMPLATE.json](N3_OBSERVATION_TEMPLATE.json).

Defaults: **three** pulses; ≤4 independent workers; ≤3 attempts per pulse; only in-turn action; owned-branch mutation only with valid path lease. No permission for background execution, auto-merge, rule relaxation, security bypass, QPS engineering acceptance or formal REX root closure. Important stop reasons: P0/P1, failed/unknown required gate, lease conflict, missing exact-head job proof, unauthorized rule change, owner acceptance needed, unrecoverable cohort drift.

A routine *technical* failure can feed P2/P3 repair; a genuine major blocker stops the affected chain and emits a lossless partial receipt. Continue independent read-only analysis when legal, but never count it as a successful N+i advance. Each N+i needs a new genuine terminal source-bound run/attempt. A failed terminal testflight may count as measured progress with an explicit RED disposition, not as green stability.

## Canonical drop-in invocation

> **N3! / 3P*** — Resume CODE PURPLE / GoGREEN from the **latest independently verified N**. Choose and execute three bounded measured pulses to N+3. Prioritize root-red leverage, **what works→better**, reverse tests and coverage, exact-head test/runner telemetry, DAG/SIPOC and REX. Parallelize disjoint owned lanes; do not ask for routine intermediate approval. No merges/waivers without independent effective gates. Preserve historical evidence, record every terminal failure and changed scope. Stop early only for a major blocker. Return N→N+i planned/actual KPI table, tests and coverage numerators/denominators, native run/attempt/job receipts, PR/main status, open gates, dashboards and a lossless re-entry instruction.

This is a **single active interaction**, not an agent that keeps working between chats. A worker invoking this contract must do the permitted work *now*, then return actual receipts. The Python controller is a deterministic validator and resume planner; it does **not** authenticate GitHub independently, run workers, open PRs or process asynchronously.

## Repeatable executable contract

With the bound charter and zero to three authenticated source observations:

```sh
python mission-control/gogreen/n3_continuation/protocol.py \
  --charter /path/to/bound_charter.json \
  --observations /path/to/native_observations.json \
  --out /new/empty/n3_receipt_directory
```

For partial resumption, add `--ledger /old/ledger.json`, pass **only new observations** and choose a **new empty output directory**. Ledger checkpoint hashes and source lineage must reconcile. Output: `ledger.json`, `return_receipt.json`, `next_action.json`, `sipoc_dag.json`, `index.html` and `manifest.json` with SHA-256 hashes.

A queued/cancelled/duplicate run, invalid root credit, stale head, absent job or ambiguous coverage scope cannot count as a completed pulse. Changed scope, production Git blob, coverage tool or eligible denominator forces `comparable_delta_pp=null`. Only statistically qualified independent observations support confidence intervals, ANOVA/PCA/Bradley-Terry or predictive model claims.

The latest return receipt reports `N+0` through `N+3`, native terminal success/failure counts, first-red debt, coverage scope comparability, source owners, next legal action, and `independent_review=UNVERIFIED` / `merge_authorized=false`. Reaching N+3 proves **three recorded measured checkpoint dispositions**, not three green runs, independent artifact authentication, authorized merges or long-term REX CONTROL.

## Integration / source ownership

Canonical Mission Control taxonomy is updated **additively**. GoGREEN's historical timeline and portfolio ledgers remain owners of their existing receipts; this protocol does not overwrite them. ABACUS owns affected code/security first-red repairs, CODEX owns its source, cryoplant-project (QPS) owns engineering acceptance, gg_MATH owns numerical/statistical qualification, Mission Control only joins bounded telemetry. TOP21 cohort definitions and upstream REX/BD root ownership remain unchanged.

Native qualification: `.github/workflows/gogreen-n3-continuation.yml` must pass 72 positive/adversarial tests with exact-head SHA, coverage.py 7.13.3, and ≥90% statement / ≥85% branch coverage of `protocol.py`. No coverage of the federation is implied.
