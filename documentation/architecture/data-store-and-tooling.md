# Team Deakins Knowledge Base — Data Store & Tooling

**Purpose:** This document describes the underlying data architecture, file layouts, schemas, and
operational tooling for the Team Deakins podcast knowledge base. It is intended as authoritative
input for downstream agents scaffolding query, retrieval, or analysis tools.

---

## 1. Overview

The knowledge base has two independent data domains:

| Domain | Source | Location | Status |
|---|---|---|---|
| **Podcast transcripts** | 347 MP3 episodes from Team Deakins RSS | `downloads/` | 290/347 transcribed (57 in progress) |
| **Forum posts** | rogerdeakins.com bbPress forums | `library/forums/` | Partial (278 posts, 45 topics) |

Both domains are flat-file JSON stores — no database required for reading. SQLite FTS5 index
exists for forum posts (`library/forums/_site/index.db`, always regenerable).

---

## 2. Podcast Transcript Data Store

### 2a. Root layout

```
downloads/
  {episode_dir}/
    audio.mp3
    metadata.json
    transcript/
      run_manifest.json
      sources.json
      runs/
        {run_id}/
          transcript.json
          transcript.txt
          transcript_segments.jsonl
          chapters.json
          chapters.txt
          chapters.ffmeta
          chapters_podcastns.json
          extraction_report.json
          speaker_embeddings/
            SPEAKER_00.npy
            SPEAKER_01.npy
            ...
            clusters.json
```

### 2b. Episode directory naming

Pattern: `S{season}E{episode}__{YYYY-MM-DD}__{guest-slug}__{source_id}/`

Examples:
- `S00E091__2021-02-21__turning-the-tables-fargo__libsyn_130aa3397c/`
- `S02E182__2026-02-25__martin-campbell-director__libsyn_6215701667/`
- `S86E000__2021-02-03__caleb-deschanel-cinematographer__libsyn_e76c45da08/`

Season `00` = early unnumbered episodes. Season `86` = bonus/special.

**Total episode directories:** 347
**With completed transcripts:** 290 (57 in progress as of 2026-03-16)

### 2c. run_id naming

Format: `run_{YYYYMMDDHHMMSS}__{model4}__{flags}`

- `model4`: first 4 chars of model slug, e.g. `larg` for `large-v3`
- `flags`: `dz` = diarized, `nd` = no diarization

Example: `run_20260309014119__larg__dz`

`transcript/run_manifest.json` tracks which run is canonical and the full run history:

```json
{
  "canonical": "run_20260309014119__larg__dz",
  "runs": [
    {
      "run_id": "run_20260309014119__larg__dz",
      "created_at": "2026-03-09T12:12:43Z",
      "whisper_model": "large-v3",
      "diarization": true,
      "speaker_embeddings": true,
      "pipeline_version": "2.0.0"
    }
  ]
}
```

---

### 2d. `metadata.json`

Sourced from RSS XML. Key fields:

```json
{
  "guid": "46639367-dbe3-4353-8f70-88cb1673dbcb",
  "title": "Turning the Tables - FARGO",
  "pub_date_iso": "2021-02-21",
  "enclosure_url": "https://traffic.libsyn.com/...",
  "enclosure_filename": "91-TTT-Fargo-ARRI-OTTO.mp3",
  "enclosure_length": 128115235,
  "enclosure_type": "audio/mpeg",
  "description_html": "...",
  "itunes": {
    "season": null,
    "episode": 91,
    "duration": "01:28:37",
    "summary": "...",
    "image": "https://..."
  },
  "provenance": {
    "rss_url": "...",
    "scraped_at": "...",
    "script_version": "ingest-v2"
  }
}
```

---

### 2e. `transcript.json` (canonical transcript — primary read target)

~2–3 MB per episode. Top-level structure:

```json
{
  "meta": {
    "episode_title": "Turning the Tables - FARGO",
    "episode_guid": "...",
    "season": null,
    "episode": 91,
    "pub_date": "2021-02-21",
    "audio_file": "audio.mp3",
    "audio_duration_seconds": 5334.41,
    "transcribed_at": "2026-03-09T12:12:43Z",
    "pipeline_version": "2.0.0",
    "whisper_model": "large-v3",
    "device": "cuda",
    "compute_type": "float16",
    "language": "en",
    "language_probability": 0.9995,
    "diarization_enabled": true
  },
  "statistics": {
    "total_segments": 952,
    "total_words": 15374,
    "total_duration_seconds": 5299.61,
    "speakers_detected": 3,
    "topics_tagged": 348,
    "films_mentioned": 11,
    "chapters_generated": 33
  },
  "chapters": [ /* see §2g */ ],
  "segments": [ /* see §2f */ ]
}
```

---

### 2f. Segment schema (within `transcript.json` → `segments[]` and `transcript_segments.jsonl`)

Each segment is one continuous speech utterance (~2–10 words). Both `transcript.json`
(full, with word-level timestamps) and `transcript_segments.jsonl` (compact, one JSON
object per line) exist. Use `.jsonl` for streaming/indexing; use `.json` for full
word-level access.

**Full segment (in transcript.json):**
```json
{
  "id": 0,
  "start": 4.7,
  "end": 7.46,
  "text": "Hi, and welcome to the Team Deakins podcast.",
  "speaker": "SPEAKER_00",
  "segment_type": "intro",
  "chapter_id": 0,
  "confidence": 0.0,
  "words": [
    { "word": " Hi,", "start": 4.7, "end": 5.06, "probability": 0.8086 },
    ...
  ],
  "topics": ["production", "camera"],
  "films": ["Fargo"]
}
```

**Compact segment (in transcript_segments.jsonl):**
```json
{ "id": 0, "start": 4.7, "end": 7.46, "text": "...", "speaker": "SPEAKER_00",
  "segment_type": "intro", "chapter_id": 0, "confidence": 0.0, "topics": [] }
```

**`segment_type` values:** `"intro"` | `"outro"` | `"content"`

- `intro`: first 90 seconds of episode
- `outro`: last 120 seconds
- `content`: everything else

**`speaker`:** Anonymous cluster label `SPEAKER_00`, `SPEAKER_01`, etc. Not yet mapped to
named individuals (James/Roger/guest). Cross-episode speaker identification (B3 phase)
is not yet implemented.

---

### 2g. Chapter schema (within `transcript.json` → `chapters[]` and `chapters.json`)

One chapter = topically coherent block of conversation, auto-generated from content
segments. Intro/outro segments are excluded from chapter generation.

```json
{
  "index": 0,
  "title": "Introduction: Turning the Tables",
  "start_time": 4.7,
  "end_time": 165.09,
  "duration": 160.39,
  "summary": "This episode is sponsored by Otto Nemitz Camera Rental...",
  "segment_range": [0, 39],
  "word_count": 387,
  "topics": ["camera", "film_format", "lenses", "lighting", "storytelling"],
  "films": ["Barton Fink", "Fargo", "No Country for Old Men", "True Grit"],
  "speakers": ["SPEAKER_00", "SPEAKER_01", "SPEAKER_02"],
  "key_phrases": ["film", "episode", "cinematic", "fargo"],
  "break_score": 0.0,
  "break_signals": {}
}
```

Additional chapter formats in each run directory:

| File | Format | Use |
|---|---|---|
| `chapters.json` | JSON with full chapter objects | Primary structured access |
| `chapters.txt` | Human-readable plain text | Quick review |
| `chapters.ffmeta` | FFmpeg metadata format | Audio player chapter injection |
| `chapters_podcastns.json` | Podcasting 2.0 namespace format | RSS chapter extension |

---

### 2h. `extraction_report.json`

Lightweight completion receipt per run. Use to check health of a transcription.

```json
{
  "episode_dir": "S00E091__...",
  "episode_title": "Turning the Tables - FARGO",
  "success": true,
  "error": null,
  "transcribed_at": "2026-03-09T12:12:43Z",
  "pipeline_version": "2.0.0",
  "processing_time_seconds": 856.72,
  "audio_duration_seconds": 5334.41,
  "segment_count": 952,
  "word_count": 15374,
  "language": "en",
  "speakers_detected": 3,
  "topics_tagged": 348,
  "films_mentioned": 11,
  "chapters_generated": 33
}
```

---

### 2i. Speaker embeddings

Located at `speaker_embeddings/` within each run directory.

| File | Description |
|---|---|
| `SPEAKER_XX.npy` | ECAPA-TDNN embedding vector (numpy, 192-dim float32) for cluster XX |
| `clusters.json` | Per-cluster metadata: total speaking duration, segment count, embedding path |

`clusters.json` example:
```json
{
  "SPEAKER_00": { "duration_s": 434.5, "segment_count": 282, "embedding_path": "SPEAKER_00.npy" },
  "SPEAKER_01": { "duration_s": 3021.9, "segment_count": 479, "embedding_path": "SPEAKER_01.npy" },
  "SPEAKER_02": { "duration_s": 1752.7, "segment_count": 416, "embedding_path": "SPEAKER_02.npy" }
}
```

**Typical cluster count:** 3–4 per episode. Known issue: over-diarization (cosine-similarity
merge pass not yet implemented). Speaker cluster labels are not named — cross-episode
clustering to identify Roger/James/guest is future work (B3 phase).

**~65 episodes** from the first overnight batch (run_20260305192707) have empty
`speaker_embeddings/` directories due to an ECAPA bug fixed mid-batch. Their transcripts
and diarization labels are correct — only the `.npy` files are missing.

---

### 2j. Aggregate corpus statistics

| Metric | Value |
|---|---|
| Episodes with transcripts | 290 (57 in progress) |
| Total audio transcribed | ~696 hours |
| Total segments | ~689,000 |
| Total words | ~7,280,000 |
| Total chapters | ~15,600 |
| Avg episode duration | ~72 min |
| Avg segments per episode | ~1,183 |
| Avg chapters per episode | ~26 |
| Whisper model | large-v3 (float16, CUDA) |
| Diarization engine | pyannote 4.0 (GPU) |
| Speaker embedding model | ECAPA-TDNN via SpeechBrain |

**Topic taxonomy** (from chapter-level tagging): `film_format`, `production`, `storytelling`,
`color`, `camera`, `lighting`, `post_production`, `composition`, `lenses`, and others.

**Films mentioned** are extracted per chapter and per segment. Prominent examples across
corpus: Blade Runner 2049, Fargo, No Country for Old Men, Skyfall, Sicario, True Grit.

---

## 3. Forum Data Store

### 3a. Layout

```
library/forums/
  posts/        278 files  — individual post JSON (PostLeaf v2 schema)
  topics/        45 files  — topic metadata + post index (TopicLeaf v2)
  forums/         0 files  — forum-level metadata (not yet scraped)
  _site/                   — derived/regenerable state
    index.db               — SQLite FTS5 full-text search index
    http_cache/            — ETag-based HTTP response cache
    coverage.json          — scrape coverage tracking
```

Forum scrape is partial (~278 posts, ~45 topics). Full scrape is pending.

### 3b. PostLeaf schema (v2)

```json
{
  "ids": {
    "post_id": "177199",
    "forum_slug": "forum",
    "topic_slug": "cinematography-male-vs-female-characters",
    "parent_post_id": "176486",
    "parent_type": "topic",
    "position": 5
  },
  "post_type": "reply",
  "author": { "display_name": "Roger Deakins", "role": "Keymaster" },
  "timestamps": { "parsed_iso": "2023-01-18T15:32:00", "parse_confidence": "medium" },
  "content_text": "...",
  "content_html": "...",
  "blocks": [...],
  "quotes": [...],
  "links": [...],
  "media": [...],
  "provenance": { "source_url": "...", "scraped_at": "..." },
  "integrity": { "content_hash": "sha256:...", "parser_version": "bbpress-v2" }
}
```

`post_type`: `"topic"` (thread starter) | `"reply"`

### 3c. TopicLeaf schema (v2)

```json
{
  "topic_url": "...",
  "topic_slug": "cinematography-male-vs-female-characters",
  "title": "...",
  "post_ids": ["176486", "177199", ...],
  "reply_tree": { "post_id": "176486", "children": [...] },
  "reply_count": 12,
  "max_depth": 1,
  "provenance": { "source_url": "...", "scraped_at": "..." },
  "integrity": { "content_hash": "sha256:...", "parser_version": "bbpress-v2" }
}
```

---

## 4. Tooling

### 4a. Episode download & ingest

| Script | Purpose |
|---|---|
| `download_episodes.py` | Downloads MP3s from RSS feed into `downloads/` as flat files |
| `ingest_teamdeakins_downloads.py` | Organises flat MP3s into structured episode dirs with `metadata.json` and transcript scaffolding |

New episodes publish every Wednesday. Run both in sequence to pick them up:
```bash
.venv/bin/python download_episodes.py
.venv/bin/python ingest_teamdeakins_downloads.py \
  --rss "https://rss.libsyn.com/shows/265448/destinations/2018942.xml" \
  --downloads ./downloads
```

### 4b. Transcription pipeline

| Script | Purpose |
|---|---|
| `scripts/tools/transcribe_episodes.py` | Core transcription engine: faster-whisper → diarization → speaker embedding → chapter generation → topic tagging |
| `scripts/tools/aws_runner.py` | AWS EC2 batch coordinator: provisions spot instances, distributes episodes, rsyncs results back |
| `scripts/tools/chapter_generator.py` | Standalone chapter generation from segments |
| `scripts/tools/topic_tagger.py` | Standalone topic/film tagging |
| `scripts/tools/preflight_check.py` | Validates local environment (GPU, pyannote, speechbrain) |
| `scripts/tools/transcription_report.py` | Generates corpus-wide stats report |

**To run a transcription batch (AWS):**
```bash
python scripts/tools/aws_runner.py \
  --provision 2 --key ~/.ssh/td-transcription.pem \
  --mode full --model large-v3 \
  --diarize --embed-speakers --hf-token "$HF_TOKEN" \
  --downloads ./downloads --library ./library \
  --scripts-dir ./scripts/tools
```

`--force` is `False` by default — only untranscribed episodes are queued.
Pass `--force` to re-transcribe everything.

**AWS infrastructure:**
- Region: `us-east-1`
- Instance: `g4dn.xlarge` spot (T4 GPU, 16 GB VRAM)
- AMI: `ami-0016081b488c7376d` (AWS Deep Learning AMI, Ubuntu)
- Credentials: AWS SSO (expires ~8 hrs — runner waits and warns on expiry)
- SSH key: `~/.ssh/td-transcription.pem`
- HF_TOKEN: stored in `.env` — load with `HF_TOKEN=$(grep HF_TOKEN .env | cut -d= -f2)`

### 4c. Transcript inspection

Quick inspection commands:

```bash
# List all completed episodes
find downloads -name "run_manifest.json" | wc -l

# List incomplete episodes
for ep in downloads/*/; do
  [ ! -f "$ep/transcript/run_manifest.json" ] && basename "$ep"
done

# Read transcript for an episode
jq '.statistics, .chapters[0:3]' \
  downloads/S00E091__*/transcript/runs/run_*/transcript.json

# Read all segments for an episode (streaming)
cat downloads/S00E091__*/transcript/runs/run_*/transcript_segments.jsonl \
  | jq 'select(.speaker == "SPEAKER_01")'

# Check extraction report
jq '.' downloads/S00E091__*/transcript/runs/run_*/extraction_report.json

# Tail batch log
tail -f /tmp/td-batch-*.log
```

### 4d. Recovery

If a batch run is interrupted mid-episode:
- Remote data is preserved at `/tmp/td_transcribe/episodes/{episode}/` on the EC2 instance
- Re-run the runner with `--hosts <same-ip> --skip-setup --mode full` to reconnect
- `discover_episodes` will skip completed episodes automatically
- Episodes with partial remote data: step 0 checks for done marker before re-launching

If spot-interrupted (instance gone):
- Re-provision with `--provision 2 --mode full` (no extra flags needed)
- Already-completed episodes are skipped automatically

### 4e. Forum scraper

```bash
# Scrape more topics
python -m deakins_forums.cli scrape-forum team-deakins --max-pages 20 --build-index

# Full-text search
python -m deakins_forums.cli search "natural lighting" --limit 20

# Rebuild SQLite index
python -m deakins_forums.cli build-index

# Export Roger-only posts
python -m deakins_forums.cli export roger-only -o analysis/roger_posts.txt
```

---

## 5. Known Data Quality Issues

| Issue | Scope | Status |
|---|---|---|
| Empty `speaker_embeddings/` | ~65 episodes (run_20260305192707) | Needs `--reembed-only` pass |
| Over-diarization (4 clusters when 2–3 expected) | All diarized episodes | Post-processing merge pass needed (cosine sim > 0.85) |
| Speaker clusters not named (SPEAKER_00/01/02) | All diarized episodes | B3 cross-episode clustering not yet implemented |
| Forum scrape partial (~278 posts) | library/forums/ | Full scrape not yet run |
| 57 episodes not yet transcribed | downloads/ | Batch in progress |

---

## 6. Future Data (not yet implemented)

| Component | Location | Description |
|---|---|---|
| Global speaker registry | `library/speaker_profiles/global_registry.json` | Maps cluster IDs to named individuals (Roger, James, guest) across all episodes |
| Speaker centroids | `library/speaker_profiles/centroids/` | Per-person mean ECAPA-TDNN embedding `.npy` files |

These will be written by a future `identify_speakers.py` B3 pass once all 347 episodes
are transcribed.
