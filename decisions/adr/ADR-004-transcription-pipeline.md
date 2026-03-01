# ADR-004: Transcription Pipeline — faster-whisper + Chapter Detection

**Status:** Accepted
**Date:** 2026-02-28
**Deciders:** Jim Green

---

## Context

The Purefoy knowledge base holds ~200 Team Deakins podcast episodes as local MP3 files in
`downloads/<episode>/`. A small subset (~5 episodes) have Apple Podcasts-sourced plain-text
transcripts (no timestamps, no speaker labels). The remainder are untranscribed.

The goal is to produce:
- Timecoded, word-level transcripts for every episode
- Optional speaker labels (host / guest)
- Topic tags cross-referencing the forum corpus
- Smart chapters usable in podcast players

Multiple approaches were considered for each sub-problem.

---

## Decisions

### 1. Transcription engine: `faster-whisper`

**Selected over:** OpenAI Whisper (original), Whisper.cpp, cloud APIs (Deepgram, Rev, AssemblyAI)

| Option | Pros | Cons |
|--------|------|------|
| OpenAI Whisper | Reference implementation | 4× slower, 2× more memory, no word timestamps in core lib |
| Whisper.cpp | Very fast on CPU | No Python API; word timestamps via extra steps |
| Deepgram / Rev | Managed, fast | Cost per minute; data leaves the machine; requires network |
| **faster-whisper** | 4× faster than Whisper, half the RAM, native word timestamps, CPU+GPU, active maintenance | One extra dependency |

faster-whisper (CTranslate2 backend) is the current community standard for local transcription.
VAD filtering reduces hallucination. Word-level timestamps enable the chapter and search features.

### 2. Speaker diarization: `pyannote.audio` (optional)

**Rationale:** Best-in-class accuracy for podcast-style 2–3 speaker audio. Made optional because:
- Requires accepting a gated HuggingFace license (free but manual step)
- Adds ~50% processing time per episode
- Plain transcripts without speaker labels still provide the primary research value

The pipeline degrades gracefully: `--diarize` is off by default, falls back silently if the model
fails to load.

### 3. Chapter detection: algorithmic (no additional ML model)

**Selected over:** LLM-based segmentation (GPT-4, Claude), Whisper large prompt steering

Pure-Python TF-IDF + sliding-window coherence scoring plus 4 auxiliary signals (pause duration,
topic-tag Jaccard, speaker-turn density, film-mention boundary). No external API call. Deterministic,
tunable, offline. For 1-hour podcasts with hundreds of segments, this produces 6–12 chapters with
reasonable titles. Quality improves as forum corpus grows.

### 4. Topic tagging: keyword TF-IDF + forum corpus cross-reference

Two-tier approach:
1. Built-in cinematography vocabulary (static, always available)
2. Forum vocabulary built from `library/forums/posts/*.json` (enhances confidence scores and
   surfaces related forum threads when corpus is loaded)

No LLM required. Each tagged segment gains `topics` and `films` arrays with confidence scores
and related forum topic slugs.

### 5. Script location: `scripts/tools/`

**Rationale:** Matches the existing convention established by `extract_teamdeakins_transcripts_v2.py`,
`migrate_transcripts_to_episodes.py`, etc. These scripts are standalone tools, not part of the
`deakins_forums` Python package. They are not included in ruff/mypy CI scope.

Consequence: four files land in `scripts/tools/`:
- `transcribe_episodes.py` — main pipeline
- `chapter_generator.py` — chapter detection (also importable as a library)
- `topic_tagger.py` — topic tagging
- `preflight_check.py` — environment validation

### 6. Separate requirements file: `requirements-transcription.txt`

`faster-whisper` and optional `pyannote.audio` are heavy dependencies (~1GB models) inappropriate
for the main `requirements.txt` used by the forum scraper. A separate opt-in file allows users
to install only what they need for transcription work.

---

## Output Schema

The pipeline writes to the existing per-episode structure (`downloads/<episode>/transcript/`):

```
transcript/
├── transcript.json              ← primary: timecoded segments, topics, chapters, stats
├── transcript.txt               ← human-readable with timecodes and chapter markers
├── transcript_segments.jsonl    ← streaming: one JSON object per segment
├── extraction_report.json       ← pipeline provenance and diagnostics
├── chapters.json                ← Purefoy internal chapter format
├── chapters_podcastns.json      ← Podcasting 2.0 JSON Chapters spec
├── chapters.txt                 ← human-readable chapter list
└── chapters.ffmeta              ← FFmpeg metadata (embeddable into MP3)
```

Existing Apple Podcasts-sourced `transcript.txt` files are detected and respected (not overwritten
unless `--force`).

---

## Consequences

- Transcribing all ~200 episodes at `large-v3` on CPU will take 80–100 hours; `medium` is recommended
  for an initial full pass, with `large-v3` for episodes of primary research interest.
- The `chapter_generator.py` module is importable by future MCP tools for on-demand chapter
  regeneration without re-transcribing.
- Forum corpus vocabulary is built lazily at runtime; the pipeline works in "static mode" on
  machines without `library/forums/posts/`.
- No changes to the `deakins_forums` package or its CI pipeline.

## Migration path

- Phase 2: Index `transcript.json` segments into the SQLite FTS5 index for cross-source search
  ("What did Roger say about X in both podcasts and forums?").
- Phase 2: Expose transcripts via the MCP stdio server (ADR-003).
