# Source-owned operator gate; PowerShell 5.1+, gh CLI already authenticated.
# Dry-run by default. No private source SHA or token embedded here.
param([switch]$Execute)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }
$env:PYTHONPATH = $Root
$Args = @("-m", "metric_atlas.owner_flight",
          "--wave", "N2_20261017",
          "--output", (Join-Path $Root "run\qps-owner-n2.json"))
if ($Execute) {
    $Args += @("--execute", "--confirm", "OWNER_APPROVED_N2_READONLY_CENSUS")
}
& $Python @Args
if ($LASTEXITCODE -ne 0) {
    throw "QPS N2 owner flight held or failed; no successful receipt inferred."
}
