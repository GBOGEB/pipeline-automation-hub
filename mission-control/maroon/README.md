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
