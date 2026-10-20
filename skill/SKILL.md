---
name: pipeline-hub-level1
description: Use in pipeline-automation-hub to census, modernize, repair, innovate, or perpetuate federation routing and document-processing capability; run Level-1 checks; orchestrate worker dispatch and receipt correlation; and apply measured PCA or Bradley-Terry diagnostics while keeping engineering authority transfer disabled.
---

# Pipeline Hub Level 1

1. Read `LEVEL1.md` and `level1/ssot.json`.
2. Run `python level1/runtime.py census` and `python level1/runtime.py mip`.
3. Reuse the existing Next.js/API and Python processing paths; do not replace healthy routing/processing code with the Level-1 wrapper.
4. Run `python level1/runtime.py orchestrate` to obtain blocks, agents, targets and authority limits.
5. The hub may dispatch work and correlate exact source/head/output digests, but routing success is never engineering/evidence acceptance.
6. PCA accepts measured numeric observations only; BT accepts explicit pairwise outcomes only. Missing input DEFERs.
7. Run `python level1/runtime.py self-test` before claiming Level-1.0. Synthetic fixtures prove implementation only.
8. Keep `authority_transfer=false`; KEB/DOW/child remain the governed acceptance chain.

## Root-red tracing (GOGREEN red-trace, N+8)

9. Before calling anything "red", "green" or "fixed", read the ledger, not a single run:
   `python mission-control/gogreen/red_trace/red_trace.py --repo GBOGEB/<repo> --branch <default> --root <checkout> --out <dir>`.
   Classes: `EVERRED`, `GREEN_TO_RED`, `RED_TO_GREEN`, `FLAKY`, `STABLE_GREEN`. One outcome per head SHA (latest attempt); cancelled/skipped never count.
10. Triage by flag, in this order:
    - `stale` (no run for >3 d): **replay first** (`workflow_dispatch`), never repair a stale red from memory.
    - `📌 pinned evidence`: the gate asserts a historical run/artifact id; artifacts expire (30 d), so suspects are meaningless — escalate the evidence-binding decision to the owner.
    - shared break root (one SHA → N workflows): **one** root, one PR; do not open N fixes.
    - otherwise: open the first red run, read the failing step, fix the earliest stage only.
11. A QA step that only says `exit code 1` is a diagnostics gap: add the on-failure `::error` annotation wrapper first (see `code-purple-method-atlas.yml`), then repair from the annotation. Do not guess.
12. Path-filtered gates cannot be required directly (PRs that miss their paths would wait forever). Require **`GOGREEN required gate`** (`.github/workflows/gogreen-required-gate.yml`), which reports on every PR and passes only when the applicable gates succeed on the exact head. Since N+9 the set it enforces comes from `mission-control/gogreen/required_gate/ADMISSION.json` **as committed on the base branch**; read `required_gate/README.md` before touching it.
12a. Telemetry has two lanes: master (`red_trace.json`) and merged-PR heads at merge time (`--pr-lane N` → `red_trace_pr.json`). A PR-only gate is invisible to the master lane; check both before calling it green. `FLAKY` by flip count is not nondeterminism: read `nondeterminism.same_head_disagreements` / `rerun_rescues`.
12b. Admission (`required_gate/admission.py`) dispositions EVERY workflow file: `ENFORCED` / `OBSERVED` / `EXCLUDED` with reason codes. Agents may propose promotions by regenerating the ledger in a PR. Agents may not demote: an enforced gate with bad evidence stays enforced as a `demotion_candidate` for the owner (ratchet).
12c. Before proposing that the owner require the gate, quote the backtest (`required_gate/backtest.py`): how many recent merges had an applicable gate red, pending or absent at merge time, per policy.
13. Ledger hand-off: ABACUS `tools/everred_v3/scripts/ingest_red_trace.py --input <red_trace.json> --apply` maps findings to EVERRED v3 events (`occurrence`, `root_candidate`, `verification`, `note`). It never emits `root_confirmed`, `closure` or `admission`.
14. Publish evidence through JADE only: `python mission-control/jade_temple/tools/build_redtrace_data.py --reports <dir>` → `site/build_redtrace.py` (HTML page + 16:9 slides) → `tools/render_redtrace_pdf.py` (interactive PDF) → `tools/run_redtrace_browser_qa.py`.

## Explicit agentic involvement

15. Every action an agent takes is recorded with an actor: `AGENT` (executed by an AI session), `OWNER` (decided or merged by the repository owner), `CI` (native GitHub Actions evidence). JADE pages render these as badges; colour is never the only cue.
16. Agents may: read, trace, replay workflows the owner authorised, open draft PRs, append typed ledger events, propose admission promotions. Agents may not: merge, change branch protection, rebind evidence policy, retire or demote gates, waive security, or confirm root causes. Those stay `OWNER`.
