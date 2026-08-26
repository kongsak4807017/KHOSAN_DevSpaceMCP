import json
import tempfile
import unittest
from pathlib import Path

from ops.profiles import materialize_profile
from ops.state import StateStore
from ops.workspaces import WorkspaceRegistry


class ProfileWorkspaceRegistryTests(unittest.TestCase):
    def _write_profile(self, root: Path, base_root: Path) -> None:
        profile_dir = root / "profiles" / "local"
        profile_dir.mkdir(parents=True)
        (profile_dir / "profile.json").write_text(
            json.dumps(
                {
                    "name": "local",
                    "port": 7678,
                    "allowedRoots": [str(base_root)],
                    "toolMode": "minimal",
                    "widgets": "changes",
                    "skillsEnabled": True,
                    "subagentsEnabled": False,
                }
            ),
            encoding="utf-8",
        )

    def test_materialize_merges_enabled_registered_workspace_roots(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            base = root / "base"
            extra = root / "unrelated" / "project-x"
            base.mkdir()
            extra.mkdir(parents=True)
            self._write_profile(root, base)

            store = StateStore(root / "runtime" / "local" / "state" / "khosan.db")
            store.initialize()
            WorkspaceRegistry(store).add("project-x", extra)

            materialized = materialize_profile(root, "local", token_factory=lambda: "x" * 32)
            config = json.loads(materialized.config_path.read_text(encoding="utf-8"))

            self.assertEqual(
                {str(Path(item).resolve()) for item in config["allowedRoots"]},
                {str(base.resolve()), str(extra.resolve())},
            )

    def test_materialize_excludes_disabled_registered_workspace_roots(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            base = root / "base"
            extra = root / "disabled" / "project-y"
            base.mkdir()
            extra.mkdir(parents=True)
            self._write_profile(root, base)

            store = StateStore(root / "runtime" / "local" / "state" / "khosan.db")
            store.initialize()
            registry = WorkspaceRegistry(store)
            registry.add("project-y", extra)
            registry.disable("project-y")

            materialized = materialize_profile(root, "local", token_factory=lambda: "x" * 32)
            config = json.loads(materialized.config_path.read_text(encoding="utf-8"))

            self.assertEqual(
                {str(Path(item).resolve()) for item in config["allowedRoots"]},
                {str(base.resolve())},
            )


if __name__ == "__main__":
    unittest.main()
