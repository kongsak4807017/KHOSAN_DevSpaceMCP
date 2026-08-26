import json
from dataclasses import dataclass
from datetime import datetime, timezone

from .evidence import ClosurePolicy
from .jobs import JobRecord, JobRepository, JobStatus
from .state import StateStore
from .workflows import WorkflowRouter
from .workspaces import WorkspaceError, WorkspaceRecord, WorkspaceRegistry


class WorkerError(ValueError):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ExecutionResult:
    success: bool
    summary: str = ""


class WorkerLeaseRepository:
    def __init__(self, store: StateStore, jobs: JobRepository):
        self.store = store
        self.jobs = jobs

    def claim_next(
        self,
        worker_id: str,
        *,
        now: float,
        lease_seconds: float,
    ) -> JobRecord | None:
        if not worker_id.strip():
            raise WorkerError("worker_id is required")
        if lease_seconds <= 0:
            raise WorkerError("lease_seconds must be positive")
        lease_until = float(now) + float(lease_seconds)
        claimed_job_id: str | None = None

        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT j.job_id, j.status
                FROM jobs AS j
                LEFT JOIN worker_leases AS l ON l.job_id = j.job_id
                WHERE j.status IN (?, ?, ?, ?, ?)
                  AND (l.job_id IS NULL OR l.lease_until <= ?)
                ORDER BY
                    CASE WHEN j.status = ? THEN 1 ELSE 0 END,
                    j.created_at,
                    j.job_id
                LIMIT 1
                """,
                (
                    JobStatus.CLAIMED.value,
                    JobStatus.PREFLIGHT.value,
                    JobStatus.RUNNING.value,
                    JobStatus.VERIFYING.value,
                    JobStatus.QUEUED.value,
                    float(now),
                    JobStatus.QUEUED.value,
                ),
            ).fetchone()
            if row is None:
                return None

            claimed_job_id = str(row["job_id"])
            current_status = JobStatus(str(row["status"]))
            if current_status == JobStatus.QUEUED:
                timestamp = _now_iso()
                cursor = connection.execute(
                    """
                    UPDATE jobs
                    SET status = ?, updated_at = ?
                    WHERE job_id = ? AND status = ?
                    """,
                    (
                        JobStatus.CLAIMED.value,
                        timestamp,
                        claimed_job_id,
                        JobStatus.QUEUED.value,
                    ),
                )
                if cursor.rowcount != 1:
                    raise WorkerError(f"concurrent claim rejected: {claimed_job_id}")
                connection.execute(
                    """
                    INSERT INTO job_events(job_id, status, created_at, details_json)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        claimed_job_id,
                        JobStatus.CLAIMED.value,
                        timestamp,
                        json.dumps({"worker_id": worker_id}, sort_keys=True),
                    ),
                )

            connection.execute(
                """
                INSERT INTO worker_leases(job_id, worker_id, lease_until)
                VALUES (?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    worker_id = excluded.worker_id,
                    lease_until = excluded.lease_until
                """,
                (claimed_job_id, worker_id, lease_until),
            )

        assert claimed_job_id is not None
        return self.jobs.get(claimed_job_id)

    def renew(
        self,
        job_id: str,
        worker_id: str,
        *,
        now: float,
        lease_seconds: float,
    ) -> None:
        if lease_seconds <= 0:
            raise WorkerError("lease_seconds must be positive")
        with self.store.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE worker_leases
                SET lease_until = ?
                WHERE job_id = ? AND worker_id = ? AND lease_until > ?
                """,
                (float(now) + float(lease_seconds), job_id, worker_id, float(now)),
            )
            if cursor.rowcount != 1:
                raise WorkerError(f"lease is not owned or has expired: {job_id}")

    def release(self, job_id: str, worker_id: str) -> None:
        with self.store.connection() as connection:
            connection.execute(
                "DELETE FROM worker_leases WHERE job_id = ? AND worker_id = ?",
                (job_id, worker_id),
            )


class JobWorker:
    def __init__(
        self,
        worker_id: str,
        jobs: JobRepository,
        leases: WorkerLeaseRepository,
        workspaces: WorkspaceRegistry,
        executor,
        *,
        lease_seconds: float = 60.0,
        router: WorkflowRouter | None = None,
        closure_policy: ClosurePolicy | None = None,
    ):
        if not worker_id.strip():
            raise WorkerError("worker_id is required")
        self.worker_id = worker_id
        self.jobs = jobs
        self.leases = leases
        self.workspaces = workspaces
        self.executor = executor
        self.lease_seconds = lease_seconds
        self.router = router
        self.closure_policy = closure_policy

    def _block(self, job: JobRecord, reason: str) -> JobRecord:
        return self.jobs.transition(
            job.job_id,
            JobStatus.BLOCKED,
            details={"reason": reason},
        )

    def _preflight(self, job: JobRecord) -> WorkspaceRecord:
        preflight = self.workspaces.preflight(job.workspace_id)
        if job.expected_head and preflight.head != job.expected_head:
            raise WorkspaceError(
                "HEAD mismatch: "
                f"expected {job.expected_head}, got {preflight.head or 'none'}"
            )
        return preflight.workspace

    def run_once(self, *, now: float) -> JobRecord | None:
        job = self.leases.claim_next(
            self.worker_id,
            now=now,
            lease_seconds=self.lease_seconds,
        )
        if job is None:
            return None

        try:
            try:
                workspace = self._preflight(job)
            except WorkspaceError as exc:
                current = self.jobs.get(job.job_id)
                return self._block(current, str(exc))

            current = self.jobs.get(job.job_id)
            if current.status == JobStatus.CLAIMED:
                current = self.jobs.transition(current.job_id, JobStatus.PREFLIGHT)
            if current.status == JobStatus.PREFLIGHT:
                current = self.jobs.transition(current.job_id, JobStatus.RUNNING)

            if current.status == JobStatus.RUNNING:
                try:
                    result = self.executor.execute(current, workspace)
                except Exception as exc:
                    return self.jobs.transition(
                        current.job_id,
                        JobStatus.FAILED,
                        details={
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                        },
                    )
                if not result.success:
                    return self.jobs.transition(
                        current.job_id,
                        JobStatus.FAILED,
                        details={"summary": result.summary},
                    )
                current = self.jobs.transition(
                    current.job_id,
                    JobStatus.VERIFYING,
                    details={"summary": result.summary},
                )

            if current.status == JobStatus.VERIFYING:
                if self.router is None or self.closure_policy is None:
                    return current
                workflow = self.router.resolve(current.workflow_type)
                decision = self.closure_policy.evaluate(
                    current.job_id,
                    workflow.required_evidence,
                    human_gate=workflow.human_gate,
                )
                return self.jobs.transition(
                    current.job_id,
                    decision.status,
                    details={
                        "missing": list(decision.missing),
                        "failed": list(decision.failed),
                        "human_gate": decision.human_gate,
                    },
                )

            return current
        finally:
            self.leases.release(job.job_id, self.worker_id)
