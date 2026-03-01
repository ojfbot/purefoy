"""
HTTP client utilities.

Responsibilities:
- Rate limiting
- Retries
- Conditional GET using ETag / Last-Modified
- Capturing provenance headers for auditability

This layer is intentionally "dumb" about forums; it only fetches URLs.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


@dataclass
class FetchResult:
    """Return object for fetches with provenance useful for downstream storage."""

    url: str
    status: int
    text: str | None
    etag: str | None
    last_modified: str | None
    not_modified: bool = False


class HttpClient:
    """
    A small, reusable HTTP client for polite crawling.

    Parameters
    ----------
    user_agent:
        User-Agent header string.
    delay_s:
        Seconds to sleep between requests (global pacing).
    timeout_s:
        Per-request timeout.
    state_path:
        Where to persist conditional request headers (ETag/Last-Modified) per URL.
    """

    def __init__(
        self,
        user_agent: str,
        delay_s: float,
        timeout_s: int,
        state_path: Path,
        max_retries: int = 3,
        cookies_path: Path | None = None,
    ) -> None:
        self.delay_s = delay_s
        self.timeout_s = timeout_s
        self.state_path = state_path
        self._state = self._load_state()
        self._last_request_time = 0.0

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})

        if cookies_path is not None and cookies_path.exists():
            self._load_cookies_from_file(cookies_path)

        retry = Retry(
            total=max_retries,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _load_cookies_from_file(self, cookies_path: Path) -> None:
        """Load session cookies from a JSON file (e.g., session_cookies.json)."""
        cookies = json.loads(cookies_path.read_text(encoding="utf-8"))
        for c in cookies:
            self.session.cookies.set(
                c["name"],
                c["value"],
                domain=c.get("domain", ""),
                path=c.get("path", "/"),
            )

    def load_cookies(self, cookies_path: Path) -> None:
        """Load or reload cookies at runtime (e.g., after auth-setup)."""
        if cookies_path.exists():
            self._load_cookies_from_file(cookies_path)

    def _load_state(self) -> dict:
        if self.state_path.exists():
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        return {"urls": {}}

    def _save_state(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(self._state, indent=2), encoding="utf-8")

    def fetch(self, url: str) -> FetchResult:
        """
        Fetch a URL with conditional caching.

        Returns `not_modified=True` when the server replies 304.
        """
        # Rate limiting
        elapsed = time.time() - self._last_request_time
        if elapsed < self.delay_s:
            time.sleep(self.delay_s - elapsed)
        self._last_request_time = time.time()

        headers = {}
        cached = self._state["urls"].get(url, {})
        if cached.get("etag"):
            headers["If-None-Match"] = cached["etag"]
        if cached.get("last_modified"):
            headers["If-Modified-Since"] = cached["last_modified"]

        resp = self.session.get(url, headers=headers, timeout=self.timeout_s)

        etag = resp.headers.get("ETag")
        last_mod = resp.headers.get("Last-Modified")

        if resp.status_code == 304:
            return FetchResult(url=url, status=304, text=None, etag=etag, last_modified=last_mod, not_modified=True)

        resp.raise_for_status()

        # update state
        self._state["urls"][url] = {"etag": etag, "last_modified": last_mod}
        self._save_state()

        return FetchResult(url=url, status=resp.status_code, text=resp.text, etag=etag, last_modified=last_mod)

    def fetch_bytes(self, url: str) -> bytes | None:
        """
        Fetch a binary resource (e.g. image) with rate limiting.

        No ETag caching — callers should check for a local file first.
        Returns None on any error.
        """
        elapsed = time.time() - self._last_request_time
        if elapsed < self.delay_s:
            time.sleep(self.delay_s - elapsed)
        self._last_request_time = time.time()

        try:
            resp = self.session.get(url, timeout=self.timeout_s)
            resp.raise_for_status()
            return resp.content
        except Exception:
            return None
