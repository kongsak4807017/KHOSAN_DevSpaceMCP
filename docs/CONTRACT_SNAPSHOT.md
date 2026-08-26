# MCP contract snapshot

## Pinned baseline

- Package: `@waishnav/devspace@1.0.8`
- Tool mode: `minimal`
- Widget mode: `changes`
- Skills: enabled
- Subagents: disabled
- Expected tools: `open_workspace`, `read`, `write`, `edit`, `bash`
- Workspace rule: open once per project/worktree, then reuse the returned `workspaceId`

The expected list comes from the pinned upstream configuration. Before web promotion it must be replaced or supplemented by a captured MCP Inspector/ChatGPT tool scan including full schemas and annotations.

## Contract gates

- One user intent per tool.
- Descriptions must state when to use the tool and important disallowed cases.
- `readOnlyHint`, `destructiveHint`, `openWorldHint`, and idempotency metadata must match behavior.
- Path inputs must remain inside configured roots.
- Write and shell tools require host confirmation appropriate to their annotations.
- Metadata diffs require app Refresh and a new-conversation regression run.
- Git write behavior is tested in a disposable local repository because upstream issue #149 showed that tool wording can cause host refusal.
