# Setting up fstalign (for later)

Written 1 November 2026. Nothing here has been installed yet.

## What it is for

`fstalign` is Rev's tool for scoring a transcript against a reference. Rev built it to
score its own engines, and the Earnings-22 paper used it. It lines the two transcripts up
word by word, like our own pipeline does, and adds a few things ours does differently:
error rates for tagged kinds of word (names, numbers, dates), a synonyms file for variants
that shouldn't count, and optional scoring of punctuation and capitals.

It only says whether each word is right or wrong. It cannot say whether an error changes
the meaning, which is what our searches and the LLM judges are for.

The plan is to run it on **Earnings-22 only**, because that is the one data set whose
references come in fstalign's own format with the names and numbers already tagged. That
gives two things for the paper:

1. A check of our own scoring against a standard tool, on the same calls.
2. A side-by-side of what a standard error breakdown shows and what our searches and the
   judges add.

It runs on the processor, not the graphics card, so it can run while the GPU is busy.
It is C++, not Python, and Rev ships it as a Docker image. On Windows that means WSL
first, then Docker.

## Is it safe to install?

Yes. Both pieces come from the people who make them, and neither is unusual on a
developer's laptop.

- **WSL** (Windows Subsystem for Linux) is Microsoft's own. It runs a real Linux system in
  a small virtual machine. Installing it switches on a Windows feature and downloads
  Ubuntu.
- **Docker** runs a program inside a sealed-off box called a container, with everything
  it needs already inside. We install Docker Engine inside Ubuntu from Docker's own
  package source, not Docker Desktop (reasons below).
- **fstalign's image** comes from Rev's official account on Docker Hub
  (`revdotcom/fstalign`), under the Apache 2.0 licence. Running an image means running
  someone else's code, so we pin an exact version, `2.0.2` (published 28 October 2026),
  instead of "latest".

Things worth knowing, none of them reasons not to:

- **Anyone allowed to run `docker` is in effect an administrator** inside Ubuntu. The
  usual tip is to add yourself to the `docker` group so you can skip `sudo`. These steps
  leave that out and use `sudo docker` instead, which keeps it explicit.
- **Containers don't open any network ports** unless told to with `-p`. fstalign never
  needs one, so nothing here listens on the network.
- **Memory.** WSL's virtual machine can use up to half the laptop's memory by default
  (about 47 GB here) while it is running. Step 2 caps it at 8 GB, which is plenty for
  fstalign, so it can never compete with an ASR run or Ollama. `wsl --shutdown` stops it
  completely.
- **Disk.** Ubuntu plus Docker plus the fstalign image is about 3 GB on C:, which has
  640 GB free. WSL's disk file grows and doesn't shrink on its own; that only matters if
  it gets used for much more than this.
- **The graphics card** isn't touched. WSL can share the card, but fstalign doesn't use
  it.
- **Virtualisation** is already on. Windows 11's own security features run on the same
  hypervisor (checked 1 November: `HypervisorPresent` is True), so nothing changes there.

**Why not Docker Desktop:** it adds a Windows program that starts at login and runs in the
background, it needs a paid licence for larger companies (free for students and
individuals), and it does nothing we need. Docker Engine inside Ubuntu only runs while
Ubuntu does.

## Steps

About an hour, mostly downloads, plus one restart.

### 1. Install WSL and Ubuntu (needs administrator, then a restart)

Open PowerShell as administrator (right-click, "Run as administrator"):

```powershell
wsl --install
```

Restart the laptop. Ubuntu opens on its own afterwards (or open "Ubuntu" from the Start
menu) and asks for a Linux username and password. These are only for Ubuntu and don't
need to match Windows. Remember the password: `sudo` asks for it.

Check it is WSL 2:

```powershell
wsl --list --verbose
```

### 2. Cap WSL's memory

Create `C:\Users\noahc\.wslconfig` with:

```ini
[wsl2]
memory=8GB
```

Then, in PowerShell, `wsl --shutdown` so the next start picks it up.

### 3. Install Docker Engine inside Ubuntu

In the Ubuntu window, Docker's official steps for Ubuntu
(https://docs.docker.com/engine/install/ubuntu/):

```bash
sudo apt update
sudo apt install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF

sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo docker run hello-world
```

The last line should print "Hello from Docker!". If it says Docker isn't running, try
`sudo systemctl start docker`. If that says the system wasn't booted with systemd, add
these two lines to `/etc/wsl.conf` (`sudo nano /etc/wsl.conf`), run `wsl --shutdown` in
PowerShell, and open Ubuntu again:

```ini
[boot]
systemd=true
```

### 4. Get fstalign

```bash
sudo docker pull revdotcom/fstalign:2.0.2
```

About 400 MB.

### 5. Test it on one Earnings-22 call

Windows drives appear inside Ubuntu under `/mnt`, so `D:\asr-corpora` is
`/mnt/d/asr-corpora`. Score one reference against itself; the error rate should be 0:

```bash
sudo docker run --rm -v /mnt/d/asr-corpora/earnings22:/data revdotcom/fstalign:2.0.2 \
  /fstalign/build/fstalign wer \
  --ref /data/references/4485192.nlp --hyp /data/references/4485192.nlp
```

Then the verbatim reference against the cleaned-up one for the same call, which should
show a real error rate (the two transcribers' choices differ):

```bash
sudo docker run --rm -v /mnt/d/asr-corpora/earnings22:/data revdotcom/fstalign:2.0.2 \
  /fstalign/build/fstalign wer \
  --ref /data/references/4485192.nlp --hyp /data/references-nonverbatim/4485192.nlp
```

If both work, tell Claude, and it will write the script that turns each engine's
Earnings-22 transcript into fstalign's input and collects the results.

### 6. Afterwards

Nothing needs to stay running. Close the Ubuntu window and run `wsl --shutdown` in
PowerShell; with Docker running as a background service, Ubuntu may not stop on its own.

## Undoing it

- Remove Ubuntu and everything inside it (Docker and the image included):
  `wsl --unregister Ubuntu`
- Remove WSL itself: `wsl --uninstall`
- Delete `C:\Users\noahc\.wslconfig`

## Sources

- fstalign README and usage notes: https://github.com/revdotcom/fstalign (Docker image
  `revdotcom/fstalign`; the `wer` command's `--ref`, `--hyp`, `--json-log`,
  `--use-case`, `--use-punctuation` and `--syn` options are in `docs/Usage.md`)
- fstalign image versions: https://hub.docker.com/r/revdotcom/fstalign/tags
- Installing WSL: https://learn.microsoft.com/en-us/windows/wsl/install
- Docker Engine on Ubuntu: https://docs.docker.com/engine/install/ubuntu/
- What our own notes say about fstalign and Earnings-22: `datasets/earnings22.md`
  (section 6) and `scoping-report.md` (the September tool survey)
