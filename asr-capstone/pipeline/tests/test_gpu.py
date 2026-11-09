"""Tests for making the CUDA libraries findable.

These exist because of a real failure that cost real time. CTranslate2 reported
`cublas64_12.dll is not found or cannot be loaded` while the file was sitting in
`site-packages/torch/lib` the whole time - it just was not anywhere Windows looks
for a bare library name. The error reads like a missing installation, so these
tests pin down the behaviour that makes it not happen again.
"""

from __future__ import annotations

import os

import pytest

from scotus_asr import gpu


def test_the_library_folders_are_found_if_they_exist():
    """On this machine PyTorch's CUDA build supplies them."""
    folders = gpu.find_cuda_library_dirs()
    # Not asserting there are any - the work laptop has none, and that is fine.
    assert all(folder.is_dir() for folder in folders)


def test_adding_the_folders_is_safe_to_repeat():
    """Called before every model load, so it must not grow the PATH each time."""
    gpu.ensure_cuda_libraries()
    after_first = os.environ.get("PATH", "")

    gpu.ensure_cuda_libraries()
    gpu.ensure_cuda_libraries()

    assert os.environ.get("PATH", "") == after_first


def test_the_folders_end_up_on_the_path():
    """The PATH is what CTranslate2 actually searches.

    `os.add_dll_directory` alone does not work - that was tried, and the load
    still failed. This is the part that matters.
    """
    gpu.ensure_cuda_libraries()
    folders = gpu.find_cuda_library_dirs()
    if not folders:
        return  # a machine without the CUDA build of PyTorch

    path_parts = {part.lower() for part in os.environ.get("PATH", "").split(os.pathsep)}
    assert any(str(folder).lower() in path_parts for folder in folders)


def test_describing_the_gpu_never_raises():
    """Said at the start of every run, including on the laptop without a card."""
    description = gpu.describe_gpu()
    assert isinstance(description, str) and description


def test_asking_for_absurd_memory_is_refused_with_a_reason():
    """And the reason names the usual culprit on this machine."""
    enough, reason = gpu.enough_memory(10_000)
    assert not enough
    assert reason


def test_a_small_request_is_allowed_when_a_gpu_is_present():
    if not gpu.cuda_libraries_ready():
        return
    enough, _reason = gpu.enough_memory(0.001)
    assert enough


def test_the_ceiling_on_the_5090_is_what_it_was():
    """23.89 GB with the desktop holding 1.3: the old fixed 92%, so nothing
    measured on that laptop changes."""
    assert gpu.share_for(23.89, others_gb=1.3) == pytest.approx(0.92)


def test_a_small_card_keeps_enough_for_the_desktop():
    """8% of an 8 GB card is 0.6 GB, too little; the floor leaves 1.5."""
    assert 8 * (1 - gpu.share_for(8.0)) == pytest.approx(1.5)


def test_the_ceiling_counts_what_other_programs_hold():
    """Ollama holding 10 GB of 24: the run may not plan on that memory."""
    share = gpu.share_for(24.0, others_gb=10.0)
    assert 24 * share == pytest.approx(13.5)


def test_device_strings_name_the_right_card():
    assert gpu.device_index("cuda") == 0
    assert gpu.device_index("cuda:1") == 1


def test_preparing_for_the_processor_does_nothing():
    """A run set to the processor has no card to protect."""
    gpu.prepare_gpu("cpu", 10_000, "anything")


def test_preparing_refuses_a_model_bigger_than_the_card():
    import torch

    if not torch.cuda.is_available():
        with pytest.raises(RuntimeError, match="cannot see one"):
            gpu.prepare_gpu("cuda", 1.0, "a model")
        return
    with pytest.raises(RuntimeError, match="Not enough video memory"):
        gpu.prepare_gpu("cuda", 10_000, "a model", cap=False)
