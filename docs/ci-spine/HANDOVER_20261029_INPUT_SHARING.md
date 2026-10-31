# CI Spine × Jacquard × PDF — lossless handover and execution chaperone

**Observation:** 29 October 2026 (Europe/Brussels). **Classification:** frozen GitHub readback and explicit implementation queue; not release authority. **Merge admission: HOLD.**

**Companion (machine-readable):** [NEXT_EXECUTION_20261029.json](NEXT_EXECUTION_20261029.json). **Standing policy:** [AGENTS.md](../../AGENTS.md). Source lineages, DoD/DoV and branch ownership are meant to survive chat/session expiration without loss.

## Mission BIOS / intent / stop condition

Build on GitHub Actions, pinned existing CI/JADE, canonical DAG/SIPOC and Plotly rather than replace them. Focus on the distinctive object-level compendium: RTM/OFFER/EVAL evidence, links to Word/contract source, real PDF/HTML/SVG/Plotly outputs, zoom/layered A3-style views, provenance, review comments and temporal branch/commit histories. Compare Ink & Switch Jacquard fine-grained provenance and Tenfold interactive objects as optional interface ideas; do not run arbitrary shell watchers from browser UI.

**Initial task is DONE only at agreed final scope** when a canonical RTM/offer/source object can be browsed through the UI, linked to exact immutable source/review identities and at least one **physically verified** source-to-PDF page/rectangle in a real owner PDF. The link must survive a controlled recompile or deliberately declare STALE. The UI must show true UNKNOWN/UNMAPPED, not fake zero, green or coordinate precision. Independent exact-head CI, CodeQL/FPC, visual QA and owner review remain separate noncompensating conditions.

## Frozen upstream receipt and status semantics

- Current master at GitHub readback: **e7b5c580fa2f1088c58913c80feeae91e6cd5ad8** (2026-10-29T08:35:02Z). Re-read on restart; it can advance.
- Historical merged #992 catalog baseline: **ca623ab83793df6edd245942884ad5428a5fe079**, 182 workflow source files and 307 test-named files. Do not call these counts a current live census, or executed test counts.
- **MERGED PR #992** at 2026-10-28T15:34:53Z: 6b6118efb3479370d5afd991a7bcbe3de1d907ea.
- **MERGED PR #989** at 2026-10-28T15:54:09Z: 6f7cf145c4ebf585dbb341ba5863e77098ad36b0.
- **MERGED PR #998** at 2026-10-29T08:35:03Z: e7b5c580fa2f1088c58913c80feeae91e6cd5ad8.
- GitHub readback verifies branch refs and PR state; it does **not** reveal uncommitted/untracked Windows worktree files. LOCAL_UNKNOWN remains unresolved until the user's local custody script is run.
- PASS applies to a completed exact-head eligible test with qualified evidence. NOT_APPLICABLE, SKIPPED, CANCELLED, UNKNOWN and DEFER are separate statuses; green badges, no matter how attractive, are not independent certification.

## Complete remote PR branch and stack identity

| PR | Exact branch / head | PR base | Role / handover state |
| --- | --- | --- | --- |
| [#997](https://github.com/GBOGEB/pipeline-automation-hub/pull/997) | refactor/ci-bundle-inventory-lifecycle-pilot-20261028 / 2b0b2622725592edbaa9d0905a4295dc1cbb4d1f | master | B00–B12 candidate CI lifecycle / stale census red; **HOLD** |
| [#1012](https://github.com/GBOGEB/pipeline-automation-hub/pull/1012) | refactor/ci-n1-title-crosswalk-20261028 / 2cd0a37920e6024454e385ac37eec1fa3f356e26 | refactor/ci-bundle-inventory-lifecycle-pilot-20261028 | N1 title adapter STACKED on #997; **HOLD** |
| [#996](https://github.com/GBOGEB/pipeline-automation-hub/pull/996) | feat/ci-spine-authority-index-20261028 / cb782597008c953a97d04cab8b431e6cab1ac974 | master | authoritative read-only CI index; **HOLD** |
| [#1001](https://github.com/GBOGEB/pipeline-automation-hub/pull/1001) | feat/ci-spine-disjoint-wave-controller-20261028 / 39e3d4ca82d6560fdefc594a516a26b0d65cd185 | master | disjoint three-worker planner; **HOLD** |
| [#1006](https://github.com/GBOGEB/pipeline-automation-hub/pull/1006) | feat/ci-spine-source-delta-audit-20261028 / 6827ad91eae632e66ea2b0890d423e706c6de1b3 | master | source-delta audit; **HOLD** |
| [#1016](https://github.com/GBOGEB/pipeline-automation-hub/pull/1016) | feat/ci-spine-w4-readonly-consumer-20261029 / b1d93dbc83c7469246b9388f52b40592d419585c | master | W4 Mission Control read-only consumer; **HOLD** |
| [#1002](https://github.com/GBOGEB/pipeline-automation-hub/pull/1002) | feat/ci-spine-jacquard-provenance-explorer-20261028 / 4cc045d322fb65fef8fb00b2cd93e50bbc52bbd8 | master | five-lens explorer / proposed canonical parent; **HOLD** |
| [#1019](https://github.com/GBOGEB/pipeline-automation-hub/pull/1019) | fix/ci-spine-1002-codeql-script-parser-20261029 / 24279024cbc683670231682c4d4fbfb5b9b6cad2 | feat/ci-spine-jacquard-provenance-explorer-20261028 | CodeQL regex repair child; **HOLD** |
| [#1021](https://github.com/GBOGEB/pipeline-automation-hub/pull/1021) | fix/ci-spine-1002-view-links-unknown-clocks-20261029 / cda6529e855f711c73dbc8cf648913dc5b5406ce | feat/ci-spine-jacquard-provenance-explorer-20261028 | workstream link and UNKNOWN-clock child; **HOLD** |
| [#1018](https://github.com/GBOGEB/pipeline-automation-hub/pull/1018) | feat/ci-spine-jq04-typed-pointers-20261029 / b3389e9f4fc9d4809abf2b2a1ef168254c474041 | feat/ci-spine-jacquard-provenance-explorer-20261028 | source→HTML pointers child; PDF not mapped; **HOLD** |
| [#1017](https://github.com/GBOGEB/pipeline-automation-hub/pull/1017) | feat/ci-spine-jacquard-provenance-explorer-20261029 / 7f93c001777dc53925a64b6f4cad1128442fb598 | master | overlapping alternate notebook; compare not duplicate; **HOLD** |

PR #1011 is a combined N6 testflight with borrowed files and an explicit **DO NOT MERGE** boundary. PR #1010 is an N+1 matrix stacked on #995, with matched T1 measurement pending. No worktree branch or PR may be silently retargeted to master. Preserve source parentage and signed/hashed custody before pruning.

### Branch work to preserve—not blindly merge

- #1002 owns the existing deterministic offline explorer, template/build script, browser/Plotly outputs, source-bound JACQUARD_CROSSWALK and scoped QA workflow; **do not create a second renderer/metric owner**.
- #1019 owns an HTMLParser fix to test_explorer.py; #1021 owns correct workstream links and UNKNOWN queue semantics, and **also edits test_explorer.py**. A blind cherry-pick or full file replacement will lose tests; resolve additively with the source owner.
- #1018 owns the POINTER_MAP, typed validator and script-free pointer atlas, reusing the parent's QA workflow. Current 3 routes are HTML-only, with PDF mapped count zero. A parent HTML update invalidates child viewer blob/hash until rebind.
- #1017 owns a separate notebook and source pointer/visual proof; compare unique capabilities and transfer only with preservation of original tests and exact source. Its edits to shared CI QA / README require overlap review.
- #996 index → #1001 wave and #1006 delta → #1016 W4 consumer is a **separate** CI authority/scaling lane. #997 → #1012 B00–B12 naming is another lane. Historic B00–B09 and candidate B00–B12 must not share an assumed B07 identity.

## Verified first-red evidence (not cancelled by green workflow runs)

| PR / artifact | Positive evidence | Unclosed evidence and required DoV |
| --- | --- | --- |
| [#1002](https://github.com/GBOGEB/pipeline-automation-hub/pull/1002) | 10 PR-triggered workflow runs successful on original head; [40726398983](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/40726398983) executed static, Chromium, Plotly scopes | **CodeQL failure** on that head; First-Pass Closure **skipped**. Unresolved CodeQL incomplete URL substring filtering in plotly_projection.py and bad HTML regexp in test_explorer.py; Codex stale document links / unknown queue rendered 0. Source reviewers must disposition each finding. |
| [#1019](https://github.com/GBOGEB/pipeline-automation-hub/pull/1019) | Scoped QA and GOGREEN were successful on own head | Fixes one HTML regex first-red only; re-run exact-head CodeQL after integration, do not assume the URL sanitization alert is closed. |
| [#1021](https://github.com/GBOGEB/pipeline-automation-hub/pull/1021) | Scoped QA and GOGREEN successful on own head | Parent viewer and template must remain byte-reproducible; test collisions with #1019 and user-facing null handling need fresh proof. |
| [#1018](https://github.com/GBOGEB/pipeline-automation-hub/pull/1018) | Existing explorer QA / GOGREEN and two independent checks successful on child head | Child is stacked on unmerged parent. Rebind exact viewer SHA256 and blob OID when parent regenerates. No PDF page/bbox/OCG proof. |
| [#1017](https://github.com/GBOGEB/pipeline-automation-hub/pull/1017) | 10 PR-triggered runs successful on own head | Not equivalent to parent #1002; independent CodeQL/FPC, review and feature parity still needed. |
| [#997](https://github.com/GBOGEB/pipeline-automation-hub/pull/997) | 7/8 PR-triggered runs successful on old head | JADE DevOps census failure there; upstream #998 merged subsequently. Rebase and requalify rather than claiming #998 green transfers. |

The original specific #1002 CodeQL review anchors: [incomplete URL substring sanitizer](https://github.com/GBOGEB/pipeline-automation-hub/pull/1002#discussion_r4403197511), [bad HTML regex](https://github.com/GBOGEB/pipeline-automation-hub/pull/1002#discussion_r4403197522), [stale documentation links](https://github.com/GBOGEB/pipeline-automation-hub/pull/1002#discussion_r4403200065) and [unknown queue falsely reported as zero](https://github.com/GBOGEB/pipeline-automation-hub/pull/1002#discussion_r4403200077). Closing them requires owner-approved exact-head evidence, not a comment asserting fixed.

## Execution DAG, temporal feedback and SIPOC

~~~mermaid
flowchart TD
  M["MERGED #989 + #992 + #998"] --> H["H-01..05: exact-head input custody"]
  M --> P["#1002 canonical explorer candidate"]
  P --> R["#1019 + #1021: source-owned fixes"]
  R --> Q["Parent regenerate + CodeQL/FPC/review"]
  Q --> T["#1018 rebind exact viewer pointer"]
  T --> D["Real PDF source/page/bbox/OCG pilot"]
  D --> A["RTM/OFFER/EVAL + annotated document links"]
  A --> W["W4 / Mission Control read-only views"]
  M --> N["#1017 alternate notebook: compare unique parts"]
  N -. "conditional unique reuse" .-> P
  M --> C["#996 CI index"]
  C --> S["#1001 wave / #1006 delta"]
  S --> V["#1016 W4 consumer"]
  V --> W
  W -. "S9 feedback NEXT pulse" .-> H
~~~

| Supplier | Input | Canonical process / owner | Output | Consumer / validation |
| --- | --- | --- | --- | --- |
| Git worktrees / GitHub | original source, refs, branch and file manifests | Git / PR with AGENTS L1/L4/L5/L6 | exact commit and SHA receipts | source owner; re-fetched remote head |
| GitHub Actions / JADE | workflow/blob OIDs, test cases, job timestamps | JADE workflow parser, actions_metrics, GoGREEN gate | tests, DAG/clock receipts | required checks and temporal readback |
| Document owner | contract Word + RTM/OFFER/EVAL + **actual PDF binary** | governed document engine and typed source/output pointer | page/rectangle/OCG mapping or UNMAPPED | independent visual PDF QA |
| Existing GUI + Plotly | source-bound HTML/SVG/JSON and source pointers | #1002 renderer, original JADE DAG & W4 SPINE | offline multiple-lens dashboard | browser accessibility, no-network, deterministic build |
| Reviewer / owner | CodeQL, FPC, comments, exact-head tests | independently reviewed and dispositioned admission | PASS/HOLD and source receipts | governed release; next pulse |

## Executable DoD/DoV queue (append-only, never turn historical PASS into current PASS)

Each row is **unchecked** until its DoD artifact and its own DoV receipt exist at the same exact source head. The machine-readable file specifies dependency IDs, owner, PR and state.
- [ ] **H-01 — custody (LOCAL_UNKNOWN).** DoD: Inventory every local Git worktree, branch, SHA, dirty/staged/untracked/conflicts and target PR. DoV: Compare local OIDs against remote heads, classify ahead/behind/diverged; no unknown local paths left uncategorized.
- [ ] **H-02 — custody (NOT_STARTED).** DoD: Store local SHA256 receipts and reversible backups for unmerged source and owner binaries outside Git. DoV: Independently verify receipt and backup, redact secrets, do not prune branches. Requires: H-01.
- [ ] **H-03 — custody (NOT_STARTED).** DoD: Allocate each unshared file to the one correct source-owned PR branch, identify shared-file collisions. DoV: Review path allowlists, no private inputs or generated binary on wrong branch. Requires: H-01.
- [ ] **H-04 — custody (NOT_STARTED).** DoD: Stage selected files only, commit and push non-force to existing PR-owned branch. DoV: Read back exact remote head and PR changed files; preserve parent/child bases and commit receipts. Requires: H-02, H-03.
- [ ] **H-05 — custody (INPUT_UNAVAILABLE).** DoD: Preserve owner-approved PDF/DOCX/PPTX binaries with byte hash/size/license and controlled locator. DoV: Re-fetch exact binary or mark unavailable; no invented local paths or PDF geometry. Requires: H-02.
- [ ] **JQ-01 — ui (CANDIDATE_HOLD).** DoD: Select canonical existing explorer vs separate #1017 notebook after feature comparison. DoV: One source owner, no duplicated scheduler/metric, independent parity matrix and reviewer choice. Requires: H-04. [PR #1002](https://github.com/GBOGEB/pipeline-automation-hub/pull/1002).
- [ ] **JQ-02 — repair (CODEQL_RED_HOLD).** DoD: Integrate #1019 HTMLParser + #1021 document/unknown-queue repairs into #1002 in approved order and regenerate HTML. DoV: All applicable tests and exact-head CodeQL—including remaining URL sanitization alert—pass; reviewer threads dispositioned. Requires: JQ-01. [PR #1002](https://github.com/GBOGEB/pipeline-automation-hub/pull/1002).
- [ ] **JQ-03 — admission (FPC_SKIPPED_HOLD).** DoD: Requalify parent source, generated HTML, browser/Plotly receipts and reviewers. DoV: Exact-head required gates, non-skipped FPC, clean CodeQL, independent eligible review. Requires: JQ-02. [PR #1002](https://github.com/GBOGEB/pipeline-automation-hub/pull/1002).
- [ ] **JQ-04 — pointer (REQUIRE_REBIND).** DoD: Rebind pointer atlas to final parent HTML blob OID and sha256, preserve three real HTML route selections and unverified PDF state. DoV: Full explorer and >=25 pointer tests, real source/output hash parity, browser navigation, no false PDF/OCG link. Requires: JQ-02, JQ-03. [PR #1018](https://github.com/GBOGEB/pipeline-automation-hub/pull/1018).
- [ ] **JQ-05 — ui (DOV_PARTIAL).** DoD: Prove offline responsive graph/SIPOC/clocks/Plotly, keyboard, focus, hash deep links and print/export. DoV: 1440x1000/1280x800/390x844 browser QA, no network/XSS/console/overflow, null remains unknown. Requires: JQ-02. [PR #1002](https://github.com/GBOGEB/pipeline-automation-hub/pull/1002).
- [ ] **JQ-06 — document (INPUT_UNAVAILABLE).** DoD: Bind one owner source object to actual PDF binary SHA, page, bbox, coordinate convention and optional verified OCG. DoV: Independent visual PDF proof and seeded negative page/scale/repagination/layer/stale SHA tests. Requires: JQ-04, H-05.
- [ ] **JQ-07 — rtm_offer_eval (NOT_STARTED).** DoD: Link RTM-#### semantics and Word/contract source to OFFER/EVAL and HTML/PDF objects. DoV: Bidirectional object ID and exact-source navigation, owner disposition remains separate. Requires: JQ-06.
- [ ] **JQ-08 — annotations (NOT_STARTED).** DoD: Anchor review comments to stable source semantics; migrate after re-render, preserving orphan/stale state. DoV: Regression for missing/reordered/moved source, changed page and conflicting annotation resolution. Requires: JQ-06.
- [ ] **JQ-09 — views (NOT_STARTED).** DoD: Pilot large-format SVG/A3 zoom, sticky legend, typed layers and cross-format links using existing renderer. DoV: Mobile/desktop keyboard/zoom/print and verified actual PDF OCG; no fake interactive PDF support. Requires: JQ-06.
- [ ] **JQ-10 — research (RESEARCH_ONLY).** DoD: Compare Jacquard, Patchwork, SyncTeX, FileWeaver, Burrito and Tenfold playground against existing assets and license. DoV: Independent ADOPT/ADAPT/REJECT and tested reuse boundary; no arbitrary privileged watcher. Requires: JQ-01.
- [ ] **CI-01 — ci (OPEN_HOLD).** DoD: Requalify canonical index source PR with existing CI and source receipts. DoV: Same-head checks, review/FPC/ruleset without relying on stale success. [PR #996](https://github.com/GBOGEB/pipeline-automation-hub/pull/996).
- [ ] **CI-02 — ci (OPEN_OLD_RED).** DoD: Rebase/requalify B00-B12 inventory after merged #998 JADE repair. DoV: No census population first-red; full test denominator and distinct candidate B07 identity; eligible review. [PR #997](https://github.com/GBOGEB/pipeline-automation-hub/pull/997).
- [ ] **CI-03 — federation (OPEN_HOLD).** DoD: Requalify #1001 worker and #1006 delta, then W4 read-only consumer #1016 against index. DoV: No duplicate metrics, current same-source telemetry, bounded negative tests, independent W4 review. Requires: CI-01. [PR #1016](https://github.com/GBOGEB/pipeline-automation-hub/pull/1016).
- [ ] **CI-04 — performance (EXPERIMENTAL).** DoD: Run trust-scoped cold/warm cache and async fan-in A/B on selected existing workflow. DoV: Matched head/runtime/lock, >=3 warm repeats, queue/install/test clocks, no security/test regression. Requires: CI-01.
- [ ] **CTRL-01 — admission (MERGE_HOLD).** DoD: Package release-bound GUI/source/doc output family and recorded reviewer dispositions. DoV: Exact SHA/OID/digest, test/visual/cross-format receipts, clean effective rules, FPC, CodeQL and independent approval. Requires: JQ-03, JQ-04, JQ-06, JQ-07, JQ-08, JQ-09, CI-03.

## DoD/DoV maturity and final stop

- **L0 Source custody:** all relevant worktrees are inventoried, every file belongs to a documented branch, local backup/hash exists, shared remote refs can be independently fetched.
- **L1 Source-bound GUI:** a single canonical offline explorer provides actual catalog, DAG/SIPOC, run clocks, hash selection, accessible navigation and zero false authority.
- **L2 Precision:** a real owner-controlled PDF binary yields at least one verified source-to-page/normalized rectangle mapping with known coordinate convention and true UNMAPPED/STALE negatives.
- **L3 Review continuity:** typed comments migrate/mark orphaned sources across outputs, and RTM/OFFER/EVAL objects remain semantically linked.
- **L4 Read-only MC federation:** canonical JADE/GoGREEN/W4 and Plotly are reused, with temporal receipts and no new formula/scheduler owner.
- **L5 Release:** all effective required checks on exact head, non-skipped FPC, clean CodeQL, eligible independent review, stable digests, visual tests and owner-approved release. No branch/prune/merge inference from badge GREEN.

## Local Windows worktree sharing: copy/paste PowerShell 7 (dry-run first)

**This chat can commit the handover to GitHub but cannot see or commit dirty files on the user's workstation.** The following reads the actual worktree list and only stages allowlisted files. Replace example local paths and branch/file choices after inspection. Do not run `git add -A` against an entire repository, or `git push --force`.

~~~powershell
$ErrorActionPreference = 'Stop'
$Repo = 'GBOGEB/pipeline-automation-hub'
$RepoRoot = 'C:\PATH\TO\YOUR\ACTUAL\pipeline-automation-hub'  # EDIT
Remove-Item Env:GITHUB_TOKEN,Env:GH_TOKEN -ErrorAction SilentlyContinue
gh auth status
git -C $RepoRoot worktree list --porcelain
git -C $RepoRoot status --short -uall
foreach ($n in @(1002,1019,1021,1018,1017,997,996,1001,1006,1016)) {
  gh pr view $n --repo $Repo --json number,headRefName,headRefOid,baseRefName,isDraft,mergeStateStatus,url
  gh pr checks $n --repo $Repo
}
~~~

Select one existing worktree with matching branch. This first block **does not stage, commit or push**:

~~~powershell
$Worktree = 'C:\PATH\TO\ONE\EXISTING\WORKTREE'  # EDIT from worktree list
$ExpectedBranch = 'fix/ci-spine-1002-codeql-script-parser-20261029'
$PR = 1019
$Allowed = @('docs/ci-spine/test_explorer.py')  # EDIT per branch and reviewed file list
$Apply = $false  # must explicitly set to $true in a separate reviewed run

$ActualBranch = (git -C $Worktree branch --show-current).Trim()
if ($ActualBranch -ne $ExpectedBranch -or $ActualBranch -in @('master','main')) {
  throw "Wrong or protected branch: $ActualBranch"
}
$Remote = (git -C $Worktree remote get-url origin).Trim()
if ($Remote -notmatch '(^|[:/])GBOGEB/pipeline-automation-hub(\.git)?$') {
  throw "Unexpected origin: $Remote"
}
$Conflicts = @(git -C $Worktree diff --name-only --diff-filter=U | Where-Object { $_ })
$StagedBefore = @(git -C $Worktree diff --cached --name-only | Where-Object { $_ })
if ($Conflicts.Count -gt 0 -or $StagedBefore.Count -gt 0) {
  throw 'Unresolved conflicts or pre-staged unrelated content'
}
foreach ($p in $Allowed) {
  if ($p -match '(?i)(^|/)(\.env|secrets?|tokens?)(/|$)|\.(pem|key|pfx)$') {
    throw "Potential secret/key path refused: $p"
  }
}
git -C $Worktree rev-parse HEAD
git -C $Worktree status --short -uall
git -C $Worktree status --short -- $Allowed
git -C $Worktree diff --stat -- $Allowed
if (-not $Apply) { Write-Host 'DRY-RUN ONLY. Review file/branch mapping before opting into Apply.'; return }
~~~

Once approved, **rerun with $Apply set to $true**, then execute the following; do not change PR base or touch other staged paths:

~~~powershell
git -C $Worktree add -A -- $Allowed
if ($LASTEXITCODE -ne 0) { throw 'Selective add failed' }
$Staged = @(git -C $Worktree diff --cached --name-only | Where-Object { $_ })
$Unapproved = @($Staged | Where-Object { $_ -notin $Allowed })
if ($Staged.Count -eq 0 -or $Unapproved.Count -gt 0) {
  throw "Empty/unapproved staged content: $($Unapproved -join ', ')"
}
git -C $Worktree diff --cached --check
if ($LASTEXITCODE -ne 0) { throw 'Staged patch check failed' }
git -C $Worktree diff --cached --stat
git -C $Worktree diff --cached -- $Allowed  # REVIEW CONTENT BEFORE COMMIT
$Consent = Read-Host "Type COMMIT $ExpectedBranch to authorize this exact branch"
if ($Consent -ne "COMMIT $ExpectedBranch") { throw 'No commit authorization; staged changes remain for inspection' }
git -C $Worktree commit -m 'fix(ci-spine): preserve source-owned input and tests'
if ($LASTEXITCODE -ne 0) { throw 'Commit failed' }
git -C $Worktree push -u origin $ExpectedBranch
if ($LASTEXITCODE -ne 0) { throw 'Push failed' }
git -C $Worktree rev-parse HEAD
gh pr view $PR --repo $Repo --json headRefName,headRefOid,baseRefName,url
gh pr checks $PR --repo $Repo
~~~

Use separate worktree/path allowlists and the **existing PR branch** for #1021 (explorer template, generated explorer and its tests), #1018 (pointers and existing QA), #1002 (explorer renderer), and #1017 (notebook-only files). #1019 and #1021 share a test file; do not overwrite one with the other. Leave PR #1018 targeted to #1002's branch until the parent is qualified. For larger or private binaries keep original files in authorized external custody and record SHA-256, size, media type, owner and retrieval locator instead of blindly committing the binary:

~~~powershell
$Inputs = @('C:\PATH\TO\AUTHORIZED\OWNER_SOURCE.pdf')  # EDIT real file(s)
$Manifest = foreach ($f in $Inputs) {
  $i = Get-Item -LiteralPath $f
  $h = Get-FileHash -Algorithm SHA256 -LiteralPath $i.FullName
  [pscustomobject]@{path=$i.FullName; bytes=$i.Length; sha256=$h.Hash; observed_utc=[DateTime]::UtcNow.ToString('o')}
}
$Manifest | Format-Table -AutoSize
# Save original binary + hash manifest in governed storage OUTSIDE Git if required.
~~~

New single-purpose worktrees, if unavoidable, must branch from a freshly re-read existing base SHA, retain restore receipts and use a new draft PR. Do not force-push, delete, prune, rebase a shared branch or rewrite an existing stacked history without source-owner approval. Remote SHA after push is the handover receipt; a local `git status` alone is not.

## Ink & Switch research and output evolution

- [Jacquard notebook](https://www.inkandswitch.com/jacquard/notebook/) 01–03: local-first scientific authoring, provenance-as-map, build dependencies from recorded commands, SyncTeX-like fine-grained source→PDF box and mirrored comments. Source↔output mapping may be imprecise and requires a precision label; do **not** import its shell watcher into the browser.
- [Tenfold](https://www.inkandswitch.com/project/tenfold/story/): interactive programmable letters/playground and visual objects, a different but potentially useful candidate for modular malleable GUI interactions; not a PDF pointer or CI authority mechanism.
- Existing [#1002 Jacquard crosswalk](https://github.com/GBOGEB/pipeline-automation-hub/blob/feat/ci-spine-jacquard-provenance-explorer-20261028/docs/ci-spine/JACQUARD_CROSSWALK.md), [#1017 notebook method](https://github.com/GBOGEB/pipeline-automation-hub/blob/feat/ci-spine-jacquard-provenance-explorer-20261029/docs/ci-spine/NOTEBOOK_JACQUARD_METHOD_DOD_DOV.md) and [#1018 pointer README](https://github.com/GBOGEB/pipeline-automation-hub/blob/feat/ci-spine-jq04-typed-pointers-20261029/docs/ci-spine/pointers/README.md) already contain design ideas; import and specialize, do not clone.

## Restart in a new session — lossless contract

Read this handover, its JSON queue and AGENTS. Re-read **current** GitHub master and all cited PR heads; preserve the frozen-versus-current distinction. Start at H-01/H-02/H-03 local custody, push H-04 selected inputs to already owned branches and capture SHA receipts. Then close #1002 first reds using #1019/#1021, reconcile #1017, regenerate/check the canonical parent, rebind #1018, pilot a true PDF pointer and migrate comments. Qualify #996/#997 and W4 consumer separately. After each pulse append current run/attempt/digest, first-red and next action to the queue; don't silently mark any item done or relax required gates.

**Disposition at commit:** HANDOVER DOCUMENTATION IMPLEMENTED; LOCAL WORKTREE SHARING UNKNOWN; JACQUARD GUI IMPLEMENTED CANDIDATE; REAL PDF SOURCE-RECTANGLE NOT PROVEN; CI / REVIEW / MERGE ADMISSION HOLD.
