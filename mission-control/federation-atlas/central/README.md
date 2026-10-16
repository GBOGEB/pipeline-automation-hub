# CODE-HEALTH / Mission Control Central (gg_mCC) — v1 candidate

**Owner and source:** `GBOGEB/pipeline-automation-hub` / existing Method Atlas.
**Status:** `READ_ONLY_CANDIDATE` · `authority_transfer=false` · `merge_authorized=false`.
**Name:** `gg_mCC` is a proposed UI/product alias. `gg_MCrtlCentral` is a
proposed long name only. There is **no** repository of that name and no
repository rename, branch redirect, code move or SSOT promotion is authorized.

This work adds a governed observability *projection* to the existing
`PROCESS_LANES_v1.json`, `METHOD_OBSERVABILITY_v1.json`, `PHASE02_KPI_TAXONOMY_v1.json`
and `CODE_PURPLE_BEAMS_DAG_v1.json`. It shall not create another crew transport
or Pages publisher. The CODE-HEALTH output is included in the existing Method
Atlas artifact, with publication only through that Atlas's existing controlled
owner path after approved merge.

## Two pillars; one Golden Thread

| Pillar | Owner | Qualification | Role |
|---|---|---|---|
| L — LOCAL_COLD | Developer/PC owner | EXACT local checkout + OS/toolchain/command output + digest | Clean clone, preconfig/preflight/precommit, lint & language probes, testflight |
| R — NATIVE_GITHUB_FEDERATED | Repo CI/owner | SHA + native run/attempt/job/step + artifact bytes + gate review | PR, Actions, runners, security, A10, CI governance, independent reviewer, product owner |

The proposed local Windows pilot root `C:\repos` has **not** been accessed.
Local Visual Basic/VBA work is optional, in an isolated trusted VM with
explicit sample provenance; never execute downloaded macros implicitly.
Python/JSON/YAML/TOML/PowerShell and offline cold checks are also proposals
until concrete local receipts are obtained.

Golden Thread identity:

`mission → wave → pulse → repo → branch → PR → exact SHA → workflow run →
attempt → job → step → artifact/member SHA-256 → fingerprint → canonical
BD root → owner/review → downstream consumer → main readback`.

A graph edge can be `DECLARED`, `OBSERVED_HISTORICAL` or `NATIVE_CURRENT`.
Only a separately verified authenticated dispatch plus accepted REX may promote
a Crew return. The historical eight DAB proposal passes are **not** eight Crew
launches. CODEX `mission_control/mycelium/control_manifest.yaml` currently
retains `mutation_enabled=false`. CODEX [#977](https://github.com/GBOGEB/CODEX/issues/977)
owns the executable architecture decision. This UI does not unlock it.

## Cohort — local taxonomy and glossary

**Cohort:** a precisely specified population on which observations can be
compared *without changing the eligible denominator, selection, configuration
or source identity*. A cohort is not the number of tests or PRs; repeated
steps on one SHA are not independently sampled process observations.

| Cohort | Identity / denominator | Not interchangeable with |
|---|---|---|
| `LOCAL_COLD` | checkout SHA × OS/toolchain/config × selected local tests | Native PR success |
| `NATIVE_MATRIX` | workflow, run, attempt, SHA, OS, Python, job / step | Authenticated Crew launch |
| `MATCHED_COVERAGE` | repo, scope, config, eligible lines and branches before/after | Other repo or different branch-scope numerator |
| `RUNNER_CAPACITY` | runner pool × actual UTC window × native job queue/runtime | Guess of available GitHub/Copilot capacity |
| `N_MINUS_1_TO_N` | two frozen compatible snapshots with explicit source times | Source-head churn or issue records as root closure |

Other controlled terms:

- **Atom:** smallest addressable source-bound node (issue, PR, root,
  run/attempt, job, step, receipt, reviewer, artifact, or event). A *defined*
  atom type is not an *observed* atom population.
- **Mycelium:** typed producer→consumer edge system, with shared awareness of
  global dependencies but no transitive transfer of repository authority.
- **Golden Thread:** immutable provenance join from source through execution,
  result, causal root and final consumer.
- **Island:** isolated PR/worker/source lease; cannot claim federation benefit
  without a crosswalk to its parent root and native receipts.
- **Tower:** repo-local authority and review/control layer.
- **Intervening PR:** another moving source head or overlapping changed path;
  triggers recensus before safe fan-in. Current example #561→#563 in Gogreen.
- **DAB:** proposal worker; GitHub job PASS proves an Action ran, not a
  CODEX-authenticated Crew / REX.
- **REX:** accepted native feedback/outcome receipt; unverified remains null.
- **BD root:** deduplicated causal fault under canonical owner and a
  post-repair proof; not a GitHub issue, scanner occurrence or closed alert.
- **3P\***: refresh/probe/rank → prepare/prove/commit method-selection cycle,
  subordinate to actual owner execution permission.
- **DMAIC/MIP:** define, measure, analyze, improve, control/recensus;
  observations and release gates remain separable.
- **PCA / BT:** analyst-only signal/prioritization methods; missing qualified
  independent observations prohibit synthetic eigenvectors/rankings.
- **N−1 / N / N+1:** previous frozen proof, current source-and-critique,
  and pre-outcome prediction/target. Review additions never erase N−1 by silence.

## N−1 / N / N+1 contract

**N−1:** retains earlier evidence, wins, unresolved first-reds and
source-version anchors. **N:** re-pins all exact heads, issue/PR populations,
ownership/changed paths, runner and gate outcomes, and critiques previous
assumptions. **N+1:** declares (separately) conditional forecast, target,
dependencies, expected measurable uplift, resource assumption and unknown
future actual. Later observed results are appended, never retrospectively
invented. Forecast error is UNKNOWN until the next *matched actual* is
available. N+1 must score both wins and regressions after evidence.

Example as of 2026-10-16: six named repos had **143 open issues, 412 closed
issues, 68 open PRs, 5,126 closed PRs**. That is a bounded six-repository
population and is not an estate-wide count or BD-root population. Eight DAB
proposal jobs were earlier reported as passing; no live authenticated Crew
or REX receipts are established in the selected evidence.

### Time, queue and back-pressure

Actual queue duration = `job.started_at - job.created_at`; actual job runtime
= `job.completed_at - job.started_at`; local preflight duration requires
a local monotonic-clock or UTC receipt. No native timestamps = UNKNOWN, never
zero. Job counts alone are not available runner slots, and a workflow-start
proxy is not a native job-created timestamp. Use a coherent UTC window and
observed runner-pool identity before p50/p95 or fan-out scaling.

Source leases are **disjoint paths** with owner and exact parent SHA. A
concurrent change to an owned path triggers WAIT/owner negotiation and an
exact-head rejoin. When runner capacity is unavailable, cold tests and
documenting next first-red are useful; no CI cancellation, skipping
governance, or synthetic worker launch. `MAY_START` is advisory; `MUST_START`
requires an authorized scheduler and actual capacity/approval, not this tool.

### P0 independence

Enterprise CI, governance inventory, A10 confidentiality, Safety, Bandit,
required checks, eligible reviewer and QPS owner's engineering disposition
are **separate non-compensating states**. E.g. ABACUS native [Enterprise
38869180768](https://github.com/GBOGEB/ABACUS/actions/runs/38869180768)
PASS versus [governance 38869180608](https://github.com/GBOGEB/ABACUS/actions/runs/38869180608)
FAIL on the same historical SHA. Neither can overwrite the other. The
candidate disjoint gate-vector producer is
[ABACUS #2033](https://github.com/GBOGEB/ABACUS/pull/2033). CODE-HEALTH
consumes qualified receipts only; it does not replace that owner.

## Execute safely

Cold/source-only (from a checked-out hub repo, POSIX):

```sh
python -m unittest discover -s mission-control/federation-atlas -p "test_*.py" -v
python mission-control/federation-atlas/central/code_health.py
SOURCE_SHA="$(git rev-parse HEAD)"
python mission-control/federation-atlas/central/code_health.py \
  --exact-git-sha "$SOURCE_SHA" --out /tmp/code-health
```

Windows PowerShell pilot, only after the user checks out the repo locally:

```powershell
Set-Location C:\repos\pipeline-automation-hub
python -m unittest discover -s mission-control/federation-atlas -p test_*.py -v
$sha = (git rev-parse HEAD).Trim()
python mission-control/federation-atlas/central/code_health.py `
  --exact-git-sha $sha --out .\build\code-health
```

Optional **read-only native recensus** (never overwrites the controlled input):

```sh
python mission-control/federation-atlas/central/recensus.py \
  --source mission-control/federation-atlas/central/CODE_HEALTH_CENTRAL_v1.json \
  --out /tmp/code-health/recensus-observed.json
```

`GITHUB_TOKEN` or `GH_TOKEN` can be supplied through the environment,
not embedded in generated HTML. For a full GitHub issue-level register rather than counts only, add
`--full-issue-register`. The bounded collector paginates open and closed
issue records for each of the six repositories and retains number, title,
native URL, state, created/updated/closed UTC timestamps and labels. It
rejects duplicate IDs, unexpected PR records, a missing page, search
incompleteness and a mid-scan change in total population. **All retrieved
issue rows have `bd_root_id=null` and `accepted_root_closure=null`** until
separately adjudicated; this is not a 90-repository fleet scan. Metadata
only; no comments, secret-bearing bodies or private files are published.

The collector reads six head commits, 24
issue/PR count populations and owned work-item PR heads. It fails on
incomplete search API results or invalid identity. Native evidence
about other repos, job queues, reviewer approvals and accepted roots
remains UNKNOWN until an appropriate qualified producer supplies it.

The existing Method Atlas workflow is the **single** render/artifact producer.
It runs these tests and emits `code-health.html`, `code-health-dag.mmd`,
`code-health.json` and `code-health-manifest.json`; the existing Pages
publisher picks up the same source-bound artifact only on the governed
`master` workflow. A passing PR artifact is not live Pages publication.

## Observed native time cohort and Windows pilot

Exact ABACUS run [38869180768](https://github.com/GBOGEB/ABACUS/actions/runs/38869180768) (SHA `a752d15cab03dc6671fffce8df2048b93c0787ee`) provides 18 time-complete successful jobs: historical queue p50 19.5 s, queue p95 100 s, runtime p95 182 s, runtime sum 1386 s, and observed peak 11 simultaneous jobs. These are single-run job statistics, **not free runner slots, Crew dispatch, REX or fleet-wide process capability**. All 18 job clock records are preserved in the snapshot.

Windows cold pilot: `central/Invoke-CodeHealthColdPilot.ps1` inspects local HEAD and worktree in dry-run mode unless explicitly invoked with the `-Execute` switch. Optional Visual Basic source fingerprinting never executes files or Office macros. Its receipt remains local-only; `C:\\repos` was not accessed by the assistant. No merge, remote mutation or native CI admission is implied.

## SIPOC and next work

| SIPOC | Content |
|---|---|
| Supplier | local developer/PC owner; GitHub; CODEX stage-only; ABACUS/DOW; QPS; gg_MATH; document owner/reviewers |
| Input | source SHA, changed paths, PR/issue, exact run/attempt/job/step, source configuration, identity-bound artifacts and clock readings |
| Process | N−1 freeze → N recensus → lease partition → cold/native flight → root clustering → independent gate vector → owner disposition → CONTROL |
| Output | CODE-HEALTH diagram/HTML, issue register, BD queue, native telemetry, forecast-vs-actual and carry-over |
| Customer | Mission Control owner, disjoint source owners, eligible reviewers, next N+1 wave, controlled engineering owner |

**Immediate dependencies:** CODEX [#977](https://github.com/GBOGEB/CODEX/issues/977),
ABACUS [#1860](https://github.com/GBOGEB/ABACUS/issues/1860),
Hub [#153](https://github.com/GBOGEB/pipeline-automation-hub/issues/153),
Hub [#520](https://github.com/GBOGEB/pipeline-automation-hub/issues/520),
Hub [#63](https://github.com/GBOGEB/pipeline-automation-hub/issues/63).
Hub Gogreen [#561](https://github.com/GBOGEB/pipeline-automation-hub/pull/561)
and [#563](https://github.com/GBOGEB/pipeline-automation-hub/pull/563)
are intervening code-development owners, not targets for this PR.

**No rename, merge, waiver, remote mutation, worker dispatch, QPS acceptance,
issue closure or native main coverage uplift is attempted.**
