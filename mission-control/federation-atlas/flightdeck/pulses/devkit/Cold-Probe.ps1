param(
  [string]$RepoRoot = '.',
  [string]$Out = '',
  [string]$PythonExe = 'python'
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$argsList = @((Join-Path $here 'worker_devkit.py'), '--config', (Join-Path $here 'runner.toml'), '--plan', (Join-Path $here 'worker_plan.json'), '--repo', $RepoRoot)
if ($Out -ne '') { $argsList += @('--out', $Out) }
& $PythonExe @argsList
if ($LASTEXITCODE -ne 0) { throw "CODE PURPLE local probe failed: $LASTEXITCODE" }
