# GM-I-C P0009 | Source-bound postmerge evidence delta

**Observed:** 12 November 2026. **Owner:** existing Hub CP.CLOSE source and B01–B46 read-only projection; **not** a new action ledger or merge gate.

Previous observation recorded 46 B IDs, 22 scoped DONE and 24 OPEN. Eight previous REVIEW_WAIT/DEPENDENCY_HOLD-linked PRs have since merged. GitHub REST review listings showed no `APPROVED` review for any of those eight. The live Hub ruleset requires zero approvals, so source integration must not be rewritten as verified independent admission. This package deliberately reports a **null current closure count** until owner evidence has been reconciled; its 46-row historical baseline is immutable.

## Actual execution

Run the existing CP.CLOSE tests, then `python mission-control/v2/handoff/closeout/w12-gmic-r2-p0009/postmerge_reconcile.py --out /tmp/gmic-p0009` and `python -m unittest discover -s mission-control/v2/handoff/closeout/w12-gmic-r2-p0009 -p 'test_*.py' -v`. The projector imports the original 46-row JSON and appends independent PR-merge evidence without promoting anything. It is offline, deterministic and read-only. It refuses a baseline whose git blob differs from `48106d26a1db49317a20b91105ccb2a76237abad` or whose any row (id, priority, state, minimum DoD/DoV) differs from that frozen projection, and it refuses a release manifest with a missing member or a checksum mismatch.

## Three disjoint lanes

**Lane A (source integration):** reconcile #1135/#1138/#1152/#1160/#1164/#1175/#1179/#1193 with their exact merged SHAs and historical reviews; inspect CI and postmerge negative canaries independently. Do not close B08/B15/B21–B24/B32/B34/B38 merely from merged PR status.

**Lane B (protocol):** GEMINI #44 must receive owner decisions on canonical v1 and changed-digest replay, followed by actual historical-source fixtures and independent tests. Its existing synthetic #48 corpus is not a substitute for approval.

**Lane C (authorization):** GEMINI #12 hosted WIF Viewer ACL and nonzero census, GEMINI #50 and Hub effective review/required-check/negative canaries remain distinct. No secrets, ruleset mutation or credential dispatch in this pulse. B44 remains workstation-only.

## Next Kahn boundary

The three lanes may execute concurrently. W4 is a strict AND join requiring A's owner-qualified source admission, B's W1/W2 protocol DoV, and C's hosted W3 plus both effective protections. W5 follows W4; W6 follows W5. B42 advisory is separate and cannot unlock hosted work.

No authority transfer, zero formal credit. The source file is an observation receipt, not an editable policy or a signed governance acceptance.
