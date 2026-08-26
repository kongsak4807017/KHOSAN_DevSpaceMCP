import argparse
import json
import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import asdict
from enum import Enum
from pathlib import Path

from .health import classify_failure, fresh_openai_request
from .jobs import JobRepository, JobStatus
from .profiles import materialize_profile
from .runtime import (
    build_child_environment,
    endpoint_for_config,
    mcp_is_ready,
    resolve_devspace_command,
)
from .service import supervise_command
from .state import StateStore
from .workflows import WorkflowRouter
from .workspaces import WorkspaceRegistry


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="KHOSAN_DevSpace")
    subcommands = parser.add_subparsers(dest="command", required=True)
    for command in ("materialize", "status", "doctor", "start"):
        child = subcommands.add_parser(command)
        child.add_argument("profile")

    classify = subcommands.add_parser("classify")
    classify.add_argument("profile")
    classify.add_argument("--forbidden", action="store_true")
    classify.add_argument("--auth-error", action="store_true")
    classify.add_argument("--tool-call-started", action="store_true")
    classify.add_argument("--window-seconds", type=int, default=120)

    workspace = subcommands.add_parser("workspace")
    workspace_commands = workspace.add_subparsers(dest="workspace_command", required=True)
    workspace_add = workspace_commands.add_parser("add")
    workspace_add.add_argument("profile")
    workspace_add.add_argument("workspace_id")
    workspace_add.add_argument("root_path")
    workspace_add.add_argument("--display-name")
    workspace_add.add_argument("--repository")
    workspace_add.add_argument("--remote")
    workspace_add.add_argument("--runtime-profile")
    for name in ("show", "disable"):
        child = workspace_commands.add_parser(name)
        child.add_argument("profile")
        child.add_argument("workspace_id")
    workspace_list = workspace_commands.add_parser("list")
    workspace_list.add_argument("profile")
    workspace_list.add_argument("--enabled-only", action="store_true")

    job = subcommands.add_parser("job")
    job_commands = job.add_subparsers(dest="job_command", required=True)
    job_create = job_commands.add_parser("create")
    job_create.add_argument("profile")
    job_create.add_argument("workspace_id")
    job_create.add_argument("workflow_type")
    job_create.add_argument("intent")
    job_create.add_argument("--expected-head")
    for name in ("show", "events"):
        child = job_commands.add_parser(name)
        child.add_argument("profile")
        child.add_argument("job_id")
    job_list = job_commands.add_parser("list")
    job_list.add_argument("profile")
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


def _jsonable(value):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return list(value)
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


def _write_json(stdout, value) -> None:
    if hasattr(value, "__dataclass_fields__"):
        value = asdict(value)
    elif isinstance(value, list):
        value = [asdict(item) if hasattr(item, "__dataclass_fields__") else item for item in value]
    stdout.write(json.dumps(value, indent=2, ensure_ascii=False, default=_jsonable) + "\n")


def _orchestration(materialized):
    store = StateStore(materialized.state_dir / "khosan.db")
    store.initialize()
    return store, WorkspaceRegistry(store), JobRepository(store)


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

    if args.command == "workspace":
        _store, workspaces, _jobs = _orchestration(materialized)
        if args.workspace_command == "add":
            record = workspaces.add(
                args.workspace_id,
                Path(args.root_path),
                display_name=args.display_name,
                repository=args.repository,
                expected_remote=args.remote,
                runtime_profile=args.runtime_profile,
            )
            materialize_profile(root, args.profile)
            _write_json(stdout, record)
            return 0
        if args.workspace_command == "disable":
            record = workspaces.disable(args.workspace_id)
            materialize_profile(root, args.profile)
            _write_json(stdout, record)
            return 0
        if args.workspace_command == "show":
            _write_json(stdout, workspaces.get(args.workspace_id))
            return 0
        _write_json(
            stdout,
            workspaces.list(include_disabled=not args.enabled_only),
        )
        return 0

    if args.command == "job":
        _store, workspaces, jobs = _orchestration(materialized)
        if args.job_command == "create":
            workspace = workspaces.get(args.workspace_id)
            if not workspace.enabled:
                raise ValueError(f"workspace is disabled: {args.workspace_id}")
            WorkflowRouter().resolve(args.workflow_type)
            record = jobs.create(
                args.workspace_id,
                args.intent,
                args.workflow_type,
                expected_head=args.expected_head,
            )
            if record.status == JobStatus.CREATED:
                record = jobs.enqueue(record.job_id)
            _write_json(stdout, record)
            return 0
        if args.job_command == "show":
            _write_json(stdout, jobs.get(args.job_id))
            return 0
        if args.job_command == "events":
            _write_json(stdout, jobs.events(args.job_id))
            return 0
        _write_json(stdout, jobs.list())
        return 0

    if args.command == "materialize":
        _write_json(stdout, payload)
        return 0

    if args.command == "status":
        payload["ready"] = bool(check(payload["endpoint"]))
        _write_json(stdout, payload)
        return 0 if payload["ready"] else 1

    if args.command == "classify":
        local_endpoint = endpoint_for_config(
            {"host": _config["host"], "port": _config["port"]}
        )
        inbound_seen, last_request = fresh_openai_request(
            root / "runtime" / args.profile / "logs" / "devspace.log",
            window_seconds=args.window_seconds,
        )
        local_ready = bool(check(local_endpoint))
        public_ready = bool(check(payload["endpoint"]))
        failure_class = classify_failure(
            forbidden=args.forbidden,
            inbound_request_seen=inbound_seen,
            local_ready=local_ready,
            public_ready=public_ready,
            auth_error=args.auth_error,
            tool_call_started=args.tool_call_started,
        )
        payload.update(
            {
                "failureClass": failure_class.value,
                "inboundRequestSeen": inbound_seen,
                "lastOpenaiRequest": last_request,
                "localReady": local_ready,
                "publicReady": public_ready,
            }
        )
        _write_json(stdout, payload)
        return 0

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
