# Portable, read-only G3P HTML QA bootstrap (Windows PowerShell 7 / 5.1)
param(
    [string]$Python = "python",
    [string]$WorkDir = ".g3p-html-qa",
    [string]$BrowserExecutable = "",
    [switch]$SkipBrowserInstall
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$Repo = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
Set-Location $Repo
& $Python --version
if ($LASTEXITCODE -ne 0) { throw "Python not available" }
$Venv = Join-Path $Repo ".venv-g3p-htmlqa"
if (-not (Test-Path $Venv)) {
    & $Python -m venv $Venv
    if ($LASTEXITCODE -ne 0) { throw "venv creation failed" }
}
$Py = Join-Path $Venv "Scripts/python.exe"
& $Py -m pip install --disable-pip-version-check "playwright==1.57.0"
if ($LASTEXITCODE -ne 0) { throw "Playwright install failed" }
if ($BrowserExecutable) {
    $env:CHROMIUM_EXECUTABLE_PATH = $BrowserExecutable
} elseif (-not $SkipBrowserInstall) {
    & $Py -m playwright install chromium
    if ($LASTEXITCODE -ne 0) { throw "Chromium install failed" }
}
$Base = Join-Path $Repo $WorkDir
New-Item -ItemType Directory -Force -Path $Base | Out-Null
$Atlas = Join-Path $Base "atlas"
New-Item -ItemType Directory -Force -Path $Atlas | Out-Null
Set-Content -Path (Join-Path $Atlas "index.html") -Value "<!doctype html><html><head><title>QA Atlas</title></head><body><h1>Atlas</h1></body></html>" -Encoding UTF8
$Source = Join-Path $Repo "mission-control/federation-atlas"
$Qa = Join-Path $Repo "mission-control/html_qa"
$Exact = (& git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $Exact -notmatch "^[0-9a-f]{40}$") { throw "exact Git checkout SHA unavailable" }
& $Py -m unittest discover -s "mission-control/html_qa" -p "test_*.py" -v
if ($LASTEXITCODE -ne 0) { throw "unit QA failed" }
& $Py -m unittest discover -s "mission-control/v2" -p "test_g3p_live_ledger.py" -v
if ($LASTEXITCODE -ne 0) { throw "G3P contract QA failed" }
& $Py (Join-Path $Source "pages_portal.py") --atlas $Atlas --out (Join-Path $Base "published") --sha $Exact
if ($LASTEXITCODE -ne 0) { throw "Pages staging failed" }
& $Py (Join-Path $Qa "prepare_sources.py") --manifest (Join-Path $Source "G3P_LIVE_SOURCES_v1.json") --repo-root $Repo --out (Join-Path $Base "fixtures")
if ($LASTEXITCODE -ne 0) { throw "source replay failed" }
& $Py (Join-Path $Qa "g3p_browser_qa.py") --html (Join-Path $Base "published/g3p/index.html") --manifest (Join-Path $Base "published/g3p/G3P_LIVE_SOURCES_v1.json") --fixtures (Join-Path $Base "fixtures") --out (Join-Path $Base "browser")
if ($LASTEXITCODE -ne 0) { throw "browser visual QA failed" }
Write-Host "PASS: local G3P QA package at $Base; no remote Pages publish or merge-authority transfer"
