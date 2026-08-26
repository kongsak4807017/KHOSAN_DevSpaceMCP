import json
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


class ProfileError(ValueError):
    pass


@dataclass(frozen=True)
class MaterializedProfile:
    config_dir: Path
    state_dir: Path
    worktree_dir: Path
    config_path: Path
    auth_path: Path
    owner_token: str
    environment: dict[str, str]


def _atomic_write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def _load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        raise ProfileError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ProfileError(f"expected a JSON object in {path}")
    return value


def _validate_allowed_roots(values: object) -> list[str]:
    if not isinstance(values, list) or not values:
        raise ProfileError("allowedRoots must contain at least one project directory")
    normalized: list[str] = []
    forbidden_roots = {
        Path.home().resolve(),
        (Path.home() / "Downloads").resolve(),
    }
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise ProfileError("allowedRoots entries must be non-empty strings")
        resolved = Path(value).expanduser().resolve()
        if resolved == Path(resolved.anchor) or resolved in forbidden_roots:
            raise ProfileError(f"broad root is not allowed: {resolved}")
        normalized.append(str(resolved))
    return normalized


def _validated_port(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 65535:
        raise ProfileError("port must be an integer between 1 and 65535")
    return value


def _validate_unique_port(root: Path, current_name: str, port: int) -> None:
    profiles_root = root / "profiles"
    for candidate in profiles_root.glob("*/profile.json"):
        if candidate.parent.name == current_name:
            continue
        other = _load_json(candidate)
        if other.get("port") == port:
            raise ProfileError(
                f"port {port} is already used by active profile {candidate.parent.name!r}"
            )


def _validate_public_base_url(name: str, value: object) -> str | None:
    if value in (None, ""):
        if name == "web":
            raise ProfileError("web profile requires a stable HTTPS origin")
        return None
    parsed = urlparse(str(value))
    if name == "web" and (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.hostname.endswith(".example")
    ):
        raise ProfileError("web profile requires a real stable HTTPS origin")
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ProfileError("publicBaseUrl must be an absolute HTTP(S) URL")
    return str(value).rstrip("/")


def materialize_profile(
    repo_root: Path,
    name: str,
    token_factory: Callable[[], str] = lambda: secrets.token_urlsafe(32),
) -> MaterializedProfile:
    root = Path(repo_root).resolve()
    profile_path = root / "profiles" / name / "profile.json"
    profile = _load_json(profile_path)
    if profile.get("name") != name:
        raise ProfileError(f"profile name must be {name!r}")

    port = _validated_port(profile.get("port"))
    _validate_unique_port(root, name, port)
    allowed_roots = _validate_allowed_roots(profile.get("allowedRoots"))
    public_base_url = _validate_public_base_url(name, profile.get("publicBaseUrl"))
    runtime = root / "runtime" / name
    config_dir = runtime / "config"
    state_dir = runtime / "state"
    worktree_dir = runtime / "worktrees"
    log_dir = runtime / "logs"
    for directory in (config_dir, state_dir, worktree_dir, log_dir):
        directory.mkdir(parents=True, exist_ok=True)

    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.json"
    auth_path = config_dir / "auth.json"
    config = {
        "host": "127.0.0.1",
        "port": port,
        "allowedRoots": allowed_roots,
        "stateDir": str(state_dir),
        "worktreeRoot": str(worktree_dir),
    }
    if public_base_url:
        config["publicBaseUrl"] = public_base_url
    _atomic_write_json(config_path, config)

    existing_auth = _load_json(auth_path)
    owner_token = existing_auth.get("ownerToken")
    if not isinstance(owner_token, str) or len(owner_token) < 16:
        owner_token = token_factory()
        if not isinstance(owner_token, str) or len(owner_token) < 16:
            raise ProfileError("generated owner token must be at least 16 characters")
        _atomic_write_json(auth_path, {"ownerToken": owner_token})

    environment = {
        "DEVSPACE_CONFIG_DIR": str(config_dir),
        "DEVSPACE_STATE_DIR": str(state_dir),
        "DEVSPACE_WORKTREE_ROOT": str(worktree_dir),
        "DEVSPACE_TOOL_MODE": str(profile.get("toolMode", "minimal")),
        "DEVSPACE_WIDGETS": str(profile.get("widgets", "changes")),
        "DEVSPACE_SKILLS": "1" if profile.get("skillsEnabled", True) else "0",
        "DEVSPACE_SUBAGENTS": "1" if profile.get("subagentsEnabled", False) else "0",
        "DEVSPACE_LOG_SHELL_COMMANDS": "0",
        "HOST": "127.0.0.1",
        "PORT": str(port),
    }
    return MaterializedProfile(
        config_dir=config_dir,
        state_dir=state_dir,
        worktree_dir=worktree_dir,
        config_path=config_path,
        auth_path=auth_path,
        owner_token=owner_token,
        environment=environment,
    )
