**CI/CD DAG + SIPOC update (23 October 2026):** [Interactive DAG / SIPOC](site/cicd_dag.html) · [model JSON](site/cicd_dag.json) · [function ⇄ SHA ⇄ OID crosswalk CSV](site/cicd_dag_crosswalk.csv) · [Mermaid total](diagrams/CICD_DAG_TOTAL_FUNCTION.mmd) ([SHA](diagrams/CICD_DAG_TOTAL_SHA.mmd), [OID](diagrams/CICD_DAG_TOTAL_OID.mmd)) · [Mermaid orchestrators](diagrams/CICD_DAG_ORCHESTRATORS_FUNCTION.mmd) · [policy](data/CICD_DAG_POLICY.json). One process model in seven views: the federation total, each focus repo, and the orchestrating/federating assets (hub, ABACUS, CODEX). Each view has three lenses. FUNCTION shows what the step means. SHA shows the exact commit or snapshot sha256 it was observed on. OID shows the git blob id of the Python, workflow or data object that produces it, plus its `def` symbol. Colour classes: CODE_PURPLE > ROOT_RED (SOURCE_RED / first red) > EVERRED > FAIL > UNKNOWN > PASS, plus P-PROCESS, ISSUE/BD and CROSSWALK. New metrics: ready frontier, blocked-by-ancestor, measurement debt, DMAIC phase yield and rolled throughput yield, critical-path PASS depth, EVERRED ratio, recovery and flake rate, median red age, Code Purple and control-plane state, BD burn-down, and OID/SHA coverage. Validated JADE child, **not staged into Pages** (owner review first). Inputs from `qps-triage-ultra/p-process` are OID-bound, so a change there needs a `--write` here.

```bash
python mission-control/jade_temple/tools/cicd_dag.py --check
python mission-control/jade_temple/site/build_cicd_dag.py --check
```

**N+8 update (20 October 2026):** [Red-trace federation ledger](site/redtrace.html) · [16:9 slides](site/redtrace-slides.html) · [interactive PDF](site/redtrace-slides.pdf) · [federation snapshot](data/RED_TRACE_FEDERATION_N8.json) · [gap analysis](data/GAP_ANALYSIS_N8.json). EVERRED / GREEN→RED / RED→GREEN for the 5 core repos (hub, ABACUS, CODEX, cryoplant-project, gg_MATH), break windows to the first red run, stale/pinned flags, a gap analysis of what our own tooling could not answer, and explicit `AGENT` / `OWNER` / `CI` actor badges. Validated JADE child, **not yet staged into Pages** (gap G13: the hosted-parity contract pins the public asset set; owner review first).

```bash
python mission-control/jade_temple/tools/build_redtrace_data.py --reports <dir-with-repo/red_trace.json>
python mission-control/jade_temple/site/build_redtrace.py --check
python mission-control/jade_temple/tools/render_redtrace_pdf.py
python mission-control/jade_temple/tools/run_redtrace_browser_qa.py
```

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
