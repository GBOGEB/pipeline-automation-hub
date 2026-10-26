# P process: Code Purple × EVERRED

The P process is one control loop that runs at two speeds.

| Mode | Purpose | Entry | Exit |
|---|---|---|---|
| **Code Purple** (acute) | PR and problem burndown. Highest priority, with most resources on one admission blocker. | Owner declares `kit/incident.yaml` | Lift criteria L1–L5 met. Close-out then hands every inherited red to EVERRED. |
| **EVERRED 3.0** (recursive) | Health monitor and continuous root-cause repair. RECURSE every pulse. | Always on | Never exits. Each `everred.json` is an immutable census row. |

The switch rules live in `p_process.yaml`; `p_decide.py` evaluates them on every refresh.

- **Escalation (EVERRED → Code Purple)** happens on any of:
  - **E1**: a red P0 control-plane probe
  - **E2**: an open case that has not been lifted
  - **E3**: the owner declares one
- **Handoff (Code Purple → EVERRED)** happens on:
  - **H1**: the case is lifted
  - **H2**: every red seen during the case has a root ID or an alias
  - **H3**: steady burndown work moves to EVERRED lanes

The authority boundary of QPS TRIAGE ULTRA applies unchanged:
- The pages are read-only review projections.
- Only the owner applies rulesets or breaks glass, using a one-time bypass actor and never by deleting rules.

## Layout

| Path | What |
|---|---|
| `kit/` | Code Purple instance (`incident.yaml`) and `readback.py`, which produces the lift census. L2 compares rule content; L5 audits every merge. |
| `everred/` | V3 root ledger `roots.yaml`; `harvest.py` collects occurrences, signatures and the `ruleset_drift` probe; `build_page.py` renders the register. |
| `rulesets/` | BASIC rulesets for ABACUS, CODEX, cryoplant-project, gg_MATH, the hub and Q_engineering_tools, plus ABACUS HARD. `verify_rulesets.py` writes the drift census `drift.json`. |
| `code-purple/` | The Code Purple page: `index.html` plus `assets/model.js` (the single model) and `assets/app.js`. `build_deck.js` and `merge_deck.py` produce the 16:9 deck. |
| `types/`, `tools/` | TypeScript types for the model and `check_model.mts`, a referential-integrity check. |
| `p_process.yaml`, `p_decide.py`, `build_p_process.py` | P-process spec, mode evaluator, and home page plus 16:9 companion PDF. |
| `refresh.py` | One command for everything below. |
| `site/` | Published static site; `manifest.json` holds a SHA-256 for every file. Staged into the CODE PURPLE Pages portal under `p-process/`. |
| `fonts/` | IBM Plex and Archivo (OFL), embedded in PDFs. Aptos is first in the CSS stack wherever it is installed. |

## Refresh

```bash
python refresh.py              # live: readback -> drift -> harvest -> decide -> pages -> PDFs -> site/manifest.json
python refresh.py --offline    # rebuild from committed data (no network)
```

The live mode needs `gh` with read access to every repository in `probe_scope`. The private cryoplant-project needs a token that can read it.

Pages re-read their JSON every 5 minutes while open, so a refreshed census appears without a rebuild once `site/` is republished. The Code Purple header between `<!-- census:begin -->` and `<!-- census:end -->` is restamped from the census on each refresh.

Committed data is a snapshot as of the last refresh; check `census_at` in `site/manifest.json`.

## Verify

```bash
python -m unittest discover -s tests -v          # offline; CI: .github/workflows/p-process.yml
node tools/check_model.mts && npx -y -p typescript@6.0.3 tsc -p tsconfig.json
```

## Zip from a fresh clone

- **GitHub:** every `p-process.yml` run uploads the artifact `p-process-site-<sha>` (zip plus `.sha256`). Download it from the run page.
- **Windows PowerShell:** `pwsh -File regenerate.ps1 [-Offline] [-Branch <name>]`. It clones the repo, installs pinned tools, refreshes, tests, then packages.
- **Linux/macOS:** `python refresh.py [--offline] && python package.py`

`package.py` checks every file against `site/manifest.json` first. Zip timestamps are fixed, so the same site always gives a byte-identical zip.

Wave record: `WAVE_CLOSE_P_PROCESS_20261018.md`.
