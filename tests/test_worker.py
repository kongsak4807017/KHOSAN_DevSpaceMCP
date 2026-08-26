import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from ops.jobs import JobRepository, JobStatus
from ops.state import StateStore
from ops.worker import ExecutionResult, JobWorker, WorkerLeaseRepository
from ops.workspaces import WorkspaceRegistry


@dataclass
class FakeExecutor:
    success: bool = True

    def __post_init__(self):
        self.calls = []

    def execute(self, job, workspace):
        self.calls.append((job.job_id, workspace.workspace_id))
        return ExecutionResult(success=self.success, summary="done" if self.success else "failed")


class WorkerTests(unittest.TestCase):
    def _environment(self, root: Path):
        store = StateStore(root / "state" / "khosan.db")
        store.initialize()
        workspaces = WorkspaceRegistry(store)
        jobs = JobRepository(store)
        leases = WorkerLeaseRepository(store, jobs)
        return store, workspaces, jobs, leases

    def test_lease_prevents_double_claim_and_expires_for_recovery(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _store, _workspaces, jobs, leases = self._environment(root)
            job = jobs.create("project", "Run tests", "test-only")
            jobs.enqueue(job.job_id)

            first = leases.claim_next("worker-a", now=100.0, lease_seconds=10)
            blocked = leases.claim_next("worker-b", now=105.0, lease_seconds=10)
            recovered = leases.claim_next("worker-b", now=111.0, lease_seconds=10)

            self.assertEqual(first.job_id, job.job_id)
            self.assertEqual(first.status, JobStatus.CLAIMED)
            self.assertIsNone(blocked)
            self.assertEqual(recovered.job_id, job.job_id)
            self.assertEqual(recovered.status, JobStatus.CLAIMED)

    def test_worker_blocks_disabled_workspace_before_executor(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "project"
            project.mkdir()
            _store, workspaces, jobs, leases = self._environment(root)
            workspaces.add("project", project)
            workspaces.disable("project")
            job = jobs.create("project", "Change code", "bugfix")
            jobs.enqueue(job.job_id)
            executor = FakeExecutor()
            worker = JobWorker("worker-a", jobs, leases, workspaces, executor)

            result = worker.run_once(now=100.0)

            self.assertEqual(result.status, JobStatus.BLOCKED)
            self.assertEqual(executor.calls, [])

    def test_executor_failure_transitions_job_to_failed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "project"
            project.mkdir()
            _store, workspaces, jobs, leases = self._environment(root)
            workspaces.add("project", project)
            job = jobs.create("project", "Change code", "bugfix")
            jobs.enqueue(job.job_id)
            executor = FakeExecutor(success=False)
            worker = JobWorker("worker-a", jobs, leases, workspaces, executor)

            result = worker.run_once(now=100.0)

            self.assertEqual(result.status, JobStatus.FAILED)
            self.assertEqual(executor.calls, [(job.job_id, "project")])

    def test_successful_executor_stops_at_verifying_without_evidence_policy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "project"
            project.mkdir()
            _store, workspaces, jobs, leases = self._environment(root)
            workspaces.add("project", project)
            job = jobs.create("project", "Change code", "bugfix")
            jobs.enqueue(job.job_id)
            executor = FakeExecutor(success=True)
            worker = JobWorker("worker-a", jobs, leases, workspaces, executor)

            result = worker.run_once(now=100.0)

            self.assertEqual(result.status, JobStatus.VERIFYING)
            self.assertEqual(executor.calls, [(job.job_id, "project")])


if __name__ == "__main__":
    unittest.main()
