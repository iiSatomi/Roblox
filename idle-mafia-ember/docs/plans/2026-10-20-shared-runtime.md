# Shared Multi-Feature Runtime: Offline Plan

**Goal:** Route Jobs, Operation starts and ready Operation collections through one broker and checkpoint ledger using injected state, storage, clock and transport.

**Architecture:** A feature descriptor supplies pure reader, planner and action-specific evidence modules. One runtime composes Context, Scheduler, Session, Checkpoint and Broker. It observes any sent owner first, then plans enabled features from one fresh snapshot, offers one scheduler choice and sends only through Broker. Feature errors become visible blockers while other features may continue. Existing `JobsRuntime` remains for its focused compatibility tests until the shared path is proven; production must use only one runtime instance.

## Task 1 — Shared coordinator

**Status:** Implemented with six focused fake-adapter tests and single-broker
Jobs/Operation start/collection flow.

- Add failing `tests/test_automation_runtime.py` with two/three real feature descriptors and fake storage/transport.
- Implement `src/engine/AutomationRuntime.luau` with `new(deps)`, `Pause`, `Resume`, `Step`, `Status`, `Stop`, `Close` and no game APIs.
- Verify one sender, collection before starting, response-only pending, exact state confirmation, 45-second skip/cooldown, uncertainty exposure, disable/stop and failure isolation.

## Task 2 — UI and release composition

**Status:** Optional App/Ember status integration passes the UI double. The
default distributed 0.1.1 prototype stays inert; real release composition is
still open.

- After engine tests pass, add optional App injection for the shared runtime and per-feature status for Jobs/Operations/Collect. Preserve the default inert Ember prototype.
- Keep real transport, atomic executor storage, live state adapter and production manifest separate until their capabilities and current contracts are verified.
