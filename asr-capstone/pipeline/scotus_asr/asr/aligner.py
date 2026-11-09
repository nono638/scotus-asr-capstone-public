"""Putting times on a transcript that came without any.

Most recent speech models produce text and nothing else. Qwen3-ASR does, and so
does Canary - its model card advertises word timings, but the transformers
documentation says plainly that those come from NVIDIA's own aligner and "are not
part of the `generate` output". The decoder has a `<|timestamp|>` token in its
vocabulary and never emits one.

This project cannot use a transcript without times. The silence measure needs to
know which seconds have no word against them, and a dropped passage has to be
locatable in the recording before anybody can listen to it. So a model that gives
no times needs a second model that supplies them.

A forced aligner is that second model. It is given the audio and the words
already known to be in it, and asked only where each one sits - no decoding, no
choosing between candidate words. One forward pass, about a twentieth of a second
for five minutes of audio, so the cost is the extra weights in memory rather than
the time.

**Why this is shared rather than copied.** Qwen3-ASR shows far more silence than
the models with their own timings, and there are two possible reasons: the model
really does drop more, or the aligner puts words in the wrong places and invents
gaps between them. Those cannot be told apart from Qwen3 alone. Running a second
aligned model through the identical aligner separates them - if it looks like the
natively-timed models, the aligner is not the problem. That argument only holds
if it is the same aligner, so there is one of these and all four engines that need it call it.

**Five minutes is the limit.** The aligner handles that much audio at a time,
which is why every engine depending on it cuts the recording into pieces smaller
than that.

**It strips punctuation, and `align` puts it back.** The aligner returns bare
words. Kept that way, an engine routed through it is scored as though it wrote no
commas and no full stops - which on the verbatim measure, the one this project
exists to make, reads as the model tidying away the record. See the note in
`align`.
"""

from __future__ import annotations

from typing import Any

from .base import Word

#: The forced aligner's Hugging Face repository. Qwen's, and used for models that
#: have nothing to do with Qwen - alignment does not care who wrote the words.
ALIGNER_ID = "Qwen/Qwen3-ForcedAligner-0.6B-hf"

#: How much audio the aligner takes in one pass, in seconds. Engines that use it
#: must keep their chunks under this.
MAX_SECONDS = 300.0


def with_marks(text: str, timed: list[dict]) -> list[tuple[str, float, float]]:
    """The engine's own tokens, with the aligner's times: (token, start, end).

    The aligner returns one entry per token that has a letter or digit in it, so a token
    of marks alone, such as "--", has no entry and the counts differ. Until November 2026
    any difference made the whole chunk take the aligner's bare words, which lost every
    comma and full stop in it (bug-audit-2026-11-05.md). Now a token of marks alone sits
    where the word before it ended. If the counts still differ, the two lists are lined up
    by their letters and digits, so no word takes another word's time, and a token the
    aligner has no entry for sits where the word before it ended too.
    """
    import difflib

    spoken = text.split()
    plain = lambda token: "".join(c for c in token.lower() if c.isalnum())
    times: list[tuple[float, float] | None] = [None] * len(spoken)
    stamps = [(float(t["start_time"]), float(t["end_time"])) for t in timed]
    worded = [i for i, token in enumerate(spoken) if plain(token)]
    if len(worded) == len(timed):
        for i, stamp in zip(worded, stamps):
            times[i] = stamp
    else:
        matcher = difflib.SequenceMatcher(None, [plain(t) for t in spoken],
                                          [plain(str(t["text"])) for t in timed], autojunk=False)
        for block in matcher.get_matching_blocks():
            for n in range(block.size):
                times[block.a + n] = stamps[block.b + n]
    if not any(times):
        return [(str(t["text"]), *stamp) for t, stamp in zip(timed, stamps)]

    out, last = [], next(t for t in times if t)[0]
    for token, stamp in zip(spoken, times):
        start, end = stamp if stamp else (last, last)
        last = end
        out.append((token, start, end))
    return out


def aligner_compute_type(settings) -> str:
    """The aligner's precision for an engine's settings: `float16` or `float32`.

    It used to follow the engine's own `compute_type` without saying so:
    `float16` gave a float16 aligner and anything else, including the
    `bfloat16` Voxtral and the Granites run in, gave float32. So the "identical
    aligner" the note above relies on ran at float16 for Qwen3 and Canary and
    float32 for the others.

    Now it can be set on its own, as `aligner_compute_type` under
    `engine_options`, and every result records it. Left unset, it follows the
    old rule, so the runs already published can be repeated exactly.
    """
    chosen = settings.engine_options.get("aligner_compute_type")
    if chosen is None:
        return "float16" if settings.compute_type == "float16" else "float32"
    if chosen not in ("float16", "float32"):
        raise ValueError(
            f"aligner_compute_type must be float16 or float32, not {chosen!r}"
        )
    return chosen


#: Rough peak memory of the aligner itself, for the engines' own estimates.
APPROX_VRAM_GB = 1.2


class ForcedAligner:
    """Says where each word of a known transcript sits in the audio.

    The model loads on first use and is kept, like the engines themselves. One
    instance per run rather than per case: loading it per case is how an earlier
    version of this project filled the card and slowed to a crawl without ever
    raising an error.

    Args:
        device: Where to put the weights, e.g. `cuda`.
        compute_type: `float16` or `float32`, matching the engine it serves.
    """

    def __init__(self, device: str = "cuda", compute_type: str = "float16") -> None:
        self.device = device
        self.compute_type = compute_type
        self._model: Any = None
        #: The aligner's own processor, and it has to be its own.
        #:
        #: `prepare_forced_aligner_inputs` builds a conversation of one text item
        #: per word and leaves the chat template to wrap each one in the
        #: timestamp markers the decoder later looks for. A transcriber's
        #: template does not write those markers. Borrowing it produces inputs
        #: with none of them, a mask that selects nothing, and a decode that
        #: fails on an empty array rather than on anything naming the cause.
        self._processor: Any = None

    @property
    def repo_id(self) -> str:
        """Which aligner this is, for the settings a run records."""
        return ALIGNER_ID

    def load(self) -> None:
        """Load the aligner and its processor, once."""
        if self._model is not None:
            return

        import torch  # noqa: PLC0415 - late, so listing engines pulls in no CUDA
        from transformers import (  # noqa: PLC0415
            AutoModelForTokenClassification,
            AutoProcessor,
        )

        dtype = torch.float16 if self.compute_type == "float16" else torch.float32
        self._processor = AutoProcessor.from_pretrained(ALIGNER_ID)
        self._model = (
            AutoModelForTokenClassification.from_pretrained(ALIGNER_ID, dtype=dtype)
            .to(self.device)
            .eval()
        )

    def align(
        self, audio, text: str, language: str = "en", offset: float = 0.0
    ) -> list[Word]:
        """Time the words of one chunk, placed in the whole recording.

        Args:
            audio: The chunk, as 16 kHz mono samples. Must be under
                `MAX_SECONDS`.
            text: What was said in it, as the transcriber produced it.
            language: Which language, passed through to the aligner.
            offset: Where this chunk begins in the recording, in seconds. Added
                to every time, so the words come back on the recording's clock
                rather than the chunk's.

        Returns:
            One `Word` per word of `text`, in order. Empty when there is no text
            to place, or when the aligner returns nothing for it.
        """
        import torch  # noqa: PLC0415

        if not text.strip():
            return []

        self.load()
        inputs, word_lists = self._processor.prepare_forced_aligner_inputs(
            audio=audio, transcript=text, language=language, return_tensors="pt"
        )
        dtype = torch.float16 if self.compute_type == "float16" else torch.float32
        inputs = inputs.to(self.device, dtype=dtype)

        with torch.no_grad():
            logits = self._model(**inputs).logits

        stamped = self._processor.decode_forced_alignment(
            logits,
            inputs["input_ids"],
            word_lists,
            self._model.config.timestamp_token_id,
        )
        if not stamped:
            return []

        timed = stamped[0]

        # Put the punctuation back.
        #
        # The aligner strips it. Given "Mr. Chief Justice, and may it please the
        # Court:" it returns Mr / Chief / Justice / and / may / it / please / the
        # / Court - one entry per whitespace-separated token of the input, in
        # order, with the marks removed and the capitals kept.
        #
        # Left alone that quietly rewrites the experiment. This project scores
        # three ways and the strictest, `verbatim`, counts punctuation and
        # capitals as part of the record - that comparison is the thesis. An
        # engine whose text arrives stripped is charged for every comma it
        # actually produced, and the fault looks like the model tidying the
        # record when it is this function discarding it. Whisper and Parakeet
        # carry their own timings and never pass through here, so the effect
        # lands on some engines and not others, which is the worst version of it.
        #
        # The leading space matches what Whisper and Parakeet produce, so the
        # scoring code sees one shape of word list whatever made it.
        return [
            Word(text=f" {word}", start=start + offset, end=end + offset, probability=None)
            for word, start, end in with_marks(text, timed)
        ]
