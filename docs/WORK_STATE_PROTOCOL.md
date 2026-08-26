# Cross-client work-state protocol

Conversation state is best effort. Files and Git are the durable source of truth.

When continuing in the same client/profile:

1. Reuse the current `workspaceId`.
2. Call `open_workspace` again only when the ID is rejected, the project/worktree changes, or the user explicitly requests a reopen.

When switching from ChatGPT web to local Codex or back:

1. Stop issuing writes from the previous client.
2. Open the same project or an explicit managed worktree once in the new profile.
3. Read the current branch, HEAD, `git status`, and diff before editing.
4. Resume from saved files and Git state; do not assume the other profile's `workspaceId` is valid.
5. If both clients must work simultaneously, allocate separate Git worktrees.

Recovery targets:

- RPO 0 for data already written to disk.
- Switch to the local profile within two minutes when ChatGPT rejects MCP before the request reaches the server.
- Conversation reasoning state is not guaranteed across clients; record important pending decisions in project documentation or a user-approved handoff file.
