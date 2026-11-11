# CODE MAROON runner

CODE_MAROON is the review- and security-debt programme declared in
`mission-control/federation-atlas/superstitch/SUPERSTITCH_TAXONOMY_v1.json`. The
2026-10-16 samples (`SEC-CODE-MAROON`, `P-CODE-MAROON` / `MAROON-FIRSTRED`) ask for a receipt that:
- deduplicates manifestations to roots;
- records closed, deferred and outstanding counts;
- keeps each scanner's provenance;
- closes nothing and has no merge authority.

`maroon.py` writes that receipt from GitHub's own alert APIs.

```bash
python mission-control/maroon/maroon.py fetch --owner GBOGEB --out <private dir>
python mission-control/maroon/maroon.py build --raw <private dir>/raw.json --out <private dir>
python mission-control/maroon/maroon.py diff --old <earlier>/MAROON_RECEIPT.json --new <private dir>/MAROON_RECEIPT.json --out <private dir>
python -m unittest discover -s mission-control/maroon -p "test_*.py"
```

## What it reads

For every non-archived source repository of the owner (forks are skipped), the runner reads three
GitHub sources:

| Source | States read | How each state counts |
|---|---|---|
| Dependabot | open, fixed, dismissed, auto-dismissed | outstanding, closed, deferred, deferred |
| Code scanning (CodeQL, Bandit, Ruff, Semgrep, Trivy, ...) | open, fixed, dismissed | outstanding, closed, deferred |
| Secret scanning | open, resolved | outstanding; closed if revoked, otherwise deferred |

A fourth source, `review_threads`, is read by `review_threads.py` for named repositories only (see
[Review threads](#review-threads)).

If a source can't be read, the runner records a coverage gap instead of a count:
- `not_enabled`: the scanner is switched off for that repository.
- `not_readable`: the caller's token can't read it.

Either way it is a gap, never zero.

## What it writes

| File | What | Where it may live |
|---|---|---|
| `raw.json` | Every alert as fetched | Private only |
| `MAROON_RECEIPT.json` | Coverage, totals, every root and every lane | Private only: names packages, rules, advisories and paths |
| `MAROON_FIXLIST.csv` | Outstanding roots, worst first, with the fix (for example `upgrade pillow to >= 11.0.0`) | Private only |
| `MAROON_LANES.md` | Lanes, worst first | Private only |
| `MAROON_PUBLIC.json` | Counts per repository: coverage, outstanding roots by severity, and manifestation dispositions | Safe to commit to a public repository |

## Roots

A root is one fix:
- **Dependabot:** one package, in one ecosystem, in one repository. Every advisory on it is a
  manifestation. The fix is to upgrade it to the highest first-patched version among its open
  advisories.
- **Code scanning:** one scanner rule in one repository. Every alert is a manifestation.
- **Secret scanning:** one secret type in one repository.

A root's severity is its worst outstanding manifestation.

## Lanes

A lane is one repository plus one source family:
- Dependabot: per ecosystem, for example `codex:deps-pip`.
- Code scanning: per tool, for example `codex:code-codeql`.
- Secrets: `codex:secrets`.

Two Dependabot lanes never edit the same manifest, so separate workers can take them in parallel.
Code-scanning lanes in one repository can touch the same source file; a lane's `shared_paths` names
those files so the work can be sequenced.

## Current receipt

`data/MAROON_PUBLIC_20261030.json` holds the counts-only projection of the first run, read on 2026-10-30:
- 34 repositories, all alert states;
- 355 outstanding roots in 21 lanes;
- 509 outstanding Dependabot manifestations (337 closed, 5 deferred);
- 13,612 outstanding code-scanning manifestations (8,868 closed);
- no open secret-scanning alerts in the 18 repositories where it could be read.

The full receipt, fix list and lanes are in the private cryoplant-project repository.

Code-scanning roots are one per rule. For osv-scanner and Trivy the rule is a CVE, so one vulnerable
package can show up as several roots there; Dependabot already groups those by package.

## What moved

`diff` compares two receipts and writes `MAROON_DELTA.json` (private: it names roots):
- **Left:** alerts that are no longer outstanding. GitHub marks a Dependabot or code-scanning alert
  `fixed` once the fix reaches the default branch, so fixes from merged PRs show up here on the next
  read.
- **Joined:** new outstanding alerts, and roots that weren't outstanding before.
- **Coverage changes:** a source that became unreadable is listed here, so it isn't mistaken for a fix.

`delta_counts()` gives the same delta as counts only.

## Nightly run

The scheduled run lives in the private cryoplant-project repository
(`.github/workflows/code-maroon-nightly.yml`). It checks out this runner at a pinned commit, fetches
with a read-only token, builds the receipt and diffs it against the committed one there.

## Review threads

A merged PR can keep open review threads from Copilot, Codex, a security bot or a person. Nothing
reads them again after the merge, so they become debt that no alert API reports.
`review_threads.py` reads them for the most recent closed PRs of the repositories you name, newest
first:

```bash
python mission-control/maroon/review_threads.py fetch --repos GBOGEB/CODEX,GBOGEB/ABACUS --limit 30 --out <private dir>
python mission-control/maroon/maroon.py build --raw <private dir>/raw.json --review <private dir>/raw_review.json --out <private dir>
```

| Field | Rule |
|---|---|
| Manifestation | One review thread: unresolved is `outstanding`, resolved is `closed` |
| Root | One theme in one repository, such as `path-alias` or `provenance-pin`, so that one root is one follow-up PR. Copilot and Codex flagging the same defect fall into one root |
| Severity | The reviewer's own: a Codex P badge (P0 critical, P1 high, P2 medium, P3 low) or Copilot's High, Medium or Low. Unrated threads are `note` |
| Lane | `<repo>:review-<theme>`. Review lanes in one repository name their `shared_paths`, as code-scanning lanes do |
| Coverage | `ok`, `not_readable`, or `not_in_scope` for a repository outside the review read |

The window is the `--limit` most recently *closed* PRs. The API only sorts by update time, so the read
pages on until the window is proven: `--limit` PRs closed no earlier than the oldest update time read. A
PR never closes after its last update, so no later page can hold a newer closure. If the page budget
runs out first, coverage is `window_unproven`, a gap rather than a silent short read.

Each repository's raw entry lists the sampled PRs. Each entry gives the PR's number, merge state, close
time, merge commit and the `#refs` in its body. The receipt keeps that sample as `review_scope`, and
each review root maps its threads to their PRs (`alert_prs`). `diff` then splits what moved:
- **Left:** the thread's PR is still sampled, so the thread was resolved.
- **Evicted:** the PR aged out of the window. `alerts_evicted` counts these, and they never clear a root.
  An eviction needs a proven window (`ok`) for that repository on both sides; a `window_unproven` or
  missing sample proves nothing, so those threads count as left.

Each raw thread carries `anchor` and `anchor_side`: the line its comment targets (the last line of the
diff hunk, however short) and whether that line was added, deleted or context in the PR. A deep read
uses them to check the default branch. A deleted target that is back means something else than an added
one still present.

A thread on a PR that closed without merging is `deferred`, not outstanding. The change never landed.

`build --review-overrides <json>` applies deep-read corrections before roots are formed, as
`{"<thread id>": {"theme": "<theme>"}}`. A re-themed finding then leaves the wrong lane and joins the
right one.

The theme is a triage heuristic over the finding's first line (`THEMES` in `review_threads.py`). An
unresolved thread is not proof that the defect is still on the default branch: a later commit may have
fixed it without a reply. Each root needs a deep read before anyone calls it fixed or open.

Resolution comes from GraphQL through `first_pass_closure_gate.resolved_thread_roots`, imported rather
than copied (AGENTS.md L4). Claude Code sessions can't reach GraphQL, so they pass `--threads ccr`.
Each repository's head SHA is recorded with its threads (AGENTS.md L6).

`raw_review.json` holds review text and paths, so it is private only. `MAROON_PUBLIC.json` holds counts.

## Storage split

The public hub holds this runner and `MAROON_PUBLIC.json` only. The full receipt, fix list and lanes
go to a private repository, because they name vulnerable packages and file paths, including for private
repositories.

## Resolving answered threads

Each fix PR ends with an evidence reply on every thread it settles. `resolve_answered.py` then resolves the
threads whose fix is on the default branch, so the landing gate on unresolved threads stays meaningful.

```bash
python mission-control/maroon/resolve_answered.py --repos GBOGEB/cryoplant-project,GBOGEB/CODEX --limit 60          # report
python mission-control/maroon/resolve_answered.py --repos GBOGEB/cryoplant-project,GBOGEB/CODEX --limit 60 --apply  # resolve
```

**Which threads it reads:** unresolved threads on merged PRs, where the last comment is from the login running the tool.

**Which threads it resolves:**
- the reply says the fix is already on main
- the reply names a merged fix PR in the same repository
- the reply names a commit on the thread's own merged PR

**What stays open:**
- a fix PR that has not merged
- a finding confirmed open
- a re-theme
- any reply the tool does not recognise, such as an `@copilot` request

A PR whose threads cannot be read is reported as a gap, and the sweep continues.

Resolution uses the `ccr` route that Claude Code sessions have. The GitHub helpers come from
`review_threads.py`.

## Open-PR pulse (proactive mode)

The sources above count debt. The pulse acts on it, starting with the open PRs where unresolved threads
block a merge today. `open_threads.py` reads every open PR of the owner (or named repositories) at one
head SHA per PR. `pulse.py` decides what each unresolved thread needs, clusters repeats, plans a DAG of
actions, records everything in a BD-queue ledger, and acts on what the evidence already proves.

```bash
python mission-control/maroon/pulse.py run  --owner GBOGEB --ledger <private>/MAROON_LEDGER.json --out <private>/<pulse>          # dry run
python mission-control/maroon/pulse.py act  --plan <private>/<pulse>/MAROON_PULSE_PLAN.json --ledger <ledger> --apply              # resolve
python mission-control/maroon/pulse.py done --ledger <ledger> --node fix:GBOGEB/ABACUS#2711 --status DONE                          # worker receipt
python mission-control/maroon/pulse.py seed --review <private>/raw_review.json --ledger <ledger>                                  # closed-PR history
```

### Verdicts

Every unresolved thread gets one verdict, evidence first (the module docstring has the full table):
`ANSWERED`, `WAIT`, `HUMAN_PENDING`, `SUGGESTION_APPLIED`, `OUT_OF_SCOPE`, `FP_HISTORY`, `SEEN_FIXED`,
`GENERATED`, `LIKELY_ADDRESSED`, `NEEDS_FIX`. False-positive and history signals:
- the suggestion is already in the file at the head;
- the path is no longer changed by the PR;
- the same finding was kept as is twice before;
- the same finding was fixed before (a regression check, not a new fix);
- the path is a generated or pinned output (regenerate, never hand-edit);
- the thread is outdated and its anchor line is gone at the head.

`ANSWERED` reuses `resolve_answered.verdict_of`, so a worker's `Fixed in <sha>.` or `Kept as is: <reason>`
reply is evidence for the next pulse. On an open PR the SHA must be one of the PR's own commits.

### Findings, recurrence and the ledger

A finding is one defect, whatever reviewer or PR shows it:
- **Identity:** a scanner rule id where there is one (`yaml.github-actions...mutable-action-tag`, `B602`, `CWE-79`);
  otherwise repository, theme and the significant words of the first line.
- **Near-duplicates:** findings without a rule id in one theme merge when their word sets overlap by 60% or more.
  Two rules never merge.

The ledger (`code_maroon.ledger.v1`, private) keeps per finding: first and last seen, pulses seen, PRs, threads,
frequency (threads per pulse), modal path and reviewer, latest verdict per thread, and tags. Re-planning the
same pulse changes no count.

| Recurrence | Rule |
|---|---|
| `ONCE` | one thread in one pulse |
| `REPEAT` | two or more threads, or seen in two or more pulses |
| `RECURRING` | two PRs |
| `SYSTEMIC` | three or more PRs: gets a `fold` node |

Tags come from the PR title, branch and labels, and the thread: `METHOD`, `REX`, `SCALING_PROOF`,
`SCALING_PILOT`, `SCALING`, and `CORE_OID` for paths whose git OIDs JADE outputs pin. A `CORE_OID` node
must re-run the JADE DAG generator in the same push.

### DAG, waves and workers

| Node | Executor | Writes | Does |
|---|---|---|---|
| `resolve:<repo>#<n>` | `act` | nothing | replies and resolves where evidence is in hand |
| `cluster:<id>` | worker | each PR branch it covers | one coherent fix for findings repeated on the same PRs |
| `fix:<repo>#<n>` | worker | that PR branch | the PR's remaining threads |
| `fold:<key>` | worker | a new branch | turns a SYSTEMIC finding into a test, lint, gate rule or doc line |
| `close:<repo>#<n>` | `act` | nothing | resolves what the workers answered, once they are done |

Edges: cluster -> fix on the same branch, fix or cluster -> close, and a chain between any two nodes that
write one branch. Waves are Kahn layers from `jade_temple/devops/lifecycle.topo_layers` (imported). The
plan asserts that no wave writes a branch twice, so the workers in one wave are disjoint. Bot branches
(Dependabot, Renovate) and forks get no writer: a bot rebase would drop the commit.

Each ready worker node gets a brief (`briefs/<node>.md`): its threads, branch heads and a contract. The
worker stops on a moved head, deep-reads before fixing, replies `Fixed in <sha>.` or `Kept as is: <reason>`,
never merges and never resolves. Queue states: `QUEUED`, `DISPATCHED` (back to `QUEUED` after 24 h with no
receipt), `DONE`, `FAILED` (`BLOCKED` after three attempts), `OBSERVED_CLOSED` when its threads are gone.

### Authority

`act` writes only with `--apply`, at most `--max-actions` (default 25), and only for `ANSWERED`,
`SUGGESTION_APPLIED` and `OUT_OF_SCOPE` unless `--include-medium` adds `FP_HISTORY`. Before each write it
reads the PR again: closed, moved head or already-resolved thread means skip. Replies carry a
`<!-- code-maroon:... -->` marker. Nothing in the pulse merges, approves or dismisses a review.

The `/maroon` skill (`SKILL.md` here) runs the pulse by hand on every open PR, or from the 8-hourly
scheduled task, and launches the workers.
