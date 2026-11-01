# JADE_TEMPLE changelog — waves J0 to N+11

> **Doc** JT-CL · **Status** ACTIVE · **Release** UNNAMED (owner sets SemVer) · **Admission** `MERGE_ADMISSION=HOLD` · **Updated** 2026-10-31

Newest first. Each entry keeps the text of the dated banner it replaces on [README](README.md) and [00 Start here](00_START_HERE.md), so the front door stays short and no link or claim is lost. Live handover checkpoints stay in [DROPIN_NEXT_CHAT.md](DROPIN_NEXT_CHAT.md). Commands to rebuild every child are in [README § Build, check and regenerate](README.md#build-check-and-regenerate-offline).

## W1 root-docs launch look (2026-10-31)

- Every root page opens with its H1, one masthead line (doc id, status, release, admission, updated) and ends with a nav footer.
- Dated banners moved from README and 00 Start here into this changelog.
- `tools/root_docs.py --check` and `tests/test_root_docs.py` keep the standard and fail on a broken relative link.

## FOCUS5 pulse P0003 (2026-10-31)

Checkpoint and handover: [DROPIN_NEXT_CHAT.md](DROPIN_NEXT_CHAT.md) · [full handover](notes/HANDOVER_JADE5_P0003_20261031.md) · [P0003 snapshot](data/FOCUS5_POINT_RELEASE_P0003.json).

## N+11 re-census and private boundary (2026-10-26)

Checkpoint: [DROPIN_NEXT_CHAT.md](DROPIN_NEXT_CHAT.md) · [N11 census reading](devops/DEVOPS_CENSUS_N11_READING.md) · [private boundary](tools/private_boundary.py).

## H01–H12 DoV owner cockpit (2026-10-23)

**Owner-facing H01-H12 DoV cockpit (SOURCE CANDIDATE; not hosted):** [single navigation desk](site/gate12_hub.html) · [content quality, code health, Pages/deployment and runtime actions](notes/GATE12_DOV_OPERATING_PLAYBOOK.md) · [source-bound KPI projection](site/gate12_data.json) · [252-slot Top21 x H01-H12 owner queue](site/gate12_bd_queue.csv). The observed focus-five 14/60 historical PASS remains separate from the 192 unassessed Top21 slots; live Pages parity, operational health and owner acceptance are unqualified.

## CI/CD DAG + SIPOC (2026-10-23)

**CI/CD DAG + SIPOC update (23 October 2026):** [Interactive DAG / SIPOC](site/cicd_dag.html) · [model JSON](site/cicd_dag.json) · [function ⇄ SHA ⇄ OID crosswalk CSV](site/cicd_dag_crosswalk.csv) · [Mermaid total](diagrams/CICD_DAG_TOTAL_FUNCTION.mmd) ([SHA](diagrams/CICD_DAG_TOTAL_SHA.mmd), [OID](diagrams/CICD_DAG_TOTAL_OID.mmd)) · [Mermaid orchestrators](diagrams/CICD_DAG_ORCHESTRATORS_FUNCTION.mmd) · [policy](data/CICD_DAG_POLICY.json). One process model in seven views: the federation total, each focus repo, and the orchestrating/federating assets (hub, ABACUS, CODEX). Each view has three lenses. FUNCTION shows what the step means. SHA shows the exact commit or snapshot sha256 it was observed on. OID shows the git blob id of the Python, workflow or data object that produces it, plus its `def` symbol. Colour classes: CODE_PURPLE > ROOT_RED (SOURCE_RED / first red) > EVERRED > FAIL > UNKNOWN > PASS, plus P-PROCESS, ISSUE/BD and CROSSWALK. New metrics: ready frontier, blocked-by-ancestor, measurement debt, DMAIC phase yield and rolled throughput yield, critical-path PASS depth, EVERRED ratio, recovery and flake rate, median red age, Code Purple and control-plane state, BD burn-down, and OID/SHA coverage. **N+9 census join:** the DevOps lifecycle census from #784 (`data/DEVOPS_CENSUS_N9.json`, digest-pinned in the policy) adds an S0..S9 lifecycle chain to the total and per-repo views, linked by crosswalk edges to the H gates and the P-loop. It also adds a 21-repo maturity heatmap, and test-inventory and deploy-contract (DP1-DP10) nodes. External workflows, input paths and first-red workflows now carry real git blob ids, bound at each repo's census HEAD (shown as `@sha`). Where that HEAD differs from the gate SHA, it is flagged rather than hidden. **#781 reconciliation:** EVERRED, P-process and Code Purple metrics are computed by `mission-control/gogreen/scale_dock.py` (#781) dock functions, not a parallel copy. Its seven cross-source checks show as the *Source consistency* node; a `HOLD_SOURCE_DISAGREEMENT` turns that node FAIL. Validated JADE child, **not staged into Pages** (owner review first). Inputs from `qps-triage-ultra/p-process` are OID-bound, so a change there needs a `--write` here.

## N+9 DevOps lifecycle and deploy contract (2026-10-23)

**[Architecture, SIPOC, maturity and adoption waves](devops/DEPLOY_PRODUCTION_ARCHITECTURE_N9.md)** · **[Generated census reading](devops/DEVOPS_CENSUS_N9_READING.md)** · **[Census data](data/DEVOPS_CENSUS_N9.json)** · **[Census tool](devops/README.md)** · **[N+9 checkpoint](DROPIN_NEXT_CHAT.md)**.

- **What it measures:** ten lifecycle stages, S0 PLAN to S9 CONTROL. Each stage has 5 probes on a cumulative L0–L5 ladder, a formalization status, and exact-head git ids plus `jade:` OIDs for every node.
- **Deploy contract:** DP1–DP10, with the reusable workflows `jade-reusable-ci.yml` and `jade-reusable-deploy.yml`.
- **Shipped:** #784 merged, plus W1 #786 (the hub Pages publisher pinned; it passes DP1–DP10).
- **Reading:** deploy, operate and monitor are the least mature stages. 0/34 deploy jobs passed the core contract before W1.
- **Open:** waves W2–W6 and the CODEX DP6 pin. API-backed probes stay UNKNOWN until a token-backed refresh runs; unknown is not zero.

## N+8 red-trace federation ledger (2026-10-20)

**N+8 update (20 October 2026):** [Red-trace federation ledger](site/redtrace.html) · [16:9 slides](site/redtrace-slides.html) · [interactive PDF](site/redtrace-slides.pdf) · [federation snapshot](data/RED_TRACE_FEDERATION_N8.json) · [gap analysis](data/GAP_ANALYSIS_N8.json). EVERRED / GREEN→RED / RED→GREEN for the 5 core repos (hub, ABACUS, CODEX, cryoplant-project, gg_MATH), break windows to the first red run, stale/pinned flags, a gap analysis of what our own tooling could not answer, and explicit `AGENT` / `OWNER` / `CI` actor badges. Validated JADE child, **not yet staged into Pages** (gap G13: the hosted-parity contract pins the public asset set; owner review first).

## N+6 read-only point-release dependency and mop-up candidate (2026-10-19)

This **staged branch**, not the accepted JADE publisher or a governed merge, adds a source-bound Top21 dependency/neuron/GOLDEN thread ledger. It does not create a competing scheduler, Pages deployment, automatic release or authority transfer.

- [N+6 owner-based mop-up / parked release checkpoint](notes/NPLUS6_POINT_RELEASE_MOPUP.md)
- [N+6 neural/parallel-lane Mermaid SPINE](diagrams/JADE_TOP21_NEURAL_NPLUS6.mmd)
- [N+6 machine-readable typed nodes/edges/Golden thread](data/POINT_RELEASE_NPLUS6_NEURAL_READONLY.json)
- Existing `sprint/Start-JadeSprint.ps1` and `sprint/cli.py` remain the sole bounded local sprint entrypoints.

Readback: 21/21 non-atomic HEAD identities, 146 ordinary open issues, 18 ordinary open PRs; canonical root counts and J5 owner-accepted releases remain **UNKNOWN**. A separately generated interactive HTML atlas passed local responsive QA, but **is not currently part of the published source-controlled Pages child**. Port its visualization through the existing single-publisher generator only after owner review, exact-source parity and noncompensating J3/J4 acceptance. `MERGE_ADMISSION=HOLD`.

## N+3 strict eight-point MIP (2026-10-19)

**N+3 update:** [8-point MIP audit](site/eightpoint.html) · [full source decisions](notes/EIGHT_POINT_MIP_DOV.md) · [current frozen 21-repo technical queue](notes/TOP21_TECHNICAL_QUEUE_NPLUS3.md) · [8-point deterministic manifest](site/eightpoint-manifest.json) · [CP.RESUME](DROPIN_NEXT_CHAT.md). It is a separate candidate from newer Mission Control main after JADE N+2 #733 merged; NOT an accepted point release or hard gate.

**N+3 strict eight-point project entry:** [eight-point MIP dashboard](site/eightpoint.html) · [all eight MIP decisions](notes/EIGHT_POINT_MIP_DOV.md) · [Top21 owner queue](notes/TOP21_TECHNICAL_QUEUE_NPLUS3.md). Exact 21-repo readback changed heads=4, owner-qualified closures=0, current release admission=HOLD.

## N+2 burn-down, stop rules and restart (2026-10-19)

**N+2 update (19 October 2026):** [Measured burn-down and stop rules](site/burndown.html) · [Current 21-source readback](data/READBACK_NPLUS2.json) · [First-red / GoGREEN evidence events](data/EVIDENCE_EVENTS_NPLUS2.json) · [Source-bound stop model](data/STOP_MODEL_NPLUS2.json). The N+1 PR #732 merged, and native JADE plus current-main Method Atlas succeeded; independent JADE hosted SHA and effective human approval remain separate HOLD gates.

**[Measured Top21 / MIP / stop dashboard](site/burndown.html)** · **[21 current heads](data/READBACK_NPLUS2.json)** · **[Strict stop model](data/STOP_MODEL_NPLUS2.json)** · **[Source-bound first-red events](data/EVIDENCE_EVENTS_NPLUS2.json)** · **[Next-chat receiver](DROPIN_NEXT_CHAT.md)**. Do not mix 13/21 historical GoGREEN overlap with full fleet admission, or issue closure with an executable native test. Three source-matched zero-gain terminal pulses pivot the measurement route; they do not waive independent acceptance.

## N+1 GoGREEN implementation and technical TODO (2026-10-18)

**N+1 source-owned Mission Control pilot.** Bootstrap PR [#729](https://github.com/GBOGEB/pipeline-automation-hub/pull/729) is merged. Later implementation must remain separately qualified on its exact PR head. JADE is **not** a second cohort source, CI scheduler, issue/BD root ledger, QPS engineering SSOT, or Pages publisher.

**[New project README](README.md)** · **[GoGREEN interactive dashboard](site/green.html)** · **[Technical launch TODO for all 21 repos](notes/REPO_TECHNICAL_NEEDS_NPLUS1.md)** · **[Full MIP/DMAIC analysis](notes/MIP_ANALYSIS_NPLUS1.md)** · **[Shared root/navigation/Pages contract](notes/NAVIGATION_PAGES_STYLE_CONTRACT.md)** · **[N+1 lossless restart](DROPIN_NEXT_CHAT.md)**.

Top21 structural census and GoGREEN merged-outcome sample have a **13-repository overlap and eight disjoint members in each**; do not mix source denominators. 21 heads were observed non-atomically 18 October. Native point-release eligibility and hosted HTTPS SHA parity remain UNKNOWN. The N+1 site is prepared as an existing-portal Pages child, not a second publisher.

**Acceptance at N+1 (historical).** Local N+1 source/negative tests **44/44 PASS**, browser three responsive viewports **3/3 PASS** using exact HTML/CSS/JS assets inlined in an admin-blocked browser environment; native exact-head and hosted Pages proof **pending**. The existing N11 source provides 26,836 tracked file atoms, 880 root files and 706 filename/path review candidates. `MERGE_ADMISSION=HOLD` and point-release qualified denominator UNKNOWN.

## J0 bootstrap (2026-10-18)

**Merged bootstrap:** [Mission Control PR #729](https://github.com/GBOGEB/pipeline-automation-hub/pull/729) merged 18 October 2026; N+1 is a separate source-owned candidate. The old 13 bootstrap additions are not the current readiness view.

---

**Nav:** [← 09 Project upload guide](09_PROJECT_UPLOAD_GUIDE.md) · [Index](00_START_HERE.md)
