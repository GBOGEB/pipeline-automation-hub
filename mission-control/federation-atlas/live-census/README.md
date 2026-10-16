# CODE PURPLE — Live Disjoint Census / Diagnostics Feed

**Release**: 2026-10-16, local producer and read-only draft publication candidate. **Admittance: HOLD.** No remote GitHub mutation, branch merge, engineering root closure, security waiver, crew dispatch or QPS owner promotion is effected by this package.

## Start (Python 3.11+)

```sh
python source/live_census.py --verify output
python -m unittest discover -s tests -p 'test_*.py' -v
python source/serve.py --out output --view view --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765/`. Its source is a **dated connector snapshot**, not a continuously running native feed. A `--refresh` command performs new read-only GET requests to the allowlisted GitHub repositories and PRs; it requires network connectivity (and optionally `GITHUB_TOKEN` with read-only access):

```sh
python source/live_census.py --refresh --previous output/snapshot.json --out output
python source/live_census.py --verify output
```

In a fresh checkout, `--previous` is optional; omit if no verified previous dataset exists. A new head invalidates a previously green status, which stays historical. Collected workflow runs are **associated** with PR source; without actual job checkout and artifact member receipts, they remain unqualified as exact-checkout proof. A collection error fails closed rather than inventing zeros.

## Docker / docking / ports

```sh
python source/live_census.py --seed data/observed_fixture.json --out output
docker compose up --build -d
docker compose ps
curl --fail http://127.0.0.1:8765/healthz
curl --fail http://127.0.0.1:8765/metrics
```

`compose.yaml` binds host `127.0.0.1:8765` only. The container is unprivileged, read-only, drops Linux capabilities, forbids privilege escalation and only mounts the generated data read-only. It **does not collect from GitHub**; collector refresh is a separate read-only Python command, or a governed GitHub Actions job. The runtime never performs repository mutations. Docker was **not run in the ChatGPT sandbox** (Docker unavailable), so actual Docker health is unverified.

## Endpoints

| Endpoint | Role |
|---|---|
| `/` | CODE PURPLE UI, dark/light theme, PR filtering and graph navigation |
| `/healthz` | server/port readiness, no engineering authority |
| `/metrics` | Prometheus-format real observed counts; does not fake closed-root=0 |
| `/api/v1/snapshot` | source-bound normalized snapshot |
| `/api/v1/nodes` | actual graph nodes, with typed identities |
| `/api/v1/edges` | declared evidence edges only; `admitted=false` |
| `/api/v1/events` | NDJSON source change / stale-proof events |
| `/api/v1/stream` | short SSE feed, heartbeats and digest updates |
| `/api/v1/diagnostics` | missingness and monitoring data |

## Existing MissionControl / Pages owner

This is an **isolated candidate**, intended to plug into `GBOGEB/pipeline-automation-hub` via a *new path lease*: `mission-control/federation-atlas/live-census/**` and `docs/code-purple-live/**`. It deliberately does not edit the incumbent `mission-control/federation-atlas/pages_portal.py` or `docs/index.html` because concurrent Pages PRs #570/#572 own related publication changes. In native PR publication, `docs/code-purple-live/` displays only its dated static `snapshot.json`; it does not become a live updating site merely because files exist on a review branch. The canonical publisher/owner must admit the PR and confirm the GitHub Pages source and URL separately. Do not enable a second competing publisher.

## Authority and SSOT

| Concept | Classification |
|---|---|
| Repository refs, PR metadata | GitHub observed, exact remote references |
| PR workflow totals | PR-associated, **not** actual checked-out source proof |
| Root candidates | stable declared categories for source-owned repair routing |
| Causal root closed counts | **UNKNOWN** (not zero), until accepted root-specific REX + main checks |
| `#2060` merged to intermediate C5 | **MERGED_INTERMEDIATE_NOT_MAIN** |
| Historical B9 | 253/625, 40.48%, 80% target on different checkout |
| Queue p50/p95 | UNKNOWN, job queue clock receipts needed |
| PCA / Bradley–Terry | WITHHELD pending independent eligible data |
| ABACUS admission | HOLD, issue #1860 |
| CODEX dispatch | STAGED_NOT_LAUNCHED, issue #977 |
| QPS engineering acceptance | DEFER, independent owner |

## Testflight and evidence

`python -m coverage run --branch --source=source -m unittest discover -s tests -p 'test_*.py' -v`

`python qa/browser_qa.py` exercises desktop, laptop and mobile interactions. The managed sandbox blocks browser localhost navigation, so the recorded successful browser checks run in-memory using exactly the same HTML/CSS/JS with a frozen schema-valid fixture; HTTP routes have separate native Python tests. Browser QA does **not** authenticate the local HTTP GUI in a real browser. Re-run both on a normal local PC or native CI runner before release.

## Owner closure / stage transition

**Read:** compare GitHub source HEAD, PR head/base, run/job/attempt, actual checkout SHA, artifacts and source semantics. **Diagnose:** join first-red -> fingerprint -> stable candidate root -> canonical owner. **Repair:** source-owned disjoint branch lease, positive and adversarial tests. **Proof:** native exact-head with matched denominators, scanner and A10 gates, independent review, effective protection. **Publish:** approved Pages owner promotes only the read-only view. **Close:** root-specific accepted REX proof and exact-main recurrence; never close from the UI, archived PR merge or graph candidate alone.

Canonical issues: [ABACUS #1929](https://github.com/GBOGEB/ABACUS/issues/1929), [ABACUS #1860](https://github.com/GBOGEB/ABACUS/issues/1860), [CODEX #977](https://github.com/GBOGEB/CODEX/issues/977). Linked PRs include #2006, #2059, #2046, #2033, #2052, #2041, #2045, #2051, #2054, #2057, #2060.
