# JADE focus-five slice: lossless handover at pulse P0004 (2026-11-02)

Supersedes [the P0003 handover](../HANDOVER_JADE5_P0003_20261031.md), which stays as history.
Session: https://claude.ai/code/session_017Fwrzak5ZCpiKxEJjfHrRW. Every figure here was read back from
GitHub on 2026-11-02 or recomputed in the session.

Files in this folder:
- `HANDOVER.md` (this note)
- `SESSION_PR_TRACE.json`: every PR this session opened since 2026-10-12, with head, merge commit, state
  and URL. Private repo rows are aggregate-only.
- `Build-JadeHandover.ps1`: builds the binaries on your machine (section 5).

## 1. State at P0004

`tools/focus5_pulse.py` at the 2026-11-02 heads reads **24 PASS / 1 FAIL / 35 UNKNOWN of 60**.
Earlier pulses: P0003 21/1/38, P0002 17/2/41, P0001 14/8/38. RELEASE_CREDIT=0, merge admission HOLD.

| Repo | Head | PASS | H04 | H05 | H06 | H08 |
|---|---|---|---|---|---|---|
| pipeline-automation-hub | 75b7278 | 5/12 | PASS | PASS | PASS | UNKNOWN: PR rule, no RED canary |
| cryoplant-project (private) | aggregate | 4/12 | UNKNOWN | PASS | PASS | UNKNOWN: PR rule, no RED canary |
| gg_MATH | 1e2caa6 | 5/12 | PASS | PASS | PASS | UNKNOWN: PR rule, no RED canary |
| DOCX_RTM_Automation | 67b5c87 | 5/12 | PASS | PASS | PASS | UNKNOWN: protected, no PR rule |
| yaml-grammar | d6988d0 | 5/12 | PASS | PASS | PASS | **FAIL: unprotected** |

In every repo, H01 and H02 PASS. H03, H07 and H09–H12 are UNKNOWN; after four pulses they are flagged
`unattended`. These gates need owner or independent acceptance and never PASS from a workflow run.

CODEX 1.4.1 (`release/RR_1_4_1_POINT_RELEASE_READINESS.yaml`, latest #1242) is NOT_READY_BLOCKERS_OPEN:
- K5 is green: Pages deploys main, and Site HTML QA reads 80/80 pages with an empty baseline.
- B1, B2 and B4 are resolved.
- B3 waits on the Actions PR setting.
- The owner H gates are open, and K1–K4 still have to run on a release PR.

## 2. What the slice changed (68 PRs since 2026-10-12)

Counts from `SESSION_PR_TRACE.json`:

| Repo | Merged | Closed by design |
|---|---|---|
| CODEX | 50 | |
| pipeline-automation-hub | 7 | |
| DOCX_RTM_Automation | 3 | 4 RED canaries |
| yaml-grammar | 3 | |
| cryoplant-project | 1 (aggregate) | |

No PR is open and no issue was opened.

Since the P0003 handover:

- **Hub #1084:** the not-started check reads every page of jobs. Codex review P2 on #984: a failure on page
  2 of a large matrix could be hidden.
- **Hub #1085** (squash 90bf6cb, which also carries the stacked #1086):
  - JADE QA and the peer census run on every master push. The invariant test is now
    `test_master_runs_on_every_push`.
  - The H04 contract `tests/test_jade_build_contract.py` requires:
    - only standard-library, local or declared imports;
    - coverage and playwright installed only from the Dependabot-owned manifest via `pip -c`;
    - Python floor 3.12.
  - It fixed real drift: the manifest was at coverage 7.17.0 and playwright 1.64.1, CI ran 7.13.3 and
    1.56.0.
- **CODEX #1237:** the HTML QA baseline is empty again. #1221 had merged its pre-rebase commit and
  restored three fixed entries.
- **CODEX #1238 and #1242:** the RR-1.4.1 record at P0003, then K5 green with blockers B1, B2 and B4
  resolved. The private cryoplant SHA was removed from the current file; git history still has it.
- **This PR:** pulse P0004, real-data tests moved to P0004, this handover.

Earlier work is in the P0003 handover, section 2.

## 3. Owner-only actions

1. **CODEX:** Settings -> Actions -> General -> "Allow GitHub Actions to create and approve pull requests"
   (B3). The metrics and reconcile bots publish `automation/*` branches, but every PR attempt is refused.
2. **yaml-grammar H08:** add a ruleset on master requiring pull requests and these checks:
   - "Stdlib-only contract on Python floor 3.11"
   - "make comments + YAML::PP parity (211 rules)"
   - "Offline fixture integrity (211 productions) (3.11)" and "(3.12)"

   Then say so, and the session opens the RED canary PR. It must be refused.
3. **DOCX_RTM_Automation H08:** add a pull request rule to main. `admission-policy.yml` stays red on main
   until then.
4. **Delete leftover DOCX branches** (the session proxy refuses ref deletion):
   - `canary/h04-red-a-unpinned-20261027`
   - `canary/h04-red-b-drift-20261027`
   - `canary/h04-red-c-hash-20261027`
   - `canary/h04-red-d-npmlock-20261027`
   - `tmp/h07-osv-scan-20261027`
5. **Hub first-pass-closure** is red on #983, #984 and #1078. Receipts are written; the gate also needs a
   completed Codex exact-head review summary on each (comment `@codex review`).
6. **Decisions:**
   - delete or archive DOCX's unused root `requirements.txt` and `requirements-dev.txt` (most of its
     Dependabot alerts);
   - purge the private SHA from CODEX history;
   - whether a point release applies to yaml-grammar at all (H03).

## 4. Next admissible actions (no owner input)

- **cryoplant H04:** a lock-backed contract like DOCX#97, done in the private repo. The current exact pins
  have no lock.
- **DOCX:** pytest 9.0.1 -> 9.0.3 (GHSA-6w46-j5rx-g56g) with a re-lock on a runner. uuid needs a major
  bump.
- **After each owner action in section 3:** run the RED canary for that repo, then take pulse P0005.

Pulse procedure:
1. `focus5_pulse.py --out data/FOCUS5_POINT_RELEASE_P0005.json --date <d>`
2. `private_boundary.py --write` on that file.
3. `rolling5.py --append-pulse ... --pulse-id P0005`
4. `regen.py --write`, then commit.
5. `regen.py --write` again for the launcher.
6. Move the real-data asserts in `tests/test_rolling5.py`.

Fetch `origin/master` before step 1: the registry is read from the local checkout.

## 5. Binaries, worktrees and reproduction on your machine

Run from this folder on Windows. You need git, gh logged in, and optionally Python 3.12:

```powershell
cd <hub clone>\mission-control\jade_temple\notes\handover_20261102
powershell -ExecutionPolicy Bypass -File .\Build-JadeHandover.ps1 -DryRun     # list every step
powershell -ExecutionPolicy Bypass -File .\Build-JadeHandover.ps1             # -> C:\Downloads
powershell -ExecutionPolicy Bypass -File .\Build-JadeHandover.ps1 -IncludePrivate -Live
```

Output goes to `C:\Downloads\JADE5_HANDOVER_20261102\`, plus `C:\Downloads\JADE5_HANDOVER_20261102.zip`:
- `bundles\<repo>.bundle`: lossless, every ref, verified with `git bundle verify`. Restore with
  `git clone <bundle> <dir>`.
- `archives\<repo>-<sha12>.zip`: the source tree at the pinned head.
- `worktrees\<repo>`: a detached checkout at the pinned head. CODEX and the hub are sparse, following the
  CODEX CLAUDE.md sparse-worktree rule.
- `trace\<repo>\pr-<n>\`: pr, files, reviews, review comments, issue comments and check runs, via REST.
- `repro\`: a fresh pulse, the JADE suite log and the regen check log.
- `SHA256SUMS.txt` and `HANDOVER_INDEX.json`.

The script is read-only against GitHub. It stops below 3 GB free, clears a stale `GITHUB_TOKEN`, prints
ASCII only, and processes the private repo only with `-IncludePrivate`. It was **not executed** in the
authoring session (no PowerShell there), so run `-DryRun` first.

Known Windows-only JADE suite failures, if any, show in `repro\jade_suite.log`. Compare them with a clean
origin/master run before calling them regressions.

## 6. REX added in this stretch

- A squash merge of a stacked pair carries both PRs' content, but neither head SHA is an ancestor of
  master. Check content on master, not ancestry.
- A pulse taken after a failed fetch reads the registry from a stale checkout while reading heads live.
  Fetch first, and fix refspecs left pointing at deleted branches.
- Codex review findings can land after a PR merges. Read reviews on merged PRs before the next pulse.
- Inline `pip install x==y` in workflows is invisible to Dependabot. Install from the manifest it owns,
  via `-c`.

## 7. Drop-in message for the next session

> Continue the JADE focus-five point-release slice from hub
> `mission-control/jade_temple/notes/handover_20261102/HANDOVER.md`. First re-read the owner actions in
> section 3 (`gh api repos/GBOGEB/<repo>/rules/branches/<branch>`, and whether `automation/*` PRs now exist in
> CODEX). For each one done, run that repo's RED canary PR and record its refusal. Then take pulse P0005 per
> section 4 (fetch first). Next work without owner input: cryoplant H04 lock contract, DOCX pytest 9.0.3
> re-lock. Rules: one head SHA per repo per pulse, UNKNOWN never PASS, RELEASE_CREDIT=0, drafts only, one
> root cause per PR, CODEX PR bodies start with `## PR CLASSIFICATION`, never push a default branch, private
> repos aggregate-only in public outputs.
