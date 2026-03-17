"""Configuration management for Nobl9 Status Page API examples."""
import os
from pathlib import Path

from .env_loader import load_env

# Package root: examples/common/ -> parent x 3
_PACKAGE_ROOT = Path(__file__).resolve().parent.parent.parent


def _load_env() -> None:
    """Load .env from package root or cwd."""
    try:
        load_env(_PACKAGE_ROOT)
    except Exception:
        pass


class Config:
    """Configuration for Nobl9 Status Page API."""

    DEFAULT_BASE_URL = "https://app.nobl9.com"

    def __init__(self):
        """Initialize configuration from environment variables."""
        _load_env()

        self.client_id = os.getenv("NOBL9_CLIENT_ID")
        self.client_secret = os.getenv("NOBL9_CLIENT_SECRET")
        self.organization = os.getenv("NOBL9_ORG")
        self.base_url = os.getenv("NOBL9_BASE_URL", self.DEFAULT_BASE_URL)
        self.api_token = os.getenv("NOBL9_API_TOKEN")

    def validate(self) -> None:
        """Validate that required configuration is present.

        Raises:
            ValueError: If required configuration is missing.
        """
        if not self.api_token and not (self.client_id and self.client_secret):
            raise ValueError(
                "Either NOBL9_CLIENT_ID and NOBL9_CLIENT_SECRET, or NOBL9_API_TOKEN must be set.\n"
                "Recommended: Use client credentials.\n"
                "Get credentials from: https://docs.nobl9.com/api/slo#tag/Access-Token"
            )
        if not self.organization:
            raise ValueError("NOBL9_ORG environment variable is required.")

    @property
    def organization_id(self) -> str:
        """Alias for organization (for compatibility)."""
        return self.organization or ""


def get_config() -> Config:
    """Get validated configuration."""
    config = Config()
    config.validate()
    return config
