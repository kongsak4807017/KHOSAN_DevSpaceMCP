# Operations runbook

## Normal startup

1. Run `npm ci` after checkout or lockfile changes.
2. Run `npm run test:strict` and `npm run compile`.
3. Run `./scripts/ops.ps1 doctor local`.
4. Run `./scripts/ops.ps1 start local` in the service session.
5. Verify with `./scripts/ops.ps1 status local`.

The local endpoint is healthy when GET `/mcp` returns `401` with a Bearer challenge. Do not require an unauthenticated `200`.

## Failure routing

| Evidence | Classification | Action |
|---|---|---|
| ChatGPT says `FORBIDDEN`; no fresh `openai-mcp/1.0.0` server request | Host or conversation capability | Check Developer Mode and app selection, use a supported conversation, or switch to local Codex. Do not restart DevSpace or the tunnel. |
| Local endpoint healthy; public endpoint unavailable | Transport | Inspect the tunnel service and stable domain. |
| OAuth resource, issuer, audience, or PKCE error | Authentication contract | Stop rollout, restore the prior origin/configuration, refresh the app, and use a new test conversation. |
| MCP request arrives but no expected tool is selected | Tool metadata or host selection | Compare the contract snapshot, descriptions, annotations, and prompt. |
| Tool call begins then fails or times out | Tool/runtime | Inspect workspace ID, path, Bash availability, timeout, and bounded logs. |
| Unknown workspace ID | Session binding | Call `open_workspace` once, store the new ID, and reuse it. |
| Supervisor exits with code 73 | Already running | Find the existing profile owner; do not start a second supervisor. |
| Supervisor exits with code 75 | Crash circuit open | Preserve logs and fix the repeated failure before restarting. |

## Safe stop

The current implementation intentionally avoids killing arbitrary port owners. Stop the service session that launched `ops.cli start`, or interrupt it. Do not use the legacy panel's port-wide kill behavior against V2.

## Rollback

V2 does not change the legacy runtime. If the canary fails, stop V2 and select the legacy ChatGPT app pointing at the legacy endpoint. Do not rotate or overwrite legacy credentials as part of rollback.
