<#
.SYNOPSIS
  JADE_TEMPLE / JADE_CASTE point-release *readiness* testflight.
.DESCRIPTION
  Local, bounded, source-hash-bound preflight. No merge, tag, release,
  remote dispatch, owner approval or Pages publication. An isolated venv
  is created locally without network access. -FreshClone and
  -InstallOptionalDependencies are the only network-requesting switches.
.EXAMPLE
  .\Start-JadeSprint.ps1 -Mode Plan
.EXAMPLE
  .\Start-JadeSprint.ps1 -Mode Full -MaxWorkers 2 -NoCache
.EXAMPLE
  .\Start-JadeSprint.ps1 -FreshClone -CloneRef code-purple/jade-n3-release-sprint-dag-20261019 -Mode Full
#>
[CmdletBinding()]
param(
  [ValidateSet("Plan","Local","Verify","Full")]
  [string]$Mode="Plan",
  [string]$ProjectRoot="",
  [string]$Workspace="",
  [ValidateRange(1,4)]
  [int]$MaxWorkers=2,
  [ValidateRange(1,72)]
  [int]$CacheHours=12,
  [switch]$FreshClone,
  [string]$CloneRef="code-purple/jade-n5-exact-head-testflight-20261019",
  [switch]$InstallOptionalDependencies,
  [switch]$WithBrowser,
  [switch]$NoCache,
  [string]$ExpectedHead="",
  [string]$NPlus2Readback="",
  [switch]$Offline
)
Set-StrictMode -Version Latest
$ErrorActionPreference="Stop"

function Assert-Exit {
  param([string]$Label)
  if ($LASTEXITCODE -ne 0) {
    throw "$Label failed with exit code $LASTEXITCODE"
  }
}

if ([string]::IsNullOrWhiteSpace($Workspace)) {
  $homePath=[Environment]::GetFolderPath("UserProfile")
  if ([string]::IsNullOrWhiteSpace($homePath)) { throw "User profile folder not available" }
  $Workspace=Join-Path $homePath "JADE_TEMPLE_WORK"
}
$Workspace=[System.IO.Path]::GetFullPath($Workspace)
[void][System.IO.Directory]::CreateDirectory($Workspace)

if ($Offline -and ($FreshClone -or $InstallOptionalDependencies)) {
  throw "Offline mode cannot clone or install dependencies"
}
if ($FreshClone) {
  if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "git CLI required for a fresh clone"
  }
  if ($CloneRef -notmatch "^[A-Za-z0-9][A-Za-z0-9/_\.\-]{0,180}$" -or
      $CloneRef.Contains("..")) {
    throw "Unsafe CloneRef"
  }
  $folder="source-"+[DateTime]::UtcNow.ToString("yyyyMMdd-HHmmss")+"-"+[Guid]::NewGuid().ToString("N").Substring(0,6)
  $target=Join-Path $Workspace $folder
  if (Test-Path -LiteralPath $target) { throw "Fresh checkout target already exists" }
  & git clone --depth 1 --no-tags --branch $CloneRef https://github.com/GBOGEB/pipeline-automation-hub.git $target
  Assert-Exit "Fresh isolated JADE clone"
  $ProjectRoot=$target
}
if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
  $ProjectRoot=Join-Path $PSScriptRoot "../../.."
}
$ProjectRoot=(Resolve-Path -LiteralPath $ProjectRoot).Path
$scriptPath=Join-Path $ProjectRoot "mission-control/jade_temple/sprint/cli.py"
if (-not (Test-Path -LiteralPath $scriptPath)) {
  throw "This source checkout has no JADE N+3 sprint CLI. Use its candidate branch, not an older master."
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  throw "Git CLI is needed for exact checkout SHA binding"
}
$head=(& git -C $ProjectRoot rev-parse HEAD | Out-String).Trim()
Assert-Exit "Read exact SHA"
if ($head -notmatch "^[0-9a-f]{40}$") { throw "Git checkout head is not an exact SHA" }
if ($ExpectedHead -and $ExpectedHead -ne $head) { throw "ExpectedHead mismatch: refusing stale testflight" }

$venv=Join-Path $Workspace ".venv-jade"
$pythonExe=Join-Path $venv "Scripts/python.exe"
if (-not (Test-Path $pythonExe)) {
  $pythonExe=Join-Path $venv "bin/python"
}
if (-not (Test-Path $pythonExe)) {
  $preferPython=$false
  if (Get-Command python -ErrorAction SilentlyContinue) {
    $probe=(& python -c "import sys;print(1 if sys.version_info >= (3,11) else 0)" 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -eq 0 -and $probe -eq "1") { $preferPython=$true }
  }
  if ($preferPython) {
    & python -m venv $venv
    Assert-Exit "Create venv with explicitly qualified active Python"
  } elseif (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3.11 -m venv $venv
    Assert-Exit "Create Python 3.11 environment"
  } else {
    throw "Install Python 3.11+ or Windows py launcher before starting"
  }
}
$pythonExe=Join-Path $venv "Scripts/python.exe"
if (-not (Test-Path $pythonExe)) {
  $pythonExe=Join-Path $venv "bin/python"
}
if (-not (Test-Path $pythonExe)) { throw "Isolated venv interpreter missing" }
$version=(& $pythonExe -c "import sys;print(sys.version_info.major,sys.version_info.minor)" | Out-String).Trim()
Assert-Exit "Venv Python version"
$parts=$version -split " "
if ([int]$parts[0] -ne 3 -or [int]$parts[1] -lt 11) {
  throw "Python 3.11+ required for JADE preflight"
}

if ($InstallOptionalDependencies) {
  $requirements=Join-Path $ProjectRoot "mission-control/jade_temple/sprint/requirements-optional.txt"
  & $pythonExe -m pip install --disable-pip-version-check -r $requirements
  Assert-Exit "Pinned optional QA dependencies"
  & $pythonExe -m playwright install chromium
  Assert-Exit "Pinned Chromium browser"
}
if ($WithBrowser -and -not $InstallOptionalDependencies) {
  Write-Warning "Browser QA selected. Ensure playwright==1.56.0 and Chromium are already installed in the isolated venv."
}

$outputDir=Join-Path $Workspace "output"
$cacheDir=Join-Path $Workspace "cache"
[void][System.IO.Directory]::CreateDirectory($outputDir)
[void][System.IO.Directory]::CreateDirectory($cacheDir)
$argv=@($scriptPath, "--mode", $Mode.ToLowerInvariant(),
         "--repo-root", $ProjectRoot, "--out", $outputDir,
         "--cache-dir", $cacheDir, "--max-workers", [string]$MaxWorkers,
         "--cache-ttl-hours", [string]$CacheHours, "--expected-head", $head)
if ($NoCache) { $argv+= "--no-cache" }
if ($WithBrowser) { $argv+= "--with-browser" }
if (-not [string]::IsNullOrWhiteSpace($NPlus2Readback)) {
  $argv+="--nplus2"
  $argv+=[System.IO.Path]::GetFullPath($NPlus2Readback)
}

Write-Host "JADE_CASTE $Mode | exact HEAD=$head | local workers=$MaxWorkers"
Write-Host "Repository=$ProjectRoot"
Write-Host "Outputs=$outputDir"
& $pythonExe @argv
Assert-Exit "JADE source-bound sprint"
Write-Host "POINT RELEASE remains TARGET_NOT_ACHIEVED. Admission remains HOLD."
Write-Host "Open $outputDir/SPRINT_DASHBOARD.html and inspect SHA256_MANIFEST.json."
