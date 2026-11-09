<#
    Record the exact versions currently installed, so the other machine can be
    brought to the same state.

        .\freeze.ps1

    Writes requirements.lock.txt. Commit that file.

    PyTorch and the NVIDIA libraries it drags in are filtered out on purpose.
    Their version strings carry a build tag such as "2.11.0+cu128" that only
    exists on the CUDA index, so a lockfile containing them fails to install on
    a machine without a GPU. setup.ps1 handles PyTorch separately for exactly
    this reason.
#>

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "No .venv here yet. Run .\setup.ps1 first."
}

# Anything whose build depends on the machine rather than on requirements.txt.
$machineSpecific = @(
    "torch", "torchaudio", "torchvision", "triton", "pytorch-triton"
)

$frozen = & $python -m pip freeze
$kept = $frozen | Where-Object {
    $name = ($_ -split "==|@|\s")[0].Trim().ToLower()
    ($machineSpecific -notcontains $name) -and ($name -notlike "nvidia-*")
}

$torchLine = $frozen | Where-Object { $_ -like "torch==*" }

$header = @(
    "# Exact versions, written by freeze.ps1 on $(Get-Date -Format 'yyyy-MM-dd').",
    "#",
    "# setup.ps1 installs from this file, after installing the right PyTorch",
    "# for the machine. Add packages to requirements.txt, not here.",
    "#",
    "# PyTorch is not listed here because its build differs per machine.",
    "# On the machine this was written from it was: $torchLine",
    ""
)

$out = Join-Path $PSScriptRoot "requirements.lock.txt"
# WriteAllLines rather than Set-Content: Windows PowerShell's utf8 adds a
# byte-order mark, which pip would read as part of the first line.
[System.IO.File]::WriteAllLines($out, [string[]]($header + $kept))

Write-Host "Wrote requirements.lock.txt ($($kept.Count) packages)" -ForegroundColor Green
