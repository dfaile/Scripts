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
    """Raised when a transient API error occurs (502, 503)."""
    pass


class StatusPageClient:
    """Client for Nobl9 Status Page API with retry and disruption helpers (Mar 16 API)."""

    def __init__(
        self,
        config: Config,
        max_retries: int = 3,
        initial_backoff: float = 1.0,
        max_backoff: float = 32.0,
        backoff_multiplier: float = 2.0,
    ):
        self.config = config
        self.session = requests.Session()
        self.access_token: Optional[str] = None
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.max_backoff = max_backoff
        self.backoff_multiplier = backoff_multiplier
        self.session.headers.update({
            "organization": config.organization,
            "Content-Type": "application/json",
        })
        if config.api_token:
            self.access_token = config.api_token
            self.session.headers["Authorization"] = f"Bearer {config.api_token}"

    def _get_access_token(self) -> str:
        if self.access_token:
            return self.access_token
        if not self.config.client_id or not self.config.client_secret:
            raise AuthenticationError(
                "Client credentials not configured. Set NOBL9_CLIENT_ID and NOBL9_CLIENT_SECRET."
            )
        credentials = f"{self.config.client_id}:{self.config.client_secret}"
        encoded = base64.b64encode(credentials.encode()).decode()
        response = requests.post(
            f"{self.config.base_url}/api/accessToken",
            headers={
                "Authorization": f"Basic {encoded}",
                "Organization": self.config.organization,
                "Accept": "application/json",
            },
        )
        if response.status_code == 200:
            self.access_token = response.json()["access_token"]
            self.session.headers["Authorization"] = f"Bearer {self.access_token}"
            return self.access_token
        elif response.status_code == 401:
            raise AuthenticationError(
                "Failed to authenticate. Check NOBL9_CLIENT_ID, NOBL9_CLIENT_SECRET, NOBL9_ORG."
            )
        raise AuthenticationError(
            f"Token generation failed (HTTP {response.status_code}): {response.text}"
        )

    def _ensure_authenticated(self) -> None:
        if not self.access_token:
            self._get_access_token()

    def _request_with_retry(self, request_func: Callable[[], requests.Response]) -> Dict[str, Any]:
        last_exception = None
        backoff = self.initial_backoff
        for attempt in range(self.max_retries + 1):
            try:
                return self._handle_response(request_func())
            except TransientAPIError as e:
                last_exception = e
                if attempt >= self.max_retries:
                    raise TransientAPIError(
                        f"Request failed after {self.max_retries + 1} attempts. Last error: {e}"
                    ) from e
                print(f"⚠️  Transient error (attempt {attempt + 1}/{self.max_retries + 1}): {e}", flush=True)
                print(f"   Retrying in {min(backoff, self.max_backoff):.1f}s...", flush=True)
                time.sleep(min(backoff, self.max_backoff))
                backoff *= self.backoff_multiplier
            except (AuthenticationError, NotFoundError, RateLimitError, ValidationError, APIError):
                raise
        if last_exception:
            raise last_exception
        raise APIError("Request failed")

    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        if response.status_code in (200, 201):
            return response.json() if response.content else {}
        if response.status_code == 204:
            return {}
        if response.status_code == 400:
            raise ValidationError(f"Validation error: {response.text or 'Bad request'}")
        if response.status_code == 401:
            raise AuthenticationError("Authentication failed. Check NOBL9 credentials and NOBL9_ORG.")
        if response.status_code == 404:
            raise NotFoundError("Resource not found")
        if response.status_code == 429:
            raise RateLimitError("Rate limit exceeded.")
        if response.status_code in (502, 503):
            raise TransientAPIError(f"Transient error (HTTP {response.status_code}): {response.text or 'Unavailable'}")
        raise APIError(f"Unexpected error (HTTP {response.status_code}): {response.text}")

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._ensure_authenticated()
        url = f"{self.config.base_url}/api/dashboards/v1{path}"
        return self._request_with_retry(lambda: self.session.get(url, params=params))

    def post(self, path: str, data: Dict[str, Any]) -> Dict[str, Any]:
        self._ensure_authenticated()
        url = f"{self.config.base_url}/api/dashboards/v1{path}"
        return self._request_with_retry(lambda: self.session.post(url, json=data))

    def put(self, path: str, data: Dict[str, Any]) -> Dict[str, Any]:
        self._ensure_authenticated()
        url = f"{self.config.base_url}/api/dashboards/v1{path}"
        return self._request_with_retry(lambda: self.session.put(url, json=data))

    # Disruption helpers (Mar 16 API)
    def get_disruptions(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self.get("/status-page/disruptions", params=params or {})

    def get_disruptions_timeline(self, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self.post("/status-page/disruptions/timeline", body or {})

    def register_disruption(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.post("/status-page/disruptions", payload)

    def change_disruption_severity(self, disruption_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.post(f"/status-page/disruptions/{disruption_id}/change-severity", payload)

    def clear_disruption(self, disruption_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.post(f"/status-page/disruptions/{disruption_id}/clear", payload)

    def list_component_disruptions(self, component_id: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self.post(f"/status-page/components/{component_id}/disruptions", body or {})

    def post_external(self, path: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.config.client_id or not self.config.client_secret:
            raise AuthenticationError("Client credentials required. Set NOBL9_CLIENT_ID and NOBL9_CLIENT_SECRET.")
        credentials = f"{self.config.client_id}:{self.config.client_secret}"
        encoded = base64.b64encode(credentials.encode()).decode()
        url = f"{self.config.base_url}/api/dashboards/v1{path}"
        headers = {
            "organization": self.config.organization,
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/json",
        }
        return self._request_with_retry(lambda: requests.post(url, json=data, headers=headers))


def pretty_print(data: Any) -> None:
    print(json.dumps(data, indent=2, default=str))
