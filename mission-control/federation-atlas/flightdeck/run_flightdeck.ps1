param(
  [Parameter(Mandatory=$true)][string]$RepoRoot,
  [Parameter(Mandatory=$true)][string]$OutDir,
  [switch]$RefreshHeads
)
$ErrorActionPreference='Stop'
$repo=(Resolve-Path $RepoRoot).Path
$here=Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Host 'MISSION_CONTROL_PREFLIGHT: compare tracked local master with origin/master'
& git -C $repo fetch --prune origin master
if ($LASTEXITCODE -ne 0) {throw 'Could not fetch origin/master; do not use a stale unverified clone'}
$local=(& git -C $repo rev-parse master).Trim()
$remote=(& git -C $repo rev-parse origin/master).Trim()
if ($local -ne $remote) {throw "Local master differs from origin/master: $local vs $remote; inspect and update through Git before generating."}
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$fleet=Join-Path $repo 'mission-control/gogreen/samples/fleet_g1.json'
$snapshot=Join-Path $OutDir 'head_snapshot_frozen.json'
Copy-Item (Join-Path $here 'head_snapshot.json') $snapshot -Force
if ($RefreshHeads) { & python (Join-Path $here 'flightdeck.py') refresh-heads --fleet $fleet --snapshot $snapshot; if ($LASTEXITCODE -ne 0) {throw 'Read-only snapshot refresh failed'} }
& python (Join-Path $here 'flightdeck.py') preflight --fleet $fleet --snapshot $snapshot --contract (Join-Path $here 'flightdeck_contract.json')
if ($LASTEXITCODE -ne 0) {throw 'Preflight failed'}
& python (Join-Path $here 'flightdeck.py') build --fleet $fleet --snapshot $snapshot --contract (Join-Path $here 'flightdeck_contract.json') --out $OutDir --exact-git-sha $remote
if ($LASTEXITCODE -ne 0) {throw 'Build failed'}
Write-Host 'Static HTML/SVG/JSON generated. Optional binary step: python source/office_export.py --input out/census.json --out out'
& python (Join-Path $here 'flightdeck.py') verify --out $OutDir
if ($LASTEXITCODE -ne 0) {throw 'Manifest verification failed'}
Write-Host "REVIEW_GUI: $OutDir/index.html"