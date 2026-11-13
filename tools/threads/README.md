# Thread tools

Tools for the lossless thread handover method (map → rescue → takeover → verify → retire)
and for red-means-stop enforcement. They used to exist only in one workstation's
`_pulse/tools/` folder. The `/thread-rollup` and `/governed-ci-evidence-recovery` skills
call them.

| Tool | What it does | Writes |
|---|---|---|
| `parked_intents.py SPEC.json [--dry-run]` | Files untracked intents as `parked-intent` issues, with source sessions and wake triggers. Idempotent per id, including comments. | GitHub issues and comments (not in a dry run) |
| `wake_check.py --pulse-dir DIR` | Read only. Lists open parked intents whose wake triggers matched new activity. A strong hit is a path change, a referenced issue update or a comment; a weak hit is a keyword in a PR title. Unread repos are reported, never treated as quiet. | `DIR/<date>/WAKE_CANDIDATES.md` and `.json`, `DIR/wake_state.json` |
| `check_presence.py OUT.json REPO…` | Read only. Shows which check runs appeared on every recent merged PR, which is the safe set for required checks. | `OUT.json` |
| `thread_wire.py DIR/wire` | Builds the per-thread wireframe (repo, branch, OID → intent, TODO, next, verdict) from `list_sessions` output and per-thread records. | `DIR/THREAD_MAP.md`, `DIR/THREAD_WIRE.json` |
| `session_census.py --sessions-dir S --pulse P --out OUT [--memory M] [--git-root D] [--git-home-re RX] [--task-title T]` | Read only. Census of every desktop session from the app's per-session JSON and transcripts, past the 200-row `list_sessions` cap: lineage, reserved number, PRs, outputs that still exist, sole-copy writes, pasted blocks, fold-back, and a capture verdict (CAPTURED / PARTIAL / AT_RISK / TASK_RUN) with a wake line. | `OUT/SESSION_CENSUS.json`, `OUT/ARCHIVE_WIREFRAME.md`, `OUT/REENTRY_CARDS.md` |

The tools reuse existing owners and do not copy them (AGENTS.md "Metric ownership"):

- **Parked-intent marker:** the parser is `triway_burndown.parked_intent_meta()` /
  `parked_intent()`. These tools load it by path through `_common.py`.
- **Worktree inventory:** use `tools/workstation/hv03_custody.py` (custody) and
  `Invoke-WorkspaceAudit.ps1` (disk and prune). To map a squash-merged worktree tip to its
  PR, use `gh api repos/O/R/commits/<sha>/pulls`; `git cherry` misses those tips.

## Rules

- `DIR`, specs and wire records are local and private. Never commit them to this public
  repo. Session titles and briefs may hold confidential project content.
- Every tool removes `GITHUB_TOKEN` and `GH_TOKEN` before calling `gh`, so `gh` uses its
  keyring sign-in.
- Run `parked_intents.py --dry-run` before every real run.
- When choosing required checks, require only checks present on every PR, never no-op
  checks, and save before, after and rollback ruleset JSON. Verify with
  `rules/branches/<branch>`. Re-run `check_presence.py` after any workflow rename.

Tests: `python -m unittest discover -s tools/threads -p 'test_threads.py'` (offline).
