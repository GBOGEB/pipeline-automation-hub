#Requires -Version 7.0
<#
.SYNOPSIS
    Write PyCharm project and IDE settings for the GBOGEB workspace folder built by Invoke-WorkspaceOverview.ps1.
.DESCRIPTION
    Project level (in <Workspace>\.idea\):
      vcs.xml            one Git root per repos\ and worktrees\ link, so every repo/worktree shows in Git / Commit
      scopes\*.xml       Repos, Worktrees, QPS ledger, YAML-JSON-TOML, Office-PDF: pick them in the Project tree
                         dropdown, in Find in Files, and for file colours
      fileColors.xml     Repos blue, Worktrees green, QPS ledger violet in the Project tree
    Workspace root:
      requirements-workspace.txt   the pins the repos use (PyCharm offers "Install requirements" for the venv)
    IDE level (unless -SkipTools), %APPDATA%\JetBrains\<PyCharm>\tools\GBOGEB.xml:
      right-click External Tools: refresh the workspace, audit a folder, QPS dry-run / publish / peer / merge
      on the selected workbook (version asked in a prompt).

    PyCharm rewrites these files when it exits, so this script stops if PyCharm is running (unless -Force).
    Existing files are backed up next to themselves as *.bak-<stamp> before they are replaced.
.EXAMPLE
    pwsh -File tools/workstation/Set-PyCharmWorkspaceConfig.ps1 -Workspace C:\repos\GBOGEB_WORKSPACE
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string] $Workspace,
    [string] $Ledger = (Join-Path $HOME 'OneDrive - Studiecentrum voor Kernenergie\Master_Input\QPS_ACTION_LEDGER'),
    [string] $PyCharmConfig,
    [switch] $SkipTools,
    [switch] $Force
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
if ((Get-Process pycharm64 -ErrorAction SilentlyContinue) -and -not $Force) {
    throw 'PyCharm is running and would overwrite these files on exit. Close PyCharm (File > Exit), rerun, then reopen it.'
}
$ws = (Resolve-Path -LiteralPath $Workspace).ProviderPath
$idea = Join-Path $ws '.idea'
New-Item -ItemType Directory -Force -Path (Join-Path $idea 'scopes') | Out-Null

function Write-Xml([string]$Path, [string]$Text) {
    if (Test-Path -LiteralPath $Path) {
        if ((Get-Content -LiteralPath $Path -Raw) -eq $Text) { return }
        Copy-Item -LiteralPath $Path "$Path.bak-$stamp"
    }
    Set-Content -LiteralPath $Path -Value $Text -Encoding utf8 -NoNewline
    Write-Host "wrote $Path"
}
function Esc([string]$s) { [Security.SecurityElement]::Escape($s) }

# ---------------------------------------------------------------- vcs.xml (one Git root per link)
$maps = foreach ($sub in 'repos', 'worktrees') {
    $d = Join-Path $ws $sub
    if (-not (Test-Path -LiteralPath $d)) { continue }
    Get-ChildItem -LiteralPath $d -Force | Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName '.git') } | Sort-Object Name |
        ForEach-Object { "    <mapping directory=`"`$PROJECT_DIR`$/$sub/$(Esc $_.Name)`" vcs=`"Git`" />" }
}
Write-Xml (Join-Path $idea 'vcs.xml') (@(
        '<?xml version="1.0" encoding="UTF-8"?>', '<project version="4">', '  <component name="VcsDirectoryMappings">'
        @($maps)
        '  </component>', '</project>', '') -join "`n")

# ---------------------------------------------------------------- scopes + file colours
$scopes = [ordered]@{
    'Repos'           = 'file:repos//*'
    'Worktrees'       = 'file:worktrees//*'
    'QPS ledger'      = 'file:extra/QPS_ACTION_LEDGER//*'
    'YAML-JSON-TOML'  = 'file:*.yaml||file:*.yml||file:*.json||file:*.toml'
    'Office-PDF'      = 'file:*.xlsx||file:*.docx||file:*.pptx||file:*.pdf'
}
foreach ($k in $scopes.Keys) {
    $file = Join-Path $idea ("scopes\" + ($k -replace '[^A-Za-z0-9]+', '_') + '.xml')
    Write-Xml $file ("<component name=`"DependencyValidationManager`">`n  <scope name=`"$(Esc $k)`" pattern=`"$(Esc $scopes[$k])`" />`n</component>")
}
Write-Xml (Join-Path $idea 'fileColors.xml') (@(
        '<?xml version="1.0" encoding="UTF-8"?>', '<project version="4">', '  <component name="SharedFileColors">'
        '    <fileColor scope="Repos" color="Blue" />'
        '    <fileColor scope="Worktrees" color="Green" />'
        '    <fileColor scope="QPS ledger" color="Violet" />'
        '  </component>', '</project>', '') -join "`n")

# ---------------------------------------------------------------- requirements for the workspace venv
Write-Xml (Join-Path $ws 'requirements-workspace.txt') (@(
        '# Pins used across GBOGEB repos (cryoplant-project, pipeline-automation-hub, ABACUS) on 2026-10-31.'
        '# For PyCharm code insight and running tools from the IDE; each repo CI keeps its own pins.'
        'openpyxl==3.1.5', 'PyYAML==6.0.3', 'jsonschema==4.25.1', 'pytest==8.4.2', '') -join "`n")

# ---------------------------------------------------------------- IDE External Tools (right-click menu)
if (-not $SkipTools) {
    if (-not $PyCharmConfig) {
        $PyCharmConfig = (Get-ChildItem (Join-Path $env:APPDATA 'JetBrains') -Directory -Filter 'PyCharm20*' | Sort-Object Name | Select-Object -Last 1).FullName
    }
    if (-not $PyCharmConfig) { throw 'PyCharm settings folder not found under %APPDATA%\JetBrains (pass -PyCharmConfig)' }
    $overview = Join-Path $PSScriptRoot 'Invoke-WorkspaceOverview.ps1'
    $audit = Join-Path $PSScriptRoot 'Invoke-WorkspaceAudit.ps1'
    $qps = Join-Path $Ledger 'tools\New-QpsLedgerVersion.ps1'
    $tools = [ordered]@{
        'Workspace: refresh overview and links'      = "-NoProfile -File `"$overview`" -PyCharmWorkspace `"$ws`" -ExtraFolder `"$Ledger`" -SkipSize"
        'Workspace: audit selected folder (read-only)' = "-NoProfile -File `"$audit`" -Root `"`$FilePath`$`" -SkipTokenCheck"
        'QPS: dry-run selected FULL (no publish)'    = "-NoProfile -File `"$qps`" -Mode Rebuild -Version `$Prompt`$ -Full `"`$FilePath`$`""
        'QPS: publish selected FULL'                 = "-NoProfile -File `"$qps`" -Mode Rebuild -Version `$Prompt`$ -Full `"`$FilePath`$`" -Publish"
        'QPS: export PEER from selected FULL'        = "-NoProfile -File `"$qps`" -Mode Peer -Version `$Prompt`$ -Full `"`$FilePath`$`" -Publish"
        'QPS: merge selected edited PEER back'       = "-NoProfile -File `"$qps`" -Mode Merge -Version `$Prompt`$ -PeerEdited `"`$FilePath`$`" -Publish"
    }
    $xml = [Collections.Generic.List[string]]::new()
    $xml.Add('<toolSet name="GBOGEB">')
    foreach ($k in $tools.Keys) {
        $xml.Add("  <tool name=`"$(Esc $k)`" showInMainMenu=`"true`" showInEditor=`"true`" showInProject=`"true`" showInSearchPopup=`"true`" disabled=`"false`" useConsole=`"true`" showConsoleOnStdOut=`"false`" showConsoleOnStdErr=`"false`" synchronizeAfterRun=`"true`">")
        $xml.Add('    <exec>')
        $xml.Add('      <option name="COMMAND" value="pwsh.exe" />')
        $xml.Add("      <option name=`"PARAMETERS`" value=`"$(Esc $tools[$k])`" />")
        $xml.Add('      <option name="WORKING_DIRECTORY" value="$ProjectFileDir$" />')
        $xml.Add('    </exec>')
        $xml.Add('  </tool>')
    }
    $xml.Add('</toolSet>')
    $td = Join-Path $PyCharmConfig 'tools'
    New-Item -ItemType Directory -Force -Path $td | Out-Null
    Write-Xml (Join-Path $td 'GBOGEB.xml') (($xml -join "`n") + "`n")
}
Write-Host "Done. Open $ws in PyCharm. Git roots: $(@($maps).Count)."
