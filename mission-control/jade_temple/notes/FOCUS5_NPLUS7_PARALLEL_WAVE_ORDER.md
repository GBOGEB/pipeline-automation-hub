# JADE_TEMPLE / QPS TRIAGE — Focus5 N+7 parallel acceptance wave

**Status:** staged read-only source-owned candidate, `MERGE_ADMISSION=HOLD`, `J5=TARGET_NOT_ACHIEVED`.
Default-branch readback is **non-atomic**, 19 October 2026. No remote CI dispatch, waiver, PR merge, independent review, engineering-root closure or J5 release was performed.

## Denominator and progress contract

All five selected repositories independently have twelve minimum gate records H01..H12 defined in [the canonical source ledger](../data/FOCUS5_POINT_RELEASE_NPLUS7.json). **H01/H02: identity and root. H03: signed applicability. H04: build reproducibility. H05: primary native B0/equivalent. H06: disjoint domain/integration smoke. H07: security and supply chain. H08: effective required checks and blocked RED canary. H09: eligible independent human review. H10: matched branch/statement coverage and negative proof. H11: source-bound site/Office/binary QA and SHA parity, or owner-signed applicability disposition. H12: version/tag/assets/rollback owner approval.**

Verified-PASS count is the only numerator; FAIL and UNKNOWN remain in denominator. **N+7 = 14/60 (23.33%), with 8 FAIL and 38 UNKNOWN.** No weighted maturity, automatic N/A or borrowed green. Each newly verified gate adds one numerator point, never a release claim without the full independent J3/J4/J5 fan-in.

Read-only source projections:
[interactive focus5](../site/focus5.html) · [60-gate CSV](../site/focus5_burndown.csv) · [typed 60-neuron DAG](../diagrams/JADE_FOCUS5_GATE_NEURONS_NPLUS7.mmd).
The other 16/21 canonical Top21 repositories remain outside this five-repo percentage.

## Four disjoint source repairs + fifth consumer lane

| Lane | Owned source commit | Current observed baseline first-red or unqualified obligation | N+1 acceptance proof |
| --- | --- | --- | --- |
| **QPS #04 — primary** | `GBOGEB/cryoplant-project` `code-purple/jade-focus-qps-w163-alias-20261019`; source exact SHA after negative-fixture correction `53789ae79330fce95133db7ca77b029be6383201` | [Canonicalization run 39174767597](https://github.com/GBOGEB/cryoplant-project/actions/runs/39174767597) failed due two immutable Top7 history files with unregistered legacy navigation G-prefix identifiers. Branch registers exact historical paths and tests new invalid paths remain blocked. | Native new-head W163 and qps-canonicalization terminal GREEN with new run/job/attempt/artifact; no source historical bytes mutated, then SSOT/control, QPS v6 RC and binary cross-format QA separately |
| **DOCX #08** | `GBOGEB/DOCX_RTM_Automation` `code-purple/jade-focus-docx-qps-bridge-20261019`, `f12a116bef7792023219096829c0fc05c9514efc` | [Admission 38177507900](https://github.com/GBOGEB/DOCX_RTM_Automation/actions/runs/38177507900) deliberately RED `main.protected=false`. Existing main Python and TypeScript CI separately green. | Native synthetic four-case RTM/OTC/DEL/source-clause tests and unchanged security, typed QPS crosswalk, human owner/Admin rule/RED-canary proof; no fabricated RTM canonical IDs |
| **YAML #16** | `GBOGEB/yaml-grammar` `code-purple/jade-focus-yaml-offline-b0-20261019`, `e0ec2c6f382cf47ee1a1addc4603644109e977aa` | Source 211 grammar rules / 422 JSON keys, Makefile remote node_modules worktree, no native Actions evidence. | Seven offline Node audit cases, exact-head owner-run reproducibility, applicability decision; don't require Pages for reference grammar without owner agreement |
| **gg_MATH #05** | `GBOGEB/gg_MATH` `code-purple/jade-focus-math-release-mpl-20261019`, `6b35710430268478504c0b329a3ed07d11cae26b` | [Release gate 39173707688](https://github.com/GBOGEB/gg_MATH/actions/runs/39173707688) fails two visual bridge tests due absent Matplotlib. Candidate pins `matplotlib==3.10.7` and guards dependency install order. | Native exact-head full release gate with PNG/SVG/HTML parity and hashes; source-bound W260 only provider proof, not QPS compliance |
| **Mission Control #02** | `GBOGEB/pipeline-automation-hub` `code-purple/jade-n6-point-release-neural-mopup-20261019` (mutable head; read back before use) | Scoped SPINE/Zero-Test checks successful at main; no terminal exact-branch whole-JADE J4, protected admission or served Pages proof. | Source-bound 60-row readback, generator `--check`, 9 negative local/CI tests, 3 served viewport hash proof through existing single publisher, owner J3/J4/J5 |

## Typed DAG and disjoint work scheduling

```text
QPS_TRIAGE source-authority / cryoplant SSOT ──────────────────────┐
DOCX synthetic candidate RTM+OTC+DEL extraction ──[source input]───┤
YAML 1.2 grammar offline source parser ───────────[reference]─────┤──> OWNER-GATED QPS J4
gg_MATH numerical/visual proof ──────────────────[provider]───────┘
ABACUS DOW independent acceptance ───────────────[separate veto]──┐
CODEX KEB authenticated REX ─────────────────────[separate veto]──┤──> Mission Control read-only JADE
Mission Control 60/60 source gate assessment ──────[observes]─────┘
               J4 success + effective governance + human review + artifacts
                                  --> owner J5 tag/rollback
```

Run only owner-disjoint changes in parallel. Path locks must remain per repository, and shared authority transitions are SERIAL. If any owner head changes, invalidate stale run or metric until re-qualified. No same-head blind retries or new scheduled workflow family.

## Parked until explicit trigger

- **QPS artifact lane:** comprehensive XLSX (formula/recalc), PPTX (slide render/overflow), PDF (every-page render), DOCX (page layout), HTML (Playwright served SHA) and cross-format SSOT digest parity await authoritative accessible input binaries and owner v6 RC signoff. Existing `BINARIES_MANIFEST.md` is a hash registry, *not a substitute for binary render acceptance*.
- **Security and rule owner:** all five protected/main governance deficiencies require effective required checks, eligible reviewer and a blocked unapproved RED canary. A Boolean protected flag is not equivalent to effective ruleset audit.
- **Manual native pilots:** four new source-owner candidate heads have no terminal exact-head B0 acceptance at latest readback; QPS only has an unrelated successful stranded-push guard. Do not treat absence of runs as failure count zero.
- **Global canonical roots:** #1929 source-bound root OPEN/CLOSED remain UNKNOWN. Dashboard #1885 53 historical href occurrences and six alert-ticket duplicate closures are housekeeping, not six causal closures.
- **W+2 coverage:** require stable source blob, Python/JS/YAML relevant test population and statement/branch opportunity denominators before assigning uplift; 12-gate 100% is independent of code coverage %.
- **Top21 extension:** propagate after focus-five owner receipts stabilize; do not auto-promote the 16 unassessed repos or combine N11 and GoGREEN different 21-member cohorts.

## Recursive exit condition

At each pulse, record `repo, default SHA, source-branch SHA, run ID, attempt, job, artifact URL/hash, first-red fingerprint, new gate PASS/FAIL/UNKNOWN, 12-denominator, owner disposition, incoming/outgoing DAG edges, local vs native evidence, next admissible action`. Recompute deterministic JSON, CSV and HTML; verify source and browser parity. Stop local source work on owner-held external gates and park with `PAUSE_OWNER_PROOF_REQUIRED`, not J5 green. Three same-cohort comparable pulses with no incremental useful proof trigger MIP causal pivot/disjoint source owner review, never an unproved stability claim.
