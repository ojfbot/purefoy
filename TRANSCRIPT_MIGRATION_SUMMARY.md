# Transcript Migration Summary

## Issue Fixed

Transcripts and manifest were being written to `teamdeakins_transcripts/` instead of the proper episode subdirectories `downloads/[episode]/transcript/`.

## Changes Made

### 1. Created Migration Script
**File**: `scripts/tools/migrate_transcripts_to_episodes.py`

Migrates existing transcripts from `teamdeakins_transcripts/` to episode directories:
- Reads transcript JSONs with episode GUIDs
- Matches GUIDs to episode `metadata.json` files
- Moves transcripts to `downloads/[episode]/transcript/`
- Renames files appropriately

### 2. Updated Extraction Script
**File**: `scripts/tools/extract_teamdeakins_transcripts_v2.py`

New version that writes directly to episode directories:
- Queries Apple Podcasts database for episodes with transcripts
- Finds cached TTML files
- Matches episodes to downloaded directories by GUID
- Extracts and saves directly to `downloads/[episode]/transcript/`

## Migration Results

✅ **Successfully migrated 5 transcripts**:

1. **EDGAR WRIGHT - Director**
   - From: `teamdeakins_transcripts/transcript_1000738504217.*`
   - To: `S02E169__2025-11-26__edgar-wright-director__libsyn_f6853474de/transcript/`

2. **DENNIS MUREN - VFX Supervisor**
   - From: `teamdeakins_transcripts/transcript_1000656376747.*`
   - To: `S02E090__2024-05-22__dennis-muren-vfx-supervisor__libsyn_aafffbfae0/transcript/`

3. **KLEBER MENDONÇA FILHO - Writer / Director**
   - From: `teamdeakins_transcripts/transcript_1000741665912.*`
   - To: `S02E172__2025-12-17__kleber-mendonça-filho-writer-director__libsyn_1dd9b3f88b/transcript/`

4. **CÉSAR CHARLONE - Cinematographer**
   - From: `teamdeakins_transcripts/transcript_1000743299891.*`
   - To: `S02E174__2025-12-31__césar-charlone-cinematographer__libsyn_4584a2f268/transcript/`

5. **EMBETH DAVIDTZ - Actor / Director**
   - From: `teamdeakins_transcripts/transcript_1000744111107.*`
   - To: `S02E175__2026-01-07__embeth-davidtz-actor-director__libsyn_cbe317a723/transcript/`

## New Directory Structure

Each episode now has transcripts in the proper location:

```
downloads/[episode]/
├── audio.mp3
├── metadata.json
└── transcript/
    ├── transcript.txt                  # Plain text transcript
    ├── transcript_sources.json         # Full metadata + transcript text
    └── sources.json                    # Extraction provenance (older)
```

### Files in transcript directory:

1. **`transcript.txt`** (Plain text)
   - Clean transcript text only
   - Easy to read/process
   - Example: 13,638 words for EMBETH DAVIDTZ episode

2. **`transcript_sources.json`** (Full metadata)
   ```json
   {
     "episode_title": "EMBETH DAVIDTZ - Actor / Director",
     "episode_guid": "9a84ef78-c7b0-4969-8954-6b8684c5b860",
     "transcript_id": "1000744111107",
     "transcript_text": "Full transcript here...",
     "word_count": 13638,
     "season": 2,
     "episode": 175,
     "duration": 4413.0,
     "extracted_at": "2026-01-15T09:58:39.374253",
     "source": "apple_podcasts_cache"
   }
   ```

3. **`sources.json`** (Extraction provenance - older format)
   - Records where transcript came from
   - Extraction timestamp
   - Source type (Apple Podcasts cache, etc.)

## Episodes with Transcripts

Found transcripts in at least **15 episode directories** (partial list):
- S00E089 - Guy Hendrix Dyas (Production Designer)
- S00E091 - Turning the Tables - FARGO
- S00E131 - Dennis Gassner (Production Designer)
- S00E136 - Jess Gonchor (Production Designer)
- S00E138 - Danielle Feinberg (Pixar DP/VFX)
- S00E155 - Ken Loach & Barry Ackroyd
- S02E002 - Rod McLean (Art Director)
- S02E090 - Dennis Muren (VFX Supervisor)
- S02E127 - Adrien Brody (Actor)
- S02E129 - Brad Ingelsby (Writer)
- S02E169 - Edgar Wright (Director)
- S02E171 - LEDs with Jeffrey Lee PhD
- S02E172 - Kleber Mendonça Filho
- S02E174 - César Charlone
- S02E175 - Embeth Davidtz

## Usage

### Extract New Transcripts

Use the v2 script to extract transcripts directly to episode directories:

```bash
python3 scripts/tools/extract_teamdeakins_transcripts_v2.py
```

**Requirements**:
1. Episodes must be downloaded to `downloads/` first
2. Transcripts must be cached in Apple Podcasts (view them in app)
3. Script matches by GUID from metadata.json

### Migrate Existing Transcripts (if needed)

If transcripts are in the old `teamdeakins_transcripts/` directory:

```bash
python3 scripts/tools/migrate_transcripts_to_episodes.py
```

## Cleanup

After migration:
- ✅ Old `teamdeakins_transcripts/` directory only contains `manifest_backup.json`
- ✅ All transcript data is now in episode directories
- ✅ Can safely remove `teamdeakins_transcripts/` if desired

## Benefits

1. **Organized Structure**: All episode data (audio, metadata, transcripts) in one place
2. **Easy Discovery**: Find transcripts with episode downloads
3. **Consistent Pattern**: Matches standard podcast directory structure
4. **No Orphaned Files**: Transcripts always paired with episodes
5. **Version Control Friendly**: Each episode is self-contained

## Notes

- The old extraction script (`extract_teamdeakins_transcripts.py`) still exists but writes to the old location
- Use `extract_teamdeakins_transcripts_v2.py` for new extractions
- Transcript IDs are preserved in `transcript_sources.json`
- GUIDs enable reliable matching between database and downloaded episodes

---

**Migration Date**: 2026-01-15
**Migrated By**: Automated migration script
**Status**: ✅ Complete
