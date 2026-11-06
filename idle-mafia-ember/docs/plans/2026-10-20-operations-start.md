# Ordinary Operation Start: Offline Slice

**Goal:** Produce one validated ordinary `StartOperation` proposal from a fresh complete Sync and current catalog, without sending a game request.

**Evidence:** Saved client `0.26.487.1`: `OpsTab` lines 291–306 computes 1/2/3/4 slots from highest level and `derived.fourthSlot`; lines 360–380 sends `StartOperation` with catalog ID; lines 982–1005 checks free slots, level, respect and cash. `GameData` lines 1475–1786 defines catalog fields. This is client behavior only, not server acceptance.

**Boundaries:** Keep collection separate. No instant finish, vouchers, cancellation, paid slot unlock or estimated-time readiness. Catalog ordering is not proof of a server tier; an offline policy may use it only as an explicit deterministic preference. Missing or malformed inputs block.

## Task 1 — Read state

**Status:** Offline reader and four focused state tests pass.

- Add failing `tests/test_operations_state.py` for fresh/full Sync, slot limits, catalog consistency, level/respect/cash, duplicates and malformed active runs.
- Implement `src/game/OperationsState.luau` as a pure copier/validator using `Context` header and resource facts. It returns a small view with eligible metadata and open slot count.
- Run focused tests, Luau compile/analyzers.

## Task 2 — Propose one start

**Status:** Offline planner and action evidence pass synthetic tests; shared
fake-broker integration is in `AutomationRuntime`. No actual send exists.

- Add failing `tests/test_operations_planner.py` for disabled/unsupported policies, unlock and cash reserves, full slots, stable action identity and deterministic choice.
- Implement `src/features/OperationsStart.luau` returning a broker-compatible proposal, without transport.
- Run the full offline suite and update roadmap/handoff. Do not claim a working gameplay feature or publish a bundle.

## Task 3 — Separate ready collection

**Status:** Offline ready-only planner, exact-index baseline and matching
active-run removal evidence pass synthetic tests. Current runtime index and
server outcome remain unverified.

- Add failing `tests/test_operations_collect.py` for ready-only current-array selection, index/identity, disable, malformed state and confirmed/ambiguous outcomes.
- Implement `src/features/OperationsCollect.luau` and `OperationsCollectEvidence.luau`. Keep the `collect` feature separate from `operations`; never use UI timer estimates or paid instant-finish calls.
- A future transport must re-read the full active array at dispatch and pass the current native array index. Reply plus matching replicated disappearance is required for confirmation; unchanged or ambiguous state remains pending.
