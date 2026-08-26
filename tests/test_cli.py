import io
import json
import tempfile
import unittest
from pathlib import Path

from ops.cli import run_cli


class CliTests(unittest.TestCase):
    def _profile_root(self, temp_dir: str) -> Path:
        root = Path(temp_dir)
        workspace = root / "workspace"
        workspace.mkdir()
        profile_dir = root / "profiles" / "local"
        profile_dir.mkdir(parents=True)
        (profile_dir / "profile.json").write_text(
            json.dumps(
                {
                    "name": "local",
                    "port": 7678,
                    "allowedRoots": [str(workspace)],
                    "toolMode": "minimal",
                    "widgets": "changes",
                }
            ),
            encoding="utf-8",
        )
        return root

    def test_materialize_prints_secret_free_summary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._profile_root(temp_dir)
            output = io.StringIO()

            result = run_cli(["materialize", "local"], repo_root=root, stdout=output)

            payload = json.loads(output.getvalue())
            self.assertEqual(result, 0)
            self.assertEqual(payload["profile"], "local")
            self.assertEqual(payload["endpoint"], "http://127.0.0.1:7678/mcp")
            self.assertNotIn("ownerToken", payload)
            self.assertNotIn("secret", output.getvalue().lower())

    def test_status_returns_nonzero_when_endpoint_is_not_ready(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._profile_root(temp_dir)
            output = io.StringIO()

            result = run_cli(
                ["status", "local"],
                repo_root=root,
                stdout=output,
                ready_check=lambda _url: False,
            )

            payload = json.loads(output.getvalue())
            self.assertEqual(result, 1)
            self.assertFalse(payload["ready"])

    def test_status_returns_zero_when_endpoint_is_ready(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._profile_root(temp_dir)
            output = io.StringIO()

            result = run_cli(
                ["status", "local"],
                repo_root=root,
                stdout=output,
                ready_check=lambda _url: True,
            )

            payload = json.loads(output.getvalue())
            self.assertEqual(result, 0)
            self.assertTrue(payload["ready"])


if __name__ == "__main__":
    unittest.main()
