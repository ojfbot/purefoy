#!/usr/bin/env python3
"""
Export transcript data into an S3-ready directory structure.

Walks DOWNLOADS_DIR, extracts metadata + chapters + JSONL segments for each
episode, and writes a flat output directory matching the TypeScript
EpisodeListItem / EpisodeDetail API contract (camelCase keys).

Output structure:
    output_dir/
      episodes/
        index.json              ← all EpisodeListItem objects
        {slug}/
          meta.json             ← EpisodeDetail shape
          chapters.json         ← ChapterResult[] (copied as-is)
          transcript.jsonl      ← SegmentCompact NDJSON (copied as-is)

Usage:
    python scripts/export-transcript-data.py
    python scripts/export-transcript-data.py --downloads ./downloads --output ./export
    python scripts/export-transcript-data.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path


def parse_slug(dirname: str) -> dict:
    """Parse S02E182__2026-02-25__guest__libsyn_abc → season/episode/date/guest."""
    m = re.match(r"S(\d+)E(\d+)__(\d{4}-\d{2}-\d{2})__(.+?)__libsyn_", dirname)
    if not m:
        return {"season": None, "episode": None, "dateFromSlug": None, "guestSlug": None}
    return {
        "season": int(m.group(1)),
        "episode": int(m.group(2)),
        "dateFromSlug": m.group(3),
        "guestSlug": m.group(4),
    }


def parse_duration_to_seconds(duration_str: str) -> int:
    """Parse 'HH:MM:SS' or 'MM:SS' to integer seconds."""
    if not duration_str:
        return 0
    parts = duration_str.split(":")
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return 0
    if len(nums) == 3:
        return nums[0] * 3600 + nums[1] * 60 + nums[2]
    if len(nums) == 2:
        return nums[0] * 60 + nums[1]
    return 0


def read_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def build_episode(episode_dir: Path) -> dict | None:
    """Build an EpisodeListItem + EpisodeDetail from an episode directory."""
    slug = episode_dir.name
    meta = read_json(episode_dir / "metadata.json")
    if not meta:
        return None

    parsed = parse_slug(slug)

    # Run manifest
    manifest = read_json(episode_dir / "transcript" / "run_manifest.json")
    canonical_run_id = None
    all_run_ids = []
    if manifest:
        canonical_run_id = manifest.get("canonical") or manifest.get("canonical_run_id")
        all_run_ids = [r.get("run_id", "") for r in manifest.get("runs", [])]

    has_transcript = canonical_run_id is not None

    # Stats from extraction_report.json
    stats = None
    chapters_data = None
    if canonical_run_id:
        run_dir = episode_dir / "transcript" / "runs" / canonical_run_id
        report = read_json(run_dir / "extraction_report.json")
        if report and report.get("success"):
            # Read chapters to populate topics/films arrays
            raw_chapters = read_json(run_dir / "chapters.json")
            if isinstance(raw_chapters, dict):
                chapters_data = raw_chapters
                ch_list = raw_chapters.get("chapters", [])
            elif isinstance(raw_chapters, list):
                chapters_data = raw_chapters
                ch_list = raw_chapters
            else:
                ch_list = []

            all_topics: set[str] = set()
            all_films: set[str] = set()
            for ch in ch_list:
                for t in ch.get("topics", []):
                    all_topics.add(t)
                for f in ch.get("films", []):
                    all_films.add(f)

            stats = {
                "chapters": report.get("chapters_generated", 0),
                "words": report.get("word_count", 0),
                "speakers": report.get("speakers_detected", 0),
                "topics": sorted(all_topics),
                "films": sorted(all_films),
            }

    # Goal / review data — not exported to S3, but flag presence
    goal_dir = episode_dir / "transcript" / "goal"
    has_goal = (goal_dir / "transcript_segments_goal.jsonl").exists()
    review_coverage = 0.0
    if has_goal:
        review = read_json(goal_dir / "review_progress.json")
        if review:
            review_coverage = review.get("review_coverage", 0.0)

    # Clean title — strip "SEASON X - EPISODE Y - " prefix
    title = meta.get("title", slug)
    clean_title = re.sub(
        r"^SEASON\s+\d+\s*-\s*EPISODE\s+\d+\s*-\s*", "", title, flags=re.I
    ).strip()

    # Duration
    itunes_duration = meta.get("itunes_duration", "")
    duration_seconds = parse_duration_to_seconds(itunes_duration)
    # Fallback to audio_metadata if available
    if not duration_seconds:
        am = meta.get("audio_metadata", {})
        if am and am.get("duration_seconds"):
            duration_seconds = int(am["duration_seconds"])

    return {
        # EpisodeListItem fields (camelCase)
        "slug": slug,
        "title": clean_title or title,
        "pubDate": meta.get("pub_date_iso", parsed["dateFromSlug"] or ""),
        "season": meta.get("itunes_season") or parsed["season"],
        "episode": meta.get("itunes_episode") or parsed["episode"],
        "duration": itunes_duration,
        "hasTranscript": has_transcript,
        "canonicalRunId": canonical_run_id,
        "hasGoal": has_goal,
        "reviewCoverage": review_coverage,
        "stats": stats,
        # EpisodeDetail extra fields
        "descriptionHtml": meta.get("description_html", ""),
        "durationSeconds": duration_seconds,
        "imageUrl": meta.get("itunes_image"),
        "allRunIds": all_run_ids,
        # Internal — not written to output, used for file copying
        "_canonicalRunDir": str(
            episode_dir / "transcript" / "runs" / canonical_run_id
        ) if canonical_run_id else None,
        "_chaptersData": chapters_data,
    }


def write_episode_files(ep: dict, output_dir: Path, dry_run: bool) -> dict:
    """Write meta.json, chapters.json, transcript.jsonl for one episode."""
    slug = ep["slug"]
    ep_out = output_dir / "episodes" / slug

    canonical_run_dir = ep.pop("_canonicalRunDir", None)
    ep.pop("_chaptersData", None)

    # meta.json — EpisodeDetail shape (everything except internal fields)
    meta = {k: v for k, v in ep.items() if not k.startswith("_")}

    files_written = {"meta": False, "chapters": False, "transcript": False}

    if dry_run:
        return files_written

    ep_out.mkdir(parents=True, exist_ok=True)

    # Write meta.json
    (ep_out / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, separators=(",", ":"))
    )
    files_written["meta"] = True

    if not canonical_run_dir:
        return files_written

    run_dir = Path(canonical_run_dir)

    # Copy chapters.json as-is (already has camelCase keys from chapter_generator)
    chapters_src = run_dir / "chapters.json"
    if chapters_src.exists():
        shutil.copy2(chapters_src, ep_out / "chapters.json")
        files_written["chapters"] = True

    # Copy transcript_segments.jsonl as-is (already has camelCase keys)
    segments_src = run_dir / "transcript_segments.jsonl"
    if segments_src.exists():
        shutil.copy2(segments_src, ep_out / "transcript.jsonl")
        files_written["transcript"] = True

    return files_written


def main():
    parser = argparse.ArgumentParser(description="Export transcript data for S3 upload")
    parser.add_argument(
        "--downloads", default="./downloads",
        help="Path to downloads directory (default: ./downloads)"
    )
    parser.add_argument(
        "--output", default="./export",
        help="Output directory for S3-ready files (default: ./export)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Scan and report without writing files"
    )
    args = parser.parse_args()

    downloads = Path(args.downloads)
    output_dir = Path(args.output)

    if not downloads.exists():
        print(f"Error: downloads directory not found: {downloads}", file=sys.stderr)
        sys.exit(1)

    # Scan all episode directories
    episode_dirs = sorted(
        d for d in downloads.iterdir()
        if d.is_dir() and d.name.startswith("S") and re.match(r"S\d+E\d+__", d.name)
    )
    print(f"Found {len(episode_dirs)} episode directories")

    episodes = []
    skipped = 0
    for ep_dir in episode_dirs:
        ep = build_episode(ep_dir)
        if ep:
            episodes.append(ep)
        else:
            skipped += 1

    # Sort by pubDate descending
    episodes.sort(key=lambda e: (e.get("pubDate", ""), e.get("episode", 0)), reverse=True)

    print(f"Built {len(episodes)} episodes ({skipped} skipped)")

    with_transcript = sum(1 for e in episodes if e["hasTranscript"])
    with_stats = sum(1 for e in episodes if e["stats"])
    print(f"  With transcripts: {with_transcript}")
    print(f"  With stats: {with_stats}")

    if args.dry_run:
        # Show a sample
        if episodes:
            sample = {k: v for k, v in episodes[0].items() if not k.startswith("_")}
            print(f"\nSample EpisodeDetail ({episodes[0]['slug']}):")
            print(json.dumps(sample, indent=2, ensure_ascii=False)[:1000])
        print(f"\nDry run — no files written. Would create {output_dir}/episodes/")
        return

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "episodes").mkdir(exist_ok=True)

    # Write per-episode files
    total_size = 0
    for i, ep in enumerate(episodes):
        write_episode_files(ep, output_dir, dry_run=False)
        if (i + 1) % 50 == 0:
            print(f"  Exported {i + 1}/{len(episodes)} episodes...")

    # Build index.json — EpisodeListItem[] (no EpisodeDetail extra fields)
    list_item_keys = {
        "slug", "title", "pubDate", "season", "episode", "duration",
        "hasTranscript", "canonicalRunId", "hasGoal", "reviewCoverage", "stats",
    }
    index_items = [
        {k: v for k, v in ep.items() if k in list_item_keys}
        for ep in episodes
    ]
    index_path = output_dir / "episodes" / "index.json"
    index_path.write_text(
        json.dumps(index_items, ensure_ascii=False, separators=(",", ":"))
    )

    # Report sizes
    for root, _dirs, files in os.walk(output_dir):
        for f in files:
            total_size += os.path.getsize(os.path.join(root, f))

    print("\nExport complete:")
    print(f"  Output: {output_dir}")
    print(f"  Episodes: {len(episodes)}")
    print(f"  Total size: {total_size / 1024 / 1024:.1f} MB")
    print(f"  Index: {index_path} ({os.path.getsize(index_path) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
