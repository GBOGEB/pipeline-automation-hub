<#
.SYNOPSIS
  Re-run the Master_Input document pipeline and see what it ACTUALLY does (#529 G09).

.DESCRIPTION
  Runs scripts/run_processing.py under the runtime harness and produces, per run:
    receipt.json   exit code, uncaught exceptions + tracebacks (every Python process), flagged stderr,
                   processes spawned, every repo function called (file:qualname@line, call counts,
                   first-call order, file SHA-256 + git O-ID), outputs created/modified/deleted vs the
                   committed outputs (SHA-256 + O-ID, JSON keys changed), input immutability proof,
                   stray repository writes
    sipoc.mmd, dag.mmd, spine.mmd, DIAGRAMS.md   generated from the run
    report.html    interactive: label toggle name | SHA-256 | O-ID | tags, filter, diagrams
  Default is SANDBOXED (outputs written to a copy; your working tree is not modified).
  -InPlace writes into app/public/outputs exactly like a real refresh (review with `git diff`).

.EXAMPLE
  pwsh ./mission-control/pipeline_runtime/Run-MasterInputPipeline.ps1
.EXAMPLE
  pwsh ./mission-control/pipeline_runtime/Run-MasterInputPipeline.ps1 -InPlace -Open
.EXAMPLE
  pwsh ./mission-control/pipeline_runtime/Run-MasterInputPipeline.ps1 -ExcelInput .\plan.xlsx -ReportDir .\runs\today
#>
[CmdletBinding()]
param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path,
    [string]$ReportDir = (Join-Path ([IO.Path]::GetTempPath()) ("master-input-run-" + (Get-Date -Format 'yyyyMMdd-HHmmss'))),
    [string]$InputDir,
    [string]$ExcelInput,
    [string]$Python,
    [switch]$InPlace,
    [switch]$Open
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Resolve-Python {
    param([string]$Preferred)
    if ($Preferred) { return $Preferred }
    foreach ($c in @('python', 'python3', 'py')) {
        $cmd = Get-Command $c -ErrorAction SilentlyContinue
        if ($cmd) { return $cmd.Source }
    }
    throw 'Python 3.10+ not found on PATH. Install Python or pass -Python <path>.'
}

$py = Resolve-Python $Python
$ver = & $py -c "import sys;print('%d.%d' % sys.version_info[:2])"
if ([version]$ver -lt [version]'3.10') { throw "Python $ver found; 3.10+ required." }
& $py -c "import pptx" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Warning 'python-pptx is not installed: the PPTX phase will report it. Install with: pip install python-pptx openpyxl'
}

$harness = Join-Path $RepoRoot 'mission-control/pipeline_runtime/harness.py'
$pyArgs = @($harness, '--repo-root', $RepoRoot, '--report-dir', $ReportDir, '--python', $py)
if ($InputDir)   { $pyArgs += @('--input-dir', $InputDir) }
if ($ExcelInput) { $pyArgs += @('--excel-input', $ExcelInput) }
if ($InPlace)    { $pyArgs += '--in-place' }

Write-Host "Master_Input pipeline · $(if ($InPlace) {'IN-PLACE'} else {'SANDBOX'}) · report -> $ReportDir" -ForegroundColor Cyan
$sw = [Diagnostics.Stopwatch]::StartNew()
$out = & $py @pyArgs
$code = $LASTEXITCODE
$sw.Stop()
$summary = $out | Select-Object -Last 1 | ConvertFrom-Json

$color = if ($summary.result -eq 'PASS') { 'Green' } else { 'Red' }
Write-Host ("Result {0} · exit {1} · {2} processes · {3} functions · outputs +{4} ~{5} -{6} · inputs immutable {7} · stray writes {8} · {9:N1}s" -f `
    $summary.result, $summary.exit_code, $summary.processes, $summary.functions, $summary.outputs.created,
    $summary.outputs.modified, $summary.outputs.deleted, $summary.inputs_immutable, $summary.stray_repo_writes,
    $sw.Elapsed.TotalSeconds) -ForegroundColor $color

$receipt = Get-Content (Join-Path $ReportDir 'receipt.json') -Raw | ConvertFrom-Json
foreach ($e in $receipt.errors.uncaught) {
    Write-Host "UNCAUGHT in $($e.process) (pid $($e.pid)): $($e.type): $($e.message)" -ForegroundColor Red
}
if ($InPlace) { Write-Host "Review the refresh with: git -C `"$RepoRoot`" diff --stat -- app/public/outputs" }
Write-Host "Report: $(Join-Path $ReportDir 'report.html')"
if ($Open) { Invoke-Item (Join-Path $ReportDir 'report.html') }
exit $code
