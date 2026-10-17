# Mission Control: 3W, 3P-CONT and N3-AUTO

**Status:** bounded control/helper, not an authorized worker dispatcher, scheduler, merge gate or replacement for the Mission Control v2 SSOT.

| Prompt | Meaning | Output |
|---|---|---|
| `3W` | Three **outcome waves**; each wave can contain several pulses or multiple disjoint workers | Outcome acceptance per wave; may exceed three executions |
| `3P-CONT` | Exactly three **consecutive pulses** N+1,N+2,N+3 in a named existing wave | Three individual action/proof receipts or an early STOP |
| `N3-AUTO` | Execute a `3P-CONT` **without routine back-and-forth**, subject to bounded scope, stop rules and owner authority | Actual vs forecast, validated receipts, unresolved gates, first major blocker |

Existing `3PR` (`Refresh-Probe-Rank`), `3PC` (`Prepare-Prove-Commit`), `3P3`, `3P*` and MIP remain separate method profiles. A pulse can choose one of those methods; a wave contains pulses. Never count an execution, source commit or emitted dashboard as a new wave automatically.

## Admission-safe protocol

1. **Precondition:** identify mission, existing wave, qualified repo and exact 40-character source SHA; declare `start_ordinal=N`; permitted file paths, worker leases, security and native-proof requirements; budget and independent reviewer.
2. **Pulse N+1:** independently observe source/input, pick one high-value bounded target by estimated effect and dependency reach, optionally execute through authorized runner, collect stdout/test/coverage/clock/manifest and first red, append a receipt.
3. **Pulse N+2:** consume the *actual* N+1 output source and receipt digest, execute the next admissible improvement, compare forecast/actual only on matched denominators, append.
4. **Pulse N+3:** repeat; return what changed, what did not, known unknowns, queue/coverage/time delta, actual source SHAs, CI status, blockers, REX, next owner action.
5. **Stop immediately:** branch drift, source conflict, path lease conflict, P0/P1 security, A10/governance, native-proof failure, missing dependency, unclassified high-risk or policy violation. Preserve previous receipts; do not invent N+3.
6. **Hold for independent review:** local test pass, source commit, graph SVG, association score or successful dry-run **never** confers native CI/security/merge admission.

## Machine contract

- Glossary: `MC_GLOSSARY_TAXONOMY_v2.json` continuation extension (v2.0.2).
- Vocabulary/guards: `MC_N3_CONTINUATION_CONTRACT_v1.json`.
- Read-only receipt validator: `n3_continuation.py`.
- Unit tests: `test_n3_continuation.py`.
- Example manifest: `../federation-atlas/CBD_GOLDEN_GRAPH_N3_20261017.json`.

```bash
python mission-control/v2/n3_continuation.py mission-control/federation-atlas/CBD_GOLDEN_GRAPH_N3_20261017.json
python -m unittest discover -s mission-control/v2 -p 'test_n3_continuation.py' -v
```

The utility validates local JSON and optionally appends **externally obtained** receipts using `--record ... --out ...`. It never authenticates a source SHA against GitHub on its own, spawns MCP workers, runs arbitrary commands, pushes to protected branches or silently completes a blocked continuation.

## N/N+3 answer contract

The final answer must disclose **planned vs actual** for all three pulses, source SHA and level of evidence for each, tests passed/failed with denominator, statement/branch coverage only if measured, cost/time saved only on comparable trials, first-red/root status (observed/unknown), merge-admission state and explicit handover. If only two pulses are completed, output `STOP_MAJOR_BLOCKER at N+2`, not `N+3 complete`.
