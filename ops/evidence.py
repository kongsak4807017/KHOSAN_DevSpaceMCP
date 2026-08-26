import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from .jobs import JobStatus
from .state import StateStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: int
    job_id: str
    kind: str
    verifier: str
    passed: bool
    exit_code: int | None
    passed_count: int | None
    failed_count: int | None
    skipped_count: int | None
    total_count: int | None
    commit_sha: str | None
    artifact_path: str | None
    artifact_hash: str | None
    external_run_id: str | None
    external_conclusion: str | None
    details: dict
    created_at: str


@dataclass(frozen=True)
class ClosureDecision:
    status: JobStatus
    missing: tuple[str, ...] = ()
    failed: tuple[str, ...] = ()
    human_gate: bool = False


class EvidenceRepository:
    def __init__(self, store: StateStore):
        self.store = store

    @staticmethod
    def _record(row: sqlite3.Row) -> EvidenceRecord:
        return EvidenceRecord(
            evidence_id=int(row["evidence_id"]),
            job_id=str(row["job_id"]),
            kind=str(row["kind"]),
            verifier=str(row["verifier"]),
            passed=bool(row["passed"]),
            exit_code=row["exit_code"],
            passed_count=row["passed_count"],
            failed_count=row["failed_count"],
            skipped_count=row["skipped_count"],
            total_count=row["total_count"],
            commit_sha=row["commit_sha"],
            artifact_path=row["artifact_path"],
            artifact_hash=row["artifact_hash"],
            external_run_id=row["external_run_id"],
            external_conclusion=row["external_conclusion"],
            details=json.loads(row["details_json"]),
            created_at=str(row["created_at"]),
        )

    def add(
        self,
        job_id: str,
        kind: str,
        *,
        passed: bool,
        verifier: str,
        exit_code: int | None = None,
        passed_count: int | None = None,
        failed_count: int | None = None,
        skipped_count: int | None = None,
        total_count: int | None = None,
        commit_sha: str | None = None,
        artifact_path: str | None = None,
        artifact_hash: str | None = None,
        external_run_id: str | None = None,
        external_conclusion: str | None = None,
        details: dict | None = None,
    ) -> EvidenceRecord:
        if not job_id.strip() or not kind.strip() or not verifier.strip():
            raise ValueError("job_id, kind, and verifier are required")
        timestamp = _now()
        payload = json.dumps(details or {}, sort_keys=True, ensure_ascii=False)
        with self.store.connection() as connection:
            job = connection.execute(
                "SELECT 1 FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            if job is None:
                raise ValueError(f"unknown job: {job_id}")
            cursor = connection.execute(
                """
                INSERT INTO evidence(
                    job_id, kind, verifier, passed, exit_code,
                    passed_count, failed_count, skipped_count, total_count,
                    commit_sha, artifact_path, artifact_hash,
                    external_run_id, external_conclusion, details_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    kind,
                    verifier,
                    1 if passed else 0,
                    exit_code,
                    passed_count,
                    failed_count,
                    skipped_count,
                    total_count,
                    commit_sha,
                    artifact_path,
                    artifact_hash,
                    external_run_id,
                    external_conclusion,
                    payload,
                    timestamp,
                ),
            )
            evidence_id = int(cursor.lastrowid)
        return self.get(evidence_id)

    def get(self, evidence_id: int) -> EvidenceRecord:
        with self.store.connection() as connection:
            row = connection.execute(
                "SELECT * FROM evidence WHERE evidence_id = ?", (evidence_id,)
            ).fetchone()
        if row is None:
            raise ValueError(f"unknown evidence: {evidence_id}")
        return self._record(row)

    def for_job(self, job_id: str) -> list[EvidenceRecord]:
        with self.store.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM evidence WHERE job_id = ? ORDER BY evidence_id",
                (job_id,),
            ).fetchall()
        return [self._record(row) for row in rows]


class ClosurePolicy:
    def __init__(self, evidence: EvidenceRepository):
        self.evidence = evidence

    def evaluate(
        self,
        job_id: str,
        required_kinds: tuple[str, ...],
        *,
        human_gate: bool = False,
    ) -> ClosureDecision:
        latest: dict[str, EvidenceRecord] = {}
        for record in self.evidence.for_job(job_id):
            latest[record.kind] = record

        missing = tuple(kind for kind in required_kinds if kind not in latest)
        if missing:
            return ClosureDecision(
                JobStatus.NEEDS_HUMAN,
                missing=missing,
                human_gate=human_gate,
            )

        failed = tuple(kind for kind in required_kinds if not latest[kind].passed)
        if failed:
            return ClosureDecision(
                JobStatus.FAILED,
                failed=failed,
                human_gate=human_gate,
            )

        if human_gate:
            return ClosureDecision(JobStatus.NEEDS_HUMAN, human_gate=True)

        return ClosureDecision(JobStatus.SUCCEEDED)
