#!/usr/bin/env python3
"""
Team Deakins Podcast KB Ingest

Purpose
-------
Turn a flat `downloads/` folder of mp3s (downloaded via Libsyn RSS enclosure URLs)
into an episode-centric knowledge base:

- One folder per episode
- `metadata.json` with robust episode metadata parsed from RSS
- `transcript/` scaffold:
    - `transcript.txt` placeholder (or filled when possible)
    - `sources.json` recording where transcripts may be obtained

Transcript Reality Check
------------------------
Apple Podcasts provides transcripts *in the Podcasts apps* and auto-generates them,
but Apple's public web episode pages do not reliably expose transcript text for
programmatic retrieval.

So this script:
1) Prefers Podcasting 2.0 `<podcast:transcript>` URLs if present in RSS.
2) Optionally uses Tapesearch as a fallback (may be partial/paywalled for recent eps).
3) Always creates a transcript placeholder so your pipeline is stable.

Usage
-----
python ingest_teamdeakins_downloads.py \
  --rss "https://rss.libsyn.com/shows/265448/destinations/2018942.xml" \
  --downloads "./downloads" \
  --fill-transcripts \
  --tapesearch

Flags
-----
--dry-run          : show what would happen without moving/writing
--fill-transcripts : attempt to fill transcript.txt from sources
--tapesearch       : enable Tapesearch fallback transcript scraping (best-effort)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# ----------------------------
# Config / Constants
# ----------------------------

DEFAULT_UA = "Mozilla/5.0 (Educational Research Bot; Fair Use; Team Deakins KB Builder)"
RATE_LIMIT_S = 2.0
HTTP_TIMEOUT_S = 45

# Podcasting namespaces commonly encountered
NS = {
    "itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "podcast": "https://podcastindex.org/namespace/1.0",
}

# Episode title often includes "SEASON 2 - EPISODE 176 - ..."
SEASON_EP_RE = re.compile(r"SEASON\s+(?P<season>\d+)\s*-\s*EPISODE\s+(?P<episode>\d+)", re.IGNORECASE)

def now_iso() -> str:
    """UTC timestamp for provenance fields."""
    return datetime.now(timezone.utc).isoformat()

def sha256_text(s: str) -> str:
    """Stable content hashing for integrity/versioning."""
    return hashlib.sha256(s.encode("utf-8", errors="ignore")).hexdigest()

def sanitize_slug(s: str, max_len: int = 80) -> str:
    """Filesystem-safe slug from a title."""
    s = s.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s).strip("-")
    return s[:max_len] if s else "untitled"

def parse_rfc822_date(s: str) -> Optional[str]:
    """Best-effort parse of RFC822 pubDate into YYYY-MM-DD (keeps it simple & stable)."""
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).date().isoformat()
    except Exception:
        return None


# ----------------------------
# HTTP Session
# ----------------------------

def make_session() -> requests.Session:
    """
    Create a retrying requests session with a polite UA.
    """
    session = requests.Session()
    session.headers.update({"User-Agent": DEFAULT_UA, "Accept": "*/*"})
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET"])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


# ----------------------------
# Models
# ----------------------------

@dataclass
class Episode:
    """
    Canonical episode model derived from RSS.

    Notes
    -----
    We intentionally store both *raw* RSS fields and normalized/derived fields.
    This keeps your KB resilient if parsing rules change later.
    """
    guid: str
    title: str
    pub_date_raw: str
    pub_date_iso: Optional[str]
    enclosure_url: str
    enclosure_filename: str
    enclosure_length: Optional[int]
    enclosure_type: Optional[str]

    description_html: Optional[str]
    content_encoded_html: Optional[str]

    itunes_season: Optional[int]
    itunes_episode: Optional[int]
    itunes_duration: Optional[str]
    itunes_explicit: Optional[str]
    itunes_episode_type: Optional[str]
    itunes_image: Optional[str]

    podcast_transcripts: list[dict[str, Any]]

    derived_slug: str
    derived_dir_id: str
    scraped_at: str

    # Audio metadata (extracted if mutagen available)
    audio_metadata: Optional[dict[str, Any]] = None


# ----------------------------
# Audio Metadata Extraction
# ----------------------------

def extract_audio_metadata(mp3_path: Path) -> Optional[dict[str, Any]]:
    """
    Extract technical metadata from MP3 file using mutagen if available.

    Returns metadata like bitrate, sample rate, duration, etc.
    """
    try:
        from mutagen.mp3 import MP3
        from mutagen.id3 import ID3

        audio = MP3(mp3_path)

        metadata = {
            "duration_seconds": audio.info.length,
            "bitrate": audio.info.bitrate,
            "sample_rate": audio.info.sample_rate,
            "channels": audio.info.channels,
            "file_size_bytes": mp3_path.stat().st_size,
        }

        # Try to get ID3 tags if present
        try:
            tags = ID3(mp3_path)
            if tags:
                metadata["id3_tags"] = {
                    k: str(v) for k, v in tags.items()
                }
        except Exception:
            pass

        return metadata
    except ImportError:
        return None
    except Exception as e:
        print(f"  Warning: Could not extract audio metadata: {e}")
        return None


# ----------------------------
# RSS Parsing
# ----------------------------

def fetch_rss(session: requests.Session, rss_url: str) -> ET.Element:
    """
    Fetch RSS XML and return root element.

    Raises on non-200 responses.
    """
    print(f"Fetching RSS feed from {rss_url}...")
    time.sleep(RATE_LIMIT_S)
    r = session.get(rss_url, timeout=HTTP_TIMEOUT_S)
    r.raise_for_status()
    return ET.fromstring(r.content)

def _text(elem: Optional[ET.Element]) -> Optional[str]:
    return elem.text.strip() if elem is not None and elem.text else None

def parse_episodes_from_rss(root: ET.Element) -> list[Episode]:
    """
    Parse RSS <item> nodes into Episode objects.

    Also detects Podcasting 2.0 transcript links:
    <podcast:transcript url="..." type="text/plain" language="en" ... />
    """
    episodes: list[Episode] = []

    for item in root.findall(".//item"):
        title = _text(item.find("title")) or "Unknown"
        guid = _text(item.find("guid")) or sha256_text(title)[:16]
        pub_date_raw = _text(item.find("pubDate")) or "Unknown"
        pub_date_iso = parse_rfc822_date(pub_date_raw)

        enclosure = item.find("enclosure")
        if enclosure is None or "url" not in enclosure.attrib:
            continue

        enclosure_url = enclosure.attrib["url"]
        enclosure_filename = os.path.basename(urlparse(enclosure_url).path)
        enclosure_length = int(enclosure.attrib["length"]) if "length" in enclosure.attrib and enclosure.attrib["length"].isdigit() else None
        enclosure_type = enclosure.attrib.get("type")

        # RSS descriptions often contain HTML; keep as-is for later parsing.
        description_html = _text(item.find("description"))
        content_encoded_html = _text(item.find("content:encoded", NS))

        itunes_season = _text(item.find("itunes:season", NS))
        itunes_episode = _text(item.find("itunes:episode", NS))
        itunes_duration = _text(item.find("itunes:duration", NS))
        itunes_explicit = _text(item.find("itunes:explicit", NS))
        itunes_episode_type = _text(item.find("itunes:episodeType", NS))

        itunes_image = None
        it_img = item.find("itunes:image", NS)
        if it_img is not None:
            itunes_image = it_img.attrib.get("href")

        # Podcasting 2.0 transcript tags
        podcast_transcripts: list[dict[str, Any]] = []
        for t in item.findall("podcast:transcript", NS):
            podcast_transcripts.append(dict(t.attrib))

        # Derive season/episode if missing by parsing title like "SEASON 2 - EPISODE 176 - ..."
        season_i = int(itunes_season) if itunes_season and itunes_season.isdigit() else None
        episode_i = int(itunes_episode) if itunes_episode and itunes_episode.isdigit() else None
        if season_i is None or episode_i is None:
            m = SEASON_EP_RE.search(title)
            if m:
                season_i = season_i or int(m.group("season"))
                episode_i = episode_i or int(m.group("episode"))

        derived_slug = sanitize_slug(title)
        derived_dir_id = sha256_text(guid + enclosure_url)[:10]

        episodes.append(
            Episode(
                guid=guid,
                title=title,
                pub_date_raw=pub_date_raw,
                pub_date_iso=pub_date_iso,
                enclosure_url=enclosure_url,
                enclosure_filename=enclosure_filename,
                enclosure_length=enclosure_length,
                enclosure_type=enclosure_type,
                description_html=description_html,
                content_encoded_html=content_encoded_html,
                itunes_season=season_i,
                itunes_episode=episode_i,
                itunes_duration=itunes_duration,
                itunes_explicit=itunes_explicit,
                itunes_episode_type=itunes_episode_type,
                itunes_image=itunes_image,
                podcast_transcripts=podcast_transcripts,
                derived_slug=derived_slug,
                derived_dir_id=derived_dir_id,
                scraped_at=now_iso(),
            )
        )

    # oldest → newest is usually useful for initial organization
    episodes.sort(key=lambda e: e.pub_date_iso or "")
    return episodes


# ----------------------------
# Storage / Layout
# ----------------------------

def episode_dir_name(ep: Episode) -> str:
    """
    Build a stable, human-friendly directory name.

    Example:
      S02E176__2026-01-14__chris-lowe-production-designer__libsyn_ab12cd34ef
    """
    season = f"S{ep.itunes_season:02d}" if ep.itunes_season is not None else "S00"
    episode = f"E{ep.itunes_episode:03d}" if ep.itunes_episode is not None else "E000"
    date = ep.pub_date_iso or "unknown-date"
    return f"{season}{episode}__{date}__{ep.derived_slug}__libsyn_{ep.derived_dir_id}"

def write_json(path: Path, data: Any, dry_run: bool) -> None:
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def ensure_placeholder_transcript(transcript_txt: Path, sources_json: Path, sources: dict, dry_run: bool) -> None:
    """
    Create transcript scaffold.

    Always creates:
    - sources.json: where transcript might be sourced
    - transcript.txt: placeholder text
    """
    write_json(sources_json, sources, dry_run=dry_run)

    if dry_run:
        return
    transcript_txt.parent.mkdir(parents=True, exist_ok=True)
    if not transcript_txt.exists():
        transcript_txt.write_text(
            "TRANSCRIPT PLACEHOLDER\n"
            "----------------------\n"
            "No transcript has been fetched yet.\n"
            "See sources.json for candidate sources and next actions.\n",
            encoding="utf-8",
        )


# ----------------------------
# Transcript filling (best-effort)
# ----------------------------

def fetch_transcript_from_podcast_namespace(session: requests.Session, ep: Episode) -> Optional[str]:
    """
    If RSS includes <podcast:transcript url="...">, fetch and return text.

    This is the most 'official' and automation-friendly path, because the tag
    is explicitly intended to link transcript files.
    """
    if not ep.podcast_transcripts:
        return None

    # pick first "text/plain" transcript if available, else first transcript
    chosen = None
    for t in ep.podcast_transcripts:
        if (t.get("type") or "").startswith("text/plain"):
            chosen = t
            break
    chosen = chosen or ep.podcast_transcripts[0]

    url = chosen.get("url")
    if not url:
        return None

    time.sleep(RATE_LIMIT_S)
    r = session.get(url, timeout=HTTP_TIMEOUT_S)
    r.raise_for_status()
    return r.text

def build_tapesearch_index(session: requests.Session) -> dict[str, str]:
    """
    Build a mapping of normalized episode title -> tapesearch episode URL.

    NOTE: This is best-effort and subject to Tapesearch access constraints and policies.
    """
    print("Building Tapesearch index...")
    show_url = "https://www.tapesearch.com/podcast/team-deakins/1510638084"
    time.sleep(RATE_LIMIT_S)
    try:
        r = session.get(show_url, timeout=HTTP_TIMEOUT_S)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        mapping: dict[str, str] = {}
        for a in soup.select('a[href^="/episode/"]'):
            title = a.get_text(" ", strip=True)
            href = a.get("href")
            if not title or not href:
                continue
            key = re.sub(r"\s+", " ", title.strip().lower())
            mapping[key] = urljoin(show_url, href)

        print(f"  Found {len(mapping)} episodes on Tapesearch")
        return mapping
    except Exception as e:
        print(f"  Warning: Could not build Tapesearch index: {e}")
        return {}

def fetch_transcript_from_tapesearch(session: requests.Session, tapesearch_url: str) -> Optional[str]:
    """
    Fetch transcript text from a Tapesearch episode page.

    Tapesearch pages show a Transcript section with timestamps, but may paywall full
    transcripts for recent episodes.
    """
    time.sleep(RATE_LIMIT_S)
    r = session.get(tapesearch_url, timeout=HTTP_TIMEOUT_S)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    text = soup.get_text("\n", strip=True)

    if "Transcript will be available on the free plan in 28 days" in text:
        return None

    # naive extraction: keep the section after "### Transcript" if present
    if "### Transcript" not in text:
        return None

    after = text.split("### Transcript", 1)[1].strip()
    # Clip off footer/disclaimer area if present
    after = after.split("Disclaimer:", 1)[0].strip()
    return after or None


# ----------------------------
# Main ingest
# ----------------------------

def ingest(
    rss_url: str,
    downloads_dir: Path,
    dry_run: bool,
    fill_transcripts: bool,
    enable_tapesearch: bool,
) -> None:
    """
    Ingest downloaded mp3s into per-episode directories and write metadata/scaffolds.
    """
    session = make_session()

    root = fetch_rss(session, rss_url)
    episodes = parse_episodes_from_rss(root)
    print(f"Found {len(episodes)} episodes in RSS feed\n")

    # Build quick lookup: enclosure filename -> Episode
    by_filename = {ep.enclosure_filename: ep for ep in episodes}

    # Optional: build tapesearch mapping once
    tapesearch_map: dict[str, str] = {}
    if enable_tapesearch:
        tapesearch_map = build_tapesearch_index(session)

    mp3_files = sorted(downloads_dir.glob("*.mp3"))
    print(f"Found {len(mp3_files)} MP3 files in downloads directory\n")

    # Track statistics
    stats = {
        "processed": 0,
        "skipped_no_match": 0,
        "skipped_exists": 0,
        "moved": 0,
        "transcripts_filled": 0,
        "errors": 0,
    }

    for i, mp3_path in enumerate(mp3_files, 1):
        print(f"[{i}/{len(mp3_files)}] Processing: {mp3_path.name}")

        ep = by_filename.get(mp3_path.name)
        if not ep:
            print(f"  [SKIP] No RSS match for: {mp3_path.name}")
            stats["skipped_no_match"] += 1
            continue

        try:
            ep_dir = downloads_dir / episode_dir_name(ep)
            audio_dest = ep_dir / "audio.mp3"
            meta_path = ep_dir / "metadata.json"
            transcript_dir = ep_dir / "transcript"
            transcript_txt = transcript_dir / "transcript.txt"
            sources_json = transcript_dir / "sources.json"

            # Extract audio metadata
            audio_metadata = extract_audio_metadata(mp3_path)
            ep.audio_metadata = audio_metadata

            # Build sources record
            sources = {
                "episode": {
                    "guid": ep.guid,
                    "title": ep.title,
                    "pub_date_raw": ep.pub_date_raw,
                    "pub_date_iso": ep.pub_date_iso,
                },
                "sources": {
                    "rss_enclosure": ep.enclosure_url,
                    "apple_podcasts_episode_page": None,
                    "podcast_namespace_transcripts": ep.podcast_transcripts,
                    "tapesearch_episode_page": None,
                },
                "notes": [
                    "Apple Podcasts transcripts are accessible in the Podcasts app UI and are auto-generated shortly after publish. "
                    "Public web episode pages may not expose transcript text for programmatic retrieval.",
                ],
                "generated_at": now_iso(),
            }

            # Attach tapesearch URL if we can match by title
            title_key = re.sub(r"\s+", " ", ep.title.strip().lower())
            ts_url = tapesearch_map.get(title_key)
            if ts_url:
                sources["sources"]["tapesearch_episode_page"] = ts_url

            # Create folders + metadata
            print(f"  Title: {ep.title}")
            print(f"  -> {ep_dir.name}")

            if not dry_run:
                ep_dir.mkdir(parents=True, exist_ok=True)

            # Move mp3 into directory
            if audio_dest.exists():
                print("  -> audio.mp3 already exists (not moving)")
                stats["skipped_exists"] += 1
            else:
                if dry_run:
                    print(f"  [DRY-RUN] Would move {mp3_path} -> {audio_dest}")
                else:
                    shutil.move(str(mp3_path), str(audio_dest))
                    print("  -> audio.mp3 moved")
                    stats["moved"] += 1

            # Write metadata.json
            meta = asdict(ep)
            meta["provenance"] = {"rss_url": rss_url, "ingested_at": now_iso()}
            write_json(meta_path, meta, dry_run=dry_run)
            if not dry_run:
                print("  -> metadata.json written")

            # Transcript scaffolds
            ensure_placeholder_transcript(transcript_txt, sources_json, sources, dry_run=dry_run)
            if not dry_run:
                print("  -> transcript scaffold created")

            # Optionally fill transcript
            if fill_transcripts and not dry_run:
                transcript_text = None

                # 1) Podcasting 2.0 transcript tag
                try:
                    transcript_text = fetch_transcript_from_podcast_namespace(session, ep)
                    if transcript_text:
                        print("  -> transcript found in podcast namespace")
                except Exception as e:
                    print(f"  -> podcast namespace transcript failed: {e}")
                    transcript_text = None

                # 2) Tapesearch fallback
                if transcript_text is None and enable_tapesearch and ts_url:
                    try:
                        transcript_text = fetch_transcript_from_tapesearch(session, ts_url)
                        if transcript_text:
                            print("  -> transcript found on Tapesearch")
                    except Exception as e:
                        print(f"  -> Tapesearch transcript failed: {e}")
                        transcript_text = None

                if transcript_text:
                    transcript_txt.write_text(transcript_text.strip() + "\n", encoding="utf-8")
                    stats["transcripts_filled"] += 1
                else:
                    print("  -> no transcript available (left placeholder)")

            stats["processed"] += 1

            # be polite
            if i < len(mp3_files):
                time.sleep(RATE_LIMIT_S)

        except Exception as e:
            print(f"  [ERROR] Failed to process: {e}")
            stats["errors"] += 1
            continue

    # Print summary
    print("\n" + "=" * 70)
    print("INGEST SUMMARY")
    print("=" * 70)
    print(f"Total MP3 files found:        {len(mp3_files)}")
    print(f"Successfully processed:       {stats['processed']}")
    print(f"Moved to episode dirs:        {stats['moved']}")
    print(f"Already existed (skipped):    {stats['skipped_exists']}")
    print(f"No RSS match (skipped):       {stats['skipped_no_match']}")
    print(f"Transcripts filled:           {stats['transcripts_filled']}")
    print(f"Errors:                       {stats['errors']}")
    print("=" * 70)

    if dry_run:
        print("\nDRY RUN - No files were actually moved or modified")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Organize Team Deakins podcast downloads into structured knowledge base"
    )
    ap.add_argument("--rss", required=True, help="Libsyn RSS feed URL")
    ap.add_argument("--downloads", required=True, help="Path to downloads/ directory")
    ap.add_argument("--dry-run", action="store_true", help="Show what would happen without making changes")
    ap.add_argument("--fill-transcripts", action="store_true", help="Attempt to fetch transcripts from sources")
    ap.add_argument("--tapesearch", action="store_true", help="Enable best-effort Tapesearch fallback for transcripts")
    args = ap.parse_args()

    downloads_path = Path(args.downloads)
    if not downloads_path.exists():
        print(f"Error: Downloads directory not found: {downloads_path}")
        sys.exit(1)

    if not downloads_path.is_dir():
        print(f"Error: {downloads_path} is not a directory")
        sys.exit(1)

    try:
        ingest(
            rss_url=args.rss,
            downloads_dir=downloads_path,
            dry_run=args.dry_run,
            fill_transcripts=args.fill_transcripts,
            enable_tapesearch=args.tapesearch,
        )
        print("\nDone!")
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
