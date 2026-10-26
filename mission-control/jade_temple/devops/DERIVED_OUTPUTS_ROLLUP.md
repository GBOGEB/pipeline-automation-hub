# Derived outputs: roll-up, TODO and REX

Plan of record: *Derived Outputs Architecture* (2026-10-26), the phase ladder P0–P4. Plan artifact: owner access only, linked from #868.
This file tracks who owns each phase, what is left, and what the work taught us. It does not restate the plan.

Pulse: hub `origin/master` `57f08d22` (#865), read 2026-10-25T23:47Z. PR heads at that time: #858 `2cdc6bcd`, #860 `dfef5acd`, #868 `9a9b6d9c`.

## Why

Committed JADE outputs pin blob OIDs and sha256 of their sources (F1 provenance, kept). Since the DAG pin landed on 10-23, all 18
non-canary JADE PR reds were stale committed outputs, not real defects. Root causes RC1–RC7 and options A–E are in the plan; the decision on
options D and E is [DR_DERIVED_OUTPUTS_OWNERSHIP.md](DR_DERIVED_OUTPUTS_OWNERSHIP.md).

## Phase owners

| Phase | Scope | Owner | State at pulse | Next action | Blocked by |
|---|---|---|---|---|---|
| P0 | Unblock #858; land one of #858 / #860, regenerate the other | #858 (`fix/hub858-red`), #860 (`chore/p-process-everred-refresh-20261024`) | #858 conflicting, FPC red; #860 green, mergeable | Land #860, merge master into #858, run `regen.py --write`, rewrite its receipt | — |
| P1 | `regen.py` chain, `.gitattributes` LF, chain tests, AGENTS.md L7 | #868 (`fix/regen-entrypoint-p1-20261026`) | All checks green except FPC; receipt written 23:48Z, gate re-running | Merge when FPC is green | — |
| P1b | `newline="\n"` / `encoding="utf-8"` in p-process writers; widen `test_portability.py`; `gogreen/spine.py` hash fix | unowned | not started | Start after P0 lands (#858 and #860 own those files) | P0 |
| P2 | Path filters cover every pinned path; `push: master` runs the checks; ratchet list empties | worktree `pah_regen` (uncommitted edits to `jade-temple-readonly-qa.yml`, `gogreen-launcher.yml`) | in progress, local only | Commit on its own branch stacked on #868; push; PR | P1 |
| P3 | Decision record: master owns derived outputs (D); semantic function pins (E) | this PR | proposed | Owner decides; on accept, implement as P3a / P3b | owner |
| P4 | Cryoplant cool-down family: registry, one W368 digest, CI for `test_w370` / `test_w373`, `.gitattributes` | unowned (`cryoplant-project`; open #2083, #2094 touch W372c / W369b only) | not started | Census the W368 → W371 pin graph at main; one PR | — |

## TODO

Order is the dependency order. Each item closes on a merged PR, not a local run.

- [ ] P0.1 Land #860 (green, mergeable).
- [ ] P0.2 #858: merge master, fix Codex P1 at `everred/harvest.py:103` (stable check-run pages), `regen.py --write`, new FPC receipt, new Codex review.
- [ ] P1.1 #868 FPC green, then merge. Afterwards, AGENTS.md L7 is the single regeneration rule.
- [ ] P2.1 Commit the `pah_regen` workflow edits on their own branch and push. They must not ride on #868 (CLAUDE.md "push early", "one session per worktree").
- [ ] P2.2 Empty `KNOWN_UNFILTERED` in `tests/test_regen.py`, so a pinned path outside the filter fails.
- [ ] P2.3 `push: master` runs `regen.py --check`; check that the first master run is green.
- [ ] P1b.1 After P0: portable writers in p_decide, refresh, build_p_process, build_page, harvest, package.
- [ ] P1b.2 Widen `test_portability.py` to p-process, gogreen and v2; fix the `gogreen/spine.py` hash-vs-file mismatch.
- [ ] P3.1 Owner decision on the DR (D and E separately).
- [ ] P3.2 If D is accepted: the PR check runs `regen.py --write` and fails only on generator errors or hand-edited outputs. A master job opens one regen PR per drift.
- [ ] P3.3 If E is accepted: normalised-AST hashes for `file::function` pins, with the old OID kept next to them for one release.
- [ ] P4.1 Cryoplant registry for W365/W366 → W368 → W369/W370 → W371 → records → discovery.
- [ ] P4.2 One W368 model-digest definition; check W371's W368 pin or drop it.
- [ ] P4.3 Run `test_w370` and `test_w373` in CI; widen W371 filters to `w368/cooldown_full/inputs/**`; add `.gitattributes`.
- [ ] R.1 After each merge, refresh this table at the new master SHA (one pulse per snapshot).

## Fan-out

JADE (the hub) is the first target, because it carries the pins and the reds. The pattern is regen registry + `.gitattributes` + master check.

1. **Hub / JADE**: P0 → P1 → P2 → P1b; P3 by decision.
2. **cryoplant-project**: P4. It has the same failure class (re-pin PRs that prove nothing) on a different chain, and it needs CoolProp.
3. **Others**: ABACUS, CODEX and gg_MATH only where a census shows committed derived outputs checked by byte equality. One owner-approved PR per repo, after the hub's first master check is green. Do not copy `regen.py`: each repo declares its own chain, and the shared part is the pattern and the test shape.

## REX

| # | What happened | Lesson | Rule it feeds |
|---|---|---|---|
| X1 | 18/18 JADE reds since 10-23 were stale outputs. #858 went red three ways in one day: a master merge, a Copilot Autofix, and Windows backslash keys. | A byte-equality check on every branch turns each master merge into N reds. Fix the structure (P1–P3), not each red. | plan RC1, RC6 |
| X2 | People ran part of the six-command chain. rolling5 was the step most often missed. | Generation order belongs in code (one entrypoint), not in a doc rule. | AGENTS.md L7 via #868 |
| X3 | Workflow-file and BD-queue edits merged green and reddened the next JADE PR. | Path filters must be derived from the pin graph and enforced by a test; master must run the check too. | P2 ratchet |
| X4 | #858 and #860 commit the same generated DAG files and the same `as_posix` fix. | Two branches that both commit derived outputs collide by construction. Land one, then regenerate the other. | P0, P3 option D |
| X5 | At this pulse, P2 edits sat uncommitted in the P1 worktree, and #868 was green except for an unfilled FPC receipt. | Push each phase on its own branch right after its first commit. Write the receipt when CI goes green, not at merge time. | CLAUDE.md "push early", AGENTS.md L1 |
| X6 | Four sessions shared the `pah-devops-n9` checkout. | Before editing a shared checkout, make your own worktree (`git worktree add`). This roll-up was written in `pah_dorollup`. | CLAUDE.md "one session per worktree" |
| X7 | A bot commit that regenerates on the PR branch would move the reviewed head (option C). | F7 review integrity rules out PR-branch bot commits. Regeneration that does not move a reviewed head must land on master, as its own PR. | DR option D |
