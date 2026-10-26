# GoGREEN TOP21 merged evidence → EVERRED candidate bridge

Extends existing canonical TOP21 roster in `mission-control/gogreen/success_graph/samples/native_success_20261017.json`; it does not define a new roster, BD register, causal root owner or release authority.

**Evidence separation:** latest merged PR number, exact PR head SHA, merge commit SHA and native run/attempt must be kept separate. `ALL_OBSERVED_SUCCESS` means only all returned actions succeeded, not an effective required-check/security/independent-review gate. A cancelled, skipped, pending or absent run cannot count as green. Missing first-red steps remain `NOT_FETCHED`, not a newly closed causal root. API 100-item truncation is fail-closed.

## Read-only live scanner
Run `python -m unittest discover -s mission-control/gogreen/merged_evidence/tests -v`. For a read-accessible TOP21 portfolio, bind a fresh 21-unique-repository JSON roster from the canonical G7 file and run:

```bash
GH_TOKEN=<read-only token> python mission-control/gogreen/merged_evidence/scan.py --roster roster_from_ssot.json --limit 1 --out output/merged_evidence
```

The dedicated workflow `.github/workflows/gogreen-top21-merged-evidence.yml` runs the regression suite and, only when the cross-repo read credential `GOGREEN_TOP21_READ_TOKEN` has been installed by the authorized owner, performs the cross-repo live scan. Without it, the workflow emits `DEFERRED_NO_CROSS_REPO_READ_TOKEN`, not invented green results. No secret is written to artifacts.

The output includes `snapshot.json`, `merged_pr_rollup.csv`, `everred_candidates.csv`, `manifest.json` (SHA256). These are **candidate** deltas for the canonical CODE PURPLE BD queue; the next fanout must resolve failing run/job/step logs, identify first-red family and deduplicate roots against EVERRED source truth. No automated update of the canonical BD queue takes place from workflow labels alone.

## Live 17-Oct-2026 bounded preliminary reconnaissance

Exactly one latest merged PR per 21 named repositories was sampled; the native PR-head workflow-run readback found 12 repositories with all observed runs successful, 4 with at least one failure/cancellation, 3 with nonterminal runs and 2 without workflow runs. Across 143 run associations: 12 failures and one cancellation (including CODEX 5 fail +1 cancelled; CoolProp 4 fail; telegraf 2 fail; github-mcp-server 1 fail). First-red job/step details remain to be retrieved and source-bound. This is not every merged PR, not a whole-portfolio green rate, and not proof of formal root closure.

## Scaling guardrails

1. Scale `--limit` from 1 to 2, then 5, then 10 only after authentication, pagination and SHA identity validation.
2. Record `N` source snapshot UTC, head/merge SHA, run ID/attempt, terminal state and API page completeness.
3. Keep BD symptoms distinct from deduplicated causal roots; no 260 historical failure associations are recounted as newly closed.
4. For green PRs, separately collect source-scoped test numerator/denominator, timing, runner concurrency and rolling N20 only with enough observed checkpoints.
5. For red PRs, collect paginated job/step first-red, identify shared source-root candidates, preserve the inherited EVERRED debt and owner/repair dependencies.
6. Route formal root and review decisions to canonical CODE PURPLE/REX owners. `MERGE_ADMISSION=HOLD` whenever required governance evidence is missing.

SIPOC: canonical roster (S) → merged PR head and merge SHA plus workflow runs (I) → same-head join/classification (P) → green/mixed/pending/absent ledgers (O) → GoGREEN / EVERRED / owner triage (C). The next DAG edge from raw red manifestations to formal root closure is DECLARED, not OBSERVED.
