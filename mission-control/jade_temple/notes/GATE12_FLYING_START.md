# Gate12 flying start: recorded source to execution

The [release desk](../site/gate12_hub.html) defaults to the latest **recorded**
FOCUS5 pulse. The original frozen baseline stays selectable. The source dates,
denominators and selected CSV follow the observation; neither view certifies
current heads. No pulse or gate status is changed by opening the desk.

## Initialize the original use case

1. Read the [original five follow-up](JADE_OG_FOLLOWUP_20261112.md) and existing
   [rolling policy](../data/ROLLING5_POLICY.json). Preserve its five repositories;
   ABACUS/CODEX provider work does not substitute for one of the original five.
2. Run `python mission-control/jade_temple/tools/regen.py --write` from the repo
   root. The canonical rolling owner verifies the append-only ledger, snapshot
   hashes, confined paths, dates, source identities, gate inventory and declared
   totals. A broken latest source fails rather than falling back to old green.
3. Read the recorded date and all 60 gate cells in the desk. Each cell drills into
   the source reason, prerequisite frontier and owner action. UNKNOWN and
   unassessed are separate; the other 16 Top21 repositories have 192 unassessed
   cells. The five progress cards retain their own historical denominators.
4. Inspect the selected queue CSV and source hashes. The latest CSV is
   `site/gate12_latest_queue.csv`; the original remains `site/gate12_bd_queue.csv`.
   The [launcher](../../gogreen/launcher/index.html) consumes the same canonical
   fields and links directly to Gate12; it calculates no gate metric.

## Execute without losing the starting state

- Start with an unblocked source-owner hurdle in the queue. READY means the
  declared prerequisites permit investigation; independent acceptance may still
  be required. Keep one repair lane and one proof lane per repository under the
  existing stabilization/BD owners. Reuse current PRs and owner issues.
- At the 12 November follow-up, gg_MATH has a canary receipt awaiting effective-rule
  verification and hardening PRs #130/#131; DOCX #86 owns missing effective policy;
  Hub #336 owns admission; yaml needs designated required checks. These are dated
  source-owner observations, not extra completed gates in the ledger.
- Prepare H03 release scope/version decisions while H07/H08/H09/H10/H11 evidence
  proceeds in disjoint lanes. H12 remains the owner release join. Transfer a
  leading repo's method, tests and REX, then earn each receiver's own proof.
- When evidence changes, read each assessed default head once and pin every
  native run/job/attempt and census record to that head. Follow AGENTS.md L6;
  do not append mixed-head census/gate observations. Private QPS identities and
  proof remain within their private owner boundary.
- Append only a qualified snapshot using `tools/rolling5.py --append-pulse ...
  --pulse-id ...`. NIRVANA still requires twelve PASS gates at the same SHA across
  two observed pulses. Repeating an unchanged UNKNOWN is not completed work.

## Verify the desk and source package

```bash
python -m unittest discover -s mission-control/jade_temple/tests -p 'test_*.py' -q
python mission-control/jade_temple/tools/run_gate12_browser_qa.py
python mission-control/jade_temple/tools/regen.py
```

Gate12 browser QA serves exact source bytes on ephemeral loopback HTTP, retaining
production CSP. It tests latest/baseline/repeated switching, matrix drilldown,
queue filters, missing/unsafe/inconsistent initialization and hostile reason text
at 1440×1000, 1280×800 and 390×844. The receipt hashes the tested HTML/CSS/UI/data
bytes. The existing native JADE browser job now runs this exact tool and uploads
its receipts/screenshots. No new publisher or scheduled job is introduced.

The launcher reads committed inputs: after committing upstream generated changes,
run `regen.py --write` again and commit its dependent launcher outputs. Verify
`REGEN_OK` and a clean worktree before publishing the candidate branch.

## Authority and availability

The desk is a source candidate. Hosted Gate12 staging, deployment and served-byte
parity remain unqualified; repository navigation is not a deployed URL. The frozen
`project()` API is preserved for the existing portfolio-readiness PR #1154 and
its weekly-watch child #1155. This slice adds no competing portfolio owner or watch.

At the source readback for this work, #1243's JADE source/browser and launcher
checks passed, but its trusted FPC controller reported
`CODEX_REVIEW_NOT_COMPLETED_ON_EXACT_HEAD`. That is an admission hurdle, not
application-test failure. Green source QA, local browser QA and a generated bundle
do not replace independent review, effective protection or the owner release decision.
