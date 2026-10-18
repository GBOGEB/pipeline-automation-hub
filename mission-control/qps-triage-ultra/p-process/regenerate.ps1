<#
.SYNOPSIS
  Regenerate the P process site and zip from a fresh clone (Windows PowerShell 5.1+ or PowerShell 7).
.DESCRIPTION
  Clones GBOGEB/pipeline-automation-hub (or reuses -RepoDir), installs pinned Python and Node tooling,
  runs refresh.py (live via GitHub CLI, or -Offline from committed data), runs the tests, then package.py.
  Output: <clone>\mission-control\qps-triage-ultra\p-process\dist\p-process-site-<census>Z.zip (+ .sha256)
.EXAMPLE
  pwsh -File regenerate.ps1                         # live readback (needs: gh auth login)
  pwsh -File regenerate.ps1 -Offline                # rebuild from committed data, no GitHub calls
  pwsh -File regenerate.ps1 -Branch qps/p-process-code-purple-everred-v3-20261017 -Offline
#>
param(
  [string]$RepoDir = (Join-Path $env:TEMP "pipeline-automation-hub"),
  [string]$Branch = "master",
  [switch]$Offline,
  [switch]$NoPdf
)
$ErrorActionPreference = "Stop"
function Need($cmd, $hint) { if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { throw "$cmd not found: $hint" } }
Need git   "install Git for Windows"
Need python "install Python 3.11+ (python.org) and tick 'Add to PATH'"
Need node  "install Node.js 22 LTS (needed for the Code Purple deck and TypeScript check)"
if (-not $Offline) { Need gh "install GitHub CLI and run: gh auth login (read access to ABACUS, CODEX, cryoplant-project, gg_MATH, hub, Q_engineering_tools)" }

if (Test-Path (Join-Path $RepoDir ".git")) {
  git -C $RepoDir fetch origin $Branch; git -C $RepoDir checkout $Branch; git -C $RepoDir pull --ff-only origin $Branch
} else {
  git clone --branch $Branch https://github.com/GBOGEB/pipeline-automation-hub.git $RepoDir
}
$P = Join-Path $RepoDir "mission-control\qps-triage-ultra\p-process"
Push-Location $P
try {
  python -m venv .venv
  $py = Join-Path $P ".venv\Scripts\python.exe"
  & $py -m pip install --disable-pip-version-check -q "pyyaml==6.0.3" "pypdf>=5,<7" "playwright==1.55.0"
  if (-not $NoPdf) {
    & $py -m playwright install chromium
    npm install --no-save --no-audit --no-fund "playwright@1.55.0" | Out-Null
    $env:PLAYWRIGHT_MODULE = Join-Path $P "node_modules\playwright"
  }
  $refreshArgs = @("refresh.py"); if ($Offline) { $refreshArgs += "--offline" }; if ($NoPdf) { $refreshArgs += "--no-pdf" }
  & $py @refreshArgs;                                  if ($LASTEXITCODE) { throw "refresh.py failed" }
  & $py -m unittest discover -s tests -v;        if ($LASTEXITCODE) { throw "tests failed" }
  node tools/check_model.mts;                    if ($LASTEXITCODE) { throw "model check failed" }
  & $py package.py;                              if ($LASTEXITCODE) { throw "package.py failed" }
  Get-ChildItem dist\*.zip | Sort-Object LastWriteTime | Select-Object -Last 1 | ForEach-Object { Write-Host "ZIP: $($_.FullName)" }
} finally { Pop-Location }
