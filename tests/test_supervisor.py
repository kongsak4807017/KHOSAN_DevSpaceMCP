import tempfile
import unittest
from pathlib import Path

from ops.supervisor import CircuitBreaker, InstanceLock, RestartPolicy


class RestartPolicyTests(unittest.TestCase):
    def test_backoff_caps_at_sixty_seconds(self):
        policy = RestartPolicy()
        self.assertEqual(
            [policy.delay_for(attempt) for attempt in range(8)],
            [5, 10, 20, 40, 60, 60, 60, 60],
        )


class CircuitBreakerTests(unittest.TestCase):
    def test_opens_after_ten_failures_within_ten_minutes(self):
        breaker = CircuitBreaker(max_failures=10, window_seconds=600)
        for second in range(9):
            self.assertFalse(breaker.record_failure(second))
        self.assertTrue(breaker.record_failure(9))

    def test_old_failures_fall_out_of_window(self):
        breaker = CircuitBreaker(max_failures=3, window_seconds=10)
        self.assertFalse(breaker.record_failure(0))
        self.assertFalse(breaker.record_failure(1))
        self.assertFalse(breaker.record_failure(20))


class InstanceLockTests(unittest.TestCase):
    def test_second_owner_cannot_acquire_same_lock(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "local.lock"
            first = InstanceLock(path)
            second = InstanceLock(path)
            try:
                self.assertTrue(first.acquire())
                self.assertFalse(second.acquire())
            finally:
                first.release()


if __name__ == "__main__":
    unittest.main()
