# JADE_TEMPLE / JADE_CASTE — Top21 GoGREEN launch-readiness pilot

> **Doc** JT-R · **Status** ACTIVE · **Release** UNNAMED (owner sets SemVer) · **Admission** `MERGE_ADMISSION=HOLD` · **Updated** 2026-10-31

JADE_TEMPLE is the read-only presentation and handover project for owner-approved next point-release readiness of the Mission Control `MISSION_SELECTED_TOP21` cohort. JADE_CASTE is its readiness ladder, J0 to J5 ([method](03_JADE_CASTE_METHOD.md)). JADE is **not** a second cohort source, CI scheduler, issue/BD root ledger, QPS engineering SSOT, or Pages publisher.

## Release status

| Item | State | Where |
|---|---|---|
| Merge admission | `MERGE_ADMISSION=HOLD` | [05 MACH tiers](05_MACH_TIERS.md), P0 factual guard |
| Point release | Unnamed; qualified denominator UNKNOWN | Owner names the SemVer |
| Hosted Pages | N+1 and N+2 children are staged at `/jade/` through the existing publisher; hosted HTTPS SHA parity UNKNOWN. H01–H12, CI/CD DAG and red-trace children are **not staged** | [Pages contract](notes/NAVIGATION_PAGES_STYLE_CONTRACT.md) |
| Latest checkpoint | FOCUS5 pulse P0003, 2026-10-31 | [DROPIN_NEXT_CHAT.md](DROPIN_NEXT_CHAT.md) |
| History | J0 bootstrap to N+11, newest first | [CHANGELOG.md](CHANGELOG.md) |

## Start here

| I want to… | Open |
|---|---|
| Review all H01–H12 gates as owner | [Gate12 DoV cockpit](site/gate12_hub.html) · [playbook](notes/GATE12_DOV_OPERATING_PLAYBOOK.md) · [KPI projection](site/gate12_data.json) · [252-slot owner queue](site/gate12_bd_queue.csv) |
| See the CI/CD process model | [Interactive DAG / SIPOC](site/cicd_dag.html) · [model JSON](site/cicd_dag.json) · [crosswalk CSV](site/cicd_dag_crosswalk.csv) · [policy](data/CICD_DAG_POLICY.json) |
| Trace reds across the federation | [Red-trace ledger](site/redtrace.html) · [16:9 slides](site/redtrace-slides.html) · [interactive PDF](site/redtrace-slides.pdf) |
| Check eight-point MIP acceptance | [8-point MIP audit](site/eightpoint.html) · [decisions](notes/EIGHT_POINT_MIP_DOV.md) · [Top21 owner queue](notes/TOP21_TECHNICAL_QUEUE_NPLUS3.md) |
| Follow burn-down and stop rules | [Burn-down](site/burndown.html) · [stop model](data/STOP_MODEL_NPLUS2.json) |
| Browse the 21-repo GoGREEN view | **[GoGREEN interactive 21-repo dashboard](site/green.html)** · **[Top21 overview / N0](site/index.html)** · **[21 owner TODOs and source identity](notes/REPO_TECHNICAL_NEEDS_NPLUS1.md)** · **[MIP/DMAIC control analysis](notes/MIP_ANALYSIS_NPLUS1.md)** · **[Machine CSV queue](site/top21_bd_queue.csv)** |
| Read the DevOps lifecycle census | [Architecture / SIPOC](devops/DEPLOY_PRODUCTION_ARCHITECTURE_N9.md) · [N11 census reading](devops/DEVOPS_CENSUS_N11_READING.md) |
| Apply the shared look and Pages rules | **[Navigation, styling and Pages implementation contract](notes/NAVIGATION_PAGES_STYLE_CONTRACT.md)** |
| Resume in a new chat | [00 Start here](00_START_HERE.md) · **[Recursive next-chat drop-in](DROPIN_NEXT_CHAT.md)** |

## What is authoritative

| Information | Controlled by | Read-only JADE view |
|---|---|---|
| Mission-selected 21-repo structural cohort | `mission-control/federation-atlas/central/top21/TOP21_COHORT_ROSTER.json` | `data/REPO_READINESS_NPLUS1.json` / `data/COHORT_CROSSWALK_NPLUS1.json` |
| Historical GoGREEN check evidence | `mission-control/gogreen/merged_outcome_census/snapshots/` | Historical `green/red/unknown` only; **13/21 overlap** |
| Repo code, exact-head Actions and release | Each original repo and eligible owner | Non-atomic readback and proposed TODO, no inferred acceptance |
| QPS engineering | `cryoplant-project` | Link/reference-only |
| CODEX federation and ABACUS evidence/admission | Their owner repositories | Typed reference-only |
| Pages release | Existing `federation-atlas/pages_portal.py` and method-atlas workflow | Static hash-checked child `/jade/`, no second publisher |

## Build, check and regenerate (offline)

All commands run from the repo root without network.

```bash
# N+1 dashboards and the full JADE test suite
python mission-control/jade_temple/site/build_dashboard.py --check
python mission-control/jade_temple/site/build_green.py --check
python -m unittest discover -s mission-control/jade_temple/tests -p 'test_*.py' -v
# N+2 burn-down, stop rules and browser QA
python mission-control/jade_temple/site/build_burndown.py --check
python mission-control/jade_temple/tools/stop_rules.py
python mission-control/jade_temple/tools/run_nplus2_browser_qa.py
# CI/CD DAG + SIPOC
python mission-control/jade_temple/tools/cicd_dag.py --check
python mission-control/jade_temple/site/build_cicd_dag.py --check
# N+8 red-trace
python mission-control/jade_temple/tools/build_redtrace_data.py --reports <dir-with-repo/red_trace.json>
python mission-control/jade_temple/site/build_redtrace.py --check
python mission-control/jade_temple/tools/render_redtrace_pdf.py
python mission-control/jade_temple/tools/run_redtrace_browser_qa.py
# Root docs: masthead, nav footer and relative links of README, 00-09 and CHANGELOG
python mission-control/jade_temple/tools/root_docs.py --check
```

Deterministic sources are in `data/`. `site/green_template.html`, `site/jade.css` and `site/jade.js` are the editable presentation inputs. `site/green.html`, `site/jade_data.js`, `site/snapshot.json`, `site/top21_bd_queue.csv` and `site/site-manifest.json` are deterministic read-only outputs; do not hand edit the generated assets. `portal_bridge.py` validates and stages them as one scoped subtree in the existing publisher.

An existing-portal-only child at `/jade/burndown.html`; hosted verification is performed independently **after** `deploy-pages` and hashes actual served files against the exact source-bound publisher artifact. No alternate workflow publishes Pages.

### Regenerating after OID / digest drift

The generated DAG outputs (`site/cicd_dag.json`, `site/cicd_dag_crosswalk.csv`, `site/cicd_dag.html`, `diagrams/CICD_DAG_*.mmd`) pin the git blob OIDs of the p-process files (`mission-control/qps-triage-ultra/p-process/**`), `mission-control/gogreen/scale_dock.py`, the workflows and the census, plus sha256 digests of every input. A change to any of them makes the JADE QA check red. The failure names each drifted source file with its old and new OID or digest (`drifted sources: ...`) and prints the one command that fixes it. Run it from the repo root and commit the outputs:

```bash
python mission-control/jade_temple/tools/cicd_dag.py --write && python mission-control/jade_temple/site/build_cicd_dag.py
```

A census refresh changes `data/DEVOPS_CENSUS_N9.json` and its digest. Re-pin `devops_census.digest_sha256` in `data/CICD_DAG_POLICY.json` first; the load error names the file and the command. When two open PRs both touch pinned inputs, whichever merges second must re-run the command on top of the first.

### One pulse (census vs gate snapshot)

The census and the latest gate snapshot (`data/ROLLING5_PULSES.json`) are two reads of the same focus repos. `pulse_alignment` in `site/cicd_dag.json` gives each focus repo `pulse_mismatch` (census SHA ≠ gate SHA, or not in the census) and a `mismatch_count`. Each REPO scope carries the same `pulse_mismatch`, and the page shows a *Pulse alignment* table. Pass `--strict-pulse` to either builder to fail on any mismatch. CI leaves it off for now, because the current census was read at newer commits than gate pulse P0001 for 4 of 5 focus repos. Turn it on in `.github/workflows/jade-temple-readonly-qa.yml` once both snapshots are re-taken in one pulse.

### Option: generate in CI (not enabled)

CI could regenerate the outputs instead of only checking them. A workflow step would run the regen command on the PR head and fail with the resulting `git diff` (or upload it as an artifact), so contributors never hand-regenerate. Alternatively, a bot commit could push the regenerated files to the PR branch. Neither is wired up: the current contract keeps generated outputs committed, reviewed and byte-checked (`--check`). A bot commit would also need `contents: write` on a workflow that is read-only today.

## Recent changes

Newest first; the full history, with the original dated banners, is in [CHANGELOG.md](CHANGELOG.md).

- **2026-10-31** — FOCUS5 pulse P0003 checkpoint; W1 root-docs launch look (this masthead, nav footer and `root_docs.py`).
- **2026-10-26** — N+11 re-census and private boundary.
- **2026-10-23** — H01–H12 DoV owner cockpit, CI/CD DAG + SIPOC, N+9 DevOps lifecycle and deploy contract.

---

**Nav:** [Index](00_START_HERE.md) · [00 Start here →](00_START_HERE.md)
