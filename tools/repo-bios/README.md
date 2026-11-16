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
