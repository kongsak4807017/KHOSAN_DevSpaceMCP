import sys
import tempfile
import unittest
from pathlib import Path

from ops.service import CIRCUIT_OPEN, LOCKED, supervise_command
from ops.supervisor import InstanceLock


class SuperviseCommandTests(unittest.TestCase):
    def test_successful_process_returns_zero_without_restart(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            result = supervise_command(
                [sys.executable, "-c", "print('ready')"],
                environment={},
                log_path=root / "service.log",
                lock_path=root / "service.lock",
                sleep_fn=lambda _delay: None,
            )
            self.assertEqual(result, 0)
            self.assertIn("ready", (root / "service.log").read_text(encoding="utf-8"))

    def test_repeated_failures_open_circuit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            moments = iter([0.0, 1.0])
            result = supervise_command(
                [sys.executable, "-c", "import sys; sys.exit(7)"],
                environment={},
                log_path=root / "service.log",
                lock_path=root / "service.lock",
                max_failures=2,
                window_seconds=600,
                sleep_fn=lambda _delay: None,
                now_fn=lambda: next(moments),
            )
            self.assertEqual(result, CIRCUIT_OPEN)
            log = (root / "service.log").read_text(encoding="utf-8")
            self.assertEqual(log.count('"event": "process_exit"'), 2)
            self.assertIn('"event": "circuit_open"', log)

    def test_second_supervisor_refuses_owned_lock(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lock_path = root / "service.lock"
            owner = InstanceLock(lock_path)
            try:
                self.assertTrue(owner.acquire())
                result = supervise_command(
                    [sys.executable, "-c", "print('must not run')"],
                    environment={},
                    log_path=root / "service.log",
                    lock_path=lock_path,
                )
            finally:
                owner.release()
            self.assertEqual(result, LOCKED)


if __name__ == "__main__":
    unittest.main()
