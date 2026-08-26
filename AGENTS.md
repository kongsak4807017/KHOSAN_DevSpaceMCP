# KHOSAN_DevSpace repository rules

- `C:\Users\User\Downloads\tunel` is the live legacy instance. Treat it as read-only unless the user explicitly requests a legacy change.
- Use the repo-local `@waishnav/devspace` dependency. Never call a floating `npx ...@latest` from runtime scripts.
- Follow TDD for behavior changes: failing test, minimal implementation, then refactor.
- Never commit `runtime/`, tokens, auth files, SQLite state, local workspace paths, logs, tunnel credentials, or generated worktrees.
- Keep the `local` and `web` profiles isolated by port, config directory, state directory, worktree root, OAuth token, logs, and orchestration database.
- A `401` response with a Bearer challenge from `/mcp` is healthy authentication discovery.
- If ChatGPT reports `FORBIDDEN` and no fresh `openai-mcp/1.0.0` request reaches the server log, classify it as a host/conversation capability failure. Do not restart local services.
- Only one client may write a checkout at a time. Use managed Git worktrees for parallel writers.
- Every durable Job names exactly one enabled KHOSAN `workspace_id`. Never fall through to a different workspace when registration, repository identity, branch/HEAD expectations, or path availability does not match.
- Revalidate workspace root, repository identity, HEAD expectations, dirty state, and project governance before recovered execution. Preserve dirty work; never reset or clean implicitly.
- KHOSAN `workspace_id`, DevSpace session `workspaceId`, and durable `job_id` are distinct identifiers with different lifetimes. Do not substitute them.
- Unknown workflow types fail closed. Do not let an agent invent a workflow that bypasses configured evidence or human gates.
- Executor self-report does not close a Job. `SUCCEEDED` requires the workflow's required evidence to be present and green plus all configured governance gates.
- Worker ownership is lease-based. Recover an expired Job through the lease mechanism; do not create a duplicate logical Job to continue it.
- Adding another local project must extend only explicit registered roots. Never widen a profile to a drive root, user home, or other broad filesystem root for convenience.
- One web MCP ingress may serve many registered workspaces; workspace growth must not create extra tunnels or relax authentication/filesystem boundaries.
- Do not promote the web profile while the security exception in `docs/SECURITY_BOUNDARY.md` is unresolved or explicitly accepted.
