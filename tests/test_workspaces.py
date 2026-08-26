import subprocess
import tempfile
import unittest
from pathlib import Path

from ops.state import StateStore
from ops.workspaces import WorkspaceError, WorkspaceRegistry


class WorkspaceRegistryTests(unittest.TestCase):
    def _registry(self, root: Path) -> WorkspaceRegistry:
        store = StateStore(root / "state" / "khosan.db")
        store.initialize()
        return WorkspaceRegistry(store)

    def test_registers_and_persists_multiple_unrelated_roots(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project_a = root / "alpha" / "project-a"
            project_b = root / "other" / "nested" / "project-b"
            project_a.mkdir(parents=True)
            project_b.mkdir(parents=True)
            registry = self._registry(root)

            registry.add("alpha", project_a, display_name="Alpha")
            registry.add("beta", project_b, display_name="Beta")

            reopened = self._registry(root)
            records = reopened.list()
            self.assertEqual([item.workspace_id for item in records], ["alpha", "beta"])
            self.assertEqual(reopened.get("alpha").root_path, str(project_a.resolve()))
            self.assertEqual(reopened.get("beta").root_path, str(project_b.resolve()))

    def test_rejects_filesystem_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            registry = self._registry(root)
            filesystem_root = Path(root.anchor)

            with self.assertRaisesRegex(WorkspaceError, "broad root"):
                registry.add("danger", filesystem_root)

    def test_rejects_duplicate_workspace_id(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "one"
            second = root / "two"
            first.mkdir()
            second.mkdir()
            registry = self._registry(root)
            registry.add("same", first)

            with self.assertRaisesRegex(WorkspaceError, "already exists"):
                registry.add("same", second)

    def test_disable_preserves_record_but_marks_it_unavailable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "project"
            project.mkdir()
            registry = self._registry(root)
            registry.add("project", project)

            disabled = registry.disable("project")

            self.assertFalse(disabled.enabled)
            self.assertFalse(registry.get("project").enabled)
            self.assertEqual(len(registry.list(include_disabled=False)), 0)
            self.assertEqual(len(registry.list(include_disabled=True)), 1)

    def test_preflight_blocks_disabled_workspace(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "project"
            project.mkdir()
            registry = self._registry(root)
            registry.add("project", project)
            registry.disable("project")

            with self.assertRaisesRegex(WorkspaceError, "disabled"):
                registry.preflight("project")

    def test_preflight_rejects_wrong_repository_identity(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "repo"
            project.mkdir()
            subprocess.run(["git", "init", str(project)], check=True, capture_output=True)
            subprocess.run(
                ["git", "-C", str(project), "remote", "add", "origin", "https://github.com/example/actual.git"],
                check=True,
                capture_output=True,
            )
            registry = self._registry(root)
            registry.add("repo", project, repository="example/expected")

            with self.assertRaisesRegex(WorkspaceError, "repository identity"):
                registry.preflight("repo")


if __name__ == "__main__":
    unittest.main()
