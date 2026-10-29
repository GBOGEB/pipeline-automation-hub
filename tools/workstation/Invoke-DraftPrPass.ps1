#Requires -Version 7.0
<#
.SYNOPSIS
    Light pass over open draft PRs: conflicts, red checks, unresolved bot review threads and live sessions.

.DESCRIPTION
    Draft PRs that were pulled back from review pile up with merge conflicts, red gates and
    unresolved Codex / Copilot / CodeQL threads. This script turns the manual pass into one report:

      * every open draft PR of -Owner (or of -Repo only), with mergeable state and failing checks;
      * every unresolved review thread, with its priority badge (P0-P3), author, outdated flag and
        whether it reads as a security finding;
      * whether another session is LIVE on the PR's branch: a local worktree on that branch with
        uncommitted changes, or with a reflog entry younger than -LiveMinutes (lesson: one session
        per worktree; a second session duplicates the fix and its push is rejected).

    Each PR gets one class, in this order:
      LIVE      another session is working the branch. Leave it to that session.
      THREAD-P1 unresolved P0/P1 or security thread on the current head. Fix first.
      CONFLICT  merge conflict with the base branch. Merge the base in, re-run the regen entrypoint.
      RED       failing checks only. Open the first red job.
      OUTDATED  only outdated threads remain. Verify each against the head, reply with the fixing SHA, resolve.
      THREAD    unresolved P2/P3 threads on the current head.
      PENDING   nothing open, but checks are still queued or running. Wait for them.
      CLEAN     nothing open and every check completed. Write the FPC receipt before it leaves draft.

    Read-only. It never pushes, comments, resolves threads or changes a PR.
    All gh calls run in a child process with GITHUB_TOKEN/GH_TOKEN stripped, so the keyring login is
    used even while a stale token is still set (lesson 8).

.EXAMPLE
    pwsh -NoProfile -File tools/workstation/Invoke-DraftPrPass.ps1
    # all open drafts of GBOGEB, table + JSON in $env:TEMP

.EXAMPLE
    pwsh -NoProfile -File tools/workstation/Invoke-DraftPrPass.ps1 -Repo pipeline-automation-hub -IncludeReady -ShowThreads
    # one repo, ready PRs too, list every open thread under its PR
#>
[CmdletBinding()]
param(
    [string]   $Owner        = 'GBOGEB',
    # Repository names under -Owner. Empty: every repo that has an open draft PR.
    [string[]] $Repo         = @(),
    [switch]   $IncludeReady,
    # Main repos whose `git worktree list` is searched for live sessions on a PR branch.
    [string[]] $MainRepo     = @('C:\Users\gbonthuy\Documents\Codex\2026-10-23\pah-devops-n9',
                                 'C:\Users\gbonthuy\ABACUS', 'C:\Users\gbonthuy\cryoplant-project'),
    [double]   $LiveMinutes  = 30,
    [string]   $ReportPath   = $env:TEMP,
    [switch]   $ShowThreads,
    # Run the offline checks of the security rule and exit. No gh calls, no installs.
    [switch]   $SelfTest
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$now = [DateTimeOffset]::UtcNow
$tokenNames = 'GITHUB_TOKEN', 'GH_TOKEN'
# Security words. "token" alone is not one (token census, tokenise); it counts only next to leak/exposure words.
$securityPattern = 'secur|inject|secret|credential|poison|traversal|XSS|untrusted|privilege|CodeQL|ReDoS|backtracking'
$tokenLeakPattern = 'token.{0,40}(leak|expos|secret|credential|hardcod)|(leak|expos|hardcod)\w*.{0,40}token'
$classOrder = 'LIVE', 'THREAD-P1', 'CONFLICT', 'RED', 'OUTDATED', 'THREAD', 'PENDING', 'CLEAN'

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

function Get-Priority([string]$Body) {
    # Codex badges read "![P1 Badge]"; CodeQL alerts carry no badge and are security by author.
    if ($Body -match '!\[(P[0-3])\b') { return $Matches[1] }
    '--'
}

function Test-SecurityThread([string]$Login, [string]$Body) {
    <# Security when CodeQL raised it, when a P0/P1 badge names a security word, or when the body names a
       token leak. A P2/P3 that only says "token" or "untrusted" in passing stays out of THREAD-P1. #>
    if ($Login -eq 'github-advanced-security') { return $true }
    if ($Body -match $tokenLeakPattern) { return $true }
    ((Get-Priority $Body) -in 'P0', 'P1') -and ($Body -match $securityPattern)
}

function Get-Title([string]$Body) {
    $t = ($Body -replace '</?sub>', '' -replace '!\[[^\]]*\]\([^)]*\)', '' -replace '[*#]', '').Trim()
    (($t -split "`n")[0]).Trim()
}

function Get-Slug([string]$Url) {
    # Same rule as Invoke-WorkspaceAudit.ps1.
    if ($Url -match 'github\.com[:/]([^/]+)/([^/]+?)(\.git)?/?$') { "$($Matches[1])/$($Matches[2])".ToLower() }
}

function Get-LiveWorktrees {
    <# Map "owner/repo|branch" -> worktrees that look live (dirty, or reflog younger than -LiveMinutes).
       Keyed by repository too, so a same-named branch in another repo is never marked LIVE. #>
    $live = @{}
    foreach ($main in $MainRepo) {
        if (-not (Test-Path -LiteralPath $main)) { continue }
        $slug = Get-Slug ((& git.exe -C $main remote get-url origin 2>$null) | Select-Object -First 1)
        if (-not $slug) { continue }
        $path = $null
        foreach ($line in @(& git.exe -C $main worktree list --porcelain 2>$null)) {
            if ($line -like 'worktree *') { $path = $line.Substring(9); continue }
            if ($line -notlike 'branch refs/heads/*' -or -not $path -or -not (Test-Path -LiteralPath $path)) { continue }
            $branch = "$slug|$($line.Substring(18))"
            $dirty = @(& git.exe -C $path status --porcelain --untracked-files=normal 2>$null | Where-Object { $_ }).Count
            $last = (& git.exe -C $path reflog -1 --format=%ct 2>$null) | Select-Object -First 1
            $ageMin = if ($last) { ($now - [DateTimeOffset]::FromUnixTimeSeconds([long]$last)).TotalMinutes } else { [double]::MaxValue }
            if ($dirty -gt 0 -or $ageMin -lt $LiveMinutes) {
                if (-not $live.ContainsKey($branch)) { $live[$branch] = [System.Collections.Generic.List[object]]::new() }
                $live[$branch].Add([pscustomobject]@{ Path = $path; Dirty = $dirty; ReflogMinutes = [math]::Round($ageMin) })
            }
        }
    }
    $live
}

$threadQuery = @'
query($o:String!,$r:String!,$n:Int!,$after:String){repository(owner:$o,name:$r){pullRequest(number:$n){
  reviewThreads(first:100,after:$after){pageInfo{hasNextPage endCursor}
    nodes{id isResolved isOutdated path line comments(first:1){nodes{author{login} body url}}}}}}}
'@

function Get-ReviewThreads([string]$Owner, [string]$Name, [int]$Number) {
    <# Every review thread, page by page: a P1 past the first 100 must still be counted. #>
    $all = [System.Collections.Generic.List[object]]::new()
    $after = $null
    do {
        $ghArgs = @('api', 'graphql', '-f', "query=$threadQuery", '-F', "o=$Owner", '-F', "r=$Name", '-F', "n=$Number")
        if ($after) { $ghArgs += @('-f', "after=$after") }
        $conn = (Get-GhJson $ghArgs).data.repository.pullRequest.reviewThreads
        foreach ($node in @($conn.nodes)) { $all.Add($node) }
        $after = $conn.pageInfo.endCursor
    } while ($conn.pageInfo.hasNextPage)
    $all
}

if ($SelfTest) {
    $cases = @(
        @{ Login = 'chatgpt-codex-connector'; Body = '![P2 Badge] Count the token census once per snapshot'; Want = $false }
        @{ Login = 'chatgpt-codex-connector'; Body = '![P2 Badge] tokenise the body before matching'; Want = $false }
        @{ Login = 'chatgpt-codex-connector'; Body = '![P1 Badge] The leaked token is printed to the job log'; Want = $true }
        @{ Login = 'chatgpt-codex-connector'; Body = '![P2 Badge] GITHUB_TOKEN is exposed in the artifact'; Want = $true }
        @{ Login = 'chatgpt-codex-connector'; Body = '![P1 Badge] Path traversal in the report path'; Want = $true }
        @{ Login = 'chatgpt-codex-connector'; Body = '![P1 Badge] Off-by-one in the page loop'; Want = $false }
        @{ Login = 'github-advanced-security'; Body = 'Checkout of untrusted code in a privileged context'; Want = $true }
    )
    $bad = @($cases | Where-Object { (Test-SecurityThread $_.Login $_.Body) -ne $_.Want })
    foreach ($b in $bad) { Write-Host "FAIL want=$($b.Want): $($b.Login) :: $($b.Body)" }
    Write-Host ("SELFTEST {0}/{1} passed" -f ($cases.Count - $bad.Count), $cases.Count)
    exit [int][bool]$bad.Count
}

# ------------------------------------------------------------------ scan --
$state = @(if (-not $IncludeReady) { '--draft' })
$repos = @(if ($Repo.Count) { $Repo | ForEach-Object { "$Owner/$_" } } else {
    @((Get-GhJson (@('search', 'prs', '--owner', $Owner, '--state', 'open', '--limit', '200', '--json', 'repository') + $state)) |
        ForEach-Object { $_.repository.nameWithOwner } | Sort-Object -Unique)
})
$live = Get-LiveWorktrees
$rows = [System.Collections.Generic.List[object]]::new()

foreach ($slug in $repos) {
    $prs = Get-GhJson @('pr', 'list', '-R', $slug, '--state', 'open', '--limit', '200', '--json',
        'number,title,isDraft,headRefName,headRefOid,mergeable,updatedAt,url,statusCheckRollup')
    foreach ($pr in @($prs | Where-Object { $IncludeReady -or $_.isDraft })) {
        $owner, $name = $slug -split '/'
        $threads = @(Get-ReviewThreads $owner $name $pr.number | Where-Object { -not $_.isResolved } | ForEach-Object {
            $c = $_.comments.nodes[0]
            $login = if ($c.author) { $c.author.login } else { 'ghost' }
            $pri = Get-Priority $c.body
            [pscustomobject]@{
                Id = $_.id; Priority = $pri; Author = $login; Outdated = [bool]$_.isOutdated
                Security = Test-SecurityThread $login $c.body
                Where = "$($_.path):$($_.line)"; Title = Get-Title $c.body; Url = $c.url
            } })
        $failing = @($pr.statusCheckRollup | Where-Object {
                ($_.PSObject.Properties['conclusion'] -and $_.conclusion -in 'FAILURE', 'TIMED_OUT', 'CANCELLED', 'ACTION_REQUIRED', 'STARTUP_FAILURE') -or
                ($_.PSObject.Properties['state'] -and $_.state -in 'FAILURE', 'ERROR') } |
            ForEach-Object { if ($_.PSObject.Properties['name']) { $_.name } else { $_.context } } | Sort-Object -Unique)
        # A CheckRun that has not completed has an empty conclusion; a StatusContext reports PENDING/EXPECTED.
        $pending = @($pr.statusCheckRollup | Where-Object {
                ($_.PSObject.Properties['status'] -and $_.status -and $_.status -ne 'COMPLETED') -or
                ($_.PSObject.Properties['state'] -and $_.state -in 'PENDING', 'EXPECTED') }).Count
        $current = @($threads | Where-Object { -not $_.Outdated })
        $urgent = @($current | Where-Object { $_.Priority -in 'P0', 'P1' -or $_.Security })
        $liveKey = "$($slug.ToLower())|$($pr.headRefName)"
        $liveHere = @(if ($live.ContainsKey($liveKey)) { $live[$liveKey] })
        $class = if ($liveHere.Count) { 'LIVE' }
                 elseif ($urgent.Count) { 'THREAD-P1' }
                 elseif ($pr.mergeable -eq 'CONFLICTING') { 'CONFLICT' }
                 elseif ($failing.Count) { 'RED' }
                 elseif ($threads.Count -and -not $current.Count) { 'OUTDATED' }
                 elseif ($threads.Count) { 'THREAD' }
                 elseif ($pending) { 'PENDING' }
                 else { 'CLEAN' }
        $rows.Add([pscustomobject]@{
            PR = "$name#$($pr.number)"; Class = $class; Draft = $pr.isDraft; Mergeable = $pr.mergeable
            Red = $failing.Count; Pending = $pending; FirstRed = ($failing | Select-Object -First 1); Open = $threads.Count; P1 = $urgent.Count; Outdated = @($threads | Where-Object Outdated).Count
            UpdatedHours = [math]::Round(($now - [DateTimeOffset]::Parse($pr.updatedAt)).TotalHours, 1)
            Branch = $pr.headRefName; Head = $pr.headRefOid.Substring(0, 8); Url = $pr.url; Title = $pr.title
            FailingChecks = $failing; Threads = $threads; LiveWorktrees = $liveHere
        })
    }
}

# ---------------------------------------------------------------- report --
$sorted = @($rows | Sort-Object { [array]::IndexOf($classOrder, $_.Class) }, PR)
$sorted | Format-Table PR, Class, Mergeable, Red, FirstRed, Open, P1, Outdated, UpdatedHours -AutoSize | Out-Host
if ($ShowThreads) {
    foreach ($r in $sorted | Where-Object Open) {
        Write-Host "$($r.PR)  [$($r.Class)]  $($r.Url)"
        foreach ($th in $r.Threads) {
            $flag = if ($th.Security) { ' SEC' } else { '' }
            $old = if ($th.Outdated) { ' outdated' } else { '' }
            Write-Host ("   [{0}{1}{2}] {3} {4} :: {5}" -f $th.Priority, $flag, $old, $th.Author, $th.Where, $th.Title)
        }
    }
}
foreach ($r in $sorted | Where-Object Class -eq 'LIVE') {
    foreach ($w in $r.LiveWorktrees) { Write-Host "LIVE $($r.PR): $($w.Path) (dirty=$($w.Dirty), reflog $($w.ReflogMinutes) min ago). Leave it to that session." }
}
$summary = $sorted | Group-Object Class | ForEach-Object { "$($_.Name)=$($_.Count)" }
Write-Host ("DRAFT_PR_PASS {0} PRs: {1}" -f $sorted.Count, ($summary -join ' '))

$file = Join-Path $ReportPath ("draft-pr-pass-{0:yyyyMMdd-HHmmss}.json" -f $now.LocalDateTime)
[ordered]@{ schema = 'workstation.draft_pr_pass.v1'; generated_at = $now.ToString('o'); owner = $Owner
    live_minutes = $LiveMinutes; read_only = $true; prs = $sorted } |
    ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $file -Encoding utf8NoBOM
Write-Host "Report: $file"
