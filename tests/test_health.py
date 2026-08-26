import json
import tempfile
import unittest
from pathlib import Path

from ops.health import FailureClass, classify_failure, last_openai_request_timestamp


class FailureClassifierTests(unittest.TestCase):
    def test_forbidden_without_inbound_request_is_host_capability(self):
        result = classify_failure(
            forbidden=True,
            inbound_request_seen=False,
            local_ready=True,
            public_ready=True,
            auth_error=False,
            tool_call_started=False,
        )
        self.assertEqual(result, FailureClass.HOST_CAPABILITY)

    def test_public_failure_with_local_ready_is_transport(self):
        result = classify_failure(
            forbidden=False,
            inbound_request_seen=False,
            local_ready=True,
            public_ready=False,
            auth_error=False,
            tool_call_started=False,
        )
        self.assertEqual(result, FailureClass.TRANSPORT)

    def test_auth_error_after_inbound_request_is_auth_contract(self):
        result = classify_failure(
            forbidden=False,
            inbound_request_seen=True,
            local_ready=True,
            public_ready=True,
            auth_error=True,
            tool_call_started=False,
        )
        self.assertEqual(result, FailureClass.AUTH_CONTRACT)

    def test_tool_failure_after_start_is_tool_runtime(self):
        result = classify_failure(
            forbidden=False,
            inbound_request_seen=True,
            local_ready=True,
            public_ready=True,
            auth_error=False,
            tool_call_started=True,
        )
        self.assertEqual(result, FailureClass.TOOL_RUNTIME)


class LogBoundaryTests(unittest.TestCase):
    def test_returns_timestamp_of_latest_openai_request(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "devspace.log"
            lines = [
                {"ts": "2026-08-26T01:00:00Z", "userAgent": "Python-urllib/3.14"},
                {"ts": "2026-08-26T01:01:00Z", "userAgent": "openai-mcp/1.0.0"},
                {"ts": "2026-08-26T01:02:00Z", "userAgent": "openai-mcp/1.0.0"},
            ]
            log_path.write_text(
                "\n".join(json.dumps(line) for line in lines), encoding="utf-8"
            )

            self.assertEqual(
                last_openai_request_timestamp(log_path), "2026-08-26T01:02:00Z"
            )


if __name__ == "__main__":
    unittest.main()
