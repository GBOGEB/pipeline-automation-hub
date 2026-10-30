#Requires -Version 7.0
<#
.SYNOPSIS
    Clear merge conflicts that sit only in generated, SHA-pinned outputs (launcher.json, JADE pages) by
    taking the base branch's copy and re-running the regen entrypoint.

.DESCRIPTION
    Generated outputs such as mission-control/gogreen/launcher/launcher.json and index.html embed blob
    OIDs and commit SHAs. Every merge to master moves them, so every open PR that also touched them
    conflicts with master. The hunks are not worth resolving by hand: the right content is whatever
    the generators produce from the merged sources.

    For each PR this script:
      1. skips it as LIVE when another worktree on its branch is dirty or has a reflog entry younger
         than -LiveMinutes (same rule as Invoke-DraftPrPass.ps1), and as FORK when the head is in a fork;
      2. checks out the PR head detached in one scratch worktree (-WorkTree; reused, then removed) and
         merges origin/<base> into it;
      3. stops as MANUAL, with the file list, if any conflicted path is not a generated output. The
         generated set is read from regen.py's CHAIN at the base commit (its owner), plus -ExtraGenerated;
      4. otherwise takes the base copy of each conflicted generated file, commits the merge, then runs
         `regen.py --write` and commits until it stops changing anything (the launcher step reads HEAD,
         so it needs the earlier outputs committed first);
      5. runs `regen.py --check`. Steps that are stale at the PR but fresh at the base mark the PR
         STALE and block the push (override with -AllowStale). Steps already stale at the base are reported only;
      6. with -Push, pushes HEAD to the PR branch with --force-with-lease pinned to the head it merged
         into. The new commit is a descendant, so this never rewrites history; the lease only refuses
         a race with someone else's push.

    Without -Push it is a dry run: the merge and regen commits are made in the scratch worktree only,
    then discarded. It never changes a PR's draft state, never comments and never merges a PR.
    The FPC receipt must be written for the final head once CI has run; the script prints the command
    (or runs it with -WriteReceipt). All gh calls run with GITHUB_TOKEN/GH_TOKEN stripped (lesson 8).

.EXAMPLE
    pwsh -NoProfile -File tools/workstation/Resolve-RegenConflicts.ps1 -Pr 1036
    # dry run for one PR: what would conflict, what regen does, whether --check ends clean

.EXAMPLE
    pwsh -NoProfile -File tools/workstation/Resolve-RegenConflicts.ps1 -All -Push
    # every open CONFLICTING PR in the repo; pushes the ones that end RESOLVED
#>
[CmdletBinding(DefaultParameterSetName = 'Pr')]
param(
    [Parameter(ParameterSetName = 'Pr', Mandatory)] [int[]] $Pr,
    [Parameter(ParameterSetName = 'All', Mandatory)] [switch] $All,
    [string]   $Repo         = 'GBOGEB/pipeline-automation-hub',
    # The main checkout; its `git worktree list` is searched for live sessions and it hosts -WorkTree.
    [string]   $MainRepo     = 'C:\Users\gbonthuy\Documents\Codex\2026-10-23\pah-devops-n9',
    [string]   $WorkTree     = (Join-Path $env:TEMP 'pah-regen-resolver'),
    # Interpreter for regen.py. Default: the declared runtime through the py launcher, else python.
    [string[]] $Python       = $(if (Get-Command py -ErrorAction SilentlyContinue) { @('py', '-3.12') } else { @('python') }),
    # Extra repo-relative globs that count as generated (** crosses folders, * does not).
    [string[]] $ExtraGenerated = @(),
    [double]   $LiveMinutes  = 30,
    [int]      $MaxRegenRounds = 4,
    [string]   $ReportPath   = $env:TEMP,
    [switch]   $Push,
    [switch]   $AllowStale,
    [switch]   $WriteReceipt,
    [switch]   $KeepWorkTree
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$now = [DateTimeOffset]::UtcNow
$tokenNames = 'GITHUB_TOKEN', 'GH_TOKEN'
$regen = 'mission-control/jade_temple/tools/regen.py'
$classOrder = 'MANUAL', 'STALE', 'FAIL', 'LIVE', 'FORK', 'RESOLVED', 'PUSHED', 'NOOP'

# ---------------------------------------------------------------- helpers --
function Invoke-Gh {
    <# Runs gh in a child process with the token variables stripped. Same rule as Invoke-WorkspaceAudit.ps1. #>
    param([string[]]$Arguments)
    $psi = [System.Diagnostics.ProcessStartInfo]::new('gh')
    foreach ($a in $Arguments) { $psi.ArgumentList.Add($a) }
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.UseShellExecute = $false
    $psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    foreach ($n in $tokenNames) { [void]$psi.Environment.Remove($n) }
    $p = [System.Diagnostics.Process]::Start($psi)
    $errTask = $p.StandardError.ReadToEndAsync()
    $out = $p.StandardOutput.ReadToEnd()
    $p.WaitForExit()
    if ($p.ExitCode -ne 0) { throw "gh $($Arguments[0..1] -join ' ') failed: $($errTask.Result.Trim())" }
    $out
}

function Get-GhJson([string[]]$Arguments) { Invoke-Gh $Arguments | ConvertFrom-Json -Depth 50 }

function W {
    <# git in the scratch worktree; returns string[], throws with the output on a non-zero exit. #>
    $out = & git.exe -C $WorkTree @args 2>&1 | ForEach-Object { "$_" }
    if ($LASTEXITCODE -ne 0) { throw "git $($args -join ' ') failed: $($out -join "`n")" }
    @($out)
}

function Wq { <# git in the scratch worktree; returns the exit code only. #> & git.exe -C $WorkTree @args *> $null; $LASTEXITCODE }

function Invoke-Regen([string]$Mode) {
    $exe, $pre = $Python[0], @($Python | Select-Object -Skip 1)
    Push-Location -LiteralPath $WorkTree
    try { $out = & $exe @pre $regen $Mode 2>&1 | ForEach-Object { "$_" } } finally { Pop-Location }
    [pscustomobject]@{ Code = $LASTEXITCODE; Lines = @($out)
        Stale = @($out | Where-Object { $_ -like 'REGEN_STALE *' } | ForEach-Object { ($_ -split '[ :]')[1] }) }
}

function Get-GeneratedPatterns {
    <# regen.py CHAIN outputs at the checked-out commit (the owner of the list), plus -ExtraGenerated. #>
    $exe, $pre = $Python[0], @($Python | Select-Object -Skip 1)
    $code = "import sys;sys.path.insert(0,'mission-control/jade_temple/tools');import regen;" +
            "print('\n'.join(o for s in regen.CHAIN for o in s.outputs))"
    Push-Location -LiteralPath $WorkTree
    try { $out = @(& $exe @pre -c $code) } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0 -or -not $out) { throw "could not read regen.CHAIN outputs" }
    @($out) + $ExtraGenerated | Where-Object { $_ }
}

function Test-Generated([string]$Path, [string[]]$Patterns) {
    foreach ($g in $Patterns) {
        $rx = '^' + ([regex]::Escape($g) -replace '\\\*\\\*', '.*' -replace '\\\*', '[^/]*') + '$'
        if ($Path -match $rx) { return $true }
    }
    $false
}

function Get-LiveWorktrees([string]$Branch) {
    <# Worktrees of -MainRepo on $Branch that look live: dirty, or reflog younger than -LiveMinutes. #>
    $hits = @(); $path = $null
    foreach ($line in @(& git.exe -C $MainRepo worktree list --porcelain 2>$null)) {
        if ($line -like 'worktree *') { $path = $line.Substring(9); continue }
        if ($line -ne "branch refs/heads/$Branch" -or -not $path -or -not (Test-Path -LiteralPath $path)) { continue }
        $dirty = @(& git.exe -C $path status --porcelain --untracked-files=normal 2>$null | Where-Object { $_ }).Count
        $last = (& git.exe -C $path reflog -1 --format=%ct 2>$null) | Select-Object -First 1
        $ageMin = if ($last) { ($now - [DateTimeOffset]::FromUnixTimeSeconds([long]$last)).TotalMinutes } else { [double]::MaxValue }
        if ($dirty -gt 0 -or $ageMin -lt $LiveMinutes) { $hits += "$path (dirty=$dirty, reflog $([math]::Round($ageMin)) min ago)" }
    }
    $hits
}

function Reset-WorkTree([string]$Ref) {
    if ((Wq rev-parse -q --verify MERGE_HEAD) -eq 0) { W merge --abort | Out-Null }
    W checkout -q --force --detach $Ref | Out-Null
    W clean -q -fdx | Out-Null
}

# ---------------------------------------------------------------- select --
$fields = 'number,title,url,headRefName,headRefOid,baseRefName,isCrossRepository,mergeable,isDraft'
$prs = if ($All) {
    @(Get-GhJson @('pr', 'list', '--repo', $Repo, '--state', 'open', '--limit', '300', '--json', $fields) |
        Where-Object mergeable -eq 'CONFLICTING')
} else {
    @($Pr | ForEach-Object { Get-GhJson @('pr', 'view', "$_", '--repo', $Repo, '--json', $fields) })
}
Write-Host ("REGEN_RESOLVE {0} PR(s) selected; push={1}" -f $prs.Count, [bool]$Push)
if (-not $prs) { return }

& git.exe -C $MainRepo fetch -q --prune origin 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { throw "git fetch origin failed in $MainRepo" }
if (-not (Test-Path -LiteralPath (Join-Path $WorkTree '.git'))) {
    & git.exe -C $MainRepo worktree add -q --detach $WorkTree 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "git worktree add $WorkTree failed" }
}

# ---------------------------------------------------------------- resolve --
$baseCache = @{}
$rows = [System.Collections.Generic.List[object]]::new()
try {
    foreach ($p in $prs) {
        $row = [ordered]@{ PR = $p.number; Class = ''; Head = $p.headRefName; Base = $p.baseRefName
            OldHead = $p.headRefOid.Substring(0, 8); NewHead = ''; Conflicts = @(); Manual = @()
            RegenRounds = 0; Stale = @(); BaseStale = @(); Detail = ''; Url = $p.url }
        try {
            if ($p.isCrossRepository) { $row.Class = 'FORK'; $row.Detail = 'head is in a fork; resolve it there'; continue }
            $live = @(Get-LiveWorktrees $p.headRefName)
            if ($live) { $row.Class = 'LIVE'; $row.Detail = ($live -join '; ') + '. Leave it to that session.'; continue }

            $base = "origin/$($p.baseRefName)"
            if (-not $baseCache.ContainsKey($base)) {
                Reset-WorkTree $base
                $baseCache[$base] = [pscustomobject]@{ Patterns = @(Get-GeneratedPatterns); Stale = @((Invoke-Regen '--check').Stale) }
            }
            $b = $baseCache[$base]; $row.BaseStale = $b.Stale

            W fetch -q origin "+refs/heads/$($p.headRefName):refs/remotes/origin/$($p.headRefName)" | Out-Null
            $head = @(W rev-parse "origin/$($p.headRefName)")[0]
            if ($head -ne $p.headRefOid) { throw "branch moved since gh read it ($($p.headRefOid.Substring(0,8)) -> $($head.Substring(0,8))); re-run" }
            Reset-WorkTree $head

            $merge = Wq merge -q --no-ff --no-commit $base
            if ((Wq rev-parse -q --verify MERGE_HEAD) -ne 0) {
                if ($merge -ne 0) { throw "git merge $base failed before recording a merge" }
                $row.Class = 'NOOP'; $row.Detail = "already contains $base"
            } else {
                $row.Conflicts = @(W diff --name-only --diff-filter=U | Where-Object { $_ })
                $row.Manual = @($row.Conflicts | Where-Object { -not (Test-Generated $_ $b.Patterns) })
                if ($row.Manual) {
                    W merge --abort | Out-Null
                    $row.Class = 'MANUAL'; $row.Detail = 'non-generated conflicts; resolve by hand, then re-run regen.py --write'
                    continue
                }
                foreach ($f in $row.Conflicts) { W checkout -q --theirs -- $f | Out-Null; W add -- $f | Out-Null }
                $msg = "Merge $base into $($p.headRefName)"
                if ($row.Conflicts) { $msg += "`n`nGenerated outputs taken from $base, then regenerated: $($row.Conflicts -join ', ')" }
                W commit -q -m $msg | Out-Null
            }

            for ($i = 1; $i -le $MaxRegenRounds; $i++) {
                $w = Invoke-Regen '--write'
                if ($w.Lines -match '^REGEN_FAIL') { throw "regen.py --write: $(($w.Lines | Select-Object -Last 5) -join ' | ')" }
                W add -A -- . | Out-Null
                if ((Wq diff --cached --quiet) -eq 0) { break }
                W commit -q -m "chore(regen): regenerate pinned outputs after merging $base (round $i)" | Out-Null
                $row.RegenRounds = $i
            }
            $row.Stale = @((Invoke-Regen '--check').Stale)
            $newStale = @($row.Stale | Where-Object { $_ -notin $b.Stale })
            $row.NewHead = @(W rev-parse HEAD)[0].Substring(0, 8)
            if ($row.Class -eq 'NOOP' -and $row.RegenRounds -eq 0) { continue }
            if ($newStale -and -not $AllowStale) {
                $row.Class = 'STALE'; $row.Detail = "stale after regen and fresh at base: $($newStale -join ', ')"; continue
            }
            $row.Class = 'RESOLVED'
            if ($Push) {
                W push -q origin "HEAD:refs/heads/$($p.headRefName)" "--force-with-lease=refs/heads/$($p.headRefName):$head" | Out-Null
                $row.Class = 'PUSHED'
                $receipt = "python scripts/fpc_receipt.py --pr $($p.number) --write"
                if ($WriteReceipt) {
                    Push-Location -LiteralPath $WorkTree
                    try { $exe, $pre = $Python[0], @($Python | Select-Object -Skip 1); & $exe @pre scripts/fpc_receipt.py --pr $p.number --write | Out-Host }
                    finally { Pop-Location }
                    $row.Detail = 'receipt written; refresh it again after CI finishes on the new head'
                } else { $row.Detail = "after CI runs on $($row.NewHead): $receipt" }
            } else { $row.Detail = 'dry run: re-run with -Push to push this merge' }
        } catch {
            $row.Class = 'FAIL'; $row.Detail = "$_"
        } finally {
            $rows.Add([pscustomobject]$row)
        }
    }
} finally {
    if ($KeepWorkTree) { Write-Host "Scratch worktree kept: $WorkTree" }
    else { & git.exe -C $MainRepo worktree remove --force $WorkTree 2>&1 | Out-Null; & git.exe -C $MainRepo worktree prune 2>&1 | Out-Null }
}

# ---------------------------------------------------------------- report --
$sorted = @($rows | Sort-Object { [array]::IndexOf($classOrder, $_.Class) }, PR)
$sorted | Format-Table PR, Class, OldHead, NewHead, @{ n = 'Conflicts'; e = { $_.Conflicts.Count } },
    @{ n = 'Manual'; e = { $_.Manual.Count } }, RegenRounds, @{ n = 'Stale'; e = { $_.Stale -join ',' } } -AutoSize | Out-Host
foreach ($r in $sorted) {
    Write-Host "$($r.Class) #$($r.PR) $($r.Head): $($r.Detail)"
    foreach ($m in $r.Manual) { Write-Host "    manual: $m" }
}
$summary = $sorted | Group-Object Class | ForEach-Object { "$($_.Name)=$($_.Count)" }
Write-Host ("REGEN_RESOLVE {0} PRs: {1}" -f $sorted.Count, ($summary -join ' '))

$file = Join-Path $ReportPath ("regen-resolve-{0:yyyyMMdd-HHmmss}.json" -f $now.LocalDateTime)
[ordered]@{ schema = 'workstation.regen_resolve.v1'; generated_at = $now.ToString('o'); repo = $Repo
    pushed = [bool]$Push; allow_stale = [bool]$AllowStale; prs = $sorted } |
    ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $file -Encoding utf8NoBOM
Write-Host "Report: $file"
if ($sorted | Where-Object Class -in 'FAIL', 'STALE') { exit 1 }
