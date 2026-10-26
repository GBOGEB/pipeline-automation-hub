# CODE PURPLE convergence receipt

Folds pulse ledgers into one receipt that follows
[`contracts/convergence-receipt.schema.json`](../../contracts/convergence-receipt.schema.json).

| Path | Role |
| --- | --- |
| `converge.py` | Reducer: normalise events, run cross-checks, write receipt + `.sha256` |
| `tests/test_converge.py` | Fail-closed tests (evidence model, plateau, schema, tamper detection) |
| `evidence/20261022/` | Input ledgers, chat-pulse transcription, generated receipt |
| `evidence/20261025/` | C18 supersession addendum (`GH_API_READONLY`, exact SHAs) and the 20261025 receipt |

```bash
python -m federation.convergence.converge
python -m pytest federation/convergence/tests
```

Rules the code enforces:

- `UNKNOWN != ZERO != VERIFIED NONE`: measures are evidence objects with a state
  (`NOT_OBSERVED`, `OBSERVED_EMPTY`, `OBSERVED_NONEMPTY`, `VERIFIED`, `CONFLICT`).
- Occurrences are not roots; `accepted_root_id` stays `null` until an owner assigns one.
- A population is comparable only when its exact head SHA equals the observed main SHA.
  A later merge without a re-observed main invalidates the anchor (`NOT_OBSERVED`).
- Integrity totals count only archives whose digest, CRC and member accounting hold in every
  ledger. Failures are counted and listed, never assumed to be zero.
- Plateau uses fresh, same-cohort measurements only. Replayed snapshots give
  `STARVED`, not `STABLE_HOLD`.

- Resolutions are optional and keyed by item id (`--resolutions <addendum>`). A supersession record
  resolves an item only when every head is an exact 40-hex SHA, the old head extends the reported
  prefix, the old head is a strict ancestor of the merged head and the merge commit has it as a parent.
  The result is `SUPERSEDED` with `WARN` while any check failed at the merged head, unless the
  failures are shown non-required and pre-existing. An invalid record leaves the item `FAIL`, and so
  does running without an addendum. The 20261022 receipt is never regenerated in place.

```bash
python -m federation.convergence.converge   --resolutions federation/convergence/evidence/20261025/C18_ABACUS_2367_SUPERSESSION_20261025.json   --out federation/convergence/evidence/20261025/CODE_PURPLE_SCALED_CONVERGENCE_20261025.json
```

Limits: the cross-checks C09–C18 are specific to the 2026-10-22 evidence (they name its
run and artifact IDs). `pasted_pulses_20261022.json` is a hand transcription of chat
reports (`CHAT_TRANSCRIPT_UNVERIFIED`). The source receipts it cites were not available.
