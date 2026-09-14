# QPS TRIAGE repository function topology v1

**As of:** 2026-09-14 13:15 +02:00  
**Owner:** `H4_QPS_TRIAGE` / `GBOGEB/pipeline-automation-hub`  
**Authority transfer:** `false`

## Decision

QPS TRIAGE should route work by **repository function**, not by repository visibility or historical activity alone. A repository may be active, a proven reserve, conditionally useful, dormant-but-exploitable, or maintenance-only. Those states describe routing value; they do not create engineering authority.

The current topology also corrects one stale assumption from the 2026-09-10 activity index: `pipeline-automation-hub` is now an actively used Mission Control/orchestration surface, and two newer capabilities deserve explicit placement — `Q_engineering_tools` as the exact-payload runtime carrier and `gg_MATH` as the generic math provider.

## Fast topology

```text
                                  H4 / MISSION CONTROL
                         GBOGEB/pipeline-automation-hub
                    route | correlate | stop | reallocate | REX
                                   authority_transfer=false
                                           |
              +----------------------------+----------------------------+
              |                            |                            |
              v                            v                            v
       H1 / CHILD AUTHORITY         H2 / SEMANTICS              H3 / MEASUREMENT
   GBOGEB/cryoplant-project          GBOGEB/CODEX                 GBOGEB/ABACUS
 engineering/source/disposition   provenance/state classes      runtime/denominator QA
              |                            |                            |
              +----------------------------+----------------------------+
                                           |
                      +--------------------+--------------------+
                      |                                         |
                      v                                         v
          TOOLING / TRACEABILITY                       EXACT RUNTIME CARRIER
       GBOGEB/DOCX_RTM_Automation                    GBOGEB/Q_engineering_tools
 parser | RTM/DTM | evidence consumer             exact blobs | tests | receipts
                                                               no authority transfer
                                           |
                                           v
                                     CONTROL RESERVES
              gg_MATH | CODESPACES_jyperter | accelerator workspace | leak dashboard
                                           |
                                           v
                                    CONDITIONAL / DORMANT
                        document-organization-system | github_Documents
                                           |
                                           v
                                     MAINTENANCE ONLY
                                        GBOGEB/stale
```

## Used now

| Repository | Current function | Why it is used now | Next exploitation |
|---|---|---|---|
| `GBOGEB/cryoplant-project` | QPS child authority | Owns engineering/source/disposition and the current M08 MIP-2 work | Execute MIP2A workbook, MIP2B narrative, MIP2C eight one-pagers, then MIP2D parity |
| `GBOGEB/pipeline-automation-hub` | H4 Mission Control | Owns method selection, routing, receipts, pressure and STOP/reallocation | Keep W2 fail-closed while routing useful independent work |
| `GBOGEB/CODEX` | H2 KEB semantics/provenance | Proven semantic challenge and authority-boundary receiver | Use once after MIP2D in the bounded 3P3 chain, unless a real semantic red appears earlier |
| `GBOGEB/ABACUS` | H3 DOW measurement/runtime | Independent measurement, denominator and runtime QA | Use once after MIP2D as independent consumer; use PCA/BT only with valid measured populations/outcomes |
| `GBOGEB/DOCX_RTM_Automation` | extraction/RTM/reliability tooling | Existing parser, traceability, receipt and analytical-consumer plane | Reuse for normalized evidence/RTM views; do not create a fifth reliability lane |
| `GBOGEB/Q_engineering_tools` | exact-payload runtime carrier | Repeatedly executes byte-bound child payloads when child Actions admission is blocked | **Highest immediate leverage:** MIP2A/B/C exact-runtime, binary roundtrip and adapter regression receipts |

## Proven reserve / exploit on trigger

| Repository | Reserve capability | Activate when |
|---|---|---|
| `GBOGEB/gg_MATH` | generic PCA/covariance/state-space, BT implementation, Monte-Carlo/uncertainty kernels | a current QPS consumer needs generic math that should not be reimplemented locally |
| `GBOGEB/CODESPACES_jyperter` | helium-property notebook/CLI developer runtime | a source-bound helium-property calculation/runtime check becomes a current blocker |
| `GBOGEB/cryogenic-accelerator-workspace` | accelerator RTM / geometry / dimensional reference | a named source-bound accelerator-interface or geometry consumer appears |
| `GBOGEB/cryo_leak_rate_dashboard` | leak-physics kernel/evidence | current leak source or a named leak-physics consumer returns |

## Dormant but exploitable

`GBOGEB/document-organization-system` remains useful as a potential deterministic artifact-index/hash service, but there is no current QPS blocker that justifies activating it. `GBOGEB/github_Documents` is similarly retained as a private-byte provenance candidate; it should be activated only for an exact ingress/retrieval hash cycle. Dormant here means **no current routing allocation**, not deprecated or disposable.

`GBOGEB/stale` remains maintenance-only and receives no QPS TRIAGE worker allocation.

## Immediate execution choice

The best next move is **not** to wake every dormant repository. The child MIP-2 seed has already executed successfully on the independent runner carrier, so the highest-value executable frontier is:

```text
cryoplant MIP-2 source doctrine
       |
       +--> MIP2A workbook adapter -----+
       +--> MIP2B narrative ------------+--> MIP2D same-doctrine parity
       +--> MIP2C 8 one-pagers ---------+
                 |
                 +--> Q_engineering_tools exact-payload/binary/runtime receipts

MIP2D PASS
   |
   v
one 3P3 only:
CODEX semantic receiver -> ABACUS independent consumer -> QPS child re-entry
   |
   v
STOP / CONTROL
```

This uses the currently proven topology instead of generating another framework layer.

## H4 gate remains unchanged

The separate H4 reliability W2 transaction remains `HOLD_QPS_REPO_LOCAL_RUNNER_923`. `Q_engineering_tools` may prove exact payload behaviour, but it does not make `runner_id=0 / steps=0` in the child repository disappear and cannot convert that local runtime gate into CONTROL.

Therefore this topology update creates zero engineering, compliance, negotiation, acceptance, release or Table-10 credit. It is a routing/control improvement only.

## Routing rules

1. Engineering/source/disposition -> `cryoplant-project`.
2. Semantics/provenance/state-class challenge -> `CODEX`.
3. Independent denominator/runtime QA -> `ABACUS`.
4. Parser/RTM/evidence normalization -> `DOCX_RTM_Automation`.
5. Exact-payload execution when authority-repo runtime is blocked -> `Q_engineering_tools`, with exact blob identity and no compensation of the local runtime veto.
6. Generic reusable mathematics -> `gg_MATH`, while policy/retention/authority remains in the consumer.
7. Orchestration, topology, resource pressure and STOP/reallocation -> `pipeline-automation-hub`.

The machine-readable companion is `QPS_REPO_FUNCTION_TOPOLOGY_v1.yaml`.
