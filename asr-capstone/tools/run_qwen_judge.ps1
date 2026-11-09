# Qwen 3.8 reads the full-v1 cases it has no answer for yet, 500 at a time.
# Each batch takes the lowest case ids with no answer. full-v1 is shuffled, so
# stopping at any point leaves a fair random draw of what was left.
# To stop: close this window. Answers are saved one by one, so only the case in
# progress is lost, and running this script again carries on where it stopped.

$repo = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repo
$Host.UI.RawUI.WindowTitle = "Qwen judge"
$env:PYTHONIOENCODING = "utf-8"

$python = ".\.venv\Scripts\python.exe"
$answers = "asr-capstone\findings\judge\answers-qwen3.8-27b-full-v1.csv"
$logDir = "D:\scotus-corpus\experiments\judge"
$log = Join-Path $logDir "qwen-full-v1.log"
New-Item -ItemType Directory -Force $logDir | Out-Null

while ($true) {
    $before = (Get-Item $answers).Length
    Write-Host "$(Get-Date -Format 'MM-dd HH:mm') starting a batch of 500. Progress is in $log"
    cmd /c "$python asr-capstone\tools\judge_failures.py --prompt 0.4 --model qwen3.8:27b --think --sample full-v1 --ask meaning --sizes minute --max-new 500 >> `"$log`" 2>&1"
    $code = $LASTEXITCODE
    $after = (Get-Item $answers).Length

    # No new answers means every case is read, or the batch failed. Either way, stop.
    if ($code -ne 0 -or $after -eq $before) {
        Write-Host "$(Get-Date -Format 'MM-dd HH:mm') stopped: exit code $code, answers file grew by $($after - $before) bytes."
        Add-Content $log "$(Get-Date -Format 'MM-dd HH:mm') loop stopped: exit code $code, answers file grew by $($after - $before) bytes."
        break
    }
}
