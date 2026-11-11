#Requires -Version 7.0
<#
.SYNOPSIS
  Remove merged branches across all of an owner's GitHub repos and local clones. Lossless only.

.DESCRIPTION
  Dry run by default. Pass -Execute to delete.

  Remote: lists every branch of every non-archived repo and hands the list to the one owner of the
  delete decision, pipeline-automation-hub scripts/branch_hygiene_delete.py (read from origin/master,
  blob OID recorded). That script deletes a branch only if its head is unchanged, it is not default
  or protected, no open PR uses it, and it is fully merged into default or is a merged PR's exact head
  (kept reachable via refs/pull/N/head). Everything else is skipped with a reason.

  Local: in each clone whose origin is github.com/<Owner>/..., after `git fetch --prune`, a branch is
  deleted only if its tip is an ancestor of origin/<default> or equals a merged PR's head SHA. Never
  the default branch, never a branch checked out in any worktree. Deletion uses
  `git update-ref -d <ref> <sha>`, so a branch that moved since the check is kept.

  Every run writes receipts with a restore command per deleted branch.

  See tools/workstation/README.md, section "Branch hygiene across repos".

.EXAMPLE
  pwsh -NoProfile -File tools\workstation\Invoke-BranchHygiene.ps1                              # dry run, all repos
.EXAMPLE
  pwsh -NoProfile -File tools\workstation\Invoke-BranchHygiene.ps1 -Repo GBOGEB/GEMINI -Execute # one repo, for real
#>
[CmdletBinding()]
param(
    [string]   $Owner         = 'GBOGEB',
    [string[]] $Repo          = @(),                       # nameWithOwner filter; empty = all
    [ValidateSet('Both', 'Remote', 'Local')]
    [string]   $Scope         = 'Both',
    [string[]] $LocalRoots    = @('C:\repos', 'C:\repos\_wt', 'C:\DEV\REPOS'),
    [int]      $MinAgeDays    = 2,                         # never touch a branch with a newer tip
    [string[]] $Exclude       = @('release/*', 'releases/*', 'gh-pages', 'develop', 'staging', 'production'),
    [switch]   $IncludeForks,
    [string]   $PahRepo       = (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent),   # the PAH checkout holding this script
    [string]   $ReceiptDir    = (Join-Path $env:LOCALAPPDATA ('branch-hygiene\' + (Get-Date -Format 'yyyyMMdd-HHmmss'))),
    [switch]   $Execute
)
$ErrorActionPreference = 'Stop'
$mode    = if ($Execute) { 'EXECUTE' } else { 'DRY RUN' }
$cutoff  = [DateTimeOffset]::UtcNow.AddDays(-$MinAgeDays)
$utf8    = [Text.UTF8Encoding]::new($false)
New-Item -ItemType Directory -Force -Path $ReceiptDir | Out-Null
Write-Host "Branch hygiene [$mode]  owner=$Owner scope=$Scope minAge=${MinAgeDays}d  receipts: $ReceiptDir"

function Test-Excluded([string] $name) { foreach ($p in $Exclude) { if ($name -like $p) { return $true } } $false }

# A dead GITHUB_TOKEN from an old shell breaks gh; use the keyring login only. The caller's values
# are put back in the final block, so running this with & leaves the calling shell unchanged.
$savedEnv = @{ GITHUB_TOKEN = $env:GITHUB_TOKEN; GH_TOKEN = $env:GH_TOKEN }
try {
Remove-Item Env:GITHUB_TOKEN, Env:GH_TOKEN -ErrorAction SilentlyContinue
gh auth status *> $null
if ($LASTEXITCODE) { throw 'gh is not signed in (run: gh auth login)' }

# ---- repo inventory -------------------------------------------------------------------------
function Invoke-Gh {   # gh with 3 tries; throws instead of returning partial output (GitHub 5xx happens)
    for ($i = 1; ; $i++) {
        $out = gh @args
        if ($LASTEXITCODE -eq 0) { return $out }
        if ($i -ge 3) { throw "gh $($args -join ' ') failed (exit $LASTEXITCODE)" }
        Start-Sleep -Seconds (5 * $i)
    }
}
$repos = Invoke-Gh repo list $Owner --limit 1000 --no-archived --json 'nameWithOwner,defaultBranchRef,isFork' | ConvertFrom-Json
if (-not $repos) { throw "gh returned no repos for $Owner" }
if (-not $IncludeForks) { $repos = $repos | Where-Object { -not $_.isFork } }
if ($Repo) { $repos = $repos | Where-Object { $_.nameWithOwner -in $Repo } }
$byName = @{}; foreach ($r in $repos) { $byName[$r.nameWithOwner.ToLower()] = $r }
Write-Host ("{0} repo(s) in scope" -f $byName.Count)

$mergedHeads = @{}   # nameWithOwner -> HashSet of merged PR head SHAs (lazy)
function Get-MergedHeads([string] $nwo) {
    if (-not $mergedHeads.ContainsKey($nwo)) {
        $set = [Collections.Generic.HashSet[string]]::new()
        Invoke-Gh pr list -R $nwo --state merged --limit 5000 --json 'headRefOid' --jq '.[].headRefOid' | ForEach-Object { [void]$set.Add($_) }
        $mergedHeads[$nwo] = $set
    }
    $mergedHeads[$nwo]
}

$summary = [Collections.Generic.List[object]]::new()

# ---- remote ---------------------------------------------------------------------------------
if ($Scope -in 'Both', 'Remote') {
    if (-not (Test-Path $PahRepo)) { throw "PAH clone not found at $PahRepo (pass -PahRepo)" }
    git -C $PahRepo fetch -q origin master
    $toolOid = git -C $PahRepo rev-parse 'origin/master:scripts/branch_hygiene_delete.py'
    if ($LASTEXITCODE) { throw 'scripts/branch_hygiene_delete.py not on PAH origin/master' }
    $tool = Join-Path $ReceiptDir "branch_hygiene_delete.$($toolOid.Substring(0,8)).py"
    [IO.File]::WriteAllText($tool, ((git -C $PahRepo cat-file -p $toolOid) -join "`n") + "`n", $utf8)
    Write-Host "remote decision owner: PAH scripts/branch_hygiene_delete.py blob $toolOid"

    $query = 'query($owner:String!,$name:String!,$prefix:String!,$endCursor:String){repository(owner:$owner,name:$name){refs(refPrefix:$prefix,first:100,after:$endCursor){pageInfo{hasNextPage endCursor} nodes{name target{oid ... on Commit{committedDate}}}}}}'
    $jq    = '.data.repository.refs.nodes[] | [.name, .target.oid, (.target.committedDate // "")] | @tsv'
    $env:GITHUB_TOKEN = gh auth token          # child process only; removed in finally, never printed
    try {
        foreach ($r in $byName.Values | Sort-Object nameWithOwner) {
            $nwo = $r.nameWithOwner; $default = $r.defaultBranchRef.name
            $o, $n = $nwo.Split('/')
            $rows = foreach ($line in (Invoke-Gh api graphql --paginate -f query=$query -f owner=$o -f name=$n -f prefix='refs/heads/' --jq $jq)) {
                $name, $sha, $date = $line.Split("`t")
                if ($name -eq $default -or (Test-Excluded $name)) { continue }
                if ($date -and [DateTimeOffset]::Parse($date, [Globalization.CultureInfo]::InvariantCulture) -gt $cutoff) { continue }
                "$name`t$sha`tdelete"
            }
            if (-not $rows) { continue }
            $slug = $nwo.Replace('/', '__')
            $list = Join-Path $ReceiptDir "$slug.remote.tsv"; $rcpt = Join-Path $ReceiptDir "$slug.remote.json"
            [IO.File]::WriteAllText($list, ($rows -join "`n") + "`n", $utf8)
            $pyArgs = @($tool, $list, '--repo', $nwo, '--receipt', $rcpt); if ($Execute) { $pyArgs += '--execute' }
            python $pyArgs > $null
            $rc = $LASTEXITCODE
            if (Test-Path $rcpt) {
                $j = Get-Content $rcpt -Raw | ConvertFrom-Json
                $summary.Add([pscustomobject]@{ Side = 'remote'; Repo = $nwo; Listed = $j.listed; Lossless = $j.eligible; Deleted = $j.deleted; Skipped = $j.skipped; Errors = $j.errors })
            } else {
                $summary.Add([pscustomobject]@{ Side = 'remote'; Repo = $nwo; Listed = @($rows).Count; Lossless = 0; Deleted = 0; Skipped = 0; Errors = "exit $rc" })
            }
        }
    } finally { Remove-Item Env:GITHUB_TOKEN -ErrorAction SilentlyContinue }
}

# ---- local ----------------------------------------------------------------------------------
if ($Scope -in 'Both', 'Local') {
    $clones = foreach ($root in $LocalRoots) {
        if (Test-Path $root) { Get-ChildItem -LiteralPath $root -Directory | Where-Object { Test-Path (Join-Path $_.FullName '.git') -PathType Container } }
    }
    foreach ($c in $clones | Sort-Object FullName -Unique) {
        $path = $c.FullName
        $url  = git -C $path remote get-url origin 2>$null
        if ($url -notmatch "github\.com[:/]+([^/]+/[^/]+?)(\.git)?/?$") { continue }
        $r = $byName[$Matches[1].ToLower()]; if (-not $r) { continue }
        $nwo = $r.nameWithOwner; $default = $r.defaultBranchRef.name
        git -C $path fetch -q --prune origin 2>$null
        if ($LASTEXITCODE) { $summary.Add([pscustomobject]@{ Side = 'local'; Repo = $path; Listed = 0; Lossless = 0; Deleted = 0; Skipped = 0; Errors = 'fetch failed' }); continue }

        $checkedOut = @(git -C $path worktree list --porcelain | Where-Object { $_ -like 'branch refs/heads/*' } | ForEach-Object { $_.Substring(7) })
        $results = foreach ($line in (git -C $path for-each-ref refs/heads --format='%(refname)%09%(objectname)%09%(committerdate:unix)')) {
            $ref, $sha, $unix = $line.Split("`t"); $name = $ref.Substring(11)
            $row = [ordered]@{ branch = $name; sha = $sha }
            if ($name -eq $default -or (Test-Excluded $name)) { continue }
            if ($ref -in $checkedOut)                         { $row.action = 'skip'; $row.reason = 'checked_out_in_worktree'; [pscustomobject]$row; continue }
            if ([DateTimeOffset]::FromUnixTimeSeconds([long]$unix) -gt $cutoff) { $row.action = 'skip'; $row.reason = 'younger_than_min_age'; [pscustomobject]$row; continue }
            git -C $path merge-base --is-ancestor $sha "refs/remotes/origin/$default" 2>$null
            if ($LASTEXITCODE -eq 0)                          { $row.proof = 'ancestor_of_default' }
            elseif ((Get-MergedHeads $nwo).Contains($sha))    { $row.proof = 'merged_pull_request_head' }
            else                                              { $row.action = 'skip'; $row.reason = 'not_proven_merged'; [pscustomobject]$row; continue }
            $row.action = 'delete'; $row.deleted = $false
            $row.restore = "git -C `"$path`" branch `"$name`" $sha"
            if ($Execute) { git -C $path update-ref -d $ref $sha; $row.deleted = ($LASTEXITCODE -eq 0) }
            [pscustomobject]$row
        }
        $results = @($results)
        if (-not $results) { continue }
        $rcpt = Join-Path $ReceiptDir ("{0}.local.json" -f ($path -replace '[:\\]+', '_'))
        [IO.File]::WriteAllText($rcpt, ([ordered]@{ schema = 'branch-hygiene-local-receipt/v1'; clone = $path; repository = $nwo; default_branch = $default; mode = $mode; results = $results } | ConvertTo-Json -Depth 5), $utf8)
        $summary.Add([pscustomobject]@{ Side = 'local'; Repo = $path; Listed = $results.Count
            Lossless = @($results | Where-Object action -eq 'delete').Count; Deleted = @($results | Where-Object deleted).Count
            Skipped = @($results | Where-Object action -eq 'skip').Count; Errors = 0 })
    }
}

$summary | Format-Table -AutoSize
$summary | Export-Csv -NoTypeInformation -Path (Join-Path $ReceiptDir 'SUMMARY.csv')
Write-Host "[$mode] lossless candidates: $(($summary | Measure-Object Lossless -Sum).Sum)  deleted: $(($summary | Measure-Object Deleted -Sum).Sum)  receipts: $ReceiptDir"
if (-not $Execute) { Write-Host 'Dry run: nothing deleted. Re-run with -Execute to delete.' }
} finally {
    foreach ($k in $savedEnv.Keys) {
        if ($null -eq $savedEnv[$k]) { Remove-Item "Env:$k" -ErrorAction SilentlyContinue }
        else { Set-Item "Env:$k" $savedEnv[$k] }
    }
}
