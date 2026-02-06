"""HTTP client for Nobl9 Status Page API."""
import json
import base64
import time
from typing import Any, Dict, Optional, Callable
import requests
from .config import Config


class APIError(Exception):
    """Base exception for API errors."""
    pass


class AuthenticationError(APIError):
    """Raised when authentication fails."""
    pass


class NotFoundError(APIError):
    """Raised when a resource is not found."""
    pass


class RateLimitError(APIError):
    """Raised when rate limit is exceeded."""
    pass


class ValidationError(APIError):
    """Raised when request validation fails."""
    pass


class TransientAPIError(APIError):
    """Raised when a transient API error occurs (502, 503).

    These errors are typically temporary and can be retried with exponential backoff.
    """
    pass


class StatusPageClient:
    """Client for interacting with Nobl9 Status Page API.

    Supports automatic retry with exponential backoff for transient API errors (502, 503).
    """

    def __init__(
        self,
        config: Config,
        max_retries: int = 3,
        initial_backoff: float = 1.0,
        max_backoff: float = 32.0,
        backoff_multiplier: float = 2.0,
    ):
        """Initialize the client.

        Args:
            config: Configuration object with API credentials.
            max_retries: Maximum number of retry attempts for transient errors (default: 3).
            initial_backoff: Initial backoff delay in seconds (default: 1.0).
            max_backoff: Maximum backoff delay in seconds (default: 32.0).
            backoff_multiplier: Multiplier for exponential backoff (default: 2.0).
        """
        self.config = config
        self.session = requests.Session()
        self.access_token: Optional[str] = None

        # Retry configuration
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.max_backoff = max_backoff
        self.backoff_multiplier = backoff_multiplier

        # Set common headers
        self.session.headers.update({
            "organization": config.organization,
            "Content-Type": "application/json",
        })

        # If using client credentials, get access token on first use
        # If using pre-generated token, set it directly
        if config.api_token:
            self.access_token = config.api_token
            self.session.headers["Authorization"] = f"Bearer {config.api_token}"

    def _get_access_token(self) -> str:
        """Get access token from Nobl9 API using client credentials.

        Returns:
            Access token string.

        Raises:
            AuthenticationError: If token generation fails.
        """
        if self.access_token:
            return self.access_token

        # Use client credentials to get access token
        if not self.config.client_id or not self.config.client_secret:
            raise AuthenticationError(
                "Client credentials not configured. Set NOBL9_CLIENT_ID and NOBL9_CLIENT_SECRET."
            )

        # Create Basic auth header (client_id:client_secret base64 encoded)
        credentials = f"{self.config.client_id}:{self.config.client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()

        # Request access token
        response = requests.post(
            f"{self.config.base_url}/api/accessToken",
            headers={
                "Authorization": f"Basic {encoded_credentials}",
                "Organization": self.config.organization,
                "Accept": "application/json",
            },
        )

        if response.status_code == 200:
            self.access_token = response.json()["access_token"]
            # Update session with bearer token
            self.session.headers["Authorization"] = f"Bearer {self.access_token}"
            return self.access_token
        elif response.status_code == 401:
            raise AuthenticationError(
                "Failed to authenticate. Check your NOBL9_CLIENT_ID, NOBL9_CLIENT_SECRET, and NOBL9_ORG."
            )
        else:
            raise AuthenticationError(
                f"Token generation failed (HTTP {response.status_code}): {response.text}"
            )

    def _ensure_authenticated(self) -> None:
        """Ensure client is authenticated before making requests."""
        if not self.access_token:
            self._get_access_token()

    def _request_with_retry(
        self, request_func: Callable[[], requests.Response]
    ) -> Dict[str, Any]:
        """Execute a request with retry logic for transient errors.

        Implements exponential backoff for transient API errors (502, 503).

        Args:
            request_func: Function that performs the HTTP request.

        Returns:
            Parsed JSON response.

        Raises:
            TransientAPIError: If all retries are exhausted.
            Other exceptions: For non-retryable errors.
        """
        last_exception: Optional[Exception] = None
        backoff = self.initial_backoff

        for attempt in range(self.max_retries + 1):
            try:
                response = request_func()
                return self._handle_response(response)
            except TransientAPIError as e:
                last_exception = e

                # If this was the last attempt, raise the exception
                if attempt >= self.max_retries:
                    raise TransientAPIError(
                        f"Request failed after {self.max_retries + 1} attempts. "
                        f"Last error: {str(e)}"
                    ) from e

                # Calculate sleep time with exponential backoff
                sleep_time = min(backoff, self.max_backoff)

                # Log retry attempt (could be made configurable with a logger)
                print(
                    f"⚠️  Transient error on attempt {attempt + 1}/{self.max_retries + 1}: {e}",
                    flush=True,
                )
                print(f"   Retrying in {sleep_time:.1f} seconds...", flush=True)

                # Wait before retrying
                time.sleep(sleep_time)

                # Increase backoff for next attempt
                backoff *= self.backoff_multiplier

            except (AuthenticationError, NotFoundError, RateLimitError, ValidationError, APIError):
                # Non-transient errors should not be retried
                raise

        # This should never be reached, but just in case
        if last_exception:
            raise last_exception
        raise APIError("Request failed with unknown error")

    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """Handle API response and raise appropriate exceptions.

        Args:
            response: HTTP response object.

        Returns:
            Parsed JSON response.

        Raises:
            AuthenticationError: If authentication fails (401).
            NotFoundError: If resource not found (404).
            RateLimitError: If rate limit exceeded (429).
            ValidationError: If request validation fails (400).
            TransientAPIError: If transient error occurs (502, 503) - can be retried.
            APIError: For other API errors.
        """
        if response.status_code == 200:
            return response.json() if response.content else {}
        elif response.status_code == 201:
            return response.json()
        elif response.status_code == 400:
            error_msg = response.text or "Bad request - invalid parameters"
            raise ValidationError(f"Validation error: {error_msg}")
        elif response.status_code == 401:
            raise AuthenticationError(
                "Authentication failed. Check your NOBL9_API_TOKEN and NOBL9_ORG."
            )
        elif response.status_code == 404:
            raise NotFoundError("Resource not found")
        elif response.status_code == 429:
            raise RateLimitError("Rate limit exceeded. Please retry later.")
        elif response.status_code == 500:
            raise APIError(f"Server error: {response.text}")
        elif response.status_code in (502, 503):
            # Transient errors that can be retried
            error_msg = response.text or "Service temporarily unavailable"
            raise TransientAPIError(
                f"Transient API error (HTTP {response.status_code}): {error_msg}"
            )
        else:
            raise APIError(
                f"Unexpected error (HTTP {response.status_code}): {response.text}"
            )

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a GET request with automatic retry for transient errors.

        Args:
            path: API endpoint path (e.g., "/status-page/status").
            params: Optional query parameters.

        Returns:
            Parsed JSON response.

        Raises:
            TransientAPIError: If all retries exhausted for transient errors.
            Other exceptions: For non-retryable errors.
        """
        self._ensure_authenticated()
        url = f"{self.config.base_url}/api/dashboards/v1{path}"

        def make_request():
            return self.session.get(url, params=params)

        return self._request_with_retry(make_request)

    def post(self, path: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make a POST request with automatic retry for transient errors.

        Args:
            path: API endpoint path.
            data: Request body data.

        Returns:
            Parsed JSON response.

        Raises:
            TransientAPIError: If all retries exhausted for transient errors.
            Other exceptions: For non-retryable errors.
        """
        self._ensure_authenticated()
        url = f"{self.config.base_url}/api/dashboards/v1{path}"

        def make_request():
            return self.session.post(url, json=data)

        return self._request_with_retry(make_request)

    def put(self, path: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make a PUT request with automatic retry for transient errors.

        Args:
            path: API endpoint path.
            data: Request body data.

        Returns:
            Parsed JSON response.

        Raises:
            TransientAPIError: If all retries exhausted for transient errors.
            Other exceptions: For non-retryable errors.
        """
        self._ensure_authenticated()
        url = f"{self.config.base_url}/api/dashboards/v1{path}"

        def make_request():
            return self.session.put(url, json=data)

        return self._request_with_retry(make_request)

    def post_external(self, path: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make a POST request with Basic authentication (for external endpoints).

        The external endpoints require Basic auth (client_id:client_secret),
        not Bearer token auth. Includes automatic retry for transient errors.

        Args:
            path: API endpoint path.
            data: Request body data.

        Returns:
            Parsed JSON response.

        Raises:
            TransientAPIError: If all retries exhausted for transient errors.
            Other exceptions: For non-retryable errors.
        """
        if not self.config.client_id or not self.config.client_secret:
            raise AuthenticationError(
                "Client credentials required for external endpoint. "
                "Set NOBL9_CLIENT_ID and NOBL9_CLIENT_SECRET."
            )

        # Create Basic auth header (client_id:client_secret base64 encoded)
        credentials = f"{self.config.client_id}:{self.config.client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()

        url = f"{self.config.base_url}/api/dashboards/v1{path}"
        headers = {
            "organization": self.config.organization,
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/json",
        }

        def make_request():
            return requests.post(url, json=data, headers=headers)

        return self._request_with_retry(make_request)


def pretty_print(data: Any) -> None:
    """Print data as pretty-formatted JSON.

    Args:
        data: Data to print (will be JSON serialized).
    """
    print(json.dumps(data, indent=2, default=str))
