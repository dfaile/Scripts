"""
Load .env from package root or cwd. Used by Config. Never log or print secret values.
"""
import os
from pathlib import Path
from typing import List, Optional, Tuple

try:
    from dotenv import load_dotenv as _load_dotenv
except ImportError:
    _load_dotenv = None


def _minimal_load(path: Path) -> None:
    """Parse KEY=VALUE lines and set os.environ (no interpolation)."""
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if key:
                os.environ.setdefault(key, value.strip().strip('"').strip("'"))


def get_env_path(package_root: Path) -> Optional[Path]:
    """Return first existing .env path: package_root/.env or cwd/.env."""
    if (package_root / ".env").is_file():
        return package_root / ".env"
    if (Path.cwd() / ".env").is_file():
        return Path.cwd() / ".env"
    return None


def load_env(package_root: Path) -> Tuple[Optional[Path], bool]:
    """Load .env from package root then cwd (cwd overrides). Returns (path_loaded, True if any loaded)."""
    loaded = False
    for path in (package_root / ".env", Path.cwd() / ".env"):
        if path.is_file():
            if _load_dotenv is not None:
                _load_dotenv(path, override=(path == Path.cwd() / ".env"))
            else:
                _minimal_load(path)
            loaded = True
    return (get_env_path(package_root), loaded)


def get_missing_required() -> List[str]:
    """Return list of required variable names that are missing. Does not return values."""
    missing: List[str] = []
    if not (os.getenv("NOBL9_ORG") or "").strip():
        missing.append("NOBL9_ORG")
    if (os.getenv("NOBL9_API_TOKEN") or "").strip():
        return missing
    if not (os.getenv("NOBL9_CLIENT_ID") or "").strip():
        missing.append("NOBL9_CLIENT_ID")
    if not (os.getenv("NOBL9_CLIENT_SECRET") or "").strip():
        missing.append("NOBL9_CLIENT_SECRET")
    return missing
