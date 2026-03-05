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

def _seg(id: int, start: float, end: float, speaker: str | None = None) -> te.SegmentResult:
    """Build a minimal SegmentResult for testing."""
    return te.SegmentResult(
        id=id,
        start=start,
        end=end,
        text=f"segment {id}",
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
