import logging
import os
import urllib.error
import urllib.request
from logging.handlers import RotatingFileHandler
from pathlib import Path
from urllib.parse import urlparse


def resolve_devspace_command(repo_root: Path, os_name: str | None = None) -> Path:
    root = Path(repo_root).resolve()
    platform = os_name or os.name
    executable = "devspace.cmd" if platform == "nt" else "devspace"
    command = root / "node_modules" / ".bin" / executable
    if not command.is_file():
        raise FileNotFoundError(
            f"repo-local DevSpace is missing at {command}; run npm ci first"
        )
    return command


def endpoint_for_config(config: dict) -> str:
    public_base_url = config.get("publicBaseUrl")
    if public_base_url:
        base = str(public_base_url).rstrip("/")
        parsed = urlparse(base)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("publicBaseUrl must be an absolute HTTP(S) URL")
        return f"{base}/mcp"
    host = str(config.get("host", "127.0.0.1"))
    port = int(config.get("port", 7676))
    return f"http://{host}:{port}/mcp"


def build_child_environment(base: dict[str, str], profile: dict[str, str]) -> dict[str, str]:
    environment = {str(key): str(value) for key, value in base.items()}
    environment.update({str(key): str(value) for key, value in profile.items()})
    environment.pop("ownerToken", None)
    return environment


def mcp_is_ready(url: str, timeout: float = 3) -> bool:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return 200 <= response.status < 400
    except urllib.error.HTTPError as exc:
        try:
            challenge = exc.headers.get("WWW-Authenticate", "").lower()
            return exc.code == 401 and "bearer" in challenge
        finally:
            exc.close()
    except (OSError, urllib.error.URLError, ValueError):
        return False


def make_rotating_logger(
    path: Path,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
) -> logging.Logger:
    if max_bytes < 1 or backup_count < 1:
        raise ValueError("log rotation limits must be positive")
    log_path = Path(path).resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(f"KHOSAN_DevSpace.{log_path}")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    for existing in list(logger.handlers):
        existing.close()
        logger.removeHandler(existing)
    handler = RotatingFileHandler(
        log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    return logger
