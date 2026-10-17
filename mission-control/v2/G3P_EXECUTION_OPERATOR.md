# G3P — Governed Three-Pulse Wave (N→N+3)

Status: **candidate control-plane execution envelope**, subject to #437/
Mission Control v2 admission. Owner: `GBOGEB/pipeline-automation-hub`
Mission Control v2. Does **not** create a new SSOT or supplant CODEX,
QPS, ABACUS, existing 3PR/3PC, DMAIC or MIP.

## Meaning and identity

| Moniker | Level | What it means | Does not mean |
|---|---|---|---|
| **3 waves** | 3 × WAVE | Three distinct delivery work packages | Exactly three feedback cycles |
| **3 pulses** | PULSE × 3 | Three feedback iterations within one WAVE | Three code commits or three test runs |
| **G3P** | WAVE execution envelope | Exactly PULSE-1, -2, -3 from N to N+3 | New method profile, three waves or successful merges |
| **3PR** | Method phases | Refresh → Probe → Rank | Three pulses |
| **3PC** | Method phases | Prepare → Prove → Commit | Three commits or automatic merge |
| **MIP** | Conditional improvement method | Modernize → Innovate → Perpetuate | Mandatory three mutations |
| **DMAIC** | Improvement supervisor | Define → Measure → Analyze → Improve → Control | Promise of five separate jobs |
| **RUN** | Runtime unit | One actual execution with native exit evidence | A pulse |
| **WORKER** | Role or owner path lease | Disjoint executor with source authority | Automatically running cloud runner |

The ordinal `N` is a declared source-bound state (repo, mission,
wave, actual commit SHA, observed time, metric population/denominators,
active first-red, canonical BD queue and safety gates). `N+1,N+2,N+3`
are **pulse receipt ordinals**, *not* implicit accepted/merged PR counts
or a statement of increasing code coverage.

## Operator contract

### Required inputs (ask no extra questions when authenticated context can supply them)

- Mission and work objective/DoV: target predicate and measurable exit
  criterion (e.g. increase branch/changed-line coverage and reduce
  **confirmed** first-reds).
- Scope: repo(s), canonical SSOT pointers, source owner/path leases,
  current N head and any incident or compliance boundaries.
- Resource budget: default **two disjoint mutation owners plus one
  verification lane**, read-only scouts may fan out. Serial writes to the
  same branch. A worker assignment is not a claim that an agent ran.
- Evidence: native GitHub current runs/attempts/jobs/steps, baseline test,
  statement/branch/changed-line denominators and timestamps, current DAG/
  SIPOC links and known UNKNOWNs.
- Boundaries: P0/P1 security, A10, governance, independent reviewers, no
  branch protection weakening, no public main merge without admission.
- If `N` is omitted: resolve the latest available exact source/head,
  record its SHA and timestamp, and disclose any non-atomic snapshot.

### One **G3P N→N+3** request means

1. **PULSE-1 / N+1 — REFRESH, CLASSIFY, ACT:** Capture exact N state,
   source-bound first-red and DAG neighbors; freeze measurable forecast
   *before* action. Perform highest-impact admissible source-owner repair,
   telemetry improvement or diagnostic. Run native checks, score actual,
   capture a receipt and next source.
2. **PULSE-2 / N+2 — REASSESS, SCALE DISJOINTLY:** Recompute from N+1
   actuals. Choose next safe source-owned target by dependency/unblock
   leverage; add representative negative tests and **measured** coverage.
   Fan out disjoint changes only, independently verify, freeze actual and
   update DAG/SIPOC/backlog links.
3. **PULSE-3 / N+3 — INTEGRATE/PROVE/CONTROL:** Reconcile source heads and
   disjoint results into an *admissible integration testflight*; rerun the
   unchanged checks on exact head, measure statement/branch/changed-line
   numerators and denominators, classify P0/P1, A10, governance, review,
   sign-off as independent states. Emit next-N baseline, DoV status, frozen
   forecast-vs-actual and a complete lossless continuation receipt.

Each pulse may use 3PR for scout/rank, 3PC for admitted implementation,
DMAIC for diagnosis and CONTROL, and conditionally MIP. These **phases**
do not increment the pulse ordinal by themselves.

### Hands-off continuation and blocker handling

"Hands-off" means exercise delegated technical discretion **within
the current invoked session**, without requesting intermediate user input
that can be safely inferred. Do not promise asynchronous action after
reply. Authenticated external runners may continue on their own platforms,
but unresolved/queued results at reply are PENDING, **not PASS**.

- **Local lane blocker:** persist HOLD/DEFER with observed evidence;
  release its path lease; continue on the next disjoint admissible
  high-leverage lane. The pulse ordinal can advance with a defensible HOLD
  receipt, never with a fabricated positive engineering outcome.
- **Major global blocker:** missing authority/permission, required safety
  bypass, uncontrolled destructive action, conflicting exact source or owner
  leases, contradictory/untrusted evidence, or no remaining safe path.
  Stop affected mutation; if globally blocking, leave later pulse slots
  `NOT_RUN_GLOBAL_BLOCKER`, report actual frontier N+k with k<3.
- **No silent omissions:** reports name blocked/untested/queued/unknown
  facts; do not turn unknown denominators into zeros or invented metrics.
- **No false convergence:** three green runs on one SHA are not three
  independent statistical observations; one common root may manifest on
  multiple PRs; downstream summary job failures are not independent roots.

## Mandatory final response after one G3P invocation

Report (a) baseline N and exact head; (b) what was **committed, tested,
measured or held** in PULSE-1, -2, -3; (c) planned vs observed values;
(d) source commits/PRs/current CI exact-head status, executed test counts,
matching statement/branch/changed-line numerators and denominators;
(e) symptoms→jobs→steps→first-red/root graph with support and noncausal
edges; (f) BD queue distinct root versus manifestation accounting;
(g) clock/runner resource costs and censored/unknown measurements;
(h) scope-limited DoV and independent gate status; (i) remaining blockers,
owners and N+3 handover/next legal action. If globally blocked, say the
actual terminal frontier (e.g. N+1), and list N+2/N+3 as NOT_RUN.

## Machine receipts and no competing source authority

`MC_GLOSSARY_TAXONOMY_v2.json` defines term/namespace semantics;
`MC_METHOD_PROFILE_REGISTRY_v1.json` owns method profile selection and
G3P envelope semantics; `MC_MISSION_TELEMETRY_CONTRACT_v1.json` owns
the optional pulse receipt dimensions. The standard-library
`g3p_execution.py` **validates/project-reports supplied receipts**, it
does NOT itself dispatch workers, mutate GitHub or authenticate arbitrary
URL strings. Its output therefore marks locator authentication and
engineering/merge acceptance UNKNOWN/HOLD. Rerun the native runner and
source verification before admission.

### Reusable operator instruction

> Execute **G3P N→N+3** on the current CODE PURPLE mission. Recensus the
> latest source-bound N and applicable canonical authorities first. Perform
> three consecutive pulse cycles without intermediate prompts, exercising
> discretion under current safety/gate/lease constraints. For each pulse,
> freeze expected metrics, choose the highest-impact admissible action,
> perform actual bounded disjoint source-owner mutations/tests, verify
> exact-head native outcomes, update the DAG/SIPOC/BD links and feed the
> observed output into the next pulse. Use existing 3PR/3PC, DMAIC and
> conditional MIP, not three waves or mere three jobs. Pivot around locally
> blocked lanes but stop on major global blockers. Return at completion
> with N, N+1, N+2, N+3 expected-vs-actual, actual commits/PR/run links,
> measured tests and coverage denominators, unresolved P0/P1/A10/security,
> independent review and main admission, plus the lossless handover.
> Do not claim work after this response unless separately scheduled.
