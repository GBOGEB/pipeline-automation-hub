# Token census

The cross-repo census, dispatch and metrics lanes run on separate runners in
separate repositories, and they reach each other with four fine-grained
personal access tokens owned by GBOGEB. This folder is the single record of
those tokens. It lists which secret holds which token, which workflows consume
each secret, and what happens when a secret is missing. The scheduled
telemetry checks that each token is doing its job.

No secret value is stored here or printed by the tool. The receipt carries
`formal_root_closure_credit: 0` and `merge_authorized: false`.

## Files

| File | What it is |
|---|---|
| `REGISTRY.json` | Tokens, secrets with their save times, and each secret's consumer workflows |
| `token_census.py` | Read-only census: consumer runs before and after each save, failed-log signals, hub secret probes |
| `tests/test_token_census.py` | Offline contract tests. They also check that every hub consumer named in the registry still reads its secret |
| `../../../.github/workflows/gogreen-token-census.yml` | PRs run the offline tests. Every 6 h (:41) and on manual dispatch, the live census also runs |

## The four tokens

| # | Token | Repositories | Permissions | Expiry | Secrets |
|---|---|---|---|---|---|
| 1 | `dag-census-read-federation` | ABACUS, CODEX, cryoplant-project, pipeline-automation-hub | Contents, Actions, Pull requests: Read | 180 d | hub `CROSS_REPO_READ_TOKEN`, hub `QPS_FEDERATION_READ_TOKEN`, ABACUS `QPS_REPO_READ_TOKEN`, ABACUS env `cryoplant-federation` `CRYOPLANT_FEDERATION_TOKEN` |
| 2 | `dag-census-read-fleet` | cryoplant-project, github_Documents, qps_deck (the private TOP21 members; public repos are readable by any token) | same as #1 | 180 d | hub `GOGREEN_TOP21_READ_TOKEN` |
| 3 | `dag-dispatch-federation` | ABACUS, CODEX, cryoplant-project | Actions: Read and write. **No Contents** | 90 d | hub `QPS_TRIAGE_DISPATCH_TOKEN` |
| 4 | `abacus-metrics-pr-writer` | ABACUS | Contents, Pull requests: Read and write | 90 d | ABACUS `METRICS_PR_TOKEN` |

Metadata: Read is implied on all four. Token #3 is Actions-only because census
fan-out uses `workflow_dispatch`. The older `repository_dispatch` needed
Contents: write, which can push code where branch rules are not enforced. See
`tools/metric-atlas/docs/QPS_CENSUS_FEDERATION_N1.md` for how each dispatch is
bound to an exact source head, so concurrent or intervening runs hold rather
than report a wrong green.

`TRIAGE_CENSUS_TOKEN` in cryoplant-project is optional and unset.
`qps-triage-console-refresh.yml` falls back to the built-in token, which can
read all three repos it needs.

## Reading the census

Each **lane** is one secret paired with one consumer workflow. A lane takes the
last completed run before the save and the latest one after. Only the
consumer's default branch counts, and only the listed events where given.
Cancelled and skipped runs are ignored.

| Verdict | Meaning |
|---|---|
| `FIXED` | red before, green after: the token did its job |
| `GREEN` / `NEW_GREEN` | green after (with or without an earlier run) |
| `BROKE` | green before, red after. Usually a soft "deferred" path turned into a live read that failed |
| `STILL_RED` / `NEW_RED` | red after |
| `NO_RUN_SINCE_SET` | nothing to judge yet |
| `NOT_SET` | optional secret not saved. The latest run state is still reported |
| `UNREAD` | the census could not list the workflow's runs |

A red lane's failed job log is scanned for one **signal**:

- `AUTH_INVALID`: a 401 or "Bad credentials"
- `FORBIDDEN`: a 403
- `SECRET_MISSING`: the workflow reports the secret as missing
- `REPO_SETTING`: Actions is not allowed to create PRs
- `NONE`: nothing token-related found

Each lane then gets an **action**:

| Action | Who | When |
|---|---|---|
| `OK` | nobody | latest run green |
| `WAIT` | nobody | no run since the save |
| `OWNER` | token owner | a token signal, a setting signal, a bad hub probe, or an unreadable lane |
| `THREAD` | a lane owner | red for a reason other than the token |

**Threads and stacks.** `threads_needed` groups the `THREAD` lanes by
repository (one stack per repo). It is empty when every red is the owner's to
fix. That case means no new thread or stack is needed for token work. A
non-empty list names the repositories that need a lane owner.

**Token health** is `ACTION_REQUIRED` when any of these holds, and the scheduled
run then goes red:

- a hub secret probe is not `VALID`;
- a consumer log shows `AUTH_INVALID`, `FORBIDDEN` or `SECRET_MISSING`.

Each hub probe is one `GET /repos/GBOGEB/cryoplant-project`. That repo is
private, so only a valid token that selects it returns 200. Secrets stored in
other repos can't be probed from the hub, so they are judged by their
consumers' runs.

## Status when this registry was written (2026-10-23 ~11:30Z)

All seven required secrets are saved.

| Lane | Result |
|---|---|
| ABACUS `cryoplant-federation.yml` | **FIXED**. It had failed daily since at least 10-17; it has been green since the save (run 39936448073) |
| ABACUS `dmaic-commit-metrics.yml` (push) | **FIXED**. The governed metrics PR step passed with `METRICS_PR_TOKEN` |
| hub `gogreen-top21-merged-evidence.yml` | **NEW_GREEN**. Its first live scan read 21 repos (run 39945670075) |
| hub `code-purple-live-census.yml` | **BROKE**, `AUTH_INVALID`. The saved `CROSS_REPO_READ_TOKEN` gets 401, while the same token #1 works in three other secrets. Re-save it with the current token #1 value |
| cryoplant `qps-triage-console-refresh.yml` | red since at least 10-21, `REPO_SETTING`. Not a token problem: allow GitHub Actions to create pull requests in that repo, or have the workflow use a token |
| the other 4 lanes | `WAIT`. Federation plan and dispatch run on `master` only by manual dispatch, after #783 merges. The federation spine runs daily. The W04 receipt runs on push |

At that point `threads_needed` was empty: no new thread or stack was needed for token work.

## Keeping it true

- **When you re-save a secret** (for example after **Regenerate**), update its
  `set_at` in `REGISTRY.json` to the time `gh secret list` shows. Otherwise the
  before/after comparison uses the old save.
- **When a workflow starts or stops reading a secret,** add or remove the
  consumer here. The contract test fails if a hub consumer no longer reads its
  secret.
- **Expiry** is estimated from the earliest save of each token's secrets.
  GitHub emails about a week ahead. Regenerate the token, re-save its secrets,
  and update `set_at`.

Run it locally as the owner. The probes are skipped, and your own login reads
the private repo:

```bash
GH_TOKEN="$(gh auth token)" PRIVATE_READ_TOKEN="$(gh auth token)" \
  python mission-control/gogreen/token_census/token_census.py \
  --registry mission-control/gogreen/token_census/REGISTRY.json --out /tmp/token-census
```
