# Federation Mechanism Ladder — Provenance Binding v1

Status: `CURRENT_ADOPTION_AUTHORITY`

As of: `2026-09-17`

Authority transfer: `false`

## Purpose

This file establishes the **current federation adoption authority** for the cross-boundary mechanism ladder:

```text
DEP / REG / SUB / ADAPTER / LAB / FORK
```

It does **not** claim to be the historical origin of that vocabulary. Historical origin remains `UNKNOWN_NEEDS_READER` unless an earlier exact repository path and SHA are recovered.

## Current normative source

The ladder is currently normative in:

`mission-control/golden-thread/FEDERATION_NATIVE_GOLDEN_THREAD_v1.md`

The federation-native Golden Thread requires a selected mechanism to identify, at minimum:

- provider;
- consumer;
- authority owner;
- exact version/SHA;
- schema;
- acceptance gate;
- expected semantic delta;
- re-entry contract.

This provenance binding makes that requirement addressable without incorrectly citing an unrelated ADR as its origin.

## Historical-origin disposition

`GBOGEB/CODEX/governance/adr/ADR-0001-runtime-debug-governance.md` and federation identifier `GG-ADR-0001` govern runtime-debug policy. They are **not** the origin authority for the mechanism ladder.

No new `GG-ADR-*` number is allocated by this file. Global ADR numbering remains a separate governance concern and must not be guessed from a local MissionControl pulse.

## Selection semantics

The six mechanism classes are adopted as follows.

| Mechanism | Federation meaning | Authority rule |
|---|---|---|
| `DEP` | Direct dependency on a provider surface/version | Consumer does not acquire provider authority |
| `REG` | Registry/reference binding to externally governed identity | Registry pointer is not the referenced source authority |
| `SUB` | Submodule/subtree-style pinned source inclusion | Pin preserves upstream identity; inclusion does not silently fork authority |
| `ADAPTER` | Explicit translation boundary between provider and consumer contracts | Adapter owns translation behavior, not upstream or downstream domain truth |
| `LAB` | Experimental/laboratory integration lane | No production/control credit without separate admission |
| `FORK` | Deliberately independent derivative authority | Authority divergence must be explicit and lineage to parent retained |

## Required mechanism receipt

Every governed cross-boundary use shall bind:

```yaml
mechanism: DEP|REG|SUB|ADAPTER|LAB|FORK
provider: owner/repo-or-surface
consumer: owner/repo-or-surface
authority_owner: owner/repo-or-domain
provider_exact_sha_or_version: string
schema_or_contract: string
acceptance_gate: string
expected_semantic_delta: string|number|object
reentry_contract: string
authority_transfer: false|explicitly_governed
```

Unknown values shall remain `UNKNOWN_NEEDS_READER`; they shall not be coerced to zero, PASS, or implied ownership.

## Relationship to Golden Thread

The mechanism ladder selects **how a cross-boundary dependency is bound**. The Golden Thread records **what happened through that binding**, including exact identities, child disposition, replay evidence, and non-compensating gates.

Neither mechanism selection nor Golden Thread replay creates engineering/source/bidder/release authority by itself.

## Provenance status

```yaml
current_adoption_authority: mission-control/golden-thread/MECHANISM_LADDER_PROVENANCE_BINDING_v1.md
normative_vocabulary_source: mission-control/golden-thread/FEDERATION_NATIVE_GOLDEN_THREAD_v1.md
historical_origin: UNKNOWN_NEEDS_READER
rejected_origin:
  repository: GBOGEB/CODEX
  path: governance/adr/ADR-0001-runtime-debug-governance.md
  federation_id: GG-ADR-0001
  reason: runtime_debug_governance_not_mechanism_ladder
```

## Control rule

Future documents may cite this binding as the **current adoption/provenance authority**. They shall not rewrite that statement as “historical origin proven” unless earlier exact evidence is separately admitted.
