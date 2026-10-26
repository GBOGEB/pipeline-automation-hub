# JADE N+9 DevOps lifecycle: fleet census, deploy contract, reusable CI/CD

Read-only measurement and standardization of the full DevOps lifecycle (S0 PLAN … S9 CONTROL) across the TOP21
roster in `../data/TOP21_PORTFOLIO.json`. It covers the hub, ABACUS, CODEX, cryoplant-project, gg_MATH and the
EXPAND/SUPPORT lanes. Design, maturity model and the deploy/production reference architecture:
[DEPLOY_PRODUCTION_ARCHITECTURE_N9.md](DEPLOY_PRODUCTION_ARCHITECTURE_N9.md).

| Asset | Role |
|---|---|
| `lifecycle.py` | Stages, SIPOC, probes, L0–L5 ladder, formalization (pure functions) |
| `workflows.py` | Workflow parser, job needs-DAG, lifecycle signals, deploy contract DP1–DP10, `lint` CLI |
| `census.py` | `fetch` (blobless git), `scan` (exact-head evidence), `check` (offline invariants) |
| `../data/DEVOPS_CENSUS_N9.json` | Committed fleet snapshot (`jade.devops.census.v1`) |
| `../data/DEVOPS_OBJECTS_N9.json` | Object table: every Python module and test file with its git blob id |
| `../../../.github/workflows/jade-reusable-ci.yml` | Reusable CI: exact SHA, zero-test guard, coverage floor, sha256 manifest |
| `../../../.github/workflows/jade-reusable-deploy.yml` | Reusable deploy: admit, verify digest, serialized environment, readback, receipt |
| `templates/jade-cicd-caller.yml` | Drop-in caller for any repository |
| `../../../.github/workflows/jade-devops-census.yml` | Offline qualification on change; weekly read-only refresh + drift report |
| `DERIVED_OUTPUTS_ROLLUP.md` | Derived-outputs plan P0–P4: phase owners, TODO, fan-out order, REX |
| `DR_DERIVED_OUTPUTS_OWNERSHIP.md` | Decision record (proposed): master owns derived outputs (D), semantic function pins (E) |

## Run

```bash
python mission-control/jade_temple/devops/census.py fetch --cache ../_jade_cache
```

```bash
python mission-control/jade_temple/devops/census.py scan --cache ../_jade_cache
```

```bash
python mission-control/jade_temple/devops/census.py check
```

```bash
python -m unittest discover -s mission-control/jade_temple/devops/tests -p "test_devops_*.py"
```

`fetch` uses `git clone --bare --filter=blob:none --depth=1` plus one batched blob fetch per repository for the
classified paths only. Nothing is checked out or executed from a scanned repository. `scan` probes
`https://gbogeb.github.io/<repo>/` and, with `--api-token-env NAME` (opt-in), the public REST API. Without a token
it uses the unauthenticated 60/h quota and records every unanswered fact as UNKNOWN.

## Identity: two IDs on every node

* **Git object id** (40-hex): `head_sha` (commit), `tree_oid`, `blob_oid`. Each equals
  `git rev-parse <commit>:<path>`, so another tool can join on it.
* **Descriptive OID** (URN): `jade:repo:<owner>/<name>`, `jade:wf:<repo>:<path>`, `jade:job:<repo>:<path>#<job>`,
  `jade:file:<repo>:<path>`, `jade:py:<repo>:<dotted.module>`, `jade:stage:<Sx>`. Job definitions also carry a
  `def_sha256` of their canonical YAML mapping.

## Rules

UNKNOWN is never PASS. No merge, release or deploy authority is derived (`merge_admission=HOLD`). Signals are
static heuristics and labelled as such. The census `digest_sha256` covers the whole document, and `check`
recomputes every stage level from its probes.
