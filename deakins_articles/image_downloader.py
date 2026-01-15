"""
Image downloader for article images.

Downloads and stores images locally with provenance tracking.
"""

import hashlib
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List
from urllib.parse import urlparse

import requests


@dataclass
class DownloadResult:
    """Result of an image download operation."""
    success: bool
    local_path: Optional[Path] = None
    size_bytes: Optional[int] = None
    content_hash: Optional[str] = None
    error: Optional[str] = None
    was_cached: bool = False


class ImageDownloader:
    """
    Download and manage article images.

    Features:
    - Content-based deduplication (hash-based storage)
    - Size limits to avoid huge files
    - Format validation
    - Provenance tracking
    - Authenticated downloads via session
    """

    def __init__(
        self,
        images_dir: Path,
        session: Optional[requests.Session] = None,
        max_size_mb: int = 10,
        allowed_formats: Optional[List[str]] = None,
        delay_s: float = 1.0,
    ):
        """
        Initialize image downloader.

        Args:
            images_dir: Directory to store downloaded images
            session: Authenticated requests.Session (optional)
            max_size_mb: Maximum file size in MB
            allowed_formats: List of allowed extensions (default: jpg, png, gif, webp)
            delay_s: Delay between downloads for rate limiting
        """
        self.images_dir = images_dir
        self.session = session or requests.Session()
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.allowed_formats = allowed_formats or ["jpg", "jpeg", "png", "gif", "webp", "svg"]
        self.delay_s = delay_s

        # Ensure directory exists
        self.images_dir.mkdir(parents=True, exist_ok=True)

        # Track last download time for rate limiting
        self._last_download_time = 0

    def download_image(self, url: str, force: bool = False) -> DownloadResult:
        """
        Download a single image.

        Args:
            url: Image URL to download
            force: Force re-download even if cached

        Returns:
            DownloadResult with download status and local path
        """
        try:
            # Parse URL for validation
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return DownloadResult(
                    success=False,
                    error=f"Invalid URL: {url}"
                )

            # Extract extension
            path_parts = parsed.path.split(".")
            if len(path_parts) > 1:
                ext = path_parts[-1].lower().split("?")[0]  # Remove query params
            else:
                ext = "jpg"  # Default

            # Validate format
            if ext not in self.allowed_formats:
                return DownloadResult(
                    success=False,
                    error=f"Unsupported format: {ext}"
                )

            # Generate URL hash for filename (to avoid duplicates)
            url_hash = hashlib.md5(url.encode()).hexdigest()[:16]

            # Check if already downloaded (unless force=True)
            existing_files = list(self.images_dir.glob(f"*-{url_hash}.{ext}"))
            if existing_files and not force:
                local_path = existing_files[0]
                return DownloadResult(
                    success=True,
                    local_path=local_path,
                    size_bytes=local_path.stat().st_size,
                    was_cached=True
                )

            # Rate limiting
            self._rate_limit()

            # Download image
            response = self.session.get(url, timeout=30, stream=True)
            response.raise_for_status()

            # Check content-type
            content_type = response.headers.get("content-type", "")
            if not content_type.startswith("image/"):
                return DownloadResult(
                    success=False,
                    error=f"Not an image: {content_type}"
                )

            # Check content-length before downloading
            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > self.max_size_bytes:
                return DownloadResult(
                    success=False,
                    error=f"Image too large: {int(content_length) / 1024 / 1024:.1f}MB"
                )

            # Download content
            content = b""
            for chunk in response.iter_content(chunk_size=8192):
                content += chunk
                if len(content) > self.max_size_bytes:
                    return DownloadResult(
                        success=False,
                        error=f"Image exceeds max size: {self.max_size_bytes / 1024 / 1024}MB"
                    )

            # Calculate content hash
            content_hash = hashlib.sha256(content).hexdigest()[:16]

            # Check if file with same content hash exists (deduplication)
            existing_by_hash = list(self.images_dir.glob(f"{content_hash}-*.{ext}"))
            if existing_by_hash and not force:
                local_path = existing_by_hash[0]
                return DownloadResult(
                    success=True,
                    local_path=local_path,
                    size_bytes=len(content),
                    content_hash=content_hash,
                    was_cached=True
                )

            # Save to disk: {content_hash}-{url_hash}.{ext}
            filename = f"{content_hash}-{url_hash}.{ext}"
            local_path = self.images_dir / filename

            with open(local_path, "wb") as f:
                f.write(content)

            return DownloadResult(
                success=True,
                local_path=local_path,
                size_bytes=len(content),
                content_hash=content_hash,
                was_cached=False
            )

        except requests.RequestException as e:
            return DownloadResult(
                success=False,
                error=f"Download failed: {e}"
            )
        except Exception as e:
            return DownloadResult(
                success=False,
                error=f"Unexpected error: {e}"
            )

    def download_images_batch(
        self,
        image_urls: List[str],
        show_progress: bool = True
    ) -> Dict[str, DownloadResult]:
        """
        Download multiple images.

        Args:
            image_urls: List of image URLs
            show_progress: Print progress messages

        Returns:
            Dict mapping URL to DownloadResult
        """
        results = {}
        total = len(image_urls)

        for i, url in enumerate(image_urls, 1):
            if show_progress:
                print(f"  Downloading image {i}/{total}: {Path(url).name[:50]}...", end=" ")

            result = self.download_image(url)

            if result.success:
                if result.was_cached:
                    if show_progress:
                        print("✓ (cached)")
                else:
                    size_mb = result.size_bytes / 1024 / 1024 if result.size_bytes else 0
                    if show_progress:
                        print(f"✓ ({size_mb:.1f}MB)")
            else:
                if show_progress:
                    print(f"✗ {result.error}")

            results[url] = result

        return results

    def _rate_limit(self):
        """Apply rate limiting between downloads."""
        if self._last_download_time:
            elapsed = time.time() - self._last_download_time
            if elapsed < self.delay_s:
                time.sleep(self.delay_s - elapsed)

        self._last_download_time = time.time()

    def get_stats(self) -> Dict[str, int]:
        """
        Get statistics about downloaded images.

        Returns:
            Dict with total_images, total_size_mb
        """
        image_files = list(self.images_dir.glob("*"))
        total_size = sum(f.stat().st_size for f in image_files if f.is_file())

        return {
            "total_images": len(image_files),
            "total_size_mb": total_size / 1024 / 1024,
        }

    def cleanup_orphaned_images(self, referenced_hashes: List[str]) -> int:
        """
        Remove images not referenced by any article.

        Args:
            referenced_hashes: List of content hashes currently in use

        Returns:
            Number of images deleted
        """
        deleted = 0
        referenced_set = set(referenced_hashes)

        for image_file in self.images_dir.glob("*"):
            if not image_file.is_file():
                continue

            # Extract content hash from filename: {hash}-{url_hash}.{ext}
            content_hash = image_file.stem.split("-")[0]

            if content_hash not in referenced_set:
                image_file.unlink()
                deleted += 1

        return deleted


# ============================================================================
# Utility Functions
# ============================================================================

def select_best_image_from_srcset(srcset: str, preferred_width: int = 600) -> Optional[str]:
    """
    Parse srcset and select the best image URL.

    Args:
        srcset: Image srcset attribute (e.g., "url1.jpg 300w, url2.jpg 600w")
        preferred_width: Preferred image width

    Returns:
        Best image URL or None
    """
    if not srcset:
        return None

    try:
        # Parse srcset: "url1 300w, url2 600w, ..."
        sources = []
        for source in srcset.split(","):
            source = source.strip()
            if not source:
                continue

            parts = source.rsplit(None, 1)
            if len(parts) == 2:
                url, descriptor = parts
                # Extract width (e.g., "600w" -> 600)
                if descriptor.endswith("w"):
                    width = int(descriptor[:-1])
                    sources.append((url, width))

        if not sources:
            return None

        # Sort by width
        sources.sort(key=lambda x: x[1])

        # Find best match (closest to preferred_width, prefer higher)
        best = sources[-1]  # Start with highest
        for url, width in sources:
            if width >= preferred_width:
                best = (url, width)
                break

        return best[0]

    except (ValueError, IndexError):
        return None
