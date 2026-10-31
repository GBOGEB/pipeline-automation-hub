<#
.SYNOPSIS
  Installs the PC dashboard launcher into a folder outside any repo and schedules a daily rebuild.

.DESCRIPTION
  Copies build_dashboards.py, template.html and REFRESH.cmd to -Target (default %USERPROFILE%\DASHBOARDS).
  dashboards.json is copied only when the target has none, so your pins and scan folders survive.
  Registers the per-user scheduled task "GBOGEB Dashboards refresh" (daily at -At, runs with pythonw so
  no window opens, catches up after a missed start), adds DASHBOARDS.url and "DASHBOARDS - refresh.lnk"
  to the desktop, and builds the page once. Generated files (index.html, build.log, pages_cache.json)
  live only in -Target. Re-run after pulling changes to update the installed copy.

.EXAMPLE
  pwsh -NoProfile -File tools\workstation\dashboards\Install-Dashboards.ps1
  pwsh -NoProfile -File tools\workstation\dashboards\Install-Dashboards.ps1 -At 07:30 -NoSchedule
#>
[CmdletBinding()]
param(
    [string]$Target = (Join-Path $env:USERPROFILE 'DASHBOARDS'),
    [string]$At = '08:00',
    [switch]$NoSchedule,
    [switch]$NoShortcuts,
    [switch]$NoBuild
)
$ErrorActionPreference = 'Stop'
$src = $PSScriptRoot
$taskName = 'GBOGEB Dashboards refresh'

New-Item -ItemType Directory -Force -Path $Target | Out-Null
foreach ($f in 'build_dashboards.py', 'template.html', 'REFRESH.cmd') {
    Copy-Item -LiteralPath (Join-Path $src $f) -Destination $Target -Force
}
$cfg = Join-Path $Target 'dashboards.json'
if (-not (Test-Path -LiteralPath $cfg)) {
    Copy-Item -LiteralPath (Join-Path $src 'dashboards.json') -Destination $cfg
    Write-Host "Installed default dashboards.json"
} else {
    Write-Host "Kept existing dashboards.json (compare with $src\dashboards.json for new defaults)"
}

$python = (Get-Command python -ErrorAction Stop).Source
$pythonw = Join-Path (Split-Path $python) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonw)) { $pythonw = $python }
$script = Join-Path $Target 'build_dashboards.py'

if (-not $NoSchedule) {
    $action = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$script`"" -WorkingDirectory $Target
    $trigger = New-ScheduledTaskTrigger -Daily -At $At
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings `
        -Description "Rebuilds $Target\index.html" -Force | Out-Null
    Write-Host "Scheduled '$taskName' daily at $At"
}

if (-not $NoShortcuts) {
    $desktop = [Environment]::GetFolderPath('Desktop')
    $uri = ([Uri](Join-Path $Target 'index.html')).AbsoluteUri
    Set-Content -LiteralPath (Join-Path $desktop 'DASHBOARDS.url') -Encoding ascii -Value @(
        '[InternetShortcut]', "URL=$uri", 'IconFile=C:\Windows\System32\shell32.dll', 'IconIndex=13')
    $lnk = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $desktop 'DASHBOARDS - refresh.lnk'))
    $lnk.TargetPath = Join-Path $Target 'REFRESH.cmd'
    $lnk.WorkingDirectory = $Target
    $lnk.Save()
    Write-Host "Desktop shortcuts written to $desktop"
}

if (-not $NoBuild) {
    & $python $script
}
