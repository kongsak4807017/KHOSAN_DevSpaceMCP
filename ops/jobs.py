from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from .state import StateStore


class JobError(ValueError):
    pass


class JobStatus(str, Enum):
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    CLAIMED = "CLAIMED"
    PREFLIGHT = "PREFLIGHT"
    RUNNING = "RUNNING"
    VERIFYING = "VERIFYING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    NEEDS_HUMAN = "NEEDS_HUMAN"
    CANCELLED = "CANCELLED"


_TERMINAL = {
    JobStatus.SUCCEEDED,
    JobStatus.FAILED,
    JobStatus.BLOCKED,
    JobStatus.NEEDS_HUMAN,
    JobStatus.CANCELLED,
}

_ALLOWED: dict[JobStatus, set[JobStatus]] = {
    JobStatus.CREATED: {JobStatus.QUEUED, JobStatus.CANCELLED},
    JobStatus.QUEUED: {JobStatus.CLAIMED, JobStatus.CANCELLED},
    JobStatus.CLAIMED: {
        JobStatus.PREFLIGHT,
        JobStatus.FAILED,
        JobStatus.BLOCKED,
        JobStatus.CANCELLED,
    },
    JobStatus.PREFLIGHT: {
        JobStatus.RUNNING,
        JobStatus.FAILED,
        JobStatus.BLOCKED,
        JobStatus.NEEDS_HUMAN,
        JobStatus.CANCELLED,
    },
    JobStatus.RUNNING: {
        JobStatus.VERIFYING,
        JobStatus.FAILED,
        JobStatus.BLOCKED,
        JobStatus.NEEDS_HUMAN,
        JobStatus.CANCELLED,
    },
    JobStatus.VERIFYING: {
        JobStatus.SUCCEEDED,
        JobStatus.FAILED,
        JobStatus.BLOCKED,
        JobStatus.NEEDS_HUMAN,
        JobStatus.CANCELLED,
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _request_hash(
    workspace_id: str,
    intent: str,
    workflow_type: str,
    expected_head: str | None,
) -> str:
    payload = json.dumps(
        {
            "workspace_id": workspace_id,
            "intent": intent,
            "workflow_type": workflow_type,
            "expected_head": expected_head,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class JobRecord:
    job_id: str
    workspace_id: str
    intent: str
    workflow_type: str
    status: JobStatus
    request_hash: str
    expected_head: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class JobEvent:
    sequence: int
    job_id: str
    status: JobStatus
    created_at: str
    details: dict


class JobRepository:
    def __init__(self, store: StateStore):
        self.store = store

    @staticmethod
    def _job(row: sqlite3.Row) -> JobRecord:
        return JobRecord(
            job_id=str(row["job_id"]),
            workspace_id=str(row["workspace_id"]),
            intent=str(row["intent"]),
            workflow_type=str(row["workflow_type"]),
            status=JobStatus(row["status"]),
            request_hash=str(row["request_hash"]),
            expected_head=row["expected_head"],
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    def create(
        self,
        workspace_id: str,
        intent: str,
        workflow_type: str,
        *,
        expected_head: str | None = None,
    ) -> JobRecord:
        if not workspace_id.strip() or not intent.strip() or not workflow_type.strip():
            raise JobError("workspace_id, intent, and workflow_type are required")
        request_hash = _request_hash(workspace_id, intent, workflow_type, expected_head)
        with self.store.connection() as connection:
            existing = connection.execute(
                "SELECT * FROM jobs WHERE request_hash = ?", (request_hash,)
            ).fetchone()
            if existing is not None:
                return self._job(existing)

            job_id = f"job_{uuid.uuid4().hex}"
            timestamp = _now()
            try:
                connection.execute(
                    """
                    INSERT INTO jobs(
                        job_id, workspace_id, intent, workflow_type, status,
                        request_hash, expected_head, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job_id,
                        workspace_id,
                        intent,
                        workflow_type,
                        JobStatus.CREATED.value,
                        request_hash,
                        expected_head,
                        timestamp,
                        timestamp,
                    ),
                )
                connection.execute(
                    "INSERT INTO job_events(job_id, status, created_at, details_json) VALUES (?, ?, ?, ?)",
                    (job_id, JobStatus.CREATED.value, timestamp, "{}"),
                )
            except sqlite3.IntegrityError:
                existing = connection.execute(
                    "SELECT * FROM jobs WHERE request_hash = ?", (request_hash,)
                ).fetchone()
                if existing is None:
                    raise
                return self._job(existing)
        return self.get(job_id)

    def get(self, job_id: str) -> JobRecord:
        with self.store.connection() as connection:
            row = connection.execute(
                "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
        if row is None:
            raise JobError(f"unknown job: {job_id}")
        return self._job(row)

    def list(self) -> list[JobRecord]:
        with self.store.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM jobs ORDER BY created_at, job_id"
            ).fetchall()
        return [self._job(row) for row in rows]

    def enqueue(self, job_id: str) -> JobRecord:
        return self.transition(job_id, JobStatus.QUEUED)

    def transition(
        self,
        job_id: str,
        status: JobStatus,
        *,
        details: dict | None = None,
    ) -> JobRecord:
        current = self.get(job_id)
        if current.status in _TERMINAL:
            raise JobError(f"job is terminal: {job_id} ({current.status.value})")
        allowed = _ALLOWED.get(current.status, set())
        if status not in allowed:
            raise JobError(
                f"illegal transition: {current.status.value} -> {status.value}"
            )
        timestamp = _now()
        payload = json.dumps(details or {}, sort_keys=True, ensure_ascii=False)
        with self.store.connection() as connection:
            cursor = connection.execute(
                "UPDATE jobs SET status = ?, updated_at = ? WHERE job_id = ? AND status = ?",
                (status.value, timestamp, job_id, current.status.value),
            )
            if cursor.rowcount != 1:
                raise JobError(f"concurrent job transition rejected: {job_id}")
            connection.execute(
                "INSERT INTO job_events(job_id, status, created_at, details_json) VALUES (?, ?, ?, ?)",
                (job_id, status.value, timestamp, payload),
            )
        return self.get(job_id)

    def events(self, job_id: str) -> list[JobEvent]:
        self.get(job_id)
        with self.store.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM job_events WHERE job_id = ? ORDER BY sequence",
                (job_id,),
            ).fetchall()
        return [
            JobEvent(
                sequence=int(row["sequence"]),
                job_id=str(row["job_id"]),
                status=JobStatus(row["status"]),
                created_at=str(row["created_at"]),
                details=json.loads(row["details_json"]),
            )
            for row in rows
        ]
