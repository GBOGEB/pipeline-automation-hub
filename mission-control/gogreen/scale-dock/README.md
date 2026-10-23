# CODE PURPLE · N+1→N+i recursive scale dock (read-only)

**Status:** LOCAL_REPRODUCIBILITY_ONLY. This is an additive Mission Control / GoGREEN integration candidate, not a second producer, fleet dispatcher or release gate. No remote worker/source mutation occurred during this local testflight. The fixture is **SYNTHETIC_REFERENCE**, not fresh GitHub evidence.

## Functional main sequence / hierarchical SIPOC

`Native evidence producers` (S) → `exact source/run/attempt/job/step, typed DAG, optional gg_MATH output` (I) → `validate, deduplicate, rank hard-DAG descendants, classify queue regime, compare N-series, decide fixed point` (P) → `JSON/Mermaid/HTML + SHA-256 bytes manifest` (O) → `#533 Method Atlas viewer, independent #530 ZIP verifier, #531 census and human reviewer` (C).

The local Python entry point is `mission-control/gogreen/scale_dock.py`. It does not import GitHub credentials, contact a network, invoke arbitrary commands, schedule executable workers or alter the source of truth. `gg_MATH` remains the mathematical provider; this only validates the `gg_math.g3a_pulse_decision.v1` digest and HOLD flags and exposes any forecast MAE as **non-native advisory evidence**. `LDAB` native manifestations and `LLDB` debugger sessions are separately classified.

## Local executable wave

```bash
python -m unittest discover -s mission-control/gogreen/tests -p test_scale_dock.py -v
python -m coverage run --branch --include='*/scale_dock.py' -m unittest discover -s mission-control/gogreen/tests -p test_scale_dock.py -q
python -m coverage json -q -o coverage.json
python mission-control/gogreen/scale_dock.py \
  --input mission-control/gogreen/samples/scale_dock_synthetic_three_pulses.json \
  --out ./out --source-sha "$(git rev-parse HEAD)"
```

An **actual** exact-source SHA must be supplied if running within a trusted checkout. Running with an arbitrary locally supplied SHA is merely reproducibility, not native authentication; the script does not corroborate `git rev-parse HEAD` itself.

## Pulse and supervision

| Pulse | Selected population | Supervisory policy | Stop criteria |
|---|---|---|---|
| N0 | source-bound initial cohort | unsupervised **read-only** census | no closure admitted |
| N+1 | same population + new native tuples / first reds | supervised repair *proposals* on disjoint paths | compare immutable population and denominators |
| N+2..N+i | recensus, queue and credible source-owner proof | no automatic execution; independent approval | N+1=N plus complete eligible cohort and zero known queue; residual ⇒ STOP_SCALING_DIAGNOSE |

The included three-pulse synthetic fixture runs 5/5 observational rows at each index, with one purely synthetic RECOVERED marker. N1=N2 yields `STOP_SCALING_DIAGNOSE_RESIDUAL` because four manifestations remain unresolved; **no real root is closed**. The regression suite also generates a synthetic 260-row cohort that has **13 fingerprints, 247 repeat occurrences, and zero known root IDs**. Those are test fixture results, not the 260 historical ABACUS workflow outcomes.

The shadow broker's proposed maxima are 4 unsupervised readers and 2 supervised source-writing candidates for observed queue-length zero; 2/1 if recovering; 0/0 if queue age p95 exceeds 600 seconds, queue length >16, or queue identities unknown. These are **candidate caps**, not runner slots, work performed, GitHub worker-hours, or a capacity estimate. No mutation may be executed without separate source-owner authority and Git lease.

## Statistics and evidence boundaries

Coverage compares only identical `(repo,population,scope,tool,selection)` and identical statement/branch denominators. If denominators change, delta remains null. A declared DAG descendant count is **structural**, not verified runtime effect. Candidate `root_id`s, fingerprints, manifestations and repeat occurrences are distinct populations. No synthetic proof can grant M1/M2/M3, PCA/Bradley–Terry, QPS, security, cross-repo coverage, publication or review acceptance. History is immutable; forecasts issued before outcomes must be preserved and scored in the **gg_MATH provider**, not retrofitted here.

N+1=N is a *local evidence-state equality* after checking source heads, native identities, population, coverage, queue identities and finding states. It is a **scaling stop/diagnostic trigger**; it does not mean M2 process stability or release admission.

## First-red / root-red and docked metrics

Every receipt now carries three additive blocks. The stop decision is unchanged by them.

**`red_metrics`** comes from the pulse series alone:
- Per pulse: red count and rate; the share of reds with a known first-failed step; root-linked vs unrooted reds; `root_red` (candidate roots with at least one RED manifestation); `root_recovered` (all RECOVERED); and `fingerprint_root_conflicts`, where one fingerprint points to two candidate roots (a crosswalk defect, not two roots).
- Per N→N+1 transition: `new_first_reds`, `recoveries`, `regressions` (RECOVERED→RED) and `persisting_reds`.
- Window totals: `everred_in_window` (RED in every pulse), `red_burndown`, `recovery_rate` and `regression_rate`. These describe manifestation state only and give no root-closure credit.

**`docks`** holds read-only projections of existing producers, each bound by `input_sha256` and aged against the latest pulse (`stale` past 72 h):

| Dock | Producer schema | Metrics |
|---|---|---|
| `everred` | `everred.census/1.0` | signature match rate; open roots by priority; closure and recurrence rate; control-plane red rate; E1 red P0 probes; scale-dock candidate roots matched to EVERRED IDs or aliases |
| `code_purple` | `code-purple.census/v2` | lift criteria met and unmet; gate-green and red-merge rate since the unblocker; open PRs; open follow-ups |
| `p_process` | `p-process.state/1.0` | mode per repo; CODE_PURPLE repos; open roots; worst priority; ruleset-red rate |
| `issue_bd` | `codepurple.bd-queue-wave.v1` | open items and issues by repo; red-PR and unknown-PR rate; manifestations per red PR; top families; queue p50/p95 |
| `crosswalk` | `codepurple.g5.discovery-gap-crosswalk.v1` | historical and current 42-cell breadth; gap packets by state and family; native-identity rate; verified archives; root-bound packets |

An absent dock is `NOT_DOCKED`, which means UNKNOWN, never zero. Docks fail closed on schema, partition, numerator/denominator, partial native identity, alias collision, and any authority, dispatch or merge flag set to true.

**`dock_consistency`** cross-checks the sources:
- incident and `lifted` match between CODE PURPLE and P-process;
- EVERRED open roots equal the P-process sum;
- snapshot timestamps agree;
- E1 and E2 imply that at least one repo is in CODE_PURPLE mode.

Any disagreement yields `HOLD_SOURCE_DISAGREEMENT`; the dock reports it and never repairs it.

```bash
P=mission-control/qps-triage-ultra/p-process/site
python mission-control/gogreen/scale_dock.py --input <series.json> --out ./out --source-sha "$(git rev-parse HEAD)" \
  --everred $P/everred/data/everred.json --code-purple $P/code-purple/kit/census.json \
  --p-process $P/data/p_state.json --issue-bd <bd_summary.json> \
  --crosswalk mission-control/gogreen/g5_gap_crosswalk_20261015.json
```

## Rebuild outputs

`out/scale-dock.json`, `out/scale-dock.mmd`, `out/scale-dock.html`, `out/scale-dock-manifest.json`. Manifest binds exact *operator-supplied* generator SHA, member byte lengths and SHA-256. Rebuild assets only from an upstream source; never edit outward HTML into engineering truth. A GitHub-native run/job/artifact receipt and independent ZIP readback remain required for `EXACT_SHA_RECEIPT`.

**Authority**: #530 ZIP verifier · #531 six-repo census · #533 viewer. ABACUS #2077/#2090/#2101 keep their own failure/root/queue ownership; CODEX owns actual LLDB sessions; private QPS data is out of this public dock.
