# Mission Control v2 operating model

This directory is the candidate canonical evolution layer for Mission Control issue #437.

It **does not replace domain/source authority** and does not rewrite historical 3P*/MIP receipts. It separates four concerns:

1. **Lifecycle** — where a mission is: REGISTERED, ACTIVE, WAIT_RETURN, CONTROLLED, CLOSED, etc.
2. **Method profile** — how bounded work is performed: 3PR, 3PC, conditional MIP, under the DMAIC supervisory loop where appropriate.
3. **Execution hierarchy** — Mission -> Sprint -> Wave -> Pulse -> Run.
4. **Resources** — crew members are logical accountable roles; runners are execution substrates.

## Canonical files

- `MISSION_CONTROL_CURRENT_v2.json` — discovery/current pointer.
- `MC_GLOSSARY_TAXONOMY_v2.json` — namespace and glossary authority for new Mission Control machine identifiers.
- `MC_METHOD_PROFILE_REGISTRY_v1.json` — DMAIC, 3P* profiles, 3PR, 3PC, and conditional MIP.
- `MC_MISSION_TELEMETRY_CONTRACT_v1.json` — required per-mission status/progress/health/coverage/metrics/crew/runners/lifecycle/TODO dimensions.
- `MC_MISSION_STATUS_CURRENT_v1.json` — first normalized current census; unknown values remain null/UNKNOWN.
- `MC_DMAIC_EVOLUTION_PLAN_v1.json` — full Define/Measure/Analyze/Improve/Control program and waves.
- `validate_mission_control_v2.py` — dependency-free fail-closed validator.

## Namespace decisions

- **MC = Mission Control** for new operational/control-plane identifiers.
- Monte Carlo is persisted as **MONTE_CARLO** or **MC_SIM**. Bare MC is forbidden for new Monte Carlo machine identifiers.
- Mission Control coverage maturity is **MCOV-0 .. MCOV-5**.
- Historical `COV-N` is a read-time alias only; new machine fields use MCOV.
- Software coverage remains numeric, qualified fields such as `statement_coverage_pct`.
- DMAIC uses phase `CONTROL`; lifecycle uses state `CONTROLLED`.
- `PR` means Pull Request. `3PR` is the fixed Refresh -> Probe -> Rank method token.
- In Mission Control, `MIP` means Modernize -> Innovate -> Perpetuate; optimization uses `MIXED_INTEGER_PROGRAMMING`, `MILP` (when linear), or `MIP_OPT`.
- Cross-domain `CI` must be qualified: `CI_PIPELINE`/`CONTINUOUS_INTEGRATION` vs `CONFIDENCE_INTERVAL`/`CI_STAT`.
- Bare `COV` is never new canonical shorthand: use `MCOV`, qualified code-coverage fields, or `COVARIANCE`/`COV_MAT`.
- `GM` is Grand Mission in Mission Control; mathematical geometric mean uses `GEOMETRIC_MEAN`/`GM_STAT`.
- `PC1` etc. are PCA components. `3PC` is Prepare -> Prove -> Commit.

## Coverage maturity

| Level | Meaning |
|---|---|
| MCOV-0 | no governed MC coverage claim beyond discovery |
| MCOV-1 | identity, scope and authority anchor |
| MCOV-2 | structural inventory of work/dependencies/resources |
| MCOV-3 | semantic predicates/dependencies/status classified |
| MCOV-4 | execution/proof paths evidenced |
| MCOV-5 | longitudinal control, regression/re-entry and durable continuity |

MCOV is **not** code/test coverage and is **not** a mission-success score.

## Mission census scope

The CURRENT mission telemetry census combines the official Mission Register, the QPS TRIAGE legacy/current mission registry, and explicitly governed Mission Control programs. Every discovered mission row in those bound sources receives its own telemetry envelope; absent measurements remain `UNKNOWN`/`null` rather than being inferred as zero or green.

## Core operating loop

```text
Mission lifecycle
    |
    +--> DMAIC supervisory loop (when admitted)
           DEFINE -> MEASURE -> ANALYZE
                         |
                         +--> select 3P* profile
                         |      3PR = Refresh -> Probe -> Rank
                         |      3PC = Prepare -> Prove -> Commit
                         |
                         +--> admit MIP only when justified
                                Modernize / Innovate / Perpetuate
           IMPROVE -> CONTROL -> RECENSUS / REX / REENTRY or CLOSE
```

A no-change CONTROL/HOLD disposition is valid. MIP is not mandatory.

## Non-equivalences

`crew assignment != runner execution != run success != proof != mission completion != authority transfer`.

Missing data is unknown, not zero. Zero-step is not application failure. Merge is not proof.

## G3P — Governed Three-Pulse Wave (proposed 2026-10-17)

Use **G3P N→N+3** for one bounded wave with three sequential measured pulse
dispositions, not three separate waves, commits, test invocations or runners.
The existing mission hierarchy remains **Mission → Sprint → Wave → Pulse → Run**.
Select the existing **3PR** (Refresh/Probe/Rank), **3PC**
(Prepare/Prove/Commit), DMAIC and conditionally MIP *inside* each pulse;
G3P is an execution envelope, **not a competing method profile**.

A frozen, exact-source N baseline is followed by PULSE-1 (N+1), PULSE-2
(N+2) and PULSE-3 (N+3). Each requires its own forecast-before-action,
observed or explicitly UNKNOWN test/coverage/telemetry, exact source and
run/attempt identity, decision, action/hold, QA, blocker, and next input.
A HOLD pulse may advance the ordinal without any engineering closure.
If all next actions are globally unsafe or lack authority, stop early and
mark later pulses NOT_RUN; never fabricate N+3.

Machine contract/renderer: `g3p_execution.py`; focused adversarial tests:
`test_g3p_execution.py`. See `G3P_EXECUTION_OPERATOR.md` for the
copyable one-turn instruction and evidence requirements. These are
consumers of the canonical glossary and method registry, **not another SSOT**.
Hands-off means no intermediate user questions within the bounded *current*
execution when safe; it does **not** authorize autonomous background work,
security waivers, force-merge, or rule-relaxation.
