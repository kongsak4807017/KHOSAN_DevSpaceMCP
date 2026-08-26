# KHOSAN_DevSpace Multi-Workspace Durable Job Orchestration Design

Date: 2026-08-27
Status: Proposed design
Branch: `design/multi-workspace-job-orchestration`

## 1. Objective

Extend the existing KHOSAN_DevSpace MCP runtime into a durable software-project execution platform without replacing DevSpace, without adding a mailbox service, and without coupling the system to one local repository.

The design must support:

- many unrelated local projects located under different directories;
- one or more local workspace roots selected explicitly per job;
- ChatGPT Web and local Codex/CLI clients using the same execution contract;
- durable jobs that survive chat loss, MCP reconnects, process restarts, and host restarts;
- independent verification evidence before a job is classified as complete;
- GitHub Issues, pull requests, Actions, and artifacts as optional project-facing control/evidence surfaces;
- one MCP ingress per profile, independent of the number of registered workspaces;
- preservation of the existing legacy service on `127.0.0.1:7676` until an explicit promotion decision.

## 2. Non-goals

This phase does not add:

- Google Sheets, email, Supabase, or any other mailbox transport;
- a distributed cloud queue;
- autonomous multi-agent reasoning inside the worker;
- broad filesystem roots such as `C:\`;
- automatic destructive Git operations;
- automatic promotion of the current web canary;
- a replacement for DevSpace's MCP tools.

## 3. Existing baseline to preserve

KHOSAN_DevSpace already provides:

- pinned `@waishnav/devspace@1.0.8`;
- isolated local/web runtime profiles;
- local loopback canary on `127.0.0.1:7678`;
- per-profile config, state, worktree, OAuth, and logs;
- allowed-root validation;
- single-owner supervision;
- restart backoff and circuit breaking;
- rotating logs;
- TDD and Git/worktree governance in `AGENTS.md`;
- cross-client continuity rules that treat files and Git as durable truth;
- GitHub Actions CI.

These remain the execution foundation.

## 4. Target architecture

```text
ChatGPT Web / Codex / CLI
          |
          v
   MCP ingress profile
          |
          v
    KHOSAN Director
          |
          v
     Workflow Router
          |
          v
   Durable Job Service
      |          |
      |          +----> append-only Job Events
      v
   KHOSAN Worker
          |
          v
 Existing DevSpace MCP/runtime
          |
          v
  Explicit Workspace Registry
          |
          v
 Project checkout / worktree
          |
          v
 Executor + tools + tests/build
          |
          v
    Evidence Collector
          |
          +----> local evidence records
          +----> Git commit / PR / Actions / artifacts
          |
          v
   Closure classification
```

The worker remains deliberately simple. It claims, validates, dispatches, records, verifies, and closes work. It does not become a second AI agent.

## 5. Workspace registry

### 5.1 Principle

A profile may access many projects, but every job names exactly one registered workspace. The MCP endpoint is not duplicated per project.

### 5.2 Registry model

Use an ignored host-local registry under the profile runtime state, for example:

`runtime/<profile>/state/workspaces.json`

The repository stores only the schema/example and validation code. Machine-specific absolute paths remain uncommitted.

Example logical record:

```json
{
  "workspace_id": "rorebuild",
  "display_name": "ROREBUILD",
  "root_path": "C:\\ROREBUILD",
  "repository": "studio/RO-REBUILD",
  "expected_remote": "studio",
  "default_branch_policy": "preserve-current",
  "runtime_profile": "unity-dotnet",
  "governance_files": ["AGENTS.md"],
  "enabled": true
}
```

Future unrelated projects can register paths such as:

- `D:\\GitHub\\project-a`
- `E:\\Research\\tool-b`
- `C:\\Users\\User\\Projects\\project-c`

without changing the MCP endpoint.

### 5.3 Safety rules

- Reject filesystem roots (`C:\`, `D:\`, `/`) and configured broad user roots.
- Resolve and canonicalize paths before comparison.
- Refuse symlink/reparse-point escape from registered roots.
- Record repository identity, branch, HEAD, and dirty state at job preflight.
- A job cannot silently fall through to another workspace if its requested workspace is unavailable.
- Parallel writers use separate managed worktrees.

## 6. Durable Job model

Jobs are first-class local records, not chat messages.

Minimum fields:

```text
job_id
workspace_id
intent
workflow_type
status
attempt
created_at
claimed_at
started_at
finished_at
worker_id
request_hash
expected_head
result_summary
error_class
```

State machine:

```text
CREATED -> QUEUED -> CLAIMED -> PREFLIGHT -> RUNNING -> VERIFYING -> SUCCEEDED
                                      |          |           |
                                      +----------+-----------+-> FAILED
                                      +-----------------------> BLOCKED
                                      +-----------------------> NEEDS_HUMAN
Any nonterminal state -------------------------------> CANCELLED
```

Transitions are validated centrally. Terminal states are immutable except through an explicit administrative recovery operation.

## 7. Local durable storage

Use local SQLite under the existing ignored profile state directory. This extends the current local-state pattern and avoids introducing a mailbox service.

Suggested tables:

- `workspaces`
- `jobs`
- `job_events`
- `job_attempts`
- `evidence`
- `worker_leases`

`job_events` is append-only and records every accepted transition. SQLite is the operational source of truth; Git/files remain the project-content source of truth.

## 8. Worker and lease model

The worker polls the local durable job store, not the network.

Responsibilities:

1. claim one eligible job atomically;
2. acquire a bounded lease;
3. validate registered workspace and governance;
4. record branch, HEAD, dirty state, remote identity, and tool availability;
5. dispatch the assignment through the existing DevSpace execution surface;
6. renew the lease while active;
7. capture structured results and artifacts;
8. run the workflow's verification gates;
9. write evidence;
10. close as `SUCCEEDED`, `FAILED`, `BLOCKED`, or `NEEDS_HUMAN`.

If the worker dies, an expired lease allows safe recovery. `request_hash` plus `job_id` prevents accidental duplicate execution of the same logical operation.

## 9. Workflow Router

Start rule-based, not AI-based.

Initial workflow classes:

- `inspect-only`
- `bugfix`
- `feature`
- `test-only`
- `build-release`
- `production-change`

Examples:

```text
bugfix:
preflight -> inspect -> reproduce -> RED test -> patch -> targeted tests -> broader tests -> verify

inspect-only:
preflight -> inspect -> evidence -> report, with no writes

production-change:
preflight -> inspect -> implement -> tests -> independent verification -> human gate -> deploy -> post-verify
```

Project-local governance can override or extend gates.

## 10. Evidence plane

Executor self-report is not sufficient for job closure.

Evidence records should support:

- command and verifier name;
- exit code;
- passed/failed/skipped/total counts when available;
- branch and commit SHA;
- before/after HEAD;
- changed files summary;
- artifact path/hash;
- GitHub Actions run ID and conclusion;
- deployment fingerprints when the project defines them;
- human-retest requirement.

Closure rule:

```text
executor_done != job_succeeded

job_succeeded = executor_done
                + required_verification_green
                + governance_satisfied
                + required_artifacts_present
```

## 11. GitHub integration

GitHub is a project lifecycle and evidence surface, not the local queue.

Optional mappings:

- GitHub Issue -> human-visible work item
- branch/worktree -> isolated execution context
- commit -> durable project checkpoint
- pull request -> review/change proposal
- GitHub Actions -> independent verification
- Actions artifacts -> evidence artifacts
- labels/checks -> summarized job state

The local SQLite job state remains authoritative for execution continuity. A GitHub outage must not corrupt or lose an active local job.

## 12. MCP ingress and tunnel strategy

### 12.1 One ingress, many workspaces

The number of tunnels/endpoints is independent of the number of workspaces.

A single web MCP profile can expose one endpoint such as:

```text
https://<stable-origin>/mcp
```

After authentication, `workspace_id` selects the registered project. Adding a new project does not require a new tunnel.

### 12.2 Local clients

Local Codex/CLI/IDE clients use the loopback local profile directly:

```text
http://127.0.0.1:7678/mcp
```

No tunnel is required for clients running on the same machine.

### 12.3 ChatGPT Web

ChatGPT Web cannot directly connect to a loopback/private local MCP endpoint. A reachable remote transport is therefore required.

The transport is treated as replaceable infrastructure:

```text
ChatGPT Web -> remote MCP transport -> local web profile -> KHOSAN/DevSpace
```

Supported design choices are:

1. OpenAI Secure MCP Tunnel when the pinned DevSpace OAuth/resource contract is compatible;
2. a stable HTTPS reverse tunnel such as ngrok/Cloudflare/Tailscale Funnel while direct DevSpace public-origin OAuth is required;
3. a future self-hosted reverse proxy with equivalent TLS, authentication, and host validation.

### 12.4 Current compatibility decision

Do not migrate the production/canary web path to OpenAI Secure MCP Tunnel yet while upstream DevSpace issue #182 remains unresolved for the pinned runtime. DevSpace 1.0.8 currently couples `publicBaseUrl` to OAuth resource identity, while Secure MCP Tunnel can present a different externally visible MCP resource origin.

Therefore:

- keep the existing local `7678` profile as the primary development path;
- keep legacy `7676` untouched;
- retain the future `7677` web profile design;
- for web canary, continue using a stable HTTPS public origin such as ngrok or an equivalent reverse tunnel unless a tested compatibility patch is adopted;
- encapsulate transport configuration so changing ngrok to Secure MCP Tunnel later requires no job/workspace architecture changes.

## 13. Governance and destructive operations

The existing `AGENTS.md` remains authoritative.

Additional rules:

- workspace registration is explicit;
- broad roots are rejected;
- jobs record expected workspace and repository identity;
- dirty work is never reset/cleaned implicitly;
- commit/push/merge/deploy behavior follows project governance;
- privileged OS administration is a separate capability class from software-project execution;
- destructive operations require explicit policy and, where configured, human approval;
- secrets, local workspace registry, SQLite job state, and logs remain ignored.

## 14. Failure and recovery

Required recovery cases:

- ChatGPT conversation disappears: job continues from durable state;
- MCP session is rejected: no job state is lost;
- DevSpace process restarts: worker reopens the registered workspace and revalidates HEAD/status;
- worker process dies: lease expires and the job becomes recoverable;
- host restarts: worker resumes from SQLite after preflight reconciliation;
- GitHub is unavailable: local execution can continue, but GitHub-dependent closure gates remain pending;
- workspace path moved or repository identity changed: job becomes `BLOCKED`, never silently redirected.

## 15. Implementation phases

### Phase 1 — Workspace Registry

- registry schema and parser;
- add/list/inspect/disable operations;
- canonical path and broad-root validation;
- repository identity preflight;
- tests for unrelated roots and invalid roots.

### Phase 2 — Durable Job Core

- SQLite schema;
- job/event repository;
- state-machine validation;
- request hash/idempotency;
- worker lease primitives;
- restart/recovery tests.

### Phase 3 — Worker

- claim/preflight/lease loop;
- DevSpace workspace dispatch adapter;
- structured result capture;
- failure classification;
- bounded supervision integration.

### Phase 4 — Evidence

- evidence schema;
- verifier adapters;
- closure policy;
- Git/GitHub evidence adapters;
- CI conclusion ingestion.

### Phase 5 — Router and Director contract

- rule-based workflows;
- project governance hooks;
- human gates;
- job continuation/resume API;
- structured summary for ChatGPT Web/Codex.

### Phase 6 — Web transport promotion

- preserve existing security gate;
- test stable HTTPS canary;
- revisit Secure MCP Tunnel only after upstream OAuth/resource compatibility is fixed or a minimal audited compatibility patch is proven.

## 16. Test strategy

All behavior changes follow TDD.

Required test groups:

- workspace registry containment and identity;
- multiple unrelated workspace roots;
- job transition legality;
- duplicate request/idempotency;
- worker lease expiry/recovery;
- worker crash and host restart recovery;
- dirty workspace preservation;
- wrong repository/branch/HEAD blocking;
- evidence-required closure;
- GitHub outage degradation;
- profile isolation;
- regression of current supervisor, OAuth, runtime, and CI behavior.

No phase is promoted while the existing strict test suite regresses.

## 17. Key design decisions

1. No mailbox layer.
2. SQLite is the local operational state store.
3. Git/files remain durable project truth.
4. GitHub is lifecycle/evidence integration, not the execution queue.
5. One MCP ingress serves many explicitly registered workspaces.
6. Local clients require no tunnel.
7. ChatGPT Web requires remote reachability; transport is replaceable.
8. Existing ngrok-style stable HTTPS can remain for the current DevSpace web canary until Secure MCP Tunnel compatibility is proven.
9. The worker is infrastructure, not another reasoning agent.
10. Independent evidence, not executor self-report, closes jobs.
