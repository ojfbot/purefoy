# Transcription Pipeline Optimization Research

**Status:** Open research — not yet implemented
**Related:** [ADR-005](../../decisions/adr/ADR-005-transcription-optimization.md) (decision + cost estimates), [ADR-004](../../decisions/adr/ADR-004-transcription-pipeline.md), [Transcription Guide](../guides/transcription-pipeline.md)
**Branch:** `research/transcription-optimization`

---

## Context

The current pipeline (`scripts/tools/transcribe_episodes.py`) produces accurate
word-level transcripts using faster-whisper large-v3, but two areas need
significant improvement before the transcripts are fully useful for downstream
search and MCP consumption:

1. **Speaker attribution** — all speech is currently unsegmented by speaker.
   Knowing that a given paragraph is Roger vs. James vs. the guest is essential
   for research queries ("what did Roger say about…").

2. **Chapter/chunk quality** — chapters are detected via TF-IDF term-shift
   heuristics. Semantic coherence (embedding-based) would produce tighter,
   more meaningful breaks. VAD tuning is also unexplored for podcast audio.

---

## 1. Speaker Diarization & Identification

### 1.1 Current state

Diarization is wired up in `transcribe_episodes.py` via `pyannote/speaker-diarization-3.1`
but is disabled by default (not in `requirements-transcription.txt`) and produces
only generic labels (`SPEAKER_00`, `SPEAKER_01`). No mapping to real names exists.

### 1.2 The Team Deakins cast

Every episode has the same two permanent speakers plus one guest:

| Speaker | Role | Notes |
|---|---|---|
| **James Deakins** | Host | Opens every episode with a nearly identical ~30 s intro |
| **Roger Deakins** | Co-host / expert | Primary knowledge source; highest-value speaker to tag |
| **Guest** | Varies | Name is in episode metadata (`metadata.json → itunes.summary`) |

### 1.3 Intro anchor — James identification

James opens each episode with a recognisably consistent greeting. This is the
single most reliable anchor for speaker fingerprinting:

- The first 60–90 seconds of audio can be used as a **James voice reference
  segment** with high confidence.
- This eliminates the need for a manually-curated reference file for James.
- Strategy: after diarization assigns `SPEAKER_XX` labels, find which speaker
  dominates the first 90 s → that label is James.

### 1.4 Roger identification

Roger is present in every episode. Approaches:

**Cross-episode speaker embedding clustering (adopted approach)**

Run pyannote diarization on all episodes → per-episode `SPEAKER_XX` clusters.
Extract per-cluster average d-vector embeddings (ECAPA-TDNN via speechbrain).
Cluster across all episodes (agglomerative, k=3 target):

- Two clusters appearing in nearly every episode = Roger + James (hosts)
- One cluster appearing in exactly one episode = guest
- Distinguish Roger from James: speaker dominant in the first 90 s = James (intro anchor)
- Guest name from `metadata.json → itunes.summary`

This is fully zero-label — no manual audio clipping or review required at any step.

**Option B — Reference audio extraction (rejected)**

Manually clip 30–60 s of clean Roger speech from a known episode. Use as a
fixed embedding reference. One-time human effort, then automated.

**Rejected:** violates the zero-label constraint ("no hand-labeled training
data"). The cross-episode clustering approach achieves the same result without
any manual labeling. See audit §2.3 and ADR-005 Phase B3.

### 1.5 Guest identification

Guest name is available in `metadata.json → itunes.summary` (parsed from RSS).
No voice fingerprint needed — after James and Roger are identified, the
remaining speaker(s) are the guest by elimination. Multi-guest episodes
(panel discussions) are rare and can be handled as `GUEST_A / GUEST_B`.

### 1.6 Implementation sketch

Two-phase design:

**Phase 1 — per-episode diarization + embedding extraction** (run per episode):

```python
def extract_episode_embeddings(
    audio_path: Path,
    diarization_output: Annotation,
) -> dict[str, np.ndarray]:
    """Return {SPEAKER_XX: mean_d_vector} for one episode."""
    # Uses speechbrain ECAPA-TDNN to extract per-cluster average embeddings
    ...
```

**Phase 2 — cross-episode clustering + name resolution** (run once after all episodes diarized):

```python
def resolve_all_speakers(
    per_episode_embeddings: dict[str, dict[str, np.ndarray]],  # {ep_id: {SPEAKER_XX: vec}}
    episode_metadata: dict[str, dict],                          # {ep_id: metadata}
) -> dict[str, dict[str, str]]:
    """Return {ep_id: {SPEAKER_XX: canonical_name}} for all episodes."""

    # 1. Stack all embeddings for global clustering
    # 2. Agglomerative clustering (k=3) → two recurring = hosts, one-off = guest
    # 3. Identify James: dominant speaker in first 90s of each episode
    # 4. Assign Roger to the other recurring cluster
    # 5. Assign guest name from metadata.json → itunes.summary
    ...
```

### 1.7 Dependencies required

```
# Add to requirements-transcription.txt (GPU path)
pyannote.audio>=3.3
torch>=2.0.0
speechbrain>=1.0.0    # for ECAPA-TDNN speaker embeddings

# Or CPU-only alternative (slower but no CUDA required)
resemblyzer>=0.1.4    # GE2E speaker encoder, pure Python
```

`resemblyzer` is the lightest-weight option and runs on CPU — worth evaluating
first given the CPU-only EC2 instances currently in use.

### 1.8 HuggingFace token requirement

`pyannote/speaker-diarization-3.1` requires:
1. HuggingFace account, accept model license at
   `https://huggingface.co/pyannote/speaker-diarization-3.1`
2. `HUGGING_FACE_HUB_TOKEN` env var on EC2 instances
3. Add to `aws_runner.py` setup step (pass via SSH env or `~/.cache/huggingface/`)

### 1.9 Open questions

- [ ] Does `resemblyzer` produce embeddings stable enough for cross-episode
  Roger identification without a manually-extracted reference clip?
- [ ] What is processing time overhead for diarization on CPU? (estimate: 0.3–0.5×
  real-time for pyannote on CPU, adding ~30 min per 90-min episode)
- [ ] Should diarization run as a separate post-processing pass (independent of
  transcription) to allow retrying without re-transcribing?
- [ ] Roger reference clip: extract from `S00E001__beginnings` (already
  transcribed) — which segment indices are cleanest solo Roger speech?

---

## 2. Chunking Strategy Improvements

### 2.1 Current state

`chapter_generator.py` uses a five-signal weighted scoring system:

| Signal | Weight | Method |
|---|---|---|
| Coherence | 35% | TF-IDF cosine distance (bag-of-words) |
| Pause | 20% | Gap duration between segments |
| Topic shift | 20% | Jaccard distance on topic tag sets |
| Speaker turn | 10% | Dominant speaker change (binary) |
| Film boundary | 15% | New films introduced |

Minimum chapter: 2 min. Target: 7 min. Max: 20 min.

### 2.2 Semantic embedding coherence (replace TF-IDF)

TF-IDF misses paraphrase and synonym-based topic shifts. Replacing coherence
scoring with sentence embeddings would catch "we used a long lens" and
"telephoto approach" as the same concept.

**Candidate models (CPU-friendly):**

| Model | Size | Inference speed | Quality |
|---|---|---|---|
| `all-MiniLM-L6-v2` | 80 MB | ~10 ms/segment | Good for semantic similarity |
| `all-mpnet-base-v2` | 420 MB | ~30 ms/segment | Better quality, slower |
| `paraphrase-MiniLM-L3-v2` | 60 MB | ~5 ms/segment | Fast, lower quality |

`all-MiniLM-L6-v2` is the recommended starting point — it runs well on CPU,
is already widely used for podcast segmentation tasks, and adds only ~2 min
overhead per 90-min episode.

**Integration point:** Replace `_compute_coherence_score` in `chapter_generator.py`
(currently lines ~200-240) with a sliding-window embedding cosine similarity.
Keep TF-IDF as fallback if `sentence-transformers` is not installed.

### 2.3 VAD parameter tuning for podcast audio

Current VAD settings in `transcribe_episodes.py`:
```python
vad_parameters={
    "min_silence_duration_ms": 500,
    "speech_pad_ms": 200,
}
```

Podcast audio characteristics differ from general audio:
- Very low background noise
- Long uninterrupted speech runs (Roger speaks for 2-4 min without pause)
- Natural conversational pauses of 300–800 ms (interviewer listening, thinking)
- No music/jingles except intro/outro

**Recommended tuning:**
```python
vad_parameters={
    "min_silence_duration_ms": 800,   # up from 500 — avoids mid-sentence splits
    "speech_pad_ms": 400,             # up from 200 — capture breath/pause edges
    "threshold": 0.3,                 # default 0.5 — more sensitive for quiet speech
}
```

This needs A/B testing against at least 3 episodes before adopting. The risk is
merging segments across natural chapter boundaries (e.g. a 600 ms pause between
topics would not trigger a new chunk).

### 2.4 Intro/outro detection and exclusion

James's ~30 s intro and the closing credits (~60 s) are boilerplate and should
be excluded from chapter detection and topic tagging. They inflate segment counts
and pollute topic distributions.

**Strategy:**
- Detect intro: first segment where James says "welcome" / "team deakins" within
  the first 90 s → mark segments 0..N_intro as `segment_type: "intro"`.
- Detect outro: last segment containing "thank you for listening" / "see you next
  week" / closing music silence → mark as `segment_type: "outro"`.
- Exclude these from chapter generation, topic tagging, and search indexing.
- Retain in `transcript.json` for completeness but tag accordingly.

This is low-risk and high-value — the intro pattern is very consistent.

### 2.5 Speaker-weighted chapter boundaries

Currently speaker turns carry only 10% weight in chapter scoring and are binary
(dominant speaker changes or doesn't). With named speaker resolution (§1 above),
this can be improved:

- **Roger-to-guest handoff**: High-value boundary signal — when Roger finishes
  a long answer and the guest responds, this is likely a topic transition.
- **James question → Roger answer**: A new James question after Roger's extended
  response is a near-certain chapter start.
- Model: score a boundary higher when: `prev_dominant == "Roger Deakins"` AND
  `next_dominant == "James Deakins"`.

This depends on speaker identification being implemented first (§1).

### 2.6 Open questions

- [ ] Benchmark `all-MiniLM-L6-v2` chapter quality vs. current TF-IDF on the
  5 transcribed episodes — measure chapter count, avg chapter length, title
  coherence. Human eval needed (30 min effort).
- [ ] What are the exact first-segment patterns in James's intro across the 5
  transcribed episodes? Extract and compare to confirm consistency before
  building intro detection.
- [ ] Should chunking be a separate post-processing pass that reads
  `transcript_segments.jsonl` and rewrites `chapters.*`? This would allow
  re-chunking without re-transcribing, which is valuable given the 90 min/episode
  transcription cost.

---

## 3. Cross-Episode Clustering Bootstrap — Next Steps

The 5 already-transcribed episodes are sufficient to validate the clustering approach
before running the full 344-episode diarization batch.

| Episode | Duration | Status |
|---|---|---|
| S00E000 joe-walker | ~112 min | ✓ transcript on disk |
| S00E000 chris-corbould | ~113 min | ✓ transcript on disk |
| S00E001 beginnings | ~56 min | ✓ transcript on disk |
| S00E002 working-together | ~47 min | ✓ transcript on disk |
| S00E003 location-scouting | ~38 min | ✓ transcript on disk |

**Zero-label validation workflow (no manual audio review needed):**

1. Run `pyannote/speaker-diarization-3.1` on all 5 episodes → per-episode `SPEAKER_XX` clusters.
2. Extract per-cluster ECAPA-TDNN d-vectors (average over each cluster's segments).
3. Run agglomerative clustering (k=3) across the 5 episodes' embeddings.
4. Assign James to the cluster dominant in each episode's first 90 s.
5. Assign Roger to the other recurring cluster.
6. Verify: spot-check 2–3 segment texts per episode to confirm assignment. This is *verification*, not labeling — no audio editing required.
7. Save centroids to `library/speaker_profiles/` for use in the full batch.

Estimated compute: ~4 min GPU × 5 episodes = ~20 min diarization. Clustering: seconds.
No manual audio clipping or review loop required.

---

## 4. Dependency Summary

| Package | Purpose | CPU viable? | License |
|---|---|---|---|
| `pyannote.audio>=3.3` | Speaker diarization | Yes (slow) | MIT + HF license |
| `resemblyzer>=0.1.4` | Speaker embeddings (GE2E) | Yes | Apache 2.0 |
| `speechbrain>=1.0.0` | ECAPA-TDNN embeddings (alt) | Yes | Apache 2.0 |
| `sentence-transformers>=3.0` | Semantic chunking embeddings | Yes | Apache 2.0 |
| `torch>=2.0.0` | Required by pyannote + speechbrain | Yes (slow) | BSD |

All are Apache/MIT licensed. `torch` is the heaviest addition (~2 GB download).
If running CPU-only, `resemblyzer` + `sentence-transformers` avoid a full torch
install.

---

## 5. Recommended Implementation Order

1. **Intro/outro detection** — zero dependencies, high value, 1–2 days effort.
2. **VAD parameter tuning** — A/B test on 3 episodes, 1 day effort.
3. **Semantic chunking (MiniLM)** — adds `sentence-transformers` dep only,
   no torch required if using ONNX runtime. 2–3 days effort.
4. **Speaker diarization + Roger/James profiles** — requires torch + pyannote
   + HuggingFace token setup on EC2. 3–5 days effort.
5. **Speaker-weighted chapter boundaries** — depends on #4. 1 day effort.

Items 1–3 can be done before the full batch completes and applied as a
post-processing pass. Item 4 requires re-processing transcripts (or running
as a separate pass reading existing `transcript_segments.jsonl`).
