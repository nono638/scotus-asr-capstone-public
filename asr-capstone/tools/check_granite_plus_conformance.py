"""Check the Granite Plus engine against IBM's published model card.

Written because "we followed best practices" is a claim, and a claim that costs
thirty-eight hours of machine time to act on deserves a test rather than an
assurance. This project has twice set a parameter from an assumption and paid
for it - Granite's 100-second chunks and Parakeet's missing generation ceiling -
so the point here is that a mismatch fails loudly.

It downloads the model card and compares it against the engine's own constants.
Nothing is loaded onto the card, so it is safe to run while a job is in flight.

Three kinds of result:

    OK    a value that matches what IBM document
    DEV   a deliberate departure, with the reason it was made
    FAIL  the engine and the card disagree, or a quotation here is wrong

Usage:
    python tools/check_granite_plus_conformance.py
    python tools/check_granite_plus_conformance.py --card some/local/README.md
"""

from __future__ import annotations

import argparse
import inspect
import re
import sys
import urllib.request
from pathlib import Path

CAPSTONE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CAPSTONE / "pipeline"))

CARD_URL = (
    "https://huggingface.co/ibm-granite/granite-speech-4.1-2b-plus/raw/main/README.md"
)


def fetch_card(local: Path | None) -> str:
    """IBM's model card, from disk if given one and from the hub otherwise."""
    if local is not None:
        return local.read_text(encoding="utf-8")
    with urllib.request.urlopen(CARD_URL, timeout=60) as response:
        return response.read().decode("utf-8")


def python_string_from_card(card: str, name: str) -> str | None:
    """The value of a Python string literal in the card's code examples.

    The card is markdown, so a prompt written in its code block appears with
    its escapes intact - `\\n` is a backslash and an n, not a newline. Comparing
    our constant against the raw markdown would therefore fail on any prompt
    containing an escape, which is how the first version of this check reported
    a false mismatch on the system prompt. Decoding the literal the way Python
    would is the fix.
    """
    found = re.search(rf'{name} = "(.*?)"', card, re.S)
    if not found:
        return None
    return found.group(1).encode().decode("unicode_escape")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--card", type=Path,
        help="A saved copy of the model card, instead of fetching it.",
    )
    args = parser.parse_args(argv)

    card = fetch_card(args.card)

    from scotus_asr.asr import granite_plus_engine as g
    from scotus_asr.asr.base import sampling_options
    from scotus_asr.asr.registry import build_engine
    from scotus_asr.config import AsrSettings

    source = inspect.getsource(g)
    engine = build_engine(
        AsrSettings(engine="granite-plus", model="granite-speech-4.1-2b-plus",
                    device="cuda", compute_type="bfloat16", language="en")
    )
    used = engine.settings_used()

    ok: list[str] = []
    dev: list[str] = []
    bad: list[str] = []

    def prompt_matches(label: str, ours: str, name: str) -> None:
        """Our prompt must be what the card's code example assigns."""
        theirs = python_string_from_card(card, name)
        if theirs is None:
            bad.append(f"{label}: no `{name} = \"...\"` found in the card. "
                       f"Either IBM renamed it or the card changed shape.")
        elif ours == theirs:
            ok.append(f"{label}: byte-identical to the card's {name}")
        else:
            bad.append(f"{label}: DIFFERS from the card\n"
                       f"        ours:  {ours!r}\n"
                       f"        card:  {theirs!r}")

    def present(label: str, needle: str, why: str) -> None:
        if needle in source:
            ok.append(f"{label}: {why}")
        else:
            bad.append(f"{label}: expected {needle!r} in the engine, not found")

    # --- the prompts, which decide what this model produces -----------------
    #
    # Load-bearing rather than cosmetic. The base Granite writes no capital
    # letters when asked IBM's default way and punctuates when asked IBM's 4.1
    # way, on the same audio and the same weights. And IBM warn that "if an
    # unfamiliar or malformed prompt is received, the model simply ignores it
    # and performs transcription" - so a mistyped timestamp prompt would not
    # error, it would quietly return untagged text and the run would produce no
    # timings at all while looking perfectly healthy.
    prompt_matches("timestamp prompt", g.TIMESTAMP_PROMPT, "TS_PROMPT")
    prompt_matches("speaker prompt", g.SPEAKER_PROMPT, "SAA_PROMPT")
    prompt_matches("system prompt", g.SYSTEM_PROMPT, "SYSTEM_PROMPT")

    # --- loading, as the card's example does it ------------------------------
    present("processor class", "AutoProcessor.from_pretrained", "the card's class")
    present("model class", "AutoModelForSpeechSeq2Seq.from_pretrained",
            "the card's class")
    present("eval mode", ".eval()", "the card calls model.eval()")
    present("device placement", "device_map=self.settings.device",
            "the card passes device_map=device")

    # --- generation, as the card's example does it ---------------------------
    present("greedy decoding", "num_beams=1", "the card passes num_beams=1")
    present("chat template", "add_generation_prompt=True",
            "the card passes tokenize=False, add_generation_prompt=True")
    present("prompt trimmed off", "produced[:, prompt_length:]",
            "the card slices outputs[0, inputs['input_ids'].shape[-1]:]")
    present("decode flags", "skip_special_tokens=True",
            "the card passes add_special_tokens=False, skip_special_tokens=True")
    present("rollover unwrap", "rollovers += 10.0",
            "the card's t = N/100 + 10R, walked forward as their example does")

    # What generate() is actually handed, rather than what this module's text
    # says. `do_sample=False` reaches it through the shared sampling_options
    # helper in base.py, so grepping this file for it - as the first version of
    # this check did - reports a false mismatch.
    effective = sampling_options(0.0)
    if effective == {"do_sample": False} and "do_sample=False" in card:
        ok.append("no sampling: generate() receives do_sample=False, as the card does")
    else:
        bad.append(f"no sampling: generate() would receive {effective}, "
                   f"card passes do_sample=False")

    # --- audio format -------------------------------------------------------
    if g.SAMPLE_RATE == 16_000:
        ok.append("sample rate: 16 kHz, as the card requires")
    else:
        bad.append(f"sample rate: {g.SAMPLE_RATE}, the card says 16000")
    present("mono", "mono=True", "the card casts to num_channels=1")

    # --- the documented ceiling we must sit under ---------------------------
    ceiling_sentence = (
        "up to 9 minutes long for ASR and SAA, and up to 3.5 minutes for timestamps"
    )
    if ceiling_sentence not in card:
        bad.append("the card no longer contains the 3.5-minute sentence this "
                   "engine's chunk length was chosen against - re-read it")
    elif g.CHUNK_SECONDS <= 210:
        ok.append(f"chunk length: {g.CHUNK_SECONDS:.0f}s, inside the card's 3.5 "
                  f"minutes (210s) for timestamp mode")
    else:
        bad.append(f"chunk length: {g.CHUNK_SECONDS:.0f}s EXCEEDS the card's 210s")

    # --- deviations, which must be deliberate and recorded ------------------
    if used.get("loop_remedy"):
        dev.append(
            f"loop remedy: {used['loop_remedy']}. The card gives no guidance on "
            f"repetition at all. Measured: the temperature ladder every other "
            f"engine here uses failed six times out of six on both chunks that "
            f"needed it; splitting recovered both."
        )
    budget = g.MAX_TOKENS_PER_SECOND * g.CHUNK_SECONDS
    if budget < 10_000:
        dev.append(
            f"generation ceiling: {g.MAX_TOKENS_PER_SECOND:.0f} tokens a second, "
            f"so {budget:.0f} for a {g.CHUNK_SECONDS:.0f}s chunk, against the "
            f"card's flat max_new_tokens=10000. Lower on purpose - measured need "
            f"is 22.2 a second, and an unbounded ceiling is what let Parakeet "
            f"return 42,639 words from ten minutes of audio."
        )
    if "prefix_text" not in source:
        dev.append(
            "incremental decoding: the card offers `prefix_text` to hand the "
            "model its previous transcript as context, and says it can improve "
            "accuracy. NOT used. This project stitches chunks with an 8-second "
            "overlap and a midpoint rule, the same way for all six other "
            "engines, and comparability across engines was preferred to a "
            "per-model feature. Worth testing separately rather than assuming."
        )
    if "start=previous_end" in source.replace(" ", "").replace("\n", ""):
        dev.append(
            "word start times: inferred from the previous word's end, because "
            "the card emits only end times. Exact for continuous speech, and "
            "the reason the `_` silence tokens must keep their timing."
        )

    for line in ok:
        print(f"  OK    {line}")
    if dev:
        print()
    for line in dev:
        print(f"  DEV   {line}")
    if bad:
        print()
    for line in bad:
        print(f"  FAIL  {line}")

    print()
    print(f"{len(ok)} matched, {len(dev)} deliberate deviations, {len(bad)} problems")
    if bad:
        print("\nSomething the vendor documents is contradicted. Do not start a "
              "run until this is understood.")
        return 1
    print("Nothing IBM documents is contradicted, and every departure is "
          "recorded in settings_used() or the engine's notes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
