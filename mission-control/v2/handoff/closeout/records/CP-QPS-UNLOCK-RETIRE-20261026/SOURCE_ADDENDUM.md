# CODE PURPLE QPS Unlock Watch — retirement H1 and R1 pulse (public-safe)

**Canonical producer:** `mission-control/v2/handoff/closeout/cp_close.py`. **Source input:** `intakes/CP-QPS-UNLOCK-RETIRE-20261026.json`. This addendum is a curated, source-linked narrative. It is not a second SSOT and not a verbatim chat transcript.

**Inputs:**
- **H1** is the handover written by the retiring ChatGPT watch at about 2026-10-26 00:56 CET. Its rows are *reported, not re-verified* unless marked R1.
- **R1** is the first read-only CP.RESUME V2 pulse: a Claude Code session using authenticated GitHub GET only, at 2026-10-26T00:45Z.

**Privacy:** `GBOGEB/cryoplant-project` (QPS) is private and this hub is public. QPS SHAs and run, job, PR and issue numbers are shown as `PRIVATE_AGGREGATE_ONLY`, following `jade_temple/tools/private_boundary.py`. Workflow names and file paths are kept.

**Sibling record:** [PR #876](https://github.com/GBOGEB/pipeline-automation-hub/pull/876) preserves the separate *Federated MIP Pulse Metrics* watch (N0) and owns the MIP-01..15 backlog. This record links to it and copies none of its rows.

## Carried state

```
MERGE_ADMISSION=HOLD
QPS_ENGINEERING_ACCEPTANCE=NOT_ESTABLISHED
MISSIONCONTROL_AUTHENTICATED_QPS_UNLOCK=NOT_ESTABLISHED
MATCHED_COVERAGE_DELTA=UNKNOWN
FORMAL_CROSS_REPO_QPS_CREDIT=NONE_ESTABLISHED
AUTHORITY_TRANSFER=false
OLD_WATCH_ENABLED=false            # reported by the retiring session; not GitHub-verifiable
R1_ALERT=SILENT                    # no class A-D qualified
```

## R1 — checkpoint versus live heads (2026-10-26T00:45Z)

| Repository / branch | H1 checkpoint (~22:42Z) | R1 current | Δ | Via |
|---|---|---|---:|---|
| `GBOGEB/ABACUS` main | `20b4c2383f442891211c99bae2725bcf1688299b` | `6ebebbc2aee8c400ecec7a8b9ee76fff80153c17` | +6 | [#2468](https://github.com/GBOGEB/ABACUS/pull/2468), [#2469](https://github.com/GBOGEB/ABACUS/pull/2469) |
| `GBOGEB/CODEX` main | `cb3b0d269bcd0ff9e96982cfc8276aa4bc187acf` | unchanged | 0 | — |
| `GBOGEB/cryoplant-project` main | PRIVATE_AGGREGATE_ONLY | PRIVATE_AGGREGATE_ONLY | +4 | 2 QPS PRs (private) |
| `GBOGEB/pipeline-automation-hub` master | `e4b901afa7706dee862730c4a468a96b7b07bcfc` | `516b905821bc1dcb299cd454a10c8c0b0f8adce3` | +4 | #865, #867, #854, #871 |

What R1 found:
- **ABACUS main `6ebebbc2`.**
  - There are 88 terminal runs that were not cancelled. 5 of them failed: CI/CD Test Suite, DMAIC V3 Enterprise CI and DOW + Recursive DMAIC Enhanced CI, plus Deploy Next.js site to Pages and DOW + Recursive DMAIC Unified CD Pipeline, which were both already red at the checkpoint.
  - 32 runs were cancelled. All of them are the PR Feedback Gate Evaluator, superseded by newer runs.
  - None of these reds names a QPS consumer, so there is no alert.
- **QPS main.**
  - `qps-canonicalization` succeeded at the new main (1/1). JADE CI, binary refresh and TRIAGE census at the same head also succeeded.
  - The QPS PR that fixed the W163 namespace collision merged with no review at its head.
  - Both new QPS merges were based on the checkpoint head, so the second was merged against an out-of-date main.
  - Result: no admission and no credit.
- **Hub master `516b9058`.** All 15 runs at this head succeeded. PR #876 records that #867, #854 and #871 merged with 0 reviews and First-Pass failures (CPQ-016 recurrence).
- **CODE PURPLE Disjoint Live Census.**
  - It failed again: [run 40244674158](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/40244674158), job `121323610711`, 2026-10-25T23:25:09Z, at `e4b901a`.
  - The step-4 log line is `{"http_status": 401, "repository": "ABACUS", "status": "SOURCE_ACCESS_UNKNOWN_FAIL_CLOSED"}`.
  - This is one more occurrence of the known root, not a new root.

### Correction to H1: W163 attribution

H1 §1.1 says native canonicalization "remained RED" even after the DELTA_1 consumer merged. That wording suggests the consumer caused the red. GitHub shows:

- canonicalization **succeeded** at the DELTA_1 consumer's merge commit;
- the first W163 red came from a **later, unrelated QPS merge**: `validate` step 7, `qps_w163_validate_namespace_collisions.py`;
- the red recurred on 3 main heads and cleared at R1's QPS main.

So the DELTA_1 consumer did not introduce W163. The recovery still earns nothing: there was no review at its head and no QPS owner acceptance. PR #876's ledger row 7 ("candidate fix unmerged, main credit 0") is now stale on the first point. The credit is still 0.

## Causal roots (R1)

| Root | State | Fingerprint | Occurrences | Next action / owner |
|---|---|---|---:|---|
| `ROOT-HUB-ABACUS-401` | open | `code-purple-live-census.yml` step 4 exit 2; `http_status=401 repository=ABACUS`; secret `CROSS_REPO_READ_TOKEN` | ≥13 | Owner replaces or re-scopes the token (SC-A003); diagnosis in [#843](https://github.com/GBOGEB/pipeline-automation-hub/pull/843) |
| `ROOT-QPS-W163-NAMESPACE` | displaced (cleared on main, not accepted) | `qps-canonicalization.yml` validate step 7 exit 1 | 3 main heads | QPS owner disposition (SC-A005) |

Rows: [PULSE_R1_EVIDENCE.jsonl](PULSE_R1_EVIDENCE.jsonl) (9) and [PULSE_R1_CAUSAL_ROOTS.jsonl](PULSE_R1_CAUSAL_ROOTS.jsonl) (2), both projected through `private_boundary.project()` and checked against a QPS identifier denylist.

## H1 — 48-hour observation ledger (as reported, UTC)

The window runs from 2026-10-23T23:56Z to 2026-10-25T23:56Z. Belgium changed from CEST to CET on 25 Oct.

| UTC | Reported transition | Class |
|---|---|---|
| 24 Oct 09:41 | ABACUS #2419 merged; QPS canonicalization dependency update | Ordinary merge |
| 24 Oct 10:44 | ABACUS #2418 merged; DMAIC refresh | No QPS acceptance |
| 24 Oct 12:03 | ABACUS #2420 merged; 15 pre-merge checks green | Governed admission unproved |
| 24 Oct 14:17 | CODEX #1163 recursive-control projection; RCH-04 0→1, W003 governance failed | Parent metric only |
| 24 Oct 14:47 | Hub run [40104008589](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/40104008589): census fan-out, six receiver jobs green | Transport proof only |
| 24 Oct 16:36 | CODEX #1164 merged; RCH integration paths 16/16 | Technical proof |
| 24 Oct 17:14 | ABACUS #2429 merged; Tables 27–29 guard; upstream-token comparison unproved | Contract guard incomplete |
| 24 Oct 18:28 | ABACUS EVERRED [40120802240](https://github.com/GBOGEB/ABACUS/actions/runs/40120802240): formatting failure in two Python cells | One recurring root |
| 24 Oct 21:12–21:23 | CODEX #1178/#1179/#1180 (observation-binder, receipt hygiene) merged | Parent technical progression |
| 25 Oct 02:42 | New main epochs in ABACUS, CODEX and QPS; parent CI/security failures | No named QPS consumer effect |
| 25 Oct 04:32 | Hub [40162279013](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/40162279013): HTTP 401 | Root first seen in window |
| 25 Oct 06:42 / 08:34 / 11:26 / 13:26 / 14:27 / 17:25 / 22:25 | Hub [40170051856](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/40170051856), [40177134525](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/40177134525), [40188831799](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/40188831799), [40197600314](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/40197600314), [40202313496](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/40202313496), [40216392888](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/40216392888), [40240126521](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/40240126521): same boundary | Occurrences of one root |
| 25 Oct 09:32 | QPS merge (private): historical TOP7 dashboard/postmortem evidence | QPS-native only |
| 25 Oct 10:35–10:37 | CODEX #1181/#1182/#1183 merged: Pages repair, inventory counts, readiness probe | No governed QPS credit |
| 25 Oct 12:00–12:02 | CODEX #1184/#1185 and hub [#848](https://github.com/GBOGEB/pipeline-automation-hub/pull/848) merged; P0002 readiness projection | Observation improvement |
| 25 Oct 15:44–15:45 | CODEX #1186 and two QPS merges (private) | Housekeeping |
| 25 Oct 18:45–18:50 | [ABACUS #2441](https://github.com/GBOGEB/ABACUS/pull/2441) and [CODEX #1192](https://github.com/GBOGEB/CODEX/pull/1192) DELTA_1 adapters merged; PR-head gates red | Producer change, no QPS acceptance |
| 25 Oct 20:07 → 21:48 | DELTA_1 QPS consumer (private PR): OPEN with federation smoke red, then merged | Ordinary merge |
| 25 Oct 22:06 → 22:42 | QPS exact-main canonicalization W163 red (private runs) | QPS-native red (see correction) |

Between these events, the old watch re-checked at about 05:00, 09:27, 10:23, 11:42, 13:43, 15:01, 16:17 and 17:27 UTC. Each check reported no accepted transition. These are stability observations, not eight separate events.

### Readiness projection (reported, not a matched cohort)

| State | P0001 | P0002 | Change |
|---|---:|---:|---:|
| PASS | 14/60 | 17/60 | +3 |
| FAIL | 8/60 | 2/60 | −6 |
| UNKNOWN | 38/60 | 41/60 | +3 |

There is no member-by-member crosswalk. Do not read this as closure of the same 60 requirements.

## Evidence receipts worth carrying

| Evidence | Native identity | Limitation |
|---|---|---|
| 24 Oct hub census | [run 40104008589](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/40104008589), artifact `12563773112`, `sha256:671be27a3396353b5502937750d209cf798a030617bdf852772e3b907f69ff88` (github_metadata) | Read-only fan-out; not engineering admission |
| 25 Oct last in-window census failure | [run 40240126521](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/40240126521), job `121309936180`, artifact `12616397382`, `sha256:9db6cb086833b0ea3deb2dc62866d2c5e183ea6e13372fcca530ebac023c1fa9` (github_metadata) | Failure receipt |
| R1 census failure | [run 40244674158](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/40244674158), job `121323610711` | Same root |
| ABACUS DELTA_1 PR-head A10 | [run 40221740474](https://github.com/GBOGEB/ABACUS/actions/runs/40221740474), job `121254575404` | Tender-material guard failed |
| CODEX DELTA_1 governance | [run 40221850891](https://github.com/GBOGEB/CODEX/actions/runs/40221850891), job `121254918144` | Governance header / follow-up failed |
| QPS DELTA_1 smoke, QPS canonicalization | PRIVATE_AGGREGATE_ONLY | PR-head smoke red; exact-main W163 red then green |

Immutable merges: ABACUS #2441 `635980c54b1a7759312e8a9a7def1498c80d0644`, CODEX #1192 `0bc810fbb74847b40a477f474f8c76bd8037032c`; the QPS consumer merge is private. Digests are API metadata, not re-hashed member bytes. Run attempts and step logs that H1 did not record remain UNKNOWN.

## PR / issue lineage

| Lane | Public identifiers | Status at R1 |
|---|---|---|
| ABACUS core control | [#1860](https://github.com/GBOGEB/ABACUS/issues/1860), [#1929](https://github.com/GBOGEB/ABACUS/issues/1929), historical PR #2105 | Issues open |
| ABACUS source / contract | #2429, #2435, [#2441](https://github.com/GBOGEB/ABACUS/pull/2441); red canary [#2470](https://github.com/GBOGEB/ABACUS/pull/2470) | #2470 open, UNSTABLE not BLOCKED (per #876) |
| CODEX MissionControl | [#977](https://github.com/GBOGEB/CODEX/issues/977), historical PR #1058 | Open |
| CODEX federation | #1163/#1164, #1178–#1186, [#1192](https://github.com/GBOGEB/CODEX/pull/1192)/#1194 | Merged; technical progression |
| Hub source access | [#843](https://github.com/GBOGEB/pipeline-automation-hub/pull/843) | Open; 401 unresolved |
| Hub observer / measurement | [#848](https://github.com/GBOGEB/pipeline-automation-hub/pull/848) merged; [#849](https://github.com/GBOGEB/pipeline-automation-hub/pull/849) open | — |
| QPS tri-repo support, owner controls, runtime, DELTA_1 consumer | Private: 1 support issue, 5 owner-control issues, 1 runtime issue, 1 historical support PR, 1 consumer PR; 6 adjacent engineering actions | Owner authority retained in QPS |

## Restart contract (CP.RESUME V2)

- **Mode:** `VERIFY_REFRESH_READ_ONLY`.
- **Scope:** the watch is not a QPS engineering burn-down. BREAD & BUTTER owns bidder reviews, LKT/ALaT, RTM/OFFER, SSOT, originals, binaries, cost, disposition and release.
- **Data direction (typed):** QPS source action → QPS SSOT → QPS release binary/QA → CODEX federation → ABACUS DOW evidence → JADE TOP7 → TOP21. An analytical edge is never an authority transfer.
- **Only four alert classes:**
  - **A.** A correctly governed parent admission with a proven QPS unlock.
  - **B.** A matched-cohort parent coverage gain that resolves a named QPS requirement.
  - **C.** A changed parent first-red that blocks or unblocks a named QPS issue.
  - **D.** An authenticated MissionControl acceptance milestone that satisfies an open QPS/TOP7 dependency.
- **Otherwise SILENT.** Persist the observation and send no narrative.
- **Restart steps:**
  1. Read this record and verify `MANIFEST.json`.
  2. Refresh heads, PR heads, issues and effective rulesets without changing anything.
  3. Diff by exact identity, then reduce roots by fingerprint.
  4. For each candidate, find the named QPS child and its native receipt.
  5. Check owner authority and governed admission separately.
  6. Publish only a qualifying differential.

Templates that already exist and should be reused rather than duplicated:
- ABACUS `handover/HANDOVER_MESSAGE_TEMPLATE.md` and `tools/handover_v2/process_spec.json`;
- hub `mission-control/v2/handoff/CP_HANDOFF_RESUME_V1.json` and `mission-control/federation-atlas/flightdeck/handover/W4/`;
- QPS `triage/jade_temple_qps/bread_and_butter/`;
- CODEX `PIPELINE/GLOSSARY.yaml`.

## H2 MIP backlog, mapped onto PR #876

The H2 list in the retiring chat overlaps #876's MIP-01..15. Implement against #876's IDs. The gaps are proposals for #876's owner, not new canonical items.

| H2 (retiring chat) | #876 equivalent | Gap |
|---|---|---|
| H2-01 Persistent observation/delta ledger | MIP-01 | — |
| H2-02 Canonical causal-root registry | MIP-09 | — |
| H2-03 Typed QPS consumer / authority graph | — | **Gap**: no unlock without a named QPS child and authority receipt |
| H2-04 Governing admission veto engine | MIP-04 (partial) | **Gap**: rejected-RED-canary and missing-review negative controls |
| H2-05 Exact-head / coverage comparator | MIP-02 + MIP-08 | — |
| H2-06 Alert suppression and idempotency | MIP-11 (+ MIP-01) | — |
| H2-07 Source/binary succession validation | MIP-03 (partial) | Controlled-original lineage |
| H2-08 Queue and time-of-flight telemetry | MIP-10 | — |
| H2-09 N−1/N/N+1 predictive REX | — | **Gap**: forecast-versus-actual log |
| H2-10 Adversarial / reverse-sequence tests | MIP-14 | — |
| H2-11 Method Atlas and dashboard | MIP-12 | — |
| H2-12 PCA/BT priority analytics | MIP-13 | — |

These negative tests carry over as acceptance fixtures for SC-A006:
- a parent merge without a named QPS receipt raises no alert;
- green CI without an eligible review earns no admission;
- a stale or cancelled SHA is not terminal evidence;
- N runs of the 401 count as one root;
- a changed coverage denominator is rejected;
- a QPS consumer merged while W163 is red is not an unlock;
- P0001→P0002 without member lineage is not closure;
- a correct ZIP digest with wrong members is rejected;
- a synthetic merge SHA substituted for the PR head is rejected;
- an A→B→A source sequence raises no duplicate alert;
- a missing original or owner decision stays UNKNOWN/HOLD.

## REX (method)

| REX | Cause | Response |
|---|---|---|
| REX-01 | Poll frequency mistaken for information frequency | Event-based delta reducer and a silent state |
| REX-02 | Parent technical progress read as QPS progress | Typed consumer and authority gate |
| REX-03 | Repeated CI failures inflate the root count | Fingerprint plus occurrence counter |
| REX-04 | Metrics from different observations look comparable | Matched numerator/denominator contract |
| REX-05 | Long chat instructions become a shadow SSOT | Repo-first record and a short CP.RESUME seed |

Retire the old chat only after SC-A001 merges and SC-A008 (a fresh-session replay) matches.
