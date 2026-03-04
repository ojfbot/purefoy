# ADR-005: Transcription Quality Improvements — Speaker ID, Semantic Chunking, Resource Planning

**Status:** Proposed — pending batch completion and human eval
**Date:** 2026-03-03
**Deciders:** Jim Green
**Supersedes:** ADR-004 §§2–3 (diarization and chapter detection)
**Research doc:** [`documentation/research/transcription-optimization.md`](../../documentation/research/transcription-optimization.md)
**Audit:** [`documentation/research/transcription-audit-2026-03-03.md`](../../documentation/research/transcription-audit-2026-03-03.md)

---

## Context

ADR-004 shipped a working transcription pipeline. The first 5 episodes are now
transcribed. Review of the output reveals two gaps that materially reduce the
value of the transcripts for downstream research and MCP queries:

1. **No speaker attribution.** All speech is in a single undifferentiated text
   stream. Knowing whether a paragraph is Roger, James, or the guest is the
   primary research axis ("what did Roger say about natural light?").

2. **Chapter quality is adequate but not excellent.** TF-IDF coherence misses
   synonym-based topic shifts. The James intro and closing credits are
   transcribed as regular content.

This ADR decides *which* improvements to make, *in what order*, and *at what
compute/cost configuration* to run them.

---

## Options

### Option A — Status quo (no changes)

Continue batch with current pipeline. Apply speaker ID and better chunking
retroactively as a post-processing pass after the batch completes.

**Cost:** $0 additional now. Post-processing cost depends on approach chosen.
**Risk:** 339 episodes of low-attribution transcripts in the library; downstream
MCP tools built on these will need schema migration when speaker labels land.

---

### Option B — Phased improvements, post-processing pass

Implement improvements as standalone scripts that read existing
`transcript_segments.jsonl` and rewrite `chapters.*` + add speaker labels.
No re-transcription needed.

**Phase B1 — Intro/outro detection + VAD tuning** (0 new dependencies)
- Mark James intro segments and closing credits as `segment_type: intro/outro`
- Exclude from chapter and topic output
- Tune VAD (`min_silence_duration_ms: 800`, `threshold: 0.3`)
- Run as post-processing on all 5 existing transcripts in ~10 minutes total

**Phase B2 — Semantic chunking** (adds `sentence-transformers`)
- Replace TF-IDF coherence with `all-MiniLM-L6-v2` embeddings
- Rewrite `chapters.*` for all completed episodes without re-transcribing

**Phase B3 — Speaker diarization + name resolution** (adds `pyannote.audio` + `resemblyzer`)
- Run diarization on existing audio files (local or EC2)
- Resolve James via intro anchor; Roger via embedding reference; guest via metadata
- Adds speaker field to each segment in `transcript.json`

**This is the recommended option.** Phases can ship independently and in order.

---

### Option C — Re-transcribe with full pipeline

Wait until all 3 phases are implemented, then re-run the full batch from scratch
with the improved pipeline. Simpler from a data-consistency standpoint but wastes
the compute already spent.

**Not recommended** until speaker ID is validated on the 5 existing episodes.

---

## Decision

**Adopt Option B** — implement as post-processing phases, ordered B1 → B2 → B3.

Each phase produces a standalone script in `scripts/tools/` that reads existing
outputs and writes improved versions. Schema additions are additive (new fields
only) so downstream consumers don't break.

---

## Cost and Resource Estimates

### Estimation prompt

Use this prompt to estimate cost for any configuration change:

```
Given:
  - N episodes remaining
  - Average audio duration: D minutes
  - Instance type: <type>
  - Processing speed: S× real-time (per instance)
  - Spot price: $P/hr
  - Instances: I

Compute:
  total_audio_hours = N × D / 60
  wall_time_hours   = total_audio_hours / (S × I)
  cost_usd          = wall_time_hours × P × I
```

### Current configurations

| Config | Instance | vCPUs | Speed | Episodes/day/instance | Spot $/hr | Wall time (339 ep) | Total cost |
|---|---|---|---|---|---|---|---|
| **CPU baseline** (current) | c5.4xlarge | 16 | ~1× RT | 17 | $0.07 | 20 days (1 inst) | $33 |
| **CPU ×8** (128 vCPU quota) | c5.4xlarge ×8 | 128 | ~1× RT | 17 | $0.07 | ~2.5 days | $34 |
| **GPU baseline** | g4dn.xlarge | 4 | ~8× RT | 130 | $0.16 | ~2.6 days (1 inst) | $10 |
| **GPU ×2** (8 G/VT vCPUs) | g4dn.xlarge ×2 | 8 | ~8× RT | 130 | $0.16 | ~1.3 days | $10 |
| **GPU ×4** (pending quota) | g4dn.xlarge ×4 | 16 | ~8× RT | 130 | $0.16 | ~0.65 days | $10 |

### Phase B post-processing estimates (local Mac, no EC2)

| Phase | Per episode | 339 episodes | Notes |
|---|---|---|---|
| B1 Intro/outro + VAD | <1 min | ~4 hours | Pure Python, no ML |
| B2 Semantic chunking | ~2 min | ~11 hours | MiniLM on CPU |
| B3 Diarization (CPU) | ~30 min | ~7 days | pyannote on CPU |
| B3 Diarization (GPU) | ~4 min | ~23 hours | pyannote on g4dn.xlarge |

**B3 GPU cost:** 23 hours × 1 × g4dn.xlarge = $3.68 spot.

### Add-on: speaker diarization to running batch

If diarization (`--diarize`) is added to the main transcription pass (not
post-processing), the overhead is approximately:

| Hardware | Transcription speed | + Diarization | Combined |
|---|---|---|---|
| c5.4xlarge (CPU) | ~1× RT | +0.4× RT | ~1.4× RT per episode |
| g4dn.xlarge (GPU) | ~8× RT | +0.4× RT (CPU side) | ~7× RT effective |

Diarization runs on CPU regardless of transcription device (pyannote default).
GPU transcription + CPU diarization pipeline is the most cost-effective option.

### Current quota headroom

| Quota | Current limit | In use | Available |
|---|---|---|---|
| Standard spot vCPUs | 128 | 0 | 128 (8 × c5.4xlarge) |
| G/VT spot vCPUs | 0 (pending) | 0 | 0 |
| On-demand (all) | 32 | 0 | 32 |

---

## Implementation Plan

### Phase B1 — Intro/outro + VAD (no new deps)

**New file:** `scripts/tools/post_process_segments.py`

- Input: `transcript_segments.jsonl`
- Detects intro (James greeting pattern in first 90 s)
- Detects outro (closing formula in last 120 s)
- Rewrites `transcript.json` with `segment_type` field
- Regenerates `chapters.*` excluding intro/outro
- VAD parameters updated in `transcribe_episodes.py` for future runs

**Acceptance criteria:**
- [ ] Intro correctly tagged in all 5 existing episodes
- [ ] Chapter count decreases or stays same (intro was inflating chapters)
- [ ] Intro text no longer appears in chapter titles

### Phase B2 — Semantic chunking

**Dependency:** `sentence-transformers>=3.0` (no torch if using ONNX runtime)

**Change:** `chapter_generator.py` — replace `_compute_coherence_score` with
embedding cosine similarity. Keep TF-IDF as fallback.

**Acceptance criteria:**
- [ ] A/B test: human rates B2 chapters as better than B1 chapters on 3 episodes
- [ ] Chapter count stays in 15–25 range (not over-splitting)

### Phase B3 — Speaker diarization + name resolution

**Dependencies:** `pyannote.audio>=3.3`, `speechbrain>=1.0.0` (ECAPA-TDNN embeddings), HuggingFace token

> **Zero-label constraint:** No manual audio clipping or hand-labeled training data.
> Speaker identity is derived entirely from automated cross-episode embedding clustering
> and structural heuristics. See audit finding §2.3 for context.

**New file:** `scripts/tools/identify_speakers.py`

**Algorithm (fully automated, no manual labels):**

1. Run `pyannote/speaker-diarization-3.1` on each episode → per-episode `SPEAKER_XX` clusters.
2. For each per-episode cluster, extract an average d-vector embedding (ECAPA-TDNN via speechbrain).
3. Collect all per-episode per-cluster embeddings across all processed episodes.
4. Run agglomerative clustering (target k=3) across the full embedding set.
5. Two clusters that appear in nearly every episode → Roger Deakins + James Deakins (hosts).
6. One cluster that appears in exactly one episode per guest → guest.
7. Distinguish Roger from James: the speaker dominant in the **first 90 s** of each episode is James (consistent intro anchor — verified in audit).
8. Name the guest from `metadata.json → itunes.summary`.

**Storage schema (`library/speaker_profiles/`):**

```
library/speaker_profiles/
  index.json                       # {episode_id: {SPEAKER_XX: canonical_name}}
  embeddings/
    S00E001_SPEAKER_00.npy         # per-episode per-cluster d-vector
    S00E001_SPEAKER_01.npy
    ...
  global_clusters.json             # {cluster_id: {name, episodes, centroid_path}}
  roger_deakins_centroid.npy       # global Roger centroid (from clustering)
  james_deakins_centroid.npy       # global James centroid
```

- Input: audio files + diarization output + episode metadata (all existing)
- Output: updated `transcript.json` with `speaker` field per segment; speaker registry files above
- Run on existing 5 episodes first for validation; then batch over remaining episodes

**Acceptance criteria:**
- [ ] Roger correctly identified in ≥4/5 existing episodes (manual spot-check of output — no labeling required to *run*)
- [ ] James correctly identified in all 5 (intro anchor should be ~100%)
- [ ] Guest name matches `metadata.json` in all 5
- [ ] No manual audio clipping required at any step

---

## Consequences

- Speaker labels enable MCP queries like "find all Roger segments on natural light"
- Semantic chapters improve podcast player UX and search precision
- Phase B3 requires one-time HuggingFace license acceptance (not automatable)
- `library/speaker_profiles/` is gitignored (binary numpy arrays, regenerable)
- Post-processing is idempotent — safe to re-run as pipeline improves
- Schema is additive — existing consumers see new optional fields, not breakage

---

## Migration notes

After Phase B3, update `index_sqlite.py` to include `speaker` in FTS5 index
and add `speaker` facet to MCP search tools (ADR-003 integration path).
