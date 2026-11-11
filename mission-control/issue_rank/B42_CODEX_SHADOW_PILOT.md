# B42 read-only CODEX/HUB semantic shadow pilot (11 November 2026)

Distinct owners remain authoritative: CODEX merged #1282 at `c7535442cd325d2b7602fcadf7677aa235ecdafd` supplies the action-intent resolver; Hub `mission-control/issue_rank/title_taxonomy.py` (blob `1f7bebe94a0fe114b604bb6bf5ecd4a6e2e1d92d`) independently supplies title classification. This pilot performs no title edits, external dispatch, PR action, scheduler, issue-closing decision, priority promotion, ruleset modification or merge authorization.

The source identity and canonical CODEX `validate_profile` checks must pass *before* any alias is evaluated. A reserved, unknown or instruction-like phrase returns no action candidate. A recognized phrase returns only a SHADOW candidate separate from the original title analysis. The CODEX profile's original status/action namespace rules are inherited unmodified. All output authority fields are false/zero.

Run: `B42_CODEX_ROOT=.codex-source python -m pytest -q mission-control/issue_rank/test_b42_codex_title_shadow.py`. This is B42 **pilot source completion only**; downstream review and full native CI remain necessary before any B42 scoped DONE. No upstream merge gate is waived.

DoD: exact-source test pass; independent review; owner confirms the alias observation has no false-equivalence or title corruption in a four-pulse comparable cohort. The separate Hub B01-B46 ledger retains its existing IDs and counts.
