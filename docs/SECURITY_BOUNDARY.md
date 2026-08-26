# Security boundary

## Enforced controls

- Both profiles bind to loopback only.
- Only the future `web` profile may be exposed through one stable HTTPS tunnel.
- Config, state, worktrees, tokens, and logs are separated per profile under ignored `runtime/` directories.
- Owner tokens are generated locally and never printed by operator commands.
- Broad drive roots such as `C:\` are rejected.
- Subagents are disabled during the continuity canary.
- Shell command text logging is disabled.
- Logs rotate at 10 MiB with five backups per stream.
- A profile lock prevents duplicate supervisors.
- Repeated failures open a circuit instead of creating an unbounded restart loop.

## Known dependency exception

`@waishnav/devspace@1.0.8` currently installs a disabled subagent dependency tree with npm advisories in `undici`, `brace-expansion`, and `protobufjs`. The upstream packages pin or shrinkwrap the affected versions, so root-level npm overrides do not currently replace them. `npm audit` reports three moderate and two high findings.

Mitigation for the canary:

- all DevSpace subagent providers are disabled;
- the canary is loopback-only;
- no public web promotion is allowed while the exception remains unresolved or is not explicitly accepted after review;
- `npm run security:audit` remains a visible manual, non-blocking canary gate; CI reports advisories and blocks critical findings while high/moderate findings remain documented;
- upgrades are pinned and tested rather than automatic.

This is not recorded as “fixed.” It is a bounded canary exception awaiting an upstream dependency release, a minimal audited fork, or an explicit risk decision.

## Credential handling

The local Owner password lives at `runtime/local/config/auth.json`. The web profile will receive a different token. Do not display either value in a UI, copy it into chat, or commit it. Before web promotion, narrow file ACLs to the interactive user and SYSTEM, then rerun OAuth and runtime tests.

## Write safety

OpenAI Developer Mode treats tools without `readOnlyHint` as write tools and normally asks for confirmation. Tool annotations must match real behavior. Only one client may write a checkout at a time; parallel work uses managed worktrees.
