#!/usr/bin/env python3
"""
Transcription Pipeline Preflight Check

Validates that all dependencies and prerequisites are met before
running the full transcription pipeline. Run this first to catch
issues early.

Usage:
  python scripts/tools/preflight_check.py [--downloads DIR] [--library DIR]
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


def check(label: str, ok: bool, detail: str = "", fix: str = "") -> bool:
    status = "✓" if ok else "✗"
    print(f"  {status} {label}")
    if detail:
        print(f"     {detail}")
    if fix and not ok:
        print(f"     Fix: {fix}")
    return ok


def warn(label: str, detail: str = "", fix: str = "") -> None:
    print(f"  ⚠  {label}")
    if detail:
        print(f"     {detail}")
    if fix:
        print(f"     Fix: {fix}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Preflight check for transcription pipeline")
    parser.add_argument("--downloads", default="./downloads")
    parser.add_argument("--library", default="./library")
    args = parser.parse_args()

    downloads_dir = Path(args.downloads).resolve()
    library_dir = Path(args.library).resolve()

    print("=" * 60)
    print("Transcription Pipeline Preflight Check")
    print("=" * 60)

    all_ok = True

    # --- Python version ---
    print("\n1. Python Environment")
    py_ver = sys.version_info
    all_ok &= check(
        f"Python {py_ver.major}.{py_ver.minor}.{py_ver.micro}",
        py_ver >= (3, 9),
        fix="Requires Python 3.9+",
    )

    # --- ffmpeg ---
    print("\n2. System Dependencies")
    ffmpeg_path = shutil.which("ffmpeg")
    all_ok &= check(
        "ffmpeg",
        ffmpeg_path is not None,
        detail=f"Found: {ffmpeg_path}" if ffmpeg_path else "Not found on PATH",
        fix="macOS: brew install ffmpeg | Ubuntu: sudo apt install ffmpeg",
    )

    # --- faster-whisper ---
    print("\n3. Python Packages")
    try:
        import faster_whisper
        version = getattr(faster_whisper, "__version__", "unknown")
        check("faster-whisper", True, detail=f"Version: {version}")
    except ImportError:
        all_ok &= check(
            "faster-whisper", False,
            fix="pip install faster-whisper  (or: pip install -r requirements-transcription.txt)",
        )

    # --- torch / GPU ---
    gpu_available = False
    try:
        import torch
        check("torch", True, detail=f"Version: {torch.__version__}")
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            gpu_mem = torch.cuda.get_device_properties(0).total_mem / 1e9
            check("CUDA GPU", True, detail=f"{gpu_name} ({gpu_mem:.1f} GB)")
            gpu_available = True
        else:
            warn(
                "No CUDA GPU detected",
                detail="Will use CPU (slower but works fine)",
                fix="For GPU: install NVIDIA drivers + CUDA toolkit",
            )
    except ImportError:
        warn(
            "torch not installed",
            detail="Will use CPU mode",
            fix="pip install torch (optional, for GPU acceleration)",
        )

    # --- pyannote (optional) ---
    try:
        import pyannote.audio
        version = getattr(pyannote.audio, "__version__", "unknown")
        check("pyannote.audio (diarization)", True, detail=f"Version: {version}")
    except ImportError:
        warn(
            "pyannote.audio not installed",
            detail="Speaker diarization will be unavailable (--diarize flag will be ignored)",
            fix="pip install pyannote.audio (optional)",
        )

    # --- Downloads directory ---
    print("\n4. Data Directories")
    needs_work = 0
    if downloads_dir.exists():
        audio_count = 0
        transcript_count = 0

        for entry in downloads_dir.iterdir():
            if not entry.is_dir():
                continue
            if not (entry / "audio.mp3").exists():
                continue
            audio_count += 1
            if (entry / "transcript" / "transcript.json").exists():
                transcript_count += 1
            else:
                needs_work += 1

        all_ok &= check(
            f"Downloads directory: {downloads_dir}",
            audio_count > 0,
            detail=f"{audio_count} episodes with audio, {transcript_count} transcribed, {needs_work} need work",
            fix="Run download_episodes.py first" if audio_count == 0 else "",
        )
    else:
        all_ok &= check(
            f"Downloads directory: {downloads_dir}",
            False,
            fix="Directory not found. Check --downloads path.",
        )

    # --- Library directory (optional) ---
    if library_dir.exists():
        posts_dir = library_dir / "forums" / "posts"
        if posts_dir.exists():
            post_count = len(list(posts_dir.glob("*.json")))
            check(
                f"Forum corpus: {posts_dir}",
                post_count > 0,
                detail=f"{post_count} posts available for topic cross-referencing",
            )
        else:
            warn(
                "Forum posts not found",
                detail="Topic tagging will use built-in vocabulary only",
                fix="Run forum scraper first for enhanced topic tagging",
            )
    else:
        warn(
            f"Library directory not found: {library_dir}",
            detail="Topic tagging will use built-in vocabulary only",
        )

    # --- Performance estimate ---
    if needs_work > 0:
        print("\n5. Performance Estimate")
        print(f"  {needs_work} episodes to transcribe")
        if gpu_available:
            print(f"     GPU large-v3: ~{needs_work * 0.4:.1f} hours")
            print(f"     GPU medium:   ~{needs_work * 0.25:.1f} hours")
        else:
            print(f"     CPU large-v3: ~{needs_work * 1.5:.1f} hours")
            print(f"     CPU medium:   ~{needs_work * 0.9:.1f} hours")
            print(f"     CPU small:    ~{needs_work * 0.45:.1f} hours")
            if not gpu_available:
                print("  Tip: Start with --model medium for a balance of speed/quality")

    # --- Summary ---
    print("\n" + "=" * 60)
    if all_ok:
        print("✓ All checks passed. Ready to transcribe!")
        print()
        print("Quick start:")
        if needs_work > 0:
            print(f"  python scripts/tools/transcribe_episodes.py --downloads {args.downloads}")
            print()
            print("Or start small:")
            print(f"  python scripts/tools/transcribe_episodes.py --downloads {args.downloads} --batch-size 1 --model medium")
        else:
            print("  All episodes already have transcripts. Use --force to re-transcribe.")
    else:
        print("✗ Some checks failed. Fix the issues above before running the pipeline.")
    print("=" * 60)

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
