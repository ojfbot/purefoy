#!/usr/bin/env python3
"""
Extract and parse TTML transcript files from Apple Podcasts cache.

TTML (Timed Text Markup Language) is an XML-based format containing:
- Word-level timestamps
- Speaker attribution
- Sentence boundaries

This script extracts plain text from cached TTML files.
"""

import xml.etree.ElementTree as ET
from pathlib import Path
import json
from typing import Optional, Dict, List

# Apple Podcasts cache location
TTML_CACHE_DIR = Path.home() / "Library/Group Containers/243LU875E5.groups.com.apple.podcasts/Library/Cache/Assets/TTML"


def extract_text_from_ttml(ttml_path: Path) -> str:
    """
    Extract plain text from TTML file, preserving sentence structure.

    Args:
        ttml_path: Path to TTML file

    Returns:
        Plain text transcript
    """
    try:
        tree = ET.parse(ttml_path)
        root = tree.getroot()

        # Define namespaces
        ns = {
            '': 'http://www.w3.org/ns/ttml',
            'podcasts': 'http://podcasts.apple.com/transcript-ttml-internal',
            'ttm': 'http://www.w3.org/ns/ttml#metadata'
        }

        # Extract all text spans
        text_parts = []

        # Find all <p> elements (paragraphs/utterances)
        for p in root.findall('.//{http://www.w3.org/ns/ttml}p'):
            paragraph_text = []

            # Get all word spans in this paragraph
            for span in p.findall('.//{http://www.w3.org/ns/ttml}span[@podcasts:unit="word"]', ns):
                word = span.text
                if word:
                    paragraph_text.append(word)

            if paragraph_text:
                # Join words and add paragraph
                text_parts.append(' '.join(paragraph_text))

        # Join paragraphs with newlines
        return '\n\n'.join(text_parts)

    except Exception as e:
        print(f"Error parsing {ttml_path}: {e}")
        return ""


def extract_metadata_from_ttml(ttml_path: Path) -> Dict:
    """
    Extract metadata from TTML file.

    Returns:
        Dict with duration, speaker info, etc.
    """
    try:
        tree = ET.parse(ttml_path)
        root = tree.getroot()

        metadata = {}

        # Get duration from body element
        body = root.find('.//{http://www.w3.org/ns/ttml}body')
        if body is not None and 'dur' in body.attrib:
            metadata['duration'] = body.attrib['dur']

        # Get language
        if '{http://www.w3.org/XML/1998/namespace}lang' in root.attrib:
            metadata['language'] = root.attrib['{http://www.w3.org/XML/1998/namespace}lang']

        # Count speakers
        speakers = set()
        for p in root.findall('.//{http://www.w3.org/ns/ttml}p'):
            if '{http://www.w3.org/ns/ttml#metadata}agent' in p.attrib:
                speakers.add(p.attrib['{http://www.w3.org/ns/ttml#metadata}agent'])
        metadata['speakers'] = list(speakers)

        return metadata

    except Exception as e:
        print(f"Error extracting metadata from {ttml_path}: {e}")
        return {}


def find_all_ttml_files() -> List[Path]:
    """Find all cached TTML transcript files."""
    if not TTML_CACHE_DIR.exists():
        print(f"Cache directory not found: {TTML_CACHE_DIR}")
        return []

    ttml_files = list(TTML_CACHE_DIR.rglob("*.ttml"))
    return ttml_files


def extract_transcript_id(ttml_path: Path) -> Optional[str]:
    """
    Extract transcript ID from filename.

    Example: transcript_1000738587623.ttml-1000738587623.ttml → 1000738587623
    """
    name = ttml_path.name
    if name.startswith("transcript_"):
        # Format: transcript_ID.ttml-ID.ttml
        parts = name.split("_")
        if len(parts) >= 2:
            transcript_id = parts[1].split(".")[0]
            return transcript_id
    return None


def main():
    """Main extraction function."""
    print("=" * 70)
    print("  Apple Podcasts TTML Transcript Extractor")
    print("=" * 70)
    print()

    # Find all TTML files
    print("Searching for cached transcript files...")
    ttml_files = find_all_ttml_files()
    print(f"Found {len(ttml_files)} transcript files\n")

    if not ttml_files:
        print("No transcript files found.")
        print("Make sure you have podcasts with transcripts in Apple Podcasts app.")
        return

    # Process first few as example
    print("Extracting first 3 transcripts as examples...\n")

    for i, ttml_path in enumerate(ttml_files[:3], 1):
        print(f"[{i}] Processing: {ttml_path.name}")

        # Extract transcript ID
        transcript_id = extract_transcript_id(ttml_path)
        print(f"    Transcript ID: {transcript_id}")

        # Extract metadata
        metadata = extract_metadata_from_ttml(ttml_path)
        if metadata:
            print(f"    Duration: {metadata.get('duration', 'unknown')}")
            print(f"    Speakers: {len(metadata.get('speakers', []))}")
            print(f"    Language: {metadata.get('language', 'unknown')}")

        # Extract text
        text = extract_text_from_ttml(ttml_path)
        word_count = len(text.split())
        print(f"    Word count: {word_count}")

        # Save to file
        output_dir = Path("extracted_transcripts")
        output_dir.mkdir(exist_ok=True)

        output_file = output_dir / f"transcript_{transcript_id}.txt"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"    Saved to: {output_file}")

        # Show preview
        preview = text[:200] + "..." if len(text) > 200 else text
        print(f"    Preview: {preview}\n")

    print("=" * 70)
    print(f"Total transcripts available: {len(ttml_files)}")
    print()
    print("Next steps:")
    print("1. Map transcript IDs to episode names/GUIDs")
    print("2. Integrate with ingest_teamdeakins_downloads.py")
    print("3. Extract all transcripts automatically")
    print("=" * 70)


if __name__ == "__main__":
    main()
