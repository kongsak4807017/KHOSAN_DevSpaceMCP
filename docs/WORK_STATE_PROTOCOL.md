# Cross-client work-state protocol

Conversation state is best effort. Files and Git are the durable source of truth for project content. KHOSAN profile-local SQLite is the durable source of truth for orchestration state.

## Identifiers

Three identifiers have different lifetimes and must not be substituted for one another:

- `workspace_id`: durable KHOSAN project identity stored in `runtime/<profile>/state/khosan.db`.
- `workspaceId`: DevSpace session/worktree handle returned by `open_workspace` for a particular client/profile session.
- `job_id`: durable KHOSAN execution identity with an append-only event history.

A new ChatGPT/Codex session may receive a new DevSpace `workspaceId` while continuing the same KHOSAN `workspace_id` and `job_id`.

## Continuing in the same client/profile

1. Reuse the current DevSpace `workspaceId`.
2. Call `open_workspace` again only when the ID is rejected, the project/worktree changes, or the user explicitly requests a reopen.
3. For durable work, inspect the current `job_id` and its events before issuing more writes.
4. Do not infer completion from conversation text; use persisted job/evidence state.

## Switching from ChatGPT Web to local Codex or back

1. Stop issuing writes from the previous client.
2. Resolve the same KHOSAN `workspace_id`; never silently choose another registered project.
3. Inspect the durable `job_id` and event history if the work belongs to an active job.
4. Open the same project or an explicit managed worktree once in the new profile.
5. Read the current branch, HEAD, `git status`, and diff before editing.
6. Resume from saved files, Git state, and durable job events; do not assume the other profile's DevSpace `workspaceId` is valid.
7. If both clients must work simultaneously, allocate separate Git worktrees and preserve the repository's single-writer rules.

## Job recovery

When a chat, MCP session, worker, or host disappears:

1. Read `job show` and `job events` for the durable `job_id`.
2. Revalidate the registered workspace root and repository identity.
3. Re-read branch, HEAD, dirty state, and governance files.
4. If a worker lease expired, reclaim the job only through the lease mechanism; do not create a duplicate logical job to continue the same operation.
5. If the requested/expected HEAD no longer matches, classify the job `BLOCKED` rather than silently executing against a different revision.
6. Continue from persisted project artifacts and event state.

The same logical job request is idempotent through its request hash. Recovery must preserve existing dirty work and must never imply `reset`, `clean`, or checkout replacement.

## Closure

Executor self-report is not authoritative closure.

A job may reach `SUCCEEDED` only after the workflow's required evidence is present and green and all configured governance gates are satisfied. Missing evidence or a human gate remains `NEEDS_HUMAN`; failed required evidence becomes `FAILED`.

Conversation summaries may describe the current state, but they must not override the persisted state machine or verification evidence.

## Recovery targets

- RPO 0 for data already written to disk or committed to the local orchestration database.
- Switch to the local profile within two minutes when ChatGPT rejects MCP before the request reaches the server.
- Conversation reasoning state is not guaranteed across clients; record important pending decisions in project documentation, durable job events/evidence, or a user-approved handoff file.
- A moved/unavailable workspace is a fail-closed condition; the system never falls through to another local project.
