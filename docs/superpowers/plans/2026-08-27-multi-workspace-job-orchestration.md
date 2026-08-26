# Multi-Workspace Durable Job Orchestration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local durable multi-workspace job orchestration layer to KHOSAN_DevSpace while preserving the existing MCP/DevSpace execution plane and single web ingress.

**Architecture:** A profile-local SQLite database under `runtime/<profile>/state/khosan.db` stores registered workspaces, jobs, append-only events, leases, and evidence. A deliberately simple worker claims jobs, validates the workspace, executes a workflow through an adapter, records evidence, and closes only when required verification passes. GitHub remains an optional lifecycle/evidence surface, not the queue.

**Tech Stack:** Python 3.13 standard library (`sqlite3`, `pathlib`, `subprocess`, `hashlib`, `json`, `uuid`), existing `unittest`, existing DevSpace 1.0.8 runtime and GitHub Actions CI.

**Spec:** `docs/superpowers/specs/2026-08-27-multi-workspace-job-orchestration-design.md`

## Global Constraints

- No Google Sheets, email, Supabase, or mailbox transport.
- Preserve legacy service `127.0.0.1:7676` untouched.
- Preserve local profile `127.0.0.1:7678` and future web profile `7677` separation.
- One MCP ingress serves many explicitly registered workspaces.
- Reject broad filesystem roots and never silently redirect to another workspace.
- Dirty work is never reset or cleaned implicitly.
- Local runtime state, workspace paths, tokens, and logs remain ignored.
- Existing strict tests and CI must remain green.
- TDD: each production behavior is introduced by a failing test first.

---

### Task 1: Profile-local SQLite state and Workspace Registry

**Files:**
- Create: `ops/state.py`
- Create: `ops/workspaces.py`
- Create: `tests/test_workspaces.py`

**Interfaces:**
- Produces: `StateStore(path: Path)` with `connection()` and `initialize()`.
- Produces: immutable `WorkspaceRecord`.
- Produces: `WorkspaceRegistry(store).add(...)`, `.get(workspace_id)`, `.list()`, `.disable(workspace_id)`, `.preflight(workspace_id)`.
- Produces: `WorkspaceError` for validation and identity failures.

- [ ] Write failing tests covering unrelated roots, broad-root rejection, duplicate IDs, persistence, disable/list/get, and wrong-repository preflight.
- [ ] Run strict CI and verify RED because `ops.workspaces` does not exist.
- [ ] Implement minimal SQLite schema and registry behavior.
- [ ] Run strict CI and verify GREEN.
- [ ] Refactor without changing behavior.

### Task 2: Durable Job Core and Append-only Event Ledger

**Files:**
- Create: `ops/jobs.py`
- Create: `tests/test_jobs.py`
- Modify: `ops/state.py`

**Interfaces:**
- Produces: `JobStatus` enum: `CREATED`, `QUEUED`, `CLAIMED`, `PREFLIGHT`, `RUNNING`, `VERIFYING`, `SUCCEEDED`, `FAILED`, `BLOCKED`, `NEEDS_HUMAN`, `CANCELLED`.
- Produces: immutable `JobRecord`.
- Produces: `JobRepository.create(...)`, `.enqueue(...)`, `.transition(...)`, `.get(...)`, `.events(...)`.
- Produces: stable SHA-256 `request_hash` used for duplicate logical request detection.

- [ ] Write failing tests for legal/illegal transitions, persistence, append-only event order, immutable terminal states, and duplicate request idempotency.
- [ ] Run strict CI and verify RED.
- [ ] Implement minimal job schema/repository/state machine.
- [ ] Run strict CI and verify GREEN.

### Task 3: Worker Lease and Crash Recovery

**Files:**
- Create: `ops/worker.py`
- Create: `tests/test_worker.py`
- Modify: `ops/state.py`
- Modify: `ops/jobs.py`

**Interfaces:**
- Produces: `WorkerLeaseRepository.claim_next(worker_id, now, lease_seconds)`.
- Produces: `.renew(job_id, worker_id, now, lease_seconds)` and `.release(...)`.
- Produces: `JobWorker.run_once()` that claims one job, performs preflight, invokes an executor adapter, captures evidence, and transitions deterministically.
- Executor adapter signature: `execute(job: JobRecord, workspace: WorkspaceRecord) -> ExecutionResult`.

- [ ] Write failing tests for atomic claim, no double claim, lease renewal, expired lease recovery, blocked preflight, and executor failure.
- [ ] Run strict CI and verify RED.
- [ ] Implement minimal leases and `run_once`.
- [ ] Run strict CI and verify GREEN.

### Task 4: Evidence Plane and Closure Policy

**Files:**
- Create: `ops/evidence.py`
- Create: `tests/test_evidence.py`
- Modify: `ops/state.py`
- Modify: `ops/worker.py`

**Interfaces:**
- Produces: `EvidenceRecord` and `EvidenceRepository.add(...)`, `.for_job(job_id)`.
- Produces: `ClosurePolicy.evaluate(job_id, required_kinds)` returning `SUCCEEDED`, `FAILED`, or `NEEDS_HUMAN` decision data.
- Evidence fields include kind, verifier, exit code, counts, commit SHA, artifact/hash, external run ID/conclusion, and structured JSON details.

- [ ] Write failing tests proving executor self-report alone cannot close a job, failed required evidence prevents success, and all required GREEN evidence permits success.
- [ ] Run strict CI and verify RED.
- [ ] Implement evidence persistence and closure policy.
- [ ] Run strict CI and verify GREEN.

### Task 5: Rule-based Workflow Router

**Files:**
- Create: `ops/workflows.py`
- Create: `tests/test_workflows.py`

**Interfaces:**
- Produces: `WorkflowDefinition(name, writable, required_evidence, human_gate)`.
- Produces: `WorkflowRouter.resolve(workflow_type)` for `inspect-only`, `bugfix`, `feature`, `test-only`, `build-release`, `production-change`.

- [ ] Write failing tests for all initial workflow classes and fail-closed unknown workflow behavior.
- [ ] Run strict CI and verify RED.
- [ ] Implement static rule-based definitions.
- [ ] Run strict CI and verify GREEN.

### Task 6: Operator CLI for Workspaces and Jobs

**Files:**
- Modify: `ops/cli.py`
- Create: `tests/test_orchestration_cli.py`

**Interfaces:**
- Add `workspace add/list/show/disable` under an explicit profile.
- Add `job create/list/show/events` under an explicit profile.
- Commands write JSON only; secrets are never printed.

- [ ] Write failing CLI tests first.
- [ ] Run strict CI and verify RED.
- [ ] Add parser and command handlers while preserving existing commands.
- [ ] Run strict CI and verify GREEN.

### Task 7: Documentation and Full Regression

**Files:**
- Modify: `README.md`
- Modify: `docs/RUNBOOK.md`
- Modify: `docs/ROADMAP.md`
- Modify: `docs/WORK_STATE_PROTOCOL.md`

**Interfaces:**
- Document one-ingress/many-workspaces behavior, local SQLite durability, recovery rules, and current tunnel strategy.

- [ ] Run `npm run test:strict`.
- [ ] Run `npm run compile`.
- [ ] Confirm GitHub Actions CI success on the branch head.
- [ ] Verify no runtime database, local paths, secrets, or logs were committed.
- [ ] Review final diff against the design spec before closeout.
