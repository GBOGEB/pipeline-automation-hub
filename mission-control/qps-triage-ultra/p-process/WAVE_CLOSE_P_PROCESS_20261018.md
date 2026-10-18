# Wave close: P process consolidation (QPS TRIAGE ULTRA)

Status: `WAVE_CLOSED`. Delivery is complete. The incident CP-2026-10-12 stays `NOT_LIFTED`, because closing it requires the owner's ruleset action.
Census: 2026-10-18T13:27:47+00:00 · EVERRED 2026-10-18T13:29:56+00:00 · PR #701.

## Delivered
- Code Purple kit (lift readback). L2 now compares rule content. L5 now reads the gate state at merge time, as Codex finding 4307198790 asked.
- EVERRED 3.0 ledger: 16 roots with 7 dimensions each.
- Harvester with a fail-closed `ruleset_drift` probe. The probe compares each required check by name and by the GitHub App that reports it, so a same-named check from another app shows as drift (Codex finding 4307198794).
- BASIC rulesets for 6 repos, plus ABACUS HARD. The hub ruleset no longer requires the path-filtered `audit` check.
- P-process spec (`p_process.yaml`) with escalation rules E1–E3 and handoff rules H1–H3. `p_decide.py` evaluates them on each refresh.
- Code Purple page split into a shared model (`model.js`) and page behaviour (`app.js`), with TypeScript types and a model integrity check.
- Pages: P-process home, Code Purple, EVERRED register. PDFs: 16:9 P deck, 40-page Code Purple deck, A4 reader.
- `refresh.py` regenerates everything. `package.py` builds a reproducible zip. `regenerate.ps1` runs the same steps on Windows from a fresh clone.
- CI: `p-process.yml` runs the offline tests and the TypeScript check, and uploads the zip as an artifact. The Pages portal stages the site under `p-process/`.

## Measured state at close
| Item | Value |
|---|---|
| Lift criteria met | 2 of 5 (L1✓, L2✗, L5✗, L3✓, L4✗) |
| ABACUS merges since #1858 | 97; gate green at merge time on 0; 97 with red checks |
| Ruleset probe | 6 of 6 repos red |
| EVERRED | 375 occurrences · 68 signatures · 15 independent roots · closure 0.2 · replay UNKNOWN |
| Modes | ABACUS=CODE_PURPLE, CODEX=EVERRED, Q_engineering_tools=EVERRED, cryoplant-project=EVERRED, gg_MATH=EVERRED, pipeline-automation-hub=EVERRED |

## Carried to the next wave (owner unless noted)
1. Import `rulesets/ABACUS.basic.json`, or add its `required_status_checks` rule to 24494381. This closes ABACUS-RC-2026-0001 (P0) and unblocks L2.
2. Import BASIC rulesets for CODEX, cryoplant-project, gg_MATH and Q_engineering_tools. Retarget hub ruleset 25252917.
3. Agent: re-run `refresh.py` after each import. Code Purple lifts only when L1–L5 all hold, then hands its roots to EVERRED (H1/H2).
4. Inherited hub reds, not caused by PR #701: `render` (CPQ N5 visual proof), `readonly-site-qa`, `first-pass-closure`.
5. The EVERRED 3.0 source text (INV-01..10, lanes A–H, P0–P7) was not available to this wave; the pages reference these items only by name.

## Regenerate
- GitHub: the `p-process.yml` run on a PR or on master uploads the artifact `p-process-site-<sha>` (zip + `.sha256`).
- Windows: `pwsh -File regenerate.ps1` for a live readback (needs `gh auth login`), or `-Offline` to rebuild from the committed data.
- Linux/macOS: `python refresh.py [--offline] && python package.py`.
