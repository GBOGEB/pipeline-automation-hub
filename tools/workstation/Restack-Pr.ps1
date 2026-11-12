<#
.SYNOPSIS
  Rebase GitHub PR branches without a checkout (no worktree, ~0 disk), and restack PRs whose
  parent PR was squash-merged. Probe by default; pushes only with -Apply, using --force-with-lease
  pinned to the head SHA GitHub reported, so a concurrent push is never overwritten.

.DESCRIPTION
  For each PR: fetch head and base into refs/restack/<n>/{head,onto}; refuse if the head moved since
  gh read it; replay each non-merge commit with `git merge-tree --write-tree` and `git commit-tree`
  (author kept). The dry run (no -Apply) prints the replay plan (pick / drop / skip per commit) and
  writes the result only to refs/restack/<n>/rebased; it never changes refs/heads/* or the remote.
  Which restack tool to use when: tools/workstation/README.md, section "Which restack tool".

.EXAMPLE
  # probe (no push)
  .\Restack-Pr.ps1 -Clone C:\Users\gbonthuy\ABACUS -Repo GBOGEB/ABACUS -Pr 2488
  # apply
  .\Restack-Pr.ps1 -Clone C:\Users\gbonthuy\ABACUS -Repo GBOGEB/ABACUS -Pr 2488 -Apply
  # parent PR squash-merged: cut the parent's commits off (Upstream = old parent head SHA or ref)
  .\Restack-Pr.ps1 -Clone C:\Users\gbonthuy\cryoplant-project -Repo GBOGEB/cryoplant-project -Pr 2094 -Upstream <sha>
  # stacked PR: rebase onto its (just rebased) parent branch
  .\Restack-Pr.ps1 -Clone ... -Repo ... -Pr 967 -Upstream <old parent head sha>

  Needs git >= 2.40 (merge-tree --merge-base). Unset a dead GITHUB_TOKEN first if gh returns 401.
#>
param(
  [Parameter(Mandatory)][string]$Clone,
  [Parameter(Mandatory)][string]$Repo,
  [Parameter(Mandatory)][int[]]$Pr,
  [string]$Upstream,        # commit/ref to cut from (default: merge-base with the base branch)
  [string]$Onto,            # branch to rebase onto (default: the PR's base branch)
  [string]$Drop,            # regex on commit subject: drop these commits (e.g. generated-output regen; rerun the generator after)
  [switch]$Apply
)
$ErrorActionPreference = 'Stop'
function G { $o = & git -C $Clone @args; if ($LASTEXITCODE) { throw "git $args failed ($LASTEXITCODE)" }; $o }

# merge-tree --write-tree --merge-base needs git 2.40 or later; older git would misread the arguments.
$gv = (& git --version) -replace '^git version\s+', ''
if ($gv -notmatch '^(\d+)\.(\d+)' -or [version]"$($Matches[1]).$($Matches[2])" -lt [version]'2.40') {
  throw "Restack-Pr.ps1 needs git >= 2.40 (found '$gv')."
}
if (-not $Apply) { Write-Host 'DRY RUN: nothing is pushed and refs/heads/* is not changed (pass -Apply to push).' }

foreach ($n in $Pr) {
  $raw = gh pr view $n -R $Repo --json 'baseRefName,headRefName,headRefOid,isCrossRepository,state'
  if ($LASTEXITCODE -or -not $raw) { Write-Warning "#${n}: gh pr view failed ($LASTEXITCODE); skipped"; continue }   # never act on an empty answer
  $p = $raw | ConvertFrom-Json
  if ($p.state -ne 'OPEN' -or $p.isCrossRepository) { Write-Warning "#${n}: skipped (state=$($p.state), fork=$($p.isCrossRepository))"; continue }
  $ontoBranch = if ($Onto) { $Onto } else { $p.baseRefName }
  $ns = "refs/restack/$n"
  G fetch -q origin "+refs/heads/${ontoBranch}:$ns/onto" "+refs/heads/$($p.headRefName):$ns/head" | Out-Null
  $head = G rev-parse "$ns/head"
  if ($head -ne $p.headRefOid) { Write-Warning "#${n}: branch moved since gh read it ($head vs $($p.headRefOid)); skipped"; continue }
  $ontoSha = G rev-parse "$ns/onto"
  $cut = if ($Upstream) { G rev-parse "$Upstream^{commit}" } else { G merge-base $ontoSha $head }
  $commits = @(G rev-list --reverse --no-merges $head "^$cut" "^$ontoSha")
  Write-Host ("#{0} plan: replay {1} commit(s) of {2} ({3}) onto {4} ({5}), cut at {6}" -f $n, $commits.Count, $p.headRefName, $head.Substring(0,9), $ontoBranch, $ontoSha.Substring(0,9), $cut.Substring(0,9))
  $tip = $ontoSha; $conflict = $null; $skipped = 0
  foreach ($c in $commits) {
    if ($Drop -and ((G log -1 --format=%s $c) -match $Drop)) { $skipped++; Write-Host "    drop $(G log -1 --format='%h %s' $c)"; continue }
    $parent = G rev-parse "$c^"
    $out = @(& git -C $Clone merge-tree --write-tree --name-only --merge-base=$parent $tip $c)
    if ($LASTEXITCODE -eq 1) { $files = $out | Select-Object -Skip 1 | Where-Object { $_ -and $_ -notmatch '^(Auto-merging|CONFLICT)' } | Select-Object -Unique
      $conflict = [pscustomobject]@{ Commit = (G log -1 --format='%h %s' $c); Files = $files }; break }
    elseif ($LASTEXITCODE) { throw "merge-tree failed on $c" }
    $tree = $out[0]
    if ($tree -eq (G rev-parse "$tip^{tree}")) { $skipped++; Write-Host "    skip $(G log -1 --format='%h %s' $c) (already upstream)"; continue }   # like rebase
    Write-Host "    pick $(G log -1 --format='%h %s' $c)"
    $msg = New-TemporaryFile
    [IO.File]::WriteAllText($msg, ((G log -1 --format=%B $c) -join "`n") + "`n")
    $env:GIT_AUTHOR_NAME = G log -1 --format=%an $c; $env:GIT_AUTHOR_EMAIL = G log -1 --format=%ae $c
    $env:GIT_AUTHOR_DATE = G log -1 --format=%ad --date=raw $c
    try { $tip = G commit-tree $tree -p $tip -F $msg } finally { Remove-Item $msg; 'GIT_AUTHOR_NAME','GIT_AUTHOR_EMAIL','GIT_AUTHOR_DATE' | % { Remove-Item "env:$_" -EA SilentlyContinue } }
  }
  if ($conflict) {
    Write-Host "#${n} CONFLICT at $($conflict.Commit)" -ForegroundColor Red
    $conflict.Files | % { Write-Host "    $_" }
    continue
  }
  if ($tip -eq $ontoSha -and $commits.Count) { Write-Warning "#${n}: every commit is already upstream; nothing left to push"; continue }
  $sameTree = (G rev-parse "$tip^{tree}") -eq (G rev-parse "$head^{tree}")
  Write-Host ("#{0} CLEAN  {1} commits replayed onto {2} ({3} dropped by -Drop or already upstream){4}" -f $n, ($commits.Count - $skipped), $ontoBranch, $skipped, $(if ($sameTree) { ' - tree unchanged' } else { '' })) -ForegroundColor Green
  G update-ref "$ns/rebased" $tip | Out-Null
  Write-Host "    result: $ns/rebased = $($tip.Substring(0,9))"
  if ($Apply) {
    G push --force-with-lease="$($p.headRefName):$head" origin "${tip}:refs/heads/$($p.headRefName)" | Out-Null
    Write-Host "    pushed $($p.headRefName): $($head.Substring(0,9)) -> $($tip.Substring(0,9))"
  }
}
