# KHOSAN_DevSpace

Private, tool-only MCP runtime profiles built around a pinned DevSpace core.

Repository: [kongsak4807017/KHOSAN_DevSpaceMCP](https://github.com/kongsak4807017/KHOSAN_DevSpaceMCP)

This repository does not replace the live legacy instance yet. The legacy service remains on `127.0.0.1:7676`. The first V2 canary is a loopback-only local profile on `127.0.0.1:7678` for Codex desktop, CLI, and IDE clients.

## Why this exists

The previous wrapper mixed UI, tunnel control, process ownership, secrets, and health polling. It also probed the public MCP endpoint every three seconds, producing hundreds of thousands of log records. This implementation separates:

- reproducible DevSpace dependency and profiles;
- runtime secrets and SQLite state;
- failure classification;
- single-owner process supervision;
- bounded logs;
- ChatGPT web and local Codex access paths.

## Archetype

`tool-only / private internal`. DevSpace supplies the MCP tools. No widget is added because the requested workflow does not need a custom UI.

## Current status

- Pinned DevSpace: `1.0.8`
- Local profile: `127.0.0.1:7678`
- Web profile: template only; it needs a separate stable HTTPS canary origin before activation
- Legacy profile: unchanged at `127.0.0.1:7676`
- Subagents: disabled in both V2 profiles

## Commands

```powershell
npm ci
npm run test:strict
npm run compile
./scripts/ops.ps1 materialize local
./scripts/ops.ps1 doctor local
./scripts/ops.ps1 start local
./scripts/ops.ps1 status local
```

`start` owns a profile lock, restarts failed child processes with capped exponential backoff, opens a circuit after repeated crashes, and writes rotating logs under the ignored `runtime/` directory.

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

## Primary references

- [OpenAI: Build an MCP server](https://developers.openai.com/plugins/build/mcp-server)
- [OpenAI: ChatGPT Developer Mode](https://developers.openai.com/api/docs/guides/developer-mode)
- [OpenAI: Codex MCP configuration](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
- [OpenAI: Connect and test a plugin](https://developers.openai.com/plugins/deploy/connect-chatgpt)
- [DevSpace upstream](https://github.com/Waishnav/devspace)

## Production readiness

The loopback local canary is implemented and validated. The separate ChatGPT web profile is intentionally not active until it has its own stable HTTPS origin and the dependency exception in `docs/SECURITY_BOUNDARY.md` is resolved or explicitly accepted.
