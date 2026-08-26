# KHOSAN_DevSpace roadmap

## Implemented

- Repository-local DevSpace `1.0.8` pin and lockfile
- Isolated `local` and `web` profile model
- Local loopback canary on port `7678`
- Runtime-local OAuth token and SQLite/worktree directories
- Health classification for host, transport, auth, server, and tool failures
- `401 Bearer` readiness handling
- Single-instance lock, capped exponential restart backoff, and crash circuit breaker
- Rotating service logs
- Secret-free operator CLI and PowerShell wrapper
- Codex MCP registration under `KHOSAN_DevSpace`
- Strict unit tests and compile checks
- Explicit profile-local multi-workspace registry for unrelated project roots
- Automatic merge of enabled registered workspace roots into DevSpace `allowedRoots`
- Profile-local durable `khosan.db` orchestration store
- First-class Jobs with request-hash idempotency and append-only event history
- Explicit fail-closed Job state machine
- Worker lease primitives for single ownership and expired-lease recovery
- Workspace/repository/HEAD preflight before execution
- Structured evidence persistence and evidence-gated closure policy
- Rule-based workflow definitions for inspect, bugfix, feature, tests, build/release, and production change
- Operator CLI for workspace registration/disable/list/show and job create/list/show/events
- Durable cross-client recovery protocol separating KHOSAN `workspace_id`, DevSpace `workspaceId`, and `job_id`

## Next: execution and evidence adapters

1. Bind `JobWorker` to a concrete reviewed executor adapter for the selected local coding-agent path rather than inventing an unrestricted shell contract.
2. Add a bounded worker service loop around the implemented claim/preflight/lease/recovery primitives.
3. Add verifier adapters that translate project test/build outputs into structured evidence.
4. Add Git/GitHub evidence adapters for commit/PR/Actions run identity and conclusion.
5. Expose reviewed orchestration operations through the MCP surface so ChatGPT/Codex can create/inspect durable work without relying on broad shell commands.
6. Exercise crash/restart recovery against real local projects before enabling autonomous continuation.

## Then: web canary

1. Obtain a separate stable HTTPS canary origin.
2. Activate `profiles/web/profile.json` from the reviewed example.
3. Run the web profile on port `7677` without stopping legacy port `7676`.
4. Validate OAuth issuer/resource/audience, DCR, PKCE S256, and MCP Inspector.
5. Create a private ChatGPT Developer Mode app named `KHOSAN_DevSpace`.
6. Run the continuity matrix: 20 calls, 10 turns, 30-minute idle, write confirmation, workspace reuse, durable-job recovery, and restart recovery.

One web MCP ingress serves all explicitly approved workspaces. Adding a project does not require another tunnel.

## Promotion gates

- Resolve or explicitly accept the documented transitive dependency advisories.
- Complete 72-hour canary soak over at least three real work sessions.
- Preserve zero duplicate supervisors and zero broad-root access.
- Demonstrate rollback to the legacy endpoint within five minutes.
- Prove durable job recovery without duplicate execution.
- Prove required evidence prevents executor self-report from closing work prematurely.
- Keep Secure MCP Tunnel as R&D until DevSpace issue #182 is fixed or a tested resource allowlist/compatibility patch exists.
