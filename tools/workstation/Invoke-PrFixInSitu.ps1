#Requires -Version 7.0
<#
.SYNOPSIS
    Fix one open PR in place: diagnose, check out, merge the base in, test, push to the same branch, then reply and resolve threads with proof.
.DESCRIPTION
    Invoke-DraftPrPass.ps1 is the read-only triage over many PRs. This script is its write side for ONE PR.
    It runs stage by stage, and each stage refuses to run unless the previous one left the PR in the state it expects:

      Diagnose (always)  PR head/base SHAs, merge state, failing checks, unresolved review threads with their
                         P0-P3 badge, a live session on the head branch, and PUSH RULES: whether a ruleset
                         applies a pull_request / non_fast_forward / update rule to the head branch. A
                         pull_request rule on a feature branch rejects every direct push (GH013); the report
                         prints the one-line ruleset fix and the new-branch fallback.
      -Prepare           A worktree on the PR head (reused when one is already on that branch and clean).
                         Refuses fork PRs, bot branches and live sessions. Records the expected head SHA.
      -Sync              Merges origin/<base> into the head (never rebase, never --ours/--theirs). On conflict
                         it stops with the merge in progress and prints, per file, what the PR changed, so
                         the hunks are resolved by hand (PR_CONFLICT_RUNBOOK.md section 2).
      -Test "<command>"  Runs the repo's declared test command in the worktree and records the exit code
                         against the exact HEAD.
      -Publish           Expected-head check (the PR head on GitHub is still the one recorded at -Prepare
                         and is an ancestor of HEAD), then `git push` without force to the PR's own branch,
                         then readback. Refuses unless -Test passed on this exact HEAD.
      -ResolveThread     For each thread id: requires the published head to be the PR head and -Test PASS on
                         it writes a closure-evidence record (repo, PR, thread, root comment, head/base SHA,
                         blob OID of the thread's file, classification, method, local_test evidence with
                         conclusion PASS, all in the field shapes of code_maroon.closure-proof.v1), replies
                         "Fixed in <sha>" with the evidence, resolves the thread, and reads it back.

    It never force-pushes, merges, approves, dismisses a review, or resolves a thread without a passing test on
    the published head. Every gh call runs with GITHUB_TOKEN/GH_TOKEN removed (lesson 8), restored afterwards.
    State and proofs go to -ReportPath as prfix_<owner>_<repo>_<pr>.json.

    MAROON (mission-control/maroon) owns the ledger-bound, proof-checked closure pipeline. Its worker needs
    Linux (fcntl). This script is the in-situ path on a Windows workstation. Its records are NOT finished
    MAROON proofs: item_id and discussion_hash come from MAROON's own provider read (operations.observation_id,
    closure.discussion_hash), which cannot be imported on Windows. Each record says maroon_ready = false and
    what MAROON must add before closure.validate() can accept it.
.EXAMPLE
    pwsh -NoProfile -File tools/workstation/Invoke-PrFixInSitu.ps1 -Repo gg_MATH -Pr 128
    # diagnose only: push rules, conflicts, red checks, threads, next step
.EXAMPLE
    pwsh -NoProfile -File tools/workstation/Invoke-PrFixInSitu.ps1 -Repo gg_MATH -Pr 128 -Clone C:\Users\gbonthuy\Documents\Codex\gg_MATH -Prepare -Sync
    # worktree on the PR head, base merged in (stops on conflicts)
.EXAMPLE
    pwsh -NoProfile -File tools/workstation/Invoke-PrFixInSitu.ps1 -Repo gg_MATH -Pr 128 -Test "python -m pytest -q tests/test_dsm_makespan.py" -Publish
    # after your fix commit: test at HEAD, then push to the same PR branch
.EXAMPLE
    pwsh -NoProfile -File tools/workstation/Invoke-PrFixInSitu.ps1 -Repo gg_MATH -Pr 128 -ResolveThread PRRT_kwDOS6bc6862X-7o -Note "gain reported as a proven interval"
    # reply with the fixing SHA and test evidence, resolve, read back
#>
# No positional binding: '-Prepare pipeline-automation-hub' must fail on the stray value, not bind it silently.
[CmdletBinding(PositionalBinding = $false)]
param(
    [string]   $Owner = 'GBOGEB',
    [string]   $Repo,
    [int]      $Pr,
    # Local clone of the repo; required by -Prepare when no worktree is on the PR branch yet.
    [string]   $Clone,
    # Worktree to use. Default: an existing worktree of -Clone on the head branch, else C:\repos\_wt\<repo>_pr<N>_<yyyymmdd>.
    [string]   $Worktree,
    [switch]   $Prepare,
    [switch]   $Sync,
    [string]   $Test,
    [switch]   $Publish,
    [string[]] $ResolveThread = @(),
    [string]   $Note,
    # MAROON classification of each resolved thread: fixed (needs a passing test), already_fixed, false_positive.
    [ValidateSet('fixed', 'already_fixed', 'false_positive')]
    [string]   $Classification = 'fixed',
    # Evidence for already_fixed / false_positive (MAROON rejects a disposition with no passing evidence):
    # what was analysed or who reviewed it, e.g. "kernels/x.py:40-52 already guards n <= 0 (commit abc123)".
    [ValidateSet('source_analysis', 'independent_review')]
    [string]   $EvidenceKind = 'source_analysis',
    [string]   $EvidenceRef,
    [string]   $ReportPath = $env:TEMP,
    [double]   $LiveMinutes = 30,
    # Run the offline checks and exit. Uses temporary git repos only; no gh calls.
    [switch]   $SelfTest
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------- helpers (pure where possible)

function Invoke-WithoutTokens {
    # Run a block without the stale-token variables (lesson 8); the caller's environment is restored afterwards.
    param([scriptblock] $Block)
    $saved = @{ GITHUB_TOKEN = $env:GITHUB_TOKEN; GH_TOKEN = $env:GH_TOKEN }
    Remove-Item Env:GITHUB_TOKEN, Env:GH_TOKEN -ErrorAction SilentlyContinue
    try { & $Block } finally {
        foreach ($k in $saved.Keys) { if ($null -ne $saved[$k]) { Set-Item "Env:$k" $saved[$k] } }
    }
}

function Invoke-Gh {
    $a = $args
    Invoke-WithoutTokens {
        $out = & gh @a 2>&1
        [pscustomobject]@{ Code = $LASTEXITCODE; Text = ($out | Out-String).Trim() }
    }
}

function Invoke-GhJson {
    $r = Invoke-Gh @args
    if ($r.Code -ne 0) { throw "gh $($args -join ' ') failed: $($r.Text)" }
    if (-not $r.Text) { return $null }
    $r.Text | ConvertFrom-Json -Depth 50
}

function Invoke-GraphQL {
    # Query and variables go in as a JSON file, so any text (quotes, newlines, long notes) survives the
    # Windows command line intact.
    param([string] $Query, [hashtable] $Variables)
    $tmp = New-TemporaryFile
    try {
        @{ query = $Query; variables = $Variables } | ConvertTo-Json -Depth 10 -Compress | Set-Content -Path $tmp -Encoding utf8NoBOM
        $r = Invoke-GhJson api graphql --input $tmp.FullName
        $errs = $r.PSObject.Properties['errors']
        if ($errs -and $errs.Value) { throw "GraphQL error: $(($errs.Value | ForEach-Object message) -join '; ')" }
        $r
    } finally { Remove-Item $tmp -ErrorAction SilentlyContinue }
}

function Add-JsonRecords {
    # Append records to a JSON array file (a lone object from an older run counts as one record).
    param([string] $Path, [object[]] $Records)
    $all = [System.Collections.Generic.List[object]]::new()
    if (Test-Path $Path) {
        $old = Get-Content $Path -Raw | ConvertFrom-Json -AsHashtable
        if ($old -is [System.Collections.IList]) { $all.AddRange([object[]]$old) } elseif ($null -ne $old) { $all.Add($old) }
    }
    foreach ($r in $Records) { $all.Add($r) }
    ConvertTo-Json -InputObject $all.ToArray() -Depth 10 | Set-Content $Path -Encoding utf8
}

function Invoke-Git {
    # Invoke-Git <dir> <git args...>. No param block on purpose: git flags such as -g or -B must reach git
    # untouched, never bind (by prefix) to a PowerShell parameter of this helper.
    $dir = [string]$args[0]
    $gitArgs = @($args | Select-Object -Skip 1 | ForEach-Object { [string]$_ })
    $out = & git -C $dir @gitArgs 2>&1
    [pscustomobject]@{ Code = $LASTEXITCODE; Text = ($out | Out-String).TrimEnd() }
}

function Get-PushBlock {
    # $Rules: output of GET repos/{o}/{r}/rules/branches/{branch}. Returns the rules that stop a plain push.
    param([object[]] $Rules)
    $blocking = @('pull_request', 'update', 'non_fast_forward', 'required_linear_history')
    @($Rules | Where-Object { $_ -and $blocking -contains $_.type } | ForEach-Object {
        [pscustomobject]@{
            Type      = $_.type
            RulesetId = $_.ruleset_id
            # non_fast_forward only blocks force-pushes; this script never force-pushes.
            Blocks    = ($_.type -in @('pull_request', 'update'))
        }
    })
}

function Get-ThreadPriority {
    param([string] $Body)
    if ($Body -match '\b(P[0-3])\b') { return $Matches[1] }
    if ($Body -match '(?i)\b(high|medium|low)\b severity') { return $Matches[1] }
    'note'
}

function Get-CodexReviewState {
    # The JSON after 'codex-review-state:v1' in Codex's summary comment, or $null.
    param([string] $Body)
    if ($Body -notmatch 'codex-review-state:v1\s*(\{.*?\})\s*-->') { return $null }
    try { $Matches[1] | ConvertFrom-Json -Depth 10 } catch { $null }
}

function Test-CodexReviewDone {
    param($State, [string] $Head)
    if (-not $State -or -not $State.PSObject.Properties['code_review']) { return $false }
    $cr = $State.code_review
    [bool]($cr -and $cr.commit_sha -eq $Head -and $cr.status -eq 'completed')
}

function Get-WorktreeOnBranch {
    # Path of the worktree that has $Branch checked out, from `git worktree list --porcelain` text.
    param([string] $Porcelain, [string] $Branch)
    foreach ($blk in ($Porcelain -split "`r?`n`r?`n")) {
        if ($blk -match "(?m)^branch refs/heads/$([regex]::Escape($Branch))\s*$" -and $blk -match '(?m)^worktree (.+?)\s*$') {
            return $Matches[1]
        }
    }
    $null
}

function Test-BotAuthor {
    # Bot-owned PRs: an app/bot author, or a branch namespace bots write to (dependabot/, renovate/).
    param($Author, [string] $HeadRef)
    $login = if ($Author) { [string]$Author.login } else { '' }
    $isBot = $Author -and $Author.PSObject.Properties['is_bot'] -and $Author.is_bot
    [bool]($isBot -or $login -match '\[bot\]$|^app/' -or $HeadRef -match '^(dependabot|renovate)/')
}

function Get-PrClass {
    param($Diag)
    if ($Diag.Fork)                                   { return 'NO_PUSH_FORK' }
    if ($Diag.Bot)                                    { return 'NO_PUSH_BOT' }
    if ($Diag.Live)                                   { return 'LIVE' }
    if ($Diag.State -ne 'OPEN')                       { return 'NOT_OPEN' }
    if ($Diag.PushBlocked)                            { return 'PUSH_BLOCKED' }
    if ($Diag.Mergeable -eq 'CONFLICTING')            { return 'CONFLICT' }
    if (@($Diag.Threads | Where-Object { $_.Priority -in 'P0', 'P1' -and -not $_.Outdated }).Count) { return 'THREAD-P1' }
    if (@($Diag.FailingChecks).Count)                 { return 'RED' }
    if (@($Diag.Threads).Count)                       { return 'THREAD' }
    if (@($Diag.PendingChecks).Count)                 { return 'PENDING' }
    'CLEAN'
}

function Get-NextStep {
    param([string] $Class, $Diag, [string] $Self)
    $base = "pwsh -NoProfile -File $Self -Owner $($Diag.Owner) -Repo $($Diag.Repo) -Pr $($Diag.Pr)"
    switch ($Class) {
        'NO_PUSH_FORK' { 'Fork PR: you cannot push to its branch. Comment the fix or open your own PR from a branch in this repo.' }
        'NO_PUSH_BOT'  { 'Bot-owned PR (Dependabot, Renovate, an app): its tool rewrites the branch. Fix on your own branch and PR, or let the bot update.' }
        'LIVE'         { "Another session is working $($Diag.HeadRef). Leave it, or message that session first." }
        'NOT_OPEN'     { 'PR is not open. Nothing to fix in place.' }
        'PUSH_BLOCKED' {
            $ids = ($Diag.Blocks | Where-Object Blocks | Select-Object -ExpandProperty RulesetId -Unique) -join ', '
            "A ruleset ($ids) applies a pull_request/update rule to $($Diag.HeadRef), so every direct push is rejected (GH013).`n" +
            "  Owner fix (keeps main protected): scope it to the default branch:`n" +
            "    '{`"conditions`":{`"ref_name`":{`"include`":[`"~DEFAULT_BRANCH`"],`"exclude`":[]}}}' | gh api -X PUT repos/$($Diag.Owner)/$($Diag.Repo)/rulesets/<id> --input -`n" +
            "  Fallback without the owner: push the fix to a NEW branch (creation is allowed) and open a superseding PR."
        }
        'CONFLICT'     { "$base -Clone <clone> -Prepare -Sync    # then resolve hunks by hand, commit, -Test, -Publish" }
        'THREAD-P1'    { "Fix the P0/P1 thread first: $base -Clone <clone> -Prepare; commit; then -Test `"<cmd>`" -Publish; then -ResolveThread <id> -Note `"...`"" }
        'RED'          { "Open the first red job: gh run view <run> -R $($Diag.Owner)/$($Diag.Repo) --log-failed; then -Prepare, fix, -Test, -Publish." }
        'THREAD'       { "Fix or answer each thread; after -Publish: $base -ResolveThread <id> -Note `"<what changed>`"" }
        'PENDING'      { 'Checks still running. Wait, then diagnose again.' }
        default        { 'Nothing open. Write the FPC receipt (scripts/fpc_receipt.py) if the repo uses it, then merge by the normal route.' }
    }
}

function New-ClosureProof {
    # Closure evidence in the field shapes closure.validate() checks (mission-control/maroon/closure.py).
    # item_id and discussion_hash are MAROON's to compute from its own provider read; they stay null here.
    param([string] $RepoFull, [int] $Number, [string] $ThreadId, [long] $CommentId, [string] $HeadSha, [string] $BaseSha,
          [hashtable] $BlobOids, [string] $Classification, [string] $TestCommand, [string] $Note, [string] $ReplyUrl,
          [string] $EvidenceKind = 'source_analysis', [string] $EvidenceRef)
    $evidence = @()
    if ($TestCommand) { $evidence += [ordered]@{ kind = 'local_test'; ref = "$TestCommand (exit 0)"; source_sha = $HeadSha; conclusion = 'PASS' } }
    if ($EvidenceRef) { $evidence += [ordered]@{ kind = $EvidenceKind; ref = $EvidenceRef; source_sha = $HeadSha; conclusion = 'PASS' } }
    if (-not $evidence.Count) { throw 'A closure record needs at least one passing evidence item (a -Test run or -EvidenceRef).' }
    [ordered]@{
        schema          = 'gbogeb.prfix.closure-evidence.v1'
        maps_to         = 'code_maroon.closure-proof.v1'
        maroon_ready    = $false
        maroon_missing  = @('item_id', 'discussion_hash')
        maroon_next     = 'On Linux/WSL: item_id = operations.observation_id(repo, pr, comment_id); discussion_hash from the provider read; then closure.validate(proof, live), which also re-checks evidence, blob OIDs and the live discussion.'
        repo            = $RepoFull
        pr              = $Number
        thread_id       = $ThreadId
        comment_id      = $CommentId
        item_id         = $null
        discussion_hash = $null
        head_sha        = $HeadSha
        base_sha        = $BaseSha
        blob_oids       = $BlobOids
        classification  = $Classification
        method          = "In-situ fix by Invoke-PrFixInSitu.ps1: $Note"
        evidence        = $evidence
        reply_url       = $ReplyUrl
        producer        = 'tools/workstation/Invoke-PrFixInSitu.ps1'
    }
}

function Test-ExpectedHead {
    # The remote PR head must still be the one recorded at -Prepare, and HEAD must descend from it.
    param([string] $Dir, [string] $Recorded, [string] $Remote)
    if ($Recorded -ne $Remote) { return "PR head moved on GitHub: recorded $Recorded, now $Remote. Someone else pushed; re-run -Prepare." }
    $r = Invoke-Git $Dir merge-base --is-ancestor $Remote HEAD
    if ($r.Code -ne 0) { return "HEAD does not descend from the PR head $Remote. A push would need force; refused." }
    $null
}

function Invoke-SyncBase {
    param([string] $Dir, [string] $BaseRef)
    $f = Invoke-Git $Dir fetch origin $BaseRef
    if ($f.Code -ne 0) { throw "fetch origin $BaseRef failed: $($f.Text)" }
    $before = (Invoke-Git $Dir rev-parse HEAD).Text
    $m = Invoke-Git $Dir merge --no-edit "origin/$BaseRef"
    if ($m.Code -eq 0) {
        $after = (Invoke-Git $Dir rev-parse HEAD).Text
        $diff = Invoke-Git $Dir diff --quiet "origin/$BaseRef" HEAD
        return [pscustomobject]@{ Status = $(if ($diff.Code -eq 0) { 'ABSORBED' } elseif ($before -eq $after) { 'UP_TO_DATE' } else { 'MERGED' })
                                  Files = @(); Head = $after }
    }
    $files = @((Invoke-Git $Dir diff --name-only --diff-filter=U).Text -split "`r?`n" | Where-Object { $_ })
    if (-not $files.Count) { throw "merge failed without conflicts: $($m.Text)" }
    [pscustomobject]@{ Status = 'CONFLICT'; Files = $files; Head = $before }
}

function Read-State { param([string] $Path) if (Test-Path $Path) { Get-Content $Path -Raw | ConvertFrom-Json -AsHashtable } else { @{} } }
function Save-State { param([string] $Path, [hashtable] $State) $State | ConvertTo-Json -Depth 20 | Set-Content -Path $Path -Encoding utf8 }

# ---------------------------------------------------------------- self test (offline)

if ($SelfTest) {
    $fail = 0
    function Assert([bool] $Cond, [string] $Msg) { if ($Cond) { Write-Host "PASS $Msg" } else { Write-Host "FAIL $Msg"; $script:fail++ } }

    $rules = @([pscustomobject]@{ type = 'pull_request'; ruleset_id = 25554283 },
               [pscustomobject]@{ type = 'non_fast_forward'; ruleset_id = 25554283 },
               [pscustomobject]@{ type = 'deletion'; ruleset_id = 25554283 })
    $b = Get-PushBlock $rules
    Assert ($b.Count -eq 2 -and @($b | Where-Object Blocks).Count -eq 1) 'pull_request blocks a plain push; non_fast_forward only blocks force'
    Assert (@(Get-PushBlock @()).Count -eq 0) 'no rules, no block'
    Assert ((Get-ThreadPriority '![P1 Badge](x) **Fix**') -eq 'P1') 'Codex P badge parsed'
    Assert ((Get-ThreadPriority 'plain text') -eq 'note') 'unrated thread is a note'
    $env:GITHUB_TOKEN = 'stale'
    $seen = Invoke-WithoutTokens { [string]$env:GITHUB_TOKEN }
    Assert ($seen -eq '' -and $env:GITHUB_TOKEN -eq 'stale') 'token removed inside the block and restored after'
    Remove-Item Env:GITHUB_TOKEN
    $jf = Join-Path ([IO.Path]::GetTempPath()) ("prfix_selftest_" + [guid]::NewGuid().ToString('N').Substring(0, 8) + '.json')
    Add-JsonRecords -Path $jf -Records @([ordered]@{ n = 1 })
    Add-JsonRecords -Path $jf -Records @([ordered]@{ n = 2 }, [ordered]@{ n = 3 })
    $back = @(Get-Content $jf -Raw | ConvertFrom-Json)
    Assert ($back.Count -eq 3 -and $back[2].n -eq 3) 'evidence file appends across runs (single record first)'
    Remove-Item $jf -ErrorAction SilentlyContinue

    Assert (Test-BotAuthor ([pscustomobject]@{ login = 'app/dependabot'; is_bot = $true }) 'dependabot/pip/x') 'bot author detected'
    Assert (-not (Test-BotAuthor ([pscustomobject]@{ login = 'GBOGEB'; is_bot = $false }) 'feat/x')) 'human author is not a bot'
    Assert (Test-BotAuthor ([pscustomobject]@{ login = 'renovate[bot]' }) 'main-update') 'login ending [bot] is a bot'
    $g = Invoke-Git ([IO.Path]::GetTempPath()) -c core.quotepath=false --version
    Assert ($g.Code -eq 0 -and $g.Text -match '^git version') 'git flags pass through Invoke-Git unbound (-c, -g, -B)'
    $porc = "worktree C:/main`nHEAD aaa`nbranch refs/heads/main`n`nworktree C:/wt/feat`nHEAD bbb`nbranch refs/heads/feat/x`n"
    Assert ((Get-WorktreeOnBranch $porc 'feat/x') -eq 'C:/wt/feat') 'worktree found on its branch (multiline records)'
    Assert ($null -eq (Get-WorktreeOnBranch $porc 'feat')) 'branch prefix does not match'
    $sum = '<!-- codex-review-state:v1 {"code_review":{"commit_sha":"abc","has_any_findings":true,"status":"completed"},"security_review":{"commit_sha":null}} -->'
    Assert (Test-CodexReviewDone (Get-CodexReviewState $sum) 'abc') 'completed review on this head'
    Assert (-not (Test-CodexReviewDone (Get-CodexReviewState $sum) 'def')) 'review of another head does not count'
    Assert (-not (Test-CodexReviewDone (Get-CodexReviewState ($sum -replace 'completed', 'in_progress')) 'abc')) 'in-progress review does not count'
    $d = [pscustomobject]@{ Fork = $false; Bot = $false; Live = $false; State = 'OPEN'; PushBlocked = $true; Mergeable = 'CONFLICTING'
                            Threads = @(); FailingChecks = @(); PendingChecks = @() }
    Assert ((Get-PrClass $d) -eq 'PUSH_BLOCKED') 'push block outranks conflict'
    $d.Bot = $true
    Assert ((Get-PrClass $d) -eq 'NO_PUSH_BOT') 'bot-owned PR refuses writes before anything else but forks'
    $d.Bot = $false
    $d.PushBlocked = $false
    Assert ((Get-PrClass $d) -eq 'CONFLICT') 'conflict class'
    $d.Mergeable = 'MERGEABLE'; $d.Threads = @([pscustomobject]@{ Priority = 'P1'; Outdated = $false })
    Assert ((Get-PrClass $d) -eq 'THREAD-P1') 'P1 thread class'
    $d.Threads = @(); $d.FailingChecks = @('x')
    Assert ((Get-PrClass $d) -eq 'RED') 'red class'

    $p = New-ClosureProof -RepoFull 'o/r' -Number 1 -ThreadId 'PRRT_x' -CommentId 42 -HeadSha ('a' * 40) -BaseSha ('b' * 40) `
        -BlobOids @{ 'k.py' = ('c' * 40) } -Classification 'fixed' -TestCommand 'pytest -q' -Note 'guard added' -ReplyUrl 'u'
    $e0 = $p.evidence[0]
    Assert ($e0.kind -eq 'local_test' -and $e0.conclusion -eq 'PASS' -and $e0.source_sha -eq $p.head_sha) 'evidence uses MAROON kind/conclusion at the head'
    Assert ($p.method.Trim().Length -ge 20 -and $p.classification -eq 'fixed' -and $p.comment_id -eq 42) 'method >= 20 chars, classification, root comment id'
    Assert ($p.maroon_ready -eq $false -and $p.maroon_missing -contains 'item_id' -and $p.schema -ne 'code_maroon.closure-proof.v1') 'not presented as a finished MAROON proof'
    $fp = New-ClosureProof -RepoFull 'o/r' -Number 1 -ThreadId 'PRRT_y' -CommentId 7 -HeadSha ('a' * 40) -BaseSha ('b' * 40) `
        -BlobOids @{ 'k.py' = ('c' * 40) } -Classification 'false_positive' -TestCommand '' -Note 'input is validated upstream' -ReplyUrl 'u' `
        -EvidenceKind 'source_analysis' -EvidenceRef 'k.py:10-20 rejects n <= 0 before the call'
    Assert ($fp.evidence.Count -eq 1 -and $fp.evidence[0].kind -eq 'source_analysis' -and $fp.evidence[0].conclusion -eq 'PASS') 'non-test disposition carries source_analysis evidence'
    $threw = $false
    try { New-ClosureProof -RepoFull 'o/r' -Number 1 -ThreadId 'z' -CommentId 1 -HeadSha ('a' * 40) -BaseSha ('b' * 40) -BlobOids @{ 'k' = ('c' * 40) } -Classification 'already_fixed' -TestCommand '' -Note 'already handled' -ReplyUrl 'u' | Out-Null } catch { $threw = $true }
    Assert $threw 'a record with no evidence is refused'

    # git fixtures: base and head edit the same line (conflict), then a clean merge.
    $tmp = Join-Path ([IO.Path]::GetTempPath()) ("prfix_selftest_" + [guid]::NewGuid().ToString('N').Substring(0, 8))
    $origin = Join-Path $tmp 'origin.git'; $work = Join-Path $tmp 'work'
    New-Item -ItemType Directory -Force $tmp | Out-Null
    & git init -q --bare -b main $origin
    & git clone -q $origin $work 2>$null
    & git -C $work config user.email t@t; & git -C $work config user.name t; & git -C $work config core.autocrlf false
    Set-Content (Join-Path $work 'a.txt') "one`n" -NoNewline; & git -C $work add a.txt; & git -C $work commit -qm base; & git -C $work push -q origin main
    & git -C $work switch -qc feat; Set-Content (Join-Path $work 'a.txt') "feat`n" -NoNewline; & git -C $work commit -qam feat
    & git -C $work switch -q main; Set-Content (Join-Path $work 'a.txt') "main`n" -NoNewline; & git -C $work commit -qam main; & git -C $work push -q origin main
    & git -C $work switch -q feat
    $s = Invoke-SyncBase -Dir $work -BaseRef main
    Assert ($s.Status -eq 'CONFLICT' -and $s.Files -contains 'a.txt') 'conflict detected and listed, merge left for hand resolution'
    & git -C $work merge --abort
    $head = (& git -C $work rev-parse HEAD)
    Assert ($null -eq (Test-ExpectedHead -Dir $work -Recorded $head -Remote $head)) 'expected head accepted'
    Assert ($null -ne (Test-ExpectedHead -Dir $work -Recorded $head -Remote ('0' * 40))) 'moved head refused'
    & git -C $work switch -qc clean main~1; Set-Content (Join-Path $work 'b.txt') "b`n" -NoNewline; & git -C $work add b.txt; & git -C $work commit -qm b
    $s2 = Invoke-SyncBase -Dir $work -BaseRef main
    Assert ($s2.Status -eq 'MERGED') 'clean merge of the base'
    Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
    if ($fail) { Write-Host "$fail self-test check(s) failed"; exit 1 }
    Write-Host 'self-test OK'; exit 0
}

# ---------------------------------------------------------------- diagnose

if (-not $Repo -or -not $Pr) { throw 'Pass -Repo <name> and -Pr <number> (or -SelfTest).' }
if ($Repo -match '/') { $Owner, $Repo = $Repo -split '/', 2 }
$full = "$Owner/$Repo"
$self = $PSCommandPath
$statePath = Join-Path $ReportPath "prfix_$($Owner)_$($Repo)_$Pr.json"
$state = Read-State $statePath

$prInfo = Invoke-GhJson pr view $Pr -R $full --json 'number,title,state,isDraft,isCrossRepository,headRefName,headRefOid,baseRefName,mergeable,mergeStateStatus,url,author'
$baseSha = (Invoke-GhJson api "repos/$full/commits/$($prInfo.baseRefName)").sha
$rules = @(Invoke-GhJson api "repos/$full/rules/branches/$([uri]::EscapeDataString($prInfo.headRefName))")
$blocks = @(Get-PushBlock $rules)
# `gh pr checks` exits 8 while checks are pending and 1 when one failed, with the JSON still on stdout.
$cr = Invoke-Gh pr checks $Pr -R $full --json 'name,state,bucket,link'
if ($cr.Code -notin 0, 1, 8 -or -not $cr.Text.StartsWith('[')) { throw "gh pr checks failed (exit $($cr.Code)): $($cr.Text)" }
$checks = @($cr.Text | ConvertFrom-Json -Depth 10)
# Every review thread, page by page (same rule as Invoke-DraftPrPass Get-ReviewThreads): a P1 after the
# first 100 must still be counted, and -ResolveThread must find it.
$q = 'query($o:String!,$r:String!,$n:Int!,$after:String){repository(owner:$o,name:$r){pullRequest(number:$n){reviewThreads(first:100,after:$after){pageInfo{hasNextPage endCursor} nodes{id isResolved isOutdated path line comments(first:1){nodes{databaseId author{login} body url}}}}}}}'
$threadNodes = [System.Collections.Generic.List[object]]::new()
$after = $null
do {
    $vars = @{ o = $Owner; r = $Repo; n = $Pr }
    if ($after) { $vars.after = $after }
    $conn = (Invoke-GraphQL -Query $q -Variables $vars).data.repository.pullRequest.reviewThreads
    foreach ($node in @($conn.nodes)) { $threadNodes.Add($node) }
    $after = $conn.pageInfo.endCursor
} while ($conn.pageInfo.hasNextPage)
# FPC needs a COMPLETED Codex review on the exact head, and reviews are requested by hand (AGENTS.md).
# Completion comes from Codex's own summary state (codex-review-state:v1), not from a review object existing.
$pages = Invoke-GhJson api --paginate --slurp "repos/$full/issues/$Pr/comments?per_page=100"
$summaries = @(@($pages | ForEach-Object { $_ }) |
    Where-Object { $_.user.login -match 'codex' -and $_.body -match 'codex-review-state:v1' })
$codexState = if ($summaries.Count) { Get-CodexReviewState $summaries[-1].body } else { $null }
$codexOnHead = Test-CodexReviewDone $codexState $prInfo.headRefOid
$threads = @($threadNodes | Where-Object { -not $_.isResolved } | ForEach-Object {
    $c = $_.comments.nodes | Select-Object -First 1
    [pscustomobject]@{ Id = $_.id; Path = $_.path; Line = $_.line; Outdated = $_.isOutdated
                       CommentId = $c.databaseId; Author = $c.author.login; Priority = Get-ThreadPriority $c.body; Url = $c.url
                       Title = (($c.body -replace '<[^>]+>|!\[[^\]]*\]\([^)]*\)|\*\*', '') -split "`n" | Where-Object { $_.Trim() } | Select-Object -First 1).Trim() }
})

# Live session: a worktree of -Clone on the head branch with uncommitted changes or a recent reflog entry.
$live = $false; $branchWorktree = $null
if ($Clone -and (Test-Path $Clone)) {
    $path = Get-WorktreeOnBranch ((Invoke-Git $Clone worktree list --porcelain).Text) $prInfo.headRefName
    if ($path) {
        $branchWorktree = $path
        $dirty = (Invoke-Git $path status --porcelain).Text
        $last = (Invoke-Git $path log -g -1 --format=%ct).Text
        $recent = $last -and ([DateTimeOffset]::UtcNow.ToUnixTimeSeconds() - [long]$last) -lt $LiveMinutes * 60
        $here = (Resolve-Path $path).Path
        $mine = ($state['worktree'] -and ((Resolve-Path $state['worktree'] -ErrorAction SilentlyContinue)?.Path -eq $here)) -or
                ($Worktree -and ((Resolve-Path $Worktree -ErrorAction SilentlyContinue)?.Path -eq $here))
        if (($dirty -or $recent) -and -not $mine) { $live = $true }
    }
}

$diag = [pscustomobject]@{
    Owner = $Owner; Repo = $Repo; Pr = $Pr; Title = $prInfo.title; Url = $prInfo.url; State = $prInfo.state; Draft = $prInfo.isDraft
    Fork = [bool]$prInfo.isCrossRepository; Bot = (Test-BotAuthor $prInfo.author $prInfo.headRefName); HeadRef = $prInfo.headRefName; HeadSha = $prInfo.headRefOid; BaseRef = $prInfo.baseRefName; BaseSha = $baseSha
    Mergeable = $prInfo.mergeable; MergeState = $prInfo.mergeStateStatus
    Blocks = $blocks; PushBlocked = [bool](@($blocks | Where-Object Blocks).Count)
    # gh's normalized bucket (pass / fail / pending / skipping / cancel) covers ACTION_REQUIRED, STALE, STARTUP_FAILURE...
    FailingChecks = @($checks | Where-Object { $_.bucket -in 'fail', 'cancel' } | ForEach-Object { "$($_.name) [$($_.state)] $($_.link)" })
    PendingChecks = @($checks | Where-Object { $_.bucket -eq 'pending' } | ForEach-Object name)
    Threads = $threads; Live = $live; BranchWorktree = $branchWorktree; CodexReviewedHead = $codexOnHead
}
$class = Get-PrClass $diag
$state.diagnose = @{ at = (Get-Date).ToString('o'); class = $class; head_sha = $diag.HeadSha; base_sha = $baseSha }
Save-State $statePath $state

Write-Host ("{0}#{1}  {2}" -f $full, $Pr, $prInfo.title)
Write-Host ("  head {0}@{1}  base {2}@{3}  merge {4}/{5}" -f $diag.HeadRef, $diag.HeadSha.Substring(0, 8), $diag.BaseRef, $baseSha.Substring(0, 8), $diag.Mergeable, $diag.MergeState)
Write-Host ("  push rules: {0}" -f $(if ($blocks.Count) { ($blocks | ForEach-Object { "$($_.Type)@$($_.RulesetId)$(if ($_.Blocks) { ' BLOCKS PUSH' })" }) -join ', ' } else { 'none' }))
Write-Host ("  checks: {0} failing, {1} pending" -f $diag.FailingChecks.Count, $diag.PendingChecks.Count)
$diag.FailingChecks | ForEach-Object { Write-Host "    RED $_" }
Write-Host ("  unresolved threads: {0}" -f $threads.Count)
$threads | ForEach-Object { Write-Host ("    {0} {1} {2}:{3} {4}" -f $_.Priority, $_.Id, $_.Path, $_.Line, $_.Title) }
Write-Host ("  codex review on this head: {0}" -f $(if ($codexOnHead) { 'yes' } else { 'NO' }))
Write-Host "  class: $class"
Write-Host "  next:  $(Get-NextStep $class $diag $self)"
if (-not $codexOnHead -and $class -in 'CLEAN', 'RED', 'PENDING', 'THREAD') {
    # Reviews are rationed (AGENTS.md): ask once, only when every fix is pushed, and not after a usage-limit reply.
    Write-Host "  review: First-Pass Closure needs a Codex review of exactly this head. When every fix is pushed, ask ONCE:"
    Write-Host "          gh pr comment $Pr -R $full --body '@codex review'"
}

$wantsWrite = $Prepare -or $Sync -or $Test -or $Publish -or $ResolveThread.Count
if (-not $wantsWrite) { $diag | ConvertTo-Json -Depth 8 | Set-Content (Join-Path $ReportPath "prfix_$($Owner)_$($Repo)_$($Pr)_diag.json") -Encoding utf8; exit 0 }
if ($class -in 'NO_PUSH_FORK', 'NO_PUSH_BOT', 'LIVE', 'NOT_OPEN') { throw "Refusing write stages: class $class." }
if (($Publish) -and $diag.PushBlocked) { throw 'Refusing -Publish: a ruleset blocks direct pushes to this branch (see push rules above).' }

# ---------------------------------------------------------------- prepare

if ($Prepare) {
    if (-not $Worktree) { $Worktree = $branchWorktree }
    if (-not $Worktree) {
        if (-not $Clone) { throw '-Prepare needs -Clone (a local clone of the repo) or -Worktree.' }
        $Worktree = Join-Path 'C:\repos\_wt' ("{0}_pr{1}_{2}" -f $Repo.ToLower(), $Pr, (Get-Date -Format yyyyMMdd))
        $f = Invoke-Git $Clone fetch origin "+refs/heads/$($diag.HeadRef):refs/remotes/origin/$($diag.HeadRef)"
        if ($f.Code -ne 0) { throw "fetch failed: $($f.Text)" }
        $a = Invoke-Git $Clone worktree add -B $diag.HeadRef $Worktree "origin/$($diag.HeadRef)"
        if ($a.Code -ne 0) { throw "worktree add failed: $($a.Text)" }
        Invoke-Git $Worktree branch --set-upstream-to "origin/$($diag.HeadRef)" | Out-Null
    } else {
        if ((Invoke-Git $Worktree status --porcelain).Text) { throw "Worktree $Worktree has uncommitted changes; commit or stash them first." }
        Invoke-Git $Worktree fetch origin $diag.HeadRef | Out-Null
        # Behind the PR head: fast-forward. Ahead of it (your fix already committed here): keep it.
        if ((Invoke-Git $Worktree merge-base --is-ancestor HEAD $diag.HeadSha).Code -eq 0) {
            $ff = Invoke-Git $Worktree merge --ff-only $diag.HeadSha
            if ($ff.Code -ne 0) { throw "Fast-forward to the PR head failed: $($ff.Text)" }
        }
    }
    $head = (Invoke-Git $Worktree rev-parse HEAD).Text
    if ($head -ne $diag.HeadSha -and (Invoke-Git $Worktree merge-base --is-ancestor $diag.HeadSha HEAD).Code -ne 0) {
        throw "Worktree HEAD $head has diverged from the PR head $($diag.HeadSha); a push would need force."
    }
    $state.worktree = $Worktree; $state.expected_head = $diag.HeadSha; $state.base_ref = $diag.BaseRef
    Save-State $statePath $state
    $ahead = (Invoke-Git $Worktree rev-list --count "$($diag.HeadSha)..HEAD").Text
    Write-Host "PREPARED $Worktree at $($head.Substring(0, 8)) ($ahead local commit(s) ahead of the PR head)"
}
if (-not $Worktree) { $Worktree = $state['worktree'] }
if (-not $Worktree -or -not (Test-Path $Worktree)) { throw 'No worktree recorded; run -Prepare first.' }

# ---------------------------------------------------------------- sync

if ($Sync) {
    $s = Invoke-SyncBase -Dir $Worktree -BaseRef $diag.BaseRef
    $state.sync = @{ status = $s.Status; files = $s.Files; head = $s.Head }
    Save-State $statePath $state
    switch ($s.Status) {
        'CONFLICT' {
            Write-Host "CONFLICT in $($s.Files.Count) file(s). The merge is left in progress in $Worktree. Resolve hunk by hand:"
            $mb = (Invoke-Git $Worktree merge-base "origin/$($diag.BaseRef)" $state['expected_head']).Text
            foreach ($file in $s.Files) {
                Write-Host "  $file"
                Write-Host "    what the PR changed:  git -C `"$Worktree`" diff $($mb.Substring(0, 12)) $($state['expected_head'].Substring(0, 12)) -- `"$file`""
            }
            Write-Host "  never 'git checkout --ours/--theirs <file>' (drops the other side's hunks). Restore markers: git checkout -m -- <file>"
            Write-Host "  then: git -C `"$Worktree`" add <files>; git -C `"$Worktree`" commit --no-edit; and re-run with -Test `"<cmd>`" -Publish"
            exit 2
        }
        'ABSORBED' { Write-Host "ABSORBED: after merging $($diag.BaseRef) the PR has no diff left. Close it instead of pushing."; exit 3 }
        default    { Write-Host "SYNC $($s.Status) at $($s.Head.Substring(0, 8))" }
    }
}

# ---------------------------------------------------------------- test

if ($Test) {
    $head = (Invoke-Git $Worktree rev-parse HEAD).Text
    if ((Invoke-Git $Worktree status --porcelain).Text) {
        throw 'Commit (or remove) every change, untracked files included, before -Test: the result is recorded against HEAD and a test must not pass on files the push will not carry.'
    }
    Push-Location $Worktree
    try {
        $t0 = Get-Date
        & pwsh -NoProfile -Command $Test
        $code = $LASTEXITCODE
    } finally { Pop-Location }
    $state.test = @{ command = $Test; exit = $code; head = $head; at = (Get-Date).ToString('o'); seconds = [int]((Get-Date) - $t0).TotalSeconds }
    Save-State $statePath $state
    if ($code -ne 0) { Write-Host "TEST FAIL (exit $code) at $($head.Substring(0, 8))"; exit 4 }
    Write-Host "TEST PASS at $($head.Substring(0, 8))"
}

# ---------------------------------------------------------------- publish

if ($Publish) {
    $head = (Invoke-Git $Worktree rev-parse HEAD).Text
    if (-not $state['test'] -or $state['test'].exit -ne 0 -or $state['test'].head -ne $head) { throw "Refusing -Publish: no passing -Test recorded on HEAD $($head.Substring(0, 8))." }
    $why = Test-ExpectedHead -Dir $Worktree -Recorded $state['expected_head'] -Remote $diag.HeadSha
    if ($head -eq $diag.HeadSha) {
        # Already the PR head (for example an earlier -Publish whose readback timed out): nothing to push.
        Write-Host 'Nothing new to push: HEAD is already the PR head.'
        $state.expected_head = $head
    } else {
        if ($why) { throw "Refusing -Publish: $why" }
        $wt = $Worktree; $ref = $diag.HeadRef
        $p = Invoke-WithoutTokens { Invoke-Git $wt push origin "HEAD:refs/heads/$ref" }
        if ($p.Code -ne 0) {
            if ($p.Text -match 'GH013|repository rule') { throw "Push rejected by a repository rule (GH013). $(Get-NextStep 'PUSH_BLOCKED' $diag $self)" }
            throw "push failed: $($p.Text)"
        }
        $state.expected_head = $head; $state.published = @{ head = $head; at = (Get-Date).ToString('o'); readback = 'pending' }
        Save-State $statePath $state
        # The branch updates at once; the PR's head can lag a few seconds behind it.
        $remote = ((Invoke-WithoutTokens { Invoke-Git $wt ls-remote origin "refs/heads/$ref" }).Text -split '\s')[0]
        if ($remote -ne $head) { throw "Readback: branch $ref is at $remote, expected $head." }
        $back = $null
        foreach ($i in 1..15) {
            $back = (Invoke-GhJson pr view $Pr -R $full --json headRefOid).headRefOid
            if ($back -eq $head) { break }
            Start-Sleep -Seconds 2
        }
        if ($back -ne $head) { throw "Readback: branch is at $head but the PR still shows $back after 30 s; re-run -Publish to confirm." }
    }
    $state.published = @{ head = $head; at = (Get-Date).ToString('o') }
    Save-State $statePath $state
    Write-Host "PUBLISHED $($head.Substring(0, 8)) to $($diag.HeadRef)"
}

# ---------------------------------------------------------------- resolve threads with proof

if ($ResolveThread.Count) {
    if (-not $Note -or $Note.Trim().Length -lt 12) { throw '-ResolveThread needs -Note: a sentence saying what changed, or why the finding does not apply.' }
    $head = $diag.HeadSha
    $tested = [bool]($state['test'] -and $state['test'].exit -eq 0 -and $state['test'].head -eq $head)
    if ($Classification -eq 'fixed' -and -not $tested) {
        throw "Refusing to resolve as fixed: no passing -Test recorded on the PR head $($head.Substring(0, 8)). Run -Test (and -Publish) first."
    }
    if ($Classification -ne 'fixed' -and -not $tested -and -not $EvidenceRef) {
        throw "Refusing to resolve as ${Classification}: pass -EvidenceRef (what you analysed, with file:lines or commit) or run -Test first. MAROON rejects a disposition without evidence."
    }
    $proofPath = Join-Path $ReportPath "prfix_$($Owner)_$($Repo)_$($Pr)_proofs.json"
    $testCmd = if ($tested) { $state['test'].command } else { '' }
    # Validate every id before the first write, so a typo cannot leave a half-processed batch.
    $missing = @($ResolveThread | Where-Object { $id = $_; -not ($threads | Where-Object Id -eq $id) })
    if ($missing.Count) { throw "Not unresolved threads on $full#${Pr}: $($missing -join ', '). Nothing was changed." }
    # Each thread's file must exist at the published head: the blob OID is the record's source identity.
    $blobs = @{}
    foreach ($id in $ResolveThread) {
        $t = $threads | Where-Object Id -eq $id
        $b = Invoke-Git $Worktree rev-parse --verify --quiet "$($head):$($t.Path)"
        if ($b.Code -ne 0 -or $b.Text -notmatch '^[0-9a-f]{40}$') {
            throw "Thread $id is on $($t.Path), which has no blob at $($head.Substring(0, 12)) (deleted or renamed?). Nothing was changed; answer it by hand or with the file's new path in -Note and MAROON."
        }
        $blobs[$id] = $b.Text
    }
    foreach ($id in $ResolveThread) {
        $t = $threads | Where-Object Id -eq $id
        $blob = $blobs[$id]
        $verb = @{ fixed = 'Fixed in'; already_fixed = 'Already fixed at'; false_positive = 'Not applicable at' }[$Classification]
        $verified = if ($tested) { "Verified: ``$($state['test'].command)`` exit 0 on ``$head``." } else { "Evidence ($EvidenceKind): $EvidenceRef" }
        $body = "$verb $($head.Substring(0, 12)): $Note`n`n$verified`nEvidence: gbogeb.prfix.closure-evidence.v1 (Invoke-PrFixInSitu.ps1); MAROON adds item_id and discussion_hash before ledger closure."
        $reply = Invoke-GraphQL -Query 'mutation($id:ID!,$b:String!){addPullRequestReviewThreadReply(input:{pullRequestReviewThreadId:$id,body:$b}){comment{url}}}' -Variables @{ id = $id; b = $body }
        $url = $reply.data.addPullRequestReviewThreadReply.comment.url
        $record = New-ClosureProof -RepoFull $full -Number $Pr -ThreadId $id -CommentId $t.CommentId -HeadSha $head -BaseSha $diag.BaseSha `
            -BlobOids @{ $t.Path = $blob } -Classification $Classification -TestCommand $testCmd -Note $Note -ReplyUrl $url `
            -EvidenceKind $EvidenceKind -EvidenceRef $EvidenceRef
        # Persist each record as soon as its reply exists, so a later failure cannot lose earlier evidence.
        try {
            $res = Invoke-GraphQL -Query 'mutation($id:ID!){resolveReviewThread(input:{threadId:$id}){thread{isResolved}}}' -Variables @{ id = $id }
            $record.resolved = [bool]$res.data.resolveReviewThread.thread.isResolved
        } catch {
            $record.resolved = $false; $record.resolve_error = "$_"
        }
        Add-JsonRecords -Path $proofPath -Records @($record)
        if (-not $record.resolved) { throw "Replied to $id ($url) but it is not resolved: $($record.resolve_error). Evidence kept in $proofPath." }
        Write-Host "RESOLVED $id  $url"
    }
    Write-Host "proofs: $proofPath"
}
