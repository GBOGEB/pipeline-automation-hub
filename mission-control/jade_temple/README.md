**N+3 update:** [8-point MIP audit](site/eightpoint.html) · [full source decisions](notes/EIGHT_POINT_MIP_DOV.md) · [current frozen 21-repo technical queue](notes/TOP21_TECHNICAL_QUEUE_NPLUS3.md) · [8-point deterministic manifest](site/eightpoint-manifest.json) · [CP.RESUME](DROPIN_NEXT_CHAT.md). It is a separate candidate from newer Mission Control main after JADE N+2 #733 merged; NOT an accepted point release or hard gate.

# JADE_TEMPLE / JADE_CASTE — Top21 GoGREEN launch-readiness pilot

**N+2 update (19 October 2026):** [Measured burn-down and stop rules](site/burndown.html) · [Current 21-source readback](data/READBACK_NPLUS2.json) · [First-red / GoGREEN evidence events](data/EVIDENCE_EVENTS_NPLUS2.json) · [Source-bound stop model](data/STOP_MODEL_NPLUS2.json). The N+1 PR #732 merged, and native JADE plus current-main Method Atlas succeeded; independent JADE hosted SHA and effective human approval remain separate HOLD gates.


**N+1 source-owned Mission Control pilot.** Bootstrap PR [#729](https://github.com/GBOGEB/pipeline-automation-hub/pull/729) is merged. Later implementation must remain separately qualified on its exact PR head. JADE is **not** a second cohort source, CI scheduler, issue/BD root ledger, QPS engineering SSOT, or Pages publisher.

## Start in one click

**[GoGREEN interactive 21-repo dashboard](site/green.html)** · **[Top21 overview / N0](site/index.html)** · **[21 owner TODOs and source identity](notes/REPO_TECHNICAL_NEEDS_NPLUS1.md)** · **[MIP/DMAIC control analysis](notes/MIP_ANALYSIS_NPLUS1.md)** · **[Navigation, styling and Pages implementation contract](notes/NAVIGATION_PAGES_STYLE_CONTRACT.md)** · **[Machine CSV queue](site/top21_bd_queue.csv)** · **[Recursive next-chat drop-in](DROPIN_NEXT_CHAT.md)**

## What is authoritative

| Information | Controlled by | Read-only JADE view |
|---|---|---|
| Mission-selected 21-repo structural cohort | `mission-control/federation-atlas/central/top21/TOP21_COHORT_ROSTER.json` | `data/REPO_READINESS_NPLUS1.json` / `data/COHORT_CROSSWALK_NPLUS1.json` |
| Historical GoGREEN check evidence | `mission-control/gogreen/merged_outcome_census/snapshots/` | Historical `green/red/unknown` only; **13/21 overlap** |
| Repo code, exact-head Actions and release | Each original repo and eligible owner | Non-atomic readback and proposed TODO, no inferred acceptance |
| QPS engineering | `cryoplant-project` | Link/reference-only |
| CODEX federation and ABACUS evidence/admission | Their owner repositories | Typed reference-only |
| Pages release | Existing `federation-atlas/pages_portal.py` and method-atlas workflow | Static hash-checked child `/jade/`, no second publisher |

## How to rebuild and test without network

```bash
python mission-control/jade_temple/site/build_dashboard.py --check
python mission-control/jade_temple/site/build_green.py --check
python -m unittest discover -s mission-control/jade_temple/tests -p 'test_*.py' -v
```

Deterministic sources are in `data/`. `site/green_template.html`, `site/jade.css` and `site/jade.js` are the editable presentation inputs. `site/green.html`, `site/jade_data.js`, `site/snapshot.json`, `site/top21_bd_queue.csv` and `site/site-manifest.json` are deterministic read-only outputs; do not hand edit the generated assets. `portal_bridge.py` validates and stages them as one scoped subtree in the existing publisher.

## Current acceptance

Local N+1 source/negative tests **44/44 PASS**, browser three responsive viewports **3/3 PASS** using exact HTML/CSS/JS assets inlined in an admin-blocked browser environment; native exact-head and hosted Pages proof **pending**. The existing N11 source provides 26,836 tracked file atoms, 880 root files and 706 filename/path review candidates. `MERGE_ADMISSION=HOLD` and point-release qualified denominator UNKNOWN.

## N+2 build and native verification

```bash
python mission-control/jade_temple/site/build_burndown.py --check
python mission-control/jade_temple/tools/stop_rules.py
python -m unittest discover -s mission-control/jade_temple/tests -p "test_*.py" -v
python mission-control/jade_temple/tools/run_nplus2_browser_qa.py
```

An existing-portal-only child at `/jade/burndown.html`; hosted verification is performed independently **after** `deploy-pages` and hashes actual served files against the exact source-bound publisher artifact. No alternate workflow publishes Pages.

## N+6 read-only point-release dependency and mop-up candidate

This **staged branch**, not the accepted JADE publisher or a governed merge, adds a source-bound Top21 dependency/neuron/GOLDEN thread ledger. It does not create a competing scheduler, Pages deployment, automatic release or authority transfer.

- [N+6 owner-based mop-up / parked release checkpoint](notes/NPLUS6_POINT_RELEASE_MOPUP.md)
- [N+6 neural/parallel-lane Mermaid SPINE](diagrams/JADE_TOP21_NEURAL_NPLUS6.mmd)
- [N+6 machine-readable typed nodes/edges/Golden thread](data/POINT_RELEASE_NPLUS6_NEURAL_READONLY.json)
- Existing `sprint/Start-JadeSprint.ps1` and `sprint/cli.py` remain the sole bounded local sprint entrypoints.

Readback: 21/21 non-atomic HEAD identities, 146 ordinary open issues, 18 ordinary open PRs; canonical root counts and J5 owner-accepted releases remain **UNKNOWN**. A separately generated interactive HTML atlas passed local responsive QA, but **is not currently part of the published source-controlled Pages child**. Port its visualization through the existing single-publisher generator only after owner review, exact-source parity and noncompensating J3/J4 acceptance. `MERGE_ADMISSION=HOLD`.


## N+7 QPS TRIAGE focus-five parallel owner lanes

**[Interactive focus-five dashboard](site/focus5.html)** · **[Source-bound 60-gate ledger](data/FOCUS5_POINT_RELEASE_NPLUS7.json)** · [60-row Excel-ready burndown CSV](site/focus5_burndown.csv) · [60-gate neural dependency graph](diagrams/JADE_FOCUS5_GATE_NEURONS_NPLUS7.mmd) · [Parallel wave and parked owner action](notes/FOCUS5_NPLUS7_PARALLEL_WAVE_ORDER.md) · [Deterministic generator](site/build_focus5.py) · [9 authored fail-closed source-contract tests](tests/test_focus5_release_contract.py).

Five repo-specific owners: **04 cryoplant-project, 08 DOCX_RTM_Automation, 16 yaml-grammar, 05 gg_MATH, 02 pipeline-automation-hub**. Current read-only evidence is **14/60 (23.33%)** verified minimum PASS, 8/60 FAIL, 38/60 UNKNOWN. This is **not** broader Top21 release completion; the 16 unassessed repositories remain outside this denominator. Each gate has the same 12-item contract and repo-specific B0 definition. Absence of an Actions workflow, genuine approval or source-binary hash never counts as PASS.

```bash
python mission-control/jade_temple/site/build_focus5.py --check
python -m unittest discover -s mission-control/jade_temple/tests -p test_focus5_release_contract.py -v
```

This is **one generated read-only child under existing JADE site**, not a new GitHub Action, dispatcher or alternative Pages publisher. The original repo owners retain source fixes, native B0 and application/release authority. `MERGE_ADMISSION=HOLD`; no J5 tag, security waiver or accepted root closure is inferred.
