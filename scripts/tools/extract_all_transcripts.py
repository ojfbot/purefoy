#!/usr/bin/env python3
"""
Extract all podcast transcripts from Apple Podcasts cache.

This script:
1. Queries the Podcasts database for episodes with transcripts
2. Finds corresponding TTML files in cache
3. Extracts plain text from TTML (XML) format
4. Saves to organized structure matching episode metadata

Usage:
    python3 extract_all_transcripts.py [--output-dir OUTPUT_DIR]
"""

import argparse
import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional
import json

# Apple Podcasts paths
DB_PATH = Path.home() / "Library/Group Containers/243LU875E5.groups.com.apple.podcasts/Documents/MTLibrary.sqlite"
CACHE_BASE = Path.home() / "Library/Group Containers/243LU875E5.groups.com.apple.podcasts/Library/Cache/Assets/TTML"


def extract_text_from_ttml(ttml_path: Path) -> str:
    """
    Extract plain text from TTML file.

    Args:
        ttml_path: Path to TTML XML file

    Returns:
        Plain text transcript
    """
    try:
        tree = ET.parse(ttml_path)
        root = tree.getroot()

        # Extract all word spans
        words = []
        for span in root.iter('{http://www.w3.org/ns/ttml}span'):
            if span.text:
                words.append(span.text)

        return ' '.join(words)

    except Exception as e:
        print(f"Error parsing {ttml_path}: {e}")
        return ""


def get_episodes_with_transcripts() -> List[Dict]:
    """
    Query database for episodes with transcript identifiers.

    Returns:
        List of dicts with episode info and transcript paths
    """
    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        return []

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = """
        SELECT
            ZTITLE as title,
            ZGUID as guid,
            ZTRANSCRIPTIDENTIFIER as transcript_id,
            ZASSETURL as asset_url,
            ZPUBDATE as pub_date,
            ZEPISODENUMBER as episode_number,
            ZSEASONNUMBER as season_number,
            ZDURATION as duration
        FROM ZMTEPISODE
        WHERE ZTRANSCRIPTIDENTIFIER IS NOT NULL
        ORDER BY ZPUBDATE DESC
    """

    cursor.execute(query)
    episodes = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return episodes


def find_ttml_file(transcript_id: str) -> Optional[Path]:
    """
    Find TTML file in cache based on transcript identifier.

    Args:
        transcript_id: Full path from database (e.g., PodcastContent221/.../transcript_ID.ttml)

    Returns:
        Path to TTML file if found, None otherwise
    """
    if not transcript_id:
        return None

    # transcript_id format: PodcastContent221/v4/74/d5/ca/.../transcript_1000590147486.ttml
    ttml_path = CACHE_BASE / transcript_id

    if ttml_path.exists():
        return ttml_path

    return None


def extract_transcript_number(transcript_id: str) -> Optional[str]:
    """Extract numeric ID from transcript path."""
    if "transcript_" in transcript_id:
        parts = transcript_id.split("transcript_")
        if len(parts) == 2:
            return parts[1].split(".")[0]
    return None


def main():
    parser = argparse.ArgumentParser(description="Extract all Apple Podcasts transcripts")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("extracted_transcripts"),
        help="Output directory for transcripts"
    )
    parser.add_argument(
        "--format",
        choices=["txt", "json"],
        default="txt",
        help="Output format (txt or json with metadata)"
    )
    args = parser.parse_args()

    print("=" * 70)
    print("  Apple Podcasts Transcript Extractor")
    print("=" * 70)
    print()

    # Create output directory
    args.output_dir.mkdir(exist_ok=True, parents=True)

    # Get episodes from database
    print("Querying database for episodes with transcripts...")
    episodes = get_episodes_with_transcripts()
    print(f"Found {len(episodes)} episodes with transcript metadata\n")

    if not episodes:
        print("No episodes with transcripts found.")
        print("Make sure Apple Podcasts app has downloaded episodes with transcripts.")
        return

    # Process each episode
    extracted_count = 0
    missing_count = 0

    print("Extracting transcripts...\n")

    for i, episode in enumerate(episodes, 1):
        title = episode['title'] or "Untitled"
        transcript_id = episode['transcript_id']
        guid = episode['guid']

        print(f"[{i}/{len(episodes)}] {title[:60]}")

        # Find TTML file
        ttml_path = find_ttml_file(transcript_id)

        if not ttml_path:
            print(f"    ⚠️  TTML file not found in cache")
            missing_count += 1
            continue

        # Extract text
        transcript_text = extract_text_from_ttml(ttml_path)

        if not transcript_text:
            print(f"    ✗ Failed to extract text")
            missing_count += 1
            continue

        word_count = len(transcript_text.split())
        print(f"    ✓ Extracted {word_count} words")

        # Save transcript
        transcript_num = extract_transcript_number(transcript_id)
        filename = f"transcript_{transcript_num}"

        if args.format == "txt":
            output_file = args.output_dir / f"{filename}.txt"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(transcript_text)

        elif args.format == "json":
            output_file = args.output_dir / f"{filename}.json"
            data = {
                "episode_title": title,
                "episode_guid": guid,
                "transcript_id": transcript_num,
                "transcript_text": transcript_text,
                "word_count": word_count,
                "duration": episode.get('duration'),
                "season": episode.get('season_number'),
                "episode": episode.get('episode_number'),
                "ttml_path": str(ttml_path)
            }
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        extracted_count += 1

    print()
    print("=" * 70)
    print("Extraction Complete!")
    print("=" * 70)
    print(f"Successfully extracted: {extracted_count}")
    print(f"Missing/failed: {missing_count}")
    print(f"Output directory: {args.output_dir}")
    print("=" * 70)

    # Save manifest
    manifest_file = args.output_dir / "manifest.json"
    manifest = {
        "total_episodes": len(episodes),
        "extracted": extracted_count,
        "missing": missing_count,
        "output_format": args.format,
        "episodes": [
            {
                "title": ep['title'],
                "guid": ep['guid'],
                "transcript_id": extract_transcript_number(ep['transcript_id']),
                "has_cache": find_ttml_file(ep['transcript_id']) is not None
            }
            for ep in episodes
        ]
    }

    with open(manifest_file, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"\nManifest saved to: {manifest_file}")


if __name__ == "__main__":
    main()
