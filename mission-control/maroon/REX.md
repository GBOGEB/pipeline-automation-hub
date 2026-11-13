# CODE MAROON REX: known fixes before push

`hints.py` tells a worker which review findings recur once they are on GitHub. REX moves that
knowledge left, onto the author's machine: a catalog of findings that keep coming back, each with a
local detector and one agreed fix, run over the lines a branch adds before it is pushed.

## Why

A mining pass on 2026-11-13 read 7,969 top-level review comments on hub, ABACUS and CODEX pull requests
(2025-09-16 to 2026-11-12):

| Reviewer | Comments |
|---|---|
| Codex (P1 1,399, P2 1,850) | 3,290 |
| Code scanning (Semgrep, ruff, CodeQL, Bandit) | 2,740 |
| Copilot | 1,938 |

The 21 catalog entries match 2,253 of them (28%). Nearly all of these are code-scanning findings,
which a tool on your machine detects as well as GitHub does. The largest:

| REX | Finding | Comments | PRs |
|---|---|---|---|
| REX-001 | Action not pinned to a full SHA | 621 | 121 |
| REX-003 | Unused import | 308 | 126 |
| REX-019 | `assert` (Bandit B101), mostly in tests | 274 | 36 |
| REX-002 | Unsorted imports | 258 | 104 |
| REX-011 | `datetime.UTC`, deprecated imports | 134 | 42 |
| REX-004 | Shebang on a non-executable file | 93 | 80 |

`evidence` in `data/REX_KNOWN_FIXES_v1.json` holds the counts per entry. The raw comments stay private.

Codex and Copilot findings are mostly semantic and do not reduce to a pattern. Their recurring themes
(exact-head binding, fail-closed validation, regenerated outputs, identity, re-run safety) are printed
as a self-review checklist after every scan.

## Use

```bash
python mission-control/maroon/rex.py scan                       # advisory: hits on the lines this branch adds
python mission-control/maroon/rex.py scan --fix                 # also apply ruff's safe fixes for autofix entries
python mission-control/maroon/rex.py scan --strict              # exit 1 on any hit
python mission-control/maroon/rex.py scan --repo C:/repos/ABACUS --base origin/main
python mission-control/maroon/rex.py install-hook               # advisory pre-push hook (REX_STRICT=1 to block)
```

`scan` diffs `merge-base(base, HEAD)..HEAD` plus uncommitted changes and reports only findings on added
lines, so an old file does not drown a new change. `ruff` entries need `ruff` on PATH. If ruff is
missing, fails or cannot read a file, the report says so in `notes`. It never reports a pass it did not
check.

## Growing the dictionary

```bash
python mission-control/maroon/rex.py fetch --repos GBOGEB/pipeline-automation-hub,GBOGEB/ABACUS,GBOGEB/CODEX --out <private dir>
python mission-control/maroon/rex.py mine --comments <private dir>/review_comments.jsonl --out <private dir>/rex_mine.json
```

`mine` reports coverage and lists the uncatalogued findings seen on at least `--min-prs` (default 3)
PRs, keyed by `hints.finding_key`. Add an entry when a candidate has one agreed fix and a local
detector. Then run `mine --write-evidence` to refresh the counts.

Detector kinds:

| Kind | Checks |
|---|---|
| `ruff` | Rule codes on added lines, with an optional `exclude` glob list |
| `regex` | A pattern on added lines under `paths` |
| `exec_bit` | A `#!` first line whose git mode is not 100755 |
| `dual_import` | A module brought in by both `import x` and `from x import` |
| `workflow_permissions` | A changed workflow with no top-level `permissions:` |
| `write_text_newline` | A `write_text(...)` call without `newline=`, found by AST |
| `companion` | A trigger path changed but the generated output it requires did not |

The `companion` trigger can be a glob, or `when_hints_regex` to reuse a `hints.py` regex such as
`PINNED_OID_RE`.

## Boundaries

- Every result is `PREPUSH_HINT_NOT_REVIEW_PROOF`. It attacks known defects early. It does not
  replace review, the FPC gate or code scanning.
- REX never posts, resolves or pushes. `operations.py` / `closure.py` still own review-thread
  closure.
- When a finding is noise at its source, the fix is the scanner configuration, not one answer per
  comment. Bandit B101 in tests is the main example (REX-019).
