"""Tests for choosing models to compare, and for tools/crowd.py on any number of them.

The runs are built in a temporary folder: a reference and one engine's output per
run, a few words each.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from scotus_asr.model_sets import ModelSet, discover, engines_in, from_pair, load_set
from scotus_asr.transcripts.model import Transcript, Turn

CAPSTONE = Path(__file__).resolve().parents[2]
REFERENCE = "OKAY SO WHERE DID YOU GROW UP I GREW UP IN LAGOS MOSTLY"


def make_run(runs_dir: Path, run: str, engine: str, said: dict[str, str],
             reference: str = REFERENCE) -> Path:
    """A run folder holding one engine's output for each recording in `said`."""
    folder = runs_dir / run
    (folder / "asr").mkdir(parents=True)
    (folder / "reference").mkdir()
    for recording, text in said.items():
        transcript = Transcript(docket=recording, turns=[
            Turn(speaker="A", text=reference, start=0.0, end=10.0)])
        (folder / "reference" / f"{recording}.json").write_text(
            json.dumps(transcript.to_dict()), encoding="utf-8")
        words = [{"text": w, "start": i * 0.5, "end": i * 0.5 + 0.4}
                 for i, w in enumerate(text.split())]
        (folder / "asr" / f"{recording}.{engine}.json").write_text(json.dumps({
            "docket": recording, "engine": engine, "model": engine, "audio_seconds": 10.0,
            "segments": [{"index": 0, "start": 0.0, "end": 10.0, "text": text, "words": words}],
        }), encoding="utf-8")
    return folder


class TestFindingRuns:
    def test_engines_in_reads_the_file_names(self, tmp_path):
        run = make_run(tmp_path, "run-1", "Qwen3-ASR-1.7B-hf", {"R1": "a", "R2": "b"})
        (run / "asr" / "R3.partial.jsonl").write_text("", encoding="utf-8")   # not finished
        assert engines_in(run) == {"Qwen3-ASR-1.7B-hf": {"R1", "R2"}}

    def test_discovery_takes_each_engines_most_complete_run(self, tmp_path):
        make_run(tmp_path, "run-1", "whisper", {"R1": "a", "R2": "b"})
        make_run(tmp_path, "run-2", "whisper", {"R1": "a"})          # newer but smaller
        make_run(tmp_path, "run-3", "parakeet", {"R1": "a"})
        make_run(tmp_path, "superseded-run-4", "parakeet", {"R1": "a", "R2": "b"})
        found = {m.engine: m.run_dir.name for m in discover(tmp_path)}
        assert found == {"whisper": "run-1", "parakeet": "run-3"}

    def test_a_tie_goes_to_the_newest_run(self, tmp_path):
        make_run(tmp_path, "run-1", "whisper", {"R1": "a"})
        make_run(tmp_path, "run-2", "whisper", {"R1": "a"})
        assert discover(tmp_path)[0].run_dir.name == "run-2"

    def test_names_pick_engines_by_prefix(self, tmp_path):
        make_run(tmp_path, "run-1", "Qwen3-ASR-1.7B-hf", {"R1": "a"})
        make_run(tmp_path, "run-2", "whisper-large-v3", {"R1": "a"})
        chosen = discover(tmp_path, ["whisper", "qwen3"])
        assert [m.engine for m in chosen] == ["whisper-large-v3", "Qwen3-ASR-1.7B-hf"]
        with pytest.raises(ValueError, match="Known"):
            discover(tmp_path, ["canary"])

    def test_a_pair_names_a_run(self, tmp_path):
        run = make_run(tmp_path, "run-1", "whisper", {"R1": "a"})
        model = from_pair(f"Whisper={run}")
        assert (model.name, model.engine) == ("Whisper", "whisper")
        with pytest.raises(ValueError, match="Name=run"):
            from_pair("just-a-path")

    def test_a_run_with_two_engines_is_refused(self, tmp_path):
        run = make_run(tmp_path, "run-1", "whisper", {"R1": "a"})
        (run / "asr" / "R1.parakeet.json").write_text("{}", encoding="utf-8")
        with pytest.raises(ValueError, match="2 engines"):
            from_pair(f"X={run}")


class TestModelSets:
    def test_a_set_file_with_relative_runs(self, tmp_path):
        make_run(tmp_path, "run-1", "whisper", {"R1": "a", "R2": "b"})
        make_run(tmp_path, "run-2", "parakeet", {"R1": "a"})
        settings = tmp_path / "set.yaml"
        settings.write_text(f"runs_dir: {tmp_path.as_posix()}\npivot: Parakeet\n"
                            "models:\n  Whisper: run-1\n  Parakeet: run-2\n", encoding="utf-8")
        chosen = load_set(settings)
        assert chosen.names == ["Whisper", "Parakeet"] and chosen.pivot == "Parakeet"
        shared, missing = chosen.shared_recordings()
        assert shared == ["R1"] and missing == {"Parakeet": ["R2"]}

    def test_the_pivot_defaults_to_the_first_model(self, tmp_path):
        a = from_pair(f"A={make_run(tmp_path, 'run-1', 'x', {'R': 'a'})}")
        b = from_pair(f"B={make_run(tmp_path, 'run-2', 'y', {'R': 'a'})}")
        assert ModelSet([a, b]).pivot == "A"

    def test_one_model_is_not_a_comparison(self, tmp_path):
        a = from_pair(f"A={make_run(tmp_path, 'run-1', 'x', {'R': 'a'})}")
        with pytest.raises(ValueError, match="at least two"):
            ModelSet([a])

    def test_an_unknown_pivot_is_refused(self, tmp_path):
        a = from_pair(f"A={make_run(tmp_path, 'run-1', 'x', {'R': 'a'})}")
        b = from_pair(f"B={make_run(tmp_path, 'run-2', 'y', {'R': 'a'})}")
        with pytest.raises(ValueError, match="pivot"):
            ModelSet([a, b], pivot="C")

    def test_the_supreme_court_set_lists_seven(self):
        import yaml
        data = yaml.safe_load((CAPSTONE / "pipeline/config/model-sets/scotus-seven.yaml")
                              .read_text(encoding="utf-8"))
        assert len(data["models"]) == 7 and data["pivot"] == "Whisper"


def _crowd():
    spec = importlib.util.spec_from_file_location("crowd", CAPSTONE / "tools" / "crowd.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestCrowdThresholds:
    def test_seven_models_keep_the_study_numbers(self):
        assert _crowd().thresholds(7) == (4, 6, 1)

    def test_three_models(self):
        crowd = _crowd()
        assert crowd.thresholds(3) == (2, 2, 0)
        assert crowd.kind_of_position(["x", "x", "y"], "y") == "against"   # two agree, wrong
        assert crowd.kind_of_position(["y", "x", "z"], "y") == "split"
        assert crowd.kind_of_position(["y", "y", "z"], "y") == "easy"
        assert crowd.kind_of_position(["a", "b", "c"], "y") == "nobody"

    def test_the_label_names_the_number_of_models(self):
        crowd = _crowd()
        assert crowd.what_the_machines_did(0, 7) == "all seven wrote the same other thing"
        assert crowd.what_the_machines_did(0, 3, n=3) == "all three wrote the same other thing"
        assert crowd.what_the_machines_did(0, 2, n=2) == "both wrote the same other thing"

    def test_the_old_names_still_describe_the_seven(self):
        crowd = _crowd()
        assert len(crowd.MODELS) == 7 and crowd.PIVOT == "Whisper"


def test_crowd_end_to_end_on_three_models(tmp_path):
    """Three made-up models on two recordings of an all-capitals reference."""
    runs = tmp_path / "runs"
    said = {
        "a": "okay so where did you grow up i grew up in lagos mostly",
        "b": "okay where did you grow up i grew up in lagos mostly",
        "c": "okay where did you go up i grew up in lagos",
    }
    paths = {name: make_run(runs, f"run-{name}", f"engine-{name}", {"R1": text, "R2": text})
             for name, text in said.items()}
    out = tmp_path / "out"
    command = [sys.executable, str(CAPSTONE / "tools" / "crowd.py"), "--out", str(out)]
    for name, path in paths.items():
        command += ["--model", f"{name.upper()}={path}"]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr

    heard = pd.read_csv(out / "heard-by.csv")
    assert list(heard.heard_by) == [0, 1, 2, 3]
    models = pd.read_csv(out / "models-and-vote.csv")
    assert list(models.model) == ["A", "B", "C"]
    assert models.set_index("model").loc["A", "wer_pct"] == 0.0
    used = pd.read_csv(out / "runs-used.csv")
    assert used.recordings_compared.tolist() == [2, 2, 2] and used["pivot"].tolist() == [True, False, False]
    # No dashes in the reference, so no interruptions table.
    assert not (out / "interruptions.csv").exists()
    # "so" left out by B and C: two of three agree against the reference.
    against = pd.read_csv(out / "against-the-record.csv")
    assert (against.record_normalised == "so").any()
    # All capitals: nothing may be labelled a name for being capitalised.
    assert not against.what_happened.eq("name or legal term").any()


def test_crowd_leaves_out_what_the_reference_leaves_out(tmp_path):
    """Words in an ignored stretch count neither way, as in the scoring stage.

    EdAcc marks each speaker's read-aloud passage this way. Here the models
    transcribe two extra words in the first second, which the reference skips.
    """
    runs = tmp_path / "runs"
    text = "please call stella " + REFERENCE.lower()
    paths = [make_run(runs, f"run-{n}", f"engine-{n}", {"R1": text}) for n in "ab"]
    for path in paths:
        ref = path / "reference" / "R1.json"
        data = json.loads(ref.read_text(encoding="utf-8"))
        data["ignore"] = [[0.0, 1.45]]   # covers the first three words' midpoints
        ref.write_text(json.dumps(data), encoding="utf-8")
    out = tmp_path / "out"
    command = [sys.executable, str(CAPSTONE / "tools" / "crowd.py"), "--out", str(out),
               "--model", f"A={paths[0]}", "--model", f"B={paths[1]}"]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    models = pd.read_csv(out / "models-and-vote.csv").set_index("model")
    assert models.loc["A", "insertions"] == 0 and models.loc["A", "wer_pct"] == 0.0
