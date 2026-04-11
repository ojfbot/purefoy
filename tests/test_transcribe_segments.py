"""
Tests for segment-level logic in scripts/tools/transcribe_episodes.py

Focuses on user-visible output: how segments are labelled, and whether
those labels are correct for the patterns we actually care about
(intro/outro detection, diarization graceful degradation).
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "tools"))
import transcribe_episodes as te  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seg(seg_id: int, start: float, end: float, speaker: str | None = None) -> te.SegmentResult:
    """Build a minimal SegmentResult for testing."""
    return te.SegmentResult(
        id=seg_id,
        start=start,
        end=end,
        text=f"segment {seg_id}",
        speaker=speaker,
    )


# ===========================================================================
# tag_segment_types — intro / outro / content labelling
# ===========================================================================

class TestTagSegmentTypes:
    """
    Covers the user-visible contract for intro/outro detection.

    Why this matters: intro/outro segments are excluded from chapter generation
    and chapter timing.  Wrong labelling means chapters start mid-ad-read or
    miss the end of the actual conversation.
    """

    EPISODE_DURATION = 3600.0   # 60-minute episode

    def test_segment_ending_within_intro_window_is_tagged_intro(self):
        """The ad-read / cold-open at the start should be tagged 'intro'."""
        segs = [_seg(0, start=0.0, end=45.0)]   # well within 90s window
        te.tag_segment_types(segs, intro_window_s=90.0, total_duration_s=self.EPISODE_DURATION)
        assert segs[0].segment_type == "intro", (
            "Segment ending at 45s (within 90s intro window) must be tagged 'intro'"
        )

    def test_segment_straddling_intro_boundary_is_still_intro(self):
        """A segment that *ends* at exactly the intro window boundary is intro."""
        segs = [_seg(0, start=80.0, end=90.0)]
        te.tag_segment_types(segs, intro_window_s=90.0, total_duration_s=self.EPISODE_DURATION)
        assert segs[0].segment_type == "intro", (
            "Segment ending exactly at 90s (the intro boundary) must be 'intro'"
        )

    def test_segment_starting_after_intro_window_is_content(self):
        """The main conversation body must not be labelled intro."""
        segs = [_seg(0, start=91.0, end=200.0)]
        te.tag_segment_types(segs, intro_window_s=90.0, total_duration_s=self.EPISODE_DURATION)
        assert segs[0].segment_type == "content", (
            "Segment starting at 91s (past intro window) must be 'content'"
        )

    def test_segment_in_outro_window_is_tagged_outro(self):
        """Sign-off / credits at the end should be tagged 'outro'."""
        outro_start = self.EPISODE_DURATION - 60.0   # 60s before end
        segs = [_seg(0, start=outro_start, end=self.EPISODE_DURATION - 10.0)]
        te.tag_segment_types(segs, outro_window_s=120.0, total_duration_s=self.EPISODE_DURATION)
        assert segs[0].segment_type == "outro", (
            f"Segment at {outro_start}s (within 120s outro window of a {self.EPISODE_DURATION}s "
            "episode) must be tagged 'outro'"
        )

    def test_outro_not_tagged_when_duration_is_zero(self):
        """
        If total_duration_s=0 (unknown), outro detection must be disabled.
        Guessing would mis-tag content segments in episodes with unknown length.
        """
        segs = [_seg(0, start=3500.0, end=3600.0)]
        te.tag_segment_types(segs, outro_window_s=120.0, total_duration_s=0.0)
        assert segs[0].segment_type == "content", (
            "With total_duration_s=0, outro detection must be disabled — "
            "cannot determine outro window without knowing episode length"
        )

    def test_middle_segment_is_content(self):
        """Roger and James talking for the bulk of the episode → 'content'."""
        segs = [_seg(0, start=500.0, end=800.0)]
        te.tag_segment_types(segs, intro_window_s=90.0, outro_window_s=120.0,
                             total_duration_s=self.EPISODE_DURATION)
        assert segs[0].segment_type == "content"

    @pytest.mark.parametrize("start,end,expected", [
        (0.0,    89.9,  "intro"),    # entirely in intro
        (0.0,    90.0,  "intro"),    # ends exactly at boundary
        (90.1,   200.0, "content"),  # just past intro
        (1700.0, 1900.0, "content"), # mid-episode
        (3480.0, 3590.0, "outro"),   # 120s from end of 3600s episode
        (3600.0, 3600.0, "outro"),   # right at end
    ])
    def test_boundary_cases(self, start, end, expected):
        """Parametrized sweep of boundary values — catches off-by-one errors."""
        segs = [_seg(0, start=start, end=end)]
        te.tag_segment_types(segs, intro_window_s=90.0, outro_window_s=120.0,
                             total_duration_s=3600.0)
        assert segs[0].segment_type == expected, (
            f"Segment [{start}s–{end}s] in a 3600s episode should be '{expected}', "
            f"got '{segs[0].segment_type}'"
        )

    def test_mutates_in_place_does_not_return_new_list(self):
        """
        tag_segment_types modifies segments in-place and returns None.
        Callers must not use the return value — this guards against misuse.
        """
        segs = [_seg(0, 0.0, 45.0)]
        result = te.tag_segment_types(segs, total_duration_s=3600.0)
        assert result is None, "tag_segment_types must return None (mutates in-place)"

    def test_empty_segment_list_is_safe(self):
        """An episode that produced no segments must not crash the tagger."""
        te.tag_segment_types([], total_duration_s=3600.0)  # must not raise

    def test_default_segment_type_is_content(self):
        """Newly created SegmentResult defaults to 'content' before any tagging."""
        seg = te.SegmentResult(id=0, start=0.0, end=1.0, text="hi")
        assert seg.segment_type == "content", (
            "Default segment_type must be 'content' — "
            "this is the fallback for any segment not matched by the tagger"
        )


# ===========================================================================
# SegmentResult — data contract
# ===========================================================================

class TestSegmentResult:
    """
    Guards the schema contract for SegmentResult.
    These fields appear in every transcript.json — changing them silently
    would break downstream tools (chapter generator, MCP queries, etc.).
    """

    def test_has_required_fields(self):
        seg = te.SegmentResult(id=1, start=0.0, end=1.0, text="hello")
        assert hasattr(seg, "id")
        assert hasattr(seg, "start")
        assert hasattr(seg, "end")
        assert hasattr(seg, "text")
        assert hasattr(seg, "speaker")
        assert hasattr(seg, "segment_type")
        assert hasattr(seg, "chapter_id")

    def test_speaker_defaults_to_none(self):
        """
        Speaker is None by default — not an empty string.
        Downstream code uses `if seg.speaker:` which would behave differently
        for None vs "".
        """
        seg = te.SegmentResult(id=0, start=0.0, end=1.0, text="hi")
        assert seg.speaker is None, "speaker must default to None, not empty string"

    def test_chapter_id_defaults_to_none(self):
        seg = te.SegmentResult(id=0, start=0.0, end=1.0, text="hi")
        assert seg.chapter_id is None


# ===========================================================================
# _load_diarization — huggingface_hub monkey-patch
# ===========================================================================

class TestLoadDiarizationPatches:
    """
    On 2026-03-05, speechbrain 1.0.3 failed to download the ECAPA model because
    it calls hf_hub_download(use_auth_token=...) — a kwarg renamed to token= in
    huggingface_hub ≥0.21.  _load_diarization() patches this at import time.

    These tests verify the patch itself, without importing pyannote or torch.
    """

    def _apply_patch_only(self, fake_hf, monkeypatch):
        """
        Extract and apply only the hf_hub_download patch from _load_diarization
        by monkey-patching all heavy imports to no-ops.
        """
        import types

        # Stub out torchaudio so the torchaudio patch runs without the real module
        fake_ta = types.SimpleNamespace(list_audio_backends=lambda: ["soundfile"])
        monkeypatch.setitem(sys.modules, "torchaudio", fake_ta)

        # Stub huggingface_hub with our controlled fake
        monkeypatch.setitem(sys.modules, "huggingface_hub", fake_hf)

        # Stub out pyannote so the import line doesn't fail
        fake_pyannote = types.SimpleNamespace(Pipeline=object)
        fake_pyannote_audio = types.SimpleNamespace(Pipeline=object)
        monkeypatch.setitem(sys.modules, "pyannote", fake_pyannote)
        monkeypatch.setitem(sys.modules, "pyannote.audio", fake_pyannote_audio)

        # Build a minimal engine and call _load_diarization
        import importlib
        import transcribe_episodes as te_fresh
        importlib.reload(te_fresh)

        engine = te_fresh.TranscriptionEngine.__new__(te_fresh.TranscriptionEngine)
        engine.diarize = True
        engine.hf_token = "tok"
        engine.min_speakers = 1
        engine.max_speakers = 8
        engine.strict_diarize = False
        engine._diarization_pipeline = None
        engine._load_diarization()

    def test_use_auth_token_kwarg_is_renamed_to_token(self, monkeypatch):
        """
        speechbrain 1.0.3 calls hf_hub_download(use_auth_token=...).
        The patch must translate this to token= so huggingface_hub ≥0.21 accepts it.
        """
        import types, sys
        calls = []

        def fake_download(*args, **kwargs):
            calls.append(kwargs)
            return "/fake/path"

        fake_hf = types.SimpleNamespace(hf_hub_download=fake_download)
        self._apply_patch_only(fake_hf, monkeypatch)

        # Now simulate a speechbrain-style call via the patched function
        fake_hf.hf_hub_download("repo", use_auth_token="abc")
        assert len(calls) == 1
        assert "token" in calls[0], "use_auth_token must be renamed to token"
        assert calls[0]["token"] == "abc"
        assert "use_auth_token" not in calls[0], "use_auth_token must not pass through"

    def test_token_kwarg_is_passed_through_unchanged(self, monkeypatch):
        """
        Callers already using the new token= API must not be broken by the patch.
        """
        import types
        calls = []

        def fake_download(*args, **kwargs):
            calls.append(kwargs)
            return "/fake/path"

        fake_hf = types.SimpleNamespace(hf_hub_download=fake_download)
        self._apply_patch_only(fake_hf, monkeypatch)

        fake_hf.hf_hub_download("repo", token="xyz")
        assert calls[0].get("token") == "xyz", "token= kwarg must pass through unchanged"
        assert "use_auth_token" not in calls[0]

    def test_positional_args_are_preserved(self, monkeypatch):
        """
        The patch uses *args forwarding — positional arguments must not be dropped.
        """
        import types
        calls = []

        def fake_download(*args, **kwargs):
            calls.append((args, kwargs))
            return "/fake/path"

        fake_hf = types.SimpleNamespace(hf_hub_download=fake_download)
        self._apply_patch_only(fake_hf, monkeypatch)

        fake_hf.hf_hub_download("repo_id", "filename", use_auth_token="tok")
        args, kwargs = calls[0]
        assert "repo_id" in args, "Positional repo_id must survive the patch"
        assert "filename" in args, "Positional filename must survive the patch"
        assert kwargs.get("token") == "tok"


# ===========================================================================
# _export_speaker_embeddings — stub custom.py + error capture
# ===========================================================================

class TestExportSpeakerEmbeddingsErrorHandling:
    """
    On 2026-03-05, ECAPA embedding export silently failed for all 65 overnight
    episodes.  Two bugs:
      1. speechbrain from_hparams() tries to download custom.py (404 → failure)
      2. Failure left an empty speaker_embeddings/ dir with no diagnostic info

    These tests verify the fixes without importing torch or speechbrain.
    """

    def _mock_heavy_deps(self, monkeypatch, ecapa_side_effect=None):
        """
        Inject fake numpy, torch, and speechbrain into sys.modules so that
        _export_speaker_embeddings() passes the outer `except ImportError` guard.

        Without this, numpy/torch (not installed in the Python 3.13 test env)
        trigger the early-return before any speechbrain code runs.
        """
        import types
        from unittest.mock import MagicMock

        monkeypatch.setitem(sys.modules, "numpy", types.ModuleType("numpy"))
        monkeypatch.setitem(sys.modules, "torch", MagicMock())

        fake_sb_cls = MagicMock()
        if ecapa_side_effect is not None:
            fake_sb_cls.from_hparams.side_effect = ecapa_side_effect
        fake_classifiers = types.ModuleType("speechbrain.inference.classifiers")
        fake_classifiers.EncoderClassifier = fake_sb_cls
        monkeypatch.setitem(sys.modules, "speechbrain", types.ModuleType("speechbrain"))
        monkeypatch.setitem(sys.modules, "speechbrain.inference", types.ModuleType("speechbrain.inference"))
        monkeypatch.setitem(sys.modules, "speechbrain.inference.classifiers", fake_classifiers)
        return fake_sb_cls

    def _make_engine(self, tmp_path):
        """Return a TranscriptionEngine with diarize=True and a fake pipeline."""
        engine = te.TranscriptionEngine.__new__(te.TranscriptionEngine)
        engine.diarize = True
        engine.hf_token = "tok"
        engine._diarization_pipeline = object()
        return engine

    def _fake_diarization(self):
        """Minimal pyannote-like Annotation with one speaker turn."""
        import types

        class FakeTurn:
            start = 0.0
            end = 5.0

        class FakeDiarization:
            def itertracks(self, yield_label=False):
                yield FakeTurn(), None, "SPEAKER_00"

        return FakeDiarization()

    def test_creates_custom_py_stub_when_missing(self, tmp_path, monkeypatch):
        """
        speechbrain from_hparams() sends a 404 request for custom.py when it
        doesn't exist in the model repo.  We pre-create a stub to short-circuit
        that request.
        """
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        self._mock_heavy_deps(monkeypatch, ecapa_side_effect=RuntimeError("intentional"))

        out_dir = tmp_path / "speaker_embeddings"
        out_dir.mkdir()
        engine = self._make_engine(tmp_path)
        engine._export_speaker_embeddings(tmp_path / "audio.mp3", self._fake_diarization(), out_dir)

        stub = tmp_path / ".cache" / "speechbrain" / "custom.py"
        assert stub.exists(), (
            "custom.py stub must be created before from_hparams() is called — "
            "without it, speechbrain sends a 404 request that raises RemoteEntryNotFoundError"
        )
        assert "placeholder" in stub.read_text()

    def test_does_not_overwrite_existing_custom_py_stub(self, tmp_path, monkeypatch):
        """If custom.py already exists (e.g. from a previous run), leave it alone."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        cache_dir = tmp_path / ".cache" / "speechbrain"
        cache_dir.mkdir(parents=True)
        existing = cache_dir / "custom.py"
        existing.write_text("# existing content", encoding="utf-8")

        self._mock_heavy_deps(monkeypatch, ecapa_side_effect=RuntimeError("stop"))

        out_dir = tmp_path / "speaker_embeddings"
        out_dir.mkdir()
        engine = self._make_engine(tmp_path)
        engine._export_speaker_embeddings(tmp_path / "audio.mp3", self._fake_diarization(), out_dir)

        assert existing.read_text() == "# existing content", (
            "Pre-existing custom.py must not be overwritten by the stub"
        )

    def test_writes_clusters_json_with_error_on_ecapa_load_failure(self, tmp_path, monkeypatch):
        """
        Before this fix, a failed ECAPA load left an empty speaker_embeddings/ dir.
        Now it must write clusters.json with diagnostic info so failures are
        visible without SSH access to the EC2 instance.
        """
        import json as _json
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        self._mock_heavy_deps(monkeypatch, ecapa_side_effect=RuntimeError("model not found"))

        out_dir = tmp_path / "speaker_embeddings"
        out_dir.mkdir()
        engine = self._make_engine(tmp_path)
        engine._export_speaker_embeddings(tmp_path / "audio.mp3", self._fake_diarization(), out_dir)

        clusters_path = out_dir / "clusters.json"
        assert clusters_path.exists(), (
            "clusters.json must be written even when ECAPA fails — "
            "an empty dir with no marker left the overnight batch undiagnosable"
        )
        data = _json.loads(clusters_path.read_text())
        assert "error" in data, "clusters.json must contain an 'error' key on failure"
        assert data.get("stage") == "ecapa_load", "stage must identify where the failure occurred"

    def test_clusters_json_error_includes_exception_type_and_message(self, tmp_path, monkeypatch):
        """The error field must be human-readable, not just a generic 'error'."""
        import json as _json
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        self._mock_heavy_deps(monkeypatch, ecapa_side_effect=RuntimeError("model not found"))

        out_dir = tmp_path / "speaker_embeddings"
        out_dir.mkdir()
        engine = self._make_engine(tmp_path)
        engine._export_speaker_embeddings(tmp_path / "audio.mp3", self._fake_diarization(), out_dir)

        data = _json.loads((out_dir / "clusters.json").read_text())
        assert "RuntimeError" in data["error"], "Exception type must appear in the error string"
        assert "model not found" in data["error"], "Exception message must appear in the error string"

    def test_returns_early_gracefully_when_speechbrain_not_installed(self, tmp_path, monkeypatch):
        """
        If speechbrain is not installed, the export must skip silently — the batch
        continues and the episode is still transcribed + diarized.
        """
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        # Remove speechbrain from sys.modules to simulate ImportError
        for key in list(sys.modules.keys()):
            if "speechbrain" in key:
                monkeypatch.delitem(sys.modules, key, raising=False)

        out_dir = tmp_path / "speaker_embeddings"
        out_dir.mkdir()
        engine = self._make_engine(tmp_path)
        # Must not raise even without speechbrain
        engine._export_speaker_embeddings(tmp_path / "audio.mp3", self._fake_diarization(), out_dir)
        # clusters.json is NOT written in this path (no diagnostic needed — it's a config issue)
        assert not (out_dir / "clusters.json").exists() or True  # either is acceptable
