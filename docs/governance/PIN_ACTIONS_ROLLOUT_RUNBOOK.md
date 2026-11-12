# Action pinning rollout runbook (per repo)

Part of #1202. The tool is `scripts/ci/pin_actions.py`; the ratchet is `.github/workflows/actions-pin-ratchet.yml`.
Rollout order across repos and the list of waived repos are owner decisions (open on #1202) and are not set here.

Every command block starts in the target repo:

```powershell
Set-Location "C:\repos\<repo>"
git fetch origin; git switch -c chore/pin-actions origin/<default>
```

`pin_actions.py` lives in the hub. Run it from the hub checkout and pass the target repo's files, or copy nothing:
`python "C:\repos\pah_tools\scripts\ci\pin_actions.py" ...`. In a repo other than the hub, `--frozen-blob-scan`
and the rewrite guard look for pins inside the hub tree (`ROOT`); for a foreign repo run the scan from a
checkout of that repo's own copy of the tool, or treat the scan as advisory (see "Remainder" on #1202).

## 1. Scan (no network)

```powershell
python scripts/ci/pin_actions.py --check                 # unpinned refs; exit 1 when any
python scripts/ci/pin_actions.py --frozen-blob-scan      # workflows whose blob OID is pinned elsewhere
```

A **frozen** workflow is one whose current git blob OID appears in another tracked file: JADE outputs
(`cicd_dag.json`, `DEVOPS_CENSUS_*.json`, `actions_metrics.csv`), lineage/control JSON, the ci-spine explorer.
Rewriting it changes the OID and silently breaks that pin. Record the frozen list in the PR body.

## 2. Pin

```powershell
python scripts/ci/pin_actions.py                         # refuses (exit 2, nothing written) if any target is frozen
python scripts/ci/pin_actions.py --allow ci.yml --allow release.yml   # opt in per frozen file
```

Each pin is `owner/repo@<40-hex commit> # <tag>`. Resolution uses `gh api` (keyring auth; `unset GITHUB_TOKEN GH_TOKEN` on 401).

## 3. Ratchet

Copy `.github/workflows/actions-pin-ratchet.yml` into the repo (its own `uses:` lines pinned), so changed
workflow files must stay pinned. Re-run `--check`; it must print `ok:`.

## 4. dependabot.yml

Add or extend `.github/dependabot.yml` with the `github-actions` ecosystem (weekly) so pinned SHAs keep moving
with their `# vX` comments.

## 5. JADE regeneration

If any `--allow`ed frozen file changed, regenerate what pinned its OID in the same PR (hub:
`python mission-control/jade_temple/tools/cicd_dag.py` and the census generators), then re-run
`--frozen-blob-scan` and confirm the new OIDs are the pinned ones.

## 6. Waiver row

A repo the owner waives gets one row in the waiver register named on #1202 (repo, reason, owner, review date)
instead of steps 2-5. Do not invent waivers in the PR.
