<#
.SYNOPSIS
  Build the JADE focus-five handover binaries locally (read-only against GitHub).

.DESCRIPTION
  For the six repositories of the JADE focus-five slice this script writes, under
  <OutDir>\JADE5_HANDOVER_20261102:

    bundles\<repo>.bundle            lossless git bundle of every ref (git bundle create --all), verified
    archives\<repo>-<sha12>.zip      source tree at the pinned head (git archive)
    worktrees\<repo>                 detached worktree at the pinned head (CODEX and hub sparse)
    trace\<repo>\pr-<n>\*.json       REST snapshot of every session PR: pr, files, reviews,
                                     review comments, issue comments, check runs of the head
    repro\                           pulse reproduction (focus5_pulse.py), JADE suite and regen logs
    SHA256SUMS.txt, HANDOVER_INDEX.json, and JADE5_HANDOVER_20261102.zip (everything except
    mirrors\ and worktrees\)

  Nothing is pushed, merged or changed on GitHub. The private repository
  (cryoplant-project) is processed only with -IncludePrivate, and its outputs stay local.

.PARAMETER OutDir
  Parent folder. Default C:\Downloads (created if missing).
.PARAMETER IncludePrivate
  Also process GBOGEB/cryoplant-project (needs your GitHub access to it).
.PARAMETER Live
  Use each repo's current default-branch head instead of the pinned handover SHA.
.PARAMETER SkipTests
  Skip the reproduction step (pulse, JADE suite, regen check).
.PARAMETER DryRun
  Print every step without running git, gh or python.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\Build-JadeHandover.ps1
.EXAMPLE
  pwsh -File .\Build-JadeHandover.ps1 -OutDir D:\handover -IncludePrivate -Live

.NOTES
  Session https://claude.ai/code/session_017Fwrzak5ZCpiKxEJjfHrRW. Written for Windows
  PowerShell 5.1 and PowerShell 7. Prints ASCII only (cp1252 console). Not executed in the
  authoring session (no PowerShell there): run -DryRun first.
#>
[CmdletBinding()]
param(
    [string]$OutDir = 'C:\Downloads',
    [switch]$IncludePrivate,
    [switch]$Live,
    [switch]$SkipTests,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$Name  = 'JADE5_HANDOVER_20261102'
$Root  = Join-Path $OutDir $Name
$Owner = 'GBOGEB'
$Here  = Split-Path -Parent $MyInvocation.MyCommand.Path
$Trace = Join-Path $Here 'SESSION_PR_TRACE.json'

# Pinned default-branch heads at handover (2026-11-02). The private head is resolved live.
$Repos = @(
    @{ name = 'CODEX';                   branch = 'main';   sha = 'cc26939df6d01eaba22fe36e728e2a04be9648e5'; private = $false
       sparse = @('mission_control', 'scripts', 'tests', '.github', 'docs/data', 'controls', 'release', 'reports', 'tools', 'federation_runtime') },
    @{ name = 'pipeline-automation-hub'; branch = 'master'; sha = '75b7278f108dfda20c8ce1cbbb8459f2eb9ec790'; private = $false
       sparse = @('mission-control', '.github', 'scripts') },
    @{ name = 'gg_MATH';                 branch = 'main';   sha = '1e2caa69fedb253d7e4423e12d35c2f0536e8af8'; private = $false; sparse = @() },
    @{ name = 'DOCX_RTM_Automation';     branch = 'main';   sha = '67b5c8754d5a9b11be814a8e2a3552f13dde9c50'; private = $false; sparse = @() },
    @{ name = 'yaml-grammar';            branch = 'master'; sha = 'd6988d00f0b25ac3df75eea9e2535b7b15d838a7'; private = $false; sparse = @() },
    @{ name = 'cryoplant-project';       branch = 'main';   sha = $null;                                       private = $true;  sparse = @() }
)

function Say([string]$m) { Write-Host ('[jade-handover] ' + $m) }

function Run([string]$exe, [string[]]$argv, [string]$cwd = $null) {
    $shown = $exe + ' ' + ($argv -join ' ')
    if ($DryRun) { Say ('DRY ' + $shown); return '' }
    $old = Get-Location
    $eap = $ErrorActionPreference
    try {
        if ($cwd) { Set-Location $cwd }
        # Windows PowerShell 5.1 turns native stderr (git progress) into terminating errors under Stop.
        $ErrorActionPreference = 'Continue'
        $out = & $exe @argv 2>&1 | ForEach-Object { "$_" }
        $code = $LASTEXITCODE
        $ErrorActionPreference = $eap
        if ($code -ne 0) { throw ('FAILED (' + $code + '): ' + $shown + "`n" + ($out | Out-String)) }
        return ($out | Out-String)
    } finally { $ErrorActionPreference = $eap; Set-Location $old }
}

function GhJson([string]$path, [string]$file) {
    # REST only: GraphQL is not used, so this also works where GraphQL is blocked.
    # Single page (per_page=100 covers every session PR); --paginate would concatenate JSON arrays.
    if ($DryRun) { Say ('DRY gh api ' + $path + ' > ' + $file); return }
    $eap = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    $out = & gh api $path 2>&1 | ForEach-Object { "$_" }
    $code = $LASTEXITCODE; $ErrorActionPreference = $eap
    if ($code -ne 0) { Say ('WARN gh api ' + $path + ' failed: ' + ($out | Out-String).Trim()); return }
    [IO.File]::WriteAllText($file, ($out -join "`n"), (New-Object Text.UTF8Encoding($false)))
}

function Ensure-Dir([string]$p) { if (-not $DryRun) { New-Item -ItemType Directory -Force -Path $p | Out-Null } }

# ---------------------------------------------------------------- preflight
Say ('output: ' + $Root)
foreach ($tool in 'git', 'gh') {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { throw ($tool + ' not found on PATH') }
}
$env:GITHUB_TOKEN = $null   # a stale token overrides the keyring login and returns 401 (CODEX CLAUDE.md)
Run 'gh' @('auth', 'status') | Out-Null

$drive = (Split-Path -Qualifier $OutDir).TrimEnd(':')
$free = (Get-PSDrive -Name $drive).Free
Say ('free on ' + $drive + ': ' + [math]::Round($free / 1GB, 2) + ' GB')
if ($free -lt 3GB) { throw 'Less than 3 GB free on the output drive; stopping before any write (mirrors of CODEX and the hub are large).' }
if (-not (Test-Path $Trace)) { throw ('missing ' + $Trace + ' (keep this script next to SESSION_PR_TRACE.json)') }

foreach ($d in 'mirrors', 'bundles', 'archives', 'worktrees', 'trace', 'repro') { Ensure-Dir (Join-Path $Root $d) }

$index = [ordered]@{ name = $Name; created_utc = (Get-Date).ToUniversalTime().ToString('s') + 'Z'; live = [bool]$Live; repos = @() }

# ---------------------------------------------------------------- repos: mirror, bundle, archive, worktree
foreach ($r in $Repos) {
    if ($r.private -and -not $IncludePrivate) { Say ('skip private ' + $r.name + ' (use -IncludePrivate)'); continue }
    $full = $Owner + '/' + $r.name
    $sha = $r.sha
    if ($Live -or -not $sha) {
        $sha = if ($DryRun) { '<live-head>' } else { (Run 'gh' @('api', ('repos/' + $full + '/commits/' + $r.branch), '--jq', '.sha')).Trim() }
    }
    $short = if ($sha.Length -ge 12) { $sha.Substring(0, 12) } else { $sha }
    Say ($full + ' @ ' + $short)

    $mirror = Join-Path $Root ('mirrors\' + $r.name + '.git')
    if (Test-Path $mirror) { Run 'git' @('--git-dir', $mirror, 'remote', 'update', '--prune') | Out-Null }
    else { Run 'git' @('-c', 'core.longpaths=true', 'clone', '--mirror', ('https://github.com/' + $full + '.git'), $mirror) | Out-Null }
    if (-not $DryRun) {
        try { Run 'git' @('--git-dir', $mirror, 'cat-file', '-e', ($sha + '^{commit}')) | Out-Null }
        catch { throw ($full + ': pinned commit ' + $sha + ' not found in the mirror') }
    }

    $bundle = Join-Path $Root ('bundles\' + $r.name + '.bundle')
    Run 'git' @('--git-dir', $mirror, 'bundle', 'create', $bundle, '--all') | Out-Null
    Run 'git' @('bundle', 'verify', $bundle) | Out-Null

    $zip = Join-Path $Root ('archives\' + $r.name + '-' + $short + '.zip')
    Run 'git' @('--git-dir', $mirror, 'archive', '--format=zip', '-o', $zip, $sha) | Out-Null

    $wt = Join-Path $Root ('worktrees\' + $r.name)
    if (-not (Test-Path $wt)) {
        Run 'git' @('-c', 'core.longpaths=true', 'clone', '--no-checkout', $mirror, $wt) | Out-Null
        if ($r.sparse.Count -gt 0) {
            Run 'git' (@('sparse-checkout', 'set') + $r.sparse) $wt | Out-Null
        }
        Run 'git' @('-c', 'core.longpaths=true', 'checkout', '--detach', $sha) $wt | Out-Null
    }

    $index.repos += [ordered]@{ repo = $full; branch = $r.branch; sha = $sha; private = $r.private
                                bundle = ('bundles/' + $r.name + '.bundle'); archive = ('archives/' + $r.name + '-' + $short + '.zip')
                                worktree = ('worktrees/' + $r.name); sparse = $r.sparse }
}

# ---------------------------------------------------------------- PR trace (REST)
$traceDoc = Get-Content -Raw -Encoding UTF8 $Trace | ConvertFrom-Json
$rows = @($traceDoc.rows)
if ($IncludePrivate) {
    Say 'resolving private session PRs (cryoplant-project) via REST'
    if (-not $DryRun) {
        # Page loop without jq: Windows PowerShell 5.1 mangles double quotes in native arguments.
        for ($page = 1; $page -le 50; $page++) {
            $json = Run 'gh' @('api', ('repos/GBOGEB/cryoplant-project/pulls?state=all&per_page=100&page=' + $page))
            $parsed = $json | ConvertFrom-Json      # two statements: PS 5.1 emits a JSON array as one object
            if ($null -eq $parsed) { break }
            $batch = @($parsed)
            if ($batch.Count -eq 0) { break }
            foreach ($p in $batch) {
                if ($p.body -and $p.body -match 'session_017Fwrzak5ZCpiKxEJjfHrRW') {
                    $rows += [pscustomobject]@{ repo = 'GBOGEB/cryoplant-project'; kind = 'pr'; number = $p.number; head_sha = $p.head.sha }
                }
            }
            if ($batch.Count -lt 100) { break }
        }
    }
}
foreach ($row in $rows) {
    if ($row.kind -ne 'pr') { continue }
    $repoShort = $row.repo.Split('/')[1]
    $dir = Join-Path $Root ('trace\' + $repoShort + '\pr-' + $row.number)
    Ensure-Dir $dir
    $base = 'repos/' + $row.repo
    GhJson ($base + '/pulls/' + $row.number)                      (Join-Path $dir 'pr.json')
    GhJson ($base + '/pulls/' + $row.number + '/files?per_page=100')    (Join-Path $dir 'files.json')
    GhJson ($base + '/pulls/' + $row.number + '/reviews?per_page=100')  (Join-Path $dir 'reviews.json')
    GhJson ($base + '/pulls/' + $row.number + '/comments?per_page=100') (Join-Path $dir 'review_comments.json')
    GhJson ($base + '/issues/' + $row.number + '/comments?per_page=100') (Join-Path $dir 'issue_comments.json')
    GhJson ($base + '/commits/' + $row.head_sha + '/check-runs?per_page=100') (Join-Path $dir 'check_runs.json')
}
Say ('traced PRs: ' + @($rows | Where-Object { $_.kind -eq 'pr' }).Count)

# ---------------------------------------------------------------- reproduction
if (-not $SkipTests) {
    $hub = Join-Path $Root 'worktrees\pipeline-automation-hub'
    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $py) { $py = Get-Command py -ErrorAction SilentlyContinue }
    if (-not $py) { Say 'WARN python not found; reproduction skipped' }
    elseif ((Test-Path $hub) -or $DryRun) {
        $repro = Join-Path $Root 'repro'
        $pulse = Join-Path $repro ('FOCUS5_PULSE_' + (Get-Date -Format 'yyyyMMdd') + '.json')
        $jt = Join-Path $hub 'mission-control\jade_temple'
        Say 'reproduce: focus5_pulse.py (read-only GitHub REST)'
        try { Run $py.Source @((Join-Path $jt 'tools\focus5_pulse.py'), '--out', $pulse, '--date', (Get-Date -Format 'yyyy-MM-dd')) $jt | Set-Content -Encoding ASCII (Join-Path $repro 'focus5_pulse.log') }
        catch { Say ('WARN pulse: ' + $_.Exception.Message.Split("`n")[0]) }
        Say 'reproduce: JADE unittest suite'
        try { Run $py.Source @('-m', 'unittest', 'discover', '-s', 'mission-control/jade_temple/tests', '-p', 'test_*.py') $hub | Set-Content -Encoding ASCII (Join-Path $repro 'jade_suite.log') }
        catch { $_.Exception.Message | Set-Content -Encoding ASCII (Join-Path $repro 'jade_suite.log'); Say 'WARN JADE suite failed (see repro\jade_suite.log)' }
        Say 'reproduce: regen.py --check'
        try { Run $py.Source @('mission-control/jade_temple/tools/regen.py') $hub | Set-Content -Encoding ASCII (Join-Path $repro 'regen_check.log') }
        catch { $_.Exception.Message | Set-Content -Encoding ASCII (Join-Path $repro 'regen_check.log'); Say 'WARN regen check failed (see repro\regen_check.log)' }
    }
}

# ---------------------------------------------------------------- copy handover docs, hashes, index, zip
foreach ($f in 'HANDOVER.md', 'SESSION_PR_TRACE.json', 'Build-JadeHandover.ps1') {
    $src = Join-Path $Here $f
    if ((Test-Path $src) -and -not $DryRun) { Copy-Item $src (Join-Path $Root $f) -Force }
}
if (-not $DryRun) {
    $index | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 (Join-Path $Root 'HANDOVER_INDEX.json')
    $sums = Join-Path $Root 'SHA256SUMS.txt'
    $files = Get-ChildItem -Recurse -File $Root | Where-Object {
        $_.FullName -notlike (Join-Path $Root 'mirrors\*') -and $_.FullName -notlike (Join-Path $Root 'worktrees\*') -and $_.Name -ne 'SHA256SUMS.txt' }
    $lines = foreach ($f in $files) {
        $h = (Get-FileHash -Algorithm SHA256 $f.FullName).Hash.ToLower()
        $h + '  ' + $f.FullName.Substring($Root.Length + 1).Replace('\', '/')
    }
    [IO.File]::WriteAllLines($sums, [string[]]$lines, (New-Object Text.UTF8Encoding($false)))
    $zipOut = Join-Path $OutDir ($Name + '.zip')
    if (Test-Path $zipOut) { Remove-Item $zipOut }
    $stage = Get-ChildItem $Root | Where-Object { $_.Name -notin 'mirrors', 'worktrees' }
    Compress-Archive -Path $stage.FullName -DestinationPath $zipOut
    Say ('zip: ' + $zipOut + ' (' + [math]::Round((Get-Item $zipOut).Length / 1MB, 1) + ' MB)')
}
Say 'done. Restore any repo losslessly with: git clone <bundle> <dir>'
