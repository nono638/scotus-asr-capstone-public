# The overnight queue: runs the work listed in overnight-queue.csv, one item at a
# time, under a fixed run name per engine so the next night carries on where this
# one stopped. The "asr-work" skill (.claude/skills/asr-work) starts it, and its
# supervisor agent watches it and restarts it. Night or day, it is the same.
#
#   .\overnight.ps1           start, or carry on
#   .\overnight.ps1 -Stop     from another window: finish the recording in
#                             progress, then end the queue
#   .\overnight.ps1 -Stop -Now   end it at once; the recording in progress is
#                             lost (the next start clears its half-written
#                             files), everything saved before it is kept
#   .\overnight.ps1 -DryRun   print what would run, run nothing
#
# Start it in its own PowerShell window, not inside a Claude session, so it
# survives the session closing.
#
# The queue file is read again before each item, so rows can be added or put on
# hold while it runs. Only rows marked "todo" run, each at most once per start.
# A stopped run exits with 130, and the queue ends there instead of starting the
# next item. A run that finishes with a few failed recordings (exit 1) does not
# hold up the rest; its failures are listed in that run's ledger.jsonl.

param([switch]$Stop, [switch]$Now, [switch]$DryRun)

$python = Join-Path $PSScriptRoot "..\..\.venv\Scripts\python.exe"
$queueFile = Join-Path $PSScriptRoot "overnight-queue.csv"
Set-Location $PSScriptRoot

# Read from the same file the configs use, so this works on either laptop.
$corpus = (Get-Content "..\local-paths.yaml" | Select-String "^scotus_corpus:").ToString().Split(":", 2)[1].Trim()
$runsDir = Join-Path $corpus "runs"
# The queue's own stop flag. Needed as well as each run's STOP file, because a
# run clears a STOP file left over from before it started - a stop asked for in
# the moment between two items would otherwise be lost.
$queueStop = Join-Path $runsDir "overnight-STOP"
# What the queue is doing, for tools/overnight_watch.py to read.
$stateFile = Join-Path $runsDir "overnight-state.json"

function Now { "$((Get-Date).ToUniversalTime().ToString('s'))+00:00" }

# A row may name several settings files, separated by spaces - an engine's and then
# a corpus's (config/qwen3.yaml config/corpora/edacc.yaml) - as a run takes --config twice.
function ConfigArgs($config) { $config -split '\s+' | Where-Object { $_ } | ForEach-Object { "--config"; $_ } }

function Save-State {
    if (-not $DryRun) {
        $state | ConvertTo-Json -Depth 5 | Set-Content $stateFile -Encoding utf8
    }
}

function End-Queue($how, $code) {
    $state.state = $how
    $state.ended = Now
    $state.exit_code = $code
    Save-State
    exit $code
}

if ($Stop -and $Now) {
    # The flag first: it is what tells the supervisor this was the user, not a
    # crash, so it does not start the queue again.
    Set-Content $queueStop "Stopped at once by the user."
    if (-not (Test-Path $stateFile)) { Write-Host "No queue state - nothing to stop."; exit 0 }
    $state = Get-Content $stateFile -Raw | ConvertFrom-Json
    if ($state.state -ne "running") { Write-Host "The queue is not running ($($state.state))."; exit 0 }
    # /T takes the python process with it, which frees the card at once.
    taskkill /PID $state.pid /T /F | Out-Null
    $state.state = "killed"
    $state.ended = Now
    $state.exit_code = -1
    $state | ConvertTo-Json -Depth 5 | Set-Content $stateFile -Encoding utf8
    Write-Host "Ended the queue at once. The recording in progress is lost; everything saved before it is kept."
    exit 0
}

if ($Stop) {
    Set-Content $queueStop "Stop the overnight queue."
    # The run in progress gets its own STOP file, so it ends after the recording it
    # is on. Asked by its own settings, since a corpus other than the Supreme
    # Court keeps its runs in another folder.
    if (Test-Path $stateFile) {
        $state = Get-Content $stateFile -Raw | ConvertFrom-Json
        if ($state.state -eq "running" -and $state.item) {
            $configArgs = ConfigArgs $state.item.config
            & $python -m scotus_asr.cli stop @configArgs --run-id $state.item.run | Out-Null
        }
    }
    Write-Host "Asked the queue to stop after the recording in progress."
    exit 0
}

if ((Test-Path $queueStop) -and -not $DryRun) { Remove-Item $queueStop }

$state = [ordered]@{
    pid = $PID; started = Now; state = "running"; ended = $null; exit_code = $null
    item = $null; items = @()
}
Save-State
$tried = @{}

while ($true) {
    $row = Import-Csv $queueFile |
        Where-Object { $_.status -eq "todo" -and -not $tried.ContainsKey("$($_.run) $($_.terms)") } |
        Select-Object -First 1
    if (-not $row) { break }
    $tried["$($row.run) $($row.terms)"] = $true

    if ((Test-Path $queueStop) -and -not $DryRun) {
        Write-Host "Stopped on request before $($row.run) $($row.terms)."
        Remove-Item $queueStop
        End-Queue "stopped" 130
    }

    $termArgs = $row.terms -split '\s+' | Where-Object { $_ } | ForEach-Object { "--term"; $_ }
    $configArgs = ConfigArgs $row.config
    if ($DryRun) {
        Write-Host "would run: cli run $configArgs $termArgs --run-id $($row.run)"
        continue
    }

    $state.item = [ordered]@{ config = $row.config; run = $row.run; terms = $row.terms; started = Now }
    Save-State
    Write-Host "`n=== $($row.run): terms $($row.terms) - started $(Get-Date -Format 'ddd HH:mm') ===`n"
    & $python -m scotus_asr.cli run @configArgs @termArgs --run-id $row.run
    $code = $LASTEXITCODE
    Write-Host "`n=== $($row.run) ended with code $code at $(Get-Date -Format 'ddd HH:mm') ===`n"

    $state.items += [ordered]@{ run = $row.run; terms = $row.terms; started = $state.item.started; ended = Now; exit_code = $code }
    $state.item = $null
    Save-State
    if ($code -eq 130) { End-Queue "stopped" 130 }
    if ($code -ne 0 -and $code -ne 1) {
        Write-Host "Unexpected exit code; ending the queue rather than guessing."
        End-Queue "crashed" $code
    }
}
Write-Host "Nothing left marked todo in overnight-queue.csv."
if (-not $DryRun) { End-Queue "done" 0 }
