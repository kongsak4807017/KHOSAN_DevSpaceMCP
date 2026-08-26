import json
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path


class FailureClass(StrEnum):
    HOST_CAPABILITY = "host_capability"
    TRANSPORT = "transport"
    AUTH_CONTRACT = "auth_contract"
    TOOL_RUNTIME = "tool_runtime"
    SERVER = "server"
    UNKNOWN = "unknown"


def classify_failure(
    *,
    forbidden: bool,
    inbound_request_seen: bool,
    local_ready: bool,
    public_ready: bool,
    auth_error: bool,
    tool_call_started: bool,
) -> FailureClass:
    if forbidden and not inbound_request_seen:
        return FailureClass.HOST_CAPABILITY
    if local_ready and not public_ready:
        return FailureClass.TRANSPORT
    if inbound_request_seen and auth_error:
        return FailureClass.AUTH_CONTRACT
    if inbound_request_seen and tool_call_started:
        return FailureClass.TOOL_RUNTIME
    if not local_ready:
        return FailureClass.SERVER
    return FailureClass.UNKNOWN


def last_openai_request_timestamp(log_path: Path) -> str | None:
    latest = None
    try:
        lines = Path(log_path).open("r", encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return None
    with lines:
        for line in lines:
            try:
                event = json.loads(line)
            except (json.JSONDecodeError, TypeError):
                continue
            if event.get("userAgent") == "openai-mcp/1.0.0" and isinstance(
                event.get("ts"), str
            ):
                latest = event["ts"]
    return latest


def fresh_openai_request(
    log_path: Path,
    *,
    now: datetime | None = None,
    window_seconds: int = 120,
) -> tuple[bool, str | None]:
    if window_seconds < 1:
        raise ValueError("window_seconds must be positive")
    timestamp = last_openai_request_timestamp(log_path)
    if timestamp is None:
        return False, None
    try:
        observed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return False, timestamp
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    age = (current - observed).total_seconds()
    return 0 <= age <= window_seconds, timestamp
