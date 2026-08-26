# KHOSAN_DevSpace repository rules

- `C:\Users\User\Downloads\tunel` is the live legacy instance. Treat it as read-only unless the user explicitly requests a legacy change.
- Use the repo-local `@waishnav/devspace` dependency. Never call a floating `npx ...@latest` from runtime scripts.
- Follow TDD for behavior changes: failing test, minimal implementation, then refactor.
- Never commit `runtime/`, tokens, auth files, SQLite state, logs, tunnel credentials, or generated worktrees.
- Keep the `local` and `web` profiles isolated by port, config directory, state directory, worktree root, OAuth token, and logs.
- A `401` response with a Bearer challenge from `/mcp` is healthy authentication discovery.
- If ChatGPT reports `FORBIDDEN` and no fresh `openai-mcp/1.0.0` request reaches the server log, classify it as a host/conversation capability failure. Do not restart local services.
- Only one client may write a checkout at a time. Use managed Git worktrees for parallel writers.
- Do not promote the web profile while the security exception in `docs/SECURITY_BOUNDARY.md` is unresolved or explicitly accepted.
