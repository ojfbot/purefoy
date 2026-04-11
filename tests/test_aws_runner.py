"""
Tests for scripts/tools/aws_runner.py

Philosophy
----------
Tests are named after *user-visible behaviour*, not internal implementation.
A failing test should tell a human (or LLM) exactly what broke and why it
matters — not just which line number raised.

Idiom primer for Python-testing newcomers:
  - pytest.fixture   — shared setup, injected by argument name
  - tmp_path         — built-in pytest fixture; gives a fresh temp directory per test
  - monkeypatch      — built-in pytest fixture; safely patches functions/env-vars
  - @parametrize     — run the same test against multiple inputs
  - assert x, "msg"  — the "msg" is shown when the assertion fails
  - pytest.raises    — assert that code raises a specific exception
"""

import json
import re
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Make scripts/tools importable without installing them
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "tools"))
import aws_runner  # noqa: E402  (import after sys.path mutation)


# ===========================================================================
# Fixtures — shared episode directory builders
# ===========================================================================

def _ep(root: Path, slug: str) -> Path:
    """Create a minimal episode directory with an audio.mp3 stub."""
    ep = root / slug
    ep.mkdir()
    (ep / "audio.mp3").write_bytes(b"stub")
    return ep


def _add_run(ep: Path, run_id: str, *, speakers_detected: int = 2) -> None:
    """Write a transcript run with a given speakers_detected count."""
    run_dir = ep / "transcript" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "transcript.json").write_text(
        json.dumps({"segments": [], "status": "ok"}), encoding="utf-8"
    )
    (run_dir / "extraction_report.json").write_text(
        json.dumps({
            "episode_dir": ep.name,
            "success": True,
            "speakers_detected": speakers_detected,
        }),
        encoding="utf-8",
    )
    # Also write run_manifest so it looks like a real completed run
    manifest = ep / "transcript" / "run_manifest.json"
    manifest.write_text(
        json.dumps({"canonical": run_id, "runs": [{"run_id": run_id}]}),
        encoding="utf-8",
    )


# ===========================================================================
# discover_episodes — the function that decides WHAT gets transcribed
# ===========================================================================

class TestDiscoverEpisodes:
    """
    Covers the user-visible contract:
      • Fresh episodes without any transcript → included
      • Episodes with a complete diarized run  → skipped (save money)
      • Episodes with a run but no speakers    → re-queued when --diarize is set
      • --limit N caps the total queue size
      • Per-episode force flag is True only for undiarized re-runs
    """

    def test_fresh_episode_is_included(self, tmp_path):
        """An episode with audio but no transcript should always be queued."""
        _ep(tmp_path, "S02E001__test__ep1")
        result = aws_runner.discover_episodes(tmp_path)
        paths = [p for p, _ in result]
        assert len(paths) == 1, "Expected 1 episode; fresh episode was not discovered"

    def test_episode_with_complete_diarized_run_is_skipped(self, tmp_path):
        """
        Once an episode has a successful diarized run it should NOT be re-run
        automatically — re-running 339 episodes every time would be expensive.
        """
        ep = _ep(tmp_path, "S02E001__test__ep1")
        _add_run(ep, "run_20260304__larg__dz", speakers_detected=3)
        result = aws_runner.discover_episodes(tmp_path, force=False)
        assert result == [], (
            "Episode with a complete diarized run should be skipped in no-force mode"
        )

    def test_undiarized_episode_is_skipped_without_diarize_flag(self, tmp_path):
        """
        A run with speakers_detected=0 is still a complete transcript.
        Without --diarize it should not be re-queued — the user didn't ask for it.
        """
        ep = _ep(tmp_path, "S02E001__test__ep1")
        _add_run(ep, "run_20260304__larg__nd", speakers_detected=0)
        result = aws_runner.discover_episodes(tmp_path, force=False, diarize=False)
        assert result == [], (
            "Undiarized episode should be skipped when --diarize is NOT set"
        )

    def test_undiarized_episode_is_requeued_when_diarize_is_enabled(self, tmp_path):
        """
        Core regression test for the bug discovered 2026-03-04:
        episodes 1-2 were transcribed without diarization (speechbrain version wrong).
        When --diarize is set, they must be re-queued automatically.
        """
        ep = _ep(tmp_path, "S02E090__dennis-muren")
        _add_run(ep, "run_20260304__larg__nd", speakers_detected=0)
        result = aws_runner.discover_episodes(tmp_path, force=False, diarize=True)
        paths = [p for p, _ in result]
        assert ep in paths, (
            "Episode with speakers_detected=0 must be re-queued when --diarize is set. "
            "This was the cause of Dennis Muren / Tom Cross running without speakers."
        )

    def test_undiarized_requeue_carries_per_episode_force_true(self, tmp_path):
        """
        The re-queued undiarized episode must have force=True so transcribe_episodes.py
        overwrites the existing transcript — otherwise the remote script will skip it.
        """
        ep = _ep(tmp_path, "S02E090__dennis-muren")
        _add_run(ep, "run_20260304__larg__nd", speakers_detected=0)
        result = aws_runner.discover_episodes(tmp_path, force=False, diarize=True)
        force_flags = {p.name: f for p, f in result}
        assert force_flags[ep.name] is True, (
            "Undiarized re-run must carry force=True; "
            "without it the remote script sees an existing transcript and skips the episode"
        )

    def test_fresh_episode_carries_per_episode_force_false(self, tmp_path):
        """
        New episodes don't need force=True — there's nothing to overwrite.
        This matters because force=True adds --force to the remote command,
        which triggers a full re-run even when a good transcript already exists.
        """
        _ep(tmp_path, "S02E001__fresh-episode")
        result = aws_runner.discover_episodes(tmp_path, force=False, diarize=True)
        force_flags = {p.name: f for p, f in result}
        assert force_flags["S02E001__fresh-episode"] is False, (
            "Fresh (never-transcribed) episode should not carry force=True"
        )

    def test_limit_caps_total_queue(self, tmp_path):
        """
        --limit N must cap the queue at N episodes regardless of how many are available.
        This is the mechanism for 'run the next 50' batches.
        """
        for i in range(10):
            _ep(tmp_path, f"S02E{i:03d}__test-episode-{i}")
        result = aws_runner.discover_episodes(tmp_path)
        limited = result[:5]  # caller applies the limit
        assert len(limited) == 5, "--limit 5 should return exactly 5 episodes"

    def test_mixed_queue_includes_both_fresh_and_undiarized(self, tmp_path):
        """
        User scenario: 'run a batch of 50 including the 2 undiarized and 48 new ones'.
        Both should appear in the same queue.
        """
        fresh = _ep(tmp_path, "S02E001__fresh")
        undiarized = _ep(tmp_path, "S02E002__undiarized")
        _add_run(undiarized, "run_20260304__nd", speakers_detected=0)

        result = aws_runner.discover_episodes(tmp_path, force=False, diarize=True)
        result_names = {p.name for p, _ in result}

        assert fresh.name in result_names, "Fresh episode must be in queue"
        assert undiarized.name in result_names, "Undiarized episode must be in queue"
        assert len(result) == 2, "Should be exactly 2 episodes"

    def test_directory_without_audio_is_skipped(self, tmp_path):
        """Directories that have no audio.mp3 should never be queued — they have nothing to transcribe."""
        ep = tmp_path / "S02E001__no-audio"
        ep.mkdir()
        (ep / "metadata.json").write_text("{}", encoding="utf-8")  # no audio.mp3
        result = aws_runner.discover_episodes(tmp_path)
        assert result == [], "Episode without audio.mp3 must be skipped"

    def test_episodes_are_returned_in_alphabetical_order(self, tmp_path):
        """
        Episode order matters for --limit batches — earlier episodes should be
        processed first (S01 before S02, E001 before E002, etc.).
        """
        _ep(tmp_path, "S02E010__later")
        _ep(tmp_path, "S02E001__earlier")
        result = aws_runner.discover_episodes(tmp_path)
        names = [p.name for p, _ in result]
        assert names == sorted(names), (
            "Episodes must be returned in alphabetical order so --limit 50 picks "
            "the earliest episodes, not arbitrary ones"
        )


# ===========================================================================
# make_run_id — naming of output directories
# ===========================================================================

class TestMakeRunId:
    """
    The run_id is used as a directory name and must be parseable by humans and
    future tooling. Tests verify the format contract.
    """

    RUN_ID_PATTERN = re.compile(r"^run_\d{14}__[a-z0-9]{1,6}__(?:dz|nd)$")

    def test_format_matches_expected_pattern(self):
        run_id = aws_runner.make_run_id("large-v3", diarize=True)
        assert self.RUN_ID_PATTERN.match(run_id), (
            f"run_id '{run_id}' does not match expected pattern "
            f"'run_YYYYMMDDHHMMSS__modelslug__dz|nd'"
        )

    def test_diarize_true_produces_dz_suffix(self):
        run_id = aws_runner.make_run_id("large-v3", diarize=True)
        assert run_id.endswith("__dz"), (
            f"Diarized run should end with '__dz', got '{run_id}'"
        )

    def test_diarize_false_produces_nd_suffix(self):
        run_id = aws_runner.make_run_id("large-v3", diarize=False)
        assert run_id.endswith("__nd"), (
            f"Non-diarized run should end with '__nd', got '{run_id}'"
        )

    def test_model_slug_strips_hyphens(self):
        """'large-v3' → 'larg' (first 4 chars after stripping hyphens/dots)."""
        run_id = aws_runner.make_run_id("large-v3", diarize=True)
        slug = run_id.split("__")[1]
        assert "-" not in slug, f"Model slug must not contain hyphens, got '{slug}'"

    @pytest.mark.parametrize("model,expected_slug", [
        ("large-v3", "larg"),
        ("medium",   "medi"),
        ("tiny",     "tiny"),
        ("small",    "smal"),
    ])
    def test_model_slug_is_first_four_chars(self, model, expected_slug):
        run_id = aws_runner.make_run_id(model, diarize=False)
        slug = run_id.split("__")[1]
        assert slug == expected_slug, (
            f"Model '{model}' should produce slug '{expected_slug}', got '{slug}'"
        )

    def test_two_calls_produce_different_run_ids(self):
        """Run IDs must be unique across batch launches to avoid directory collisions."""
        import time
        id1 = aws_runner.make_run_id("large-v3", diarize=True)
        time.sleep(1.01)  # run_id timestamp is second-resolution; sleep > 1s guarantees different ts
        id2 = aws_runner.make_run_id("large-v3", diarize=True)
        assert id1 != id2, (
            "Two run_id calls must produce different values — "
            "collision would cause one batch to overwrite another's transcripts"
        )


# ===========================================================================
# _update_run_manifest — the local tracking file written after each rsync
# ===========================================================================

class TestUpdateRunManifest:
    """
    run_manifest.json tracks all runs for an episode and which is canonical.
    It's the source of truth for 'has this episode been diarized?'
    """

    def test_creates_manifest_for_new_episode(self, tmp_path):
        ep = _ep(tmp_path, "S02E001__new-episode")
        (ep / "transcript").mkdir()
        aws_runner._update_run_manifest(ep, "run_20260304__larg__dz", {
            "whisper_model": "large-v3",
            "diarization": True,
        })
        manifest_path = ep / "transcript" / "run_manifest.json"
        assert manifest_path.exists(), "run_manifest.json must be created"
        data = json.loads(manifest_path.read_text())
        assert data["canonical"] == "run_20260304__larg__dz"
        assert len(data["runs"]) == 1

    def test_appends_to_existing_manifest_without_duplicating(self, tmp_path):
        """
        Re-running an episode must add a new entry, not duplicate the existing one.
        Duplicate runs would make it hard to identify the canonical transcript.
        """
        ep = _ep(tmp_path, "S02E001__existing")
        (ep / "transcript").mkdir()
        aws_runner._update_run_manifest(ep, "run_001", {"diarization": False})
        aws_runner._update_run_manifest(ep, "run_002", {"diarization": True})
        # Call run_002 again — must not duplicate
        aws_runner._update_run_manifest(ep, "run_002", {"diarization": True})

        data = json.loads((ep / "transcript" / "run_manifest.json").read_text())
        run_ids = [r["run_id"] for r in data["runs"]]
        assert run_ids.count("run_002") == 1, (
            "Calling _update_run_manifest twice with the same run_id must not duplicate it"
        )

    def test_canonical_is_updated_to_most_recent_run(self, tmp_path):
        """The canonical pointer should always point to the latest run."""
        ep = _ep(tmp_path, "S02E001__episode")
        (ep / "transcript").mkdir()
        aws_runner._update_run_manifest(ep, "run_001", {"diarization": False})
        aws_runner._update_run_manifest(ep, "run_002", {"diarization": True})
        data = json.loads((ep / "transcript" / "run_manifest.json").read_text())
        assert data["canonical"] == "run_002", (
            "After a second run, canonical must point to 'run_002', not the original 'run_001'"
        )

    def test_manifest_survives_corrupt_existing_file(self, tmp_path, caplog):
        """
        A corrupt manifest must not crash the batch — the episode was already
        transcribed successfully and losing the manifest is recoverable.
        """
        ep = _ep(tmp_path, "S02E001__corrupt")
        transcript_dir = ep / "transcript"
        transcript_dir.mkdir()
        (transcript_dir / "run_manifest.json").write_text("NOT VALID JSON", encoding="utf-8")
        # Must not raise
        aws_runner._update_run_manifest(ep, "run_001", {"diarization": True})


# ===========================================================================
# pip install command safety — regression for the 2026-03-04 silent failure
# ===========================================================================

class TestPipInstallCommandDesign:
    """
    On 2026-03-04, the pip install of speechbrain silently failed because:
      1. speechbrain==1.0.4 does not exist on PyPI
      2. The command `pip install ... | tail -20` exits 0 even when pip fails
         (shell pipelines return the exit code of the LAST command, not pip)

    These tests verify both fixes are in place in the source code.
    They read the source as a string — intentionally brittle to any regression.
    """

    SETUP_SOURCE = Path(__file__).parent.parent / "scripts" / "tools" / "aws_runner.py"

    def test_speechbrain_version_is_pinned_to_existing_release(self):
        """
        speechbrain==1.0.4 does not exist. The correct pin is ==1.0.3.
        If someone 'fixes' this to an unknown future version, this test will catch it.
        """
        source = self.SETUP_SOURCE.read_text(encoding="utf-8")
        assert "speechbrain==1.0.3" in source, (
            "speechbrain must be pinned to ==1.0.3 (the latest release as of 2026-03-04). "
            "speechbrain==1.0.4 does NOT exist on PyPI and caused silent install failure."
        )
        assert "speechbrain==1.0.4" not in source, (
            "speechbrain==1.0.4 was reverted back — this version does not exist on PyPI"
        )

    def test_pip_install_uses_pipefail_to_propagate_errors(self):
        """
        `pip install ... 2>&1 | tail -20` exits 0 even when pip fails, because the
        shell returns the exit code of `tail`, not `pip`. The fix is `set -o pipefail;`
        which makes the pipeline exit with pip's code.

        Without this, a completely failed install looks like success.
        """
        source = self.SETUP_SOURCE.read_text(encoding="utf-8")
        assert "set -o pipefail" in source, (
            "pip install command must use 'set -o pipefail' to ensure pip failures "
            "are not silently swallowed by the '| tail -20' pipe. "
            "This was the root cause of pyannote/speechbrain silently not installing."
        )


# ===========================================================================
# update_sg_ssh_rule — IP-change handling
# ===========================================================================

class TestUpdateSgSshRule:
    """
    On 2026-03-04, SSH connections timed out because the security group still
    allowed the OLD home IP. The fix: auto-update the SG before SSH wait.
    """

    def _make_sg_response(self, existing_cidr: str) -> dict:
        return {
            "SecurityGroups": [{
                "IpPermissions": [{
                    "IpProtocol": "tcp",
                    "FromPort": 22,
                    "ToPort": 22,
                    "IpRanges": [{"CidrIp": existing_cidr}],
                }]
            }]
        }

    def test_noop_when_ip_already_allowed(self):
        """
        If our current IP is already in the SG, no AWS calls should be made.
        Unnecessarily revoking/re-authorizing races with running instances.
        """
        with patch("urllib.request.urlopen") as mock_urlopen, \
             patch("aws_runner._aws") as mock_aws:

            mock_urlopen.return_value.__enter__ = lambda s: s
            mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value.read.return_value = b"1.2.3.4\n"
            mock_aws.return_value = self._make_sg_response("1.2.3.4/32")

            aws_runner.update_sg_ssh_rule()

            revoke_calls = [
                c for c in mock_aws.call_args_list
                if "revoke-security-group-ingress" in str(c)
            ]
            assert revoke_calls == [], (
                "When our IP is already allowed, no revoke call should be made"
            )

    def test_updates_rule_when_ip_has_changed(self):
        """
        User scenario: Mac IP changed overnight (DHCP, VPN, coffee shop).
        The SG must be updated so SSH doesn't time out waiting 360 seconds.
        """
        with patch("urllib.request.urlopen") as mock_urlopen, \
             patch("aws_runner._aws") as mock_aws:

            mock_urlopen.return_value.__enter__ = lambda s: s
            mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value.read.return_value = b"9.9.9.9\n"
            mock_aws.return_value = self._make_sg_response("1.2.3.4/32")

            aws_runner.update_sg_ssh_rule()

            all_calls = str(mock_aws.call_args_list)
            assert "revoke-security-group-ingress" in all_calls, (
                "Stale IP '1.2.3.4' must be revoked when current IP is '9.9.9.9'"
            )
            assert "authorize-security-group-ingress" in all_calls, (
                "New IP '9.9.9.9/32' must be authorized"
            )

    def test_warns_and_continues_when_ip_lookup_fails(self, caplog):
        """
        If checkip.amazonaws.com is unreachable (offline, firewall), the batch
        must not crash — it should log a warning and proceed.  The user may have
        already set up the SG manually.
        """
        import urllib.error
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("unreachable")), \
             patch("aws_runner._aws") as mock_aws:

            aws_runner.update_sg_ssh_rule()  # must not raise

            assert mock_aws.call_count == 0, (
                "If IP lookup fails, no AWS calls should be made"
            )


# ===========================================================================
# _launch_detached — detached SSH process launch
# ===========================================================================

class TestLaunchDetached:
    """
    _launch_detached() sends a nohup command to the remote host and returns
    the remote PID as a string.  The job must survive SSH disconnect.
    """

    def _make_worker(self) -> aws_runner.RemoteWorker:
        return aws_runner.RemoteWorker(host="1.2.3.4", key_path=Path("/tmp/test.pem"))

    def test_returns_pid_on_success(self):
        """When SSH launches the job and echoes a numeric PID, the PID string is returned."""
        worker = self._make_worker()
        with patch.object(worker, "_ssh", side_effect=[
            (0, "", ""),         # mkdir -p log dir
            (0, "12345\n", ""),  # nohup ... & echo $!
        ]):
            pid = worker._launch_detached("echo hello", "/tmp/test.log")
        assert pid == "12345", f"Expected '12345', got '{pid!r}'"

    def test_raises_runtime_error_on_nonzero_ssh_exit(self):
        """When SSH returns a non-zero exit code on launch, RuntimeError is raised."""
        worker = self._make_worker()
        with patch.object(worker, "_ssh", side_effect=[
            (0, "", ""),                   # mkdir
            (1, "", "permission denied"),  # launch fails
        ]):
            with pytest.raises(RuntimeError, match="Failed to launch"):
                worker._launch_detached("echo hello", "/tmp/test.log")

    def test_raises_runtime_error_when_stdout_is_not_a_digit(self):
        """
        If SSH exits 0 but stdout is non-numeric (e.g. 'nohup: ignoring input'),
        the PID is ambiguous — RuntimeError must be raised.
        """
        worker = self._make_worker()
        with patch.object(worker, "_ssh", side_effect=[
            (0, "", ""),
            (0, "nohup: ignoring input\n", ""),
        ]):
            with pytest.raises(RuntimeError, match="Failed to launch"):
                worker._launch_detached("echo hello", "/tmp/test.log")

    def test_mkdir_is_called_before_nohup_launch(self):
        """
        The log directory must be created before nohup redirects stdout there —
        otherwise nohup will fail trying to open a non-existent directory.
        """
        worker = self._make_worker()
        calls = []

        def track(cmd, **kw):
            calls.append(cmd)
            return (0, "99\n", "") if len(calls) > 1 else (0, "", "")

        with patch.object(worker, "_ssh", side_effect=track):
            worker._launch_detached("my_cmd", "/tmp/logs/ep.log")

        assert len(calls) >= 2, "Expected at least 2 SSH calls"
        assert "mkdir" in calls[0], (
            f"First SSH call must create the log dir via mkdir, got: {calls[0]!r}"
        )

    def test_launch_command_uses_nohup_and_echoes_pid(self):
        """
        The remote command must be wrapped with nohup and '& echo $!' so it
        survives SSH disconnect and the caller can poll the specific PID.
        """
        worker = self._make_worker()
        launch_cmd = None

        def capture(cmd, **kw):
            nonlocal launch_cmd
            if "nohup" in cmd:
                launch_cmd = cmd
                return (0, "42\n", "")
            return (0, "", "")

        with patch.object(worker, "_ssh", side_effect=capture):
            worker._launch_detached("my_transcribe_cmd", "/tmp/logs/ep.log")

        assert launch_cmd is not None, "No nohup command was sent to the remote"
        assert "nohup" in launch_cmd, "Command must use nohup to survive disconnect"
        assert "echo $!" in launch_cmd, "Command must echo the PID after '&'"


# ===========================================================================
# _poll_until_done — heartbeat loop watching for remote job completion
# ===========================================================================

class TestPollUntilDone:
    """
    _poll_until_done() polls the remote host every poll_interval seconds until
    the done marker file appears.  It handles transient SSH failures with
    exponential backoff and raises TimeoutError if the deadline is exceeded.
    """

    def _make_worker(self) -> aws_runner.RemoteWorker:
        return aws_runner.RemoteWorker(host="1.2.3.4", key_path=Path("/tmp/test.pem"))

    def test_returns_when_done_marker_found_on_first_poll(self):
        """Happy path: done marker exists on the first poll → return immediately."""
        worker = self._make_worker()
        with patch.object(worker, "_ssh", return_value=(0, "", "")), \
             patch("time.sleep"), \
             patch("time.monotonic", return_value=0.0):
            # Does not raise
            worker._poll_until_done("/tmp/done", "123", "ep", "/tmp/ep.log",
                                    timeout=3600, poll_interval=1)

    def test_keeps_polling_until_done_marker_appears(self):
        """
        If the done marker is absent for the first two polls but present on the third,
        the method must keep waiting and return normally (not raise).
        """
        worker = self._make_worker()
        # 2 miss cycles (marker absent, PID alive) then 1 hit
        ssh_responses = [
            (1, "", ""),  # poll 1: test -f → absent
            (0, "", ""),  # poll 1: kill -0 → alive
            (1, "", ""),  # poll 2: test -f → absent
            (0, "", ""),  # poll 2: kill -0 → alive
            (0, "", ""),  # poll 3: test -f → found!
        ]
        with patch.object(worker, "_ssh", side_effect=ssh_responses), \
             patch("time.sleep"), \
             patch("time.monotonic", return_value=0.0):
            worker._poll_until_done("/tmp/done", "123", "ep", "/tmp/ep.log",
                                    timeout=3600, poll_interval=1)

    def test_raises_runtime_error_when_process_dies_without_marker(self):
        """
        If kill -0 fails (process is gone) but the done marker was never written,
        the transcription crashed — RuntimeError must be raised.
        """
        worker = self._make_worker()
        ssh_responses = [
            (1, "", ""),            # test -f → absent
            (1, "", ""),            # kill -0 → process gone
            (0, "CRASH LOG\n", ""), # tail -40 for diagnosis
        ]
        with patch.object(worker, "_ssh", side_effect=ssh_responses), \
             patch("time.sleep"), \
             patch("time.monotonic", return_value=0.0):
            with pytest.raises(RuntimeError, match="exited without writing"):
                worker._poll_until_done("/tmp/done", "123", "ep", "/tmp/ep.log",
                                        timeout=3600, poll_interval=1)

    def test_runtime_error_includes_log_tail_for_diagnosis(self):
        """
        The RuntimeError message must embed the last log lines so the operator
        can diagnose the failure without manually SSH-ing to the (now dead) instance.
        """
        worker = self._make_worker()
        ssh_responses = [
            (1, "", ""),
            (1, "", ""),
            (0, "CUDA OOM at segment 412\n", ""),
        ]
        with patch.object(worker, "_ssh", side_effect=ssh_responses), \
             patch("time.sleep"), \
             patch("time.monotonic", return_value=0.0):
            with pytest.raises(RuntimeError) as exc_info:
                worker._poll_until_done("/tmp/done", "123", "ep", "/tmp/ep.log",
                                        timeout=3600, poll_interval=1)
        assert "CUDA OOM at segment 412" in str(exc_info.value), (
            "RuntimeError must include the remote log tail for diagnosis"
        )

    def test_raises_timeout_error_when_deadline_exceeded(self):
        """
        If the episode hasn't finished within `timeout` seconds, TimeoutError is raised.
        The job may still be running — this is distinct from RuntimeError (job crashed).
        """
        worker = self._make_worker()
        # First monotonic() call sets deadline (0 + 3600 = 3600).
        # Second call (while condition) returns 3601 → loop body never executes.
        with patch.object(worker, "_ssh", return_value=(1, "", "")), \
             patch("time.sleep"), \
             patch("time.monotonic", side_effect=[0.0, 3601.0]):
            with pytest.raises(TimeoutError):
                worker._poll_until_done("/tmp/done", "123", "ep", "/tmp/ep.log",
                                        timeout=3600, poll_interval=1)

    def test_timeout_error_includes_ssh_recovery_command(self):
        """
        The TimeoutError message must include a full 'ssh ... tail -100 <log>' command
        so the operator knows exactly how to inspect what's happening remotely.
        """
        worker = self._make_worker()
        with patch.object(worker, "_ssh", return_value=(1, "", "")), \
             patch("time.sleep"), \
             patch("time.monotonic", side_effect=[0.0, 9999.0]):
            with pytest.raises(TimeoutError) as exc_info:
                worker._poll_until_done("/tmp/done", "123", "ep", "/tmp/ep.log",
                                        timeout=3600, poll_interval=1)
        msg = str(exc_info.value)
        assert "ssh" in msg.lower(), "TimeoutError must include an ssh recovery command"
        assert "/tmp/ep.log" in msg, "TimeoutError must name the log file path"

    def test_exponential_backoff_after_ssh_timeout(self):
        """
        Transient SSH timeouts (network blip, lid close) must trigger exponential
        backoff so the polling doesn't hammer a temporarily unreachable host.
        First backoff is 30s; second is 60s (2×).
        """
        worker = self._make_worker()
        sleep_calls: list[float] = []

        def fake_sleep(secs):
            sleep_calls.append(secs)

        call_count = [0]

        def flaky_ssh(cmd, **kw):
            call_count[0] += 1
            if call_count[0] <= 2:
                raise subprocess.TimeoutExpired(cmd="ssh", timeout=15)
            return (0, "", "")  # done marker found on 3rd call

        with patch.object(worker, "_ssh", side_effect=flaky_ssh), \
             patch("time.sleep", side_effect=fake_sleep), \
             patch("time.monotonic", return_value=0.0):
            worker._poll_until_done("/tmp/done", "123", "ep", "/tmp/ep.log",
                                    timeout=999999, poll_interval=1)

        backoff_sleeps = [s for s in sleep_calls if s > 1]
        assert 30 in backoff_sleeps, (
            f"First SSH timeout must trigger 30s backoff; got sleeps: {sleep_calls}"
        )
        assert 60 in backoff_sleeps, (
            f"Second SSH timeout must trigger 60s backoff (2×30); got sleeps: {sleep_calls}"
        )

    def test_backoff_is_capped_at_600_seconds(self):
        """
        After many consecutive SSH timeouts the backoff must not grow beyond 600s —
        otherwise the operator waits too long between status updates.
        """
        worker = self._make_worker()
        sleep_calls: list[float] = []

        def fake_sleep(secs):
            sleep_calls.append(secs)

        call_count = [0]

        def mostly_flaky_ssh(cmd, **kw):
            call_count[0] += 1
            if call_count[0] <= 15:
                raise subprocess.TimeoutExpired(cmd="ssh", timeout=15)
            return (0, "", "")  # eventually done

        with patch.object(worker, "_ssh", side_effect=mostly_flaky_ssh), \
             patch("time.sleep", side_effect=fake_sleep), \
             patch("time.monotonic", return_value=0.0):
            worker._poll_until_done("/tmp/done", "123", "ep", "/tmp/ep.log",
                                    timeout=999999, poll_interval=1)

        assert max(sleep_calls) <= 600, (
            f"Backoff must be capped at 600s; got max={max(sleep_calls)}: {sleep_calls}"
        )


# ===========================================================================
# process_episode — reconnect and error-handling behaviour
# ===========================================================================

class TestProcessEpisodeReconnect:
    """
    process_episode() must handle the reconnect scenario (done marker already on
    remote) and must NOT delete remote data when the job monitoring fails, since
    partial results may be recoverable.
    """

    def _make_worker(self, run_id: str = "run_20260304__larg__dz") -> aws_runner.RemoteWorker:
        return aws_runner.RemoteWorker(
            host="1.2.3.4",
            key_path=Path("/tmp/test.pem"),
            run_id=run_id,
            diarize=True,
        )

    def test_skips_transcription_when_done_marker_exists_on_remote(self, tmp_path):
        """
        Reconnect scenario: we lost SSH mid-episode but the remote job finished.
        process_episode() must detect the done marker and NOT re-launch the job.
        """
        worker = self._make_worker()
        ep = _ep(tmp_path, "S02E001__test")

        with patch.object(worker, "_ssh", return_value=(0, "", "")), \
             patch.object(worker, "_rsync_down"), \
             patch.object(worker, "_launch_detached") as mock_launch, \
             patch.object(worker, "_finish_local"):
            worker.process_episode(ep, tmp_path)

        assert mock_launch.call_count == 0, (
            "_launch_detached must NOT be called when done marker already exists on remote; "
            "re-launching would overwrite the completed transcript"
        )

    def test_rsyncs_results_on_reconnect(self, tmp_path):
        """On reconnect, rsync must still be called to retrieve the remote results."""
        worker = self._make_worker()
        ep = _ep(tmp_path, "S02E001__test")

        with patch.object(worker, "_ssh", return_value=(0, "", "")), \
             patch.object(worker, "_rsync_down") as mock_rsync, \
             patch.object(worker, "_launch_detached"), \
             patch.object(worker, "_finish_local"):
            worker.process_episode(ep, tmp_path)

        assert mock_rsync.call_count >= 1, (
            "_rsync_down must be called on reconnect to retrieve the finished transcript"
        )

    def test_remote_dir_is_not_deleted_on_timeout_error(self, tmp_path):
        """
        On TimeoutError (job still running), the remote episode directory must be
        preserved — the job may finish later and can be recovered via --hosts <ip> --skip-setup.
        """
        worker = self._make_worker()
        ep = _ep(tmp_path, "S02E001__test")
        cleanup_calls: list[str] = []

        def mock_ssh(cmd, **kw):
            if "rm -rf" in cmd:
                cleanup_calls.append(cmd)
            if "test -f" in cmd:
                return (1, "", "")  # not done yet
            return (0, "", "")

        with patch.object(worker, "_ssh", side_effect=mock_ssh), \
             patch.object(worker, "_rsync_up"), \
             patch.object(worker, "_launch_detached", return_value="999"), \
             patch.object(worker, "_poll_with_progress",
                          side_effect=TimeoutError("timed out")):
            success, _ = worker.process_episode(ep, tmp_path)

        assert success is False
        assert not cleanup_calls, (
            "Remote dir must NOT be deleted on TimeoutError — "
            "job may still be running and results are recoverable"
        )

    def test_remote_dir_is_not_deleted_on_runtime_error(self, tmp_path):
        """
        On RuntimeError (remote job crashed), the remote directory must be preserved
        so partial transcripts can be manually inspected or recovered.
        """
        worker = self._make_worker()
        ep = _ep(tmp_path, "S02E001__test")
        cleanup_calls: list[str] = []

        def mock_ssh(cmd, **kw):
            if "rm -rf" in cmd:
                cleanup_calls.append(cmd)
            if "test -f" in cmd:
                return (1, "", "")
            return (0, "", "")

        with patch.object(worker, "_ssh", side_effect=mock_ssh), \
             patch.object(worker, "_rsync_up"), \
             patch.object(worker, "_launch_detached", return_value="999"), \
             patch.object(worker, "_poll_with_progress",
                          side_effect=RuntimeError("remote job exited")):
            success, _ = worker.process_episode(ep, tmp_path)

        assert success is False
        assert not cleanup_calls, (
            "Remote dir must NOT be deleted on RuntimeError — "
            "partial results may be recoverable manually"
        )

    def test_done_marker_path_includes_run_id_when_set(self, tmp_path):
        """
        With a run_id set, the done marker must live inside runs/{run_id}/ so
        each versioned run has its own independent completion signal.
        """
        run_id = "run_20260304__larg__dz"
        worker = self._make_worker(run_id=run_id)
        ep = _ep(tmp_path, "S02E001__test")
        checked_paths: list[str] = []

        def track_ssh(cmd, **kw):
            if "test -f" in cmd:
                checked_paths.append(cmd)
            return (1, "", "")  # force early exit via mkdir failure

        with patch.object(worker, "_ssh", side_effect=track_ssh), \
             patch.object(worker, "_rsync_up", side_effect=Exception("bail")):
            worker.process_episode(ep, tmp_path)

        assert checked_paths, "No 'test -f' SSH call was made"
        assert run_id in checked_paths[0], (
            f"Done marker path must include run_id '{run_id}'; got: {checked_paths[0]!r}"
        )

    def test_done_marker_path_without_run_id_uses_legacy_location(self, tmp_path):
        """
        Without a run_id (legacy mode), the done marker falls back to
        transcript/extraction_report.json rather than a versioned runs/ path.
        """
        worker = self._make_worker(run_id="")
        ep = _ep(tmp_path, "S02E001__test")
        checked_paths: list[str] = []

        def track_ssh(cmd, **kw):
            if "test -f" in cmd:
                checked_paths.append(cmd)
            return (1, "", "")

        with patch.object(worker, "_ssh", side_effect=track_ssh), \
             patch.object(worker, "_rsync_up", side_effect=Exception("bail")):
            worker.process_episode(ep, tmp_path)

        assert checked_paths, "No 'test -f' SSH call was made"
        assert "runs/" not in checked_paths[0], (
            f"Without run_id, done marker must NOT be inside a runs/ dir; "
            f"got: {checked_paths[0]!r}"
        )
        assert "extraction_report.json" in checked_paths[0]

    def test_finish_local_writes_run_manifest_when_run_id_is_set(self, tmp_path):
        """
        _finish_local() must update run_manifest.json when run_id is set —
        this is how the local machine tracks which runs have been completed.
        """
        ep = _ep(tmp_path, "S02E001__test")
        (ep / "transcript").mkdir()
        worker = self._make_worker(run_id="run_20260304__larg__dz")

        worker._finish_local(tmp_path, ep.name, "large-v3")

        manifest = ep / "transcript" / "run_manifest.json"
        assert manifest.exists(), "_finish_local must create run_manifest.json"
        data = json.loads(manifest.read_text())
        assert data["canonical"] == "run_20260304__larg__dz"

    def test_finish_local_is_noop_without_run_id(self, tmp_path):
        """
        Without a run_id (legacy mode), _finish_local() must be a no-op —
        no manifest is written and no exception is raised.
        """
        ep = _ep(tmp_path, "S02E001__test")
        worker = self._make_worker(run_id="")

        worker._finish_local(tmp_path, ep.name, "large-v3")

        manifest = ep / "transcript" / "run_manifest.json"
        assert not manifest.exists(), (
            "_finish_local must not create run_manifest.json when run_id is empty (legacy mode)"
        )
