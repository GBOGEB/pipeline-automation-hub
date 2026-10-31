#Requires -Version 7.0
<#
.SYNOPSIS
    One bird's-eye view of every git repo and worktree on this PC, plus an optional PyCharm workspace folder.
.DESCRIPTION
    Runs in sequence, read-only:
      1. Invoke-WorkspaceAudit.ps1 (same folder, the owner of the KEEP / PUSH-ME / REMOVABLE / LEFTOVER rules)
         once per -Root, never with -Apply. Roots with no git folder directly under them are skipped.
      2. The same audit for every <main repo>\.claude\worktrees folder found in step 1 (Claude Code worktrees).
      3. `git worktree list --porcelain` for every main repo, to list worktrees that live anywhere else and
         stale entries whose folder is gone.
    Writes WORKSPACE_OVERVIEW.md, .csv and .json into -OutDir (dated), plus WORKSPACE_OVERVIEW_latest.md.

    -PyCharmWorkspace <folder> also builds a folder of directory junctions that PyCharm opens as one project:
      repos\      main clones          (<repo>__<folder>)
      worktrees\  KEEP / PUSH-ME worktrees, i.e. not yet landed (<repo>__<folder>)
      extra\      folders from -ExtraFolder (e.g. a non-git working folder)
    Only junctions are created or removed in that folder. Their targets are never modified or deleted.
.EXAMPLE
    pwsh -File tools/workstation/Invoke-WorkspaceOverview.ps1
.EXAMPLE
    pwsh -File tools/workstation/Invoke-WorkspaceOverview.ps1 -PyCharmWorkspace C:\repos\GBOGEB_WORKSPACE -ExtraFolder "$HOME\OneDrive - Studiecentrum voor Kernenergie\Master_Input\QPS_ACTION_LEDGER"
.EXAMPLE
    pwsh -File tools/workstation/Invoke-WorkspaceOverview.ps1 -ReuseReports "$HOME\workspace-overview\reports\20261031-1945" -PyCharmWorkspace C:\repos\GBOGEB_WORKSPACE
    # rebuild the overview and the PyCharm folder from an earlier audit run, without re-auditing
#>
[CmdletBinding()]
param(
    [string[]] $Root = @(
        'C:\repos\_wt', 'C:\repos', 'C:\DEV\REPOS',
        (Join-Path $HOME 'Documents\Codex\2026-10-19\upd\work'),
        (Join-Path $HOME 'Documents\Codex\2026-10-23'),
        $HOME,
        (Join-Path $HOME 'OneDrive - Studiecentrum voor Kernenergie')
    ),
    [string]   $OutDir = (Join-Path $HOME 'workspace-overview'),
    [string]   $ReuseReports,
    [string]   $PyCharmWorkspace,
    [string[]] $ExtraFolder = @(),
    [switch]   $SkipSize
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$audit = Join-Path $PSScriptRoot 'Invoke-WorkspaceAudit.ps1'
$stamp = Get-Date -Format 'yyyyMMdd-HHmm'
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

function Get-Key([string]$Path) { if ($Path) { [IO.Path]::GetFullPath($Path).TrimEnd('\').ToLowerInvariant() } else { '' } }
function Test-HasGitChild([string]$Dir) {
    (Test-Path -LiteralPath $Dir) -and [bool](Get-ChildItem -LiteralPath $Dir -Directory -Force -ErrorAction SilentlyContinue |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName '.git') } | Select-Object -First 1)
}
function Invoke-Audit([string]$Dir, [string]$ReportRoot) {
    $name = ($Dir -replace '[:\\/ ]+', '_').Trim('_')
    $dest = Join-Path $ReportRoot $name
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    $auditArgs = @('-NoProfile', '-File', $audit, '-Root', $Dir, '-ReportPath', $dest, '-SkipTokenCheck')
    if ($SkipSize) { $auditArgs += '-SkipSize' }
    Write-Host ("[{0:HH:mm:ss}] audit {1}" -f (Get-Date), $Dir)
    & pwsh @auditArgs *> (Join-Path $dest 'console.txt')
    if ($LASTEXITCODE) { Write-Warning "audit of $Dir exited $LASTEXITCODE (see $dest\console.txt)" }
}

# ------------------------------------------------------------------ 1-2. audits (read-only)
if ($ReuseReports) {
    $reportRoot = (Resolve-Path -LiteralPath $ReuseReports).ProviderPath
}
else {
    $reportRoot = Join-Path $OutDir "reports\$stamp"
    foreach ($r in $Root) {
        if (Test-HasGitChild $r) { Invoke-Audit $r $reportRoot } else { Write-Host "skip $r (no git folder directly under it)" }
    }
}
function Read-Reports {
    Get-ChildItem -LiteralPath $reportRoot -Recurse -Filter 'workspace-audit-*.json' | ForEach-Object {
        $j = Get-Content -LiteralPath $_.FullName -Raw | ConvertFrom-Json
        foreach ($e in @($j.Entries)) { $e | Add-Member -NotePropertyName Root -NotePropertyValue $j.Root -Force; $e }
    }
}
$all = @(Read-Reports)
if (-not $ReuseReports) {
    $audited = @{}; foreach ($r in $Root) { $audited[(Get-Key $r)] = $true }
    $claude = $all | Where-Object { $_.MainRepo } | ForEach-Object { Join-Path $_.MainRepo '.claude\worktrees' } | Sort-Object -Unique
    foreach ($c in $claude) {
        if (-not $audited.ContainsKey((Get-Key $c)) -and (Test-HasGitChild $c)) { Invoke-Audit $c $reportRoot; $audited[(Get-Key $c)] = $true }
    }
    $all = @(Read-Reports)
}
$seen = @{}; $entries = [Collections.Generic.List[object]]::new()
foreach ($e in $all) { $k = Get-Key $e.Path; if ($k -and -not $seen.ContainsKey($k)) { $seen[$k] = $true; $entries.Add($e) } }

# ------------------------------------------------------------------ 3. worktrees git knows about elsewhere
$outside = [Collections.Generic.List[object]]::new()
$mains = $entries | Where-Object { $_.MainRepo } | Select-Object -ExpandProperty MainRepo | Sort-Object -Unique
foreach ($m in $mains) {
    if (-not (Test-Path -LiteralPath $m)) { continue }
    $text = (& git.exe -C $m worktree list --porcelain 2>$null) -join "`n"
    foreach ($block in ($text -split "`n`n")) {
        $d = @{}
        foreach ($line in ($block -split "`n")) { $kv = $line -split ' ', 2; $d[$kv[0]] = if ($kv.Count -gt 1) { $kv[1] } else { $true } }
        $p = $d['worktree']
        if (-not $p -or $seen.ContainsKey((Get-Key $p)) -or (Get-Key $p) -eq (Get-Key $m)) { continue }
        $branch = '(detached)'
        if ($d.ContainsKey('branch')) { $branch = ([string]$d['branch']) -replace '^refs/heads/', '' }
        $outside.Add([pscustomobject]@{
                Main = $m; Path = $p; Branch = $branch
                OnDisk = (Test-Path -LiteralPath $p); Prunable = $d.ContainsKey('prunable'); Locked = $d.ContainsKey('locked')
            })
    }
}

# ------------------------------------------------------------------ 4. overview files
$order = @{ 'PUSH-ME' = 0; 'REMOVABLE' = 1; 'LEFTOVER' = 2; 'KEEP' = 3 }
function GB($list) { $t = 0L; foreach ($x in @($list)) { if ($x) { $t += [long]$x.SizeBytes } }; [math]::Round($t / 1GB, 2) }
function Row($e) {
    $pr = ("{0} {1}" -f $e.PRState, $e.PR).Trim()
    "| $($e.Class) | ``$($e.Name)`` | $($e.Kind) | $($e.Branch) | $pr | $($e.Ahead)/$($e.Behind) | $(if ($e.Dirty) { 'yes' }) | $($e.LastCommitAge) | $([math]::Round($e.SizeBytes / 1MB)) | $($e.Reason) |"
}
$hdr = "| Class | Folder | Kind | Branch | PR | Ahead/Behind | Dirty | Last commit | MB | Why |`n|---|---|---|---|---|---|---|---|---|---|"
$md = [Collections.Generic.List[string]]::new()
$md.Add("# Workspace overview — $env:COMPUTERNAME — $(Get-Date -Format 'yyyy-MM-dd HH:mm')`n")
$md.Add("Read-only. Classification by ``Invoke-WorkspaceAudit.ps1`` (one run per root, never ``-Apply``); reports in ``$reportRoot``.`n")
$md.Add("- **PUSH-ME:** local commits not on GitHub; push before anything else.")
$md.Add("- **REMOVABLE:** clean, and its work has landed.")
$md.Add("- **LEFTOVER:** non-git residue.")
$md.Add("- **KEEP:** everything else.`n")
$md.Add("## 1. Per root`n")
$md.Add("| Root | Entries | PUSH-ME | REMOVABLE | LEFTOVER | KEEP | GB | Reclaimable GB |`n|---|---|---|---|---|---|---|---|")
foreach ($g in ($entries | Group-Object Root | Sort-Object Name)) {
    $c = $g.Group | Group-Object Class -AsHashTable -AsString
    $n = { param($k) if ($c -and $c.ContainsKey($k)) { $c[$k].Count } else { 0 } }
    $md.Add("| ``$($g.Name)`` | $($g.Count) | $(& $n 'PUSH-ME') | $(& $n 'REMOVABLE') | $(& $n 'LEFTOVER') | $(& $n 'KEEP') | $(GB $g.Group) | $(GB ($g.Group | Where-Object Class -in 'REMOVABLE','LEFTOVER')) |")
}
$md.Add("| **All** | **$($entries.Count)** | **$(@($entries | Where-Object Class -eq 'PUSH-ME').Count)** | **$(@($entries | Where-Object Class -eq 'REMOVABLE').Count)** | **$(@($entries | Where-Object Class -eq 'LEFTOVER').Count)** | **$(@($entries | Where-Object Class -eq 'KEEP').Count)** | **$(GB $entries)** | **$(GB ($entries | Where-Object Class -in 'REMOVABLE','LEFTOVER'))** |`n")
$md.Add("## 2. PUSH-ME — push first (``git -C <path> push -u origin HEAD``)`n")
$pm = @($entries | Where-Object Class -eq 'PUSH-ME' | Sort-Object Name)
if ($pm) { $md.Add($hdr); $pm | ForEach-Object { $md.Add((Row $_)) }; $md.Add('') } else { $md.Add("None.`n") }
$md.Add("## 3. REMOVABLE / LEFTOVER`n")
$rm = @($entries | Where-Object Class -in 'REMOVABLE', 'LEFTOVER' | Sort-Object SizeBytes -Descending)
if ($rm) {
    $md.Add($hdr); $rm | ForEach-Object { $md.Add((Row $_)) }
    $md.Add("`nTo remove the REMOVABLE linked worktrees of one root, run ``Invoke-WorkspaceAudit.ps1 -Root <root> -Apply``. It re-checks each entry and never forces. Delete LEFTOVER folders by hand.`n")
}
else { $md.Add("None.`n") }
$md.Add("## 4. Per repository`n")
foreach ($g in ($entries | Group-Object { if ($_.Repo) { $_.Repo } else { '(no origin / leftover)' } } | Sort-Object Count -Descending)) {
    $md.Add("### $($g.Name) — $($g.Count) folders, $(GB $g.Group) GB`n")
    $md.Add($hdr)
    $g.Group | Sort-Object { $order[$_.Class] }, Name | ForEach-Object { $md.Add((Row $_)) }
    $md.Add('')
}
$md.Add("## 5. Worktrees registered in git outside the audited folders`n")
if ($outside.Count) {
    $md.Add("| Main repo | Worktree | Branch | On disk | Prunable | Locked |`n|---|---|---|---|---|---|")
    $outside | Sort-Object Main, Path | ForEach-Object { $md.Add("| ``$($_.Main)`` | ``$($_.Path)`` | $($_.Branch) | $(if ($_.OnDisk) { 'yes' } else { '**missing**' }) | $(if ($_.Prunable) { 'yes' }) | $(if ($_.Locked) { 'yes' }) |") }
    $md.Add("`nA **missing** or prunable entry is stale bookkeeping; ``git -C <main repo> worktree prune`` clears it without deleting files.`n")
}
else { $md.Add("None.`n") }
$md.Add("## 6. Duplicate clones`n")
$dups = @($entries | Where-Object { $_.Kind -eq 'clone' -and $_.Repo } | Group-Object Repo | Where-Object Count -gt 1)
if ($dups) { foreach ($g in $dups) { $md.Add("- **$($g.Name)**: " + (($g.Group | ForEach-Object { "``$($_.Path)`` ($($_.Class))" }) -join '; ')) }; $md.Add('') } else { $md.Add("None.`n") }

$base = Join-Path $OutDir "WORKSPACE_OVERVIEW_$stamp"
$md -join "`n" | Set-Content -LiteralPath "$base.md" -Encoding utf8
Copy-Item "$base.md" (Join-Path $OutDir 'WORKSPACE_OVERVIEW_latest.md') -Force
$entries | Sort-Object { $order[$_.Class] }, Repo, Name |
    Select-Object Class, Name, Kind, Repo, Branch, PRState, PR, Ahead, Behind, Unpushed, Dirty, Stashes, HostedWorktrees, LastCommitAge, SizeBytes, Reason, Path, MainRepo, Root |
    Export-Csv -LiteralPath "$base.csv" -NoTypeInformation -Encoding utf8
[ordered]@{ Generated = (Get-Date).ToString('s'); Reports = $reportRoot; Entries = $entries; Outside = $outside } |
    ConvertTo-Json -Depth 6 | Set-Content -LiteralPath "$base.json" -Encoding utf8

# ------------------------------------------------------------------ 5. PyCharm workspace (junctions only)
if ($PyCharmWorkspace) {
    $ws = $PyCharmWorkspace
    $want = @{}
    foreach ($e in $entries) {
        if (-not $e.Repo -or $e.Class -notin 'KEEP', 'PUSH-ME' -or -not (Test-Path -LiteralPath $e.Path)) { continue }
        $sub = if ($e.Kind -eq 'clone') { 'repos' } elseif ($e.Kind -eq 'worktree') { 'worktrees' } else { continue }
        $want[(Join-Path $ws "$sub\$(($e.Repo -split '/')[-1])__$($e.Name)")] = $e.Path
    }
    foreach ($x in $ExtraFolder) { if (Test-Path -LiteralPath $x) { $want[(Join-Path $ws "extra\$(Split-Path $x -Leaf)")] = (Resolve-Path -LiteralPath $x).ProviderPath } }
    foreach ($sub in 'repos', 'worktrees', 'extra') { New-Item -ItemType Directory -Force -Path (Join-Path $ws $sub) | Out-Null }
    $removed = 0; $added = 0
    foreach ($sub in 'repos', 'worktrees', 'extra') {
        foreach ($i in Get-ChildItem -LiteralPath (Join-Path $ws $sub) -Force) {
            if ($i.LinkType -ne 'Junction') { continue }                                   # never touch real folders
            if (-not $want.ContainsKey($i.FullName) -or ($i.LinkTarget -ne $want[$i.FullName])) {
                [IO.Directory]::Delete($i.FullName, $false); $removed++                    # removes the link only
            }
        }
    }
    foreach ($kv in $want.GetEnumerator()) {
        if (-not (Test-Path -LiteralPath $kv.Key)) { New-Item -ItemType Junction -Path $kv.Key -Target $kv.Value | Out-Null; $added++ }
    }
    @(
        "# $(Split-Path $ws -Leaf) — PyCharm workspace (generated $(Get-Date -Format 'yyyy-MM-dd HH:mm'))", '',
        'Every entry below is a directory junction (link) to the real folder. Deleting a link here does not delete the target.',
        'Rebuilt by tools/workstation/Invoke-WorkspaceOverview.ps1 -PyCharmWorkspace; landed (REMOVABLE) worktrees drop out automatically.', '',
        '- repos\      main clones', '- worktrees\  worktrees not yet landed (KEEP / PUSH-ME)', '- extra\      other working folders', '',
        "Overview: $base.md"
    ) | Set-Content -LiteralPath (Join-Path $ws 'README_WORKSPACE.md') -Encoding utf8
    Write-Host "PyCharm workspace $ws : $($want.Count) links ($added added, $removed removed)"
}
Write-Host "Overview: $base.md"
Write-Host ("{0} folders: {1} PUSH-ME, {2} REMOVABLE, {3} LEFTOVER, {4} KEEP; {5} worktrees registered elsewhere ({6} missing)" -f $entries.Count,
    @($entries | Where-Object Class -eq 'PUSH-ME').Count, @($entries | Where-Object Class -eq 'REMOVABLE').Count,
    @($entries | Where-Object Class -eq 'LEFTOVER').Count, @($entries | Where-Object Class -eq 'KEEP').Count,
    $outside.Count, @($outside | Where-Object { -not $_.OnDisk }).Count)
