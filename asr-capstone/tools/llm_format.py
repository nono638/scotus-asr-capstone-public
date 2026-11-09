"""Can a local language model format machine transcripts the way the record does?

Qwen3 hears best of the seven models but punctuates worst of the six that
punctuate, so on the verbatim rule - where every comma and capital counts - it
loses to Whisper. This hands each machine transcript to a local LLM (through
Ollama) with one of three prompts, each allowed to do more than the last:

  step 1  punctuation, capitals, dashes, numbers as digits. The words are
          locked: anything the LLM changes beyond that is put back in code.
  step 2  step 1, plus removing doubled words and fixing obvious mishearings.
  step 3  conservative proofreading toward a final transcript, with real
          before/after examples.

Every step starts from the raw machine words, not from the step before. The
prompts are in tools/llm_format_prompts/; their examples all come from October
Term 2010 arguments, which are never scored, so nothing leaks.

Then each version is scored against the official transcript the same three ways
as the published results, and every official word is checked for whether the
LLM fixed it (wrong before, right after) or broke it (right before, wrong after).

The card. A 31B model is 19 GB before it does any work, and this laptop has
rebooted once (21 September 2026) when its card overfilled and Windows quietly
moved video memory into system RAM. So every chunk is followed by a reading of
the card, written to gpu-watch.jsonl, and the run stops itself if memory, the
spill into system RAM, the temperature or the speed look wrong. Each argument
ends by unloading the model. A stopped run picks up where it left off.

Usage:
    python tools/llm_format.py check --llm gemma4:31b
    python tools/llm_format.py try   --llm gemma4:31b --model Qwen3 --docket 16-658
    python tools/llm_format.py run   --llm gemma4:31b --cases pilot --models Qwen3
    python tools/llm_format.py score --llm gemma4:31b --cases pilot
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import statistics
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

import pandas as pd

TOOLS = Path(__file__).resolve().parent
CAPSTONE = TOOLS.parent
sys.path.insert(0, str(CAPSTONE / "pipeline"))
sys.path.insert(0, str(TOOLS))

import crowd  # noqa: E402
from scotus_asr.config import local_path  # noqa: E402
from scotus_asr.scoring.align import align_words  # noqa: E402
from scotus_asr.scoring.normalize import NORMALIZERS, _lowercase_nopunct, _standard  # noqa: E402
from scotus_asr.stages import _load_asr_result  # noqa: E402
from scotus_asr.transcripts.model import Transcript  # noqa: E402


def runs_dir() -> Path:
    """The seven runs, wherever local-paths.yaml says the corpus is."""
    return local_path("scotus_corpus") / "runs"


def out_dir() -> Path:
    """Where this experiment's outputs go, beside the corpus."""
    return local_path("scotus_corpus") / "experiments" / "llm-format"


FINDINGS = CAPSTONE / "findings" / "llm-format"
PROMPTS = TOOLS / "llm_format_prompts"
OLLAMA = "http://localhost:11434"

#: The order models are run in: the three that answer the main question first.
MODEL_ORDER = ["Qwen3", "Whisper", "Granite Plus", "Voxtral", "Canary", "Parakeet", "Granite"]
STEPS = [1, 2, 3]
#: The order the full run takes them in: step 1 for every model first, since it
#: answers the main question, and step 2 last, since the pilot showed it hurts.
RUN_ORDER = [1, 3, 2]

#: The three shortest arguments outside the sample, for trying prompts and
#: models on. Kept apart so the prompts are never tuned on a scored case.
PILOT = ["16-658", "16-534", "16-1067"]

#: Words the LLM edits per request, and the read-only context either side.
#: Longer inputs make LLMs over-correct less; context either side keeps the
#: punctuation right at the edges.
CHUNK_WORDS = 400
BEFORE_WORDS = 50
AFTER_WORDS = 40

#: Ollama settings. Thinking is on by default for Gemma 4 here and only costs
#: time. Temperature 0 makes a rerun give the same text. The context window
#: is fixed because Ollama's default on this card is 32,768 tokens - four times
#: the memory - and changing it between requests reloads the model.
NUM_CTX = 8192
OPTIONS = {"temperature": 0, "seed": 1, "num_ctx": NUM_CTX}

#: A chunk whose word count comes back further off than this is split in half
#: and tried again; a half that still fails keeps the machine's own words.
WORD_COUNT_TOLERANCE = 0.25

FILLERS = {"uh", "um", "mm", "hmm", "mhm", "er", "ah"}

#: Speaker labels the prompts forbid. Removed if they slip through anyway,
#: since the scoring drops speaker labels from the record too.
SPEAKER_LABEL = re.compile(
    r"\b(?:CHIEF JUSTICE|JUSTICE|MR\.|MS\.|MRS\.|GENERAL)(?: [A-Z][A-Za-z'\-]+)?\s*:\s*"
)

# The card. 0.92 of the 24,463 MiB this card reports, the same ceiling
# `gpu.cap_memory` puts on the speech runs; it leaves the desktop its 1.3 GB.
MAX_MEMORY_MIB = 22_500
MAX_SPILL_RISE_MIB = 1024   # Ollama's memory in system RAM, above its level at load
HOT_CELSIUS = 87
COOL_DOWN_SECONDS = 120
SLOW_FACTOR = 3             # slower than a third of the usual pace: the 21 September symptom
PAUSE_BETWEEN_CHUNKS = 1.0


# ---------------------------------------------------------------------------
# Which cases, and what each model wrote
# ---------------------------------------------------------------------------

def case_list(name: str) -> list[str]:
    """The 15 scored arguments (every fourth of the 61), the pilot three, or all 61.

    "all" was added in October 2026 so every argument has a formatted Qwen3 to
    show; the scored results stay those of the 15.
    """
    if name == "pilot":
        return PILOT
    # The 61 OT2017 arguments: every docket the Parakeet run transcribed.
    every = sorted(crowd.seven(runs_dir()).by_name("Parakeet").recordings())
    if name == "all":
        return every
    return every[0::4][:15]


def machine_words(model: str, docket: str) -> list[str]:
    """What the model wrote, seam fix applied, as the scoring reads it."""
    result = _load_asr_result(crowd.seven(runs_dir()).by_name(model).asr_file(docket))
    return [w.text.strip() for w in result.words if w.text.strip()]


def reference_words(docket: str) -> list[str]:
    """The official transcript without speaker labels, as the scoring reads it."""
    path = runs_dir() / crowd.RUNS["Qwen3"] / "reference" / f"{docket}.json"
    transcript = Transcript.from_dict(json.loads(path.read_text(encoding="utf-8")))
    return transcript.full_text(include_speakers=False).split()


def folder_name(llm: str) -> str:
    return llm.replace(":", "-").replace("/", "-")


def output_path(llm: str, step: int, model: str, docket: str) -> Path:
    return out_dir() / folder_name(llm) / f"step{step}" / model.replace(" ", "-") / f"{docket}.json"


# ---------------------------------------------------------------------------
# Talking to Ollama
# ---------------------------------------------------------------------------

def read_prompt(step: int) -> list[dict]:
    """The system message and example pairs for one step, as chat messages."""
    text = (PROMPTS / f"step{step}.txt").read_text(encoding="utf-8")
    parts = re.split(r"^=== (SYSTEM|EXAMPLE INPUT|EXAMPLE OUTPUT) ===\s*$", text, flags=re.M)
    roles = {"SYSTEM": "system", "EXAMPLE INPUT": "user", "EXAMPLE OUTPUT": "assistant"}
    return [{"role": roles[parts[i]], "content": parts[i + 1].strip()}
            for i in range(1, len(parts), 2)]


def user_message(before: list[str], words: list[str], after: list[str]) -> str:
    message = ""
    if before:
        message += "BEFORE (already done, for context only):\n<<<\n" + " ".join(before) + "\n>>>\n\n"
    message += "TEXT TO FORMAT:\n<<<\n" + " ".join(words) + "\n>>>"
    if after:
        message += "\n\nAFTER (for context only, do not include):\n<<<\n" + " ".join(after) + "\n>>>"
    return message


def post(path: str, body: dict, timeout: float = 900) -> dict:
    request = urllib.request.Request(
        OLLAMA + path, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def ask(llm: str, messages: list[dict], words_in: int) -> dict:
    """One request. Room for twice the words in, so a loop cannot run on."""
    body = {
        "model": llm, "messages": messages, "stream": False, "think": False,
        "keep_alive": "10m",
        "options": {**OPTIONS, "num_predict": int(words_in * 1.5 * 2) + 100},
    }
    started = time.time()
    reply = post("/api/chat", body)
    return {
        "text": reply["message"]["content"].strip(),
        "done_reason": reply.get("done_reason"),
        "tokens": reply.get("eval_count", 0),
        "seconds": reply.get("eval_duration", 0) / 1e9,
        "wall_seconds": round(time.time() - started, 2),
        "thinking": bool(reply["message"].get("thinking")),
    }


def unload(llm: str) -> None:
    post("/api/generate", {"model": llm, "keep_alive": 0})


def loaded_models() -> list[dict]:
    with urllib.request.urlopen(OLLAMA + "/api/ps", timeout=30) as response:
        return json.loads(response.read().decode("utf-8")).get("models", [])


# ---------------------------------------------------------------------------
# Keeping the words: the step 1 lock
# ---------------------------------------------------------------------------

def units(words: list[str]) -> list[str]:
    """Words, with pure punctuation ("--") stuck onto the word before it.

    Under lowercase_nopunct a dash has no letters at all, so on its own it
    could not be lined up with anything.
    """
    out: list[str] = []
    for word in words:
        if out and not _lowercase_nopunct(word):
            out[-1] += " " + word
        else:
            out.append(word)
    return out


def spoken_form(pieces: list[str]) -> str:
    """What a stretch says, ignoring how it is written.

    Numbers go through the Whisper normaliser, so "two thousand twelve" and
    "2012" agree. Brackets become spaces first, because that normaliser drops
    anything inside them and "4(a)(5)(C)" would come out as "4". Then only
    letters and digits are compared, so "four A five C" and "4(a)(5)(C)" agree
    too. ("versus" is not let become "v.": this term's record writes "versus"
    199 times and "v." 37.)
    """
    text = re.sub(r"[()\[\]]", " ", " ".join(pieces))
    return re.sub(r"[^a-z0-9$%]", "", _standard(text))


def clean_reply(text: str) -> tuple[str, int]:
    """The LLM's reply without speaker labels or stray markers."""
    text, labels = SPEAKER_LABEL.subn("", text)
    return text.replace("<<<", "").replace(">>>", "").replace("|||", " ").strip(), labels


def chunk_output(chunk: dict, step: int) -> list[str]:
    """A chunk's words. Step 1 is locked again from the saved reply, so a
    change to the lock reaches finished runs without asking the LLM again."""
    if step != 1 or chunk["kept_machine_words"] == len(chunk["input"]):
        return chunk["output"]
    return lock_words(chunk["input"], clean_reply(chunk["raw_reply"])[0])[0]


def has_filler(pieces: list[str]) -> bool:
    return any(w in FILLERS for piece in pieces for w in _lowercase_nopunct(piece).split())


def lock_words(machine: list[str], llm_text: str) -> tuple[list[str], int]:
    """Keep the LLM's punctuation and capitals, and the machine's words.

    The two are lined up word by word, ignoring case and punctuation. Where
    they differ, the LLM's version is kept only if it says the same thing once
    numbers and citations are written the same way (see `spoken_form`), and
    no "uh" or "um" came or went. Anything else gets the machine's words back.

    Returns the words and how many stretches were put back.
    """
    a, b = units(machine), units(llm_text.split())
    key_a = [_lowercase_nopunct(u) for u in a]
    key_b = [_lowercase_nopunct(u) for u in b]
    matcher = difflib.SequenceMatcher(a=key_a, b=key_b, autojunk=False)
    kept: list[str] = []
    put_back = 0
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            kept += b[j1:j2]
            continue
        same_meaning = spoken_form(a[i1:i2]) == spoken_form(b[j1:j2])
        if same_meaning and not has_filler(a[i1:i2]) and not has_filler(b[j1:j2]):
            kept += b[j1:j2]
        else:
            kept += a[i1:i2]
            put_back += 1
    return " ".join(kept).split(), put_back


# ---------------------------------------------------------------------------
# Watching the card
# ---------------------------------------------------------------------------

SPILL_COMMAND = (
    "$ids = (Get-Process ollama* -ErrorAction SilentlyContinue).Id; "
    "$s = (Get-Counter '\\GPU Process Memory(*)\\Shared Usage').CounterSamples | "
    "Where-Object { $ids -contains [int](($_.InstanceName -split '_')[1]) }; "
    "[int](($s | Measure-Object CookedValue -Sum).Sum / 1MB)"
)


def card_reading() -> dict:
    """Memory used, temperature and power from nvidia-smi, and Ollama's spill
    into system RAM from Windows (which nvidia-smi and `ollama ps` cannot see)."""
    line = subprocess.run(
        ["nvidia-smi", "--query-gpu=memory.used,memory.total,temperature.gpu,power.draw",
         "--format=csv,noheader,nounits"],
        capture_output=True, text=True, check=True).stdout.strip().splitlines()[0]
    used, total, temp, power = [x.strip() for x in line.split(",")]
    spill = subprocess.run(["powershell", "-NoProfile", "-Command", SPILL_COMMAND],
                           capture_output=True, text=True).stdout.strip()
    return {
        "time": datetime.now().isoformat(timespec="seconds"),
        "memory_used_mib": int(float(used)), "memory_total_mib": int(float(total)),
        "temperature_c": int(float(temp)),
        "power_w": float(power) if power not in ("[N/A]", "") else None,
        "spill_mib": int(spill) if spill.lstrip("-").isdigit() else None,
    }


class Watchdog:
    """Writes a line per chunk and says when to stop, the way the speech runs'
    gpu-memory.jsonl and watch_pace do."""

    def __init__(self, log_path: Path):
        log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log = log_path.open("a", encoding="utf-8")
        self.spill_at_load: int | None = None
        self.rates: list[float] = []

    def note(self, **fields) -> dict:
        reading = {**card_reading(), **fields}
        self.log.write(json.dumps(reading) + "\n")
        self.log.flush()
        return reading

    def after_load(self, llm: str) -> None:
        """The model must sit wholly on the card, inside the ceiling."""
        models = [m for m in loaded_models() if m["name"] == llm or m["model"] == llm]
        if not models:
            raise SystemExit(f"STOP: {llm} is not loaded after a request.")
        model = models[0]
        on_card = model.get("size_vram", 0) / max(model.get("size", 1), 1)
        reading = self.note(event="loaded", size_mib=model.get("size", 0) // 2**20,
                            on_card_share=round(on_card, 3))
        if on_card < 0.999:
            raise SystemExit(f"STOP: only {on_card:.0%} of {llm} is on the card; "
                             "Ollama has put the rest on the processor.")
        if reading["memory_used_mib"] > MAX_MEMORY_MIB:
            raise SystemExit(f"STOP: {reading['memory_used_mib']} MiB in use after loading, "
                             f"over the {MAX_MEMORY_MIB} MiB ceiling.")
        self.spill_at_load = reading["spill_mib"]

    def after_chunk(self, tokens_per_second: float, **fields) -> None:
        reading = self.note(event="chunk", tokens_per_second=round(tokens_per_second, 1), **fields)
        if reading["memory_used_mib"] > MAX_MEMORY_MIB:
            raise SystemExit(f"STOP: {reading['memory_used_mib']} MiB in use, over the ceiling.")
        if self.spill_at_load is not None and reading["spill_mib"] is not None:
            if reading["spill_mib"] - self.spill_at_load > MAX_SPILL_RISE_MIB:
                raise SystemExit(f"STOP: Ollama's memory in system RAM rose to "
                                 f"{reading['spill_mib']} MiB; the card is spilling.")
        if len(self.rates) >= 10 and tokens_per_second < statistics.median(self.rates) / SLOW_FACTOR:
            raise SystemExit(f"STOP: {tokens_per_second:.1f} tokens a second against a usual "
                             f"{statistics.median(self.rates):.1f}; the card may be paging.")
        self.rates.append(tokens_per_second)
        if reading["temperature_c"] >= HOT_CELSIUS:
            print(f"  card at {reading['temperature_c']} C, resting {COOL_DOWN_SECONDS} s")
            self.note(event="cooling")
            time.sleep(COOL_DOWN_SECONDS)


def check_card_is_free() -> None:
    reading = card_reading()
    print(f"card: {reading['memory_used_mib']} of {reading['memory_total_mib']} MiB in use, "
          f"{reading['temperature_c']} C")
    if loaded_models():
        raise SystemExit("STOP: Ollama already has a model loaded. Run 'ollama stop <name>' first.")
    if reading["memory_used_mib"] > 3000:
        raise SystemExit("STOP: something else is using the card. Close it first.")


# ---------------------------------------------------------------------------
# Formatting one argument
# ---------------------------------------------------------------------------

def format_words(llm: str, step: int, prompt: list[dict], before: list[str],
                 words: list[str], after: list[str], depth: int = 0) -> tuple[list[str], dict]:
    """Format one chunk, splitting it once if the LLM's answer is the wrong length."""
    reply = ask(llm, prompt + [{"role": "user", "content": user_message(before, words, after)}],
                len(words))
    text, labels = clean_reply(reply["text"])
    out = text.split()
    record = {"tokens": reply["tokens"], "seconds": reply["seconds"],
              "wall_seconds": reply["wall_seconds"], "labels_removed": labels,
              "thinking": reply["thinking"], "put_back": 0, "kept_machine_words": 0,
              "raw_reply": reply["text"]}

    off = abs(len(out) - len(words)) / max(len(words), 1)
    if off > WORD_COUNT_TOLERANCE or reply["done_reason"] == "length":
        if depth == 0 and len(words) >= 40:
            half = len(words) // 2
            left, r1 = format_words(llm, step, prompt, before, words[:half], words[half:half + AFTER_WORDS], 1)
            right, r2 = format_words(llm, step, prompt, left[-BEFORE_WORDS:], words[half:], after, 1)
            merged = {k: r1[k] + r2[k] for k in ("tokens", "seconds", "wall_seconds",
                                                 "labels_removed", "put_back", "kept_machine_words")}
            merged.update(thinking=r1["thinking"] or r2["thinking"], split=True,
                          raw_reply=r1["raw_reply"] + "\n|||\n" + r2["raw_reply"])
            return left + right, merged
        record["kept_machine_words"] = len(words)
        return list(words), record

    if step == 1:
        out, record["put_back"] = lock_words(words, text)
    return out, record


def format_case(llm: str, step: int, model: str, docket: str, watchdog: Watchdog) -> None:
    path = output_path(llm, step, model, docket)
    saved = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    if saved and saved.get("done"):
        return
    words = machine_words(model, docket)
    chunks = saved["chunks"] if saved else []
    prompt = read_prompt(step)
    done_words = [w for c in chunks for w in c["output"]]
    start = chunks[-1]["end"] if chunks else 0

    first = True
    while start < len(words):
        end = min(start + CHUNK_WORDS, len(words))
        if len(words) - end < 60:   # do not leave a scrap for the last request
            end = len(words)
        out, record = format_words(llm, step, prompt, done_words[-BEFORE_WORDS:],
                                   words[start:end], words[end:end + AFTER_WORDS])
        if first:
            watchdog.after_load(llm)
            first = False
        chunks.append({"start": start, "end": end, "input": words[start:end],
                       "output": out, **record})
        done_words += out
        rate = record["tokens"] / record["seconds"] if record["seconds"] else 0.0
        watchdog.after_chunk(rate, step=step, model=model, docket=docket, chunk_end=end)
        save(path, {"llm": llm, "step": step, "model": model, "docket": docket,
                    "options": OPTIONS, "done": False, "chunks": chunks})
        start = end
        time.sleep(PAUSE_BETWEEN_CHUNKS)

    save(path, {"llm": llm, "step": step, "model": model, "docket": docket,
                "options": OPTIONS, "done": True, "chunks": chunks})


def save(path: Path, data: dict) -> None:
    """Write through a temporary file, so a crash cannot leave half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def run(args) -> None:
    check_card_is_free()
    models = [m for m in MODEL_ORDER if m in args.models] if args.models else MODEL_ORDER
    steps = args.steps or RUN_ORDER
    dockets = case_list(args.cases)
    watchdog = Watchdog(out_dir() / folder_name(args.llm) / "gpu-watch.jsonl")
    for step in steps:
        for model in models:
            for docket in dockets:
                if output_path(args.llm, step, model, docket).exists() and json.loads(
                        output_path(args.llm, step, model, docket).read_text(encoding="utf-8")).get("done"):
                    continue
                began = time.time()
                print(f"{datetime.now():%H:%M} {args.llm} step {step} {model} {docket}", flush=True)
                try:
                    format_case(args.llm, step, model, docket, watchdog)
                finally:
                    # Unloading after every argument gives back anything leaked.
                    unload(args.llm)
                    time.sleep(5)
                print(f"      done in {(time.time() - began) / 60:.1f} min", flush=True)
    print("all done")


def try_one(args) -> None:
    """Format the first chunk of one argument at each step and print it. Saves nothing."""
    check_card_is_free()
    words = machine_words(args.model, args.docket)[:CHUNK_WORDS]
    watchdog = Watchdog(out_dir() / folder_name(args.llm) / "gpu-watch.jsonl")
    try:
        for n, step in enumerate(args.steps or STEPS):
            out, record = format_words(args.llm, step, read_prompt(step), [], words, [])
            if n == 0:
                watchdog.after_load(args.llm)
            rate = record["tokens"] / record["seconds"] if record["seconds"] else 0
            print(f"\n===== step {step}: {rate:.1f} tokens/s, {record['wall_seconds']} s, "
                  f"put back {record['put_back']}, labels {record['labels_removed']}, "
                  f"thinking {record['thinking']}")
            print(" ".join(out))
        print("\n===== machine words\n" + " ".join(words))
    finally:
        unload(args.llm)


def check(args) -> None:
    """Load the model with the run's settings and report where it sits."""
    check_card_is_free()
    watchdog = Watchdog(out_dir() / folder_name(args.llm) / "gpu-watch.jsonl")
    try:
        ask(args.llm, [{"role": "user", "content": "Say OK."}], 2)
        watchdog.after_load(args.llm)
        reading = card_reading()
        model = loaded_models()[0]
        print(f"{args.llm}: {model['size'] / 2**30:.1f} GiB, "
              f"{model['size_vram'] / model['size']:.0%} on the card; card now "
              f"{reading['memory_used_mib']} of {reading['memory_total_mib']} MiB, "
              f"spill {reading['spill_mib']} MiB, {reading['temperature_c']} C")
        print("OK to run.")
    finally:
        unload(args.llm)


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def mark_after(words: list[str], i: int) -> str:
    """The punctuation mark that follows word i, if it is one we count."""
    if i + 1 < len(words) and words[i + 1] in ("--", "-"):
        return "--"
    end = words[i].rstrip("\"')")
    for mark in ("?", ",", "."):
        if end.endswith(mark):
            return mark
    return ""


def punctuation_counts(reference: list[str], hypothesis: list[str]) -> dict:
    """For words both texts share, does each have the same mark after it?"""
    alignment = align_words(reference, hypothesis, "lowercase_nopunct")
    rs, hs = alignment.reference.source_index, alignment.hypothesis.source_index
    counts = {m: {"tp": 0, "fp": 0, "fn": 0} for m in ("?", ",", ".", "--")}
    seen = set()
    for chunk in alignment.chunks:
        if chunk.kind != "equal":
            continue
        for k in range(chunk.ref_end - chunk.ref_start):
            r, h = rs[chunk.ref_start + k], hs[chunk.hyp_start + k]
            if r in seen:
                continue
            seen.add(r)
            want, got = mark_after(reference, r), mark_after(hypothesis, h)
            if want and want == got:
                counts[want]["tp"] += 1
            else:
                if got:
                    counts[got]["fp"] += 1
                if want:
                    counts[want]["fn"] += 1
    return counts


def score(args) -> None:
    dockets = case_list(args.cases)
    FINDINGS.mkdir(parents=True, exist_ok=True)
    score_rows, change_rows, broken_rows, punct_rows = [], [], [], []
    for docket in dockets:
        reference = reference_words(docket)
        for model in MODEL_ORDER:
            versions = {0: machine_words(model, docket)}
            for step in STEPS:
                path = output_path(args.llm, step, model, docket)
                if path.exists():
                    data = json.loads(path.read_text(encoding="utf-8"))
                    if data.get("done"):
                        versions[step] = [w for c in data["chunks"] for w in chunk_output(c, step)]
            wrote: dict[int, list[str]] = {}
            added: dict[int, int] = {}
            for step, words in versions.items():
                for name in NORMALIZERS:
                    alignment = align_words(reference, words, name)
                    if name == "standard":
                        ref_tokens = alignment.reference.tokens
                        wrote[step] = crowd.what_each_wrote(alignment)
                        added[step] = alignment.insertions
                    score_rows.append({"llm": args.llm, "step": step, "model": model, "docket": docket,
                                       "rule": name, "wer": alignment.wer * 100,
                                       "substitutions": alignment.substitutions,
                                       "deletions": alignment.deletions,
                                       "insertions": alignment.insertions,
                                       "reference_tokens": alignment.reference_length})
                for mark, c in punctuation_counts(reference, words).items():
                    punct_rows.append({"llm": args.llm, "step": step, "model": model,
                                       "docket": docket, "mark": mark, **c})
            # Fixed and broken words. Step 1 is compared with the raw words: they
            # are locked, so whatever moves is the normaliser scoring "1610(g)"
            # and "sixteen ten g" differently. Steps 2 and 3 are compared with
            # step 1, which writes citations the same way, so what is left is
            # the words the LLM actually changed.
            for step in versions:
                if step == 0:
                    continue
                base = 1 if step > 1 and 1 in versions else 0
                fixed = broken = 0
                for i, right in enumerate(ref_tokens):
                    before_ok, after_ok = wrote[base][i] == right, wrote[step][i] == right
                    if after_ok and not before_ok:
                        fixed += 1
                    elif before_ok and not after_ok:
                        broken += 1
                        broken_rows.append({
                            "llm": args.llm, "step": step, "compared_with": base, "model": model,
                            "docket": docket, "official": " ".join(ref_tokens[max(0, i - 4):i + 5]),
                            "word": right, "llm_wrote": wrote[step][i] or "(nothing)"})
                change_rows.append({"llm": args.llm, "step": step, "compared_with": base,
                                    "model": model, "docket": docket,
                                    "fixed": fixed, "broken": broken,
                                    "added_before": added[base], "added_after": added[step]})

    tag = folder_name(args.llm) + "-" + args.cases
    scores = pd.DataFrame(score_rows)
    scores.to_csv(FINDINGS / f"scores-{tag}.csv", index=False)
    summary = (scores.groupby(["llm", "model", "step", "rule"])["wer"].agg(["mean", "count"])
               .round(3).reset_index().rename(columns={"mean": "wer", "count": "cases"}))
    summary.to_csv(FINDINGS / f"summary-{tag}.csv", index=False)
    changes = pd.DataFrame(change_rows)
    changes.to_csv(FINDINGS / f"changes-{tag}.csv", index=False)
    broken = pd.DataFrame(broken_rows)
    if len(broken):
        broken = broken.groupby(["model", "step"]).head(300)
    broken.to_csv(FINDINGS / f"broken-words-{tag}.csv", index=False)
    punct = pd.DataFrame(punct_rows).groupby(["llm", "model", "step", "mark"])[["tp", "fp", "fn"]].sum()
    punct["precision"] = (punct.tp / (punct.tp + punct.fp)).round(3)
    punct["recall"] = (punct.tp / (punct.tp + punct.fn)).round(3)
    punct.reset_index().to_csv(FINDINGS / f"punctuation-{tag}.csv", index=False)

    print(summary.pivot_table(index=["model", "step"], columns="rule", values="wer").round(2))
    if len(changes):
        print(changes.groupby(["model", "step"])[["fixed", "broken"]].sum())
    check_baseline(scores)


def check_baseline(scores: pd.DataFrame) -> None:
    """Step 0 must reproduce the published per-case figures exactly."""
    worst = 0.0
    for model, run in crowd.RUNS.items():
        published = CAPSTONE / "findings" / run / "scores.csv"
        mine = scores[(scores.step == 0) & (scores.model == model)]
        if mine.empty or not published.exists():
            continue
        p = pd.read_csv(published).set_index(["docket", "normalizer"])["wer_percent"]
        for row in mine.itertuples():
            worst = max(worst, abs(row.wer - p.loc[(row.docket, row.rule)]))
    print(f"step 0 against the published scores: largest difference {worst:.4f} points")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("check", "try", "run", "score"):
        p = sub.add_parser(name)
        p.add_argument("--llm", default="gemma4:31b")
        p.add_argument("--steps", type=int, nargs="*")
        if name in ("run", "score"):
            p.add_argument("--cases", choices=["pilot", "sample", "all"], default="pilot")
        if name == "run":
            p.add_argument("--models", nargs="*")
        if name == "try":
            p.add_argument("--model", default="Qwen3")
            p.add_argument("--docket", default=PILOT[0])
    args = parser.parse_args()
    {"check": check, "try": try_one, "run": run, "score": score}[args.command](args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
