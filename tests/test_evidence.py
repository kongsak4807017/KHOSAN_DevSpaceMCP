import tempfile
import unittest
from pathlib import Path

from ops.evidence import ClosurePolicy, EvidenceRepository
from ops.jobs import JobRepository, JobStatus
from ops.state import StateStore


class EvidenceClosureTests(unittest.TestCase):
    def _repos(self, root: Path):
        store = StateStore(root / "state" / "khosan.db")
        store.initialize()
        jobs = JobRepository(store)
        evidence = EvidenceRepository(store)
        return jobs, evidence

    def _verifying_job(self, jobs: JobRepository):
        job = jobs.create("project", "Fix behavior", "bugfix")
        jobs.enqueue(job.job_id)
        jobs.transition(job.job_id, JobStatus.CLAIMED)
        jobs.transition(job.job_id, JobStatus.PREFLIGHT)
        jobs.transition(job.job_id, JobStatus.RUNNING)
        return jobs.transition(job.job_id, JobStatus.VERIFYING)

    def test_executor_self_report_without_required_evidence_cannot_succeed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            jobs, evidence = self._repos(Path(temp_dir))
            job = self._verifying_job(jobs)
            policy = ClosurePolicy(evidence)

            decision = policy.evaluate(job.job_id, ("targeted-tests", "regression"))

            self.assertEqual(decision.status, JobStatus.NEEDS_HUMAN)
            self.assertEqual(decision.missing, ("targeted-tests", "regression"))

    def test_failed_required_evidence_forces_failed_decision(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            jobs, evidence = self._repos(Path(temp_dir))
            job = self._verifying_job(jobs)
            evidence.add(job.job_id, "targeted-tests", passed=True, verifier="pytest")
            evidence.add(job.job_id, "regression", passed=False, verifier="full-suite")
            policy = ClosurePolicy(evidence)

            decision = policy.evaluate(job.job_id, ("targeted-tests", "regression"))

            self.assertEqual(decision.status, JobStatus.FAILED)
            self.assertEqual(decision.failed, ("regression",))

    def test_all_required_green_evidence_permits_success(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            jobs, evidence = self._repos(Path(temp_dir))
            job = self._verifying_job(jobs)
            evidence.add(job.job_id, "targeted-tests", passed=True, verifier="pytest")
            evidence.add(job.job_id, "regression", passed=True, verifier="full-suite")
            policy = ClosurePolicy(evidence)

            decision = policy.evaluate(job.job_id, ("targeted-tests", "regression"))

            self.assertEqual(decision.status, JobStatus.SUCCEEDED)
            self.assertEqual(decision.missing, ())
            self.assertEqual(decision.failed, ())

    def test_human_gate_prevents_automatic_success(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            jobs, evidence = self._repos(Path(temp_dir))
            job = self._verifying_job(jobs)
            evidence.add(job.job_id, "tests", passed=True, verifier="suite")
            evidence.add(job.job_id, "deployment", passed=True, verifier="post-deploy")
            policy = ClosurePolicy(evidence)

            decision = policy.evaluate(
                job.job_id,
                ("tests", "deployment"),
                human_gate=True,
            )

            self.assertEqual(decision.status, JobStatus.NEEDS_HUMAN)
            self.assertTrue(decision.human_gate)


if __name__ == "__main__":
    unittest.main()
