# DR: who owns derived outputs, and what a function pin hashes

Status: **PROPOSED**. This is an owner decision. D and E are decided separately. Nothing in this record changes behaviour until it is accepted.
Context: *Derived Outputs Architecture* plan, phase P3. The TODO, REX and phase owners are tracked in issue #870, which is the one roll-up; this file is only the decision.

## Context

JADE and the p-process views are committed on every feature branch. The PR check compares their bytes with what the generators produce
from that branch's sources. Every pin is a whole-file blob OID, including `file::function` pins. As a result:

- each master merge invalidates the committed outputs on every open branch (RC1);
- bots (Dependabot, Copilot Autofix, merge-from-master) commit without regenerating, and their PRs go red (RC6);
- a comment or formatting change in a pinned function invalidates the view, although its meaning did not change (RC3).

P1 (one entrypoint) and P2 (trigger coverage plus a master check) make staleness cheap to fix and early to see. They do not remove it.

## Constraints that do not move

- **F1 provenance.** Every published view names the exact source blobs it was built from (CODE PURPLE source-bound evidence).
- **F7 review integrity.** No bot commit moves a reviewed PR head. The Codex exact-head review and the FPC receipt bind that head. This rules
  out option C (a bot regenerates on the PR branch).

## Decision D: master owns derived outputs

**Proposal.** A PR no longer has to carry fresh outputs.

- The PR check runs `regen.py --write` in CI. It fails on a generator error, or when a committed output differs from the regenerated output
  *and* the PR also changed that output by hand.
- Unchanged-but-stale outputs pass the PR, and the check reports them as "master will refresh".
- A job on `push: master` runs `regen.py --check`. On drift, it opens (or updates) one `regen/master-<sha>` PR containing only regenerated files.
  That PR has its own review and receipt.

**Gains.** RC1 and RC6 go away: open branches and bot PRs stop going red on drift they did not cause. Generated files stop colliding
between parallel PRs (#858 / #860).

**Costs and risks.**

- Master lags its sources by one regen PR. Published views can be one merge old, but their provenance still names the master SHA they
  were built from, so F1 holds.
- The master job needs `contents: write` and `pull-requests: write` on a default-branch job. It must check out `github.sha` and
  assert it, never a `needs.*` output (CLAUDE.md, privileged workflow jobs).
- A PR that changes meaning (a generator or ruleset change) must still show its regenerated output. The check uploads the diff as an artifact
  and the PR body links it, so reviewers see the effect before merge.

**Accept when:** the owner agrees that a PR check passing on stale-but-untouched outputs is acceptable evidence.

## Decision E: semantic function pins

**Proposal.** A `file::function` pin hashes the function's normalised AST (`ast.dump` without positions, docstrings stripped), not the
whole-file blob OID. Whole-file pins stay as they are. For one release, both the old OID and the new hash are written, and the check reports
pins where they disagree.

**Gains.** Comment, format and unrelated-edit churn in pinned files stops invalidating views (RC3).

**Costs and risks.**

- The evidence definition changes: "built from blob X" becomes "built from a function with meaning Y". CODE PURPLE consumers that compare
  OIDs must accept the new field.
- It only reduces how often pins go stale; it does not remove staleness. A docstring the view renders must not be stripped.
- Python-only. Other pinned files keep blob OIDs.

**Accept when:** the owner agrees that an AST hash is admissible source-bound evidence for function pins.

## Proof and rollback (both decisions)

- **Negative controls before activation.** Each control runs on a PR and must produce the stated outcome:
  - a hand edit to a generated output: red;
  - a generator change without its output: red;
  - an unrelated PR on a stale master: green, with a "master will refresh" note;
  - a comment-only edit to a pinned function: no drift under E, drift under the old OID.
- **F1 byte provenance stays.** Every view keeps its source blob OIDs and sha256. E adds a field; it removes none.
- **Rollback.** Revert the activating PR. The byte-equality PR check and whole-file pins are the fallback and stay in the code until one release after activation.

## Options not taken

- **C. A bot regenerates on the PR branch.** It breaks F7, and commits made with `GITHUB_TOKEN` do not retrigger CI.
- **Status quo after P1 and P2.** Staleness is cheap and visible, but every master merge still reddens every open JADE branch.

## Decision

| Item | Decision | By | Date | PR |
|---|---|---|---|---|
| D | pending | owner | | |
| E | pending | owner | | |
