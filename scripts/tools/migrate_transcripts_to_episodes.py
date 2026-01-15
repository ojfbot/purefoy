#!/usr/bin/env python3
"""
Migrate transcripts from teamdeakins_transcripts/ to downloads/[episode]/transcript/

This script:
1. Reads transcript JSONs from teamdeakins_transcripts/
2. Matches them to episode directories using GUID
3. Moves transcripts to downloads/[episode]/transcript/
"""

import json
import shutil
from pathlib import Path

# Paths
TRANSCRIPTS_DIR = Path("teamdeakins_transcripts")
DOWNLOADS_DIR = Path("downloads")


def find_episode_dir_by_guid(guid: str) -> Path:
    """Find episode directory by GUID from metadata.json."""
    for episode_dir in DOWNLOADS_DIR.iterdir():
        if not episode_dir.is_dir() or episode_dir.name.startswith("."):
            continue

        metadata_file = episode_dir / "metadata.json"
        if not metadata_file.exists():
            continue

        try:
            with open(metadata_file, "r") as f:
                metadata = json.load(f)

            if metadata.get("guid") == guid:
                return episode_dir
        except Exception as e:
            print(f"Warning: Could not read {metadata_file}: {e}")
            continue

    return None


def migrate_transcripts():
    """Migrate all transcripts to episode directories."""
    print("=" * 70)
    print("Migrating Transcripts to Episode Directories")
    print("=" * 70)
    print()

    if not TRANSCRIPTS_DIR.exists():
        print(f"✗ Transcript directory not found: {TRANSCRIPTS_DIR}")
        return

    # Find all transcript JSONs
    transcript_jsons = list(TRANSCRIPTS_DIR.glob("transcript_*.json"))

    if not transcript_jsons:
        print(f"✗ No transcript JSONs found in {TRANSCRIPTS_DIR}")
        return

    print(f"Found {len(transcript_jsons)} transcript files\n")

    migrated = 0
    not_found = 0

    for transcript_json in transcript_jsons:
        # Read transcript metadata
        with open(transcript_json, "r") as f:
            transcript_data = json.load(f)

        episode_title = transcript_data.get("episode_title", "Unknown")
        guid = transcript_data.get("episode_guid")
        transcript_id = transcript_data.get("transcript_id")

        print(f"Processing: {episode_title}")
        print(f"  GUID: {guid}")
        print(f"  Transcript ID: {transcript_id}")

        if not guid:
            print(f"  ✗ No GUID found, skipping\n")
            not_found += 1
            continue

        # Find matching episode directory
        episode_dir = find_episode_dir_by_guid(guid)

        if not episode_dir:
            print(f"  ✗ Episode directory not found\n")
            not_found += 1
            continue

        print(f"  → Episode: {episode_dir.name}")

        # Create transcript directory
        transcript_dir = episode_dir / "transcript"
        transcript_dir.mkdir(exist_ok=True)

        # Move transcript.txt
        txt_file = TRANSCRIPTS_DIR / f"transcript_{transcript_id}.txt"
        if txt_file.exists():
            dest_txt = transcript_dir / "transcript.txt"
            shutil.move(str(txt_file), str(dest_txt))
            print(f"  ✓ Moved: transcript.txt")

        # Move transcript.json (as sources.json)
        dest_json = transcript_dir / "transcript_sources.json"
        shutil.move(str(transcript_json), str(dest_json))
        print(f"  ✓ Moved: transcript_sources.json")

        migrated += 1
        print()

    # Clean up manifest
    manifest_file = TRANSCRIPTS_DIR / "manifest.json"
    if manifest_file.exists():
        dest_manifest = TRANSCRIPTS_DIR / "manifest_backup.json"
        shutil.move(str(manifest_file), str(dest_manifest))
        print(f"Backed up manifest.json to manifest_backup.json")

    print("=" * 70)
    print(f"✓ Migrated: {migrated} transcripts")
    print(f"✗ Not found: {not_found} episodes")
    print("=" * 70)

    if migrated > 0:
        print(f"\nTranscripts are now in: downloads/[episode]/transcript/")
        print(f"  - transcript.txt (plain text)")
        print(f"  - transcript_sources.json (metadata)")


if __name__ == "__main__":
    migrate_transcripts()
