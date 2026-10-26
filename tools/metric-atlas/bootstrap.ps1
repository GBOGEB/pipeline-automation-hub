<#
.CODE PURPLE Metric Atlas local bootstrap.
No network access or Python packages are required for dashboard generation.
Example: powershell -ExecutionPolicy Bypass -File .\bootstrap.ps1 -RunTests -OpenDashboard
#>
param(
    [switch]$RunTests,
    [switch]$OpenDashboard,
    [switch]$UpgradePip
)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
Write-Host 'CODE PURPLE Metric Atlas - read-only local bootstrap'
$launcher = $null
if (Get-Command py -ErrorAction SilentlyContinue) { $launcher = @('py', '-3') }
elseif (Get-Command python -ErrorAction SilentlyContinue) { $launcher = @('python') }
else { throw 'Python 3.9 or newer is required. Install Python, then rerun.' }
$program = $launcher[0]
$prefixArgs = @()
if ($launcher.Count -gt 1) { $prefixArgs = $launcher[1..($launcher.Count-1)] }
& $program @prefixArgs -c "import sys; assert sys.version_info >= (3,9), 'Python 3.9+ required'; print(sys.version)"
if ($LASTEXITCODE -ne 0) { throw 'Python version check failed.' }
if (-not (Test-Path '.venv\Scripts\python.exe')) {
    & $program @prefixArgs -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Failed to create .venv' }
}
$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if ($UpgradePip) {
    Write-Warning 'Upgrading pip accesses the network; this is optional.'
    & $venvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw 'pip upgrade failed' }
}
if ($RunTests) {
    & $venvPython -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Local test suite failed' }
}
& $venvPython -m metric_atlas.cli build --input data\observations.json --output run
if ($LASTEXITCODE -ne 0) { throw 'Metric Atlas build failed' }
Write-Host 'Dashboard: ' (Join-Path $PSScriptRoot 'run\index.html')
Write-Host 'CLI example: .venv\Scripts\python.exe -m metric_atlas.cli --help'
Write-Host 'Optional GitHub read-only observation (requires gh auth):'
Write-Host '  .venv\Scripts\python.exe -m metric_atlas.cli collect-gh --repo GBOGEB/ABACUS --pr 2080 --output run\gh_2080.json'
if ($OpenDashboard) { Start-Process (Join-Path $PSScriptRoot 'run\index.html') }
