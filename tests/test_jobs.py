import tempfile
import unittest
from pathlib import Path

from ops.jobs import JobError, JobRepository, JobStatus
from ops.state import StateStore


class JobRepositoryTests(unittest.TestCase):
    def _repository(self, root: Path) -> JobRepository:
        store = StateStore(root / "state" / "khosan.db")
        store.initialize()
        return JobRepository(store)

    def test_create_is_idempotent_for_same_logical_request(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = self._repository(Path(temp_dir))

            first = repo.create("rorebuild", "Fix Solar Sword", "bugfix", expected_head="abc123")
            second = repo.create("rorebuild", "Fix Solar Sword", "bugfix", expected_head="abc123")

            self.assertEqual(first.job_id, second.job_id)
            self.assertEqual(first.request_hash, second.request_hash)
            self.assertEqual(first.status, JobStatus.CREATED)

    def test_different_request_creates_different_job(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = self._repository(Path(temp_dir))

            first = repo.create("a", "one", "bugfix")
            second = repo.create("a", "two", "bugfix")

            self.assertNotEqual(first.job_id, second.job_id)

    def test_legal_transitions_are_persisted_as_append_only_events(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo = self._repository(root)
            job = repo.create("project", "Run tests", "test-only")

            repo.enqueue(job.job_id)
            repo.transition(job.job_id, JobStatus.CLAIMED)
            repo.transition(job.job_id, JobStatus.PREFLIGHT)

            reopened = self._repository(root)
            self.assertEqual(reopened.get(job.job_id).status, JobStatus.PREFLIGHT)
            self.assertEqual(
                [event.status for event in reopened.events(job.job_id)],
                [JobStatus.CREATED, JobStatus.QUEUED, JobStatus.CLAIMED, JobStatus.PREFLIGHT],
            )

    def test_illegal_transition_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = self._repository(Path(temp_dir))
            job = repo.create("project", "Build", "build-release")

            with self.assertRaisesRegex(JobError, "illegal transition"):
                repo.transition(job.job_id, JobStatus.SUCCEEDED)

            self.assertEqual(repo.get(job.job_id).status, JobStatus.CREATED)

    def test_terminal_state_is_immutable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = self._repository(Path(temp_dir))
            job = repo.create("project", "Inspect", "inspect-only")
            repo.enqueue(job.job_id)
            repo.transition(job.job_id, JobStatus.CLAIMED)
            repo.transition(job.job_id, JobStatus.PREFLIGHT)
            repo.transition(job.job_id, JobStatus.RUNNING)
            repo.transition(job.job_id, JobStatus.FAILED)

            with self.assertRaisesRegex(JobError, "terminal"):
                repo.transition(job.job_id, JobStatus.QUEUED)


if __name__ == "__main__":
    unittest.main()
