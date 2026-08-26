# KHOSAN_DevSpace

Private, tool-only MCP runtime profiles built around a pinned DevSpace core, with profile-local durable orchestration for multiple software projects.

Repository: [kongsak4807017/KHOSAN_DevSpaceMCP](https://github.com/kongsak4807017/KHOSAN_DevSpaceMCP)

This repository does not replace the live legacy instance yet. The legacy service remains on `127.0.0.1:7676`. The V2 local profile is loopback-only on `127.0.0.1:7678` for Codex desktop, CLI, and IDE clients.

## Why this exists

The previous wrapper mixed UI, tunnel control, process ownership, secrets, and health polling. It also probed the public MCP endpoint every three seconds, producing hundreds of thousands of log records. KHOSAN_DevSpace separates:

- reproducible DevSpace dependency and profiles;
- runtime secrets and SQLite state;
- explicit multi-project workspace registration;
- durable jobs and append-only job events;
- worker leases and restart recovery primitives;
- independent verification evidence and closure policy;
- failure classification;
- single-owner process supervision;
- bounded logs;
- ChatGPT web and local Codex access paths.

## Archetype

`tool-only / private internal`. DevSpace supplies the MCP execution tools. KHOSAN adds orchestration and governance around that execution plane rather than replacing it.

## Current status

- Pinned DevSpace: `1.0.8`
- Local profile: `127.0.0.1:7678`
- Web profile: template only; it needs a separate stable HTTPS canary origin before activation
- Legacy profile: unchanged at `127.0.0.1:7676`
- Subagents: disabled in both V2 profiles
- Orchestration database: ignored `runtime/<profile>/state/khosan.db`
- One MCP profile may serve many explicitly registered local workspaces

## Core commands

```powershell
npm ci
npm run test:strict
npm run compile
./scripts/ops.ps1 materialize local
./scripts/ops.ps1 doctor local
./scripts/ops.ps1 start local
./scripts/ops.ps1 status local
./scripts/ops.ps1 classify local --forbidden
```

`start` owns a profile lock, restarts failed child processes with capped exponential backoff, opens a circuit after repeated crashes, and writes rotating logs under the ignored `runtime/` directory.

## Multi-workspace registry

Register each project explicitly. Paths are stored only in the ignored profile-local SQLite database; they are not committed to the repository.

```powershell
./scripts/ops.ps1 workspace add local rorebuild C:\ROREBUILD --display-name ROREBUILD
./scripts/ops.ps1 workspace add local project-x D:\GitHub\project-x --repository owner/project-x
./scripts/ops.ps1 workspace list local
./scripts/ops.ps1 workspace show local project-x
./scripts/ops.ps1 workspace disable local project-x
```

Enabled registered roots are merged into the materialized DevSpace `allowedRoots`. Adding another project does **not** create another MCP endpoint or tunnel. Broad drive roots, the user home, and Downloads are rejected.

`workspace_id` is KHOSAN's durable project identifier. It is different from DevSpace's session-scoped `workspaceId` returned by `open_workspace`.

## Durable jobs

Create a job against exactly one registered workspace and an explicit rule-based workflow:

```powershell
./scripts/ops.ps1 job create local rorebuild bugfix "Fix Solar Sword runtime behavior"
./scripts/ops.ps1 job list local
./scripts/ops.ps1 job show local <job_id>
./scripts/ops.ps1 job events local <job_id>
```

`job create` is idempotent for the same logical request and enqueues a newly created job. The operational state machine is persisted in SQLite. Executor self-report is not sufficient for successful closure; required evidence must be present and green.

Initial workflow classes are `inspect-only`, `bugfix`, `feature`, `test-only`, `build-release`, and `production-change`. Unknown workflow names fail closed.

## Tunnel model

Local Codex/CLI/IDE clients use `http://127.0.0.1:7678/mcp` directly and need no tunnel.

ChatGPT Web still needs a remotely reachable MCP transport. The transport is independent of the number of registered workspaces: one web MCP ingress can serve all approved workspaces. Keep the existing stable HTTPS/ngrok-style canary approach until the documented DevSpace OAuth/resource compatibility issue is resolved or an explicitly reviewed compatibility path is proven. Changing transport later must not require changing the workspace/job architecture.

## Codex local registration

```powershell
codex mcp add KHOSAN_DevSpace --url http://127.0.0.1:7678/mcp
codex mcp login KHOSAN_DevSpace
```

OAuth requires the generated Owner password stored in the ignored local profile auth file. Enter it only in the loopback approval page; do not paste it into chat or logs. Restart the Codex client after authentication so its MCP inventory refreshes.

## Documentation

- [Runbook](docs/RUNBOOK.md)
- [Security boundary](docs/SECURITY_BOUNDARY.md)
- [ChatGPT web setup](docs/CHATGPT_SETUP.md)
- [Contract snapshot](docs/CONTRACT_SNAPSHOT.md)
- [Cross-client work-state protocol](docs/WORK_STATE_PROTOCOL.md)
- [Roadmap](docs/ROADMAP.md)
- [Multi-workspace orchestration design](docs/superpowers/specs/2026-08-27-multi-workspace-job-orchestration-design.md)
- [Implementation plan](docs/superpowers/plans/2026-08-27-multi-workspace-job-orchestration.md)

## Primary references

- [OpenAI: Build an MCP server](https://developers.openai.com/plugins/build/mcp-server)
- [OpenAI: ChatGPT Developer Mode](https://developers.openai.com/api/docs/guides/developer-mode)
- [OpenAI: Codex MCP configuration](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
- [OpenAI: Connect and test a plugin](https://developers.openai.com/plugins/deploy/connect-chatgpt)
- [DevSpace upstream](https://github.com/Waishnav/devspace)

## Production readiness

The local profile and orchestration core are developed independently from the web canary. The separate ChatGPT web profile remains intentionally inactive until it has its own stable HTTPS origin and the dependency/security exception in `docs/SECURITY_BOUNDARY.md` is resolved or explicitly accepted. Legacy `7676` remains untouched until a separate promotion decision.
