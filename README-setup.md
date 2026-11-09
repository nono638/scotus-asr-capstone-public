# Setting this up on a machine

## Short version

```powershell
git clone <your repo url> Fall-2026
cd Fall-2026
.\setup.ps1
```

That builds a Python environment inside the folder and installs everything. It takes a few
minutes, mostly downloading PyTorch.

If you need the sample audio, which the repository does not carry:

```powershell
.\.venv\Scripts\python.exe asr-capstone\sample\fetch_sample_media.py
```

On the 5090 laptop, which has the corpus, also say where the corpus is. Copy the example
and change the paths in it if the corpus is somewhere else:

```powershell
Copy-Item asr-capstone\local-paths.example.yaml asr-capstone\local-paths.yaml
```

`local-paths.yaml` is not in git, because each laptop keeps the corpus in its own place.
The settings files and tools say `{scotus_corpus}/runs` and read the real folder from it.
Without it, anything that needs the corpus stops and says what to do; the tests and the
notebook do not need it.

## Running things

Call the environment's Python directly. Don't activate it:

```powershell
.\.venv\Scripts\python.exe script.py
.\.venv\Scripts\python.exe -m jupyter lab
```

Activation only lasts for one terminal session. Calling the executable by path always hits
the right environment, which matters here because the whole point is that nothing lands in
the system Python.

## Adding a package

Add it to `requirements.txt`, then:

```powershell
.\setup.ps1     # installs it
.\freeze.ps1    # records exact versions in requirements.lock.txt
```

Commit both files. The other machine picks it up with `git pull` and `.\setup.ps1`, which
installs the exact versions in `requirements.lock.txt` first and then anything in
`requirements.txt` that is newer than the last freeze.

## Why PyTorch is handled separately

It is not in `requirements.txt`. The two laptops need different builds:

| Machine | Build | Comes from |
|---|---|---|
| Personal (RTX 5090, 24 GB) | `torch 2.11.0+cu128` | PyTorch's CUDA index |
| Work (Intel graphics) | processor-only | PyTorch's CPU index |

A version like `2.11.0+cu128` does not exist on ordinary PyPI, so a shared lockfile naming it
fails on the work laptop. `setup.ps1` looks for an NVIDIA card and installs the matching one.

**The failure this prevents is a quiet one.** Plain `pip install torch` gives you the
processor-only build on every machine, including the one with the 5090. It imports without
complaint and simply never touches the card — you notice when a job that should take twenty
minutes is still running the next morning. The scoping report found exactly this build
already installed once. `setup.ps1` ends by running a real calculation on the GPU so the
result is visible rather than assumed.

CUDA 12.8 rather than 13.x, even though the driver supports both, because `ctranslate2` and
`onnxruntime` still link against CUDA 12 and mixing major CUDA versions in one environment
causes loader errors that are hard to trace.

## Checking the GPU is actually being used

```powershell
.\.venv\Scripts\python.exe -c "import torch; print(torch.cuda.is_available(), torch.version.cuda)"
```

Expect `True 12.8` on the personal laptop.

If it says `True` but jobs are still slow or fail to allocate memory, check what is already
holding the card:

```powershell
nvidia-smi
```

Ollama keeps a model resident and can hold around 21 of the 24 GB. `ollama stop <model>`
gives it back.

## Where things live

The project is a git repository; GitHub is the backup, and git is how work moves between
the two laptops. Nothing depends on which folder it is cloned into.

## Python version

Built on Python 3.14. Checked in September 2026: every dependency here works on it, either
with a native `cp314` wheel or an `abi3` wheel that covers all later versions.

Two optional packages have no wheels at all and compile from source, which needs Visual
Studio Build Tools — `openai-whisper` and `meeteval`. Neither is installed. That is true on
any Python version, not something specific to 3.14. `faster-whisper` is installed instead and
is the faster option anyway.
