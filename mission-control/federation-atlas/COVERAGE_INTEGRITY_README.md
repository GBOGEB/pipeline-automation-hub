# CODE PURPLE - Coverage Integrity Atlas (W+4)

**Scope:** read-only source-bound coverage review **incubator** for `GBOGEB/pipeline-automation-hub`. The existing Mission Control Method Atlas remains the sole Pages publisher. This bounded slice adds no new publisher, producer, workflow or remote dispatcher. Integration into that publisher is **PENDING**, because active PR #753 already owns edits to `pages_portal.py` and the canonical observation pipeline.

## Canonical implementation map (previous nine numbered objectives)

1. **Source-matched comparison:** #2016 and #2017 have the same ten source Git blobs, identical per-file eligible statements/branches and Coverage.py v7.16.2 on Python 3.11. PR-head tests differ; this is a historical comparison, not combined exact-main coverage.
2. **Repository separation:** ABACUS broad main, QPS N6 (12 modules), gg_MATH focused module, CODEX unknown, and Mission Control #531 six-repo breadth retain independent scope keys and cannot be naively summed.
3. **Full inventory:** historical QPS LKT 10 Python modules, later QPS main directory 15 Python candidate modules. The five newcomers are inventory additions, not measured zero-coverage modules. Current-main coverage is UNKNOWN.
4. **Standard metrics:** statement n/d, branch n/d, per-module minima, zero-statement and zero-branch files, source Git blobs, run/attempt/job and verified artifact member checksums, source inventory, native runner evidence, metrics owner and authority ceilings.
5. **Non-compensating gate:** every active declared production file must be present in fresh measurement and no measured executable module may be at 0% statements or at 0% eligible branches. `UNKNOWN` cannot be replaced with zero or pass; branchless files are N/A. A module regression is visible even when total coverage rises. QPS #2030 contains the existing source/CI gate; this view does not replace or claim it has executed.
6. **Method relationships:** `dependency.mmd` (DAG), `sipoc.mmd` (five-stage supplier/input/process/output/customer), `spline.mmd` (N/N+1 and unknown current), plus two SVG themes, with typed source/proof/gate/view/HOLD roles and dashed non-authoritative links.
7. **Observation contract:** `COVERAGE_INTEGRITY_OBSERVATIONS_v1.json` is a pinned *historical* source snapshot. A new observation requires native run/job/attempt IDs, actual >0 executed steps, exact SHA, eligible inventory, per-file source blob, valid Coverage.py JSON, downloaded ZIP + CRC + SHA-256. Any mismatch yields INCOMPARABLE or HOLD.
8. **Thematic launcher:** the standalone, offline `coverage_integrity.py` generates `/coverage-integrity/index.html` for **local preview**. Light/dark/system selectors are client-side display settings, not evidence changes. A Pages navigation link/staging change is held for the existing #753 source owner to resolve, avoiding overlapping `pages_portal.py` modifications. No remote JS/CSS or private bidder contents.
9. **BD queue and recursive control:** prioritize (P0) runner admission with executed steps, (P0) fresh 15-file QPS main coverage and zero-coverage gate, (P0) dashboard regression, (P0) ABACUS zero-file census and fixed-denominator 2,043-statement gap, (P0) independent review/RED canary, (P1) #531 credential-return 42-cell census, (P1) M1/M2/M3/PCA/BT statistical readiness. Stop retries at three independently comparable unchanged observations; new run ID alone is not progress.

## Verified historical QPS evidence

| PR exact head | Python 3.11 run / job | ZIP artifact and hash | Statements | Branches |
|---|---|---|---:|---:|
| #2016 `a975da034e590049f7270bb7116ba96aa540343e` | `39235772095` / `118004344696` | `12179875406`, SHA256 `6af88e006ace8e76dc4c7ec7c66236c786726d48a088f700f795d7a75d51d82d` | 754/852 | 270/304 |
| #2017 `a31e094a046e24bf52f024ed21913ed09159c20f` | `39236354670` / `118006251696` | `12180055848`, SHA256 `7dc0849fce48b2b327560dd0589735095feef150396094fdb3f646df5f3f646a` | 763/852 | 277/304 |

Both downloaded ZIPs passed CRC and `coverage.json` member SHA-256 verification on 19 October 2026. The changed module coverage is `build_dashboard.py`: **-9 statements / -2 branches** and `support_bridge.py`: **+18 / +9**. There are no fully zero-covered measured modules in the historic ten-file cohort. This does **not** qualify the later 15-file main population.

**Current observational boundary:** Latest observed QPS main `2c85973b2a9ab65407af812b70958063ce8803f8`; ABACUS main `f2b78a1a626ab72fefbc04e8d2b9505c735eb9b8`; Method Atlas host master `9b9a556b4287889c44cd0d5d3c2ac16b33baea4e` as of the snapshot readback. Any later head makes the readback historical. QPS #2030 (merged 14:35:39 UTC) had zero independent submitted reviews; its previous exact-head CI failure was pre-execution and does not prove the Python gate executed successfully. Engineering/merge credit remains zero.

## Reproduction

From `pipeline-automation-hub` repository root, use the **existing** Method Atlas test cohort (no extra runner family):

```powershell
python -m unittest discover -s mission-control/federation-atlas -p 'test_coverage_integrity.py' -v
$head = (git rev-parse HEAD).Trim()
python mission-control/federation-atlas/coverage_integrity.py --head $head --out .local-coverage-integrity
python mission-control/federation-atlas/coverage_integrity.py --head $head --out .local-coverage-integrity --verify-only
python -m http.server 8765 --directory .local-coverage-integrity
```

Then open `http://127.0.0.1:8765/`. This is **not** yet staged by `pages_portal.py`, pending disjoint integration with active PR #753. For a branch checkout, local validation remains a preflight, not a native GitHub Actions receipt. Do not treat the generated `presentation_head` as evidence that pinned historical QPS source measurements were rerun.

## Minimal producer input for a future pulse

Future observation records must provide a qualified `repository`, `population_key`, exact source `head_sha`, owned source file inventory (with per-file Git blob identities), statement and branch eligible/covered counts, `coverage.py` and Python versions, native run/attempt/numeric job with positive steps and terminal status, downloaded ZIP ID and independently verified ZIP and JSON member hashes/CRC. Missing provenance leaves the corresponding metric `UNKNOWN`. Do not retrofit an old artifact under a new run ID.

## Publisher collision / source-owner disposition

Active Mission Control PR #753 (`feat/method-atlas-io-broker-20261019`) already changes `pages_portal.py`, adds `orchestration/coverage_contract.py`, a historical observation contract, the central themed dashboard, and native tests. This incubator does **not** touch any of those files. The PR #753 producer contains historical reported QPS module counts but flags `independently_verified=false`; this incubator supplies a separately hash-checked 10-module historical ZIP per-source comparison and a responsive viewer. The owner should **bridge or prune** rather than run two independent coverage ledgers. Do not enable Pages staging, new CI dispatch or alternative authority until that decision.

## Governance

`MERGE_ADMISSION=HOLD` - `ENGINEERING_ACCEPTANCE=WITHHELD` - `SECURITY_WAIVER=NONE` - `FORMAL_CREDIT_DELTA=0`.

Canonical federation #531 remains the 42-cell producer; #530 is the ZIP verifier; #533 is only a method viewer. The covered statements target for ABACUS 75% with denominator 43,527 is +2,043, **not** a cross-repository goal. The dashboard does not act as an authenticated current #531 producer or authorize QPS owner decisions.
