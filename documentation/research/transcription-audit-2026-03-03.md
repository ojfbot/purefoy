# Transcription Pipeline Audit — 2026-03-03

**Auditor:** Claude Sonnet 4.6
**Scope:** ADR-004, ADR-005, `scripts/tools/`, actual transcript artifacts, AWS configuration
**Branch:** `research/transcription-optimization`

---

## 1. ADR-005 Implementation Status

| Phase | Description | Status | Evidence |
|---|---|---|---|
| **B1** | Intro/outro detection + VAD tuning | **Not implemented** | `post_process_segments.py` does not exist; `segment_type` field absent from all outputs; VAD params unchanged (500ms, not 800ms) |
| **B2** | Semantic chunking (MiniLM) | **Not implemented** | No `sentence_transformers` import anywhere; `chapter_generator.py` uses TF-IDF only |
| **B3** | Speaker diarization + name resolution | **Infrastructure only** | pyannote wired in `transcribe_episodes.py` but `--diarize` off by default; `identify_speakers.py` does not exist; `library/speaker_profiles/` does not exist; all segments have `"speaker": null` |

### Design constraint alignment

| Research-backed constraint | Status |
|---|---|
| Whisper v3 ASR with timestamped segments | **Implemented** — large-v3, word-level timestamps |
| pyannote diarization backbone | **Wired but disabled** — off by default, not in batch run |
| Zero-label speaker ID via cross-episode embedding clustering | **Not implemented and partially misspecified** — see §3 |
| Intro anchor (first 90s = James) | **Not implemented** |
| Guest identification via episode metadata | **Not implemented** |
| Semantic chunking (MiniLM, unsupervised) | **Not implemented** |
| Intro/outro via time-window + lexical rules | **Not implemented** — only first chapter renamed "Introduction" |
| LLM-based chapter title/summary generation | **Not implemented** — TF-IDF key phrase extraction only |
| Cost/throughput envelope per ADR-005 | **Partially defined** — tables exist, batch not yet run at target config |

---

## 2. Concrete Gaps

### 2.1 Phase B1 — missing files and field

**`scripts/tools/post_process_segments.py` does not exist.**

The intro "detection" in `chapter_generator.py` (line 616–619) only renames the first chapter to
"Introduction: Guest" if it starts before t=30s. It does NOT:
- Match any lexical pattern ("Welcome to the Team Deakins podcast…")
- Mark segments with `segment_type: intro`
- Exclude intro/outro from chapter generation, topic tagging, or search output

Confirmed in live output (`transcript_segments.jsonl` segment 0):
```
"Hi, and welcome to the Team Deakins podcast. This podcast is a dialogue between Roger and"
speaker: null, segment_type: [FIELD ABSENT]
```
This intro text is included verbatim in chapters, topics, and downstream search output.

VAD parameters in `transcribe_episodes.py` are still `min_silence_duration_ms: 500`,
`speech_pad_ms: 200` — not the podcast-tuned values (800ms / 400ms) proposed in the research doc.

### 2.2 Phase B2 — no semantic coherence path

`chapter_generator.py` computes coherence exclusively via TF-IDF bag-of-words (`_cosine_distance`,
line ~154). There is no import of `sentence_transformers` and no fallback path.

Symptom: chapter 0 ("Introduction") spans segments 0–26, includes James's boilerplate intro AND the
opening question, because the lexical vocabulary of both is similar (podcast meta-language). A
semantic embedding would separate these clearly.

Chapter titles are produced by TF-IDF key-phrase extraction, not LLM prompting. The user's design
constraint specifies "chapter titles and summaries are produced by an LLM via prompting, not by a
trained classifier." This is not currently implemented. Chapter 1 in S00E001 is titled "Economics
and Course" with summary "GNP, NNP, it was awful." — clearly sub-optimal.

### 2.3 Phase B3 — zero-label constraint conflict

The research doc (§1.4, Option B, recommended) proposes:
> "Manually clip 30–60s of clean Roger speech from a known episode … Use as a fixed embedding
> reference… One-time human effort."

**This directly contradicts the design constraint:** "Speaker identification should avoid any
hand-labeled training data."

The correct zero-label approach is cross-episode embedding clustering:

1. Run pyannote diarization on all episodes → SPEAKER_XX labels per episode (fully automated).
2. For each episode, extract a per-cluster embedding vector (e.g., d-vector average).
3. Cluster all per-episode embeddings across episodes (agglomerative or k-means, k=3 expected).
4. Two clusters that appear in nearly every episode = Roger and James (hosts).
5. One cluster that appears in exactly one episode per guest = guest.
6. Distinguish Roger from James using the structural heuristic: dominant speaker in first 90s = James.
7. Name the guest using `metadata.json → itunes.summary`.

This requires no manual audio clipping or labeling. ADR-005 and the research doc should be
corrected to specify this approach.

### 2.4 AWS runner does not enable diarization

`aws_runner.py` invokes `transcribe_episodes.py` without `--diarize`. The 339 pending episodes
will be transcribed **without speaker labels**. Phase B3 must therefore post-process existing audio
files — it cannot be folded into the main batch.

This is consistent with ADR-005's "Option B (post-processing)" decision, but it means:
- The 339 transcripts will need a separate diarization batch run (estimated 23 hrs GPU at ~$3.68
  spot, or 7 days CPU).
- Cross-episode clustering requires all episodes to be diarized before any names can be resolved.
- The speaker profiles (`library/speaker_profiles/`) and name mappings cannot be produced until
  after the diarization batch completes.

### 2.5 Schema not ready for downstream MCP/RAG use

Current `transcript_segments.jsonl` output:
```jsonl
{"id": 0, "start": 6.42, "end": 12.56, "text": "...", "speaker": null, "confidence": 0.0, ...}
```

Missing for MCP/RAG queries:
- `speaker` is always `null` → "Roger on topic X" queries impossible
- `segment_type` absent → intro boilerplate pollutes search results
- `chapter_id` not in segment records → cannot join segments to chapters without range scan
- No `speaker_role` field (`host` / `guest`) → role-based queries impossible
- `confidence` is always `0.0` → cannot filter low-quality segments

The SQLite FTS5 index (`index_sqlite.py`) is not yet updated to include `speaker` or
`segment_type` as facets (this is called out in ADR-005 migration notes but not yet done).

### 2.6 Cross-episode speaker clustering — no design or storage plan

The research doc and ADR-005 both refer to per-episode speaker labels but neither specifies:
- Where cross-episode embeddings are stored (format, path, schema).
- How the global speaker registry maps episode-local SPEAKER_XX to canonical names.
- How to handle episodes where pyannote assigns different cluster counts (e.g., 2 vs. 3 speakers).
- What the CLI interface looks like for the `identify_speakers.py` script.

Without this design, Phase B3 cannot be implemented without ad-hoc decisions that may require
re-processing.

---

## 3. Prioritized Recommendations

### P0 — Fix the zero-label conflict before starting B3 (0 code, design only)

Update ADR-005 and the research doc to replace the "manually extract Roger clip" approach with the
cross-episode embedding clustering approach:

1. Diarize all episodes → per-episode SPEAKER_XX clusters.
2. Average d-vector embeddings per cluster per episode.
3. Cluster across episodes → two recurring = Roger + James, one-off = guest.
4. Use first-90s dominance to assign James vs. Roger.
5. Use metadata for guest name.

This keeps the pipeline fully zero-label and is not harder to implement than the manual approach.

### P1 — Implement Phase B1 before the batch runs

`post_process_segments.py` can be built in 1–2 days and run on the 5 existing episodes as a
dry-run while the batch is pending. Key lexical patterns to detect:

**James intro** (first 90s):
```
"welcome to the team deakins podcast"
"this podcast is a dialogue between roger and james deakins"
```

**Outro** (last 120s):
```
"thanks for listening"
"thank you for listening"
"see you next week"
"you can find us at"
```

Add `segment_type: "intro" | "outro" | "content"` to segment schema. Regenerate chapters.json
excluding intro/outro. This alone will improve chapter quality noticeably.

Also fix VAD: `min_silence_duration_ms: 800`, `speech_pad_ms: 400`, `threshold: 0.3` in
`transcribe_episodes.py`. These affect future batch runs but not already-transcribed episodes.

### P2 — Add `chapter_id` to segment schema now (additive, zero cost)

Add a `chapter_id: int | null` field to each segment record pointing to the chapter it belongs to.
This eliminates the need for range scans when joining segments to chapters and is required for
efficient MCP/RAG queries. Zero processing cost — computed during existing chapter generation.

### P3 — Switch chapter titles to LLM prompting (Phase B2 prerequisite)

The current TF-IDF key-phrase titles ("Economics and Course", "GNP, NNP, it was awful") are poor.
Replacing with an LLM call is low-risk and high-value:

```python
prompt = f"""
Episode: {episode_title}
Chapter {i+1} of {total} ({start_ts}–{end_ts}):
{chapter_text[:1200]}

Write a concise, descriptive chapter title (4–8 words) and a 1-sentence summary.
JSON: {{"title": "...", "summary": "..."}}
"""
```

This can be added to `chapter_generator.py` with a `--use-llm` flag and a cheap model (haiku-class).
Cost: ~$0.001 per chapter × 22 chapters × 344 episodes ≈ $7.50 total.

### P4 — Design cross-episode speaker registry before implementing B3

Before writing `identify_speakers.py`, specify:

```
library/speaker_profiles/
  index.json                         # {episode_id: {SPEAKER_XX: canonical_name}}
  embeddings/
    S00E001_SPEAKER_00.npy           # per-episode per-cluster embedding vector
    S00E001_SPEAKER_01.npy
    ...
  global_clusters.json               # {cluster_id: {name, episodes, centroid_path}}
  roger_deakins_centroid.npy         # global Roger centroid (computed from clustering)
  james_deakins_centroid.npy         # global James centroid
```

This schema supports incremental updates (new episodes add new per-episode embeddings; global
centroids can be re-clustered periodically).

### P5 — Update FTS5 index for speaker and segment_type facets

Once Phase B1 lands, update `index_sqlite.py` to index `segment_type` and `speaker` as additional
columns. These are the two most-requested MCP query dimensions. The index rebuild is ~5 min from
existing JSON leafs and does not require re-transcribing.

---

## 4. Manual Intervention Risk Assessment

| Pipeline step | Requires manual labor? | Risk level |
|---|---|---|
| Transcription (current) | None | None |
| Intro detection (B1) | None — lexical patterns | Low |
| Semantic chunking (B2) | None | None |
| Diarization run | None | None |
| Cross-episode clustering | None (automated agglomerative) | Low — may need k tuning |
| James identification (intro heuristic) | None | Low |
| Roger identification (cluster proximity) | None if P0 implemented | Low |
| Guest naming | None — uses metadata.json | None |
| Roger reference clip (current ADR-005) | **YES — manual audio clip required** | HIGH — contradicts zero-label constraint |

After P0 (fix the design), no step requires manual labeling.
