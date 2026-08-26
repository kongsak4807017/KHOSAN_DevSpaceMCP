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

## Next: web canary

1. Obtain a separate stable HTTPS canary origin.
2. Activate `profiles/web/profile.json` from the reviewed example.
3. Run the web profile on port `7677` without stopping legacy port `7676`.
4. Validate OAuth issuer/resource/audience, DCR, PKCE S256, and MCP Inspector.
5. Create a private ChatGPT Developer Mode app named `KHOSAN_DevSpace`.
6. Run the continuity matrix: 20 calls, 10 turns, 30-minute idle, write confirmation, workspace reuse, and restart recovery.

## Promotion gates

- Resolve or explicitly accept the documented transitive dependency advisories.
- Complete 72-hour canary soak over at least three real work sessions.
- Preserve zero duplicate supervisors and zero broad-root access.
- Demonstrate rollback to the legacy endpoint within five minutes.
- Keep Secure MCP Tunnel as R&D until DevSpace issue #182 is fixed or a tested resource allowlist patch exists.
