"""
Configuration for Deakins Articles scraper.

Follows same pattern as deakins_forums/config.py with additional
authentication settings for members-only content.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ArticlesSettings:
    """Settings for the articles scraper with authentication support."""

    # Base URLs
    base_url: str = "https://www.rogerdeakins.com"
    login_url: str = "https://www.rogerdeakins.com/wp-login.php"
    articles_index_url: str = "https://www.rogerdeakins.com/members-only/looking-at-lighting/"

    # Authentication (members-only content)
    username: Optional[str] = None
    password: Optional[str] = None
    session_cookie_file: Optional[Path] = None  # Cache session cookies

    # HTTP client settings
    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36 "
        "(Educational Research Bot; Contact: research@example.com)"
    )
    delay_s: float = 3.0  # Rate limiting: seconds between requests
    timeout_s: int = 30  # Request timeout
    max_retries: int = 3  # Retry attempts for failed requests

    # Storage paths
    out_dir: Path = Path(__file__).parent.parent / "library" / "articles"
    images_dir: Path = Path(__file__).parent.parent / "library" / "articles" / "images"

    # Image download settings
    download_images: bool = True
    max_image_size_mb: int = 10
    image_formats: list = None  # Allow all by default

    # Scraping behavior
    max_articles_per_film: int = 0  # 0 = unlimited
    skip_existing: bool = True  # Skip if article already scraped and unchanged

    def __post_init__(self):
        """Set defaults and resolve paths."""
        if self.image_formats is None:
            self.image_formats = ["jpg", "jpeg", "png", "gif", "webp", "svg"]

        # Resolve paths
        self.out_dir = self.out_dir.resolve()
        self.images_dir = self.images_dir.resolve()

        if self.session_cookie_file is None:
            self.session_cookie_file = self.out_dir / "_site" / "session_cookies.json"

    @classmethod
    def from_env(cls) -> "ArticlesSettings":
        """
        Load settings from environment variables with fallback to defaults.

        Environment variables:
        - DEAKINS_ARTICLES_BASE_URL
        - DEAKINS_ARTICLES_USERNAME
        - DEAKINS_ARTICLES_PASSWORD
        - DEAKINS_ARTICLES_USER_AGENT
        - DEAKINS_ARTICLES_DELAY_S
        - DEAKINS_ARTICLES_TIMEOUT_S
        - DEAKINS_ARTICLES_MAX_RETRIES
        - DEAKINS_ARTICLES_OUT_DIR
        - DEAKINS_ARTICLES_DOWNLOAD_IMAGES
        - DEAKINS_ARTICLES_MAX_IMAGE_SIZE_MB
        """
        kwargs = {}

        # URLs
        if val := os.getenv("DEAKINS_ARTICLES_BASE_URL"):
            kwargs["base_url"] = val
        if val := os.getenv("DEAKINS_ARTICLES_LOGIN_URL"):
            kwargs["login_url"] = val
        if val := os.getenv("DEAKINS_ARTICLES_INDEX_URL"):
            kwargs["articles_index_url"] = val

        # Authentication
        if val := os.getenv("DEAKINS_ARTICLES_USERNAME"):
            kwargs["username"] = val
        if val := os.getenv("DEAKINS_ARTICLES_PASSWORD"):
            kwargs["password"] = val
        if val := os.getenv("DEAKINS_ARTICLES_SESSION_COOKIE_FILE"):
            kwargs["session_cookie_file"] = Path(val)

        # HTTP settings
        if val := os.getenv("DEAKINS_ARTICLES_USER_AGENT"):
            kwargs["user_agent"] = val
        if val := os.getenv("DEAKINS_ARTICLES_DELAY_S"):
            kwargs["delay_s"] = float(val)
        if val := os.getenv("DEAKINS_ARTICLES_TIMEOUT_S"):
            kwargs["timeout_s"] = int(val)
        if val := os.getenv("DEAKINS_ARTICLES_MAX_RETRIES"):
            kwargs["max_retries"] = int(val)

        # Storage
        if val := os.getenv("DEAKINS_ARTICLES_OUT_DIR"):
            kwargs["out_dir"] = Path(val)

        # Image settings
        if val := os.getenv("DEAKINS_ARTICLES_DOWNLOAD_IMAGES"):
            kwargs["download_images"] = val.lower() in ("true", "1", "yes")
        if val := os.getenv("DEAKINS_ARTICLES_MAX_IMAGE_SIZE_MB"):
            kwargs["max_image_size_mb"] = int(val)

        # Scraping behavior
        if val := os.getenv("DEAKINS_ARTICLES_MAX_PER_FILM"):
            kwargs["max_articles_per_film"] = int(val)
        if val := os.getenv("DEAKINS_ARTICLES_SKIP_EXISTING"):
            kwargs["skip_existing"] = val.lower() in ("true", "1", "yes")

        return cls(**kwargs)

    def ensure_directories(self):
        """Create necessary directories if they don't exist."""
        dirs_to_create = [
            self.out_dir,
            self.out_dir / "articles",
            self.out_dir / "films",
            self.out_dir / "_site",
            self.images_dir,
        ]

        for dir_path in dirs_to_create:
            dir_path.mkdir(parents=True, exist_ok=True)

    def validate(self) -> list[str]:
        """
        Validate settings and return list of errors.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        if not self.base_url:
            errors.append("base_url is required")

        if self.delay_s < 0:
            errors.append("delay_s must be non-negative")

        if self.timeout_s <= 0:
            errors.append("timeout_s must be positive")

        if self.max_retries < 0:
            errors.append("max_retries must be non-negative")

        if self.max_image_size_mb <= 0:
            errors.append("max_image_size_mb must be positive")

        # Authentication warning (not an error, just a note)
        if not self.username or not self.password:
            errors.append(
                "WARNING: username/password not set - "
                "will only be able to scrape public metadata"
            )

        return errors


def load_settings(
    override_username: Optional[str] = None,
    override_password: Optional[str] = None,
) -> ArticlesSettings:
    """
    Load settings with optional credential overrides.

    Args:
        override_username: Override username (e.g., from CLI args)
        override_password: Override password (e.g., from CLI args)

    Returns:
        ArticlesSettings instance
    """
    settings = ArticlesSettings.from_env()

    # CLI overrides take precedence
    if override_username:
        settings.username = override_username
    if override_password:
        settings.password = override_password

    # Ensure directories exist
    settings.ensure_directories()

    return settings
