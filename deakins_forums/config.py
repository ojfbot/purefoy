"""Configuration management for the scraper."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Settings:
    """Application settings with sensible defaults."""

    base_url: str = "https://rogerdeakins.com"
    forums_index_url: str = "https://rogerdeakins.com/forums/"
    user_agent: str = "Mozilla/5.0 (Educational Research Bot; Fair Use; Cinematography Education)"
    delay_s: float = 3.0
    timeout_s: int = 30
    max_retries: int = 3
    out_dir: Path = Path(__file__).parent.parent / "library" / "forums"

    @classmethod
    def from_env(cls) -> Settings:
        """Load settings from environment variables with fallback to defaults."""
        return cls(
            base_url=os.getenv("DEAKINS_BASE_URL", cls.base_url),
            user_agent=os.getenv("DEAKINS_USER_AGENT", cls.user_agent),
            delay_s=float(os.getenv("DEAKINS_DELAY_S", str(cls.delay_s))),
            timeout_s=int(os.getenv("DEAKINS_TIMEOUT_S", str(cls.timeout_s))),
            max_retries=int(os.getenv("DEAKINS_MAX_RETRIES", str(cls.max_retries))),
            out_dir=Path(os.getenv("DEAKINS_OUT_DIR", str(cls.out_dir))),
        )
