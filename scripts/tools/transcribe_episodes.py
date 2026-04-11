#!/usr/bin/env python3
"""
Team Deakins Podcast Transcription Pipeline

Extracts timecoded, topic-tagged transcripts from locally downloaded
podcast episodes using faster-whisper. Integrates with the Purefoy
knowledge base for cross-referencing against forum discussions.

Design goals:
  - Fail-safe: errors in one episode never block the next
  - Resumable: skips already-transcribed episodes
  - Observable: clear progress, gap reporting, structured logs
  - Structured: timecoded segments, word timestamps, topic tags

Usage:
  python scripts/tools/transcribe_episodes.py [OPTIONS]

Options:
  --downloads DIR      Path to downloads directory (default: ./downloads)
  --library DIR        Path to library directory for forum cross-ref (default: ./library)
  --model MODEL        Whisper model size (default: large-v3)
  --device DEVICE      Compute device: auto, cpu, cuda (default: auto)
  --compute-type TYPE  Quantization: float16, int8, int8_float16 (default: auto)
  --language LANG      Force language (default: auto-detect)
  --diarize            Enable speaker diarization (requires pyannote.audio)
  --hf-token TOKEN     HuggingFace token for diarization models
  --min-speakers N     Minimum speakers for diarization (default: 2)
  --max-speakers N     Maximum speakers for diarization (default: 4)
  --no-topics          Disable topic tagging
  --no-chapters        Disable smart chapter generation
  --chapter-min N      Minimum chapter length in seconds (default: 120)
  --chapter-target N   Target chapter length in seconds (default: 420)
  --chapter-max N      Maximum chapter length in seconds (default: 1200)
  --force              Re-transcribe even if transcript exists
  --episode DIRNAME    Process only this episode directory name
  --dry-run            Show what would be processed without doing it
  --batch-size N       Max episodes to process in one run (default: unlimited)
  --report FILE        Write batch report to this file
  --verbose            Verbose logging

Requirements:
  pip install faster-whisper
  System: ffmpeg must be installed

Optional:
  pip install pyannote.audio  # for --diarize
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import platform
import shutil
import signal
import sys
import time
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

# Make sibling scripts importable when run as a script
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("transcribe")

PIPELINE_VERSION = "2.0.0"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class EpisodeInfo:
    """Metadata about a discovered episode."""
    dir_name: str
    dir_path: Path
    audio_path: Path
    metadata_path: Path | None
    has_existing_transcript: bool
    existing_transcript_type: str | None  # "pipeline", "apple", "placeholder", None

    title: str | None = None
    guid: str | None = None
    season: int | None = None
    episode: int | None = None
    pub_date: str | None = None
    duration_hint: float | None = None


@dataclass
class SegmentResult:
    """A single transcription segment with all annotations."""
    id: int
    start: float
    end: float
    text: str
    speaker: str | None = None
    segment_type: Literal["intro", "outro", "content"] = "content"
    chapter_id: int | None = None
    confidence: float = 0.0
    words: list[dict[str, Any]] = field(default_factory=list)
    topics: list[dict[str, Any]] = field(default_factory=list)
    films: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class TranscriptionResult:
    """Complete transcription output for one episode."""
    success: bool
    episode_dir: str
    error: str | None = None
    error_traceback: str | None = None
    duration_seconds: float = 0.0
    processing_time_seconds: float = 0.0

    language: str | None = None
    language_probability: float | None = None
    segment_count: int = 0
    word_count: int = 0
    total_audio_duration: float = 0.0
    speakers_detected: int = 0
    topics_tagged: int = 0
    films_mentioned: int = 0
    chapters_generated: int = 0


@dataclass
class BatchReport:
    """Report for an entire transcription run."""
    started_at: str
    finished_at: str | None = None
    pipeline_version: str = PIPELINE_VERSION
    whisper_model: str = ""
    device: str = ""
    compute_type: str = ""
    diarization_enabled: bool = False
    topic_tagging_enabled: bool = True

    total_discovered: int = 0
    total_processed: int = 0
    total_succeeded: int = 0
    total_failed: int = 0
    total_skipped: int = 0
    total_processing_time: float = 0.0

    results: list[dict[str, Any]] = field(default_factory=list)
    failures: list[dict[str, Any]] = field(default_factory=list)
    gaps: list[dict[str, Any]] = field(default_factory=list)

    system_info: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Graceful shutdown
# ---------------------------------------------------------------------------

_shutdown_requested = False


def _handle_signal(signum: int, frame: Any) -> None:
    global _shutdown_requested
    if _shutdown_requested:
        logger.warning("Second interrupt — forcing exit")
        sys.exit(130)
    _shutdown_requested = True
    logger.warning("Shutdown requested — finishing current episode then saving report...")


signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def format_duration(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h}:{m:02d}:{s:02d}" if h > 0 else f"{m}:{s:02d}"


# ---------------------------------------------------------------------------
# Progress reporting (observability for remote polling)
# ---------------------------------------------------------------------------

STAGE_NAMES = [
    "model_loading",
    "transcription",
    "intro_outro_tagging",
    "topic_tagging",
    "diarization",
    "speaker_embedding",
    "chapter_generation",
    "write_outputs",
]


class ProgressReporter:
    """Writes structured progress to a JSON file for remote monitoring.

    The local aws_runner polls this file via SSH to track stage transitions,
    detect stalls, and collect GPU/system metrics — replacing blind PID-alive
    polling with real observability.
    """

    def __init__(self, progress_path: Path, episode_name: str) -> None:
        self._path = progress_path
        self._episode = episode_name
        self._started_at = now_iso()
        self._stage: str | None = None
        self._stage_started: float = 0.0
        self._stage_timings: dict[str, float] = {}
        self._stages_completed: list[str] = []
        self._gpu_cache: tuple[float, dict[str, Any]] = (0.0, {})
        self._enabled = True

    def report_stage(self, stage: str, detail: str | None = None) -> None:
        """Record a stage transition and write progress file."""
        now = time.monotonic()
        if self._stage is not None:
            self._stage_timings[self._stage] = round(now - self._stage_started, 1)
            self._stages_completed.append(self._stage)
        self._stage = stage
        self._stage_started = now
        self._write(detail=detail)

    def heartbeat(self, detail: str | None = None) -> None:
        """Update progress within a stage (e.g. segment count)."""
        self._write(detail=detail)

    def finish(self, error: str | None = None) -> None:
        """Mark processing as done (success or failure)."""
        now = time.monotonic()
        if self._stage is not None:
            self._stage_timings[self._stage] = round(now - self._stage_started, 1)
            self._stages_completed.append(self._stage)
        self._write(done=True, error=error)

    def _collect_gpu_metrics(self) -> dict[str, Any]:
        """Collect GPU metrics via nvidia-smi, cached for 5 seconds."""
        now = time.monotonic()
        if now - self._gpu_cache[0] < 5.0:
            return self._gpu_cache[1]
        try:
            import subprocess as _sp
            out = _sp.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            )
            if out.returncode == 0:
                parts = out.stdout.strip().split(", ")
                if len(parts) == 3:
                    metrics = {
                        "utilization_pct": int(parts[0]),
                        "memory_used_mb": int(parts[1]),
                        "memory_total_mb": int(parts[2]),
                    }
                    self._gpu_cache = (now, metrics)
                    return metrics
        except Exception:
            pass
        return self._gpu_cache[1]

    def _write(self, detail: str | None = None, done: bool = False, error: str | None = None) -> None:
        """Atomically write progress JSON (tmp + rename)."""
        if not self._enabled:
            return
        try:
            stage_index = STAGE_NAMES.index(self._stage) + 1 if self._stage in STAGE_NAMES else 0
            data = {
                "version": 1,
                "episode": self._episode,
                "pid": os.getpid(),
                "started_at": self._started_at,
                "updated_at": now_iso(),
                "stage": self._stage,
                "stage_index": stage_index,
                "stage_count": len(STAGE_NAMES),
                "stages_completed": list(self._stages_completed),
                "stage_started_at": datetime.fromtimestamp(
                    time.time() - (time.monotonic() - self._stage_started),
                    tz=timezone.utc,
                ).isoformat() if self._stage else None,
                "stage_timings": dict(self._stage_timings),
                "gpu": self._collect_gpu_metrics(),
                "detail": detail,
                "error": error,
                "done": done,
            }
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
            tmp.replace(self._path)
        except Exception as e:
            logger.debug("Failed to write progress file: %s", e)
            self._enabled = False


class _NoOpReporter:
    """Stub reporter when --progress-file is not set."""
    def report_stage(self, stage: str, detail: str | None = None) -> None: pass
    def heartbeat(self, detail: str | None = None) -> None: pass
    def finish(self, error: str | None = None) -> None: pass


def format_timestamp_srt(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def get_system_info() -> dict[str, Any]:
    info: dict[str, Any] = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "machine": platform.machine(),
    }
    try:
        import torch
        info["torch_version"] = torch.__version__
        info["cuda_available"] = torch.cuda.is_available()
        if torch.cuda.is_available():
            info["cuda_device"] = torch.cuda.get_device_name(0)
            props = torch.cuda.get_device_properties(0)
            mem = getattr(props, "total_memory", None) or getattr(props, "total_mem", 0)
            info["cuda_memory_gb"] = round(mem / 1e9, 1)
    except ImportError:
        info["torch_version"] = None
        info["cuda_available"] = False
    info["ffmpeg_available"] = shutil.which("ffmpeg") is not None
    return info


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def discover_episodes(
    downloads_dir: Path, force: bool = False, single: str | None = None,
) -> list[EpisodeInfo]:
    """
    Scan downloads directory for episodes that need transcription.

    An episode needs transcription if:
    1. It has audio.mp3
    2. It has no transcript.json, OR transcript.json is a placeholder, OR --force
    """
    episodes: list[EpisodeInfo] = []

    if not downloads_dir.exists():
        logger.error("Downloads directory does not exist: %s", downloads_dir)
        return episodes

    for entry in sorted(downloads_dir.iterdir()):
        if not entry.is_dir():
            continue
        if single and entry.name != single:
            continue

        audio_path = entry / "audio.mp3"
        if not audio_path.exists():
            continue

        metadata_path = entry / "metadata.json"
        transcript_json = entry / "transcript" / "transcript.json"
        transcript_txt = entry / "transcript" / "transcript.txt"

        has_existing = False
        existing_type: str | None = None

        if transcript_json.exists():
            try:
                data = json.loads(transcript_json.read_text(encoding="utf-8"))
                if data.get("meta", {}).get("pipeline_version"):
                    has_existing = True
                    existing_type = "pipeline"
            except Exception:
                pass

        if not has_existing:
            runs_dir = entry / "transcript" / "runs"
            if runs_dir.exists() and any(
                r.is_dir() and (r / "transcript.json").exists()
                for r in runs_dir.iterdir()
            ):
                has_existing = True
                existing_type = "pipeline"

        if not has_existing and transcript_txt.exists():
            txt = transcript_txt.read_text(encoding="utf-8", errors="replace")
            if "TRANSCRIPT PLACEHOLDER" in txt:
                existing_type = "placeholder"
            elif len(txt.strip()) > 100:
                has_existing = True
                existing_type = "apple"

        ep = EpisodeInfo(
            dir_name=entry.name,
            dir_path=entry,
            audio_path=audio_path,
            metadata_path=metadata_path if metadata_path.exists() else None,
            has_existing_transcript=has_existing,
            existing_transcript_type=existing_type,
        )

        if metadata_path.exists():
            try:
                meta = json.loads(metadata_path.read_text(encoding="utf-8"))
                ep.title = meta.get("title")
                ep.guid = meta.get("guid")
                ep.season = meta.get("itunes_season")
                ep.episode = meta.get("itunes_episode")
                ep.pub_date = meta.get("pub_date_iso")
                am = meta.get("audio_metadata") or {}
                ep.duration_hint = am.get("duration_seconds")
                if not ep.duration_hint:
                    dur_str = meta.get("itunes_duration")
                    if dur_str and ":" in str(dur_str):
                        parts = str(dur_str).split(":")
                        try:
                            if len(parts) == 3:
                                ep.duration_hint = int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
                            elif len(parts) == 2:
                                ep.duration_hint = int(parts[0]) * 60 + float(parts[1])
                        except ValueError:
                            pass
                    elif dur_str:
                        try:
                            ep.duration_hint = float(dur_str)
                        except ValueError:
                            pass
            except Exception as e:
                logger.debug("Error reading metadata for %s: %s", entry.name, e)

        if has_existing and not force:
            continue

        episodes.append(ep)

    return episodes


def discover_all_episodes(downloads_dir: Path) -> list[EpisodeInfo]:
    """Discover ALL episodes including already-transcribed ones (for gap reporting)."""
    episodes: list[EpisodeInfo] = []
    if not downloads_dir.exists():
        return episodes

    for entry in sorted(downloads_dir.iterdir()):
        if not entry.is_dir():
            continue

        audio_path = entry / "audio.mp3"
        metadata_path = entry / "metadata.json"
        transcript_json = entry / "transcript" / "transcript.json"
        transcript_txt = entry / "transcript" / "transcript.txt"

        has_transcript = False
        transcript_type: str | None = None

        if transcript_json.exists():
            try:
                data = json.loads(transcript_json.read_text(encoding="utf-8"))
                if data.get("meta", {}).get("pipeline_version"):
                    has_transcript = True
                    transcript_type = "pipeline"
            except Exception:
                pass

        if not has_transcript and transcript_txt.exists():
            txt = transcript_txt.read_text(encoding="utf-8", errors="replace")
            if "TRANSCRIPT PLACEHOLDER" not in txt and len(txt.strip()) > 100:
                has_transcript = True
                transcript_type = "apple"

        ep = EpisodeInfo(
            dir_name=entry.name,
            dir_path=entry,
            audio_path=audio_path,
            metadata_path=metadata_path if metadata_path.exists() else None,
            has_existing_transcript=has_transcript,
            existing_transcript_type=transcript_type,
        )

        if metadata_path.exists():
            try:
                meta = json.loads(metadata_path.read_text(encoding="utf-8"))
                ep.title = meta.get("title")
                ep.guid = meta.get("guid")
                ep.season = meta.get("itunes_season")
                ep.episode = meta.get("itunes_episode")
                ep.pub_date = meta.get("pub_date_iso")
            except Exception:
                pass

        episodes.append(ep)

    return episodes


# ---------------------------------------------------------------------------
# Transcription Engine
# ---------------------------------------------------------------------------

class TranscriptionEngine:
    """
    Wraps faster-whisper and optional diarization into a single interface.

    Handles model loading (once, reused across episodes), transcription with
    word timestamps, VAD filtering, optional speaker diarization, and
    hallucination detection.
    """

    def __init__(
        self,
        model_size: str = "large-v3",
        device: str = "auto",
        compute_type: str = "auto",
        language: str | None = None,
        diarize: bool = False,
        hf_token: str | None = None,
        min_speakers: int = 2,
        max_speakers: int = 4,
        cpu_threads: int = 0,
        beam_size: int = 3,
        compression_ratio_threshold: float = 3.5,
        strict_diarize: bool = False,
    ):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self.diarize = diarize
        self.hf_token = hf_token
        self.min_speakers = min_speakers
        self.max_speakers = max_speakers
        self.cpu_threads = cpu_threads  # 0 = CTranslate2 auto (uses all cores)
        self.beam_size = beam_size
        self.strict_diarize = strict_diarize
        # Podcast audio naturally runs 3.0–3.8 due to conversational repetition.
        # Whisper default of 2.4 triggers ~5 temperature retries per flagged segment
        # which can add 3-5 min per problematic passage.
        self.compression_ratio_threshold = compression_ratio_threshold
        self._model: Any = None
        self._diarization_pipeline: Any = None

    def load_model(self) -> None:
        """Load the whisper model. Call once before processing episodes."""
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise ImportError(
                "faster-whisper is required. Install with:\n"
                "  pip install faster-whisper\n"
                "System dependency: ffmpeg must be installed."
            )

        device = self.device
        compute_type = self.compute_type

        if device == "auto":
            # Prefer CUDA if torch+CUDA is available; otherwise CPU.
            # On Apple Silicon, CTranslate2 uses the Accelerate framework in
            # CPU mode which is highly optimised (ANE/BLAS) — no Metal needed.
            cuda_available = False
            try:
                import torch
                cuda_available = torch.cuda.is_available()
            except ImportError:
                pass
            device = "cuda" if cuda_available else "cpu"

        if compute_type == "auto":
            if device == "cuda":
                compute_type = "float16"
            else:
                # int8 is fastest on Apple Silicon (Accelerate BLAS) and
                # conventional x86 CPUs. Quality difference vs float32 is
                # negligible with large-v3.
                compute_type = "int8"

        self.device = device
        self.compute_type = compute_type

        # Log Apple Silicon detection for visibility
        machine = platform.machine()
        if machine == "arm64" and device == "cpu":
            logger.info(
                "Apple Silicon detected (%s) — using Accelerate-accelerated CPU mode",
                platform.processor() or machine,
            )

        logger.info("Loading whisper model: %s (device=%s, compute_type=%s, cpu_threads=%s)",
                    self.model_size, device, compute_type, self.cpu_threads or "auto")

        self._model = WhisperModel(
            self.model_size,
            device=device,
            compute_type=compute_type,
            cpu_threads=self.cpu_threads,
        )
        logger.info("Whisper model loaded successfully")

        if self.diarize:
            self._load_diarization()

    def _load_diarization(self) -> None:
        try:
            # torchaudio ≥2.6 removed list_audio_backends(); pyannote.audio calls it on import.
            # Patched against: torchaudio==2.10.0+cu128 (DLAMI), pyannote.audio==4.0.4.
            # TODO: remove once pyannote drops the call (track: pyannote-audio issue #1724).
            import torchaudio as _ta
            if not hasattr(_ta, "list_audio_backends"):
                _ta.list_audio_backends = lambda: ["soundfile", "sox_io"]
            # speechbrain 1.0.3 uses hf_hub_download(use_auth_token=) which was renamed to
            # token= in huggingface_hub ≥0.21. Patch it globally so both pyannote and
            # speechbrain work without changing their source.
            # Patched against: speechbrain==1.0.3, huggingface_hub==0.29.x (DLAMI).
            import huggingface_hub as _hfhub
            _orig_hf_dl = _hfhub.hf_hub_download
            def _patched_hf_dl(*args: Any, **kw: Any) -> Any:
                if "use_auth_token" in kw:
                    kw["token"] = kw.pop("use_auth_token")
                return _orig_hf_dl(*args, **kw)
            _hfhub.hf_hub_download = _patched_hf_dl
            from pyannote.audio import Pipeline as PyannotePipeline
        except ImportError:
            if self.strict_diarize:
                raise RuntimeError(
                    "pyannote.audio not installed and --strict-diarize is set. "
                    "Install with: pip install pyannote.audio"
                )
            logger.warning(
                "pyannote.audio not installed — diarization disabled.\n"
                "Install with: pip install pyannote.audio"
            )
            self.diarize = False
            return

        if not self.hf_token:
            self.hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")

        if not self.hf_token:
            logger.warning(
                "No HuggingFace token — diarization disabled.\n"
                "Provide with --hf-token or set HF_TOKEN environment variable."
            )
            self.diarize = False
            return

        try:
            import torch as _torch_dz
            logger.info("Loading speaker diarization model...")
            self._diarization_pipeline = PyannotePipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                token=self.hf_token,
            )
            # Move to GPU if available — reduces per-episode time from ~30 min to ~4 min
            if _torch_dz.cuda.is_available():
                self._diarization_pipeline.to(_torch_dz.device("cuda"))
                logger.info("Diarization model loaded and moved to CUDA")
            else:
                logger.info("Diarization model loaded (CPU)")
        except Exception as e:
            if self.strict_diarize:
                raise RuntimeError(
                    f"Diarization model failed to load and --strict-diarize is set: {e}"
                ) from e
            logger.warning("Failed to load diarization model: %s — continuing without", e)
            self.diarize = False

    def transcribe(
        self,
        audio_path: Path,
        embeddings_dir: Path | None = None,
        progress_reporter: ProgressReporter | _NoOpReporter | None = None,
    ) -> tuple[list[SegmentResult], dict[str, Any]]:
        """Transcribe an audio file. Returns (segments, info_dict)."""
        reporter = progress_reporter or _NoOpReporter()
        if self._model is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        logger.info("Transcribing: %s", audio_path.name)

        transcribe_kwargs: dict[str, Any] = {
            "word_timestamps": True,
            "vad_filter": True,
            "vad_parameters": {"min_silence_duration_ms": 800, "speech_pad_ms": 200},
            "beam_size": self.beam_size,
            "compression_ratio_threshold": self.compression_ratio_threshold,
        }
        if self.language:
            transcribe_kwargs["language"] = self.language

        segments_iter, info = self._model.transcribe(str(audio_path), **transcribe_kwargs)

        # Collect segments with heartbeat reporting every 50 segments
        raw_segments: list[Any] = []
        for seg in segments_iter:
            raw_segments.append(seg)
            if len(raw_segments) % 50 == 0:
                reporter.heartbeat(detail=f"Segment {len(raw_segments)}")

        info_dict: dict[str, Any] = {
            "language": info.language,
            "language_probability": round(info.language_probability, 4),
            "duration": info.duration,
        }

        logger.info(
            "Transcription complete: %d segments, language=%s (%.1f%%), duration=%s",
            len(raw_segments), info.language, info.language_probability * 100,
            format_duration(info.duration),
        )

        results: list[SegmentResult] = []
        for i, seg in enumerate(raw_segments):
            words = []
            if seg.words:
                for w in seg.words:
                    words.append({
                        "word": w.word,
                        "start": round(w.start, 3),
                        "end": round(w.end, 3),
                        "probability": round(w.probability, 4),
                    })

            results.append(SegmentResult(
                id=i,
                start=round(seg.start, 3),
                end=round(seg.end, 3),
                text=seg.text.strip(),
                confidence=round(getattr(seg, "avg_log_prob", 0.0), 4),
                words=words,
            ))

        results = self._filter_hallucinations(results)

        if self.diarize and self._diarization_pipeline:
            reporter.report_stage("diarization", detail="Running speaker diarization")
            results = self._apply_diarization(audio_path, results, embeddings_dir=embeddings_dir)

        return results, info_dict

    def _filter_hallucinations(self, segments: list[SegmentResult]) -> list[SegmentResult]:
        """Detect and remove likely hallucinated segments."""
        hallucination_phrases = {
            "thank you", "thanks for watching", "subscribe",
            "please like and subscribe", "see you next time",
            "music", "applause", "laughter",
        }

        filtered: list[SegmentResult] = []
        prev_text = ""

        for seg in segments:
            text_lower = seg.text.lower().strip()
            if not text_lower:
                continue
            if text_lower == prev_text and len(text_lower) < 50:
                logger.debug("Filtered hallucination (repeat): '%s' at %.1fs", seg.text, seg.start)
                continue
            if len(text_lower.split()) <= 4 and text_lower in hallucination_phrases:
                logger.debug("Filtered hallucination (phrase): '%s' at %.1fs", seg.text, seg.start)
                continue
            words = text_lower.split()
            if len(words) > 10 and len(set(words)) / len(words) < 0.2:
                logger.debug("Filtered hallucination (internal repeat): '%.60s...' at %.1fs", seg.text, seg.start)
                continue
            filtered.append(seg)
            prev_text = text_lower

        if len(filtered) < len(segments):
            logger.info("Filtered %d hallucinated segments (%d → %d)", len(segments) - len(filtered), len(segments), len(filtered))

        for i, seg in enumerate(filtered):
            seg.id = i

        return filtered

    def _apply_diarization(
        self,
        audio_path: Path,
        segments: list[SegmentResult],
        embeddings_dir: Path | None = None,
    ) -> list[SegmentResult]:
        """Apply speaker diarization labels to transcription segments."""
        if not self._diarization_pipeline:
            return segments

        try:
            logger.info("Running speaker diarization...")
            # torchcodec on DLAMI PyTorch 2.10 can't find FFmpeg .so files, so
            # pyannote can't load audio from a file path directly. Work around
            # by converting to 16kHz mono WAV with the ffmpeg executable, loading
            # with scipy.io.wavfile (no extra deps), and passing in-memory tensor.
            import subprocess as _sp
            import tempfile as _tf
            import scipy.io.wavfile as _wfio
            import torch as _torch
            _audio_input: Any = None
            with _tf.NamedTemporaryFile(suffix=".wav", delete=False) as _tmp:
                _wav_path = _tmp.name
            try:
                _sp.run(
                    ["ffmpeg", "-i", str(audio_path),
                     "-ac", "1", "-ar", "16000", "-y", _wav_path],
                    capture_output=True, check=True,
                )
                _sr, _data = _wfio.read(_wav_path)
                _waveform = _torch.from_numpy(
                    _data.astype("float32") / 32768.0
                ).unsqueeze(0)
                _audio_input = {"waveform": _waveform, "sample_rate": _sr}
            finally:
                Path(_wav_path).unlink(missing_ok=True)

            raw = self._diarization_pipeline(
                _audio_input,
                min_speakers=self.min_speakers,
                max_speakers=self.max_speakers,
            )
            # pyannote ≥ 4.0 wraps the Annotation in DiarizeOutput.speaker_diarization
            diarization = getattr(raw, "speaker_diarization", raw)

            speaker_timeline: list[tuple[float, float, str]] = []
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                speaker_timeline.append((turn.start, turn.end, speaker))

            speakers_found: set[str] = set()
            for seg in segments:
                best_speaker: str | None = None
                best_overlap = 0.0
                for sp_start, sp_end, speaker in speaker_timeline:
                    overlap = max(0.0, min(seg.end, sp_end) - max(seg.start, sp_start))
                    if overlap > best_overlap:
                        best_overlap = overlap
                        best_speaker = speaker
                if best_speaker:
                    seg.speaker = best_speaker
                    speakers_found.add(best_speaker)

            logger.info("Diarization complete: %d speakers detected", len(speakers_found))

            if embeddings_dir is not None:
                self._export_speaker_embeddings(audio_path, diarization, embeddings_dir)

        except Exception as e:
            logger.warning("Diarization failed: %s — continuing without speaker labels", e)

        return segments

    def _export_speaker_embeddings(
        self,
        audio_path: Path,
        diarization: Any,
        out_dir: Path,
    ) -> None:
        """Extract and save ECAPA-TDNN embedding per speaker cluster via ffmpeg + speechbrain."""
        try:
            import subprocess as _sp
            import numpy as np
            import torch
            try:
                from speechbrain.inference.classifiers import EncoderClassifier
            except ImportError:
                from speechbrain.pretrained import EncoderClassifier  # type: ignore[no-redef]
        except ImportError:
            logger.warning("speechbrain not installed — skipping speaker embedding export")
            return

        out_dir.mkdir(parents=True, exist_ok=True)

        ecapa_savedir = Path.home() / ".cache" / "speechbrain"
        ecapa_savedir.mkdir(parents=True, exist_ok=True)
        # speechbrain from_hparams tries to download custom.py for user-defined modules;
        # spkrec-ecapa-voxceleb has no custom.py, so create a stub to avoid 404.
        stub = ecapa_savedir / "custom.py"
        if not stub.exists():
            stub.write_text("# placeholder\n", encoding="utf-8")
        try:
            classifier = EncoderClassifier.from_hparams(
                source="speechbrain/spkrec-ecapa-voxceleb",
                savedir=str(ecapa_savedir),
                run_opts={"device": "cpu"},
            )
        except Exception as e:
            err_msg = f"{type(e).__name__}: {e}"
            logger.warning("Failed to load ECAPA model: %s — skipping embedding export", err_msg)
            (out_dir / "clusters.json").write_text(
                json.dumps({"error": err_msg, "stage": "ecapa_load"}, indent=2),
                encoding="utf-8",
            )
            return

        # Collect segments per speaker cluster from pyannote output
        clusters: dict[str, dict[str, Any]] = {}
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            if speaker not in clusters:
                clusters[speaker] = {"segments": [], "total_duration": 0.0}
            clusters[speaker]["segments"].append((turn.start, turn.end))
            clusters[speaker]["total_duration"] += turn.end - turn.start

        clusters_meta: dict[str, Any] = {}
        for speaker, info in clusters.items():
            try:
                chunks: list[np.ndarray] = []
                all_segs = info["segments"]
                if len(all_segs) > 30:
                    logger.debug(
                        "Speaker %s has %d segments; capping embedding extraction at 30 "
                        "(may under-represent long speakers)",
                        speaker, len(all_segs),
                    )
                for start, end in all_segs[:30]:
                    duration = end - start
                    if duration < 0.5:
                        continue
                    cmd = [
                        "ffmpeg", "-i", str(audio_path),
                        "-ss", str(start), "-t", str(duration),
                        "-ac", "1", "-ar", "16000", "-f", "f32le",
                        "-loglevel", "quiet", "pipe:1",
                    ]
                    result = _sp.run(cmd, capture_output=True, timeout=30)
                    if result.returncode == 0 and result.stdout:
                        chunks.append(np.frombuffer(result.stdout, dtype=np.float32))

                if not chunks:
                    continue

                audio_np = np.concatenate(chunks)
                waveform = torch.from_numpy(audio_np).unsqueeze(0)
                embedding = classifier.encode_batch(waveform)
                embedding_np = embedding.squeeze().cpu().numpy()

                emb_path = out_dir / f"{speaker}.npy"
                np.save(str(emb_path), embedding_np)
                clusters_meta[speaker] = {
                    "duration_s": round(info["total_duration"], 2),
                    "segment_count": len(info["segments"]),
                    "embedding_path": emb_path.name,
                }
            except Exception as e:
                logger.warning("Failed to export embedding for %s: %s", speaker, e)

        (out_dir / "clusters.json").write_text(
            json.dumps(clusters_meta, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info("Speaker embeddings exported: %d clusters → %s", len(clusters_meta), out_dir)


# ---------------------------------------------------------------------------
# Segment annotation helpers
# ---------------------------------------------------------------------------

def tag_segment_types(
    segments: list[SegmentResult],
    intro_window_s: float = 90.0,
    outro_window_s: float = 120.0,
    total_duration_s: float = 0.0,
) -> None:
    """
    Mark segments in intro/outro time windows in-place.

    Segments whose end time falls within the first intro_window_s seconds are
    tagged "intro". Segments whose start time falls within the last
    outro_window_s seconds are tagged "outro". Everything else is "content".
    total_duration_s is required for outro detection; if 0, outro is skipped.
    """
    for seg in segments:
        if seg.end <= intro_window_s:
            seg.segment_type = "intro"
        elif total_duration_s > 0 and seg.start >= (total_duration_s - outro_window_s):
            seg.segment_type = "outro"
        # else: stays "content" (default)


def _update_run_manifest(episode_dir: Path, run_id: str, meta: dict[str, Any]) -> None:
    """Write or update transcript/run_manifest.json with the given run entry."""
    manifest_path = episode_dir / "transcript" / "run_manifest.json"
    try:
        if manifest_path.exists():
            data: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
        else:
            data = {"canonical": run_id, "runs": []}

        existing_ids = {r["run_id"] for r in data.get("runs", [])}
        if run_id not in existing_ids:
            data["runs"].append({"run_id": run_id, "created_at": now_iso(), **meta})
        data["canonical"] = run_id

        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logger.debug("Failed to update run manifest: %s", e)


# ---------------------------------------------------------------------------
# Output Writers
# ---------------------------------------------------------------------------

def write_transcript_json(
    episode: EpisodeInfo,
    segments: list[SegmentResult],
    info_dict: dict[str, Any],
    topic_summary: dict[str, Any],
    engine_config: dict[str, Any],
    output_dir: Path,
    chapter_set: Any | None = None,
) -> Path:
    """Write the full structured transcript.json."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "transcript.json"

    total_words = sum(len(s.text.split()) for s in segments)
    speakers = {s.speaker for s in segments if s.speaker}
    topics_tagged = sum(1 for s in segments if s.topics)

    data: dict[str, Any] = {
        "meta": {
            "episode_title": episode.title,
            "episode_guid": episode.guid,
            "season": episode.season,
            "episode": episode.episode,
            "pub_date": episode.pub_date,
            "audio_file": "audio.mp3",
            "audio_duration_seconds": round(info_dict.get("duration", 0), 2),
            "transcribed_at": now_iso(),
            "pipeline_version": PIPELINE_VERSION,
            "whisper_model": engine_config.get("model_size", "unknown"),
            "device": engine_config.get("device", "unknown"),
            "compute_type": engine_config.get("compute_type", "unknown"),
            "language": info_dict.get("language"),
            "language_probability": info_dict.get("language_probability"),
            "diarization_enabled": engine_config.get("diarize", False),
        },
        "statistics": {
            "total_segments": len(segments),
            "total_words": total_words,
            "total_duration_seconds": round(
                (max(s.end for s in segments) - min(s.start for s in segments)), 2,
            ) if segments else 0,
            "speakers_detected": len(speakers),
            "topics_tagged": topics_tagged,
            "films_mentioned": len(topic_summary.get("films_mentioned", [])),
            "chapters_generated": chapter_set.chapter_count if chapter_set else 0,
        },
        "chapters": [],
        "segments": [
            {
                "id": s.id,
                "start": s.start,
                "end": s.end,
                "text": s.text,
                "speaker": s.speaker,
                "segment_type": s.segment_type,
                "chapter_id": s.chapter_id,
                "confidence": s.confidence,
                "words": s.words,
                "topics": s.topics,
                "films": s.films,
            }
            for s in segments
        ],
        "topics_summary": topic_summary.get("topics", []),
        "films_summary": topic_summary.get("films_mentioned", []),
    }

    if chapter_set is not None:
        data["chapters"] = [
            {
                "index": ch.index,
                "title": ch.title,
                "start_time": ch.start_time,
                "end_time": ch.end_time,
                "duration": ch.duration,
                "summary": ch.summary,
                "segment_range": list(ch.segment_range),
                "word_count": ch.word_count,
                "topics": ch.topics,
                "films": ch.films,
                "speakers": ch.speakers,
                "key_phrases": ch.key_phrases,
            }
            for ch in chapter_set.chapters
        ]

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def write_transcript_txt(
    episode: EpisodeInfo,
    segments: list[SegmentResult],
    info_dict: dict[str, Any],
    output_dir: Path,
    chapter_set: Any | None = None,
) -> Path:
    """Write human-readable plain text transcript with timecodes and chapter markers."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "transcript.txt"

    lines: list[str] = [
        f"TRANSCRIPT: {episode.title or episode.dir_name}",
        f"Date: {episode.pub_date or 'unknown'}",
        f"Duration: {format_duration(info_dict.get('duration', 0))}",
        f"Language: {info_dict.get('language', 'unknown')}",
        f"Model: faster-whisper {PIPELINE_VERSION}",
        f"Transcribed: {now_iso()}",
        "",
    ]

    if chapter_set is not None and chapter_set.chapter_count > 0:
        lines.append("CHAPTERS:")
        for ch in chapter_set.chapters:
            h = int(ch.start_time // 3600)
            m = int((ch.start_time % 3600) // 60)
            s = int(ch.start_time % 60)
            lines.append(f"  {h:02d}:{m:02d}:{s:02d}  {ch.title}")
        lines.append("")

    lines.append("=" * 72)
    lines.append("")

    chapter_starts: dict[int, Any] = {}
    if chapter_set is not None:
        for ch in chapter_set.chapters:
            seg_start = ch.segment_range[0] if isinstance(ch.segment_range, (list, tuple)) else 0
            chapter_starts[seg_start] = ch

    current_speaker: str | None = None
    for seg in segments:
        if seg.id in chapter_starts:
            ch = chapter_starts[seg.id]
            lines.extend(["", f"--- {ch.title} ---"])
            if ch.summary:
                lines.append(f"    {ch.summary}")
            lines.append("")

        tc = format_timestamp_srt(seg.start)
        if seg.speaker and seg.speaker != current_speaker:
            current_speaker = seg.speaker
            lines.append(f"\n[{current_speaker}]")

        lines.append(f"[{tc}]  {seg.text}")

    lines.extend([
        "",
        "=" * 72,
        f"Total segments: {len(segments)}",
        f"Total words: {sum(len(s.text.split()) for s in segments)}",
    ])
    if chapter_set:
        lines.append(f"Total chapters: {chapter_set.chapter_count}")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_segments_jsonl(segments: list[SegmentResult], output_dir: Path) -> Path:
    """Write streaming-friendly line-delimited JSON (one segment per line)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "transcript_segments.jsonl"

    with open(path, "w", encoding="utf-8") as f:
        for seg in segments:
            line = json.dumps({
                "id": seg.id,
                "start": seg.start,
                "end": seg.end,
                "text": seg.text,
                "speaker": seg.speaker,
                "segment_type": seg.segment_type,
                "chapter_id": seg.chapter_id,
                "confidence": seg.confidence,
                "topics": [t["topic"] for t in seg.topics] if seg.topics else [],
            }, ensure_ascii=False)
            f.write(line + "\n")

    return path


def update_sources_json(output_dir: Path, engine_config: dict[str, Any], transcribed_at: str) -> None:
    """Add a whisper_local entry to sources.json without disturbing existing entries.

    sources.json is the provenance ledger written by ingest_teamdeakins_downloads.py.
    It records which external services supplied transcripts. We append our Whisper
    run as an additional source alongside any Apple Podcasts / Tapesearch entries.
    transcript_sources.json (the raw Apple TTML dump) is never touched.
    """
    sources_path = output_dir / "sources.json"
    if not sources_path.exists():
        return

    try:
        data: dict[str, Any] = json.loads(sources_path.read_text(encoding="utf-8"))
    except Exception:
        return  # Don't clobber a file we can't parse

    sources = data.setdefault("sources", {})
    sources["whisper_local"] = {
        "model": engine_config.get("model_size", "unknown"),
        "device": engine_config.get("device", "cpu"),
        "compute_type": engine_config.get("compute_type", "int8"),
        "pipeline_version": PIPELINE_VERSION,
        "transcribed_at": transcribed_at,
    }

    notes: list[str] = data.setdefault("notes", [])
    notes.append(f"Whisper ({engine_config.get('model_size', 'unknown')}) transcription added on {transcribed_at[:10]}")

    sources_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def write_extraction_report(episode: EpisodeInfo, result: TranscriptionResult, output_dir: Path) -> Path:
    """Write per-episode extraction report."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "extraction_report.json"

    data = {
        "episode_dir": episode.dir_name,
        "episode_title": episode.title,
        "success": result.success,
        "error": result.error,
        "transcribed_at": now_iso(),
        "pipeline_version": PIPELINE_VERSION,
        "processing_time_seconds": round(result.processing_time_seconds, 2),
        "audio_duration_seconds": round(result.total_audio_duration, 2),
        "segment_count": result.segment_count,
        "word_count": result.word_count,
        "language": result.language,
        "speakers_detected": result.speakers_detected,
        "topics_tagged": result.topics_tagged,
        "films_mentioned": result.films_mentioned,
        "chapters_generated": result.chapters_generated,
    }

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------

def process_episode(
    episode: EpisodeInfo,
    engine: TranscriptionEngine,
    topic_tagger: Any | None,
    chapter_generator: Any | None = None,
    run_id: str | None = None,
    embed_speakers: bool = False,
    progress_reporter: ProgressReporter | _NoOpReporter | None = None,
) -> TranscriptionResult:
    """
    Process a single episode through the full pipeline.

    This function NEVER raises — all errors are caught and returned
    in the TranscriptionResult.
    """
    reporter = progress_reporter or _NoOpReporter()
    result = TranscriptionResult(success=False, episode_dir=episode.dir_name)
    start_time = time.monotonic()

    # Resolve output dir early so it is available in the finally block
    if run_id:
        output_dir = episode.dir_path / "transcript" / "runs" / run_id
    else:
        output_dir = episode.dir_path / "transcript"

    try:
        if not episode.audio_path.exists():
            result.error = f"Audio file not found: {episode.audio_path}"
            return result

        file_size = episode.audio_path.stat().st_size
        if file_size < 1024:
            result.error = f"Audio file too small ({file_size} bytes) — likely corrupt"
            return result

        # Stage 1: Transcribe (with optional diarization + embedding export)
        reporter.report_stage("transcription", detail="Starting whisper transcription")
        embeddings_dir = (output_dir / "speaker_embeddings") if (embed_speakers and engine.diarize) else None
        segments, info_dict = engine.transcribe(
            episode.audio_path, embeddings_dir=embeddings_dir,
            progress_reporter=reporter,
        )

        result.language = info_dict.get("language")
        result.language_probability = info_dict.get("language_probability")
        result.total_audio_duration = info_dict.get("duration", 0)
        result.segment_count = len(segments)
        result.word_count = sum(len(s.text.split()) for s in segments)

        if not segments:
            result.error = "Transcription produced zero segments"
            return result

        # Stage 1b: Tag intro/outro time windows
        reporter.report_stage("intro_outro_tagging")
        tag_segment_types(segments, total_duration_s=result.total_audio_duration or 0.0)
        intro_count = sum(1 for s in segments if s.segment_type == "intro")
        outro_count = sum(1 for s in segments if s.segment_type == "outro")
        if intro_count or outro_count:
            logger.info("Segment types tagged: %d intro, %d outro, %d content",
                        intro_count, outro_count, len(segments) - intro_count - outro_count)

        # Stage 2: Topic tagging
        reporter.report_stage("topic_tagging")
        topic_summary: dict[str, Any] = {"topics": [], "films_mentioned": []}

        if topic_tagger is not None:
            logger.info("Tagging topics...")
            all_segment_topics = []
            all_segment_films = []

            for seg in segments:
                matches = topic_tagger.tag_segment(seg.text)
                seg.topics = [asdict(m) for m in matches]
                all_segment_topics.append(matches)

                films = topic_tagger.detect_films(seg.text)
                seg.films = [asdict(f) for f in films]
                all_segment_films.append(films)

            topic_summary = topic_tagger.build_episode_summary(all_segment_topics, all_segment_films)
            result.topics_tagged = sum(1 for s in segments if s.topics)
            result.films_mentioned = len(topic_summary.get("films_mentioned", []))

            logger.info(
                "Topics tagged: %d segments, %d unique topics, %d films mentioned",
                result.topics_tagged, len(topic_summary.get("topics", [])), result.films_mentioned,
            )

        # Stage 3: Count speakers
        result.speakers_detected = len({s.speaker for s in segments if s.speaker})

        # Stage 4: Chapter generation
        reporter.report_stage("chapter_generation")
        chapter_set = None
        if chapter_generator is not None:
            try:
                logger.info("Generating smart chapters...")
                seg_dicts = [
                    {
                        "id": s.id, "start": s.start, "end": s.end, "text": s.text,
                        "speaker": s.speaker, "confidence": s.confidence,
                        "topics": s.topics, "films": s.films,
                    }
                    for s in segments
                ]
                chapter_set = chapter_generator.generate(seg_dicts, info_dict.get("duration", 0), episode.title)
                result.chapters_generated = chapter_set.chapter_count
                logger.info(
                    "Chapters generated: %d chapters (avg %.0fs each)",
                    chapter_set.chapter_count,
                    info_dict.get("duration", 0) / max(chapter_set.chapter_count, 1),
                )
                # Backfill chapter_id on each segment using chapter.segment_range
                for ch in chapter_set.chapters:
                    lo, hi = ch.segment_range
                    for i in range(lo, hi + 1):
                        if i < len(segments):
                            segments[i].chapter_id = ch.index
            except Exception as e:
                logger.warning("Chapter generation failed: %s — continuing without", e)

        # Stage 5: Write outputs
        reporter.report_stage("write_outputs")
        # output_dir was resolved above (supports --run-id for multi-run layout)
        # sources.json stays in the base transcript/ dir (episode-level provenance)
        base_transcript_dir = episode.dir_path / "transcript"
        engine_config = {
            "model_size": engine.model_size,
            "device": engine.device,
            "compute_type": engine.compute_type,
            "diarize": engine.diarize,
        }

        write_transcript_json(episode, segments, info_dict, topic_summary, engine_config, output_dir, chapter_set)
        write_transcript_txt(episode, segments, info_dict, output_dir, chapter_set)
        write_segments_jsonl(segments, output_dir)
        update_sources_json(base_transcript_dir, engine_config, now_iso())

        if chapter_set is not None and chapter_set.chapter_count > 0:
            try:
                from chapter_generator import (
                    write_chapters_ffmetadata,
                    write_chapters_json,
                    write_chapters_txt as write_ch_txt,
                    write_podcastns_chapters,
                )
                write_chapters_json(chapter_set, output_dir / "chapters.json")
                write_podcastns_chapters(chapter_set, output_dir / "chapters_podcastns.json")
                write_ch_txt(chapter_set, output_dir / "chapters.txt")
                write_chapters_ffmetadata(chapter_set, output_dir / "chapters.ffmeta")
            except Exception as e:
                logger.warning("Failed to write chapter files: %s", e)

        result.success = True
        logger.info("✓ %s — %d segments, %d words", episode.dir_name, len(segments), result.word_count)

        if run_id:
            _update_run_manifest(episode.dir_path, run_id, {
                "whisper_model": engine.model_size,
                "diarization": engine.diarize,
                "speaker_embeddings": embed_speakers and engine.diarize,
                "pipeline_version": PIPELINE_VERSION,
            })

    except MemoryError:
        result.error = (
            "Out of memory. Try a smaller model (--model medium or --model small) "
            "or close other applications."
        )
        result.error_traceback = traceback.format_exc()
        logger.error("✗ OOM processing %s: %s", episode.dir_name, result.error)

    except KeyboardInterrupt:
        result.error = "Interrupted by user"
        raise

    except Exception as e:
        result.error = f"{type(e).__name__}: {e}"
        result.error_traceback = traceback.format_exc()
        logger.error("✗ Error processing %s: %s", episode.dir_name, result.error)

    finally:
        result.processing_time_seconds = time.monotonic() - start_time
        reporter.finish(error=result.error)
        try:
            write_extraction_report(episode, result, output_dir)
        except Exception as e:
            logger.debug("Failed to write extraction report: %s", e)

    return result


def run_pipeline(args: argparse.Namespace) -> BatchReport:
    """Execute the full transcription pipeline. Returns a BatchReport."""
    report = BatchReport(
        started_at=now_iso(),
        whisper_model=args.model,
        diarization_enabled=args.diarize,
        topic_tagging_enabled=not args.no_topics,
        system_info=get_system_info(),
    )

    downloads_dir = Path(args.downloads).resolve()
    library_dir = Path(args.library).resolve() if args.library else None

    if not shutil.which("ffmpeg"):
        logger.error(
            "ffmpeg not found on PATH. Install it:\n"
            "  macOS:  brew install ffmpeg\n"
            "  Ubuntu: sudo apt install ffmpeg"
        )
        report.finished_at = now_iso()
        report.total_failed = -1  # sentinel: forces sys.exit(1) in main()
        return report

    logger.info("Discovering episodes in %s ...", downloads_dir)
    episodes = discover_episodes(downloads_dir, force=args.force, single=args.episode)
    all_episodes = discover_all_episodes(downloads_dir)
    report.total_discovered = len(all_episodes)

    if not episodes:
        logger.info("No episodes need transcription. Use --force to re-transcribe.")
        report.gaps = _build_gaps(all_episodes)
        report.finished_at = now_iso()
        return report

    logger.info(
        "Found %d episodes to process (out of %d total, %d already done)",
        len(episodes), len(all_episodes), len(all_episodes) - len(episodes),
    )

    if args.batch_size and args.batch_size > 0:
        episodes = episodes[:args.batch_size]
        logger.info("Batch limited to %d episodes", len(episodes))

    if args.dry_run:
        logger.info("\n--- DRY RUN ---")
        for ep in episodes:
            dur_str = format_duration(ep.duration_hint) if ep.duration_hint else "unknown"
            logger.info("  Would process: %s (%s, ~%s)", ep.dir_name, ep.title or "no title", dur_str)
        report.finished_at = now_iso()
        return report

    # Create a pre-model reporter for single-episode runs so model loading
    # is visible in progress.json (the main observability gap that caused
    # silent 60-minute hangs on model download).
    _pre_reporter: ProgressReporter | _NoOpReporter = _NoOpReporter()
    _progress_file = getattr(args, "progress_file", None)
    if args.episode and len(episodes) == 1:
        ep0 = episodes[0]
        if _progress_file:
            _pre_reporter = ProgressReporter(Path(_progress_file), ep0.dir_name)
        else:
            _pre_reporter = ProgressReporter(ep0.dir_path / "progress.json", ep0.dir_name)

    engine = TranscriptionEngine(
        model_size=args.model,
        device=args.device,
        compute_type=args.compute_type,
        language=args.language,
        diarize=args.diarize,
        hf_token=args.hf_token,
        min_speakers=args.min_speakers,
        max_speakers=args.max_speakers,
        cpu_threads=args.cpu_threads,
        beam_size=args.beam_size,
        compression_ratio_threshold=args.compression_ratio_threshold,
        strict_diarize=getattr(args, "strict_diarize", False),
    )

    _pre_reporter.report_stage("model_loading", detail=f"Loading {args.model}")
    try:
        engine.load_model()
    except (ImportError, Exception) as e:
        _pre_reporter.finish(error=str(e))
        logger.error("Failed to load model: %s", e)
        report.finished_at = now_iso()
        return report

    report.device = engine.device
    report.compute_type = engine.compute_type

    # Load topic tagger
    topic_tagger: Any | None = None
    if not args.no_topics:
        try:
            from topic_tagger import TopicTagger
            topic_tagger = TopicTagger(library_dir=library_dir)
            if library_dir and (library_dir / "forums" / "posts").exists():
                if topic_tagger.load_corpus():
                    logger.info("Forum corpus loaded for enhanced topic tagging")
                else:
                    logger.info("Using built-in cinematography vocabulary (no forum corpus)")
            else:
                logger.info("Using built-in cinematography vocabulary (no forum corpus available)")
        except ImportError as e:
            logger.warning("Could not load topic_tagger: %s — skipping topic tagging", e)

    # Load chapter generator
    chapter_generator: Any | None = None
    if not args.no_chapters:
        try:
            from chapter_generator import ChapterConfig, ChapterGenerator
            chapter_config = ChapterConfig(
                min_chapter_seconds=args.chapter_min,
                target_chapter_seconds=args.chapter_target,
                max_chapter_seconds=args.chapter_max,
            )
            chapter_generator = ChapterGenerator(chapter_config)
            logger.info(
                "Chapter generator enabled (min=%.0fs, target=%.0fs, max=%.0fs)",
                args.chapter_min, args.chapter_target, args.chapter_max,
            )
        except ImportError as e:
            logger.warning("Could not load chapter_generator: %s — skipping chapters", e)

    for i, episode in enumerate(episodes, 1):
        if _shutdown_requested:
            logger.info("Shutdown requested — stopping after %d episodes", i - 1)
            break

        sep = "=" * 60
        dur_str = format_duration(episode.duration_hint) if episode.duration_hint else "unknown"
        logger.info(
            "\n%s\n[%d/%d] %s\n  Title: %s\n  Duration: %s\n%s",
            sep, i, len(episodes), episode.dir_name, episode.title or "(no title)", dur_str, sep,
        )

        # Create per-episode progress reporter for remote monitoring.
        # For single-episode runs, reuse the pre-model reporter so model_loading
        # timing is included in the same progress file.
        if isinstance(_pre_reporter, ProgressReporter) and len(episodes) == 1:
            _reporter: ProgressReporter | _NoOpReporter = _pre_reporter
        else:
            _pf = getattr(args, "progress_file", None)
            if _pf:
                _reporter = ProgressReporter(Path(_pf), episode.dir_name)
            elif getattr(args, "episode", None):
                _reporter = ProgressReporter(episode.dir_path / "progress.json", episode.dir_name)
            else:
                _reporter = _NoOpReporter()

        result = process_episode(
            episode, engine, topic_tagger, chapter_generator,
            run_id=getattr(args, "run_id", None),
            embed_speakers=getattr(args, "embed_speakers", False),
            progress_reporter=_reporter,
        )

        if result.success:
            report.total_succeeded += 1
            report.results.append({
                "episode_dir": episode.dir_name,
                "title": episode.title,
                "segments": result.segment_count,
                "words": result.word_count,
                "duration": round(result.total_audio_duration, 1),
                "processing_time": round(result.processing_time_seconds, 1),
                "language": result.language,
                "speakers": result.speakers_detected,
                "topics_tagged": result.topics_tagged,
                "films_mentioned": result.films_mentioned,
                "chapters_generated": result.chapters_generated,
            })
        else:
            report.total_failed += 1
            report.failures.append({
                "episode_dir": episode.dir_name,
                "title": episode.title,
                "error": result.error,
                "traceback": result.error_traceback,
            })

        report.total_processed += 1
        report.total_processing_time += result.processing_time_seconds

    report.total_skipped = len(all_episodes) - len(episodes)
    report.gaps = _build_gaps(discover_all_episodes(downloads_dir))
    report.finished_at = now_iso()
    return report


def _build_gaps(all_episodes: list[EpisodeInfo]) -> list[dict[str, Any]]:
    return [
        {
            "episode_dir": ep.dir_name,
            "title": ep.title,
            "has_audio": ep.audio_path.exists(),
            "existing_type": ep.existing_transcript_type,
            "reason": "no audio file" if not ep.audio_path.exists() else "not yet transcribed",
        }
        for ep in all_episodes
        if not ep.has_existing_transcript
    ]


def write_batch_report(report: BatchReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(report), indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Batch report written: %s", path)


def print_summary(report: BatchReport) -> None:
    print("\n" + "=" * 60)
    print("TRANSCRIPTION RUN SUMMARY")
    print("=" * 60)
    print(f"  Pipeline version:   {report.pipeline_version}")
    print(f"  Whisper model:      {report.whisper_model}")
    print(f"  Device:             {report.device}")
    print(f"  Compute type:       {report.compute_type}")
    print(f"  Diarization:        {'enabled' if report.diarization_enabled else 'disabled'}")
    print(f"  Topic tagging:      {'enabled' if report.topic_tagging_enabled else 'disabled'}")
    print()
    print(f"  Episodes discovered:  {report.total_discovered}")
    print(f"  Episodes processed:   {report.total_processed}")
    print(f"  Succeeded:            {report.total_succeeded}")
    print(f"  Failed:               {report.total_failed}")
    print(f"  Skipped (existing):   {report.total_skipped}")
    print(f"  Gaps remaining:       {len(report.gaps)}")
    print(f"  Total time:           {format_duration(report.total_processing_time)}")

    if report.failures:
        print("\n  FAILURES:")
        for f in report.failures:
            print(f"    ✗ {f['episode_dir']}")
            print(f"       {f['error']}")

    if report.gaps:
        print(f"\n  GAPS ({len(report.gaps)} episodes without transcripts):")
        for g in report.gaps[:10]:
            print(f"    ⚠  {g['episode_dir']} — {g['reason']}")
        if len(report.gaps) > 10:
            print(f"    ... and {len(report.gaps) - 10} more")

    print("=" * 60)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Transcribe Team Deakins podcast episodes with timecodes and topic tags",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/tools/transcribe_episodes.py
  python scripts/tools/transcribe_episodes.py --model medium
  python scripts/tools/transcribe_episodes.py --episode S02E169__2025-11-26__...
  python scripts/tools/transcribe_episodes.py --diarize --hf-token YOUR_TOKEN
  python scripts/tools/transcribe_episodes.py --dry-run

Requirements:
  pip install faster-whisper    (see requirements-transcription.txt)
  System: ffmpeg must be installed
        """,
    )

    p.add_argument("--downloads", default="./downloads")
    p.add_argument("--library", default="./library")

    p.add_argument(
        "--model", default="large-v3",
        choices=["tiny", "tiny.en", "base", "base.en", "small", "small.en",
                 "medium", "medium.en", "large-v1", "large-v2", "large-v3",
                 "distil-large-v3", "distil-medium.en", "distil-small.en"],
    )
    p.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    p.add_argument("--compute-type", default="auto", choices=["auto", "float16", "float32", "int8", "int8_float16"])
    p.add_argument("--language", default=None)

    p.add_argument("--diarize", action="store_true")
    p.add_argument("--hf-token", default=None)
    p.add_argument("--run-id", default=None,
                   help="Versioned run identifier. Output goes to transcript/runs/{run-id}/. "
                        "If omitted, writes to transcript/ (legacy mode).")
    p.add_argument("--embed-speakers", action="store_true",
                   help="Export ECAPA-TDNN speaker embeddings per cluster (requires --diarize).")
    p.add_argument("--min-speakers", type=int, default=2)
    p.add_argument("--max-speakers", type=int, default=4)
    p.add_argument("--cpu-threads", type=int, default=0,
                   help="CTranslate2 CPU threads (0=auto/all cores, recommended: 12 on M3 Max)")
    p.add_argument("--beam-size", type=int, default=3,
                   help="Whisper beam size (1=fastest/greedy, 3=default, 5=slowest/best)")
    p.add_argument("--compression-ratio-threshold", type=float, default=3.5,
                   help="Compression ratio above which Whisper retries at higher temperature "
                        "(default 3.5 for podcasts; Whisper default 2.4 causes excess retries)")

    p.add_argument("--no-topics", action="store_true")
    p.add_argument("--no-chapters", action="store_true")
    p.add_argument("--chapter-min", type=float, default=120)
    p.add_argument("--chapter-target", type=float, default=420)
    p.add_argument("--chapter-max", type=float, default=1200)
    p.add_argument("--force", action="store_true")
    p.add_argument("--episode", default=None)
    p.add_argument("--batch-size", type=int, default=0)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--report", default=None)
    p.add_argument("--progress-file", default=None,
                   help="Write structured progress JSON to this path (for remote monitoring). "
                        "Default: {episode_dir}/progress.json when --episode is set.")
    p.add_argument("--strict-diarize", action="store_true",
                   help="Fail hard if diarization cannot load (no silent fallback).")
    p.add_argument("--verbose", action="store_true")

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    print("=" * 60)
    print("Team Deakins Transcription Pipeline")
    print(f"Pipeline version: {PIPELINE_VERSION}")
    print("=" * 60)

    report = run_pipeline(args)

    report_path = args.report or f"transcription_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    write_batch_report(report, Path(report_path))
    print_summary(report)

    sys.exit(1 if report.total_failed > 0 else 0)


if __name__ == "__main__":
    main()
