# Burn-down pulses

Two scripts that read GitHub once and write the datasets behind the owner's two burn-down dashboards
(claude.ai artifacts). The scheduled tasks `burndown-pulse-refresh` (every 30 min) and `issue-pulse-refresh`
(hourly at :15) run them and upload the JSON to the dashboard. Until #1199 they lived only on one PC.

| Script | Writes | Rows (`kind`) | Reads |
| --- | --- | --- | --- |
| `burndown_pulse.py` | `pulse.json` | `meta`, `repo`, `pr`, `wf`, `day` | open PRs, merges per day (7 days), default-branch workflow runs, default-branch head SHA, for PAH, cryoplant-project and ABACUS |
| `issue_pulse.py` | `issue_pulse.json` | `meta`, `repo`, `issue`, `pr`, `edge`, `day` | open issues from the canonical register (`retrieve_issue_register` in `mission-control/federation-atlas/central/recensus.py`, imported from a git ref, not copied), issue-PR links, opened/closed per day (14 days), for PAH, cryoplant-project, ABACUS and CODEX |

Both print one JSON summary line (`path`, `rows`, `pulse_at`, and `heads` or `counts` + `register`).

## Read-only toward GitHub

Every `gh` call goes through `burndown_pulse.gh()`, which calls `assert_read_only()` first. Only
`repo view`, `pr list`, `run list` and `gh api` GETs (and GraphQL queries, not mutations) are allowed;
anything else raises `ValueError` before `gh` runs. `gh` runs without `GITHUB_TOKEN` / `GH_TOKEN`, so the
keyring login is used even while a stale token is set.

## Run

```powershell
Set-Location "<your pipeline-automation-hub clone>"
git fetch -q origin master
python tools\workstation\dashboards\pulse\burndown_pulse.py "$env:TEMP\pulse-out"
python tools\workstation\dashboards\pulse\issue_pulse.py "$env:TEMP\issue-out"
```

`issue_pulse.py` reads the register from `--ref` (default `origin/master`) of a hub clone, chosen in this
order: `--pah <clone>`, the `ISSUE_PULSE_PAH` environment variable, then the clone the script sits in. No
user path is built in.

## Test

```powershell
python -m unittest discover -s tools/workstation/dashboards/pulse -p "test_*.py" -v
```

The tests replace `burndown_pulse.run` with a fake `gh` runner, so they need no network and no login. They
cover the read-only guard, the PR next-step and issue link-state rules, the register loaded from a git ref,
and that no user path appears in the scripts. CI runs them in `.github/workflows/workstation-dashboards-qa.yml`.
