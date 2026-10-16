# CODE PURPLE developer on-ramp / cold worker scout

**Authority:** read-only and local by default; `security_waiver=false`, `authority_transfer=false`, `dispatch=STAGED_NOT_LAUNCHED`. This package is **not** a Crew launcher, GitHub mutation gateway, or replacement MissionControl SSOT.

## Where these files belong

For source-controlled developer onboarding, place this `devkit/` directory at `mission-control/federation-atlas/flightdeck/pulses/devkit/` in `GBOGEB/pipeline-automation-hub`. The canonical live process contracts stay in `mission-control/federation-atlas/`, telemetry from existing `PR_MERGE_TEMPORAL_H1_20261016.json` and `pr_run_history_collect.py`, and BD roots from ABACUS issue #1929. Ignore generated `.local-code-purple/` and local environment receipts.

## Visual Studio Code

1. Open the **repository root**, e.g. `C:\repos\pipeline-automation-hub`, not the standalone `devkit/` as the workspace.
2. Use an isolated Python 3.11/3.12 virtual environment. Python 3.9/3.10 can work after `python -m pip install tomli`.
3. Copy the provided `.vscode/tasks.json` and `.vscode/launch.json` templates only after checking any existing `.vscode/` configuration; **merge tasks rather than overwriting**.
4. Command Palette → **Tasks: Run Task** → `CODE PURPLE: cold probe (read-only)`; open `.local-code-purple/devkit-receipt.json`.
5. Run `CODE PURPLE: contract tests`; use **Run and Debug** → `CODE PURPLE cold scout` for breakpoints. Extension required: Python + Python Debugger. They are editor tools, not agent permissions.

## PyCharm

Open the repository root as a Project; configure a project virtual environment interpreter. Run → Edit Configurations → Python: script `mission-control/federation-atlas/flightdeck/pulses/devkit/worker_devkit.py`, working directory the repository root, parameters `--repo . --out .local-code-purple/devkit-receipt.json`; environment `PYTHONDONTWRITEBYTECODE=1;CODE_PURPLE_MODE=READ_ONLY_COLD`. A second **Python tests → Unittests** configuration targets `devkit/test_worker_devkit.py` or the exact discovery directory. Mark **Run with Python console** off when evaluating stdout JSON; debugger breakpoints stay in this process only. Do not share secrets in saved Run Configurations.

## PowerShell

```powershell
cd C:\repos\pipeline-automation-hub
python --version
pwsh -NoProfile -File .\mission-control\federation-atlas\flightdeck\pulses\devkit\Cold-Probe.ps1 -RepoRoot . -Out .\.local-code-purple\devkit-receipt.json
python -m unittest discover -s mission-control/federation-atlas/flightdeck/pulses/devkit -p test_worker_devkit.py -v
git rev-parse HEAD
git status --short --branch
```

`pwsh` is PowerShell 7. Windows PowerShell may run `powershell -NoProfile -File` instead; script uses portable PowerShell syntax.

## Bash

```bash
cd ~/repos/pipeline-automation-hub
python3 --version
bash mission-control/federation-atlas/flightdeck/pulses/devkit/cold_probe.sh . .local-code-purple/devkit-receipt.json
python3 -m unittest discover -s mission-control/federation-atlas/flightdeck/pulses/devkit -p test_worker_devkit.py -v
git rev-parse HEAD
git status --short --branch
```

## Manual cold static probes (not automatically run)

The scout *detects*, but never executes, linters, tests or agent CLIs. In an isolated **fresh clone or worktree**, choose only project-supported versions/configuration and manually run bounded checks such as:

```bash
python -m pip check
python -m compileall -q mission-control/federation-atlas/flightdeck/pulses/devkit
python -m unittest discover -s mission-control/federation-atlas/flightdeck/pulses/devkit -p test_worker_devkit.py -v
python -m pytest --collect-only -q
python -m ruff check mission-control/federation-atlas/flightdeck/pulses/devkit
```

`pip check`, collection and lint can fail for missing optional dependencies; record `NOT_RUN` versus `FAIL`. Cold results are **non-blocking diagnostics** but cannot override native exact-head CI, A10, Safety, governance or independent review. Never silently apply `ruff --fix`, `black`, `git reset --hard` or changes to production policy. A P0 security finding remains P0 even if a local cold task is skipped.

## Agentic CLIs and discovery

The scout checks `codex`, `claude`, `gemini`, `aider`, `opencode`, `gh` with PATH detection **only**. Presence does not imply authentication, billing, permission, capability, sandboxing, worker launch or REX acceptance. All agent dispatch is withheld. `AGENTS.md`, `SKILL.md`, `CODEOWNERS`, `pyproject.toml`, `requirements.txt`, `README.md` may be **indexed by name** for orientation, not executed or copied to an agent. Resolve canonical math through `GBOGEB/gg_MATH`, federation execution through `pipeline-automation-hub`, repo-local repairs through ABACUS, QPS decisions through its owner. Only authorized users can enable bounded external agents in a separate PR with principal/ref/action/lease/idempotency/REX validation.

## Data and scheduling

- `runner.toml` is a local **example overlay**, not the project's `pyproject.toml` or a new canonical policy.
- `worker_plan.json` is a **proposed** task graph with exact SHA, typed skill, lease, disjoint dependencies and simulated two-worker waves. Four-worker expansion depends on native queue p95, actual conflicts, repeated observations and owner approval.
- `SCHEDULE_TEMPLATE.json` is **MANUAL_ONLY**. To set a recurring developer job, use VS Code Task Scheduler / cron / Windows Task Scheduler after owner approval; this package does not create scheduled jobs.
- Extension inventory covers `.py`, `.toml`, `.json`, `.yaml`, `.yml`, `.ps1`, `.sh`, `.md`, `.ipynb` and Dockerfile; secrets and `.git` metadata are never inspected.
- Unknown `JYKALL` was not resolved as a named dependency and therefore is **not silently installed or invoked**.

**Definition of value:** first-red disappears on matched native exact head, coverage numerators and denominators are source-matched, root recurrence checked, independently governed gates pass. Everything else remains supporting observations.
