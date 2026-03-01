#!/usr/bin/env python3
"""
Transcription Batch Runner

Automation wrapper around transcribe_episodes.py for long background runs.
Adds log rotation, per-episode checkpointing, retry logic, and status queries.

Subcommands
-----------
  test     Process only episodes with existing Apple Podcasts transcripts
           (forces re-transcription to produce structured pipeline output)
  full     Process all episodes without a pipeline transcript (placeholders)
  retry    Re-run episodes that failed in a previous batch
  status   Print current progress without running anything

Usage examples
--------------
  # Dry-run first — see what test would process
  python scripts/tools/run_batch.py test --dry-run

  # Run test against all Apple-transcribed episodes, medium model
  python scripts/tools/run_batch.py test --model medium --verbose

  # Run test on just Edgar Wright
  python scripts/tools/run_batch.py test --episode S02E169__2025-11-26__edgar-wright-director__libsyn_f6853474de

  # Full batch in background (log to analysis/transcription/logs/)
  nohup python scripts/tools/run_batch.py full --model large-v3 >> analysis/transcription/logs/run.log 2>&1 &

  # Check status of the background run
  python scripts/tools/run_batch.py status

  # Retry last batch's failures
  python scripts/tools/run_batch.py retry --model medium
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# Make sibling scripts importable
sys.path.insert(0, str(Path(__file__).parent))

RUNNER_VERSION = "1.0.0"

# Canonical paths (relative to repo root, resolved at runtime)
DOWNLOADS_DIR = Path("downloads")
LIBRARY_DIR = Path("library")
LOGS_DIR = Path("analysis/transcription/logs")
STATUS_FILE = Path("analysis/transcription/status.json")
BATCH_REPORTS_DIR = Path("analysis/transcription/batch_reports")


# ---------------------------------------------------------------------------
# Status tracking
# ---------------------------------------------------------------------------

@dataclass
class RunStatus:
    """Persisted status for monitoring a long-running batch."""
    run_id: str
    mode: str
    started_at: str
    updated_at: str
    model: str
    state: str = "running"          # running | completed | failed | interrupted

    total_queued: int = 0
    total_processed: int = 0
    total_succeeded: int = 0
    total_failed: int = 0
    total_skipped: int = 0

    current_episode: str = ""
    current_episode_started: str = ""

    succeeded: list[str] = field(default_factory=list)
    failed: list[dict[str, str]] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    last_batch_report: str = ""     # path to most recent batch JSON


def load_status(status_file: Path) -> RunStatus | None:
    """Load persisted status from disk."""
    if not status_file.exists():
        return None
    try:
        data = json.loads(status_file.read_text(encoding="utf-8"))
        return RunStatus(**{k: v for k, v in data.items() if k in RunStatus.__dataclass_fields__})
    except Exception:
        return None


def save_status(status: RunStatus, status_file: Path) -> None:
    """Persist status to disk (atomic write via tmp file)."""
    status_file.parent.mkdir(parents=True, exist_ok=True)
    status.updated_at = datetime.now(timezone.utc).isoformat()
    tmp = status_file.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(status), indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(status_file)


# ---------------------------------------------------------------------------
# Episode discovery helpers (extends transcribe_episodes discovery)
# ---------------------------------------------------------------------------

def find_apple_transcribed_episodes(downloads_dir: Path) -> list[str]:
    """
    Return directory names of episodes that have real Apple Podcasts transcripts
    (non-placeholder transcript.txt, no pipeline transcript.json).
    """
    result: list[str] = []
    for entry in sorted(downloads_dir.iterdir()):
        if not entry.is_dir() or not (entry / "audio.mp3").exists():
            continue
        tj = entry / "transcript" / "transcript.json"
        tt = entry / "transcript" / "transcript.txt"
        has_pipeline = tj.exists() and _has_pipeline_version(tj)
        has_apple = tt.exists() and not _is_placeholder(tt)
        if has_apple and not has_pipeline:
            result.append(entry.name)
    return result


def find_unprocessed_episodes(downloads_dir: Path) -> list[str]:
    """
    Return directory names of episodes with audio but no pipeline transcript.
    (Includes placeholder episodes, excludes Apple-only ones unless --force.)
    """
    result: list[str] = []
    for entry in sorted(downloads_dir.iterdir()):
        if not entry.is_dir() or not (entry / "audio.mp3").exists():
            continue
        tj = entry / "transcript" / "transcript.json"
        if not (tj.exists() and _has_pipeline_version(tj)):
            result.append(entry.name)
    return result


def _has_pipeline_version(transcript_json: Path) -> bool:
    try:
        data = json.loads(transcript_json.read_text(encoding="utf-8"))
        return bool(data.get("meta", {}).get("pipeline_version"))
    except Exception:
        return False


def _is_placeholder(transcript_txt: Path) -> bool:
    try:
        return "TRANSCRIPT PLACEHOLDER" in transcript_txt.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return True


# ---------------------------------------------------------------------------
# Batch report loading (for retry mode)
# ---------------------------------------------------------------------------

def find_latest_batch_report(reports_dir: Path) -> Path | None:
    """Find the most recent batch report JSON."""
    if not reports_dir.exists():
        return None
    reports = sorted(reports_dir.glob("batch_*.json"))
    return reports[-1] if reports else None


def load_failed_episodes(batch_report_path: Path) -> list[str]:
    """Extract failed episode directory names from a batch report."""
    try:
        data = json.loads(batch_report_path.read_text(encoding="utf-8"))
        return [f["episode_dir"] for f in data.get("failures", [])]
    except Exception:
        return []


def load_gap_episodes(batch_report_path: Path) -> list[str]:
    """Extract gap (not-yet-transcribed) episode names from a batch report."""
    try:
        data = json.loads(batch_report_path.read_text(encoding="utf-8"))
        return [g["episode_dir"] for g in data.get("gaps", []) if g.get("has_audio")]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def setup_logging(logs_dir: Path, run_id: str, verbose: bool) -> Path:
    """Configure logging to both console and a rotating log file."""
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / f"{run_id}.log"

    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s [%(levelname)s] %(name)s — %(message)s"

    # Root logger: console
    logging.basicConfig(level=level, format=fmt, datefmt="%H:%M:%S", stream=sys.stdout, force=True)

    # File handler (full path, unbuffered via PYTHONUNBUFFERED env)
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)  # always debug to file
    fh.setFormatter(logging.Formatter(fmt, datefmt="%Y-%m-%dT%H:%M:%S"))
    logging.getLogger().addHandler(fh)

    return log_file


# ---------------------------------------------------------------------------
# Core runner
# ---------------------------------------------------------------------------

def run_pipeline_for_episode(
    episode: str,
    model: str,
    library_dir: Path,
    downloads_dir: Path,
    batch_reports_dir: Path,
    force: bool,
    no_topics: bool,
    no_chapters: bool,
    chapter_min: float,
    chapter_target: float,
    chapter_max: float,
    diarize: bool,
    hf_token: str | None,
    dry_run: bool,
    run_id: str,
    cpu_threads: int = 0,
    beam_size: int = 3,
    compression_ratio_threshold: float = 3.5,
) -> tuple[bool, str | None]:
    """
    Run the transcription pipeline for a single episode via subprocess.

    Using subprocess isolation means a crash in one episode (OOM, segfault in
    CTranslate2) cannot corrupt the runner process state.

    Returns: (success, error_message)
    """
    pipeline = Path(__file__).parent / "transcribe_episodes.py"
    python = sys.executable

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = batch_reports_dir / f"batch_{run_id}_{episode[:40]}_{ts}.json"
    batch_reports_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        python, str(pipeline),
        "--downloads", str(downloads_dir),
        "--library", str(library_dir),
        "--model", model,
        "--episode", episode,
        "--report", str(report_path),
        "--verbose",
    ]
    if force:
        cmd.append("--force")
    if no_topics:
        cmd.append("--no-topics")
    if no_chapters:
        cmd.append("--no-chapters")
    if chapter_min != 120:
        cmd.extend(["--chapter-min", str(chapter_min)])
    if chapter_target != 420:
        cmd.extend(["--chapter-target", str(chapter_target)])
    if chapter_max != 1200:
        cmd.extend(["--chapter-max", str(chapter_max)])
    if cpu_threads > 0:
        cmd.extend(["--cpu-threads", str(cpu_threads)])
    if beam_size != 3:
        cmd.extend(["--beam-size", str(beam_size)])
    if compression_ratio_threshold != 3.5:
        cmd.extend(["--compression-ratio-threshold", str(compression_ratio_threshold)])
    if diarize:
        cmd.append("--diarize")
    if hf_token:
        cmd.extend(["--hf-token", hf_token])
    if dry_run:
        cmd.append("--dry-run")

    logger = logging.getLogger("runner")
    logger.info("  cmd: %s", " ".join(str(c) for c in cmd[2:]))  # skip python path

    try:
        # Stream subprocess output live (no capture — goes to our log handlers)
        result = subprocess.run(cmd, check=False)

        if result.returncode == 0:
            return True, None
        else:
            return False, f"Exit code {result.returncode}"

    except KeyboardInterrupt:
        raise  # propagate — outer loop handles shutdown
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def run_batch(
    episodes: list[str],
    mode: str,
    model: str,
    downloads_dir: Path,
    library_dir: Path,
    logs_dir: Path,
    status_file: Path,
    batch_reports_dir: Path,
    force: bool,
    no_topics: bool,
    no_chapters: bool,
    chapter_min: float,
    chapter_target: float,
    chapter_max: float,
    diarize: bool,
    hf_token: str | None,
    dry_run: bool,
    delay_between: float,
    single_episode: str | None,
    cpu_threads: int = 0,
    workers: int = 1,
    beam_size: int = 3,
    compression_ratio_threshold: float = 3.5,
) -> RunStatus:
    """
    Process a list of episodes, checkpointing status after each one.

    When workers > 1, episodes are processed concurrently via a thread pool
    (each thread launches an isolated subprocess). Threads are safe; all shared
    state mutations are protected by a lock.

    Handles KeyboardInterrupt gracefully (saves state then exits).
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_id = f"{mode}_{ts}"
    log_file = setup_logging(logs_dir, run_id, verbose=True)

    # When multiple workers are requested, auto-split the available cores.
    # If the user explicitly set --cpu-threads, honour that; otherwise divide
    # the machine's logical cores evenly among workers.
    if workers > 1 and cpu_threads == 0:
        total_cores = os.cpu_count() or 8
        # With 3+ workers cap at 4 threads each (12 total on 16-core M3 Max),
        # leaving ~4 cores for the OS/compressor and cutting load-avg pressure.
        # With 2 workers keep the higher allocation (8 threads each).
        cpu_threads = max(4, total_cores // workers)
        if workers >= 3:
            cpu_threads = min(cpu_threads, 4)

    logger = logging.getLogger("runner")
    logger.info("=" * 70)
    logger.info("Batch Runner v%s — mode=%s, run_id=%s", RUNNER_VERSION, mode, run_id)
    logger.info("Log file: %s", log_file)
    logger.info(
        "Model: %s | Episodes queued: %d | Workers: %d | CPU threads/worker: %s",
        model, len(episodes), workers, cpu_threads or "auto",
    )
    logger.info("=" * 70)

    status = RunStatus(
        run_id=run_id,
        mode=mode,
        started_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
        model=model,
        total_queued=len(episodes),
    )
    save_status(status, status_file)

    if dry_run:
        logger.info("[DRY RUN] Would process %d episodes:", len(episodes))
        for ep in episodes:
            logger.info("  - %s", ep)
        status.state = "completed"
        status.total_skipped = len(episodes)
        save_status(status, status_file)
        return status

    # Common kwargs for every run_pipeline_for_episode call
    _ep_kwargs: dict = dict(
        model=model,
        library_dir=library_dir,
        downloads_dir=downloads_dir,
        batch_reports_dir=batch_reports_dir,
        force=force,
        no_topics=no_topics,
        no_chapters=no_chapters,
        chapter_min=chapter_min,
        chapter_target=chapter_target,
        chapter_max=chapter_max,
        diarize=diarize,
        hf_token=hf_token,
        dry_run=False,
        run_id=run_id,
        cpu_threads=cpu_threads,
        beam_size=beam_size,
        compression_ratio_threshold=compression_ratio_threshold,
    )

    state_lock = threading.Lock()
    total = len(episodes)

    def _process_one(indexed_episode: tuple[int, str]) -> None:
        """Worker function: process one episode and update shared status."""
        i, episode = indexed_episode
        logger.info("")
        logger.info("━" * 70)
        logger.info("[%d/%d] %s", i, total, episode)
        logger.info("━" * 70)

        with state_lock:
            status.current_episode = episode
            status.current_episode_started = datetime.now(timezone.utc).isoformat()
            save_status(status, status_file)

        ep_start = time.monotonic()
        success, error = run_pipeline_for_episode(episode=episode, **_ep_kwargs)
        elapsed = time.monotonic() - ep_start

        with state_lock:
            status.total_processed += 1
            if success:
                status.total_succeeded += 1
                status.succeeded.append(episode)
                logger.info("✓ %s — done in %.0fs", episode, elapsed)
            else:
                status.total_failed += 1
                status.failed.append({"episode": episode, "error": error or "unknown"})
                logger.error("✗ %s — FAILED: %s (%.0fs)", episode, error, elapsed)
            save_status(status, status_file)

    indexed = list(enumerate(episodes, 1))

    if workers <= 1:
        # Sequential path — preserves KeyboardInterrupt behaviour
        for item in indexed:
            try:
                _process_one(item)
            except KeyboardInterrupt:
                logger.warning("Interrupted — saving state")
                status.state = "interrupted"
                status.current_episode = ""
                save_status(status, status_file)
                _print_run_summary(status, logger)
                return status

            if delay_between > 0 and item[0] < total:
                logger.debug("Sleeping %.1fs between episodes...", delay_between)
                time.sleep(delay_between)
    else:
        # Parallel path — N episodes run concurrently as isolated subprocesses
        logger.info("Running %d episodes with %d parallel workers", total, workers)
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
                futs = {pool.submit(_process_one, item): item[1] for item in indexed}
                for fut in concurrent.futures.as_completed(futs):
                    try:
                        fut.result()
                    except Exception as exc:
                        ep = futs[fut]
                        logger.error("Unhandled exception for %s: %s", ep, exc)
                        with state_lock:
                            status.total_failed += 1
                            status.failed.append({"episode": ep, "error": str(exc)})
                            save_status(status, status_file)
        except KeyboardInterrupt:
            logger.warning("Interrupted — saving state")
            status.state = "interrupted"
            status.current_episode = ""
            save_status(status, status_file)
            _print_run_summary(status, logger)
            return status

    status.state = "completed"
    status.current_episode = ""
    save_status(status, status_file)

    _print_run_summary(status, logger)
    return status


def _print_run_summary(status: RunStatus, logger: logging.Logger) -> None:
    logger.info("")
    logger.info("=" * 70)
    logger.info("RUN COMPLETE — %s", status.run_id)
    logger.info("=" * 70)
    logger.info("  State:      %s", status.state)
    logger.info("  Queued:     %d", status.total_queued)
    logger.info("  Processed:  %d", status.total_processed)
    logger.info("  Succeeded:  %d", status.total_succeeded)
    logger.info("  Failed:     %d", status.total_failed)
    logger.info("  Skipped:    %d", status.total_skipped)

    if status.failed:
        logger.error("")
        logger.error("FAILURES (%d):", len(status.failed))
        for f in status.failed:
            logger.error("  ✗ %(episode)s — %(error)s", f)

    logger.info("")
    logger.info("Status file: %s", STATUS_FILE)
    logger.info("  Retry failed episodes with:")
    logger.info("    python scripts/tools/run_batch.py retry")
    logger.info("  Or target a specific episode:")
    logger.info("    python scripts/tools/run_batch.py full --episode <name>")


# ---------------------------------------------------------------------------
# Status subcommand
# ---------------------------------------------------------------------------

def cmd_status(status_file: Path, downloads_dir: Path, batch_reports_dir: Path) -> None:
    """Print current run status and overall collection state."""
    print("=" * 70)
    print("Transcription Collection Status")
    print("=" * 70)

    # Overall collection state
    total = 0
    pipeline_done = 0
    apple_only = 0
    placeholders = 0
    no_audio = 0

    if downloads_dir.exists():
        for entry in sorted(downloads_dir.iterdir()):
            if not entry.is_dir():
                continue
            total += 1
            audio = entry / "audio.mp3"
            tj = entry / "transcript" / "transcript.json"
            tt = entry / "transcript" / "transcript.txt"

            if not audio.exists():
                no_audio += 1
            elif tj.exists() and _has_pipeline_version(tj):
                pipeline_done += 1
            elif tt.exists() and not _is_placeholder(tt):
                apple_only += 1
            else:
                placeholders += 1

    print(f"\nCollection ({downloads_dir}):")
    print(f"  Total episode dirs:          {total}")
    print(f"  ✓ Pipeline transcripts:       {pipeline_done}")
    print(f"  ⚠  Apple-only (no timestamps): {apple_only}")
    print(f"  ○ Placeholder (not done yet): {placeholders}")
    if no_audio:
        print(f"  ✗ No audio file:              {no_audio}")
    print(f"  Remaining to transcribe:      {total - pipeline_done}")

    # Current/last run status
    status = load_status(status_file)
    if status:
        print(f"\nLast Run ({status.run_id}):")
        print(f"  State:      {status.state}")
        print(f"  Mode:       {status.mode}")
        print(f"  Model:      {status.model}")
        print(f"  Started:    {status.started_at[:19]}")
        print(f"  Updated:    {status.updated_at[:19]}")
        print(f"  Progress:   {status.total_processed}/{status.total_queued} ({status.total_succeeded} ✓, {status.total_failed} ✗)")
        if status.current_episode:
            print(f"  In progress: {status.current_episode}")
        if status.failed:
            print(f"\n  Failed ({len(status.failed)}):")
            for f in status.failed[:20]:
                print(f"    ✗ {f['episode']} — {f['error']}")
            if len(status.failed) > 20:
                print(f"    ... and {len(status.failed) - 20} more")
    else:
        print("\nNo previous run found.")

    # Latest batch report
    latest = find_latest_batch_report(batch_reports_dir)
    if latest:
        print(f"\nLatest batch report: {latest.name}")
        gaps = load_gap_episodes(latest)
        failures = load_failed_episodes(latest)
        if gaps:
            print(f"  Gaps in last batch: {len(gaps)} episodes not yet transcribed")
        if failures:
            print(f"  Failures in last batch: {len(failures)}")

    print("=" * 70)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="run_batch.py",
        description="Batch runner for the Team Deakins transcription pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  test    Re-transcribe the 13 episodes that have Apple Podcasts transcripts.
          Forces pipeline output (structured JSON with timestamps) to replace
          the plain-text Apple transcripts. Good for validating the pipeline.

  full    Transcribe all 331 placeholder episodes (those without any real
          transcript yet). Skips episodes already done. Resumable — run again
          after interruption to pick up where you left off.

  retry   Re-run episodes that failed in the most recent batch run.

  status  Show collection state and last run progress without running anything.

Background execution:
  nohup python scripts/tools/run_batch.py full --model large-v3 &
  python scripts/tools/run_batch.py status     # check progress
  tail -f analysis/transcription/logs/*.log    # stream logs live

Recovery after interruption:
  The pipeline is naturally resumable — episodes with pipeline transcripts
  are automatically skipped. Simply re-run the same command to continue.
  Use 'retry' to specifically re-run known failures.
        """,
    )

    sub = p.add_subparsers(dest="mode", required=True)

    # Shared options
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--downloads", default="./downloads")
    shared.add_argument("--library", default="./library")
    shared.add_argument(
        "--model", default="large-v3",
        choices=["tiny", "tiny.en", "base", "base.en", "small", "small.en",
                 "medium", "medium.en", "large-v1", "large-v2", "large-v3",
                 "distil-large-v3", "distil-medium.en", "distil-small.en"],
        help="Whisper model (default: large-v3 — best quality, ~2-4 min/episode on M3 Max)",
    )
    shared.add_argument("--episode", default=None, help="Process only this one episode dir name")
    shared.add_argument("--no-topics", action="store_true")
    shared.add_argument("--no-chapters", action="store_true")
    shared.add_argument("--chapter-min", type=float, default=120)
    shared.add_argument("--chapter-target", type=float, default=420)
    shared.add_argument("--chapter-max", type=float, default=1200)
    shared.add_argument("--diarize", action="store_true")
    shared.add_argument("--hf-token", default=None)
    shared.add_argument("--cpu-threads", type=int, default=0,
                        help="CTranslate2 threads per worker (0=auto; halved automatically with --workers 2)")
    shared.add_argument("--workers", type=int, default=1,
                        help="Parallel episode workers (default 1). "
                             "2 workers on M3 Max ≈ 2× throughput. "
                             "Each worker gets cpu_count//workers threads automatically.")
    shared.add_argument("--beam-size", type=int, default=3,
                        help="Whisper beam size (1=fastest, 3=default, 5=best quality)")
    shared.add_argument("--compression-ratio-threshold", type=float, default=3.5,
                        help="Suppress temperature retries above this ratio (default 3.5 for podcasts)")
    shared.add_argument("--delay", type=float, default=0.0, help="Seconds to wait between episodes (sequential only)")
    shared.add_argument("--dry-run", action="store_true")
    shared.add_argument("--verbose", action="store_true")

    sub.add_parser("test", parents=[shared], help="Re-transcribe the 13 Apple-only episodes")
    sub.add_parser("full", parents=[shared], help="Transcribe all placeholder episodes")
    sub.add_parser("retry", parents=[shared], help="Re-run failures from last batch")
    status_p = sub.add_parser("status", help="Show collection state without running anything")
    status_p.add_argument("--downloads", default="./downloads")

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    downloads_dir = Path(args.downloads).resolve()
    logs_dir = LOGS_DIR
    status_file = STATUS_FILE
    batch_reports_dir = BATCH_REPORTS_DIR

    # Status command — no-op beyond printing
    if args.mode == "status":
        cmd_status(status_file, downloads_dir, batch_reports_dir)
        return

    library_dir = Path(args.library).resolve()

    # Pre-flight checks
    if not shutil.which("ffmpeg"):
        print("ERROR: ffmpeg not found on PATH.", file=sys.stderr)
        print("  macOS:  brew install ffmpeg", file=sys.stderr)
        print("  Ubuntu: sudo apt install ffmpeg", file=sys.stderr)
        sys.exit(1)

    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        print("ERROR: faster-whisper not installed.", file=sys.stderr)
        print("  pip install -r requirements-transcription.txt", file=sys.stderr)
        sys.exit(1)

    # Build episode queue based on mode
    if args.mode == "test":
        episodes = find_apple_transcribed_episodes(downloads_dir)
        if not episodes:
            print("No Apple-transcribed episodes found. Nothing to test against.")
            sys.exit(0)
        force = True  # must force — Apple transcripts count as "existing"
        print(f"Test mode: {len(episodes)} Apple-transcribed episodes queued for re-transcription")

    elif args.mode == "full":
        episodes = find_unprocessed_episodes(downloads_dir)
        force = False
        print(f"Full mode: {len(episodes)} episodes without pipeline transcripts")

    elif args.mode == "retry":
        latest = find_latest_batch_report(batch_reports_dir)
        if not latest:
            # Fall back to status file
            status = load_status(status_file)
            if status and status.failed:
                episodes = [f["episode"] for f in status.failed]
            else:
                print("No previous batch report found and no failures in status file.")
                print("Run 'test' or 'full' first.")
                sys.exit(0)
        else:
            episodes = load_failed_episodes(latest)
            if not episodes:
                print(f"No failures in last batch report ({latest.name}). Nothing to retry.")
                sys.exit(0)
        force = True  # retries force re-run even if partial output exists
        print(f"Retry mode: {len(episodes)} episodes from previous failures")

    else:
        print(f"Unknown mode: {args.mode}", file=sys.stderr)
        sys.exit(1)

    if not episodes:
        print("Nothing to process.")
        sys.exit(0)

    if args.episode:
        if args.episode not in episodes:
            print(f"Warning: --episode '{args.episode}' not in the {args.mode} queue.")
            print(f"  Available: {episodes[:5]}{'...' if len(episodes) > 5 else ''}")
        episodes = [e for e in episodes if e == args.episode] or [args.episode]
        print(f"Filtered to single episode: {args.episode}")

    # Run
    status = run_batch(
        episodes=episodes,
        mode=args.mode,
        model=args.model,
        downloads_dir=downloads_dir,
        library_dir=library_dir,
        logs_dir=logs_dir,
        status_file=status_file,
        batch_reports_dir=batch_reports_dir,
        force=force,
        no_topics=args.no_topics,
        no_chapters=args.no_chapters,
        chapter_min=args.chapter_min,
        chapter_target=args.chapter_target,
        chapter_max=args.chapter_max,
        diarize=args.diarize,
        hf_token=args.hf_token,
        dry_run=args.dry_run,
        delay_between=args.delay,
        single_episode=None,  # already filtered above
        cpu_threads=args.cpu_threads,
        workers=args.workers,
        beam_size=args.beam_size,
        compression_ratio_threshold=args.compression_ratio_threshold,
    )

    # Exit code reflects overall success
    sys.exit(0 if status.total_failed == 0 else 1)


if __name__ == "__main__":
    main()
