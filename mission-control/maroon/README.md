# CODE MAROON: observe, repair, prove and close

MAROON now has separate intake and worker paths. The active-PR scanner augments a private durable
ledger; a claimed worker diagnoses a coherent finding group, repairs or explains it, verifies the
current source, replies, resolves the review thread and closes the corresponding ledger item after
provider readback. See [OPERATIONS.md](OPERATIONS.md) for manual invocation, scheduling, SIPOC,
Kahn sequencing, action envelopes, recovery and the scaling contract.

The security census remains read-only. The worker's bounded authority comes from the current user
request and actual authenticated provider permissions. MAROON has no merge or protection-bypass
authority. A resolved thread, a satisfied ledger item and a merge-ready PR are separate facts.

CODE_MAROON is the review- and security-debt programme declared in
`mission-control/federation-atlas/superstitch/SUPERSTITCH_TAXONOMY_v1.json`. The
2026-10-16 samples (`SEC-CODE-MAROON`, `P-CODE-MAROON` / `MAROON-FIRSTRED`) ask for a receipt that:
- deduplicates manifestations to roots;
- records closed, deferred and outstanding counts;
- keeps each scanner's provenance;
- originally closed nothing and had no merge authority; the new proof-bound worker handles
  explicitly authorized review-item closure while merge authority remains separate.

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
- **Left:** positively observed alerts that are no longer outstanding. GitHub marks a Dependabot or code-scanning alert
  `fixed` once the fix reaches the default branch, so fixes from merged PRs show up here on the next
  read.
- **Joined:** new outstanding alerts, and roots that weren't outstanding before.
- **Coverage changes / unobserved:** missing or unreadable observations remain UNKNOWN. Their
  disappearance never clears a root. Provider resolution and deferral have separate counters.

`delta_counts()` gives the same delta as counts only.

## Nightly run

The scheduled run lives in the private cryoplant-project repository
(`.github/workflows/code-maroon-nightly.yml`). It checks out this runner at a pinned commit, fetches
with a read-only token, builds the receipt and diffs it against the committed one there.

## Review threads

A merged PR can keep open review threads from Copilot, Codex, a security bot or a person. Nothing
reads them again after the merge, so they become debt that no alert API reports.
`review_threads.py` reads all OPEN PRs with `--state open`. `--state closed` (the compatible default)
reads the recent closed window; `--state all` reads all OPEN plus that bounded closed window:

```bash
python mission-control/maroon/review_threads.py fetch --repos GBOGEB/CODEX,GBOGEB/ABACUS --limit 30 --out <private dir>
python mission-control/maroon/review_threads.py fetch --repos GBOGEB/CODEX,GBOGEB/ABACUS --state open --out <private dir>
python mission-control/maroon/maroon.py build --raw <private dir>/raw.json --review <private dir>/raw_review.json --out <private dir>
```

| Field | Rule |
|---|---|
| Manifestation | One review thread: unresolved is `outstanding`, resolved is `closed` |
| Census root | A theme in one repository, such as `path-alias` or `provenance-pin`. This is a triage category, not proof that all findings share one repair. The operations queue keeps conservative branch/source diagnosis groups and each child identity |
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
- **Left:** the current receipt positively records the thread's resolved or deferred disposition.
- **Evicted:** the PR aged out of the window. `alerts_evicted` counts these, and they never clear a root.
  An eviction needs a proven window (`ok`) for that repository on both sides; a `window_unproven` or
  missing sample proves nothing, so those threads count as unobserved rather than fixed.

Each raw thread carries `anchor` and `anchor_side`: the line its comment targets (the last line of the
diff hunk, however short) and whether that line was added, deleted or context in the PR. A deep read
uses them to check the default branch. A deleted target that is back means something else than an added
one still present.

A thread on a PR that closed without merging is `deferred`, not outstanding. The change never landed.
An OPEN unmerged PR remains outstanding. CodeQL-linked review obligations retain full identities in
`linked_alerts` for the operations queue; the security census still delegates their alert counts to
the native code-scanning owner, avoiding a second security-root count.

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

`resolve_answered.py` reports historical prose candidates. Wording such as “already fixed”, “kept as
is”, a merged PR reference or an abbreviated SHA never authorizes resolution. The old prose-only
`--apply` route is rejected.

```bash
python mission-control/maroon/resolve_answered.py --repos GBOGEB/cryoplant-project,GBOGEB/CODEX --limit 60
python mission-control/maroon/resolve_answered.py --proofs <private proofs.json> --ledger <private ledger.json> --apply
```

**Which threads it reads:** unresolved threads on merged PRs, where the last comment is from the login running the tool.

**Which threads the proof-bound path resolves:** active, non-canary threads with a live leased
ledger item; exact head/base and source blob OIDs; unchanged discussion; finding-specific test or
source-analysis evidence; and authenticated provider permission. A journal persists reply, resolve,
readback and ledger closure so partial completion can be reconciled.

**What stays open:**
- a fix PR that has not merged
- a finding confirmed open
- a re-theme
- any reply the tool does not recognise, such as an `@copilot` request

A PR whose threads cannot be read is reported as a gap, and the sweep continues.

Historical candidate discovery can use the existing `ccr` reader. Proof-bound application uses
official GitHub REST/GraphQL through `closure.GitHub`; connected-tool adapters must preserve the same
evidence and checkpoint contract. The GitHub helpers come from `review_threads.py`.
