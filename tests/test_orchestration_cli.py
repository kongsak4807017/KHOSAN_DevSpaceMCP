import io
import json
import tempfile
import unittest
from pathlib import Path

from ops.cli import run_cli


class OrchestrationCliTests(unittest.TestCase):
    def _repo(self, root: Path) -> Path:
        base = root / "base"
        base.mkdir()
        profile_dir = root / "profiles" / "local"
        profile_dir.mkdir(parents=True)
        (profile_dir / "profile.json").write_text(
            json.dumps(
                {
                    "name": "local",
                    "port": 7678,
                    "allowedRoots": [str(base)],
                    "toolMode": "minimal",
                    "widgets": "changes",
                    "skillsEnabled": True,
                    "subagentsEnabled": False,
                }
            ),
            encoding="utf-8",
        )
        return base

    def _run(self, root: Path, *args: str):
        output = io.StringIO()
        code = run_cli(args, repo_root=root, stdout=output)
        return code, json.loads(output.getvalue())

    def test_workspace_add_and_disable_rematerialize_allowed_roots(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            base = self._repo(root)
            project = root / "other" / "project-x"
            project.mkdir(parents=True)

            code, added = self._run(
                root,
                "workspace",
                "add",
                "local",
                "project-x",
                str(project),
                "--display-name",
                "Project X",
            )

            self.assertEqual(code, 0)
            self.assertEqual(added["workspace_id"], "project-x")
            config = json.loads(
                (root / "runtime" / "local" / "config" / "config.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                {str(Path(item).resolve()) for item in config["allowedRoots"]},
                {str(base.resolve()), str(project.resolve())},
            )

            code, disabled = self._run(
                root, "workspace", "disable", "local", "project-x"
            )
            self.assertEqual(code, 0)
            self.assertFalse(disabled["enabled"])
            config = json.loads(
                (root / "runtime" / "local" / "config" / "config.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                {str(Path(item).resolve()) for item in config["allowedRoots"]},
                {str(base.resolve())},
            )

    def test_job_create_enqueues_and_events_are_queryable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._repo(root)
            project = root / "project"
            project.mkdir()
            self._run(root, "workspace", "add", "local", "project", str(project))

            code, created = self._run(
                root,
                "job",
                "create",
                "local",
                "project",
                "bugfix",
                "Fix behavior",
            )

            self.assertEqual(code, 0)
            self.assertEqual(created["workspace_id"], "project")
            self.assertEqual(created["status"], "QUEUED")
            job_id = created["job_id"]

            code, events = self._run(root, "job", "events", "local", job_id)
            self.assertEqual(code, 0)
            self.assertEqual(
                [event["status"] for event in events],
                ["CREATED", "QUEUED"],
            )

            code, jobs = self._run(root, "job", "list", "local")
            self.assertEqual(code, 0)
            self.assertEqual([job["job_id"] for job in jobs], [job_id])


if __name__ == "__main__":
    unittest.main()
