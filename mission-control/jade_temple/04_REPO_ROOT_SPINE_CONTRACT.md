# Proposed root entrypoint + repo SPINE contract v0 (soft pilot)

> **Doc** JT-04 · **Status** PROPOSAL · **Release** UNNAMED (owner sets SemVer) · **Admission** `MERGE_ADMISSION=HOLD` · **Updated** 2026-10-31

## Discovered reality / compatibility

GitHub displays repository README by its actual case-sensitive path; the 2026-10-18 root listing observed **20 `README.md` files and one `ReadMe.md` (`yaml-grammar`)**, not absence of a README. `CODEX` already contains `GLOB.yaml` and `GLOB_POLICY.md`; `GEMINI` has `repo_manifest.yaml`; `Q_engineering_tools` has root `index.html`. Do not overwrite or standardize these unilaterally.

## Recommended portable, add-only proposal

```text
repo-root/
  README.md                  # preserve actual spelling, human GitHub front door
  .jade/repo.yaml            # OPTIONAL owner-approved manifest / pointer, not a new SSOT
  docs/START_HERE.md         # optional concise human index; preserve existing equivalents
  docs/site/index.html      # source-built HTML candidate; hosted location chosen by owner
  src/ or package/ or kernels/# actual existing source root (do not rename)
  tests/                     # real tests (or repo-native equivalent)
  .github/workflows/         # existing CI, no unreviewed protection changes
  pyproject.toml | package.json | go.mod | Cargo.toml | requirements*.txt | ...
```

The contract defines required *meaning*, not obligatory file layout or language. Inspect readme, owner, file map, entrypoint, package/runtime manifests, build/test commands, docs/HTML route, release/tag policy, security/CI, canonical issue/BD paths and SHA-bearing federation edges. A dynamic `glob.yaml` may stay as-is; never assume one filename is universal.

## Manifest schema *candidate* (additive owner-owned pointer)

```yaml
schema: jade-caste/repo-pointer/v0
repository: GBOGEB/example
observed_commit: null      # required only in dated derived census, not immutable repo doc
canonical_readme: README.md
source_roots: []           # actual verified relative paths
build_entrypoints: []      # e.g. pyproject.toml, package.json, go.mod, workflow
canonical_issue_queue: null
site:
  source_path: null
  hosted_url: null
  served_sha: null
release:
  owner: null
  version_policy: null
  last_qualified_tag: null
governance:
  proposed_tier: null
  effective_protection_evidence: null
```

## Non-breaking convergence DAG

`DISCOVER → classify by ownership/use → propose manifest links → add alias/redirect → grep + import/URL/workflow consumer census → parallel owner review → test old and new paths → migrate one owner slice → recheck history+Pages+release → retire only after explicit approvals`.

Forbidden: bulk root shuffle, any automatic deletion, rename without grep/import/Pages/CI consumer proof, moving engineering truth into JADE, using stem-matched formats as proof of duplicate content, editing upstream-derived replicas without an owner applicability decision. Existing N11 root steward recognizes `KEEP_JUSTIFIED`, `CANONICAL_ROOT`, `LINK_ALIAS_FIRST`, `MOVE_WITH_CONSUMER_REPLAY`, `ARCHIVE_PRESERVE_LINKS`, `WAIT_OWNER`.

---

**Nav:** [← 03 JADE_CASTE method](03_JADE_CASTE_METHOD.md) · [Index](00_START_HERE.md) · [05 MACH tiers →](05_MACH_TIERS.md)
