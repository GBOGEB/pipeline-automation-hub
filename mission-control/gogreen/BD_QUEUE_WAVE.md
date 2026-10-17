# CODE PURPLE - BD queue wave

Source authority: native GitHub repositories and exact PR-head workflow runs, not this generated index.

bd_queue_wave.py reads open PR/issue lists from ABACUS, CODEX, Mission Control and QPS, then groups failed workflow manifestations; it never infers causal roots from a workflow name.

Run the source's test_bd_queue_wave.py with unittest. Native GoGREEN CI enforces 95% branch-aware focused coverage and executes the live GitHub census on a trusted runner. Output: bd_summary.json, bd_pr_queue.json, bd_manifestations.json, bd_pr_queue.csv, BD_REPORT.md, bd_files_sha256.json and native_execution_receipt.json.

Safety: read-only token, bounded four-way API fanout, exact-head identities, duplicate run attempt collapse, no source mutation or worker dispatch. Partial/missing PR data stays UNKNOWN. Queue p50/p95 is workflow-level created-to-start time only. Matched broad coverage, blocked time, causal closure and M2/M3 stability remain UNKNOWN.
