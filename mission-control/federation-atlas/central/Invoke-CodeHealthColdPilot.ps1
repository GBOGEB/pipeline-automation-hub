# CODE-HEALTH Pillar L — optional Windows cold-pilot. Never auto-dispatches.
# Usage: .\Invoke-CodeHealthColdPilot.ps1 -RepoRoot C:\repos\pipeline-automation-hub
#        .\Invoke-CodeHealthColdPilot.ps1 -RepoRoot C:\repos\pipeline-automation-hub -Execute -ProbeVisualBasic
[CmdletBinding()]
param(
  [string]$RepoRoot = "C:\repos\pipeline-automation-hub",
  [string]$OutputDir = "",
  [string]$ExpectedSha = "",
  [switch]$Execute,
  [switch]$ProbeVisualBasic
)

$ErrorActionPreference = "Stop"
$startUtc = [DateTime]::UtcNow
$timer = [System.Diagnostics.Stopwatch]::StartNew()
if (-not (Test-Path -LiteralPath $RepoRoot -PathType Container)) {
  throw "Local repo not found. No PC source or Crew launch has been authenticated."
}
$root = (Resolve-Path -LiteralPath $RepoRoot).Path
if (-not $OutputDir) {
  $OutputDir = Join-Path $root "build\code-health-cold"
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  throw "git executable unavailable"
}
$head = (& git -C $root rev-parse --verify HEAD 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $head -notmatch '^[0-9a-f]{40}$') {
  throw "Local source identity unavailable"
}
$dirtyLines = @(& git -C $root status --porcelain --untracked-files=normal 2>&1)
if ($LASTEXITCODE -ne 0) { throw "Local worktree check failed" }
$dirty = $dirtyLines.Count -gt 0
$headMatches = (-not $ExpectedSha) -or ($ExpectedSha -eq $head)
if (-not $headMatches) {
  throw "Expected exact Git SHA does not match local checkout"
}
$tests = @{
  attempted = $false
  exit_code = $null
  executed = $null
  passed = $null
  elapsed_seconds = $null
  log_sha256 = $null
}
$vb = @{
  requested = [bool]$ProbeVisualBasic
  files_seen_bounded = $null
  files_hashed = $null
  sample_limit = 20
  executed = $false
  classification = "NOT_RUN"
}
$status = "DRY_RUN_NOT_EXECUTED"

if ($ProbeVisualBasic) {
  # File inventory only: no cscript, macro, VBE/Office automation, or VB execution.
  $files = @(Get-ChildItem -LiteralPath $root -Recurse -File -ErrorAction Stop |
    Where-Object { $_.Extension -in @(".vb", ".vba", ".vbs") } |
    Select-Object -First 21)
  $vb.files_seen_bounded = $files.Count
  $items = @()
  foreach ($file in ($files | Select-Object -First 20)) {
    $digest = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    $items += @{ relative_path = $file.FullName.Substring($root.Length).TrimStart("\"); sha256 = $digest }
  }
  $vb.files_hashed = $items.Count
  $vb.partial_population = $files.Count -gt 20
  $vb.files = $items
  $vb.classification = "FINGERPRINT_ONLY_NOT_EXECUTED"
}
if ($Execute) {
  if ($dirty) {
    $status = "BLOCKED_DIRTY_WORKTREE"
  } elseif (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    $status = "BLOCKED_PYTHON_UNAVAILABLE"
  } else {
    $status = "TESTFLIGHT_STARTED"
    $tests.attempted = $true
    New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
    $log = Join-Path $OutputDir "cold-unittest.log"
    $testTimer = [System.Diagnostics.Stopwatch]::StartNew()
    $saved = Get-Location
    try {
      Set-Location -LiteralPath $root
      & python -m unittest discover -s mission-control/federation-atlas -p 'test_code_health_*.py' -v 2>&1 |
        Out-File -FilePath $log -Encoding utf8
      $tests.exit_code = $LASTEXITCODE
    } finally {
      Set-Location $saved
      $testTimer.Stop()
    }
    $tests.elapsed_seconds = [math]::Round($testTimer.Elapsed.TotalSeconds, 3)
    if (Test-Path -LiteralPath $log -PathType Leaf) {
      $tests.log_sha256 = (Get-FileHash -LiteralPath $log -Algorithm SHA256).Hash.ToLowerInvariant()
      $tail = Get-Content -LiteralPath $log -Tail 25 | Out-String
      if ($tail -match 'Ran\s+(\d+)\s+tests?') {
        $tests.executed = [int]$Matches[1]
      }
      $tests.passed = ($tests.exit_code -eq 0 -and
        $tests.executed -gt 0 -and $tail -match 'OK')
    }
    $status = if ($tests.passed) { "LOCAL_TEST_PASS_NOT_NATIVE" } else { "LOCAL_TEST_FAIL" }
  }
}

$timer.Stop()
$record = [ordered]@{
  schema = "missioncontrol.code_health.local_cold_receipt.v1"
  pillar = "L"
  repository = "GBOGEB/pipeline-automation-hub"
  branch = (& git -C $root branch --show-current | Out-String).Trim()
  source_sha = $head
  expected_sha = if ($ExpectedSha) { $ExpectedSha } else { $null }
  repo_root_local_only = $root
  started_at_utc = $startUtc.ToString("o")
  completed_at_utc = [DateTime]::UtcNow.ToString("o")
  elapsed_seconds = [math]::Round($timer.Elapsed.TotalSeconds, 3)
  worktree_dirty = $dirty
  status = $status
  tests = $tests
  visual_basic = $vb
  authenticated_crew_launch = $null
  accepted_rex = $null
  main_merge = $false
  root_closed = $null
  native_CI_admission = "UNKNOWN"
  authority_transfer = $false
  remote_mutation = $false
}
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$dest = Join-Path $OutputDir "cold-receipt.json"
$record | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $dest -Encoding utf8
Write-Output "CODE-HEALTH local cold pilot: $status"
Write-Output "Exact local SHA: $head"
Write-Output "Local receipt only: $dest"
Write-Output "No GitHub dispatch, merge, A10/security waiver or REX authentication."
if ($Execute -and $status -ne "LOCAL_TEST_PASS_NOT_NATIVE") { exit 1 }
