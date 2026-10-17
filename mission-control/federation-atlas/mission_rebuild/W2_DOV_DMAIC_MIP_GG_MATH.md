# Mission Control W2 — Pipeline/Federation convergence and source-bound DoV

W2 is a **read-only telemetry observation adapter and HTML/Plotly consumer** in the *existing* Method Atlas and Pages flow. It does **not** duplicate the scientific gg_MATH convergence kernel, create a scheduler, dispatch workers, issue a security waiver, accept QPS engineering or repair historic merge governance.

## W1 native first-red / attempt handover

W1 original PR [#669](https://github.com/GBOGEB/pipeline-automation-hub/pull/669) head `28b6b0dd6910cf730456fcdbf0c95b157626773b` merged as `ea9d7e531eb43a160e9edbf185c7db700f1cd28b` at 2026-10-17T19:07:16Z **without a terminal head-qualified Method Atlas result or recorded independent reviewer**. Original run [#39060705443](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/39060705443) was QUEUED, attempt 1, job 117477894170, at the prior live check. `attempts/2` returned 404. Never re-label the historic unapproved merge as approved; preserve `MERGE_ADMISSION=HOLD`.

The current live script refreshes these exact identities rather than copying this note into acceptance evidence. It does not repeatedly rerun an unchanged queued run.

## Four bottom-row unknowns — source-owning unblocks

| Row | W1 status | W2 improvement / direct unblock | Can turn green when |
|---|---|---|---|
| Statements / branches / coverage delta | UNKNOWN numerator, denominator and matched scope | W2 types unbound fields as null, not zero. Existing Method Atlas may emit focused coverage but it is NOT broad or another repo's coverage. | Terminal native exact-head coverage JSON validated for matched file/cohort, both statement+branch numerators/denominators; compare immutable population |
| Runner capacity / actual worker hours | UNKNOWN | W2 queries native GitHub queued/in-progress **run counts**, disambiguating backlog from free runners. Planner max 3/2 remains a *historical knob*, not measured capacity. | Native job actual start/end, runner identity/slots or authorized runner inventory with source time and a method to aggregate nonoverlapping busy minutes |
| Independent reviews | Historic W1: **0 recorded** | W2 read-only live PR review readback; zero is observed zero, not unknown. | Independently eligible human review of **next PR** before merge; historic approval cannot be backfilled |
| M1/M2/M3 / PCA / BT / capability | M1 structural only; M2/M3 HOLD | W2 links to canonical gg_MATH source and uses its native job/artifact status; Plotly renders observation charts **without computing a second scientific fit**. | M1 measurement-system checks; M2 matched repeated independent cohort with stability test; M3 CTQ/independence/capability; PCA aligned features & eigengap; BT connected paired comparisons and bootstrap CI |

Other frontier: artifact ZIP and responsive QA for W1 exact-head remain UNKNOWN while the native W1 job is queued; **gg_MATH provider** native artifact verification is a distinct completed owner-owned lane.

## gg_MATH source and independent proof

Canonical provider [#61](https://github.com/GBOGEB/gg_MATH/pull/61), source head `37afe75d9911691698a849b21fcfad0df1844432`:
- [Native run 39047980808](https://github.com/GBOGEB/gg_MATH/actions/runs/39047980808) attempt 1 terminal SUCCESS, Python 3.11 and 3.12 kernel jobs plus Plotly HTML job all SUCCESS.
- Native artifact 12107372904, 2,227,336 ZIP bytes, SHA-256 `bcc99279e0a1dd536f5f9b5c34046777178d0bd8ece3ed2640899033f444e2a9`. Independently downloaded and verified: 7 ZIP members, 6/6 provider-manifest member digests, 10 native HTML contract tests; browser QA 1440×1000 / 1280×800 / 390×844, zero recorded console/page errors and horizontal body overflow.
- **Artifact contains synthetic methodological examples** (`test_fixture_only=true`); not a live federation M2/M3 or QPS receipt.
- [gg_MATH #63 run 39049078036](https://github.com/GBOGEB/gg_MATH/actions/runs/39049078036): attempt 1 terminal SUCCESS, Python 3.11/3.12 jobs passed.
- Original `GG_MATH_CONVERGENCE_BRIDGE_v1.json` still says #61 QUEUED and `native_terminal_verified=false`. W2 identifies this as consumer observation drift, without rewriting historical snapshots or asserting owner admission.

## Math, DMAIC and MIP gate

For comparable matched-eligibility fractions `y_i=k_i/d_i` the pulse velocity `v_i=(y_i-y_(i-1))/(N_i-N_(i-1))` is defined **only if** `d_i` and scope identity are comparable. Acceleration `a_i=v_i-v_(i-1)` is not a control-limit test. A flat sequence with queued jobs is `BLOCKED_UNTIL_OWNER_EVIDENCE`, not `STABILIZED`; a short zero slope without blocking is `PLATEAU_DESCRIPTIVE_NOT_PROVEN_STABLE`. Do not fit a trend with one or two non-atomic snapshots.

**DMAIC:** Define CTQ and owner root → Measure native run/job/attempt and matched population → Analyze duplicate fingerprints vs deduplicated causes, queue/worker dependency → Improve source-owner repair/receipt binding → Control fresh exact-head execution plus next independent pulse. **MIP:** Modernize stale bridge, Innovate typed readbacks + Plotly, Perpetuate only after DoV and repeatable adoption.

**PCA:** In `gg_MATH/kernels/convergence_control.py`, require paired feature identity and matched preprocessing, independent effective `n≥max(20,5p)`, explain eigengap and align loading vectors/congruence; no PCA certificate from the graph's 54 nodes as though they were independent observations. **Bradley–Terry:** require a connected graph of matched paired method outcomes, exposure-balanced comparisons, uncertainty intervals and prospective prediction scoring. No observations => unqualified.

**Six Sigma:** `DPMO=10^6 d/n` only for a defined defect opportunity and independence. Even zero defects need at least `ceil(log(0.05)/log(1-3.4e-6))=881,097` independent opportunities to obtain a one-sided 95% upper defect bound at or below the conventional shifted-Six-Sigma 3.4-DPMO target. Merely running ten positive tests cannot establish this. This is a statistical sample-size calculation, not a requirement to run millions of current Mission Control tests.

## W2 completion acceptance (conjunction)

`W2_DOV = SOURCE_SHA_MATCH ∧ NATIVE_JOB_ATTEMPT_RECEIPT ∧ FOUR_STATE_ROWS_NOT_IMPUTED ∧ GG_MATH_PROVENANCE_BOUND ∧ PLOTLY_4_CHARTS ∧ THREE_VIEWPORT_QA ∧ PAGES_MEMBER_BYTE_PARITY`

Native job-run identity, run attempt and artifact member bytes must be available *and* terminal before exact-head DoV. A source-owned diagram or source API claim is not itself merge admission. The W2 script may return partial observations with typed `UNKNOWN`; these improve observability but do **not** make W2 DoV PASS.

Build in existing Atlas native job:
```sh
python -m unittest discover -s mission-control/federation-atlas -p 'test_*.py' -v
python mission-control/federation-atlas/mission_rebuild/w2_live_bridge.py --head "$(git rev-parse HEAD)" --out /tmp/code-purple-atlas/mission-rebuild/evidence.json
python mission-control/federation-atlas/mission_rebuild/w2_plotly.py --snapshot /tmp/code-purple-atlas/mission-rebuild/evidence.json --out /tmp/code-purple-atlas/mission-rebuild
```

Use existing `pages_portal.py` and `code-purple-method-atlas.yml`, not a duplicate publisher. GH_TOKEN is only read-only; cross-repo source access may fail and must then become UNKNOWN.
