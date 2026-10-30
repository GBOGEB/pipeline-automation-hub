# HV-03 — local worktree and asset custody collector

**Source owner:** `tools/workstation/`. This additive reader **does not replace** the existing [Invoke-WorkspaceAudit.ps1](Invoke-WorkspaceAudit.ps1), which owns token, disk, push-age and optional cleanup classifications. HV-03 neither invokes its `-Apply` switch nor adds its own cleanup process.

**Trust boundary:** execute locally on a Windows PowerShell 7 workstation with Git and Python 3.10+. This project is PUBLIC. Private receipt bytes and raw export assets MUST remain outside Git and must not be sent to GitHub issues, Actions artifacts, chat, Pages or PR comments without separate, explicit owner authorization.

## Repeatable dry-run on the actual workstation

No local path is assumed. Set a real existing clone location yourself.

```powershell
$Repo = 'C:\PATH\TO\pipeline-automation-hub'   # replace from an actual directory
$Private = Join-Path $env:LOCALAPPDATA 'GBOGEB\HV03'
python tools/workstation/hv03_custody.py --repo $Repo
# No files created in dry-run. It prints only aggregate counts, opaque digest and HOLD.

# Explicit private output is opt-in, outside every Git worktree:
python tools/workstation/hv03_custody.py --repo $Repo --out-dir $Private
Copy-Item (Join-Path $Private 'HV03_PRIVATE.json') (Join-Path $Private 'HV03_PRIOR.json')
python tools/workstation/hv03_custody.py --repo $Repo --out-dir $Private --compare (Join-Path $Private 'HV03_PRIOR.json')
# repeat_scan_equal=true ONLY if the actual content and branch refs stayed identical
```

A private owner allowlist is optional; without it every file owner is **UNKNOWN**. The owner map is a private JSON file of form `{"schema":"gbo.hv03.owner-allowlist.v1","rules":[{"glob":"docs/ci-spine/**","owner":"explorer source owner","pr":1002}]}`. This is an **illustrative** rule, not a pre-approved ownership assignment. Competing glob matches are classified `COLLISION`; no guessed ownership is substituted. Use `--owner-map <private-file>` after explicit owner review.

## Inventory and receipts

- All Git-linked worktrees and local branch refs, exact local HEAD OIDs and current branch (detached remains null).
- Porcelain-v1 `-z` staged/unstaged/untracked/deleted/renamed files; working-tree SHA-256 and bounded file byte counts.
- Staged index Git blob OID and SHA-256 separately from the current working-tree bytes; conflict stages retained.
- Already tracked owner binaries by extension (PDF/DOCX/PPTX/XLSX/ZIP/images/executables etc.), with hash limits shown as `SIZE_LIMIT` rather than invented success.
- Synthetic `DECLARED_UNVERIFIED` file-owner mappings only when an explicit local owner map is supplied; otherwise `UNKNOWN`.
- `HV03_PRIVATE.json` and `HV03_SUMMARY.json` only when `--out-dir` is explicitly supplied outside the clone. On Windows the directory and both receipts get a protected DACL with one full-control ACE for the current user (`icacls`), read back and verified; on POSIX modes are 0700/0600. If owner-only access cannot be verified, nothing is written. Summary excludes file names and absolute paths.
- `incomplete_hashes` counts working-tree and staged-index entries that are not `HASHED`; `incomplete_worktrees` counts listed worktrees that are missing or prunable. A file whose size, mtime or identity changes while it is read is `CHANGED_DURING_SCAN`.
- Git runs with `core.fsmonitor=false` and `core.untrackedCache=false`, and with repository-local variables (`GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE` and the rest of `git rev-parse --local-env-vars`) removed, so no configured hook runs and the requested clone is the one scanned.
- Byte-deterministic SHA-256 of the private receipt, and optional prior-receipt comparison. The receipt carries no wall-clock claim, to allow stable same-state readback.

No `git fetch`, GitHub API, remote-head authentication, `git add`, commit, push, prune, delete, network upload or shell program installation occurs. A repository can change during scanning; re-run and compare. If it changes, mark `DRIFT` and reconcile before allowing any publication. **No successful scanner result alone authorizes publication**.

## Tests and DoV

```powershell
python -m unittest discover -s tools/workstation -p 'test_hv03_custody.py' -v
```

DoD: executable source, ten local fixture controls and owner instructions committed to a disjoint PR. DoV remains pending until (1) those tests run in an eligible environment, (2) two scans of the actual user workstation match with no unresolved file-owner collisions or unreadable bytes, (3) actual private receipts are independently reviewed, and (4) any external remote SHA comparison occurs via a separately authorized source readback. **Merge admission HOLD**; no vault or conversation export is included in this scope.
