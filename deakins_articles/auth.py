"""
Authentication handler for Roger Deakins members-only content.

Manages WordPress login, session cookies, and authentication validation.
"""

import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


@dataclass
class AuthSession:
    """Represents an authenticated session."""
    cookies: Dict[str, str]
    authenticated_at: str  # ISO timestamp
    username: str
    expires_at: Optional[str] = None  # ISO timestamp

    def is_expired(self) -> bool:
        """Check if session has expired (assumes 24hr expiry if not specified)."""
        if self.expires_at:
            expires = datetime.fromisoformat(self.expires_at)
            return datetime.now() > expires

        # Default: session expires after 24 hours
        authenticated = datetime.fromisoformat(self.authenticated_at)
        return datetime.now() > authenticated + timedelta(hours=24)

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON storage."""
        return {
            "cookies": self.cookies,
            "authenticated_at": self.authenticated_at,
            "username": self.username,
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AuthSession":
        """Deserialize from dictionary."""
        return cls(
            cookies=data["cookies"],
            authenticated_at=data["authenticated_at"],
            username=data["username"],
            expires_at=data.get("expires_at"),
        )


class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass


class WordPressAuthHandler:
    """
    Handles WordPress authentication for rogerdeakins.com.

    Features:
    - WordPress wp-login.php form authentication
    - Session cookie persistence
    - Automatic session validation
    - Re-authentication on expiry
    """

    def __init__(
        self,
        base_url: str,
        login_url: str,
        session_file: Optional[Path] = None,
        user_agent: str = "Mozilla/5.0",
    ):
        """
        Initialize authentication handler.

        Args:
            base_url: Site base URL
            login_url: WordPress login endpoint
            session_file: Path to persist cookies (JSON)
            user_agent: User agent string
        """
        self.base_url = base_url
        self.login_url = login_url
        self.session_file = session_file
        self.user_agent = user_agent

        self.session: Optional[AuthSession] = None
        self._requests_session = requests.Session()
        self._requests_session.headers.update({"User-Agent": user_agent})

        # Load cached session if available
        if session_file and session_file.exists():
            self._load_session()

    def authenticate(self, username: str, password: str, force: bool = False) -> bool:
        """
        Authenticate with WordPress and establish session.

        Args:
            username: WordPress username
            password: WordPress password
            force: Force re-authentication even if session exists

        Returns:
            True if authentication succeeded

        Raises:
            AuthenticationError: If login fails
        """
        # Check if we already have a valid session
        if not force and self.session and not self.session.is_expired():
            print(f"✓ Using cached session for user '{username}'")
            return True

        print(f"Authenticating as '{username}'...")

        # Clear any existing cookies to avoid duplicates
        self._requests_session.cookies.clear()

        # Step 1: GET login page to get any CSRF tokens or nonces
        try:
            login_page = self._requests_session.get(
                self.login_url, timeout=30, allow_redirects=True
            )
            login_page.raise_for_status()
        except requests.RequestException as e:
            raise AuthenticationError(f"Failed to load login page: {e}")

        # Parse login form for hidden fields
        soup = BeautifulSoup(login_page.text, "html.parser")
        login_form = soup.find("form", {"id": "loginform"})

        if not login_form:
            raise AuthenticationError("Could not find WordPress login form")

        # Extract all hidden form fields (CSRF tokens, redirects, etc.)
        form_data = {
            "log": username,
            "pwd": password,
            "wp-submit": "Log In",
            "redirect_to": self.base_url,
            "testcookie": "1",
        }

        # Add any hidden fields from the form
        for hidden_input in login_form.find_all("input", {"type": "hidden"}):
            name = hidden_input.get("name")
            value = hidden_input.get("value", "")
            if name:
                form_data[name] = value

        # Step 2: POST login credentials
        try:
            login_response = self._requests_session.post(
                self.login_url,
                data=form_data,
                timeout=30,
                allow_redirects=True,
            )
            login_response.raise_for_status()
        except requests.RequestException as e:
            raise AuthenticationError(f"Login request failed: {e}")

        # Step 3: Validate authentication succeeded
        # WordPress redirects to redirect_to URL on success
        # Check for error messages in response
        if "login_error" in login_response.url or "error" in login_response.url:
            raise AuthenticationError("Invalid username or password")

        # Look for WordPress authentication cookies
        # Convert to dict to handle duplicate cookie names
        auth_cookies = {}
        for cookie in self._requests_session.cookies:
            if "wordpress" in cookie.name.lower() or "wp" in cookie.name.lower():
                auth_cookies[cookie.name] = cookie.value

        if not auth_cookies:
            raise AuthenticationError("No authentication cookies received")

        # Step 4: Verify access to members-only content
        if not self._verify_authenticated():
            raise AuthenticationError("Authentication appeared to succeed but cannot access members-only content")

        # Step 5: Store session - convert cookies to simple dict
        all_cookies = {}
        for cookie in self._requests_session.cookies:
            all_cookies[cookie.name] = cookie.value

        self.session = AuthSession(
            cookies=all_cookies,
            authenticated_at=datetime.now().isoformat(),
            username=username,
        )

        self._save_session()
        print(f"✓ Successfully authenticated as '{username}'")
        return True

    def _verify_authenticated(self) -> bool:
        """
        Verify that we can access members-only content.

        Returns:
            True if authenticated session can access restricted content
        """
        # Try accessing a members-only page
        test_url = urljoin(self.base_url, "/members-only/looking-at-lighting/")

        try:
            response = self._requests_session.get(test_url, timeout=30)
            response.raise_for_status()

            # If we see a login form, we're not authenticated
            if "wp-login.php" in response.url or "restricted to site members" in response.text.lower():
                return False

            return True

        except requests.RequestException:
            return False

    def get_authenticated_session(self) -> requests.Session:
        """
        Get a requests.Session with authentication cookies.

        Returns:
            Authenticated requests.Session

        Raises:
            AuthenticationError: If not authenticated
        """
        if not self.session or self.session.is_expired():
            raise AuthenticationError("Not authenticated or session expired. Call authenticate() first.")

        # Apply cookies to session
        self._requests_session.cookies.update(self.session.cookies)
        return self._requests_session

    def is_authenticated(self) -> bool:
        """Check if currently authenticated with valid session."""
        return self.session is not None and not self.session.is_expired()

    def logout(self):
        """Clear authentication session."""
        self.session = None
        self._requests_session.cookies.clear()

        if self.session_file and self.session_file.exists():
            self.session_file.unlink()

        print("✓ Logged out")

    def _save_session(self):
        """Persist session to disk."""
        if not self.session or not self.session_file:
            return

        self.session_file.parent.mkdir(parents=True, exist_ok=True)

        with open(self.session_file, "w") as f:
            json.dump(self.session.to_dict(), f, indent=2)

    def _load_session(self):
        """Load session from disk."""
        if not self.session_file or not self.session_file.exists():
            return

        try:
            with open(self.session_file) as f:
                data = json.load(f)

            self.session = AuthSession.from_dict(data)

            # Check if expired
            if self.session.is_expired():
                print(f"Cached session for '{self.session.username}' has expired")
                self.session = None
                return

            # Restore cookies to requests session
            self._requests_session.cookies.update(self.session.cookies)

            print(f"✓ Loaded cached session for '{self.session.username}'")

        except (json.JSONDecodeError, KeyError) as e:
            print(f"⚠ Could not load session file: {e}")
            self.session = None


# ============================================================================
# Convenience functions
# ============================================================================

def authenticate_from_settings(settings) -> WordPressAuthHandler:
    """
    Create and authenticate using ArticlesSettings.

    Args:
        settings: ArticlesSettings instance with credentials

    Returns:
        Authenticated WordPressAuthHandler

    Raises:
        AuthenticationError: If authentication fails
    """
    if not settings.username or not settings.password:
        raise AuthenticationError(
            "Username and password required for authentication. "
            "Set DEAKINS_ARTICLES_USERNAME and DEAKINS_ARTICLES_PASSWORD "
            "or provide via CLI arguments."
        )

    auth_handler = WordPressAuthHandler(
        base_url=settings.base_url,
        login_url=settings.login_url,
        session_file=settings.session_cookie_file,
        user_agent=settings.user_agent,
    )

    auth_handler.authenticate(settings.username, settings.password)

    return auth_handler
