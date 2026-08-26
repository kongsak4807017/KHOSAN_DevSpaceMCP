import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class StateStore:
    def __init__(self, path: Path):
        self.path = Path(path).resolve()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS workspaces (
                    workspace_id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    root_path TEXT NOT NULL UNIQUE,
                    repository TEXT,
                    expected_remote TEXT,
                    runtime_profile TEXT,
                    governance_files_json TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1))
                );

                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    intent TEXT NOT NULL,
                    workflow_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    request_hash TEXT NOT NULL UNIQUE,
                    expected_head TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS job_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    details_json TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS worker_leases (
                    job_id TEXT PRIMARY KEY,
                    worker_id TEXT NOT NULL,
                    lease_until REAL NOT NULL,
                    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS evidence (
                    evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    verifier TEXT NOT NULL,
                    passed INTEGER NOT NULL CHECK (passed IN (0, 1)),
                    exit_code INTEGER,
                    passed_count INTEGER,
                    failed_count INTEGER,
                    skipped_count INTEGER,
                    total_count INTEGER,
                    commit_sha TEXT,
                    artifact_path TEXT,
                    artifact_hash TEXT,
                    external_run_id TEXT,
                    external_conclusion TEXT,
                    details_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE RESTRICT
                );

                CREATE INDEX IF NOT EXISTS idx_job_events_job_sequence
                    ON job_events(job_id, sequence);
                CREATE INDEX IF NOT EXISTS idx_jobs_status
                    ON jobs(status);
                CREATE INDEX IF NOT EXISTS idx_evidence_job_kind
                    ON evidence(job_id, kind, evidence_id);
                CREATE INDEX IF NOT EXISTS idx_worker_leases_until
                    ON worker_leases(lease_until);
                """
            )
