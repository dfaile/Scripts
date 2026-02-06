"""Configuration management for Nobl9 Status Page API examples."""
import os
from typing import Optional
from dotenv import load_dotenv


class Config:
    """Configuration for Nobl9 Status Page API."""

    DEFAULT_BASE_URL = "https://app.nobl9.com"

    def __init__(self):
        """Initialize configuration from environment variables."""
        load_dotenv()

        self.client_id = os.getenv("NOBL9_CLIENT_ID")
        self.client_secret = os.getenv("NOBL9_CLIENT_SECRET")
        self.organization = os.getenv("NOBL9_ORG")
        self.base_url = os.getenv("NOBL9_BASE_URL", self.DEFAULT_BASE_URL)

        # For backwards compatibility, also support pre-generated tokens
        self.api_token = os.getenv("NOBL9_API_TOKEN")

    def validate(self) -> None:
        """Validate that required configuration is present.

        Raises:
            ValueError: If required configuration is missing.
        """
        # Either client credentials or API token must be provided
        if not self.api_token and not (self.client_id and self.client_secret):
            raise ValueError(
                "Either NOBL9_CLIENT_ID and NOBL9_CLIENT_SECRET, or NOBL9_API_TOKEN must be set.\n"
                "Recommended: Use client credentials (NOBL9_CLIENT_ID and NOBL9_CLIENT_SECRET).\n"
                "Get your client credentials from: https://docs.nobl9.com/api/slo#tag/Access-Token"
            )
        if not self.organization:
            raise ValueError(
                "NOBL9_ORG environment variable is required.\n"
                "Set this to your Nobl9 organization ID."
            )


def get_config() -> Config:
    """Get validated configuration.

    Returns:
        Config: Validated configuration object.

    Raises:
        ValueError: If required configuration is missing.
    """
    config = Config()
    config.validate()
    return config
