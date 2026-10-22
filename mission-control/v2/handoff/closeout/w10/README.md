# CODE PURPLE W10 — canonical lossless GitHub-first handover

**Identity:** `CP-W10-MYCELIUM-FEDERATION-20261018` · **capture:** 18 October 2026, date-only/non-atomic. **State:** REVIEWABLE_PROPOSAL; `MERGE_ADMISSION=HOLD`.

This is an **append-only successor** to the already merged W9 evidence and the frozen CP-FED-CENSUS-W4 record. The canonical producers are unchanged:

- ABACUS `tools/handover_v2/process_spec.json`, `handover/HANDOVER_MESSAGE_TEMPLATE.md`: independent `LOSSLESS_HANDOVER_V2` domain capsule schema, not attested by this GitHub-only record.
- Mission Control `mission-control/v2/handoff/closeout/cp_close.py`: **only** GitHub-first CP.CLOSE nine-artifact generator for this session.
- Mission Control `mission-control/v2/handoff/CP_HANDOFF_RESUME_V1.json`: `CP.HANDOFF` / `CP.RESUME` / `G3P.EXECUTE(N,N+3)` operator, not an automated ChatGPT tool.

## Read and verify in order

1. [Source intake](../intakes/CP-W10-MYCELIUM-FEDERATION-20261018.json) — 12 traced intents, 23 owned actions, 6 decisions, 6 insights, 5 PRs, 16 typed historical/pending metrics, **all 19 CPQ identifiers**.
2. [Generated canonical record](../records/CP-W10-MYCELIUM-FEDERATION-20261018/START_HERE.md) — **only after** generated nine files are committed and native byte-parity receipt is terminal; otherwise use the source intake and pending Actions artifact.
3. [Current public-safe repository heads](PUBLIC_REPO_HEADS.json), [matched metrics & unknowns](METRIC_LEDGER.md), [19-item CPQ projection](GLOBAL_CPQ_TODO.md), and [SIPOC/DAG](SPINE_SIPOC.mmd).
4. [Copy-ready CP.RESUME instruction](NEXT_CHAT_DROPIN.md) — fresh-fetch the actual current heads and required protections **before any mutation**.

### Historical last-good hook (not a claim about later master)

Hub #724 source `fec6231abdead0ce8554b36c7199470bda3a97b1` merged as `2cc9b4d433c404b50d7afc661f863b96d42e97cc`. W9 [native run 39147416140](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/39147416140), attempt 1, 3 successful native jobs; Python 3.11 and 3.12 each **77/77** test cases; coverage only for `collect.py+history.py` at this head: **434/516 statements, 122/144 branches**. Artifact `12143768528`, independently checked ZIP **135187 bytes**, SHA-256 `262131fdaba860aef00e28dd158bb4f8eed7b1da00c36010a69a0f83b584ba12`, **10/10** ZIP CRC, **7/7** member-manifest SHA-256. This is **not #530's global custody acceptance**.

W9 CODEX Mycelium run census **661/661** (261 successes / 400 failures), selected detailed jobs **160 = 100 red+60 green**; two step-level symptom fingerprints, not two independently identified causal roots. Canonical CPQ **19 items: 10 DONE, 5 ACTIVE, 2 TODO, 2 READER**, i.e., nine non-DONE, **zero new independently accepted causal closures**.

CODEX #1097 N7 receipt diagnostic passed at `d3f55c168a65bd287873d461bcc26ddaccbfbfaf`, [run 39146937220](https://github.com/GBOGEB/CODEX/actions/runs/39146937220), attempt 1, job `117732579114`: **23/23 tests**, **495/512 statements**, **114/136 branches**, original 90%/80% minima unchanged. It then **merged**, but has zero observed PR reviews, so no governed-admission credit.

**New first-red to carry:** OSV fail-on-vuln [run 39147772131](https://github.com/GBOGEB/CODEX/actions/runs/39147772131), job `117735007297`, on historical CODEX main `d4174eb97a48ee5bc0d463640a305dd63059fa12`, **6 vulnerabilities/4 packages**, 3 medium + 3 low. Attribution to #1097 is **unproven**. Preserve fail-closed security.

**Next unqualified child:** [hub #725](https://github.com/GBOGEB/pipeline-automation-hub/pull/725) `f83f2fcea92cbc21ff54aabdc5e79aa239547a5a`, [first W10 run 39148332224](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/39148332224) queued at capture; **34 authored tests**, no executed, coverage, ZIP or severity credit until terminal exact-head evidence.

## Reproducible canonical generator (no duplicate tools)

```bash
C=mission-control/v2/handoff/closeout
NAME=CP-W10-MYCELIUM-FEDERATION-20261018
BD=mission-control/federation-atlas/CODE_PURPLE_BD_QUEUE_v1.json
python "$C/cp_close.py" --intake "$C/intakes/$NAME.json" --bd "$BD" \
  --out "$C/records/$NAME" --zip "/tmp/$NAME.zip"
python "$C/cp_close.py" --intake "$C/intakes/$NAME.json" --bd "$BD" \
  --out "$C/records/$NAME" --check
```

The new native workflow `.github/workflows/cp-w10-federation-handover.yml` runs the unchanged generator, replay check, SHA-256 and ZIP CRC. The committed record must **exactly** match the generator, and untracked output members must be disclosed separately. No source record may claim full verbatim ChatGPT transcript, original message IDs, private QPS contents, authenticated remote worker, human review, waiver or merge.

**Fidelity:** `GITHUB_FIRST_OPERATIONAL_NOT_VERBATIM_NOT_V2_SEALED`; raw complete chat export unavailable, therefore chat statistics null/UNKNOWN. No private QPS SHA, title, commercial/engineering bytes or issue count is included in this public package.

**Admission:** M1 partial, M2/M3/PCA/BT not qualified, worker-hours/capacity unknown. Required admin review and effective rules/negative RED canary remain independently owner-blocked. `MERGE_ADMISSION=HOLD`.
