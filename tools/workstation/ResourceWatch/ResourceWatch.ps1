<#
ResourceWatch - disk and memory watchdog for this PC (Windows PowerShell 5.1).

Modes
  Check      Run by the scheduled task every few minutes. Measures C: and RAM, clears regenerable
             caches according to the disk band (config.json), and shows a notification.
  Review     Opened from a notification's "Review" button. Pick idle programs to close (a normal
             close request, so unsaved work prompts as usual) or open Edge's tab-discard page.
  Status     Print the measurements, bands, pending clean-ups and close candidates. Changes nothing.
  Unpin      Background job: mark OneDrive files idle for -UnpinDays as online-only.
  Install    Register the scheduled task and the resourcewatch: link used by notifications.
  Uninstall  Remove both again (this folder and its log stay).

Never deletes user documents, never empties the Recycle Bin, never force-kills a program.
#>
param(
    [ValidateSet('Check', 'Review', 'Status', 'Unpin', 'Install', 'Uninstall')][string]$Mode = 'Check',
    [int]$UnpinDays = 90,
    [double]$SimulateFreeGB = -1,
    [double]$SimulateAvailPct = -1,
    [switch]$DryRun,
    [switch]$TestToast,
    [string]$Url,
    [string]$ConfigPath,
    [switch]$LoadOnly   # define functions only (tests dot-source the script with this)
)
$ErrorActionPreference = 'Continue'
$Here = $PSScriptRoot
if (-not $ConfigPath) {
    # config.json is the local copy; the repo ships config.example.json.
    $ConfigPath = Join-Path $Here 'config.json'
    if (-not (Test-Path $ConfigPath)) { $ConfigPath = Join-Path $Here 'config.example.json' }
}
$Config = Get-Content $ConfigPath -Raw | ConvertFrom-Json
$StatePath = Join-Path $Here 'state.json'
$LogPath = Join-Path $Here 'watch.log'
$TaskName = 'ResourceWatch'
$Protocol = 'resourcewatch'
$PsExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'

$FILE_PINNED = 0x80000
$FILE_UNPINNED = 0x100000
$FILE_RECALL = 0x400000
$FILE_OFFLINE = 0x1000

if (-not ('RWNative' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class RWNative {
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern bool SetFileAttributesW(string path, uint attrs);
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [StructLayout(LayoutKind.Sequential)] struct LII { public uint cbSize; public uint dwTime; }
    [DllImport("user32.dll")] static extern bool GetLastInputInfo(ref LII info);
    public static int ForegroundPid() { uint pid; GetWindowThreadProcessId(GetForegroundWindow(), out pid); return (int)pid; }
    public static double InputIdleMinutes() {
        var l = new LII(); l.cbSize = (uint)Marshal.SizeOf(l);
        if (!GetLastInputInfo(ref l)) return 0;
        return unchecked((uint)Environment.TickCount - l.dwTime) / 60000.0;
    }
}
'@
}

# ---------- helpers ----------

function Write-Log([string]$Message) {
    if ((Test-Path $LogPath) -and (Get-Item $LogPath).Length -gt 2MB) {
        Move-Item $LogPath "$LogPath.old" -Force
    }
    Add-Content -Path $LogPath -Value ('{0:yyyy-MM-dd HH:mm:ss}  {1}' -f (Get-Date), $Message) -Encoding UTF8
}

function ConvertTo-Hash($Object) {
    if ($null -eq $Object) { return $null }
    if ($Object -is [System.Management.Automation.PSCustomObject]) {
        $h = @{}
        foreach ($p in $Object.PSObject.Properties) { $h[$p.Name] = ConvertTo-Hash $p.Value }
        return $h
    }
    if ($Object -is [System.Collections.IEnumerable] -and $Object -isnot [string]) {
        return , @($Object | ForEach-Object { ConvertTo-Hash $_ })
    }
    return $Object
}

function Read-State {
    $s = $null
    if (Test-Path $StatePath) {
        try { $s = ConvertTo-Hash (Get-Content $StatePath -Raw | ConvertFrom-Json) } catch { $s = $null }
    }
    if ($null -eq $s) { $s = @{} }
    foreach ($k in 'lastNotify', 'lastCleanup', 'foreground', 'cpu', 'oneDrive') {
        if ($s[$k] -isnot [hashtable]) { $s[$k] = @{} }
    }
    foreach ($k in 'freeHistory', 'oneDriveRestarts') {
        if ($null -eq $s[$k]) { $s[$k] = @() } else { $s[$k] = @($s[$k]) }
    }
    if (-not $s['firstRun']) { $s['firstRun'] = (Get-Date).ToString('o') }
    return $s
}

function Save-State($State) {
    if ($DryRun) { return }
    $State | ConvertTo-Json -Depth 6 | Set-Content -Path $StatePath -Encoding UTF8
}

function To-Date($Value) {
    if ($Value -is [datetime]) { return $Value }
    return [datetime]::Parse([string]$Value, [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::RoundtripKind)
}

function Get-MinutesSince([hashtable]$Table, [string]$Key) {
    if (-not $Table.ContainsKey($Key) -or -not $Table[$Key]) { return [double]::MaxValue }
    return ((Get-Date) - (To-Date $Table[$Key])).TotalMinutes
}

function Format-GB([double]$Bytes) { '{0:N1} GB' -f ($Bytes / 1GB) }

function Get-FolderBytes([string]$Path) {
    if (-not (Test-Path $Path)) { return 0 }
    $sum = (Get-ChildItem $Path -Recurse -Force -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
    if ($sum) { return [double]$sum } else { return 0 }
}

function Get-PagefileBytes {
    # The page file causes most 'unexplained' free-space swings (#1166 section 3): log it with every snapshot.
    $f = Get-Item (Join-Path "$($Config.disk.drive):\" 'pagefile.sys') -Force -ErrorAction SilentlyContinue
    if ($f) { return [double]$f.Length } else { return 0 }
}

function Test-IsLink($Item) {
    # Junctions and symlinks point elsewhere (often at a repo or OneDrive): never descend into or delete through them.
    return [bool]($Item.Attributes -band [IO.FileAttributes]::ReparsePoint)
}

function Remove-TreeChildren([string]$Path) {
    # Delete each child on its own, so one locked folder (e.g. a .pytest_cache husk) does not stop its siblings.
    # -Confirm:$false: a confirmation prompt fails in the non-interactive scheduled task.
    $freed = 0
    foreach ($c in Get-ChildItem -LiteralPath $Path -Force -ErrorAction SilentlyContinue) {
        if (Test-IsLink $c) { continue }
        if ($c.PSIsContainer) {
            $freed += Remove-TreeChildren $c.FullName
            try { Remove-Item -LiteralPath $c.FullName -Force -Confirm:$false -ErrorAction Stop } catch { }
        } else {
            $len = [double]$c.Length
            try { Remove-Item -LiteralPath $c.FullName -Force -Confirm:$false -ErrorAction Stop; $freed += $len } catch { }
        }
    }
    return $freed
}

function Get-RecycleBinBytes {
    try {
        $items = (New-Object -ComObject Shell.Application).NameSpace(10).Items()
        $sum = ($items | Measure-Object -Property Size -Sum).Sum
        if ($sum) { return [double]$sum }
    } catch { }
    return 0
}

# ---------- notifications ----------

function Show-Toast([string]$Title, [string]$Body, [string]$Level) {
    Write-Log "NOTIFY [$Level] $Title | $Body"
    if ($DryRun -and -not $TestToast) { return }
    if ($PSVersionTable.PSVersion.Major -gt 5) { return }  # WinRT toasts need Windows PowerShell 5.1
    try {
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
        $esc = { param($t) [Security.SecurityElement]::Escape($t) }
        $scenario = ''
        if ($Level -in 'critical', 'emergency', 'clogged') { $scenario = ' scenario="reminder"' }
        $logUri = 'file:///' + ($LogPath -replace '\\', '/' -replace ' ', '%20')
        $xml = @"
<toast$scenario activationType="protocol" launch="${Protocol}:review">
  <visual><binding template="ToastGeneric">
    <text>$(& $esc $Title)</text>
    <text>$(& $esc $Body)</text>
  </binding></visual>
  <actions>
    <action content="Review" activationType="protocol" arguments="${Protocol}:review"/>
    <action content="Open log" activationType="protocol" arguments="$(& $esc $logUri)"/>
  </actions>
</toast>
"@
        $doc = New-Object Windows.Data.Xml.Dom.XmlDocument
        $doc.LoadXml($xml)
        $toast = New-Object Windows.UI.Notifications.ToastNotification $doc
        $aumid = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($aumid).Show($toast)
    } catch {
        Write-Log "toast failed: $($_.Exception.Message)"
    }
}

# ---------- disk ----------

function Get-FreeGB {
    if ($SimulateFreeGB -ge 0) { return $SimulateFreeGB }
    return [math]::Round((Get-PSDrive $Config.disk.drive).Free / 1GB, 2)
}

function Get-DiskBand([double]$FreeGB) {
    $band = $null
    foreach ($b in ($Config.disk.bands | Sort-Object maxFreeGB -Descending)) {
        if ($FreeGB -le $b.maxFreeGB) { $band = $b }
    }
    return $band
}

function Get-CleanupsFor($Band) {
    if ($null -eq $Band) { return @() }
    $list = @()
    foreach ($b in ($Config.disk.bands | Sort-Object maxFreeGB -Descending)) {
        if ($b.maxFreeGB -ge $Band.maxFreeGB) { $list += @($b.cleanup) }
    }
    # A deeper band's version of a clean-up replaces the milder one.
    if ($list -contains 'temp1') { $list = $list | Where-Object { $_ -notin 'temp7', 'temp2' } }
    elseif ($list -contains 'temp2') { $list = $list | Where-Object { $_ -ne 'temp7' } }
    if ($list -contains 'oneDriveUnpin30') { $list = $list | Where-Object { $_ -ne 'oneDriveUnpin90' } }
    return @($list | Select-Object -Unique)
}

function Invoke-WithTimeout([string]$Exe, [string[]]$Arguments, [int]$Seconds) {
    # External tools must never stall the check: kill them after $Seconds.
    $p = Start-Process $Exe -ArgumentList $Arguments -WindowStyle Hidden -PassThru
    if (-not $p.WaitForExit($Seconds * 1000)) {
        Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
        Write-Log "timed out after $Seconds s: $Exe $($Arguments -join ' ')"
    }
}

function Remove-OlderThan([string]$Path, [double]$Days, [string[]]$Keep = @()) {
    if (-not (Test-Path $Path)) { return 0 }
    $cut = (Get-Date).AddDays(-$Days)
    $freed = 0
    foreach ($item in Get-ChildItem $Path -Force -ErrorAction SilentlyContinue) {
        if ($item.Name -in $Keep -or $item.LastWriteTime -ge $cut) { continue }
        if (Test-IsLink $item) { continue }   # junction: skip, never follow
        if ($item.PSIsContainer) {
            $freed += Remove-TreeChildren $item.FullName
            try { Remove-Item -LiteralPath $item.FullName -Force -Confirm:$false -ErrorAction Stop } catch { }
        } else {
            $len = [double]$item.Length
            try { Remove-Item -LiteralPath $item.FullName -Force -Confirm:$false -ErrorAction Stop; $freed += $len } catch { }   # in use: skip
        }
    }
    return $freed
}

function Invoke-Cleanup([string]$Name, [hashtable]$State, [bool]$Urgent) {
    $cooldown = $Config.disk.cleanupCooldownMin
    if ($Name -like 'oneDriveUnpin*') { $cooldown = $Config.disk.unpinCooldownMin }
    if ($Name -eq 'openStorageSettings') { $cooldown = 60 }
    if ($Urgent -and $Name -notlike 'oneDriveUnpin*') { $cooldown = 30 }
    if ((Get-MinutesSince $State.lastCleanup $Name) -lt $cooldown) { return 0 }
    if ($DryRun) { Write-Log "dry run: would run clean-up $Name"; return 0 }
    $State.lastCleanup[$Name] = (Get-Date).ToString('o')
    Write-Log "clean-up $Name starting"
    $freed = 0
    switch ($Name) {
        'temp7'      { $freed = Remove-OlderThan $env:TEMP 7 @('claude') }
        'temp2'      { $freed = Remove-OlderThan $env:TEMP 2 @('claude') }
        'temp1'      { $freed = Remove-OlderThan $env:TEMP 1 @('claude') }
        'crashDumps' { $freed = Remove-OlderThan (Join-Path $env:LOCALAPPDATA 'CrashDumps') 0 }
        'werReports' {
            foreach ($sub in 'ReportArchive', 'ReportQueue') {
                $freed += Remove-OlderThan (Join-Path $env:LOCALAPPDATA "Microsoft\Windows\WER\$sub") 0
            }
        }
        'npmCache' {
            # Delete the cache folder directly: calling npm can hang (on this PC it resolves to an npm.ps1 inside OneDrive).
            $dir = Join-Path $env:LOCALAPPDATA 'npm-cache'
            $before = Get-FolderBytes $dir
            foreach ($sub in '_cacache', '_npx') {
                Remove-Item (Join-Path $dir $sub) -Recurse -Force -Confirm:$false -ErrorAction SilentlyContinue
            }
            $freed = $before - (Get-FolderBytes $dir)
        }
        'pipCache' {
            $dir = Join-Path $env:LOCALAPPDATA 'pip\cache'
            $before = Get-FolderBytes $dir
            $py = Get-Command python.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($py) { Invoke-WithTimeout $py.Source @('-m', 'pip', 'cache', 'purge') 120 }
            $freed = $before - (Get-FolderBytes $dir)
        }
        'vscodeOldServers' {
            # VS Code downloads its server again when needed; keep the newest one.
            $dir = Join-Path $env:USERPROFILE '.vscode\cli\servers'
            if (Test-Path $dir) {
                $old = Get-ChildItem $dir -Directory | Sort-Object LastWriteTime -Descending | Select-Object -Skip 1
                foreach ($d in $old) {
                    $size = Get-FolderBytes $d.FullName
                    try { Remove-Item $d.FullName -Recurse -Force -Confirm:$false -ErrorAction Stop; $freed += $size } catch { }
                }
            }
        }
        'oneDriveUnpin90' { Start-UnpinJob 90 }
        'oneDriveUnpin30' { Start-UnpinJob 30 }
        'openStorageSettings' { Start-Process 'ms-settings:storagesense' }
    }
    if ($freed -lt 0) { $freed = 0 }
    Write-Log ("clean-up {0}: freed {1}" -f $Name, (Format-GB $freed))
    return $freed
}

function Start-UnpinJob([int]$Days) {
    $lock = Join-Path $Here 'unpin.lock'
    if (Test-Path $lock) {
        $pidText = Get-Content $lock -ErrorAction SilentlyContinue
        if ($pidText -and (Get-Process -Id ([int]$pidText) -ErrorAction SilentlyContinue)) { return }
    }
    Start-Process $PsExe -WindowStyle Hidden -ArgumentList @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`"", '-Mode', 'Unpin', '-UnpinDays', $Days)
    Write-Log "started OneDrive online-only pass for files idle $Days+ days"
}

function Invoke-Unpin([int]$Days, [hashtable]$State) {
    $root = $env:OneDriveCommercial
    if (-not $root) { $root = $env:OneDrive }
    if (-not $root -or -not (Test-Path $root)) { Write-Log 'unpin: no OneDrive folder'; return }
    Set-Content (Join-Path $Here 'unpin.lock') $PID
    $cut = (Get-Date).AddDays(-$Days)
    $marked = 0; $markedBytes = 0.0; $waiting = 0.0; $pinned = 0.0; $cloud = 0.0
    $stack = New-Object System.Collections.Stack
    $stack.Push((Get-Item -LiteralPath $root))
    while ($stack.Count -gt 0) {
        $dir = $stack.Pop()
        try { $entries = @($dir.EnumerateFileSystemInfos()) } catch { continue }
        foreach ($e in $entries) {
            $a = [int]$e.Attributes
            if ($e -is [IO.DirectoryInfo]) {
                if ($e.Name -ne '.git' -and -not ($a -band $FILE_PINNED)) { $stack.Push($e) }
                continue
            }
            if ($a -band ($FILE_RECALL -bor $FILE_OFFLINE)) { $cloud += $e.Length; continue }
            if ($a -band $FILE_PINNED) { $pinned += $e.Length; continue }
            if ($a -band $FILE_UNPINNED) { $waiting += $e.Length; continue }
            if ($e.LastWriteTime -ge $cut) { continue }
            $new = [uint32](($a -band 0xFFBFF) -bor $FILE_UNPINNED)
            if ([RWNative]::SetFileAttributesW($e.FullName, $new)) {
                $marked++; $markedBytes += $e.Length; $waiting += $e.Length
            }
        }
    }
    $State.oneDrive['lastUnpin'] = (Get-Date).ToString('o')
    $State.oneDrive['waitingBytes'] = $waiting
    $State.oneDrive['cloudBytes'] = $cloud
    $State.oneDrive['pinnedBytes'] = $pinned
    Write-Log ("unpin {0}d: marked {1} files ({2}); waiting for upload {3}; online-only {4}" -f `
        $Days, $marked, (Format-GB $markedBytes), (Format-GB $waiting), (Format-GB $cloud))
    Remove-Item (Join-Path $Here 'unpin.lock') -Force -ErrorAction SilentlyContinue
}

function Test-OneDrive([hashtable]$State, [double]$FreeGB) {
    # Returns a short problem description, or '' when OneDrive looks healthy.
    $problem = ''
    # Right after boot OneDrive has not started yet; that is not a crash.
    $uptimeMin = ((Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime).TotalMinutes
    if ($uptimeMin -ge 10 -and -not (Get-Process OneDrive -ErrorAction SilentlyContinue)) {
        $exe = Join-Path $env:ProgramFiles 'Microsoft OneDrive\OneDrive.exe'
        if (-not (Test-Path $exe)) { $exe = Join-Path $env:LOCALAPPDATA 'Microsoft\OneDrive\OneDrive.exe' }
        if ((Test-Path $exe) -and -not $DryRun) {
            Start-Process $exe -ArgumentList '/background'
            $State.oneDriveRestarts = @($State.oneDriveRestarts) + (Get-Date).ToString('o')
            Write-Log 'OneDrive was not running: started it'
        }
        $recent = @($State.oneDriveRestarts | Where-Object { ((Get-Date) - (To-Date $_)).TotalHours -lt 24 })
        $State.oneDriveRestarts = $recent
        if ($recent.Count -ge 3) { $problem = "OneDrive stopped $($recent.Count) times in 24 h. Consider Settings > Account > Unlink this PC, then sign in again." }
    }
    $diag = Join-Path $env:LOCALAPPDATA 'Microsoft\OneDrive\logs\Business1\SyncDiagnostics.log'
    if (Test-Path $diag) {
        $stamp = (Get-Item $diag).LastWriteTime.ToString('o')
        $line = Select-String -Path $diag -Pattern '^driveChangesToSend = (\d+)' | Select-Object -First 1
        if ($line -and $State.oneDrive['queueStamp'] -ne $stamp) {
            $n = [int]$line.Matches[0].Groups[1].Value
            $prev = $State.oneDrive['queue']
            if ($null -eq $prev -or $n -lt [int]$prev) { $State.oneDrive['queueSince'] = $stamp }
            $State.oneDrive['queue'] = $n
            $State.oneDrive['queueStamp'] = $stamp
        }
        $since = $State.oneDrive['queueSince']
        if ($since -and $State.oneDrive['queue'] -gt 0 -and $FreeGB -le 20) {
            $hours = ((Get-Date) - (To-Date $since)).TotalHours
            if ($hours -ge $Config.disk.oneDriveStalledAfterHours) {
                $problem = ("OneDrive upload queue ({0:N0} changes) has not shrunk for {1:N0} h. Open the OneDrive icon and check sync issues." -f $State.oneDrive['queue'], $hours)
            }
        }
    }
    return $problem
}

function Get-TopWriters([hashtable]$State) {
    $now = @{}
    foreach ($p in Get-CimInstance Win32_Process -Property ProcessId, Name, WriteTransferCount -ErrorAction SilentlyContinue) {
        $now["$($p.ProcessId)"] = @{ name = $p.Name; w = [double]$p.WriteTransferCount }
    }
    $prev = $State['writes']
    $State['writes'] = @{}
    foreach ($k in $now.Keys) { $State['writes'][$k] = $now[$k].w }
    if ($prev -isnot [hashtable]) { return @() }
    $deltas = foreach ($k in $now.Keys) {
        if ($prev.ContainsKey($k)) {
            [pscustomobject]@{ Name = $now[$k].name; Bytes = $now[$k].w - [double]$prev[$k] }
        }
    }
    return @($deltas | Group-Object Name | ForEach-Object {
            [pscustomobject]@{ Name = $_.Name; Bytes = ($_.Group | Measure-Object Bytes -Sum).Sum } } |
        Sort-Object Bytes -Descending | Select-Object -First 3)
}

function Invoke-DiskCheck([hashtable]$State) {
    $free = Get-FreeGB
    $now = Get-Date
    $State.freeHistory = @(@($State.freeHistory) + @{ t = $now.ToString('o'); gb = $free } |
        Where-Object { ($now - (To-Date $_.t)).TotalHours -lt 48 })
    $band = Get-DiskBand $free
    $cl = $Config.disk.clogged

    # Clogged = practically full, writes failing, or space vanishing fast.
    $reasons = @()
    if ($free -lt $cl.freeBelowGB) { $reasons += "only $free GB free" }
    if (-not $DryRun -and $SimulateFreeGB -lt 0) {
        $probe = Join-Path $env:TEMP 'resourcewatch.probe'
        try { [IO.File]::WriteAllBytes($probe, (New-Object byte[] 1MB)); Remove-Item $probe -Force }
        catch { $reasons += 'cannot write to disk' }
    }
    $window = @($State.freeHistory | Where-Object { ($now - (To-Date $_.t)).TotalMinutes -le $cl.runawayWindowMin })
    $peak = ($window | ForEach-Object { [double]$_.gb } | Measure-Object -Maximum).Maximum
    $writers = Get-TopWriters $State
    $runaway = ''
    if ($peak -and ($peak - $free) -ge $cl.runawayDropGB) {
        $who = ($writers | Where-Object Bytes -gt 100MB | ForEach-Object { '{0} ({1})' -f $_.Name, (Format-GB $_.Bytes) }) -join ', '
        $runaway = ('Lost {0:N1} GB in {1} min{2}.' -f ($peak - $free), $cl.runawayWindowMin, $(if ($who) { "; biggest writers: $who" } else { '' }))
        # A fast drop is only an emergency once space is already short.
        if ($free -le $cl.runawayCloggedBelowGB) { $reasons += $runaway.TrimEnd('.') }
    }
    $clogged = $reasons.Count -gt 0

    # Clogged runs every clean-up we have, whatever the band.
    $cleanBand = if ($clogged) { $Config.disk.bands | Sort-Object maxFreeGB | Select-Object -First 1 } else { $band }
    $freed = 0
    foreach ($c in (Get-CleanupsFor $cleanBand)) {
        $freed += Invoke-Cleanup $c $State ($clogged -or ($band -and $band.level -eq 'emergency'))
    }
    $oneDriveProblem = Test-OneDrive $State $free

    $prevBand = $State['diskBand']
    $bandName = if ($clogged) { 'clogged' } elseif ($band) { $band.name } else { 'ok' }
    $State['diskBand'] = $bandName
    Write-Log ("disk: {0} GB free, band {1}, freed {2}; pagefile {3}, recycle bin {4}, OneDrive waiting {5}, cloud {6}" -f
        $free, $bandName, (Format-GB $freed), (Format-GB (Get-PagefileBytes)), (Format-GB (Get-RecycleBinBytes)),
        (Format-GB ([double]$State.oneDrive['waitingBytes'])), (Format-GB ([double]$State.oneDrive['cloudBytes'])))
    if ($runaway -and -not $clogged -and (Get-MinutesSince $State.lastNotify 'diskDrop') -ge 60) {
        $State.lastNotify['diskDrop'] = $now.ToString('o')
        Show-Toast "C: space dropping fast ($free GB free)" "$runaway If RAM is low, the page file grows: close idle programs." 'warning'
    }
    if ($bandName -eq 'ok') {
        if ($prevBand -and $prevBand -ne 'ok') { Write-Log "disk recovered from band $prevBand" }
        return
    }

    $level = if ($clogged) { 'clogged' } else { $band.level }
    $every = if ($clogged) { $cl.notifyEveryMin } else { $band.notifyEveryMin }
    $worse = ($prevBand -ne $bandName) -and ($prevBand -eq $null -or $prevBand -eq 'ok' -or $bandName -eq 'clogged' -or
        ($prevBand -ne 'clogged' -and (Get-DiskBand $free).maxFreeGB -lt (($Config.disk.bands | Where-Object name -eq $prevBand).maxFreeGB)))
    if (-not $worse -and (Get-MinutesSince $State.lastNotify 'disk') -lt $every) { return }
    $State.lastNotify['disk'] = $now.ToString('o')

    $parts = @()
    if ($freed -gt 50MB) { $parts += "Cleared $(Format-GB $freed) of caches." }
    $bin = Get-RecycleBinBytes
    if ($bin -gt 1GB) { $parts += "Recycle Bin holds $(Format-GB $bin): empty it." }
    $waiting = $State.oneDrive['waitingBytes']
    if ($waiting -gt 1GB) { $parts += "OneDrive: $(Format-GB $waiting) waiting to upload before it can be freed." }
    if ($oneDriveProblem) { $parts += $oneDriveProblem }
    if ($clogged) { $parts = @("Clogged: $($reasons -join '; ').") + $parts }
    $advice = if ($clogged) { ($Config.disk.bands | Sort-Object maxFreeGB | Select-Object -First 1).advice } else { $band.advice }
    if ($advice) { $parts += $advice }
    $title = if ($clogged) { "C: is clogged ($free GB free)" } else { "C: $free GB free (below $($band.name))" }
    Show-Toast $title ($parts -join ' ') $level
}

# ---------- memory ----------

function Get-MemoryStatus {
    $os = Get-CimInstance Win32_OperatingSystem
    # "Available" as Task Manager shows it: free plus standby cache.
    $availKB = (Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory).AvailableKBytes
    if (-not $availKB) { $availKB = $os.FreePhysicalMemory }
    $avail = 100.0 * $availKB / $os.TotalVisibleMemorySize
    if ($SimulateAvailPct -ge 0) { $avail = $SimulateAvailPct }
    [pscustomobject]@{
        TotalGB   = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
        AvailGB   = [math]::Round($availKB / 1MB, 1)
        AvailPct  = [math]::Round($avail, 1)
        CommitPct = [math]::Round(100.0 - 100.0 * $os.FreeVirtualMemory / $os.TotalVirtualMemorySize, 1)
    }
}

function Get-AppUsage([hashtable]$State, [bool]$Record) {
    # Per program: memory, CPU since the last check, minutes since it was last in front.
    $session = (Get-Process -Id $PID).SessionId
    $procs = Get-Process | Where-Object { $_.SessionId -eq $session }
    $now = Get-Date
    $fgPid = [RWNative]::ForegroundPid()
    $userIdle = [RWNative]::InputIdleMinutes()
    $fgName = ($procs | Where-Object Id -eq $fgPid | Select-Object -First 1).ProcessName
    if ($Record -and $fgName -and $userIdle -lt 10) { $State.foreground[$fgName] = $now.ToString('o') }

    $lastCheck = $State['lastCheck']
    $intervalSec = if ($lastCheck) { ($now - (To-Date $lastCheck)).TotalSeconds } else { 0 }
    $watchingMin = ($now - (To-Date $State.firstRun)).TotalMinutes
    $cores = [Environment]::ProcessorCount
    $prevCpu = $State.cpu
    $newCpu = @{}
    $apps = foreach ($g in ($procs | Group-Object ProcessName)) {
        $cpu = ($g.Group | Measure-Object CPU -Sum).Sum
        if ($null -eq $cpu) { $cpu = 0 }
        $newCpu[$g.Name] = $cpu
        $cpuPct = $null
        if ($intervalSec -gt 60 -and $prevCpu.ContainsKey($g.Name)) {
            $cpuPct = [math]::Round(100.0 * ($cpu - [double]$prevCpu[$g.Name]) / $intervalSec / $cores, 2)
        }
        $idle = Get-MinutesSince $State.foreground $g.Name
        if ($idle -eq [double]::MaxValue) { $idle = $watchingMin }
        $titles = @($g.Group | Where-Object { $_.MainWindowTitle } | ForEach-Object MainWindowTitle)
        [pscustomobject]@{
            Name      = $g.Name
            MB        = [math]::Round(($g.Group | Measure-Object WorkingSet64 -Sum).Sum / 1MB)
            Processes = $g.Count
            IdleMin   = [math]::Round($idle)
            CpuPct    = $cpuPct
            Windows   = ($titles -join ' | ')
            HasWindow = $titles.Count -gt 0
        }
    }
    if ($Record) {
        $State.cpu = $newCpu
        $State['lastCheck'] = $now.ToString('o')
    }
    return @($apps | Sort-Object MB -Descending)
}

function Get-CloseCandidates($Apps) {
    $m = $Config.memory
    return @($Apps | Where-Object {
            $_.MB -ge $m.candidateMinMB -and $_.IdleMin -ge $m.candidateIdleMin -and
            ($null -eq $_.CpuPct -or $_.CpuPct -le $m.candidateMaxCpuPct) -and
            ($_.HasWindow -or $_.Name -eq 'msedge') -and $_.Name -notin $m.neverPropose
        })
}

function Get-EdgeSummary {
    $edge = @(Get-CimInstance Win32_Process -Filter "Name='msedge.exe'" -ErrorAction SilentlyContinue)
    if ($edge.Count -eq 0) { return $null }
    $renderers = @($edge | Where-Object { $_.CommandLine -match '--type=renderer' -and $_.CommandLine -notmatch '--extension-process' })
    [pscustomobject]@{
        Processes  = $edge.Count
        TabProcs   = $renderers.Count
        MB         = [math]::Round(($edge | Measure-Object WorkingSetSize -Sum).Sum / 1MB)
        TabMB      = [math]::Round(($renderers | Measure-Object WorkingSetSize -Sum).Sum / 1MB)
    }
}

function Invoke-MemoryCheck([hashtable]$State) {
    $mem = Get-MemoryStatus
    $apps = Get-AppUsage $State $true
    $band = $null
    foreach ($b in ($Config.memory.bands | Sort-Object maxAvailPct -Descending)) {
        if ($mem.AvailPct -le $b.maxAvailPct) { $band = $b }
    }
    if ($mem.CommitPct -ge $Config.memory.criticalCommitPct) {
        $band = $Config.memory.bands | Sort-Object maxAvailPct | Select-Object -First 1
    }
    $bandName = if ($band) { $band.name } else { 'ok' }
    $prev = $State['memBand']
    $State['memBand'] = $bandName
    Write-Log ("memory: {0}% available ({1} of {2} GB), commit {3}%, band {4}" -f $mem.AvailPct, $mem.AvailGB, $mem.TotalGB, $mem.CommitPct, $bandName)
    if (-not $band) { return }

    $candidates = Get-CloseCandidates $apps
    $edge = Get-EdgeSummary
    $worse = $prev -ne $bandName -and ($prev -in $null, 'ok', 'propose' -or $bandName -eq 'critical')
    if (-not $worse -and (Get-MinutesSince $State.lastNotify 'memory') -lt $band.notifyEveryMin) { return }
    $State.lastNotify['memory'] = (Get-Date).ToString('o')

    $parts = @()
    $top = $candidates | Select-Object -First 3 | ForEach-Object { '{0} {1:N1} GB, idle {2} min' -f $_.Name, ($_.MB / 1024), $_.IdleMin }
    if ($top) { $parts += 'Idle and heavy: ' + ($top -join '; ') + '.' }
    if ($edge -and $edge.TabMB -gt 1024) {
        $parts += ('Edge: {0} tab processes use {1:N1} GB; Review > Edge tabs to discard idle ones.' -f $edge.TabProcs, ($edge.TabMB / 1024))
    }
    if (-not $parts) { $parts += 'No idle program stands out; close what you are not using.' }
    $level = switch ($bandName) { 'propose' { 'notice' } 'urgent' { 'urgent' } default { 'critical' } }
    Show-Toast ("Memory low: {0}% free, commit {1}%" -f $mem.AvailPct, $mem.CommitPct) ($parts -join ' ') $level
}

# ---------- review (interactive) ----------

function Invoke-Review {
    $state = Read-State
    $mem = Get-MemoryStatus
    $apps = Get-AppUsage $state $false
    $edge = Get-EdgeSummary
    $free = Get-FreeGB
    Write-Host ("C: {0} GB free.  RAM {1}% available ({2} of {3} GB), commit {4}%." -f $free, $mem.AvailPct, $mem.AvailGB, $mem.TotalGB, $mem.CommitPct)
    if ($edge) { Write-Host ("Edge: {0} tab processes, {1:N1} GB." -f $edge.TabProcs, ($edge.TabMB / 1024)) }

    $rows = @()
    $rows += [pscustomobject]@{ Action = 'Edge: review and discard idle tabs (opens edge://discards)'; Name = '#edge'; MB = $(if ($edge) { $edge.TabMB } else { 0 }); IdleMin = ''; CpuPct = ''; Windows = '' }
    $rows += [pscustomobject]@{ Action = 'Open Windows storage settings'; Name = '#storage'; MB = ''; IdleMin = ''; CpuPct = ''; Windows = '' }
    $candidateNames = @(Get-CloseCandidates $apps | ForEach-Object Name)
    foreach ($a in ($apps | Where-Object { $_.HasWindow -and $_.MB -ge 100 -and $_.Name -notin $Config.memory.neverPropose })) {
        $tag = if ($a.Name -in $candidateNames) { 'Close (idle, suggested)' } else { 'Close' }
        $rows += [pscustomobject]@{ Action = $tag; Name = $a.Name; MB = $a.MB; IdleMin = $a.IdleMin; CpuPct = $a.CpuPct; Windows = $a.Windows }
    }

    $picked = $rows | Out-GridView -PassThru -Title 'ResourceWatch: select what to do (Ctrl+click for several), then OK. Programs get a normal close request; unsaved work will ask first.'
    foreach ($p in @($picked)) {
        switch ($p.Name) {
            '#edge' { Start-Process 'msedge.exe' 'edge://discards' }
            '#storage' { Start-Process 'ms-settings:storagesense' }
            default {
                $n = 0
                foreach ($proc in Get-Process -Name $p.Name -ErrorAction SilentlyContinue | Where-Object MainWindowHandle -ne 0) {
                    if ($proc.CloseMainWindow()) { $n++ }
                }
                Write-Log "review: asked $($p.Name) to close ($n windows)"
                Write-Host "Asked $($p.Name) to close $n window(s)."
            }
        }
    }
    if (@($picked).Count -gt 0) { Start-Sleep -Seconds 3 }
}

# ---------- status ----------

function Show-Status {
    $state = Read-State
    $free = Get-FreeGB
    $band = Get-DiskBand $free
    $mem = Get-MemoryStatus
    $apps = Get-AppUsage $state $false
    "C: free            : $free GB  (band: $(if ($band) { $band.name + ' / ' + $band.level } else { 'ok' }))"
    "Clean-ups in band  : $((Get-CleanupsFor $band) -join ', ')"
    "Recycle Bin        : $(Format-GB (Get-RecycleBinBytes))"
    "OneDrive waiting   : $(if ($state.oneDrive['waitingBytes']) { Format-GB $state.oneDrive['waitingBytes'] } else { 'not measured yet' })"
    "OneDrive queue     : $($state.oneDrive['queue'])"
    "RAM available      : $($mem.AvailPct)% ($($mem.AvailGB) of $($mem.TotalGB) GB), commit $($mem.CommitPct)%"
    $edge = Get-EdgeSummary
    if ($edge) { "Edge               : $($edge.TabProcs) tab processes, $([math]::Round($edge.TabMB / 1024, 1)) GB (all Edge $([math]::Round($edge.MB / 1024, 1)) GB)" }
    ''
    'Close candidates (idle, heavy):'
    Get-CloseCandidates $apps | Select-Object Name, MB, IdleMin, CpuPct, Windows | Format-Table -AutoSize | Out-String -Width 200
    'Top programs by memory:'
    $apps | Select-Object -First 10 Name, MB, Processes, IdleMin, CpuPct | Format-Table -AutoSize | Out-String -Width 200
}

# ---------- install ----------

function Install-Watch {
    $vbs = Join-Path $Here 'run-hidden.vbs'
    @"
' Starts the ResourceWatch check without flashing a console window.
CreateObject("WScript.Shell").Run """$PsExe"" -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""$PSCommandPath"" -Mode Check", 0, False
"@ | Set-Content -Path $vbs -Encoding ASCII

    $key = "HKCU:\Software\Classes\$Protocol"
    New-Item -Path "$key\shell\open\command" -Force | Out-Null
    Set-ItemProperty -Path $key -Name '(default)' -Value 'URL:ResourceWatch'
    Set-ItemProperty -Path $key -Name 'URL Protocol' -Value ''
    Set-ItemProperty -Path "$key\shell\open\command" -Name '(default)' `
        -Value "`"$PsExe`" -NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Mode Review -Url `"%1`""

    $action = New-ScheduledTaskAction -Execute (Join-Path $env:SystemRoot 'System32\wscript.exe') -Argument "`"$vbs`""
    $every = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes $Config.checkEveryMin)
    $logon = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
        -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
    $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $every, $logon -Settings $settings -Principal $principal `
        -Description 'Disk and memory watchdog: clears regenerable caches by free-space band and proposes closing idle programs.' -Force | Out-Null
    Write-Log 'installed scheduled task and resourcewatch: link'
    "Installed. Task '$TaskName' runs every $($Config.checkEveryMin) min. Log: $LogPath"
}

function Uninstall-Watch {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Remove-Item "HKCU:\Software\Classes\$Protocol" -Recurse -Force -ErrorAction SilentlyContinue
    Write-Log 'uninstalled'
    'Removed the scheduled task and the resourcewatch: link. This folder is left in place.'
}

# ---------- main ----------

if ($LoadOnly) { return }

switch ($Mode) {
    'Install' { Install-Watch }
    'Uninstall' { Uninstall-Watch }
    'Status' { Show-Status }
    'Review' { Invoke-Review }
    'Unpin' {
        $state = Read-State
        Invoke-Unpin $UnpinDays $state
        # Merge only the OneDrive figures, in case a check saved state meanwhile.
        $fresh = Read-State
        $fresh.oneDrive = $state.oneDrive
        Save-State $fresh
    }
    'Check' {
        # The launcher returns at once, so the scheduler can start overlapping checks; let only one through.
        $mutex = New-Object System.Threading.Mutex($false, 'Local\ResourceWatchCheck')
        $owner = Join-Path $Here 'check.owner'
        $got = $false
        try { $got = $mutex.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $got = $true }
        if (-not $got) {
            # A check older than 20 minutes is stuck: stop it and take over, so one hang can't silence the watcher.
            $holder = Get-Content $owner -ErrorAction SilentlyContinue
            $proc = if ($holder) { Get-Process -Id ([int]$holder) -ErrorAction SilentlyContinue }
            if (-not $proc -or ((Get-Date) - $proc.StartTime).TotalMinutes -lt 20) { return }
            Write-Log "check $holder stuck since $($proc.StartTime): stopped it"
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            try { $got = $mutex.WaitOne(10000) } catch [System.Threading.AbandonedMutexException] { $got = $true }
            if (-not $got) { return }
        }
        Set-Content $owner $PID
        $state = Read-State
        try { Invoke-DiskCheck $state } catch { Write-Log "disk check failed: $($_.Exception.Message)" }
        try { Invoke-MemoryCheck $state } catch { Write-Log "memory check failed: $($_.Exception.Message)" }
        Save-State $state
    }
}
