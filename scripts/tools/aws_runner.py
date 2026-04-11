#!/usr/bin/env python3
"""
aws_runner.py — Remote transcription coordinator for EC2 GPU instances.

Runs faster-whisper large-v3 on GPU (CUDA / float16) rather than local CPU,
achieving ~8× real-time vs ~1.2× local.  Audio is never stored permanently
on AWS — each episode is uploaded, processed, and cleaned up before the next
one starts on that worker.  Transcript output is written back to the local
downloads/ transcript directories.

Quick start:

  # 1. Provision one or more g4dn.xlarge spot instances
  #    (AWS Deep Learning AMI — Ubuntu 20.04 recommended)

  # 2. One-time setup per instance (installs deps, warms model):
  python scripts/tools/aws_runner.py \\
      --hosts 1.2.3.4 --key ~/.ssh/key.pem --setup-only

  # 3. Run the 13 Apple-transcribed test episodes:
  python scripts/tools/aws_runner.py \\
      --hosts 1.2.3.4 --key ~/.ssh/key.pem --mode test

  # 4. Full run across three instances in parallel:
  python scripts/tools/aws_runner.py \\
      --hosts ip1,ip2,ip3 --key ~/.ssh/key.pem --mode full

  # 5. Single episode:
  python scripts/tools/aws_runner.py \\
      --hosts 1.2.3.4 --key ~/.ssh/key.pem \\
      --mode episode --episode S02E169__2025-11-26__edgar-wright-director__libsyn_f6853474de

Notes:
  - Requires ssh and rsync in $PATH (macOS: both included).
  - Each EC2 worker processes one episode at a time (GPU is the bottleneck).
    To parallelise, pass multiple --hosts (one episode per instance at once).
  - The remote /tmp/td_transcribe/ tree is ephemeral — nothing persists
    between episodes beyond the HuggingFace model cache (~/.cache/huggingface).
  - Recommended instance: g4dn.xlarge (T4, 16 GB VRAM, $0.16/hr spot).
    large-v3 in float16 uses ~3.1 GB VRAM, runs at ~8× real-time.
  - Python 3.11+ required on the remote instance (for StrEnum in models.py).
    DLAMI ships with Python 3.10; install 3.11 via deadsnakes if needed:
      sudo add-apt-repository ppa:deadsnakes/ppa -y
      sudo apt-get install -y python3.11 python3.11-venv
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import logging
import os
import shlex
import subprocess
import sys
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# EC2 provisioning constants (pre-configured for this account)
# ---------------------------------------------------------------------------

EC2_DEFAULTS = {
    "ami_id": "ami-0016081b488c7376d",          # DLAMI GPU PyTorch 2.7 Ubuntu 22.04 (2026-02-22)
    "instance_type": "g4dn.xlarge",             # T4 GPU, 4 vCPU, 16 GB RAM
    "key_name": "td-transcription",             # Key pair created for this project
    "security_group_id": "sg-0b8a7b84c3e156322", # td-transcription-sg (SSH from office IP)
    "region": "us-east-1",
    "best_az": "us-east-1b",                    # Cheapest AZ at provisioning time ($0.197/hr spot)
    "spot_max_price": "0.35",                   # Hard cap — on-demand is $0.526, this gives headroom
    "default_key_path": "~/.ssh/td-transcription.pem",
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s — %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, datefmt="%H:%M:%S")
logger = logging.getLogger("aws_runner")

PIPELINE_VERSION = "aws-v2.0"


def make_run_id(model: str, diarize: bool) -> str:
    """Generate a deterministic run identifier shared across all episodes in a batch."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    model_slug = model.replace("-", "").replace(".", "")[:4]  # e.g. "larg" from "large-v3"
    flags = "dz" if diarize else "nd"
    return f"run_{ts}__{model_slug}__{flags}"


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
            data["runs"].append({
                "run_id": run_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                **meta,
            })
        data["canonical"] = run_id
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logger.debug("Failed to update run manifest for %s: %s", episode_dir.name, e)


# Scripts that must be present on the remote instance alongside
# transcribe_episodes.py (it imports them at runtime).
REQUIRED_SCRIPTS = [
    "transcribe_episodes.py",
    "chapter_generator.py",
    "topic_tagger.py",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# RemoteWorker
# ---------------------------------------------------------------------------


@dataclass
class RemoteWorker:
    """Represents one EC2 instance as a transcription worker."""

    host: str
    key_path: Path
    user: str = "ubuntu"
    remote_base: str = "/tmp/td_transcribe"
    # python executable to use on the remote (override if 3.11 is non-default)
    python: str = "python3"
    device: str = "cuda"
    compute_type: str = "float16"
    cpu_threads: int = 0  # 0 = let faster-whisper choose
    # Run versioning and diarization
    run_id: str = ""
    diarize: bool = False
    hf_token: str | None = None
    embed_speakers: bool = False
    # Actual ffmpeg bin directory discovered during setup (may differ from /usr/bin on DLAMI)
    ffmpeg_dir: str = ""

    # ── SSH / rsync helpers ───────────────────────────────────────────────

    @property
    def _ssh_opts(self) -> list[str]:
        return [
            "-i", str(self.key_path),
            "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "ConnectTimeout=30",
            "-o", "ServerAliveInterval=60",
            "-o", "ServerAliveCountMax=10",
        ]

    def _ssh(self, cmd: str, timeout: int = 300) -> tuple[int, str, str]:
        """Run a shell command on the remote host. Returns (rc, stdout, stderr)."""
        full = ["ssh"] + self._ssh_opts + [f"{self.user}@{self.host}", cmd]
        result = subprocess.run(full, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout, result.stderr

    def _launch_detached(self, remote_cmd: str, log_path: str) -> str:
        """
        Launch remote_cmd detached via nohup; return the remote PID.

        The process survives SSH disconnect. stdout+stderr are written to
        log_path on the remote host for later inspection.
        """
        self._ssh(f"mkdir -p $(dirname {shlex.quote(log_path)})", timeout=15)
        # Use 'sh -c' so env-var prefixes (HF_TOKEN=...) are honoured by the shell.
        launch = (
            f"nohup sh -c {shlex.quote(remote_cmd)} "
            f">{shlex.quote(log_path)} 2>&1 & echo $!"
        )
        rc, out, err = self._ssh(launch, timeout=30)
        pid = out.strip()
        if rc != 0 or not pid.isdigit():
            raise RuntimeError(
                f"Failed to launch detached job on {self.host}: {err[:300] or out!r}"
            )
        return pid

    def _poll_until_done(
        self,
        done_marker: str,
        pid: str,
        ep_name: str,
        log_path: str,
        timeout: int = 7200,
        poll_interval: int = 60,
    ) -> None:
        """
        Block until done_marker file exists on the remote host.

        Polls every poll_interval seconds via short SSH commands.  Handles
        transient SSH failures (network blips, brief disconnects) with
        exponential back-off up to 10 minutes.  On reconnect after a gap
        it re-checks the done_marker before re-checking the PID, so a job
        that completed while we were disconnected is recognised immediately.

        Raises RuntimeError if the remote process exits without writing the
        marker, or TimeoutError if timeout is exceeded.
        """
        deadline = time.monotonic() + timeout
        backoff = 30

        while time.monotonic() < deadline:
            time.sleep(poll_interval)
            try:
                # Primary check: completion marker written by transcribe_episodes.py
                rc, _, _ = self._ssh(f"test -f {shlex.quote(done_marker)}", timeout=15)
                if rc == 0:
                    return  # ✓ done

                # Secondary check: is the process still alive?
                rc2, _, _ = self._ssh(f"kill -0 {pid} 2>/dev/null", timeout=15)
                if rc2 != 0:
                    # Process exited without writing the done marker — transcription failed.
                    # Read last 40 lines of log for diagnosis.
                    _, tail, _ = self._ssh(
                        f"tail -40 {shlex.quote(log_path)} 2>/dev/null", timeout=15
                    )
                    raise RuntimeError(
                        f"Remote job PID {pid} exited without writing "
                        f"completion marker.\nLast log lines:\n{tail}"
                    )

                backoff = 30  # reset after a successful check
                logger.debug(
                    "[%s] Job PID %s still running (%s)...",
                    self.host, pid, ep_name,
                )

            except subprocess.TimeoutExpired:
                logger.warning(
                    "[%s] SSH check timed out for %s — retrying in %ds...",
                    self.host, ep_name, backoff,
                )
                time.sleep(backoff)
                backoff = min(backoff * 2, 600)  # cap at 10 min

        raise TimeoutError(
            f"Episode {ep_name} did not complete within {timeout // 60} min. "
            f"Remote log: ssh -i {self.key_path} {self.user}@{self.host} "
            f"tail -100 {log_path}"
        )

    def _rsync_up(self, local: Path, remote_path: str, timeout: int = 600) -> None:
        """Upload local path → remote."""
        ssh_cmd = "ssh " + " ".join(shlex.quote(o) for o in self._ssh_opts)
        dst = f"{self.user}@{self.host}:{remote_path}"
        cmd = ["rsync", "-az", "-e", ssh_cmd, str(local), dst]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            raise RuntimeError(f"rsync upload failed [{self.host}]: {result.stderr[:400]}")

    def _rsync_down(self, remote_path: str, local: Path, timeout: int = 120) -> None:
        """Download remote path → local directory."""
        ssh_cmd = "ssh " + " ".join(shlex.quote(o) for o in self._ssh_opts)
        src = f"{self.user}@{self.host}:{remote_path}"
        local.mkdir(parents=True, exist_ok=True)
        cmd = ["rsync", "-az", "-e", ssh_cmd, src, str(local) + "/"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            raise RuntimeError(f"rsync download failed [{self.host}]: {result.stderr[:400]}")

    # ── Connectivity ──────────────────────────────────────────────────────

    def ping(self) -> bool:
        """Return True if SSH connection succeeds."""
        try:
            rc, _, _ = self._ssh("echo ok", timeout=15)
            return rc == 0
        except Exception:
            return False

    def check_python(self) -> str:
        """Return the python binary path that satisfies 3.11+, or raise."""
        for candidate in [self.python, "python3.11", "python3.12", "python3"]:
            rc, out, _ = self._ssh(
                f"{candidate} -c \"import sys; print(sys.version_info[:2])\"",
                timeout=15,
            )
            if rc == 0:
                try:
                    major, minor = eval(out.strip())
                    if (major, minor) >= (3, 11):
                        logger.info("[%s] Python %d.%d → using %s", self.host, major, minor, candidate)
                        return candidate
                except Exception:
                    pass
        raise RuntimeError(
            f"No Python 3.11+ found on {self.host}. "
            "Install via: sudo add-apt-repository ppa:deadsnakes/ppa -y && "
            "sudo apt-get install -y python3.11"
        )

    # ── One-time setup ────────────────────────────────────────────────────

    def setup(
        self,
        scripts_dir: Path,
        library_dir: Path | None,
        model: str = "large-v3",
        warm_model: bool = True,
    ) -> None:
        """
        Idempotent one-time setup:
          1. Verify Python 3.11+
          2. pip install faster-whisper
          3. Upload transcription scripts
          4. Upload forum library (vocab, ~2 MB)
          5. Optionally warm the Whisper model (download + cache, ~3.1 GB)
        """
        logger.info("[%s] Setting up instance...", self.host)

        # 1. Find a good Python
        py = self.check_python()
        self.python = py

        # 2. Install system deps (ffmpeg) + faster-whisper
        logger.info("[%s] Installing ffmpeg...", self.host)
        # Fresh EC2 instances may have a stale apt cache or a lock held by unattended-upgrades.
        # Update first, then install with a 300s lock timeout.
        rc_upd, upd_out, _ = self._ssh(
            "sudo apt-get -o DPkg::Lock::Timeout=300 update -qq 2>&1 | tail -3",
            timeout=360,
        )
        if rc_upd != 0:
            logger.warning("[%s] apt-get update returned %d: %s", self.host, rc_upd, upd_out.strip())
        rc_inst, inst_out, _ = self._ssh(
            "sudo apt-get -o DPkg::Lock::Timeout=300 install -y ffmpeg 2>&1 | tail -5",
            timeout=360,
        )
        if rc_inst != 0:
            logger.warning("[%s] apt-get install ffmpeg returned %d: %s", self.host, rc_inst, inst_out.strip())
        # Verify and capture actual ffmpeg path (DLAMI may have it in conda, not /usr/bin)
        rc2, ffmpeg_path, _ = self._ssh("which ffmpeg", timeout=10)
        if rc2 != 0 or not ffmpeg_path.strip():
            raise RuntimeError(
                f"ffmpeg not found on {self.host} after install attempt. "
                f"apt update rc={rc_upd}, apt install rc={rc_inst}. "
                f"Install output: {inst_out.strip()[:200]}"
            )
        self.ffmpeg_dir = ffmpeg_path.strip().rsplit("/", 1)[0]
        logger.info("[%s] ffmpeg ready at %s", self.host, ffmpeg_path.strip())

        # g4dn.xlarge has 16 GB RAM; transcribe_episodes.py peaks at ~14.5 GB anon-RSS
        # during ECAPA speaker-embedding load (whisper model + pyannote results + full
        # episode waveform all in-memory simultaneously). Add a 16 GB swapfile so the
        # kernel can page rather than OOM-kill the process.
        logger.info("[%s] Enabling swap (16 GB)...", self.host)
        self._ssh(
            "if ! swapon --show | grep -q /swapfile; then "
            "  sudo fallocate -l 16G /swapfile && "
            "  sudo chmod 600 /swapfile && "
            "  sudo mkswap /swapfile && "
            "  sudo swapon /swapfile; "
            "fi",
            timeout=60,
        )
        logger.info("[%s] Swap ready", self.host)

        logger.info("[%s] Installing faster-whisper...", self.host)
        rc, _, err = self._ssh(
            # Pin torch<2.11 to stay compatible with DLAMI's cuDNN 9.10.
            # torch 2.11+ is compiled against cuDNN 9.19 which mismatches.
            # DLAMI ships torch 2.10 pre-installed; the constraint prevents
            # faster-whisper from pulling 2.11+ as a transitive upgrade.
            f"set -o pipefail; {py} -m pip install -q "
            f"'faster-whisper>=1.0.0,<2.0' 'torch>=2.10.0,<2.11' 'torchaudio>=2.10.0,<2.11' "
            f"2>&1 | tail -5",
            timeout=300,
        )
        if rc != 0:
            raise RuntimeError(f"pip install failed on {self.host}: {err[:300]}")
        logger.info("[%s] faster-whisper ready", self.host)

        if self.diarize:
            logger.info("[%s] Installing pyannote.audio + speechbrain...", self.host)
            rc, _, err = self._ssh(
                # Pin exact known-working versions to skip pip's resolver.
                # Remove -q so we can see what's being compiled/downloaded if slow.
                f"set -o pipefail; {py} -m pip install 'pyannote.audio==4.0.4' 'speechbrain==1.0.3' 2>&1 | tail -20",
                timeout=3600,
            )
            if rc != 0:
                raise RuntimeError(
                    f"[{self.host}] pyannote/speechbrain install FAILED — "
                    f"diarization would silently produce speakers_detected=0. "
                    f"stderr: {err[:400]}"
                )
            else:
                logger.info("[%s] pyannote.audio + speechbrain ready", self.host)
            # HF_TOKEN is passed as an env-var prefix on each remote command (env_prefix in
            # process_episode). Writing it to ~/.profile is unnecessary and leaks the token
            # to disk across reboots / snapshots.

        # 3. Create remote directory tree
        self._ssh(
            f"mkdir -p {self.remote_base}/scripts {self.remote_base}/library",
            timeout=15,
        )

        # 4. Upload scripts
        missing: list[str] = []
        for name in REQUIRED_SCRIPTS:
            src = scripts_dir / name
            if src.exists():
                self._rsync_up(src, f"{self.remote_base}/scripts/", timeout=30)
            else:
                missing.append(name)
        if missing:
            logger.warning("[%s] Scripts not found locally, skipping: %s", self.host, missing)
        logger.info("[%s] Scripts uploaded", self.host)

        # 5. Upload forum library (vocab for topic tagging)
        if library_dir and library_dir.exists():
            logger.info("[%s] Uploading forum library...", self.host)
            self._rsync_up(library_dir, f"{self.remote_base}/", timeout=120)
            logger.info("[%s] Library uploaded", self.host)
        else:
            logger.info("[%s] No library dir — topic tagging will be skipped", self.host)

        # 6. Warm model (download to ~/.cache/huggingface — survives instance restart
        #    until the instance is terminated; spot instances should use this for speed)
        if warm_model:
            logger.info("[%s] Warming model %s (~3.1 GB, may take 3-5 min)...", self.host, model)
            warm_cmd = (
                f"{py} -c \""
                f"from faster_whisper import WhisperModel; "
                f"WhisperModel('{model}', device='cuda', compute_type='float16')"
                f"\""
            )
            rc, _, err = self._ssh(warm_cmd, timeout=600)
            if rc != 0:
                logger.warning(
                    "[%s] Model warm failed (will download on first episode): %s",
                    self.host, err[:200],
                )
            else:
                logger.info("[%s] Model warmed and cached ✓", self.host)

            if self.embed_speakers:
                logger.info("[%s] Pre-downloading ECAPA-TDNN embedding model (~200 MB)...", self.host)
                warm_ecapa = (
                    f"{py} -c \""
                    f"from speechbrain.inference.classifiers import EncoderClassifier; "
                    f"import pathlib; "
                    f"EncoderClassifier.from_hparams("
                    f"source='speechbrain/spkrec-ecapa-voxceleb', "
                    f"savedir=str(pathlib.Path.home() / '.cache' / 'speechbrain'), "
                    f"run_opts={{'device': 'cpu'}})"
                    f"\""
                )
                rc, _, err = self._ssh(warm_ecapa, timeout=300)
                if rc != 0:
                    logger.warning("[%s] ECAPA model pre-download failed: %s", self.host, err[:200])
                else:
                    logger.info("[%s] ECAPA model cached ✓", self.host)

        logger.info("[%s] Setup complete", self.host)

    # ── Episode processing ────────────────────────────────────────────────

    def process_episode(
        self,
        episode_dir: Path,
        local_downloads: Path,
        model: str = "large-v3",
        force: bool = True,
    ) -> tuple[bool, str | None]:
        """
        Transcribe one episode on this instance.

        Flow:
          1. rsync audio.mp3 + metadata.json  →  /tmp/td_transcribe/episodes/EPISODE/
          2. Launch transcribe_episodes.py detached via nohup (survives SSH disconnect)
          3. Poll for completion via short SSH heartbeats; reconnects transparently
          4. rsync transcript/ output  →  local downloads/EPISODE/transcript/
          5. rm -rf remote episode dir  (only after successful rsync)

        On disconnect: the remote job continues running.  On reconnect (--hosts
        <same-ip> --skip-setup), discover_episodes() skips already-completed
        episodes and process_episode() checks for an existing done marker before
        launching a new job, so no work is duplicated.
        """
        ep_name = episode_dir.name
        remote_ep = f"{self.remote_base}/episodes/{ep_name}"
        remote_log = f"{self.remote_base}/logs/{ep_name}.log"
        done_marker = (
            f"{remote_ep}/transcript/runs/{self.run_id}/extraction_report.json"
            if self.run_id
            else f"{remote_ep}/transcript/extraction_report.json"
        )

        try:
            # ── 0. Check if already done on remote (reconnect scenario) ───
            rc, _, _ = self._ssh(f"test -f {shlex.quote(done_marker)}", timeout=15)
            if rc == 0:
                logger.info(
                    "[%s] Found existing remote results for %s — skipping transcription",
                    self.host, ep_name,
                )
                # Jump straight to rsync
                remote_transcript = f"{remote_ep}/transcript"
                local_transcript = local_downloads / ep_name / "transcript"
                logger.info("[%s] ↓ Fetching transcript output for %s...", self.host, ep_name)
                self._rsync_down(remote_transcript, local_transcript.parent, timeout=120)
                self._finish_local(local_downloads, ep_name, model)
                try:
                    self._ssh(f"rm -rf {shlex.quote(remote_ep)}", timeout=30)
                except Exception:
                    pass
                return True, None

            # ── 1. Prepare remote dir ──────────────────────────────────────
            rc, _, err = self._ssh(f"mkdir -p {shlex.quote(remote_ep)}", timeout=15)
            if rc != 0:
                return False, f"Failed to create remote dir: {err[:200]}"

            # ── 2. Upload inputs ───────────────────────────────────────────
            audio_path = episode_dir / "audio.mp3"
            metadata_path = episode_dir / "metadata.json"

            if not audio_path.exists():
                return False, f"No audio.mp3 in {ep_name}"

            size_mb = round(audio_path.stat().st_size / 1_048_576)
            logger.info("[%s] ↑ Uploading %s (%s MB)...", self.host, ep_name, size_mb)
            self._rsync_up(audio_path, f"{remote_ep}/", timeout=300)

            if metadata_path.exists():
                self._rsync_up(metadata_path, f"{remote_ep}/", timeout=30)

            # ── 3. Build transcription command ────────────────────────────
            remote_downloads = f"{self.remote_base}/episodes"
            remote_library = f"{self.remote_base}/library"
            remote_script = f"{self.remote_base}/scripts/transcribe_episodes.py"

            # HF_TOKEN is an env-var prefix rather than a --flag so it does not
            # appear in /proc/{pid}/cmdline on the remote host.
            # PATH is set explicitly because nohup sh -c runs a non-interactive,
            # non-login shell whose PATH may not include /usr/bin (where apt
            # installs ffmpeg). Sourcing .bashrc in a nohup context is unreliable.
            # self.ffmpeg_dir is discovered during setup — prepend it so the detached
            # process finds ffmpeg even if it lives in a conda bin (common on DLAMI).
            std_path = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
            if self.ffmpeg_dir and self.ffmpeg_dir not in std_path:
                std_path = f"{self.ffmpeg_dir}:{std_path}"
            env_prefix = f"PATH={std_path} "
            if self.hf_token:
                env_prefix += f"HF_TOKEN={self.hf_token} "
            cmd_parts = [
                f"PYTHONPATH={self.remote_base}/scripts",
                self.python, remote_script,
                "--downloads", remote_downloads,
                "--library", remote_library,
                "--episode", ep_name,
                "--model", model,
                "--device", self.device,
                "--compute-type", self.compute_type,
            ]
            if self.run_id:
                cmd_parts += ["--run-id", self.run_id]
            if self.diarize:
                cmd_parts.append("--diarize")
            if self.embed_speakers:
                cmd_parts.append("--embed-speakers")
            if self.cpu_threads > 0:
                cmd_parts += ["--cpu-threads", str(self.cpu_threads)]
            if force:
                cmd_parts.append("--force")

            remote_cmd = env_prefix + " ".join(cmd_parts)

            # ── 4. Launch detached + poll ──────────────────────────────────
            # GPU transcription: ~11 min; + GPU diarization: ~5 min; total ~16 min typical.
            # CPU transcription: ~30 min; + CPU diarization: ~30 min; total ~60 min.
            if self.device == "cuda":
                job_timeout = 7200    # 2 hrs
            else:
                job_timeout = 14400   # 4 hrs

            logger.info("[%s] ⚡ Transcribing %s on %s (detached)...", self.host, ep_name, self.device.upper())
            t0 = time.monotonic()

            pid = self._launch_detached(remote_cmd, remote_log)
            logger.info(
                "[%s] Job PID %s | log: ssh -i %s %s@%s tail -f %s",
                self.host, pid, self.key_path, self.user, self.host, remote_log,
            )

            self._poll_until_done(done_marker, pid, ep_name, remote_log, timeout=job_timeout)

            elapsed = time.monotonic() - t0
            logger.info("[%s] ✓ Transcription done in %.0f s", self.host, elapsed)

            # ── 5. Retrieve output ─────────────────────────────────────────
            remote_transcript = f"{remote_ep}/transcript"
            local_transcript = local_downloads / ep_name / "transcript"
            local_transcript.mkdir(parents=True, exist_ok=True)

            logger.info("[%s] ↓ Fetching transcript output for %s...", self.host, ep_name)
            self._rsync_down(remote_transcript, local_transcript.parent, timeout=120)

            self._finish_local(local_downloads, ep_name, model)

            # ── 6. Cleanup remote dir (only after successful rsync) ────────
            try:
                self._ssh(f"rm -rf {shlex.quote(remote_ep)}", timeout=30)
                logger.debug("[%s] Remote %s cleaned up", self.host, ep_name)
            except Exception as cleanup_err:
                logger.warning(
                    "[%s] Cleanup warning for %s: %s — remote dir left on instance",
                    self.host, ep_name, cleanup_err,
                )

            return True, None

        except (TimeoutError, RuntimeError) as e:
            # Job monitoring failed or remote job died.  DO NOT clean up the
            # remote dir — partial results may be present and recoverable via
            # --hosts <same-ip> --skip-setup on reconnect.
            logger.warning(
                "[%s] Episode %s failed: %s", self.host, ep_name, e
            )
            logger.warning(
                "[%s] Remote data preserved at %s — rerun with --hosts %s --skip-setup to recover",
                self.host, remote_ep, self.host,
            )
            return False, str(e)

        except Exception as e:
            return False, f"{type(e).__name__}: {e}"

    def _finish_local(self, local_downloads: Path, ep_name: str, model: str) -> None:
        """Update run_manifest.json after a successful rsync."""
        if self.run_id:
            _update_run_manifest(
                local_downloads / ep_name,
                self.run_id,
                {
                    "whisper_model": model,
                    "diarization": self.diarize,
                    "speaker_embeddings": self.embed_speakers and self.diarize,
                    "pipeline_version": PIPELINE_VERSION,
                },
            )


# ---------------------------------------------------------------------------
# Episode discovery  (mirrors transcribe_episodes.py logic)
# ---------------------------------------------------------------------------


def _latest_run_report(episode_dir: Path) -> dict:
    """Return extraction_report dict from the most recent run, or {}."""
    runs_dir = episode_dir / "transcript" / "runs"
    if not runs_dir.exists():
        return {}
    candidates = sorted(
        (r for r in runs_dir.iterdir() if r.is_dir() and (r / "extraction_report.json").exists()),
        key=lambda r: r.name,
        reverse=True,
    )
    if not candidates:
        return {}
    try:
        return json.loads((candidates[0] / "extraction_report.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def _latest_dz_run_has_embeddings(episode_dir: Path) -> bool:
    """Return True if the most recent diarized run has non-empty speaker_embeddings/."""
    runs_dir = episode_dir / "transcript" / "runs"
    if not runs_dir.exists():
        return False
    dz_runs = sorted(
        (r for r in runs_dir.iterdir()
         if r.is_dir() and r.name.endswith("__dz") and (r / "extraction_report.json").exists()),
        key=lambda r: r.name,
        reverse=True,
    )
    if not dz_runs:
        return False
    emb_dir = dz_runs[0] / "speaker_embeddings"
    return emb_dir.is_dir() and bool(list(emb_dir.glob("*.npy")))


def discover_episodes(
    downloads_dir: Path,
    force: bool = False,
    diarize: bool = False,
    embed_speakers: bool = False,
) -> list[tuple[Path, bool]]:
    """Return (episode_dir, per_episode_force) pairs that need transcription.

    When diarize=True, episodes whose latest run has speakers_detected=0 are
    included with force=True so diarization is re-run even if a transcript exists.

    When embed_speakers=True, episodes whose latest diarized run has speakers but
    no .npy files in speaker_embeddings/ are re-queued with force=True.
    """
    episodes: list[tuple[Path, bool]] = []
    for entry in sorted(downloads_dir.iterdir()):
        if not entry.is_dir():
            continue
        audio = entry / "audio.mp3"
        if not audio.exists():
            continue
        if force:
            episodes.append((entry, True))
            continue

        transcript_json = entry / "transcript" / "transcript.json"
        runs_dir = entry / "transcript" / "runs"
        has_transcript = False
        if transcript_json.exists():
            try:
                data = json.loads(transcript_json.read_text(encoding="utf-8"))
                if data.get("status") != "placeholder":
                    has_transcript = True
            except Exception:
                pass
        if not has_transcript and runs_dir.exists() and any(
            r.is_dir() and (r / "transcript.json").exists()
            for r in runs_dir.iterdir()
        ):
            has_transcript = True

        if not has_transcript:
            episodes.append((entry, False))
        elif diarize:
            # Re-run if existing transcript has no speaker diarization
            report = _latest_run_report(entry)
            if report.get("speakers_detected") == 0:
                logger.debug("Re-queuing %s (undiarized run)", entry.name)
                episodes.append((entry, True))
            elif embed_speakers and not _latest_dz_run_has_embeddings(entry):
                # Diarization succeeded but ECAPA embeddings are missing
                logger.debug("Re-queuing %s (missing speaker embeddings)", entry.name)
                episodes.append((entry, True))
        elif embed_speakers:
            # Re-run if diarization succeeded but ECAPA embeddings are missing
            # (used when --embed-speakers is passed without --diarize)
            report = _latest_run_report(entry)
            if report.get("speakers_detected", 0) > 0 and not _latest_dz_run_has_embeddings(entry):
                logger.debug("Re-queuing %s (missing speaker embeddings)", entry.name)
                episodes.append((entry, True))

    return episodes


def discover_test_episodes(downloads_dir: Path) -> list[Path]:
    """Return episodes that have Apple Podcasts transcripts (13 test episodes)."""
    result: list[Path] = []
    for entry in sorted(downloads_dir.iterdir()):
        if not entry.is_dir():
            continue
        sources = entry / "transcript" / "sources.json"
        if not sources.exists():
            continue
        try:
            data = json.loads(sources.read_text(encoding="utf-8"))
            if data.get("sources", {}).get("apple_podcasts_cache"):
                result.append(entry)
        except Exception:
            continue
    return result


# ---------------------------------------------------------------------------
# Status tracking
# ---------------------------------------------------------------------------


@dataclass
class BatchStatus:
    run_id: str
    mode: str
    model: str
    hosts: list[str]
    started_at: str = field(default_factory=now_iso)
    state: str = "running"
    total_queued: int = 0
    total_processed: int = 0
    total_succeeded: int = 0
    total_failed: int = 0
    current_episodes: dict[str, str] = field(default_factory=dict)  # host → episode
    succeeded: list[str] = field(default_factory=list)
    failed: list[dict] = field(default_factory=list)


def save_status(status: BatchStatus, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "run_id": status.run_id,
        "mode": status.mode,
        "started_at": status.started_at,
        "updated_at": now_iso(),
        "model": status.model,
        "hosts": status.hosts,
        "state": status.state,
        "total_queued": status.total_queued,
        "total_processed": status.total_processed,
        "total_succeeded": status.total_succeeded,
        "total_failed": status.total_failed,
        "current_episodes": status.current_episodes,
        "succeeded": status.succeeded,
        "failed": status.failed,
    }
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Batch runner
# ---------------------------------------------------------------------------


def run_aws_batch(
    workers: list[RemoteWorker],
    episodes: list[tuple[Path, bool]],
    local_downloads: Path,
    model: str = "large-v3",
    force: bool = True,
    mode: str = "full",
    status_path: Path | None = None,
) -> None:
    """
    Distribute episodes across workers.  Each worker processes one episode at
    a time (GPU serialises anyway).  Multiple workers = multiple instances
    running different episodes simultaneously.
    """
    run_id = f"aws_{mode}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    status_path = status_path or Path("analysis/transcription/aws_status.json")

    status = BatchStatus(
        run_id=run_id,
        mode=mode,
        model=model,
        hosts=[w.host for w in workers],
    )
    status.total_queued = len(episodes)
    save_status(status, status_path)
    state_lock = threading.Lock()

    # Shared queue — any free worker picks the next episode
    episode_queue: list[tuple[Path, bool]] = list(episodes)
    queue_lock = threading.Lock()

    logger.info("=" * 70)
    logger.info("AWS Batch  run_id=%s  mode=%s  episodes=%d  instances=%d",
                run_id, mode, len(episodes), len(workers))
    logger.info("Status file: %s", status_path)
    logger.info("=" * 70)

    def worker_loop(w: RemoteWorker) -> None:
        while True:
            with queue_lock:
                if not episode_queue:
                    break
                ep, ep_force = episode_queue.pop(0)
                idx = status.total_processed + len(episode_queue) + 1  # approximate

            with state_lock:
                status.current_episodes[w.host] = ep.name
                save_status(status, status_path)

            logger.info("[%s] Processing %s", w.host, ep.name)
            t0 = time.monotonic()
            success, error = w.process_episode(
                episode_dir=ep,
                local_downloads=local_downloads,
                model=model,
                force=force or ep_force,
            )
            elapsed = time.monotonic() - t0

            with state_lock:
                status.total_processed += 1
                status.current_episodes.pop(w.host, None)
                if success:
                    status.total_succeeded += 1
                    status.succeeded.append(ep.name)
                    logger.info("✓ [%s] %s (%.0f s)", w.host, ep.name, elapsed)
                else:
                    status.total_failed += 1
                    status.failed.append({
                        "episode": ep.name,
                        "host": w.host,
                        "error": error or "unknown",
                    })
                    logger.error("✗ [%s] %s — %s", w.host, ep.name, error)
                save_status(status, status_path)

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(workers)) as pool:
        futs = [pool.submit(worker_loop, w) for w in workers]
        for fut in concurrent.futures.as_completed(futs):
            try:
                fut.result()
            except Exception as e:
                logger.error("Worker thread error: %s", e)

    status.state = "completed" if status.total_failed == 0 else "completed_with_errors"
    save_status(status, status_path)

    logger.info("=" * 70)
    logger.info("Batch complete — %d/%d succeeded, %d failed",
                status.total_succeeded, status.total_queued, status.total_failed)
    if status.failed:
        logger.info("Failed episodes:")
        for f in status.failed:
            logger.error("  %s  [%s]  %s", f["episode"], f["host"], f["error"])
    logger.info("=" * 70)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# EC2 Provisioning
# ---------------------------------------------------------------------------


class SSOTokenExpiredError(RuntimeError):
    """Raised when the AWS SSO token has expired and needs manual refresh."""


def _aws(args: list[str], check: bool = True) -> dict | list | str:
    """Run an AWS CLI command and return parsed JSON output."""
    cmd = ["aws"] + args + ["--output", "json", "--region", EC2_DEFAULTS["region"]]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        stderr = result.stderr[:400]
        if "token has expired" in stderr.lower():
            raise SSOTokenExpiredError(f"aws {args[0]} failed: {stderr}")
        raise RuntimeError(f"aws {args[0]} failed: {stderr}")
    if result.stdout.strip():
        return json.loads(result.stdout)
    return {}


def _aws_r(args: list[str], check: bool = True, max_wait_s: int = 7200) -> dict | list | str:
    """Like _aws() but waits up to max_wait_s for manual SSO refresh on token expiry.

    When the SSO token expires the function logs a prominent warning every 60 s
    and retries automatically once the user runs ``aws sso login`` in a terminal.
    All in-flight AWS calls in other threads will also block, which is correct —
    every AWS operation needs valid credentials.
    """
    wait = 60
    deadline = time.monotonic() + max_wait_s
    while True:
        try:
            return _aws(args, check=check)
        except SSOTokenExpiredError:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise
            logger.warning(
                "AWS SSO token expired — run 'aws sso login' in a terminal to refresh. "
                "Retrying in %d s (will keep trying for %.0f more min).",
                wait,
                remaining / 60,
            )
            time.sleep(min(wait, remaining))
            wait = min(wait * 2, 300)


def provision_spot_instances(
    count: int,
    az: str | None = None,
    instance_type: str | None = None,
) -> list[str]:
    """
    Request `count` spot instances and return their public IPs
    once they are running and SSH-reachable.

    Uses the pre-configured AMI, key pair, and security group in EC2_DEFAULTS.
    Instances are tagged `td-transcription` for easy identification and cleanup.
    """
    instance_type = instance_type or EC2_DEFAULTS["instance_type"]
    vpc_id = _get_default_vpc()

    # Collect subnets to try. If az is specified, filter to that AZ only.
    # Otherwise collect all VPC subnets and sort best_az first (spot capacity
    # varies by AZ — we retry each in turn on InsufficientInstanceCapacity).
    subnet_filters = [f"Name=vpc-id,Values={vpc_id}"]
    if az:
        subnet_filters.append(f"Name=availabilityZone,Values={az}")
    all_subnets_resp = _aws_r(["ec2", "describe-subnets", "--filters"] + subnet_filters)
    all_subnets = all_subnets_resp.get("Subnets", [])
    if not all_subnets:
        raise RuntimeError(f"No subnet found (vpc={vpc_id}, az={az or 'any'})")
    # Sort: prefer best_az first, then alphabetical for determinism.
    best_az = EC2_DEFAULTS.get("best_az", "")
    all_subnets.sort(key=lambda s: (0 if s.get("AvailabilityZone") == best_az else 1,
                                    s.get("AvailabilityZone", "")))
    logger.info("Requesting %d × %s spot instance(s) — will try %d AZ(s): %s",
                count, instance_type, len(all_subnets),
                [s["AvailabilityZone"] for s in all_subnets])

    run_instances_args = [
        "ec2", "run-instances",
        "--image-id", EC2_DEFAULTS["ami_id"],
        "--instance-type", instance_type,
        "--key-name", EC2_DEFAULTS["key_name"],
        "--security-group-ids", EC2_DEFAULTS["security_group_id"],
        "--count", str(count),
        "--block-device-mappings",
        json.dumps([{
            "DeviceName": "/dev/sda1",
            "Ebs": {"VolumeSize": 100, "VolumeType": "gp3", "DeleteOnTermination": True},
        }]),
        "--instance-market-options",
        json.dumps({
            "MarketType": "spot",
            "SpotOptions": {
                "MaxPrice": EC2_DEFAULTS["spot_max_price"],
                "SpotInstanceType": "one-time",
            },
        }),
        "--tag-specifications",
        json.dumps([{
            "ResourceType": "instance",
            "Tags": [
                {"Key": "Name", "Value": "td-transcription"},
                {"Key": "Project", "Value": "purefoy"},
            ],
        }]),
    ]

    result = None
    last_err: Exception | None = None
    for subnet in all_subnets:
        subnet_id = subnet["SubnetId"]
        subnet_az = subnet.get("AvailabilityZone", "?")
        logger.info("Trying subnet %s (%s)...", subnet_id, subnet_az)
        try:
            result = _aws_r(run_instances_args + ["--subnet-id", subnet_id])
            logger.info("Launched in %s", subnet_az)
            break
        except RuntimeError as exc:
            if "InsufficientInstanceCapacity" in str(exc):
                logger.warning("No capacity in %s, trying next AZ...", subnet_az)
                last_err = exc
                continue
            raise
    if result is None:
        raise RuntimeError(
            f"InsufficientInstanceCapacity in all AZs tried. Last error: {last_err}"
        )

    instance_ids = [i["InstanceId"] for i in result.get("Instances", [])]
    if not instance_ids:
        raise RuntimeError("No instances returned from run-instances")
    logger.info("Launched instances: %s", instance_ids)

    # Wait until running
    logger.info("Waiting for instances to reach 'running' state...")
    _aws_r(["ec2", "wait", "instance-running", "--instance-ids"] + instance_ids, check=True)
    logger.info("All instances running")

    # Get public IPs
    desc = _aws_r(["ec2", "describe-instances", "--instance-ids"] + instance_ids)
    ips: list[str] = []
    for res in desc["Reservations"]:
        for inst in res["Instances"]:
            ip = inst.get("PublicIpAddress")
            if ip:
                ips.append(ip)
            else:
                logger.warning("Instance %s has no public IP", inst["InstanceId"])

    logger.info("Instance IPs: %s", ips)
    return ips, instance_ids


def terminate_instances(instance_ids: list[str]) -> None:
    """Terminate a specific list of instances (only those launched in this run)."""
    if not instance_ids:
        logger.info("No instances to terminate")
        return
    logger.info("Terminating %d instance(s): %s", len(instance_ids), instance_ids)
    _aws_r(["ec2", "terminate-instances", "--instance-ids"] + instance_ids)
    logger.info("Termination requested — instances will shut down shortly")


def _get_default_vpc() -> str:
    """Return the default VPC ID for the configured region."""
    result = _aws_r(["ec2", "describe-vpcs", "--filters", "Name=isDefault,Values=true"])
    vpcs = result.get("Vpcs", [])
    if not vpcs:
        raise RuntimeError("No default VPC found in " + EC2_DEFAULTS["region"])
    return vpcs[0]["VpcId"]


def update_sg_ssh_rule() -> None:
    """Update the td-transcription SG to allow SSH from the current public IP."""
    sg_id = EC2_DEFAULTS["security_group_id"]
    try:
        resp = urllib.request.urlopen("https://checkip.amazonaws.com", timeout=10)
        my_ip = resp.read().decode().strip()
    except Exception as exc:
        logger.warning("Could not determine public IP — skipping SG update: %s", exc)
        return

    cidr = f"{my_ip}/32"
    # Get existing SSH ingress rules
    sg_info = _aws_r(["ec2", "describe-security-groups", "--group-ids", sg_id])
    existing_ssh = [
        r for r in sg_info["SecurityGroups"][0]["IpPermissions"]
        if r.get("FromPort") == 22 and r.get("IpProtocol") == "tcp"
    ]
    existing_cidrs = {
        r["CidrIp"]
        for perm in existing_ssh
        for r in perm.get("IpRanges", [])
    }

    if cidr in existing_cidrs:
        logger.info("SG SSH rule already allows %s — no update needed", cidr)
        return

    # Revoke only CIDRs that are not the current IP — leave any other team member rules intact.
    for perm in existing_ssh:
        stale = [r for r in perm.get("IpRanges", []) if r["CidrIp"] != cidr]
        if not stale:
            continue
        stale_perm = dict(perm)
        stale_perm["IpRanges"] = stale
        _aws_r(["ec2", "revoke-security-group-ingress",
               "--group-id", sg_id,
               "--ip-permissions", json.dumps([stale_perm])])
        for r in stale:
            logger.info("Revoked stale SSH rule: %s", r["CidrIp"])

    # Authorize current IP
    _aws_r(["ec2", "authorize-security-group-ingress",
            "--group-id", sg_id,
            "--protocol", "tcp", "--port", "22",
            "--cidr", cidr])
    logger.info("SG updated — SSH allowed from %s", cidr)


def wait_for_ssh(ips: list[str], key_path: Path, user: str = "ubuntu",
                 timeout_s: int = 360) -> None:
    """Poll SSH connectivity until all instances accept connections."""
    logger.info("Waiting for SSH to become available on %d instance(s)...", len(ips))
    deadline = time.monotonic() + timeout_s
    pending = set(ips)
    while pending and time.monotonic() < deadline:
        for ip in list(pending):
            result = subprocess.run(
                ["ssh",
                 "-i", str(key_path),
                 "-o", "BatchMode=yes",
                 "-o", "StrictHostKeyChecking=accept-new",
                 "-o", "ConnectTimeout=5",
                 f"{user}@{ip}", "echo ok"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                logger.info("  ✓ SSH ready: %s", ip)
                pending.discard(ip)
        if pending:
            time.sleep(10)
    if pending:
        raise RuntimeError(f"SSH not ready after {timeout_s}s on: {pending}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="AWS remote transcription runner — GPU compute, local output",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--hosts", default="",
        help="Comma-separated EC2 IP addresses or DNS names. "
             "Not required when using --provision (IPs are discovered automatically).",
    )
    p.add_argument(
        "--key", required=True, type=Path,
        help="Path to SSH private key (.pem file)",
    )
    p.add_argument(
        "--user", default="ubuntu",
        help="SSH username on EC2 instances (default: ubuntu)",
    )
    p.add_argument(
        "--python", default="python3",
        help="Python executable on remote (default: python3; try python3.11 if needed)",
    )
    p.add_argument(
        "--downloads", type=Path, default=Path("./downloads"),
        help="Local downloads directory (default: ./downloads)",
    )
    p.add_argument(
        "--library", type=Path, default=Path("./library"),
        help="Local library directory for forum vocab (default: ./library)",
    )
    p.add_argument(
        "--scripts-dir", type=Path, default=Path("./scripts/tools"),
        help="Directory containing transcribe_episodes.py etc. (default: ./scripts/tools)",
    )
    p.add_argument(
        "--model", default="large-v3",
        help="Whisper model name (default: large-v3)",
    )
    p.add_argument(
        "--mode", choices=["test", "full", "episode"], default="full",
        help="Run mode: test (13 Apple episodes), full (all pending), episode (single)",
    )
    p.add_argument(
        "--episode",
        help="Specific episode directory name — required for --mode episode",
    )
    p.add_argument(
        "--force", action="store_true", default=False,
        help="Re-transcribe even if transcript.json already exists",
    )
    p.add_argument(
        "--no-force", dest="force", action="store_false",
        help="Skip episodes that already have a transcript.json",
    )
    p.add_argument(
        "--limit", type=int, default=0, metavar="N",
        help="Cap the episode queue at N episodes (0 = no limit). Applied after discovery.",
    )
    p.add_argument(
        "--device", default="cuda", choices=["cuda", "cpu", "auto"],
        help="Compute device on remote instance (default: cuda). Use cpu for non-GPU instances.",
    )
    p.add_argument(
        "--compute-type", default="float16",
        choices=["float16", "int8", "int8_float16", "float32"],
        help="Quantization type (default: float16 for GPU; use int8 for CPU).",
    )
    p.add_argument(
        "--cpu-threads", type=int, default=0,
        help="CPU threads for faster-whisper (default: 0 = auto). Recommended: vCPU count.",
    )
    p.add_argument(
        "--instance-type", default=EC2_DEFAULTS["instance_type"],
        help=f"EC2 instance type to provision (default: {EC2_DEFAULTS['instance_type']}). "
             "Use c5.4xlarge for CPU-only (standard spot quota).",
    )
    p.add_argument(
        "--provision", type=int, metavar="N",
        help=(
            "Auto-provision N spot instances, run the batch, "
            "then terminate them. Requires AWS CLI configured. "
            "Uses pre-configured AMI/key/SG in EC2_DEFAULTS."
        ),
    )
    p.add_argument(
        "--provision-az", default="",
        help="AZ to provision in (default: empty = let AWS pick for best spot capacity). "
             f"Cheapest historically: {EC2_DEFAULTS['best_az']}",
    )
    p.add_argument(
        "--setup-only", action="store_true",
        help="Run instance setup (install deps, warm model) then exit",
    )
    p.add_argument(
        "--skip-setup", action="store_true",
        help="Skip setup step (use if instances are already configured)",
    )
    p.add_argument(
        "--status-file", type=Path,
        default=Path("analysis/transcription/aws_status.json"),
        help="Path to write status JSON (default: analysis/transcription/aws_status.json)",
    )
    p.add_argument(
        "--diarize", action="store_true",
        help="Enable speaker diarization via pyannote (runs on CPU alongside GPU Whisper). "
             "Requires --hf-token or HF_TOKEN env var.",
    )
    p.add_argument(
        "--hf-token", default=None,
        help="HuggingFace token for pyannote model access. "
             "Defaults to HF_TOKEN environment variable.",
    )
    p.add_argument(
        "--embed-speakers", action="store_true",
        help="Export ECAPA-TDNN speaker embeddings per cluster after diarization. "
             "Requires --diarize. Enables cross-episode speaker clustering (B3).",
    )
    p.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable DEBUG logging",
    )
    return p


def main() -> None:
    args = build_parser().parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    key_path = args.key.expanduser()

    if not args.hosts and not args.provision:
        logger.error("Either --hosts or --provision N is required")
        sys.exit(1)

    # Resolve HF token (CLI arg > env var)
    hf_token: str | None = args.hf_token or os.environ.get("HF_TOKEN")
    if args.diarize and not hf_token:
        logger.error("--diarize requires a HuggingFace token. "
                     "Pass --hf-token or set HF_TOKEN environment variable.")
        sys.exit(1)

    # Generate a single run_id shared across all episodes in this batch
    run_id = make_run_id(args.model, args.diarize)
    logger.info("Batch run_id: %s", run_id)

    # ── Auto-provision mode ──────────────────────────────────────────────────
    provisioned_ids: list[str] = []
    if args.provision:
        if not args.provision > 0:
            logger.error("--provision N must be > 0")
            sys.exit(1)
        # Use the pre-configured key if --key is still the default placeholder
        if not key_path.exists():
            default_key = Path(EC2_DEFAULTS["default_key_path"]).expanduser()
            if default_key.exists():
                key_path = default_key
                logger.info("Using default key: %s", key_path)
            else:
                logger.error("Key not found at %s — specify --key or run aws_runner.py setup", key_path)
                sys.exit(1)

        provisioned_ids: list[str] = []
        try:
            ips, provisioned_ids = provision_spot_instances(
                args.provision, az=args.provision_az, instance_type=args.instance_type,
            )
            update_sg_ssh_rule()
            wait_for_ssh(ips, key_path, user=args.user)
            # Patch args.hosts so the rest of main() uses the provisioned IPs
            args.hosts = ",".join(ips)
        except Exception as e:
            logger.error("Provisioning failed: %s", e)
            terminate_instances(provisioned_ids)
            sys.exit(1)

    # ── Build workers from host list ─────────────────────────────────────────
    hosts = [h.strip() for h in args.hosts.split(",") if h.strip()]
    workers = [
        RemoteWorker(
            host=h,
            key_path=key_path,
            user=args.user,
            python=args.python,
            device=args.device,
            compute_type=args.compute_type,
            cpu_threads=args.cpu_threads,
            run_id=run_id,
            diarize=args.diarize,
            hf_token=hf_token,
            embed_speakers=args.embed_speakers,
        )
        for h in hosts
    ]

    # Verify SSH connectivity
    logger.info("Checking connectivity to %d instance(s)...", len(workers))
    bad: list[str] = []
    for w in workers:
        if w.ping():
            logger.info("  ✓ %s reachable", w.host)
        else:
            logger.error("  ✗ %s — cannot connect (check IP, key, security group port 22)", w.host)
            bad.append(w.host)
    if bad:
        if args.provision:
            terminate_instances(provisioned_ids)
        sys.exit(1)

    # Setup (idempotent; skippable)
    if not args.skip_setup:
        warm = True  # Always warm model — preflight will catch missing cache otherwise
        logger.info("Running setup on %d instance(s)%s...",
                    len(workers), " (model warm included)" if warm else "")
        setup_ok = True
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(workers)) as pool:
            futs = {
                pool.submit(
                    w.setup, args.scripts_dir, args.library, args.model, warm
                ): w
                for w in workers
            }
            for fut in concurrent.futures.as_completed(futs):
                w = futs[fut]
                try:
                    fut.result()
                except Exception as e:
                    logger.error("Setup failed for %s: %s", w.host, e)
                    setup_ok = False
        if not setup_ok:
            if args.provision:
                logger.info("Setup failed — terminating provisioned instance(s)...")
                terminate_instances(provisioned_ids)
            sys.exit(1)

    if args.setup_only:
        logger.info("Setup complete. Run without --setup-only to begin transcription.")
        return

    # Discover episodes
    if args.mode == "test":
        raw_eps = discover_test_episodes(args.downloads)
        if not raw_eps:
            logger.error(
                "No test episodes found — expected episodes with sources.json "
                "containing apple_podcasts_cache entry in %s", args.downloads,
            )
            sys.exit(1)
        logger.info("Test mode: %d Apple-transcribed episodes queued", len(raw_eps))
        episodes = [(ep, args.force) for ep in raw_eps]

    elif args.mode == "episode":
        if not args.episode:
            logger.error("--episode EPISODE_DIR is required for --mode episode")
            sys.exit(1)
        ep_path = args.downloads / args.episode
        if not ep_path.exists():
            logger.error("Episode directory not found: %s", ep_path)
            sys.exit(1)
        episodes = [(ep_path, args.force)]
        logger.info("Single episode mode: %s", args.episode)

    else:  # full
        episodes = discover_episodes(
            args.downloads,
            force=args.force,
            diarize=args.diarize,
            embed_speakers=args.embed_speakers,
        )
        if not episodes:
            logger.info("No episodes pending transcription.")
            return
        if args.limit > 0:
            episodes = episodes[:args.limit]
        rerun_count = sum(1 for _, f in episodes if f)
        logger.info("Full mode: %d episodes queued%s", len(episodes),
                    f" ({rerun_count} force re-runs)" if rerun_count else "")

    # Run — always terminate provisioned instances on exit (success or error)
    try:
        run_aws_batch(
            workers=workers,
            episodes=episodes,
            local_downloads=args.downloads,
            model=args.model,
            force=args.force,
            mode=args.mode,
            status_path=args.status_file,
        )
    finally:
        if args.provision:
            logger.info("Batch complete — terminating %d provisioned instance(s)...", args.provision)
            terminate_instances(provisioned_ids)


if __name__ == "__main__":
    main()
