<#
Install-ResourceWatch.ps1 - register the ResourceWatch scheduled task and resourcewatch: link.

Default is a dry run: it prints what it would register and changes nothing.
Pass -Apply to register (it calls ResourceWatch.ps1 -Mode Install from -Target).

  -Target  Folder that holds ResourceWatch.ps1 (default: this folder).
           Copy config.example.json to config.json there first if you want local overrides.
#>
param(
    [string]$Target = $PSScriptRoot,
    [switch]$Apply
)
$ErrorActionPreference = 'Stop'
$script = Join-Path $Target 'ResourceWatch.ps1'
if (-not (Test-Path $script)) { throw "ResourceWatch.ps1 not found in $Target" }
$config = Join-Path $Target 'config.json'
if (-not (Test-Path $config)) { $config = Join-Path $Target 'config.example.json' }
$every = (Get-Content $config -Raw | ConvertFrom-Json).checkEveryMin
$existing = Get-ScheduledTask -TaskName 'ResourceWatch' -ErrorAction SilentlyContinue

"Script   : $script"
"Config   : $config"
"Task     : ResourceWatch, every $every min and at logon, via run-hidden.vbs"
"Link     : HKCU\Software\Classes\resourcewatch"
"Existing : $(if ($existing) { ($existing.Actions | ForEach-Object { "$($_.Execute) $($_.Arguments)" }) -join '; ' } else { 'none' })"
if (-not $Apply) { 'Dry run: nothing registered. Re-run with -Apply to register (replaces an existing task).'; return }
& $script -Mode Install
