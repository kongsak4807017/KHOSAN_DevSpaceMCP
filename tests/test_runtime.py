import logging
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ops.runtime import (
    build_child_environment,
    endpoint_for_config,
    make_rotating_logger,
    mcp_is_ready,
    resolve_devspace_command,
)


class CommandResolutionTests(unittest.TestCase):
    def test_windows_uses_repo_local_devspace_command(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            command = root / "node_modules" / ".bin" / "devspace.cmd"
            command.parent.mkdir(parents=True)
            command.write_text("@echo off\n", encoding="utf-8")

            self.assertEqual(resolve_devspace_command(root, os_name="nt"), command)

    def test_missing_local_dependency_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(FileNotFoundError, "npm ci"):
                resolve_devspace_command(Path(temp_dir), os_name="nt")


class EndpointTests(unittest.TestCase):
    def test_local_profile_uses_loopback_endpoint(self):
        self.assertEqual(
            endpoint_for_config({"host": "127.0.0.1", "port": 7678}),
            "http://127.0.0.1:7678/mcp",
        )

    def test_web_profile_uses_public_base_url(self):
        self.assertEqual(
            endpoint_for_config(
                {
                    "host": "127.0.0.1",
                    "port": 7677,
                    "publicBaseUrl": "https://canary.example.test/",
                }
            ),
            "https://canary.example.test/mcp",
        )

    def test_child_environment_preserves_path_and_applies_profile_values(self):
        result = build_child_environment(
            {"PATH": "existing", "KEEP": "yes"},
            {"PORT": "7678", "DEVSPACE_CONFIG_DIR": "runtime/config"},
        )
        self.assertEqual(result.get("PATH"), "existing")
        self.assertEqual(result.get("KEEP"), "yes")
        self.assertEqual(result.get("PORT"), "7678")
        self.assertNotIn("ownerToken", result)


class _McpHandler(BaseHTTPRequestHandler):
    response_code = 401
    challenge = 'Bearer scope="devspace"'

    def do_GET(self):
        self.send_response(self.response_code)
        if self.challenge:
            self.send_header("WWW-Authenticate", self.challenge)
        self.end_headers()

    def log_message(self, _format, *_args):
        return


class McpReadinessTests(unittest.TestCase):
    def _serve(self, status: int, challenge: str | None):
        handler = type(
            "ConfiguredMcpHandler",
            (_McpHandler,),
            {"response_code": status, "challenge": challenge},
        )
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_port}/mcp"

    def test_bearer_challenge_is_ready(self):
        self.assertTrue(mcp_is_ready(self._serve(401, 'Bearer scope="devspace"')))

    def test_unrelated_gateway_error_is_not_ready(self):
        self.assertFalse(mcp_is_ready(self._serve(502, None)))


class RotatingLoggerTests(unittest.TestCase):
    def test_log_rotates_instead_of_growing_without_bound(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "service.log"
            logger = make_rotating_logger(path, max_bytes=80, backup_count=2)
            self.addCleanup(logging.Logger.manager.loggerDict.pop, logger.name, None)
            for index in range(20):
                logger.info("line-%02d-abcdefghijkl", index)
            for handler in logger.handlers:
                handler.flush()
                handler.close()

            self.assertTrue(path.exists())
            self.assertTrue(path.with_name("service.log.1").exists())
            self.assertLessEqual(path.stat().st_size, 80)


if __name__ == "__main__":
    unittest.main()
