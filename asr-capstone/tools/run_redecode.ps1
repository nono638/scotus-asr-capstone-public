# Decode again the chunks of each run the aligner's fault or the engine's giving up damaged
# (tools/redecode_chunks.py). Each run carries on where it stopped if this is started again.
# The last line of the log says "ALL FINISHED" when every run has been done.

$repo = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repo
$Host.UI.RawUI.WindowTitle = "Redecode chunks"
$env:PYTHONIOENCODING = "utf-8"
$python = ".\.venv\Scripts\python.exe"
$log = "D:\scotus-corpus\experiments\redecode.log"

$runs = @(
    "scotus run-20260921-051927",            # Qwen3, 2017
    "scotus run-20260922-002324",            # Voxtral, 2017
    "scotus run-20260921-033436",            # Canary, 2017
    "scotus run-20260923-011250",            # Granite, 2017
    "earnings22 run-earnings22-qwen3",
    "edacc run-edacc-qwen3",
    "edacc run-edacc-canary --missing-only", # EdAcc has no punctuation to score, so only
    "edacc run-edacc-granite --missing-only",#   the chunks that vanished
    "coraal run-coraal-qwen3",
    "scotus run-scotus250-qwen3"             # Qwen3, the other terms
)
foreach ($run in $runs) {
    $parts = $run -split " "
    $extra = if ($parts.Count -gt 2) { $parts[2] } else { "" }
    Add-Content $log "$(Get-Date -Format 'MM-dd HH:mm') starting $run"
    cmd /c "$python asr-capstone\tools\redecode_chunks.py --corpus $($parts[0]) --source $($parts[1]) $extra >> `"$log`" 2>&1"
    if ($LASTEXITCODE -ne 0) {
        Add-Content $log "$(Get-Date -Format 'MM-dd HH:mm') STOPPED: $run exited with $LASTEXITCODE"
        exit 1
    }
}
Add-Content $log "$(Get-Date -Format 'MM-dd HH:mm') ALL FINISHED"
