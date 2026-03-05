#!/usr/bin/env python3
"""
Transcription progress report for Team Deakins podcast episodes.

Walks downloads/*/transcript/runs/ (and legacy transcript/) to classify
each episode and emit a Markdown summary.

Usage:
    python scripts/tools/transcription_report.py
    python scripts/tools/transcription_report.py --downloads ./downloads
    python scripts/tools/transcription_report.py --output documentation/guides/transcription-batch-status.md
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class RunInfo:
    run_id: str
    episode_name: str
    speakers_detected: int
    processing_time_seconds: float
    transcribed_at: str
    success: bool


@dataclass
class EpisodeStatus:
    name: str
    audio_size_bytes: int
    state: str          # "diarized" | "transcribed_no_speakers" | "pending"
    best_run: RunInfo | None = None
    all_runs: list[RunInfo] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_run(run_dir: Path, episode_name: str) -> RunInfo | None:
    report = run_dir / "extraction_report.json"
    if not report.exists():
        return None
    try:
        data = json.loads(report.read_text(encoding="utf-8"))
        if not data.get("success", False):
            return None
        return RunInfo(
            run_id=run_dir.name,
            episode_name=episode_name,
            speakers_detected=int(data.get("speakers_detected", 0)),
            processing_time_seconds=float(data.get("processing_time_seconds", 0.0)),
            transcribed_at=data.get("transcribed_at", ""),
            success=True,
        )
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def _classify_episode(ep_dir: Path) -> EpisodeStatus:
    audio = ep_dir / "audio.mp3"
    audio_size = audio.stat().st_size if audio.exists() else 0
    name = ep_dir.name
    status = EpisodeStatus(name=name, audio_size_bytes=audio_size, state="pending")

    transcript_dir = ep_dir / "transcript"
    if not transcript_dir.is_dir():
        return status

    runs: list[RunInfo] = []

    # Versioned runs layout: transcript/runs/{run_id}/extraction_report.json
    runs_dir = transcript_dir / "runs"
    if runs_dir.is_dir():
        for run_dir in sorted(runs_dir.iterdir()):
            if run_dir.is_dir():
                run = _load_run(run_dir, name)
                if run:
                    runs.append(run)

    # Legacy layout: transcript/extraction_report.json
    if not runs:
        legacy = _load_run(transcript_dir, name)
        if legacy:
            # Represent legacy runs with a synthetic run_id
            legacy.run_id = "legacy"
            runs.append(legacy)

    if not runs:
        return status

    status.all_runs = runs
    # Pick the most recent run (last by sorted run_id; ISO timestamp prefix sorts correctly)
    best = max(runs, key=lambda r: r.transcribed_at)
    status.best_run = best
    status.state = "diarized" if best.speakers_detected > 0 else "transcribed_no_speakers"
    return status


def _progress_bar(done: int, total: int, width: int = 40) -> str:
    if total == 0:
        filled = 0
    else:
        filled = round(done / total * width)
    bar = "#" * filled + "-" * (width - filled)
    pct = round(done / total * 100) if total else 0
    return f"[{bar}] {pct}%  ({done}/{total})"


def _mb(size_bytes: int) -> str:
    return f"{size_bytes / 1_048_576:.1f} MB"


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------

def build_report(downloads_dir: Path) -> str:
    episodes = sorted(
        (d for d in downloads_dir.iterdir() if d.is_dir() and (d / "audio.mp3").exists()),
        key=lambda d: d.name,
    )

    statuses = [_classify_episode(ep) for ep in episodes]

    diarized = [s for s in statuses if s.state == "diarized"]
    no_speakers = [s for s in statuses if s.state == "transcribed_no_speakers"]
    pending = [s for s in statuses if s.state == "pending"]
    total = len(statuses)
    completed = len(diarized) + len(no_speakers)

    # Most recent 10 completed runs (across all episodes, sorted by transcribed_at desc)
    all_runs: list[RunInfo] = []
    for s in statuses:
        all_runs.extend(s.all_runs)
    recent_runs = sorted(all_runs, key=lambda r: r.transcribed_at, reverse=True)[:10]

    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines: list[str] = []

    lines.append(f"<!-- Last generated: {now} -->")
    lines.append("")
    lines.append("# Team Deakins — Transcription Progress")
    lines.append("")
    lines.append(f"_Generated: {now}_")
    lines.append("")

    # Summary block
    lines.append("## Summary")
    lines.append("")
    lines.append(f"| Metric | Count |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total episodes with audio | {total} |")
    lines.append(f"| Diarized (speakers detected) | {len(diarized)} |")
    lines.append(f"| Transcribed (no speakers) | {len(no_speakers)} |")
    lines.append(f"| Pending | {len(pending)} |")
    lines.append("")

    # Progress bar
    lines.append("### Overall completion")
    lines.append("")
    lines.append(f"```")
    lines.append(_progress_bar(completed, total))
    lines.append(f"```")
    lines.append("")

    # Recent completed runs table
    lines.append("## Most Recent Completed Runs (last 10)")
    lines.append("")
    if recent_runs:
        lines.append("| Episode | Run ID | Speakers | Processing Time |")
        lines.append("|---------|--------|----------|----------------|")
        for r in recent_runs:
            pt = f"{r.processing_time_seconds:.0f}s"
            lines.append(f"| {r.episode_name} | `{r.run_id}` | {r.speakers_detected} | {pt} |")
    else:
        lines.append("_No completed runs yet._")
    lines.append("")

    # Pending episodes table (first 10 by name)
    lines.append("## Pending Episodes (first 10)")
    lines.append("")
    pending_sorted = sorted(pending, key=lambda s: s.name)[:10]
    if pending_sorted:
        lines.append("| Episode | Audio Size |")
        lines.append("|---------|-----------|")
        for s in pending_sorted:
            lines.append(f"| {s.name} | {_mb(s.audio_size_bytes)} |")
    else:
        lines.append("_No pending episodes._")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a Markdown transcription progress report.",
    )
    parser.add_argument(
        "--downloads",
        type=Path,
        default=Path("./downloads"),
        help="Path to the downloads directory (default: ./downloads)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write report to this file instead of stdout",
    )
    args = parser.parse_args()

    downloads_dir = args.downloads.expanduser().resolve()
    if not downloads_dir.is_dir():
        print(f"ERROR: downloads directory not found: {downloads_dir}", file=sys.stderr)
        sys.exit(1)

    report = build_report(downloads_dir)

    if args.output:
        out_path = args.output.expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
        print(f"Updated: {out_path}")
    else:
        print(report)


if __name__ == "__main__":
    main()
