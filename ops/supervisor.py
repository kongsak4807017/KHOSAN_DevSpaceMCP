from collections import deque
from pathlib import Path
from typing import BinaryIO


class RestartPolicy:
    def delay_for(self, attempt: int) -> int:
        if attempt < 0:
            raise ValueError("attempt cannot be negative")
        return min(5 * (2**attempt), 60)


class CircuitBreaker:
    def __init__(self, max_failures: int, window_seconds: int):
        if max_failures < 1 or window_seconds < 1:
            raise ValueError("circuit breaker limits must be positive")
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self._failures: deque[float] = deque()

    def record_failure(self, timestamp: float) -> bool:
        cutoff = timestamp - self.window_seconds
        while self._failures and self._failures[0] < cutoff:
            self._failures.popleft()
        self._failures.append(timestamp)
        return len(self._failures) >= self.max_failures


class InstanceLock:
    def __init__(self, path):
        self.path = Path(path)
        self._handle: BinaryIO | None = None

    def acquire(self) -> bool:
        if self._handle is not None:
            return True
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+b")
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        try:
            if __import__("os").name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            return False
        self._handle = handle
        return True

    def release(self) -> None:
        if self._handle is None:
            return
        handle, self._handle = self._handle, None
        handle.seek(0)
        try:
            if __import__("os").name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()
