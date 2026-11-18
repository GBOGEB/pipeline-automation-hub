# Exact-commit repository BIOS report

From the hub root, with its existing PyYAML dependency installed:

```bash
python tools/repo-bios/report.py \
  --repo GBOGEB/pipeline-automation-hub=/path/to/pipeline-automation-hub \
  --repo GBOGEB/CODEX=/path/to/CODEX \
  --repo GBOGEB/ABACUS=/path/to/ABACUS \
  --repo GBOGEB/gg_MATH=/path/to/gg_MATH \
  --repo GBOGEB/cryoplant-project=/path/to/cryoplant-project \
  --entry GBOGEB/pipeline-automation-hub=scripts/run_processing.py \
  --out /path/outside/git/repo-bios-report
```

Open `index.html` locally. It provides searchable per-repository statistics,
workflow upstream/downstream/wave drilldowns, source OIDs and ADR/AHT path
candidates. `report.json` retains all data; `report.md` is the compact report.
Add repeated `--entry OWNER/REPO=path` arguments for explicitly scoped main
pipeline files. No entry selection means UNKNOWN, not zero pipeline LOC.
Use `--metric OWNER/REPO=path/to/metrics.json` to include committed DMAIC/KPI
documents verbatim with their blob OID and SHA-256. These retain their original
scope and time windows: copying a historic value does not verify a current KPI.

Reads each HEAD once and all content from that commit's tree via `git cat-file`;
dirty, untracked and staged changes do not affect measurements. Repositories are
read sequentially, **not an atomic fleet snapshot**. Missing/incomplete objects
fail generation. Workflow parsing and Kahn ordering reuse the JADE owners.
Direct root workflow YAML files are active workflow candidates; nested legacy
YAML files are excluded. Conditions, matrix expansion, external dependencies,
live blockers and native test execution are not evaluated.

Language LOC is physical lines, including comments/blank lines, for the declared
extension map. Unmapped, binary and symlink objects are separately accounted;
symlinks are never followed. Tests and generated/vendor paths use documented
name heuristics and can overlap; do not sum these as disjoint populations.
ADR and AHT discovery is path-based, not semantic validation. No remote source
code or workflow is executed. No secrets, runtime health or approvals are read.
Runtime KPIs are UNKNOWN and point to the existing owners, not recomputed here.

Outputs must be outside every scanned Git worktree. Reports can contain private
paths, decisions and source links: keep them private unless the source owner
authorizes a separate public projection. Do not commit a mixed private report.
The HTML has no CDN or automatic network requests; source links require an
explicit click. JSON's SHA-256 is in `SHA256SUMS` with the other report outputs.

Verification:

```bash
python -m unittest discover -s tools/repo-bios -p 'test_*.py' -v
```

See the root [BIOS](../../REPO_BIOS.md) for purpose, topology, SIPOC, lane matrix,
ADR/OID development, existing metric ownership and next dependency-ready slices.

## Development map: explicit pipeline scope, SIPOC, ADR and job observations

Add `--profiles tools/repo-bios/profiles.json` to enable the development view.
Profiles select source files and workflows for review; they do not declare an
entire repository's transitive main pipeline. Each pipeline has its own entry
LOC, source OIDs, Kahn SVG, clickable/keyboard job panel and SIPOC card. Repeated
files across pipeline cards are counted once in the repository entry-LOC total.
Purpose, entry scope and ADR crosswalks are review declarations bound to current
source blobs. They are not owner acceptance or a new graph authority.

The public profile intentionally contains no private cryoplant paths. Copy it
outside Git and add private pipeline/decision selectors there to build a mixed
private report. An unconfigured private profile stays `PRIVATE_PROFILE_REQUIRED`.

ADR extraction recognizes explicit `Status:`, `Owner:` and `Authority:` lines,
including bold Markdown labels, or corresponding `##` sections. It preserves
source text and line numbers. Even `Status: ACCEPTED` remains a source declaration;
acceptance is `NOT_EVALUATED`. `REVIEW_CROSSWALK` links are context, never hard edges.

Optional `--job-observations /private/job-observations.json` takes a list of
records with these fields:

```json
{
  "repository": "OWNER/REPO",
  "source_sha": "exact source commit SHA",
  "workflow": ".github/workflows/ci.yml",
  "workflow_blob_oid": "exact workflow blob OID",
  "job_key": "build",
  "run_id": 100,
  "job_id": 200,
  "run_attempt": 1,
  "run_url": "https://github.com/OWNER/REPO/actions/runs/100",
  "job_url": "https://github.com/OWNER/REPO/actions/runs/100/job/200",
  "observed_at": "2026-11-18T11:00:00Z",
  "completed_at": "2026-11-18T10:00:00Z",
  "status": "completed",
  "conclusion": "failure"
}
```

The example is a schema illustration, not a real execution record. An importer
must map a native job name to one unambiguous YAML job key; matrix/ambiguous names
must remain unmapped. Freshness defaults to 86,400 seconds from **completion**,
not collection, configurable with `--max-age-seconds`. Source/OID drift, missing
identity, invalid URLs, future/stale timestamps or no data remain UNKNOWN.

The newest matched observation wins over an older green. Displayed states are
`REPORTED_*`, not verified test/coverage/admission proof. Failed direct
prerequisites and unobserved prerequisites are separate lists. Conditions,
artifact integrity and review/owner/environment gates remain unevaluated even
when all job metadata says success. Reusable calls and environments are shown as
context relations; only declared same-workflow `needs` edges enter this graph.
Critical-path/float/unlock metrics remain with the existing owner and PR #1276.

The new test collector at
`mission-control/jade_temple/devops/tests/test_devops_repo_bios.py` includes this
suite in the existing JADE offline workflow, without changing workflow permissions
or adding a publisher. Native execution still needs an actual run receipt.
