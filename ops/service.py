import json
import os
import subprocess
import time
from collections.abc import Callable, Sequence
from pathlib import Path

from .runtime import build_child_environment, make_rotating_logger
from .supervisor import CircuitBreaker, InstanceLock, RestartPolicy


LOCKED = 73
CIRCUIT_OPEN = 75


def supervise_command(
    command: Sequence[str | Path],
    *,
    environment: dict[str, str],
    log_path: Path,
    lock_path: Path,
    max_failures: int = 10,
    window_seconds: int = 600,
    sleep_fn: Callable[[float], None] = time.sleep,
    now_fn: Callable[[], float] = time.monotonic,
) -> int:
    instance_lock = InstanceLock(lock_path)
    if not instance_lock.acquire():
        return LOCKED

    logger = make_rotating_logger(log_path)
    breaker = CircuitBreaker(max_failures, window_seconds)
    policy = RestartPolicy()
    attempt = 0
    child_environment = build_child_environment(dict(os.environ), environment)
    creationflags = 0x08000000 if os.name == "nt" else 0

    try:
        while True:
            logger.info(
                json.dumps(
                    {"event": "process_start", "attempt": attempt}, ensure_ascii=False
                )
            )
            try:
                with subprocess.Popen(
                    [str(item) for item in command],
                    env=child_environment,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    creationflags=creationflags,
                ) as process:
                    assert process.stdout is not None
                    for line in process.stdout:
                        logger.info(line.rstrip("\r\n"))
                    return_code = process.wait()
            except KeyboardInterrupt:
                logger.info(json.dumps({"event": "operator_interrupt"}))
                return 130
            except OSError as exc:
                return_code = 127
                logger.info(
                    json.dumps(
                        {
                            "event": "process_start_error",
                            "errorType": type(exc).__name__,
                        }
                    )
                )

            logger.info(
                json.dumps(
                    {"event": "process_exit", "returnCode": return_code},
                    ensure_ascii=False,
                )
            )
            if return_code == 0:
                return 0
            if breaker.record_failure(now_fn()):
                logger.info(
                    json.dumps(
                        {
                            "event": "circuit_open",
                            "failures": max_failures,
                            "windowSeconds": window_seconds,
                        }
                    )
                )
                return CIRCUIT_OPEN
            sleep_fn(policy.delay_for(attempt))
            attempt += 1
    finally:
        instance_lock.release()
        for handler in list(logger.handlers):
            handler.flush()
            handler.close()
            logger.removeHandler(handler)
