# Podcast Transcription Pipeline

**Created:** 2026-02-28
**Updated:** 2026-03-04 (v2.0.0 — multi-run layout, inline diarization, intro/outro tagging)
**Status:** Active
**ADR:** [ADR-004](../../decisions/adr/ADR-004-transcription-pipeline.md), [ADR-005](../../decisions/adr/ADR-005-transcription-optimization.md)
**Progress:** [transcription-batch-status.md](./transcription-batch-status.md)

---

## Overview

A robust, resumable pipeline for extracting timecoded, speaker-labeled, topic-tagged transcripts
from locally downloaded Team Deakins podcast episodes. Integrates with the existing Purefoy
knowledge base and cross-references against the forum corpus.

Scripts live in `scripts/tools/`.

---

## Architecture

```
Discovery → Transcription → Diarization → Seg Tagging → Chapter Detection → Output → Reporting
    ↓            ↓               ↓             ↓               ↓               ↓          ↓
 Find eps    faster-whisper  pyannote.audio  intro/outro    Sliding-window  runs/{id}  Gap report
 needing     large-v3 GPU    speaker labels  time windows   TF-IDF coherence JSON/TXT   manifest
 work        float16 CUDA    CUDA (4 min/ep) + chapter_id   + 4 aux signals  per-run    batch log
```

v2.0.0 runs diarization **inline** (not post-processing) so audio is read once. Each run lands in
`transcript/runs/{run_id}/` — multiple runs per episode are supported and tracked via `run_manifest.json`.

### Design Principles

1. **Fail-safe iteration** — Every episode is wrapped in try/except. A failure never blocks the next episode.
2. **Resumable** — Detects existing `transcript.json` files (with `pipeline_version` key) and skips them. Force-retranscribe with `--force`.
3. **Gap reporting** — After each run, a machine-readable report lists what succeeded, failed, and is missing.
4. **Structured output** — Timecoded segments, word-level timestamps, speaker labels, and topic tags all in one structured JSON per episode.
5. **Convention-matching** — Output lands in the existing `downloads/<episode>/transcript/` structure.

---

## Installation

```bash
# Core transcription (CPU)
pip install -r requirements-transcription.txt

# GPU acceleration (NVIDIA only)
pip install faster-whisper[cuda]

# Optional: speaker diarization
pip install pyannote.audio
huggingface-cli login  # then accept pyannote model license
```

System dependency: **ffmpeg** must be installed.
```bash
brew install ffmpeg        # macOS
sudo apt install ffmpeg    # Ubuntu/Debian
```

---

## Quick Start

```bash
# 1. Validate environment
python scripts/tools/preflight_check.py

# 2. Dry run — see what would be processed
python scripts/tools/transcribe_episodes.py --dry-run

# 3. Transcribe one episode with medium model (fast test)
python scripts/tools/transcribe_episodes.py --model medium --batch-size 1

# 4. Full run with best model
python scripts/tools/transcribe_episodes.py --model large-v3
```

---

## Usage

```bash
# All untranscribed episodes
python scripts/tools/transcribe_episodes.py

# Specific model
python scripts/tools/transcribe_episodes.py --model large-v3

# Single episode
python scripts/tools/transcribe_episodes.py --episode S02E169__2025-11-26__edgar-wright-director__libsyn_f6853474de

# With speaker diarization
python scripts/tools/transcribe_episodes.py --diarize --hf-token YOUR_TOKEN

# Force re-transcribe (overwrites existing)
python scripts/tools/transcribe_episodes.py --force

# Skip topic tagging (faster)
python scripts/tools/transcribe_episodes.py --no-topics

# Custom chapter lengths
python scripts/tools/transcribe_episodes.py --chapter-min 180 --chapter-target 600

# Generate chapters from existing transcript
python scripts/tools/chapter_generator.py downloads/S02E169_.../transcript/transcript.json
```

---

## Output Schema

### Per-Episode Output (v2.0.0 — multi-run layout)

```
downloads/<episode>/
├── audio.mp3
├── metadata.json
└── transcript/
    ├── run_manifest.json              ← canonical pointer + run history
    └── runs/
        └── run_20260304__larg__dz/   ← one directory per pipeline run
            ├── transcript.json        ← primary: timecoded segments, topics, chapters
            ├── transcript.txt         ← human-readable with timecodes + chapter markers
            ├── transcript_segments.jsonl  ← streaming: one segment per line
            ├── extraction_report.json ← pipeline provenance and diagnostics
            ├── chapters.json          ← Purefoy internal chapter format
            ├── chapters_podcastns.json ← Podcasting 2.0 JSON Chapters spec
            ├── chapters.txt           ← human-readable chapter list
            ├── chapters.ffmeta        ← FFmpeg metadata (embeddable into MP3)
            └── speaker_embeddings/    ← present if --embed-speakers
                ├── SPEAKER_00.npy     ← ECAPA-TDNN embedding for this cluster
                ├── SPEAKER_01.npy
                └── clusters.json      ← {SPEAKER_XX: {duration_s, segment_count}}
```

**run_id format:** `run_{YYYYMMDDHHMMSS}__{model4}__{dz|nd}`
e.g. `run_20260304203440__larg__dz` = large-v3, diarized, 2026-03-04 20:34 UTC.

### `transcript.json` Structure (v2.0.0)

```json
{
  "meta": {
    "episode_title": "EDGAR WRIGHT - Director",
    "audio_duration_seconds": 4213.5,
    "transcribed_at": "2026-03-04T12:00:00Z",
    "pipeline_version": "2.0.0",
    "whisper_model": "large-v3",
    "language": "en",
    "language_probability": 0.98
  },
  "statistics": {
    "total_segments": 342,
    "total_words": 14500,
    "speakers_detected": 3,
    "topics_tagged": 18,
    "chapters_generated": 8
  },
  "chapters": [...],
  "segments": [
    {
      "id": 0,
      "start": 0.0,
      "end": 4.52,
      "text": "Welcome to Team Deakins.",
      "speaker": "SPEAKER_00",
      "segment_type": "intro",
      "chapter_id": null,
      "confidence": 0.95,
      "words": [{"word": "Welcome", "start": 0.0, "end": 0.42, "probability": 0.98}],
      "topics": [{"topic": "storytelling", "confidence": 0.6, "keywords_matched": [...]}],
      "films": []
    }
  ],
  "topics_summary": [...],
  "films_summary": [...]
}
```

**New fields in v2.0.0:**
- `segment_type` — `"intro"` (first 90s), `"outro"` (last 120s), or `"content"` (everything else)
- `chapter_id` — index of the chapter this segment belongs to; `null` for intro/outro segments
- `pipeline_version: "2.0.0"`

---

## Performance Estimates

| Model | VRAM | Speed (1hr audio, GPU) | Speed (1hr audio, CPU) | Quality |
|-------|------|-------------------------|-------------------------|---------|
| tiny | <1GB | ~2 min | ~6 min | Low |
| small | ~2GB | ~8 min | ~24 min | Good |
| medium | ~5GB | ~15 min | ~45 min | Very good |
| large-v3 | ~10GB | ~25 min | ~90 min | Best |

For ~200 episodes averaging 1 hour each:
- `medium` on GPU: ~50 hours
- `medium` on CPU: ~150 hours

**Recommendation:** Start with `medium` for a complete pass, then `large-v3` for key episodes.

---

## Error Handling

Every episode is isolated. The pipeline handles:

| Error | Behaviour |
|-------|-----------|
| Missing audio | Logged, skipped, reported in gaps |
| Corrupted audio | Caught by ffmpeg/whisper, logged, continues |
| Out of memory | Caught, suggests smaller model, continues |
| Keyboard interrupt | Graceful shutdown, saves progress report |
| Whisper hallucination | Filtered via repetition/low-uniqueness heuristics |
| Diarization failure | Falls back to no-speaker transcript, logged |

---

## Integration with Purefoy KB

### Forum Cross-Reference

The topic tagger loads forum vocabulary and surfaces connections:
- Segments mentioning "Skyfall" link to forum topics about Skyfall
- Technical terms like "anamorphic" link to relevant discussions
- Equipment mentions link to gear-related forum posts

### Existing Apple Podcasts Transcripts

Five episodes have Apple Podcasts-sourced plain-text transcripts in
`downloads/<episode>/transcript/transcript.txt`. These are detected by the pipeline
and not overwritten (no `pipeline_version` key in the file). They will be superseded
once re-transcribed with `--force`.

### Future: MCP Integration (ADR-003)

Transcripts stored in this format are ready for:
- FTS5 indexing alongside forum posts (cross-source search)
- MCP server exposure (`transcript.json` segments are already agent-friendly)
- Cross-source queries: "What did Roger say about X in both the podcast and forums?"
