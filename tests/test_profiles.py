import json
import tempfile
import unittest
from pathlib import Path

from ops.profiles import ProfileError, materialize_profile


class MaterializeProfileTests(unittest.TestCase):
    def _write_profile(self, root: Path, name: str, **overrides) -> None:
        profile_dir = root / "profiles" / name
        profile_dir.mkdir(parents=True)
        payload = {
            "name": name,
            "port": 7678,
            "allowedRoots": [str(root / "workspace")],
            "toolMode": "minimal",
            "widgets": "changes",
            "skillsEnabled": True,
            "subagentsEnabled": False,
        }
        payload.update(overrides)
        (profile_dir / "profile.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )

    def test_materialize_writes_isolated_config_and_secret(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "workspace").mkdir()
            self._write_profile(root, "local")

            result = materialize_profile(root, "local", token_factory=lambda: "x" * 32)

            config = json.loads(result.config_path.read_text(encoding="utf-8"))
            auth = json.loads(result.auth_path.read_text(encoding="utf-8"))
            self.assertEqual(config.get("host"), "127.0.0.1")
            self.assertEqual(config.get("port"), 7678)
            self.assertEqual(config.get("allowedRoots"), [str(root / "workspace")])
            self.assertNotIn("publicBaseUrl", config)
            self.assertEqual(auth, {"ownerToken": "x" * 32})
            self.assertEqual(result.environment["DEVSPACE_CONFIG_DIR"], str(result.config_dir))
            self.assertEqual(result.environment["DEVSPACE_STATE_DIR"], str(result.state_dir))
            self.assertEqual(result.environment["DEVSPACE_WORKTREE_ROOT"], str(result.worktree_dir))

    def test_materialize_reuses_existing_owner_token(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "workspace").mkdir()
            self._write_profile(root, "local")
            first = materialize_profile(root, "local", token_factory=lambda: "a" * 32)

            second = materialize_profile(root, "local", token_factory=lambda: "b" * 32)

            self.assertEqual(first.owner_token, "a" * 32)
            self.assertEqual(second.owner_token, "a" * 32)

    def test_rejects_broad_drive_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_profile(root, "local", allowedRoots=["C:\\"])

            with self.assertRaisesRegex(ProfileError, "broad root"):
                materialize_profile(root, "local", token_factory=lambda: "x" * 32)

    def test_rejects_user_home_as_allowed_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_profile(root, "local", allowedRoots=[str(Path.home())])

            with self.assertRaisesRegex(ProfileError, "broad root"):
                materialize_profile(root, "local", token_factory=lambda: "x" * 32)

    def test_rejects_downloads_as_allowed_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_profile(
                root, "local", allowedRoots=[str(Path.home() / "Downloads")]
            )

            with self.assertRaisesRegex(ProfileError, "broad root"):
                materialize_profile(root, "local", token_factory=lambda: "x" * 32)

    def test_web_profile_requires_real_https_origin(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "workspace").mkdir()
            self._write_profile(
                root,
                "web",
                port=7677,
                publicBaseUrl="https://replace-me.example",
            )

            with self.assertRaisesRegex(ProfileError, "stable HTTPS origin"):
                materialize_profile(root, "web", token_factory=lambda: "x" * 32)

    def test_active_profiles_cannot_share_port(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "workspace").mkdir()
            self._write_profile(root, "local", port=7678)
            self._write_profile(
                root,
                "web",
                port=7678,
                publicBaseUrl="https://canary.example.test",
            )

            with self.assertRaisesRegex(ProfileError, "already used"):
                materialize_profile(root, "web", token_factory=lambda: "x" * 32)

    def test_profiles_do_not_share_runtime_directories(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "workspace").mkdir()
            self._write_profile(root, "local", port=7678)
            self._write_profile(
                root,
                "web",
                port=7677,
                publicBaseUrl="https://canary.example.test",
            )

            local = materialize_profile(root, "local", token_factory=lambda: "a" * 32)
            web = materialize_profile(root, "web", token_factory=lambda: "b" * 32)

            self.assertNotEqual(local.config_dir, web.config_dir)
            self.assertNotEqual(local.state_dir, web.state_dir)
            self.assertNotEqual(local.worktree_dir, web.worktree_dir)
            self.assertNotEqual(local.owner_token, web.owner_token)


if __name__ == "__main__":
    unittest.main()
