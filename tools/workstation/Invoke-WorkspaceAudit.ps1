#Requires -Version 7.0
<#
.SYNOPSIS
    Recurring workstation audit: stale GitHub tokens, unpushed branches and reclaimable worktrees/clones.

.DESCRIPTION
    Makes three CI lessons permanent:
      L5  Push branches early   - flags local-only/ahead branches older than -PushAfterHours (PUSH-ME).
      L8  Stale GITHUB_TOKEN    - reports GITHUB_TOKEN/GH_TOKEN at Process/User/Machine scope and whether
                                  each value still authenticates, compared with the gh keyring login.
                                  It prints the removal command but NEVER changes environment variables.
      L9  Disk is tight         - sizes every git repo/worktree directly under -Root, classifies it as
                                  REMOVABLE / PUSH-ME / KEEP and totals the reclaimable space.

    Read-only by default. -Apply removes REMOVABLE entries only:
      * linked worktrees with `git worktree remove` (never --force), then `git worktree prune`;
      * standalone duplicate clones only when -AllowCloneDelete is ALSO passed, moved to the
        Recycle Bin (never hard-deleted).
    Entries that are dirty, have unpushed commits, have stashes, host linked worktrees, are locked,
    or match -Exclude are never touched. Each removal re-checks the entry immediately beforehand.

    All gh calls run in a child process with GITHUB_TOKEN/GH_TOKEN stripped, so the keyring login is
    used even while a stale token is still set (lesson 8).

.EXAMPLE
    pwsh -File tools/workstation/Invoke-WorkspaceAudit.ps1
    # report only, default root, JSON in $env:TEMP

.EXAMPLE
    pwsh -File tools/workstation/Invoke-WorkspaceAudit.ps1 -Apply
    # remove clean, fully-landed linked worktrees (clones are only reported)
#>
[CmdletBinding()]
param(
    [string]   $Root           = 'C:\Users\gbonthuy\Documents\Codex\2026-10-19\upd\work',
    [double]   $PushAfterHours = 4,
    [string]   $ReportPath     = $env:TEMP,
    # Folder-name wildcards that are in use and must never be removed.
    [string[]] $Exclude        = @('wt-jade5', 'wt-lesson*'),
    # Folder-name wildcards for non-git residue (removed worktrees) to report as LEFTOVER.
    [string[]] $LeftoverPattern = @('wt-*', 'qa-tmp-*', 'ABACUS*', 'CODEX*'),
    [switch]   $Apply,
    [switch]   $AllowCloneDelete,
    [switch]   $SkipSize,
    [switch]   $SkipTokenCheck
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$now = [DateTimeOffset]::UtcNow
$tokenNames = 'GITHUB_TOKEN', 'GH_TOKEN'

# ---------------------------------------------------------------- helpers --
function G([string]$Dir) {
    # git with output as string[]; never throws, returns $null on failure.
    $out = & git.exe -C $Dir @args 2>$null
    if ($LASTEXITCODE -ne 0) { return $null }
    @($out)
}

function Invoke-Gh {
    <# Runs gh in a child process. Token variables are stripped from the child's environment,
       then -Env (name->value) is applied. The current process environment is never modified. #>
    param([string[]]$Arguments, [hashtable]$Env = @{}, [string]$WorkingDirectory = $PWD.Path)
    $psi = [System.Diagnostics.ProcessStartInfo]::new('gh')
    foreach ($a in $Arguments) { $psi.ArgumentList.Add($a) }
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.UseShellExecute = $false
    $psi.WorkingDirectory = $WorkingDirectory
    foreach ($n in $tokenNames) { [void]$psi.Environment.Remove($n) }
    foreach ($k in $Env.Keys) { $psi.Environment[$k] = $Env[$k] }
    try {
        $p = [System.Diagnostics.Process]::Start($psi)
        $errTask = $p.StandardError.ReadToEndAsync()
        $out = $p.StandardOutput.ReadToEnd()
        $p.WaitForExit()
        [pscustomobject]@{ ExitCode = $p.ExitCode; Out = $out.Trim(); Err = $errTask.Result.Trim() }
    }
    catch { [pscustomobject]@{ ExitCode = -1; Out = ''; Err = $_.Exception.Message } }
}

function Get-Slug([string]$Url) {
    # Same rule as Stack-Helper.ps1.
    if ($Url -match 'github\.com[:/]([^/]+)/([^/]+?)(\.git)?/?$') { "$($Matches[1])/$($Matches[2])".ToLower() }
}

function Get-DirSize([string]$Path) {
    # Skips reparse points (junctions/symlinks) so nothing is counted twice or outside the tree.
    $opt = [System.IO.EnumerationOptions]::new()
    $opt.RecurseSubdirectories = $true
    $opt.IgnoreInaccessible = $true
    $opt.AttributesToSkip = [System.IO.FileAttributes]::ReparsePoint
    $sum = 0L
    foreach ($f in [System.IO.DirectoryInfo]::new($Path).EnumerateFiles('*', $opt)) { $sum += $f.Length }
    $sum
}

function New-Entry([hashtable]$Fields) {
    # One shape for every row (StrictMode-safe; stable JSON schema).
    $e = [ordered]@{
        Name = ''; Path = ''; Kind = ''; MainRepo = $null; Repo = $null; Branch = ''; Head = $null; Upstream = $null
        Ahead = 0; Behind = 0; Unpushed = 0; Dirty = $false; LastCommitHours = -1; LastCommitAge = ''
        DefaultRef = $null; InDefault = $false; PR = ''; PRState = ''; PRError = $null; Locked = $false
        HostedWorktrees = 0; Stashes = 0; Excluded = $false; Class = 'KEEP'; Reason = ''; SizeBytes = 0L
    }
    foreach ($k in $Fields.Keys) { $e[$k] = $Fields[$k] }
    [pscustomobject]$e
}

function Format-Age([double]$Hours) {
    if ($Hours -lt 0) { return '' }
    if ($Hours -lt 1) { return '<1h' }
    if ($Hours -lt 48) { return '{0:N0}h' -f $Hours }
    '{0:N0}d' -f ($Hours / 24)
}

function Get-GitState([string]$Dir) {
    <# Everything the safety rules depend on; called again right before any removal. #>
    $st = [ordered]@{}
    $st.Branch = (G $Dir symbolic-ref -q --short HEAD) | Select-Object -First 1
    if (-not $st.Branch) { $st.Branch = '(detached)' }
    $st.Head = (G $Dir rev-parse HEAD) | Select-Object -First 1
    $st.Upstream = (G $Dir rev-parse --abbrev-ref --symbolic-full-name '@{u}') | Select-Object -First 1
    $st.Ahead = 0; $st.Behind = 0
    if ($st.Upstream) {
        $c = (G $Dir rev-list --left-right --count 'HEAD...@{u}') | Select-Object -First 1
        if ($c -match '^(\d+)\s+(\d+)$') { $st.Ahead = [int]$Matches[1]; $st.Behind = [int]$Matches[2] }
    }
    # Untracked files count as dirty (git worktree remove refuses them too); unreadable status counts as dirty.
    $porcelain = @(& git.exe -C $Dir status --porcelain --untracked-files=normal 2>$null | Where-Object { $_ })
    $st.Dirty = ($LASTEXITCODE -ne 0) -or ($porcelain.Count -gt 0)
    $st.DirtyFiles = $porcelain.Count
    # Commits on HEAD that no remote-tracking ref contains.
    $st.Unpushed = [int]((G $Dir rev-list --count HEAD --not --remotes) | Select-Object -First 1)
    $st.RemoteCheckedLive = $false
    if ($st.Unpushed -gt 0 -and $st.Branch -ne '(detached)') {
        # Single-branch clones (narrow fetch refspec) never get remote-tracking refs for pushed branches,
        # so ask the remote directly before calling the work unpushed.
        $remoteSha = ((G $Dir ls-remote origin "refs/heads/$($st.Branch)") | Select-Object -First 1) -replace '\s.*$', ''
        if ($remoteSha) {
            & git.exe -C $Dir merge-base --is-ancestor HEAD $remoteSha 2>$null
            if ($LASTEXITCODE -eq 0) { $st.Unpushed = 0; $st.RemoteCheckedLive = $true }
        }
    }
    $range = if ($st.Unpushed -gt 0) { @('HEAD', '--not', '--remotes') } elseif ($st.Ahead -gt 0) { @('@{u}..HEAD') } else { @() }
    $st.OldestUnpushedHours = -1
    if ($range) {
        $ts = G $Dir log --format=%ct @range
        if ($ts) {
            $min = ($ts | ForEach-Object { [long]$_ } | Measure-Object -Minimum).Minimum
            $st.OldestUnpushedHours = [math]::Round(($now - [DateTimeOffset]::FromUnixTimeSeconds($min)).TotalHours, 1) | ForEach-Object { [math]::Max(0, $_) }
        }
    }
    $ct = (G $Dir log -1 --format=%ct) | Select-Object -First 1
    $st.LastCommitHours = if ($ct) { [math]::Round(($now - [DateTimeOffset]::FromUnixTimeSeconds([long]$ct)).TotalHours, 1) | ForEach-Object { [math]::Max(0, $_) } } else { -1 }
    [pscustomobject]$st
}

# ------------------------------------------------------- 1. token check --
$token = [ordered]@{ Checked = $false; Findings = @(); KeyringLogin = $null; RemoveCommands = @() }
if (-not $SkipTokenCheck) {
    $token.Checked = $true
    $kr = Invoke-Gh -Arguments @('api', 'user', '--jq', '.login')
    $token.KeyringLogin = if ($kr.ExitCode -eq 0) { $kr.Out } else { "FAILED: $($kr.Err -split "`n" | Select-Object -First 1)" }
    foreach ($n in $tokenNames) {
        foreach ($scope in 'Process', 'User', 'Machine') {
            $v = [Environment]::GetEnvironmentVariable($n, [EnvironmentVariableTarget]::$scope)
            if (-not $v) { continue }
            # GH_TOKEN wins over GITHUB_TOKEN inside gh, so test every value through GH_TOKEN.
            $r = Invoke-Gh -Arguments @('api', 'user', '--jq', '.login') -Env @{ GH_TOKEN = $v }
            $ok = $r.ExitCode -eq 0
            $token.Findings += [pscustomobject]@{
                Name   = $n
                Scope  = $scope
                Prefix = if ($v.Length -ge 4) { $v.Substring(0, 4) + '...' } else { '...' }
                Valid  = $ok
                Login  = if ($ok) { $r.Out } else { $null }
                Error  = if ($ok) { $null } else { ($r.Err -split "`n" | Select-Object -First 1) }
            }
            if ($scope -ne 'Process') {
                $cmd = "[Environment]::SetEnvironmentVariable('$n', `$null, '$scope')"
                if ($scope -eq 'Machine') { $cmd += '   # needs an elevated shell' }
                $token.RemoveCommands += $cmd
            }
        }
    }
}

# ------------------------------------------- 2. inventory and classify --
if (-not (Test-Path -LiteralPath $Root)) { throw "Root not found: $Root" }
$Root = (Resolve-Path -LiteralPath $Root).ProviderPath
$entries = [System.Collections.Generic.List[object]]::new()
$prCache = @{}
$defaultCache = @{}

# @() keeps a one-folder root an array: under StrictMode a single object has no .Count (line below)
$dirs = @(Get-ChildItem -LiteralPath $Root -Directory -Force | Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName '.git') })
$i = 0
foreach ($d in $dirs) {
    $i++
    Write-Progress -Activity 'Workspace audit' -Status $d.Name -PercentComplete (100 * $i / [math]::Max(1, $dirs.Count))
    $path = $d.FullName
    $isWorktree = Test-Path -LiteralPath (Join-Path $path '.git') -PathType Leaf
    $commonDir = (G $path rev-parse --path-format=absolute --git-common-dir) | Select-Object -First 1
    if (-not $commonDir) {
        $entries.Add((New-Entry @{ Name = $d.Name; Path = $path; Kind = 'broken'; Dirty = $true; Reason = 'git cannot read this repo' }))
        continue
    }
    $mainRepo = Split-Path ([System.IO.Path]::GetFullPath($commonDir)) -Parent
    $st = Get-GitState $path
    $slug = Get-Slug ((G $path remote get-url origin) | Select-Object -First 1)

    # Default branch of origin (cached per main repo).
    if (-not $defaultCache.ContainsKey($mainRepo)) {
        $def = (G $path symbolic-ref -q --short refs/remotes/origin/HEAD) | Select-Object -First 1
        if (-not $def) { foreach ($c in 'origin/master', 'origin/main') { if (G $path rev-parse -q --verify "$c^{commit}") { $def = $c; break } } }
        $defaultCache[$mainRepo] = $def
    }
    $defaultRef = $defaultCache[$mainRepo]
    $inDefault = $false
    if ($defaultRef -and $st.Head) {
        & git.exe -C $path merge-base --is-ancestor $st.Head $defaultRef 2>$null
        $inDefault = $LASTEXITCODE -eq 0
    }

    # PR state for the branch.
    $prState = ''; $prNumbers = ''; $prError = $null
    $isDefaultBranch = $defaultRef -and ($st.Branch -eq ($defaultRef -replace '^origin/', ''))
    if ($slug -and $st.Branch -ne '(detached)' -and -not $isDefaultBranch) {
        $key = "$slug|$($st.Branch)"
        if (-not $prCache.ContainsKey($key)) {
            $ghArgs = @('pr', 'list', '-R', $slug, '--head', $st.Branch, '--state', 'all', '--json', 'number,state', '--limit', '20')
            $r = Invoke-Gh -Arguments $ghArgs
            if ($r.ExitCode -ne 0) { Start-Sleep -Seconds 2; $r = Invoke-Gh -Arguments $ghArgs }   # one retry: transient API errors
            $prCache[$key] = if ($r.ExitCode -eq 0 -and $r.Out) { , @($r.Out | ConvertFrom-Json) } else { ($r.Err -split "`n" | Select-Object -First 1) + " (exit $($r.ExitCode))" }
        }
        $prs = $prCache[$key]
        if ($prs -is [string]) { $prState = 'ERROR'; $prError = $prs }
        elseif ($prs.Count -eq 0) { $prState = 'NONE' }
        else {
            $prNumbers = ($prs | ForEach-Object { "#$($_.number)" }) -join ','
            $states = $prs.state
            $prState = if ($states -contains 'OPEN') { 'OPEN' } elseif ($states -contains 'MERGED') { 'MERGED' } else { 'CLOSED' }
        }
    }

    # Worktree / clone specifics.
    $locked = $false; $hostedWorktrees = 0; $stashes = 0; $otherUnpushed = 0
    if ($isWorktree) {
        $wl = G $mainRepo worktree list --porcelain
        $block = ($wl -join "`n") -split "`n`n" | Where-Object { $_ -match "(?m)^worktree (.+)$" -and ([System.IO.Path]::GetFullPath($Matches[1]) -eq [System.IO.Path]::GetFullPath($path)) }
        $locked = [bool]($block -match '(?m)^locked')
    }
    else {
        $hostedWorktrees = @((G $path worktree list --porcelain) | Where-Object { $_ -like 'worktree *' }).Count - 1
        $stashes = @(G $path stash list).Count
        # Commits on ANY local branch that are on no remote: deleting the clone would lose them.
        $otherUnpushed = [int]((G $path rev-list --count --branches --not --remotes) | Select-Object -First 1)
    }

    $excluded = [bool]($Exclude | Where-Object { $d.Name -like $_ })
    $landed = $inDefault -or $prState -in 'MERGED', 'CLOSED'
    $unpushed = $st.Unpushed -gt 0 -or $st.Ahead -gt 0
    $class = 'KEEP'; $reason = @()

    if ($unpushed -and $st.OldestUnpushedHours -ge $PushAfterHours) {
        $class = 'PUSH-ME'
        $reason += if (-not $st.Upstream) { "local-only branch, $($st.Unpushed) unpushed" } else { "ahead $($st.Ahead) of $($st.Upstream)" }
        $reason += "oldest unpushed $(Format-Age $st.OldestUnpushedHours)"
    }
    elseif ($unpushed) { $reason += "$([math]::Max($st.Unpushed, $st.Ahead)) unpushed commit(s), younger than $PushAfterHours h" }
    elseif ($st.Dirty) { $reason += "dirty ($($st.DirtyFiles) files)" }
    elseif (-not $landed) { $reason += if ($prState -eq 'OPEN') { "PR $prNumbers open" } else { 'not in default branch, no merged/closed PR' } }
    elseif ($excluded) { $reason += 'excluded (in use)' }
    elseif ($locked) { $reason += 'worktree is locked' }
    elseif (-not $isWorktree -and $hostedWorktrees -gt 0) { $reason += "main repo of $hostedWorktrees linked worktree(s)" }
    elseif (-not $isWorktree -and $stashes -gt 0) { $reason += "$stashes stash entries" }
    elseif (-not $isWorktree -and $otherUnpushed -gt 0) { $reason += "$otherUnpushed unpushed commits on other local branches" }
    else {
        $class = 'REMOVABLE'
        $reason += if ($prState -in 'MERGED', 'CLOSED') { "PR $prNumbers $($prState.ToLower())" } else { "fully in $defaultRef" }
    }
    if ($class -eq 'PUSH-ME' -and $st.Dirty) { $reason += 'also dirty' }

    $entries.Add((New-Entry @{
        Name            = $d.Name
        Path            = $path
        Kind            = if ($isWorktree) { 'worktree' } else { 'clone' }
        MainRepo        = $mainRepo
        Repo            = $slug
        Branch          = $st.Branch
        Head            = $st.Head
        Upstream        = $st.Upstream
        Ahead           = $st.Ahead
        Behind          = $st.Behind
        Unpushed        = $st.Unpushed
        Dirty           = $st.Dirty
        LastCommitHours = $st.LastCommitHours
        LastCommitAge   = Format-Age $st.LastCommitHours
        DefaultRef      = $defaultRef
        InDefault       = $inDefault
        PR              = $prNumbers
        PRState         = $prState
        PRError         = $prError
        Locked          = $locked
        HostedWorktrees = $hostedWorktrees
        Stashes         = $stashes
        Excluded        = $excluded
        Class           = $class
        Reason          = $reason -join '; '
        SizeBytes       = if ($SkipSize) { 0 } else { Get-DirSize $path }
    }))
}
Write-Progress -Activity 'Workspace audit' -Completed

# Residue of removed worktrees/clones: matching folders with no .git (often only .pytest_cache, or empty).
# Reported only; -Apply never deletes them.
foreach ($d in Get-ChildItem -LiteralPath $Root -Directory -Force | Where-Object { -not (Test-Path -LiteralPath (Join-Path $_.FullName '.git')) }) {
    if (-not ($LeftoverPattern | Where-Object { $d.Name -like $_ })) { continue }
    $top = try { @(Get-ChildItem -LiteralPath $d.FullName -Force -ErrorAction Stop | ForEach-Object Name) } catch { @('<access denied>') }
    $entries.Add((New-Entry @{
        Name = $d.Name; Path = $d.FullName; Kind = 'leftover'; Class = 'LEFTOVER'
        Reason = 'no .git; contains: ' + $(if ($top) { ($top | Select-Object -First 4) -join ', ' } else { '(empty)' })
        SizeBytes = if ($SkipSize) { 0L } else { Get-DirSize $d.FullName }
    }))
}

# Never offer the last copy of a repo: if every clone of a slug is REMOVABLE, keep the most recent one.
foreach ($grp in ($entries | Where-Object { $_.Kind -eq 'clone' -and $_.Repo } | Group-Object Repo)) {
    if (-not ($grp.Group | Where-Object Class -ne 'REMOVABLE')) {
        $keep = $grp.Group | Sort-Object LastCommitHours | Select-Object -First 1
        $keep.Class = 'KEEP'; $keep.Reason = "last clone of $($grp.Name) under root"
    }
}

# ------------------------------------------------------------- 3. disk --
$drive = Get-PSDrive -Name (Split-Path $Root -Qualifier).TrimEnd(':')
$removable = @($entries | Where-Object Class -eq 'REMOVABLE')
function ConvertTo-GB($Items) { $t = 0L; foreach ($x in @($Items)) { if ($x) { $t += $x.SizeBytes } }; [math]::Round($t / 1GB, 2) }
$disk = [pscustomobject]@{
    Drive              = "$($drive.Name):"
    FreeGB             = [math]::Round($drive.Free / 1GB, 2)
    ReclaimableGB      = ConvertTo-GB $removable
    ReclaimableWorktreeGB = ConvertTo-GB ($removable | Where-Object Kind -eq 'worktree')
    ReclaimableCloneGB = ConvertTo-GB ($removable | Where-Object Kind -eq 'clone')
    LeftoverGB         = ConvertTo-GB ($entries | Where-Object Class -eq 'LEFTOVER')
    SizesMeasured      = -not $SkipSize
}

# ------------------------------------------------------------ 4. apply --
$actions = [System.Collections.Generic.List[object]]::new()
if ($Apply) {
    $prune = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($e in $removable) {
        $fresh = Get-GitState $e.Path   # re-check: other sessions may have touched it since the scan
        if ($fresh.Dirty -or $fresh.Unpushed -gt 0 -or $fresh.Ahead -gt 0 -or $fresh.Head -ne $e.Head -or $fresh.Branch -ne $e.Branch) {
            $actions.Add([pscustomobject]@{ Name = $e.Name; Action = 'skipped'; Detail = 'changed since scan (dirty, unpushed or moved HEAD)' }); continue
        }
        if ($e.Kind -eq 'worktree') {
            $out = & git.exe -C $e.MainRepo worktree remove $e.Path 2>&1   # never --force
            $ok = $LASTEXITCODE -eq 0
            [void]$prune.Add($e.MainRepo)
            $actions.Add([pscustomobject]@{ Name = $e.Name; Action = if ($ok) { 'worktree removed' } else { 'failed' }; Detail = ($out -join ' ').Trim() })
        }
        elseif (-not $AllowCloneDelete) {
            $actions.Add([pscustomobject]@{ Name = $e.Name; Action = 'skipped'; Detail = 'clone: pass -AllowCloneDelete to recycle it' })
        }
        elseif (-not $IsWindows) {
            $actions.Add([pscustomobject]@{ Name = $e.Name; Action = 'skipped'; Detail = 'Recycle Bin only available on Windows' })
        }
        else {
            try {
                Add-Type -AssemblyName Microsoft.VisualBasic
                # AllDialogs: Windows asks before permanently deleting anything too large for the Recycle Bin.
                [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory($e.Path,
                    [Microsoft.VisualBasic.FileIO.UIOption]::AllDialogs,
                    [Microsoft.VisualBasic.FileIO.RecycleOption]::SendToRecycleBin)
                $actions.Add([pscustomobject]@{ Name = $e.Name; Action = 'clone recycled'; Detail = 'moved to Recycle Bin (empty it to free the space)' })
            }
            catch { $actions.Add([pscustomobject]@{ Name = $e.Name; Action = 'failed'; Detail = $_.Exception.Message }) }
        }
    }
    foreach ($m in ($entries | Where-Object { $_.MainRepo } | ForEach-Object MainRepo | Sort-Object -Unique)) { [void]$prune.Add($m) }
    foreach ($m in $prune) {
        if (Test-Path -LiteralPath $m) {
            & git.exe -C $m worktree prune 2>$null
            $actions.Add([pscustomobject]@{ Name = (Split-Path $m -Leaf); Action = 'worktree prune'; Detail = $m })
        }
    }
}

# ----------------------------------------------------------- 5. output --
$summary = [ordered]@{
    Entries   = $entries.Count
    Removable = $removable.Count
    PushMe    = @($entries | Where-Object Class -eq 'PUSH-ME').Count
    Keep      = @($entries | Where-Object Class -eq 'KEEP').Count
    Leftover  = @($entries | Where-Object Class -eq 'LEFTOVER').Count
}
$report = [ordered]@{
    GeneratedUtc   = $now.ToString('o')
    Computer       = $env:COMPUTERNAME
    Root           = $Root
    Mode           = if ($Apply) { if ($AllowCloneDelete) { 'apply+clones' } else { 'apply' } } else { 'report-only' }
    PushAfterHours = $PushAfterHours
    Exclude        = $Exclude
    Summary        = $summary
    Disk           = $disk
    Token          = $token
    Entries        = $entries
    Actions        = $actions
}
New-Item -ItemType Directory -Force -Path $ReportPath | Out-Null
$jsonPath = Join-Path $ReportPath ("workspace-audit-{0:yyyyMMdd-HHmmss}.json" -f [DateTime]::Now)
$report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $jsonPath -Encoding utf8

Write-Host "`n== Token check (lesson 8) ==" -ForegroundColor Cyan
if (-not $token.Checked) { Write-Host 'skipped' }
else {
    Write-Host "gh keyring login (tokens stripped): $($token.KeyringLogin)"
    if (-not $token.Findings) { Write-Host 'No GITHUB_TOKEN/GH_TOKEN set at any scope. Good.' -ForegroundColor Green }
    else {
        $token.Findings | Format-Table Name, Scope, Prefix, Valid, Login, Error -AutoSize | Out-String -Width 200 | Write-Host
        if ($token.Findings | Where-Object { -not $_.Valid }) {
            Write-Host 'A stale token overrides the gh keyring login and causes 401s.' -ForegroundColor Yellow
        }
        if ($token.RemoveCommands) {
            Write-Host 'To remove it (run yourself, then open a new shell; this script never does):' -ForegroundColor Yellow
            $token.RemoveCommands | ForEach-Object { Write-Host "  $_" }
        }
        if ($token.Findings | Where-Object Scope -eq 'Process') { Write-Host '  # this shell only: Remove-Item Env:GITHUB_TOKEN, Env:GH_TOKEN -ErrorAction SilentlyContinue' }
    }
}

Write-Host "`n== Repos and worktrees under $Root (lessons 5, 9) ==" -ForegroundColor Cyan
$entries | Sort-Object @{ e = { @{ 'PUSH-ME' = 0; 'REMOVABLE' = 1; 'LEFTOVER' = 2; 'KEEP' = 3 }[$_.Class] } }, Name |
    Format-Table Class, Name, Kind, Branch, @{ n = 'Ahd'; e = 'Ahead' }, @{ n = 'Bhd'; e = 'Behind' },
        @{ n = 'Dirty'; e = { if ($_.Dirty) { 'yes' } else { '' } } }, @{ n = 'Age'; e = 'LastCommitAge' },
        PRState, @{ n = 'SizeMB'; e = { [long][math]::Round($_.SizeBytes / 1MB) }; a = 'right' }, Reason -AutoSize |
    Out-String -Width 260 | Write-Host

Write-Host '== Disk ==' -ForegroundColor Cyan
Write-Host ("{0} free {1} GB; reclaimable {2} GB ({3} GB worktrees, {4} GB clones){5}" -f $disk.Drive, $disk.FreeGB,
    $disk.ReclaimableGB, $disk.ReclaimableWorktreeGB, $disk.ReclaimableCloneGB, $(if ($SkipSize) { ' [sizes skipped]' } else { '' }))
Write-Host ("{0} entries: {1} REMOVABLE, {2} PUSH-ME, {3} KEEP, {4} LEFTOVER ({5} GB, delete by hand)" -f $summary.Entries, $summary.Removable,
    $summary.PushMe, $summary.Keep, $summary.Leftover, $disk.LeftoverGB)
if ($actions.Count) { $actions | Format-Table -AutoSize | Out-String -Width 200 | Write-Host }
elseif (-not $Apply) { Write-Host 'Report only. Re-run with -Apply to remove REMOVABLE worktrees (clones also need -AllowCloneDelete).' }
Write-Host "JSON report: $jsonPath"
