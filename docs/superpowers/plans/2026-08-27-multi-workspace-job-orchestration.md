# Multi-Workspace Durable Job Orchestration Implementation Plan

**Goal:** Add a local durable multi-workspace job orchestration layer to KHOSAN_DevSpace while preserving the existing MCP/DevSpace execution plane and single web ingress.

**Architecture:** A profile-local SQLite database under `runtime/<profile>/state/khosan.db` stores registered workspaces, jobs, append-only events, leases, and evidence. A deliberately simple worker claims jobs, validates the workspace, invokes a reviewed executor adapter, and uses independent evidence for closure. GitHub remains an optional lifecycle/evidence surface, not the queue.

**Tech Stack:** Python 3.13 standard library, existing `unittest`, pinned DevSpace 1.0.8, and GitHub Actions CI.

**Spec:** `docs/superpowers/specs/2026-08-27-multi-workspace-job-orchestration-design.md`

## Implementation checkpoint — 2026-08-27

Implemented in this branch:

- [x] Profile-local SQLite `StateStore` with deterministic connection ownership.
- [x] Explicit multi-workspace registry supporting unrelated project roots.
- [x] Broad-root rejection, repository-identity preflight, HEAD/dirty inspection, and disable semantics.
- [x] Enabled registered roots merged into materialized DevSpace `allowedRoots`.
- [x] Durable Jobs, SHA-256 request idempotency, validated state transitions, and append-only events.
- [x] Worker lease primitives, atomic claim, no-double-claim behavior, expired-lease recovery, and preflight blocking.
- [x] Generic `JobWorker` execution-adapter interface.
- [x] Durable evidence repository and evidence-gated closure policy.
- [x] Rule-based fail-closed workflow router.
- [x] Workspace and Job operator CLI plus PowerShell passthrough wrapper.
- [x] Cross-client durable-state, recovery, tunnel, and governance documentation.
- [x] TDD RED runs were observed before production implementations.
- [x] Code-core Windows CI reached GREEN before final documentation edits.

Final branch verification still required after the last documentation/governance commit:

- [ ] Fresh `npm run test:strict` on final HEAD.
- [ ] Fresh `npm run compile` on final HEAD.
- [ ] Fresh critical dependency-audit gate on final HEAD.
- [ ] Verify final diff contains no `runtime/`, SQLite database, local runtime path state, token, auth file, log, tunnel credential, or generated worktree.

Intentionally deferred rather than guessed:

- [ ] Concrete coding-agent executor binding (`Codex`, another reviewed executor, or an approved DevSpace-mediated adapter).
- [ ] Long-running worker service/daemon loop around the implemented `run_once` + lease primitives.
- [ ] Project-specific verifier adapters that transform test/build output into Evidence records.
- [ ] Git/GitHub evidence adapter for commits, PRs, Actions runs, and artifacts.
- [ ] MCP-facing orchestration tools for Job/Workspace operations.
- [ ] Real-host crash/restart soak and autonomous continuation acceptance.

These deferred items are the next execution-adapter/evidence-integration phase. The current implementation must not invent an unrestricted shell executor merely to make the system appear autonomous.

## Global constraints

- No Google Sheets, email, Supabase, or mailbox transport.
- Preserve legacy service `127.0.0.1:7676` untouched.
- Preserve local profile `127.0.0.1:7678` and future web profile `7677` separation.
- One MCP ingress serves many explicitly registered workspaces.
- Reject broad filesystem roots and never silently redirect to another workspace.
- Dirty work is never reset or cleaned implicitly.
- Local runtime state, workspace paths, tokens, and logs remain ignored.
- Existing strict tests and CI must remain green.
- TDD is required for behavior changes.

## Phase 1 — Workspace Registry

Implemented interfaces:

- `StateStore(path)`
- immutable `WorkspaceRecord`
- `WorkspaceRegistry.add/get/list/disable/preflight`
- `WorkspaceError`
- automatic materialized-profile integration for enabled roots

Verified behaviors include unrelated roots, broad-root rejection, duplicate IDs, persistence, disable semantics, and wrong-repository preflight.

## Phase 2 — Durable Job Core

Implemented interfaces:

- `JobStatus`: `CREATED`, `QUEUED`, `CLAIMED`, `PREFLIGHT`, `RUNNING`, `VERIFYING`, `SUCCEEDED`, `FAILED`, `BLOCKED`, `NEEDS_HUMAN`, `CANCELLED`
- immutable `JobRecord`
- `JobRepository.create/get/list/enqueue/transition/events`
- stable SHA-256 `request_hash`

Terminal states are immutable through the normal transition API and illegal transitions fail closed.

## Phase 3 — Worker Lease and Recovery Core

Implemented interfaces:

- `WorkerLeaseRepository.claim_next/renew/release`
- `JobWorker.run_once`
- executor adapter contract `execute(job, workspace) -> ExecutionResult`

This phase provides durable ownership/recovery primitives and the execution boundary. A concrete coding-agent executor and persistent service loop are deliberately left for the next reviewed phase.

## Phase 4 — Evidence Plane

Implemented interfaces:

- `EvidenceRecord`
- `EvidenceRepository.add/get/for_job`
- `ClosurePolicy.evaluate`

Executor self-report alone cannot close a Job. Missing required evidence yields `NEEDS_HUMAN`; failed required evidence yields `FAILED`; all required green evidence permits automated success only when no human gate remains.

## Phase 5 — Rule-based Workflow Router

Implemented initial workflows:

- `inspect-only`
- `bugfix`
- `feature`
- `test-only`
- `build-release`
- `production-change`

Unknown workflow names fail closed.

## Phase 6 — Operator CLI

Implemented commands:

- `workspace add/list/show/disable`
- `job create/list/show/events`

Commands emit JSON and never print runtime secrets. Adding/disabling a workspace rematerializes the profile so enabled registry roots become the DevSpace access boundary.

## Phase 7 — Documentation and Regression

Updated:

- `README.md`
- `docs/RUNBOOK.md`
- `docs/ROADMAP.md`
- `docs/WORK_STATE_PROTOCOL.md`
- `AGENTS.md`

Final closeout is gated on fresh final-HEAD CI and changed-file inspection.
