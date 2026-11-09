<#
    Build this folder's Python environment from scratch.

    Safe to run more than once. Run it after cloning on a new machine, and again
    whenever requirements.txt changes.

        .\setup.ps1

    What it does, and why:

    * Creates .venv inside this folder, so nothing is ever installed into the
      system Python.
    * Looks for an NVIDIA card and installs the matching PyTorch. This is the
      whole reason a script exists instead of one pip command: the CUDA build and
      the processor-only build come from different indexes, and installing the
      wrong one is silent. You get a working import and no GPU.
#>

[CmdletBinding()]
param(
    # CUDA 12.8 rather than 13.x: the driver here supports both, but ctranslate2
    # and onnxruntime still link against CUDA 12, and mixing major versions in
    # one environment produces loader errors that are painful to diagnose.
    [string]$CudaIndex = "https://download.pytorch.org/whl/cu128",
    [string]$CpuIndex  = "https://download.pytorch.org/whl/cpu",

    # Skip the GPU check and install the processor-only build regardless.
    [switch]$ForceCpu
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$venv   = Join-Path $PSScriptRoot ".venv"
$python = Join-Path $venv "Scripts\python.exe"

# --- 1. Find a Python to build the environment from -------------------------
# Ask the py launcher first. On a fresh Windows machine, `python` on PATH is
# often only the Microsoft Store stub in \WindowsApps\, which prints "Python was
# not found" instead of running. The py launcher can live in \WindowsApps\ too,
# but it is real and points at the actual install, so only `python` is skipped
# there.

function Find-BasePython {
    $launcher = Get-Command py -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($launcher) {
        # try/catch because with ErrorActionPreference = Stop, anything py
        # writes to stderr would otherwise end the script before the fallback.
        try {
            $path = & $launcher.Source -3 -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $path) { return "$path".Trim() }
        }
        catch { }
    }

    $onPath = Get-Command python -CommandType Application -All -ErrorAction SilentlyContinue |
        Where-Object { $_.Source -notlike '*\WindowsApps\*' } |
        Select-Object -First 1
    if ($onPath) { return $onPath.Source }

    throw "No Python found. Install Python 3.12 or newer first."
}

if (-not (Test-Path $python)) {
    $base = Find-BasePython

    $version = & $base -c "import sys; print('%d.%d' % sys.version_info[:2])"
    Write-Host "Creating .venv from Python $version" -ForegroundColor Cyan
    & $base -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw "Could not create the virtual environment." }
}
else {
    Write-Host "Reusing the existing .venv" -ForegroundColor Cyan
}

& $python -m pip install --upgrade pip --quiet

# --- 2. Which machine is this? ----------------------------------------------

$hasGpu = $false
if (-not $ForceCpu) {
    $smi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
    if ($smi) {
        $gpu = & nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>$null
        if ($LASTEXITCODE -eq 0 -and $gpu) {
            $hasGpu = $true
            Write-Host "Found an NVIDIA card: $gpu" -ForegroundColor Green
        }
    }
}

if ($hasGpu) {
    $index = $CudaIndex
    Write-Host "Installing the CUDA build of PyTorch" -ForegroundColor Cyan
}
else {
    $index = $CpuIndex
    Write-Host "No NVIDIA card visible. Installing the processor-only build of PyTorch." -ForegroundColor Yellow
}

& $python -m pip install torch torchaudio --index-url $index
if ($LASTEXITCODE -ne 0) { throw "Installing PyTorch failed." }

# --- 3. Everything else -----------------------------------------------------
# Separate command so pip resolves these against ordinary PyPI. Passing the
# PyTorch index here as well would send pip looking for every package on a
# server that only carries a handful of them.

# The lock file first, so both laptops get exactly the versions freeze.ps1
# recorded. Then requirements.txt, which adds anything listed since the last
# freeze and leaves the pinned versions alone.
$lock = Join-Path $PSScriptRoot "requirements.lock.txt"
if (Test-Path $lock) {
    & $python -m pip install -r $lock
    if ($LASTEXITCODE -ne 0) { throw "Installing the locked versions failed." }
}

& $python -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Installing the requirements failed." }

# --- 4. Prove it actually works ---------------------------------------------
# An import that succeeds proves nothing about the GPU, which is the trap this
# script exists to avoid, so run a real calculation on the card.

Write-Host ""
& $python -c @"
import torch
print('torch          ', torch.__version__)
print('built for CUDA ', torch.version.cuda or 'processor only')
if torch.cuda.is_available():
    name = torch.cuda.get_device_name(0)
    gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
    x = torch.randn(512, 512, device='cuda')
    ok = bool((x @ x).sum().isfinite())
    print('GPU            ', name, '(%.1f GB)' % gb)
    print('GPU maths work ', ok)
else:
    print('GPU            ', 'not available - running on the processor')
"@

Write-Host ""
Write-Host "Done. Run things with .\.venv\Scripts\python.exe" -ForegroundColor Green
Write-Host "To record exact versions for the other machine: .\freeze.ps1" -ForegroundColor DarkGray
