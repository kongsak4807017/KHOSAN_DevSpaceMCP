import json
import re
import sqlite3
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .state import StateStore


class WorkspaceError(ValueError):
    pass


_WORKSPACE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


@dataclass(frozen=True)
class WorkspaceRecord:
    workspace_id: str
    display_name: str
    root_path: str
    repository: str | None
    expected_remote: str | None
    runtime_profile: str | None
    governance_files: tuple[str, ...]
    enabled: bool


@dataclass(frozen=True)
class WorkspacePreflight:
    workspace: WorkspaceRecord
    repository: str | None
    branch: str | None
    head: str | None
    dirty: bool | None


def _canonical_project_root(path: Path) -> Path:
    requested = Path(path).expanduser()
    if not requested.exists() or not requested.is_dir():
        raise WorkspaceError(f"workspace root does not exist or is not a directory: {requested}")
    resolved = requested.resolve()
    broad_roots = {
        Path(resolved.anchor).resolve(),
        Path.home().resolve(),
        (Path.home() / "Downloads").resolve(),
    }
    if resolved in broad_roots:
        raise WorkspaceError(f"broad root is not allowed: {resolved}")
    return resolved


def _normalize_repository(value: str) -> str:
    text = value.strip().rstrip("/")
    if text.endswith(".git"):
        text = text[:-4]
    if text.startswith("git@") and ":" in text:
        text = text.split(":", 1)[1]
    elif "://" in text:
        parsed = urlparse(text)
        text = parsed.path.lstrip("/")
    return text.strip("/").lower()


def _git(root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


class WorkspaceRegistry:
    def __init__(self, store: StateStore):
        self.store = store

    @staticmethod
    def _record(row: sqlite3.Row) -> WorkspaceRecord:
        return WorkspaceRecord(
            workspace_id=str(row["workspace_id"]),
            display_name=str(row["display_name"]),
            root_path=str(row["root_path"]),
            repository=row["repository"],
            expected_remote=row["expected_remote"],
            runtime_profile=row["runtime_profile"],
            governance_files=tuple(json.loads(row["governance_files_json"])),
            enabled=bool(row["enabled"]),
        )

    def add(
        self,
        workspace_id: str,
        root_path: Path,
        *,
        display_name: str | None = None,
        repository: str | None = None,
        expected_remote: str | None = None,
        runtime_profile: str | None = None,
        governance_files: tuple[str, ...] = ("AGENTS.md",),
    ) -> WorkspaceRecord:
        if not _WORKSPACE_ID.fullmatch(workspace_id):
            raise WorkspaceError("workspace_id must use letters, numbers, dot, underscore, or hyphen")
        root = _canonical_project_root(root_path)
        if not governance_files or any(not item.strip() for item in governance_files):
            raise WorkspaceError("governance_files must contain non-empty relative paths")
        if any(Path(item).is_absolute() or ".." in Path(item).parts for item in governance_files):
            raise WorkspaceError("governance_files must stay relative to the workspace")
        try:
            with self.store.connection() as connection:
                connection.execute(
                    """
                    INSERT INTO workspaces(
                        workspace_id, display_name, root_path, repository,
                        expected_remote, runtime_profile, governance_files_json, enabled
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                    (
                        workspace_id,
                        display_name or workspace_id,
                        str(root),
                        repository,
                        expected_remote,
                        runtime_profile,
                        json.dumps(list(governance_files)),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise WorkspaceError(f"workspace already exists: {workspace_id}") from exc
        return self.get(workspace_id)

    def get(self, workspace_id: str) -> WorkspaceRecord:
        with self.store.connection() as connection:
            row = connection.execute(
                "SELECT * FROM workspaces WHERE workspace_id = ?", (workspace_id,)
            ).fetchone()
        if row is None:
            raise WorkspaceError(f"unknown workspace: {workspace_id}")
        return self._record(row)

    def list(self, *, include_disabled: bool = True) -> list[WorkspaceRecord]:
        sql = "SELECT * FROM workspaces"
        params: tuple[object, ...] = ()
        if not include_disabled:
            sql += " WHERE enabled = ?"
            params = (1,)
        sql += " ORDER BY workspace_id"
        with self.store.connection() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self._record(row) for row in rows]

    def disable(self, workspace_id: str) -> WorkspaceRecord:
        self.get(workspace_id)
        with self.store.connection() as connection:
            connection.execute(
                "UPDATE workspaces SET enabled = 0 WHERE workspace_id = ?",
                (workspace_id,),
            )
        return self.get(workspace_id)

    def preflight(self, workspace_id: str) -> WorkspacePreflight:
        workspace = self.get(workspace_id)
        if not workspace.enabled:
            raise WorkspaceError(f"workspace is disabled: {workspace_id}")
        root = Path(workspace.root_path)
        if not root.exists() or not root.is_dir():
            raise WorkspaceError(f"workspace root is unavailable: {root}")

        remote_name = workspace.expected_remote or "origin"
        remote_url = _git(root, "remote", "get-url", remote_name)
        actual_repository = _normalize_repository(remote_url) if remote_url else None
        if workspace.repository:
            expected_repository = _normalize_repository(workspace.repository)
            if actual_repository != expected_repository:
                raise WorkspaceError(
                    "repository identity mismatch: "
                    f"expected {expected_repository}, got {actual_repository or 'none'}"
                )

        head = _git(root, "rev-parse", "HEAD")
        branch = _git(root, "branch", "--show-current")
        status = _git(root, "status", "--porcelain")
        return WorkspacePreflight(
            workspace=workspace,
            repository=actual_repository,
            branch=branch or None,
            head=head or None,
            dirty=None if status is None else bool(status),
        )
