# Operations runbook

## Normal startup

1. Run `npm ci` after checkout or lockfile changes.
2. Run `npm run test:strict` and `npm run compile`.
3. Run `./scripts/ops.ps1 doctor local`.
4. Run `./scripts/ops.ps1 start local` in the service session.
5. Verify with `./scripts/ops.ps1 status local`.

The local endpoint is healthy when GET `/mcp` returns `401` with a Bearer challenge. Do not require an unauthenticated `200`.

## Registering another local project

Use one durable KHOSAN `workspace_id` per project checkout/root. The local path is stored in ignored profile-local SQLite state.

```powershell
./scripts/ops.ps1 workspace add local project-x D:\GitHub\project-x --repository owner/project-x
./scripts/ops.ps1 workspace list local
./scripts/ops.ps1 workspace show local project-x
```

Registration rejects broad filesystem roots. Enabled registered roots are merged into the materialized DevSpace `allowedRoots` automatically. If the DevSpace service is already running when the registry changes, restart that profile deliberately so the process reloads the materialized config; do not kill arbitrary port owners.

To remove a project from future execution without deleting its durable record:

```powershell
./scripts/ops.ps1 workspace disable local project-x
```

A disabled root is removed from the next materialized `allowedRoots`.

### Two workspace identifiers

- `workspace_id`: durable KHOSAN project identity stored in `khosan.db` and referenced by Jobs.
- `workspaceId`: DevSpace session/worktree handle returned by `open_workspace` for a particular client/profile session.

Never substitute one for the other.

## Durable jobs

Create a queued Job only against an enabled registered workspace:

```powershell
./scripts/ops.ps1 job create local project-x bugfix "Fix the reported behavior"
./scripts/ops.ps1 job list local
./scripts/ops.ps1 job show local <job_id>
./scripts/ops.ps1 job events local <job_id>
```

The local operational state lives at:

```text
runtime/<profile>/state/khosan.db
```

This file is runtime state and must not be committed, copied into chat, or treated as project source code.

The normal state flow is:

```text
CREATED -> QUEUED -> CLAIMED -> PREFLIGHT -> RUNNING -> VERIFYING -> SUCCEEDED
```

Failure/stop classifications include `FAILED`, `BLOCKED`, `NEEDS_HUMAN`, and `CANCELLED`. Terminal state is immutable through the normal transition API.

## Worker recovery model

A worker claims eligible jobs with a bounded lease. The lease prevents simultaneous workers from owning the same job. If the worker or host dies, the lease expires and another worker may recover the durable job.

Every fresh execution/recovery preflight revalidates the registered workspace. A moved path, disabled workspace, repository-identity mismatch, or requested HEAD mismatch blocks the job instead of silently switching project.

Dirty work is never reset or cleaned implicitly.

## Evidence and closure

Executor self-report is not sufficient for `SUCCEEDED`.

The rule-based workflow defines required evidence kinds. Missing required evidence yields `NEEDS_HUMAN`; failed required evidence yields `FAILED`; a human-gated workflow remains `NEEDS_HUMAN` even if automated evidence is green.

Evidence records can carry verifier name, exit code, pass/fail counts, commit SHA, artifact/hash, and external CI run/conclusion. GitHub is an evidence/lifecycle surface, not the local job queue.

## Failure routing

| Evidence | Classification | Action |
|---|---|---|
| ChatGPT says `FORBIDDEN`; no fresh `openai-mcp/1.0.0` server request | Host or conversation capability | Check Developer Mode and app selection, use a supported conversation, or switch to local Codex. Do not restart DevSpace or the tunnel. |
| Local endpoint healthy; public endpoint unavailable | Transport | Inspect the tunnel service and stable domain. |
| OAuth resource, issuer, audience, or PKCE error | Authentication contract | Stop rollout, restore the prior origin/configuration, refresh the app, and use a new test conversation. |
| MCP request arrives but no expected tool is selected | Tool metadata or host selection | Compare the contract snapshot, descriptions, annotations, and prompt. |
| Tool call begins then fails or times out | Tool/runtime | Inspect DevSpace `workspaceId`, registered KHOSAN `workspace_id`, path, Bash availability, timeout, and bounded logs. |
| Unknown DevSpace `workspaceId` | Session binding | Call `open_workspace` once, store the new session ID, and reuse it. |
| Unknown KHOSAN `workspace_id` | Durable project binding | Register the intended project explicitly. Never fall through to another project root. |
| Job remains active but lease expired | Worker recovery | Re-run preflight, reclaim with one worker, and continue from durable state. |
| Supervisor exits with code 73 | Already running | Find the existing profile owner; do not start a second supervisor. |
| Supervisor exits with code 75 | Crash circuit open | Preserve logs and fix the repeated failure before restarting. |

## Tunnel behavior

Local clients on the same machine use `127.0.0.1:7678` directly and require no tunnel.

ChatGPT Web requires one remotely reachable MCP transport for the web profile. The number of registered workspaces does not change the number of tunnels. Keep transport concerns separate from workspace/job state so ngrok or another stable HTTPS transport can later be replaced without migrating jobs.

## Safe stop

The current implementation intentionally avoids killing arbitrary port owners. Stop the service session that launched `ops.cli start`, or interrupt it. Do not use the legacy panel's port-wide kill behavior against V2.

## Rollback

V2 does not change the legacy runtime. If the canary fails, stop V2 and select the legacy ChatGPT app pointing at the legacy endpoint. Do not rotate or overwrite legacy credentials as part of rollback. Local KHOSAN orchestration state may remain for diagnosis but must not be used to infer that an unverified job succeeded.
