import argparse
import json
import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from .profiles import materialize_profile
from .runtime import (
    build_child_environment,
    endpoint_for_config,
    mcp_is_ready,
    resolve_devspace_command,
)
from .service import supervise_command


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="KHOSAN_DevSpace")
    subcommands = parser.add_subparsers(dest="command", required=True)
    for command in ("materialize", "status", "doctor", "start"):
        child = subcommands.add_parser(command)
        child.add_argument("profile")
    return parser


def _summary(repo_root: Path, name: str) -> tuple[object, dict, dict]:
    materialized = materialize_profile(repo_root, name)
    config = json.loads(materialized.config_path.read_text(encoding="utf-8"))
    payload = {
        "profile": name,
        "endpoint": endpoint_for_config(config),
        "configDir": str(materialized.config_dir),
        "stateDir": str(materialized.state_dir),
        "worktreeDir": str(materialized.worktree_dir),
    }
    return materialized, config, payload


def run_cli(
    argv: Sequence[str],
    *,
    repo_root: Path,
    stdout,
    ready_check: Callable[[str], bool] | None = None,
) -> int:
    args = _parser().parse_args(list(argv))
    root = Path(repo_root).resolve()
    materialized, _config, payload = _summary(root, args.profile)
    check = ready_check or mcp_is_ready

    if args.command == "materialize":
        stdout.write(json.dumps(payload, indent=2) + "\n")
        return 0

    if args.command == "status":
        payload["ready"] = bool(check(payload["endpoint"]))
        stdout.write(json.dumps(payload, indent=2) + "\n")
        return 0 if payload["ready"] else 1

    command = resolve_devspace_command(root)
    environment = build_child_environment(dict(os.environ), materialized.environment)
    if args.command == "doctor":
        return subprocess.run(
            [str(command), "doctor"], cwd=root, env=environment, check=False
        ).returncode

    runtime_dir = root / "runtime" / args.profile
    return supervise_command(
        [command, "serve"],
        environment=materialized.environment,
        log_path=runtime_dir / "logs" / "devspace.log",
        lock_path=runtime_dir / "supervisor.lock",
    )


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    return run_cli(sys.argv[1:], repo_root=repo_root, stdout=sys.stdout)


if __name__ == "__main__":
    raise SystemExit(main())
