# Collection parity method (v2)

Code-side guard owner: `scripts/coverage_waves_parity_guard.py` (hub). ABACUS keeps its own guard at
`scripts/ci/family_collect_guard.py`. This doc owns the method; `COLLECTION_PARITY_LEDGER.jsonl` beside it owns the rows.

## Question

Does CI collect at least as many tests as a local `pytest --collect-only` at the same commit? A test that exists
but is never collected in CI cannot go red, so it gives a false green (an uncollected family).

## Steps (one pulse per snapshot)

1. Record one SHA per repo: the head of the origin default branch
   (`gh api repos/<owner>/<repo>/commits/<branch> --jq .sha`). Every number in a row comes from that SHA.
   Record `census_at` (UTC).
2. Local vector (`local`): in a clean worktree at that SHA, on the repo's declared interpreter, run
   `python -m pytest --collect-only -q` and record `N tests collected` and `M errors`. Collection errors are
   recorded, not hidden; a workstation-only error (missing optional dependency) is noted in `reason`.
3. CI vector (`ci`): from the runs at the same `head_sha`
   (`gh api "repos/<owner>/<repo>/actions/runs?head_sha=<sha>"`), read the `collected` / `passed` lines of each
   pytest job log per lane. Record the run ids and per-lane counts in `ci_lanes`. For CODEX, record the
   `tests/coverage_waves` lane separately in `coverage_waves`.
   `ci` is the number of distinct test node IDs collected across all lanes, never the sum of lane totals: matrix
   jobs run the same suite more than once (e.g. hub `coverage-waves.yml` runs `tests/coverage_waves` on Ubuntu and
   Windows), so a sum counts those tests twice and can hide an uncollected family. Take the union of the lanes'
   collected node IDs (e.g. `pytest --collect-only -q` output or a junit report per lane). If node IDs cannot be
   read, a lane total may be added only when the lane is shown to be disjoint from the others (different test
   paths, not a matrix copy); otherwise record `ci` as null and give the row `UNKNOWN`.
4. Verdict per row: `PASS` only when local collection had zero errors (`local_errors` is 0) and ci >= local,
   with `ci` computed as in step 3;
   `GAP` when ci < local (open a G-lane issue naming the uncollected families and put it in `issue`); `UNKNOWN`
   with a written `reason` when either vector cannot be read at that SHA, or when local collection had errors
   (the local count is then only a partial denominator; keep `UNKNOWN` until collection succeeds on the
   declared interpreter).
5. Private repos (cryoplant-project): rows hold counts, SHAs and run ids only. No paths, file names or test names.

## Check

- Every ledger row is `PASS`, `GAP` with an `issue`, or `UNKNOWN` with a non-empty `reason`.
- No `PASS` row has a non-zero `local_errors`.
- `grep -nE '[A-Za-z]:\\|/Users/|/home/' docs/ci-spine/COLLECTION_PARITY_*` finds nothing.

## History

- v1 (2026-10-31 audit) fanned out the G lanes: #1056, #1060, cryoplant-project#2185, CODEX#1216,
  CODEX#1231-#1236. Method and the 74-row ledger lived outside git.
- v2 (2026-11-12, #1204) moves the method into the hub and re-censuses the five repos at one SHA each.
  The first v2 census is mostly `UNKNOWN`: most default-branch heads had no completed pytest run to read.
  Next census: run step 2 per repo and read CI on a head that has a completed test run.
