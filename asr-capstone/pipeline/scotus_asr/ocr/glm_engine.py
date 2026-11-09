"""Reading page text with GLM-OCR.

A 0.9B model built only for document recognition, MIT licensed. It is small
enough to read thousands of pages unattended and currently leads OmniDocBench,
ahead of general vision models many times its size - which is the 2026 story in
document recognition: a specialist beats a generalist at this one job.

It is never shown the left margin. The image handed to it is cropped so the line
numbers are not in it, which is what makes it safe to use here. A model asked to
transcribe a column of bare integers has almost no linguistic signal to work from
and will supply the number that ought to come next whether or not the ink is
there. Cropping removes the opportunity rather than relying on an instruction.

So the division of labour is: geometry decides structure, this decides words.
Neither is asked to do the other's job.
"""

from __future__ import annotations

import logging
from typing import Any

from ..gpu import ensure_cuda_libraries

logger = logging.getLogger(__name__)

#: What the model card recommends for plain document transcription. The other
#: documented prompts ("Formula Recognition:", "Table Recognition:") are for
#: material these transcripts do not contain.
DEFAULT_PROMPT = "Text Recognition:"


class GlmOcrEngine:
    """Reads the body of a page and returns its text.

    The model is loaded the first time a page is read rather than in the
    constructor, so building the list of work for a run costs nothing and a run
    where every page is already done never touches the GPU.

    Args:
        model_id: Which weights to use.
        device: `cuda` or `cpu`.
        prompt: What to ask for. The default is plain transcription.
        max_new_tokens: Ceiling on the output. A transcript page holds about 25
            lines of roughly twelve words, so 1024 is comfortable; the cap exists
            to stop a confused model generating indefinitely on a blank page and
            stalling an overnight run.
    """

    def __init__(
        self,
        model_id: str = "zai-org/GLM-OCR",
        device: str = "cuda",
        prompt: str = DEFAULT_PROMPT,
        max_new_tokens: int = 1024,
    ) -> None:
        self.model_id = model_id
        self.device = device
        self.prompt = prompt
        self.max_new_tokens = max_new_tokens
        self._model: Any = None
        self._tokenizer: Any = None

    @property
    def name(self) -> str:
        """Used in filenames and in the results tables."""
        return "glm-ocr"

    def _load(self) -> tuple[Any, Any]:
        """Load the model and its processor, once.

        The processor, not the tokenizer. This matters and is easy to get wrong:
        the model card's own example uses `AutoTokenizer.apply_chat_template`,
        and on transformers 5 that returns `input_ids` and `attention_mask` and
        **no pixel data at all**. The image is dropped without a word of warning,
        the model receives a text-only prompt, and it answers with an empty
        document - which reads exactly like a blank page rather than like a bug.
        """
        if self._model is not None:
            return self._model, self._tokenizer

        ensure_cuda_libraries()

        # Imported late so that the rest of the pipeline, and the tests, run
        # without loading transformers and the CUDA libraries behind it.
        import torch
        from transformers import AutoModelForMultimodalLM, AutoProcessor

        logger.info("Loading %s onto %s", self.model_id, self.device)

        self._tokenizer = AutoProcessor.from_pretrained(self.model_id)
        self._model = AutoModelForMultimodalLM.from_pretrained(
            self.model_id,
            dtype=torch.float16 if self.device == "cuda" else torch.float32,
            device_map=self.device,
        )
        self._model.eval()
        return self._model, self._tokenizer

    def read(self, image: Any) -> str:
        """Read one cropped page image.

        Args:
            image: A PIL image of the body of a page, with the margin already
                cropped away.

        Returns:
            The text, one line per line of the page. Blank if the model produced
            nothing - which is a real answer for a blank page, and is left blank
            rather than guessed at.
        """
        model, processor = self._load()

        import torch

        # Three channels, always. A grey image comes back from the contrast step
        # and the vision side expects colour.
        picture = image.convert("RGB")

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": picture},
                    {"type": "text", "text": self.prompt},
                ],
            }
        ]

        inputs = processor.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
        ).to(model.device)

        # The failure this guards against is silent: if the image is dropped,
        # generation still succeeds and returns an empty document, which looks
        # like a blank page rather than like a mistake.
        if "pixel_values" not in inputs and "pixel_values_videos" not in inputs:
            raise RuntimeError(
                "The image did not reach the model - the prepared inputs carry "
                "no pixel data. Any text this produced would be invented, so "
                "nothing is returned."
            )

        with torch.inference_mode():
            outputs = model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                # Greedy. This is transcription, not writing: there is one right
                # answer and sampling can only move away from it.
                do_sample=False,
            )

        # Everything after the prompt is the answer.
        generated = outputs[0][inputs["input_ids"].shape[-1]:]
        text = processor.decode(generated, skip_special_tokens=True)
        return _strip_code_fence(text)


def _strip_code_fence(text: str) -> str:
    """Remove the markdown fence the model wraps its answer in.

    GLM-OCR returns document text inside a ```markdown block. The fence is
    presentation, not content, and would otherwise be scored as words nobody
    said.
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        # Drop the opening fence, and the closing one if it is there.
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines)
    return cleaned.strip()
