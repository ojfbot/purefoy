#!/usr/bin/env python3
"""
Extract Team Deakins podcast transcripts from Apple Podcasts cache.

This script:
1. Queries database for Team Deakins episodes with transcripts
2. Finds cached TTML files
3. Extracts plain text
4. Saves in format compatible with ingest pipeline

Usage:
    python3 extract_teamdeakins_transcripts.py
"""

import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path
import json
from datetime import datetime

# Paths
DB_PATH = Path.home() / "Library/Group Containers/243LU875E5.groups.com.apple.podcasts/Documents/MTLibrary.sqlite"
CACHE_BASE = Path.home() / "Library/Group Containers/243LU875E5.groups.com.apple.podcasts/Library/Cache/Assets/TTML"


def extract_text_from_ttml(ttml_path: Path) -> str:
    """Extract plain text from TTML XML file."""
    try:
        tree = ET.parse(ttml_path)
        root = tree.getroot()

        words = []
        for span in root.iter('{http://www.w3.org/ns/ttml}span'):
            if span.text:
                words.append(span.text)

        return ' '.join(words)
    except Exception as e:
        print(f"Error parsing {ttml_path}: {e}")
        return ""


def get_teamdeakins_episodes():
    """Get all Team Deakins episodes with transcript metadata from database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = """
        SELECT
            e.ZTITLE as title,
            e.ZGUID as guid,
            e.ZTRANSCRIPTIDENTIFIER as transcript_id,
            e.ZEPISODENUMBER as episode_number,
            e.ZSEASONNUMBER as season_number,
            e.ZPUBDATE as pub_date,
            e.ZDURATION as duration
        FROM ZMTEPISODE e
        JOIN ZMTPODCAST p ON e.ZPODCAST = p.Z_PK
        WHERE p.ZTITLE = 'Team Deakins'
          AND e.ZTRANSCRIPTIDENTIFIER IS NOT NULL
        ORDER BY e.ZPUBDATE DESC
    """

    cursor.execute(query)
    episodes = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return episodes


def find_cached_ttml(transcript_id: str) -> Path:
    """
    Find cached TTML file.

    Database stores: PodcastContent221/.../transcript_ID.ttml
    Actual file is:  PodcastContent221/.../transcript_ID.ttml-ID.ttml
    """
    if not transcript_id or "transcript_" not in transcript_id:
        return None

    # Extract transcript number
    transcript_num = transcript_id.split("transcript_")[1].split(".")[0]

    # Build actual cache path (note: double extension)
    ttml_path = CACHE_BASE / f"{transcript_id}-{transcript_num}.ttml"

    return ttml_path if ttml_path.exists() else None


def main():
    print("=" * 70)
    print("  Team Deakins Transcript Extractor")
    print("=" * 70)
    print()

    # Get episodes from database
    print("Querying database for Team Deakins episodes...")
    episodes = get_teamdeakins_episodes()
    print(f"Found {len(episodes)} Team Deakins episodes with transcript metadata\n")

    # Check which are cached
    print("Checking cache for available transcripts...")
    cached_episodes = []

    for ep in episodes:
        ttml_path = find_cached_ttml(ep['transcript_id'])
        if ttml_path:
            ep['ttml_path'] = ttml_path
            cached_episodes.append(ep)

    print(f"Found {len(cached_episodes)} episodes with cached transcripts\n")

    if not cached_episodes:
        print("No cached transcripts found.")
        print("\nTo cache transcripts:")
        print("1. Open Apple Podcasts app")
        print("2. Navigate to Team Deakins podcast")
        print("3. Open episodes and view their transcripts")
        print("4. Run this script again")
        return

    # Extract transcripts
    print("Extracting transcripts...\n")
    output_dir = Path("teamdeakins_transcripts")
    output_dir.mkdir(exist_ok=True)

    extracted = []

    for i, ep in enumerate(cached_episodes, 1):
        title = ep['title']
        print(f"[{i}/{len(cached_episodes)}] {title}")

        # Extract text
        transcript_text = extract_text_from_ttml(ep['ttml_path'])
        word_count = len(transcript_text.split())
        print(f"    Words: {word_count}")

        # Extract transcript ID
        transcript_num = ep['transcript_id'].split("transcript_")[1].split(".")[0]

        # Save as plain text
        txt_file = output_dir / f"transcript_{transcript_num}.txt"
        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write(transcript_text)

        # Save with metadata as JSON
        json_file = output_dir / f"transcript_{transcript_num}.json"
        metadata = {
            "episode_title": title,
            "episode_guid": ep['guid'],
            "transcript_id": transcript_num,
            "transcript_text": transcript_text,
            "word_count": word_count,
            "season": ep.get('season_number'),
            "episode": ep.get('episode_number'),
            "duration": ep.get('duration'),
            "extracted_at": datetime.now().isoformat(),
            "source": "apple_podcasts_cache"
        }

        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        extracted.append({
            "title": title,
            "guid": ep['guid'],
            "transcript_id": transcript_num,
            "word_count": word_count
        })

        print(f"    ✓ Saved to {txt_file.name}\n")

    # Save manifest
    manifest = {
        "podcast": "Team Deakins",
        "total_episodes_with_transcript_metadata": len(episodes),
        "cached_transcripts": len(cached_episodes),
        "extracted": len(extracted),
        "extraction_date": datetime.now().isoformat(),
        "episodes": extracted
    }

    manifest_file = output_dir / "manifest.json"
    with open(manifest_file, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print("=" * 70)
    print("Extraction Complete!")
    print("=" * 70)
    print(f"Extracted: {len(extracted)} transcripts")
    print(f"Output: {output_dir}/")
    print(f"Manifest: {manifest_file}")
    print("=" * 70)
    print()
    print("Note: Only recently viewed episodes are cached.")
    print("To get more transcripts:")
    print("  1. Open Podcasts app")
    print("  2. View transcript for desired episodes")
    print("  3. Run this script again")


if __name__ == "__main__":
    main()
