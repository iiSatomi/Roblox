# Engine and Jobs Implementation Plan

> For implementation: work through these tasks in order, one reviewed slice at a time. This plan tracks source work; a checked task needs its stated evidence.

**Goal:** Turn the clean inert Ember prototype into a reliable modular application, then deliver ordinary Jobs as its first confirmed gameplay function.

**Architecture:** Native readers create validated snapshots. Pure feature planners propose one action at a time to a single broker. The broker owns admission, pacing, confirmation, uncertainty and recovery; the UI displays desired settings and effective status. A version-consistent loader assembles reviewed modules before any gameplay starts.

**Tech stack:** Luau, Ember 3.0.0 as currently reviewed, Python/Lupa fake-clock tests, official Luau compiler/analyzer, a commit-pinned GitHub release.

## Global constraints and evidence

- Read `skills/idle-mafia-hub/SKILL.md`, `docs/AGENT_HANDOFF.md`, `docs/Ember-UI-Reference.md` before changes that touch the game or Ember UI. Recheck current Ember source/API before changing UI behavior.
- Read `../place-audit-2026-10-20.md`, `../native-reuse-audit.md`, and the matching entries in `../native-reuse-decisions.json` before defining a game action. Saved client source is evidence of client behavior only. Runtime response and server acceptance are unverified.
- Send only ordinary authorized actions through the supported native dispatch boundary. Saved Jobs UI contains `DoJob:InvokeServer(job.id)` and MWClient wraps Remotes through `RemoteLink`; confirm the live invocation contract before a gameplay build. No entitlement spoofing or private handshake constants.
- One active hub request, at least one second between sends, quarter-second planner checks. An unconfirmed mutation is skipped at **exactly 45 seconds after first send**, with duplicate-risk logging and a **45–300-second affected-feature cooldown**. A late response cannot clear a newer owner or create a second success. A skip is not server cancellation.
- Heists → Favors → Operations → other eligible work. An active matching native controller owns its domain; unknown activity is a blocker, not permission to send. Jobs stays disabled until the first vertical slice is complete.
- Feature switches are desired state. Effective execution requires fresh state, permissions, resources, native ownership and a healthy broker. Import is paused. Stop/unload prevents new sends and preserves uncertain records.
- No new gameplay outcome is called confirmed from a remote return alone. Use exact state/reply evidence per action. Do not run the legacy hub and the new sender together.
- Keep `.private/` game extracts, dependency source, account files, compiler binaries, and assembled executor files out of publication. Dependency redistribution and loader capabilities need resolution before a public runnable release.

## File and dependency map

All paths below are relative to `idle-mafia-ember/`. The listed names are new source ownership boundaries, not legacy imports. Existing `src/App.luau`, `src/storage/Settings.luau`, `src/ui/EmberAdapter.luau`, `src/ui/Catalog.luau`, and `preview/catalog.json` remain the UI baseline.

```text
saved client evidence → contracts/native fixtures
  → engine contracts + clock → broker admission → 45s recovery
  → native context/ownership + scheduler → lifecycle/checkpoints
  → release manifest/loader validation
  → Jobs reader + planner → Jobs confirmation + App status → live evidence
```

Each task changes at most a focused handful of source/test files. Tests use a fake clock and fake transport; no offline test sends a real game action. Run from the repository root with the bundled Python/Lupa environment recorded in `../ember-ui-prototype.md`. For a new `test_*.py` file, use `& $py -m unittest discover -s idle-mafia-ember/tests -p test_*.py -q` with a quoted concrete filename. Compile every newly added `.luau` module with `.private/luau-compiler/luau-compile.exe --null` and analyze applicable source with both solvers. Existing 26 UI checks and 12 Node checks are regression gates when shared UI/settings code changes.

## M2: engine and release foundation

### Task 1: Fix the actual shared and Job contracts

**Status:** Offline source contract and synthetic fixtures recorded; live wire,
response and state-confirmation shape intentionally remain open.

**Files:** create `docs/m2-native-contracts.md`, `tests/fixtures/job-snapshots.lua`; update `docs/roadmap.md` and `docs/parity.md` only where source evidence changes a requirement.

**Work:** Record the current native paths for job catalog, replicated player/job/energy state, Auto Jobs entitlement **and actual activity**, client action wrapper, server-time/buff/economy context, and any response fields visible in the saved client. Mark every unknown field and server-side behavior explicitly. Define fixture cases for available job, locked job, insufficient energy, active native controller, unknown controller status, stale state, and changed catalog. Record the profile/control key mapping for Jobs and the action's exact proposed confirmation evidence. Do not guess wire-only fields from UI arguments.

**Acceptance:** Every fixture field is traceable to a current saved-client source anchor or labelled test-only; unknown runtime response fields remain unresolved. The contract distinguishes `proposed`, `sent`, `returned`, `confirmed`, `rejected`, and `skipped/unconfirmed`. **Verification:** rerun `node idle-mafia-ember/tools/check_native_audit.mjs idle-mafia-ember/.private/place-2026-10-20`, and inspect fixture parsing with the new focused test in Task 2.

### Task 2: Define snapshots, proposals, records and the fake clock

**Status:** Implemented and covered by four focused contract/clock checks.

**Files:** create `src/engine/Contracts.luau`, `src/engine/Clock.luau`, `tests/test_engine_contracts.py`.

**Interfaces:** `Contracts.validateSnapshot(raw, expectedSession)` returns a copied validated header or a reason; `Contracts.validateProposal(raw, snapshot)` returns a copied action proposal or a reason; `Clock.new(nowFn)` exposes monotonic `Now()`. Proposal identity includes session/account/place/release, feature, action key, snapshot revision, flat intent and resource exposure. Do not expose mutable raw state to planners.

**Steps:** add failing tests for bad account/place/release, missing/stale revision, nonmonotonic fake time and duplicate action keys; run them and observe failure; implement the smallest contracts/clock; rerun focused tests and Luau compilation. **Acceptance:** malformed or stale inputs cannot become sendable proposals. No Roblox service is needed to run these tests.

### Task 3: Admit and pace one request

**Status:** Implemented behind injected fake transport; five broker checks cover
single ownership, preflight, spacing, session identity and reply-only evidence.

**Files:** create `src/engine/Broker.luau`, `tests/test_engine_broker.py`; use Task 2 contracts.

**Interfaces:** `Broker.new(clock, transport, journal, policy)`; `Broker:Offer(proposal, snapshot)` returns admitted/wait/blocked with a reason; `Broker:Tick(snapshot)` handles due work; `Broker:Status()` returns one active owner and next send time. Transport has only `Send(proposal, onReturn)` and is injected by tests. Broker does not ask a planner to mutate state.

**Steps:** first fail cases for two simultaneous offers, repeated action key, stale preflight and a second send at 0.999 seconds; then implement admission and send-time spacing; rerun focused tests and compile. **Acceptance:** at most one admitted request, minimum one-second send interval, and a return value alone never marks a mutation confirmed.

### Task 4: Resolve, skip and fence uncertainty

**Status:** Implemented in memory and covered by four recovery checks. Durable
uncertainty/checkpoints belong to Task 6; no live transport is connected.

**Files:** modify `src/engine/Broker.luau`; create `src/engine/Journal.luau`, `tests/test_engine_recovery.py`.

**Interfaces:** `Broker:Observe(snapshot)` matches action-specific state evidence; `Journal:Record(event)` keeps bounded immutable events with session/action identity; `Broker:Tick(snapshot)` skips the current mutation at first-send time + 45 seconds and cools down only its feature.

**Steps:** fail scenarios at 44.999, 45.000 and 46 seconds, a late callback after a newer owner starts, duplicate evidence and an unrelated eligible proposal after skip; implement state transitions and fences; rerun tests and compile. **Acceptance:** one skip event exactly at deadline, duplicate risk visible, feature cooldown 45–300 seconds, other work resumes, late result cannot release or double-count the newer action. Preserve the skipped record for reconciliation.

### Task 5: Add native contexts and feature arbitration

**Status:** Partial offline slice. A fresh native header, separate entitlement
and saved activity for Jobs/Shop/Crew Auto Roll/city Boss Auto, conservative
unknown ownership, resource reservations, strict Heists/Favors/Operations
precedence and equal-priority rotation have eight focused tests. Partial Sync
cannot assert a controller activity. Current economic/buff derivation, shared
read budgets and native runtime shape validation remain open; do not treat this
task as complete. See [owner evidence](../m2-native-owners.md).

**Files:** create `src/game/Context.luau`, `src/engine/Scheduler.luau`, `tests/test_engine_scheduler.py`; update fixtures as evidence requires.

**Interfaces:** `Context.new(contracts):Read(rawState, expectedSession, now, maxAge)` reports freshness, native server time, resources, entitlement and activity separately; economics/buffs currently report unknown. The adapter supplies `native.fullSync=true` only for a complete replicated Sync, never for a partial tick. `Scheduler:Choose(context, desired, brokerStatus, now)` returns an ordered candidate and wait reason; it never sends. The ownership state is `active`, `inactive`, or `unknown` for each relevant native controller.

**Steps:** fail active/unknown Auto Jobs, stale resources, Heists/Favors/Operations precedence, waiting board fairness, same-resource conflicts and background-read budget cases; implement pure arbitration; rerun tests and compile. **Acceptance:** no competing Job proposal when native activity is active or unknown; no feature can consume another feature's reserved or uncertain resources.

### Task 6: Session lifecycle and local recovery

  **Status:** Offline core implemented and tested. Session pause/resume/stop/close,
  write-ahead unresolved-action ledger, scoped rejoin recovery, conflict blocking,
  fail-closed storage errors and duplicate initialization have 14 fake-storage
  tests. The actual executor storage adapter, cross-process lease/atomicity,
  App composition and native AFK flow remain open; this is not a live durable
  recovery claim.

**Files:** create `src/engine/Session.luau`, `src/storage/Checkpoint.luau`, `tests/test_engine_session.py`; modify broker only if its session interface requires it.

**Interfaces:** `Session:Pause()`, `Session:Resume()`, `Session:Stop()`, `Session:Close()` gate proposals; `Checkpoint:Save(record)` and `Checkpoint:Load(account, place, release)` use an injected storage adapter. Desired settings remain separate from effective execution.

**Steps:** fail tests for paused import, stop during pending work, failed write, corrupt checkpoint, account/place/release switch, duplicate initialization and teleport/rejoin with an uncertain action; implement lifecycle and conservative reconciliation; rerun tests and compile. **Acceptance:** no new send after stop/unload; uncertain exposure is retained or visibly blocks retry if durable storage fails. Observe the native AFK refresh flow before adding any fallback idle routine.

### Task 7: Package a consistent inert release

  **Status:** The pure manifest validator and loader are implemented offline
  with 17 focused tests. Metadata is checked before fetch; bytes are pinned by
  one commit and SHA-256, then every module compiles before any executes and
  App starts once. Fetch/cache/compiler/hash are injected fake adapters. A real
  `manifest.json`, bootstrap/runtime adapters, Ember distribution and executor
  verification remain open; no runnable remote release exists. See
  [loader boundary](../m2-loader.md).

**Files:** create `manifest.json`, `src/loader/Manifest.luau`, `tests/test_release_manifest.py`; add `Loader.luau` and `tests/test_loader.py` only after the manifest validator passes.

**Interfaces:** manifest pins one commit and each module's path, SHA-256 and dependency list. `Manifest.validate(manifest, bytesByPath)` rejects missing/wrong hashes, cycles and duplicate module IDs before any module executes. `Loader.start(fetch, cache, compile, manifest, dependencies)` prefetches, verifies, compiles and initializes once before constructing App.

**Steps:** fail tests for partial download, wrong hash, cycle, compile failure, duplicate load, cache recovery and mixed commits; implement a pure validator first, then loader; rerun focused tests and compile all modules. **Acceptance:** no partial startup or duplicate sender; no mutable-branch module fetch during gameplay. Verify actual executor HTTP/hash/cache primitives before shipping this loader. Resolve Ember source distribution or use a permitted reviewed dependency path; do not publish private dependency bytes by default.

## M3: ordinary Jobs vertical slice

### Task 8: Read Jobs state and propose one eligible action

  **Status:** Partial offline slice. `JobsState` and `Jobs` are pure modules
  with 13 focused synthetic tests. Complete native Sync, current catalog/rules,
  native ownership, level, energy, mastery discount, exact selected ID, reserve
  and stable action identity are handled. Balanced/XP/Cash/Mastery/Selected job
  have deterministic provisional policies; Custom and city-specific selection
  block until input schemas and native rules are verified. No transport adapter,
  App setting binding or live result exists. See [Jobs planner note](../m3-jobs-planner.md).

**Files:** create `src/game/JobsState.luau`, `src/features/Jobs.luau`, `tests/test_jobs_planner.py`; use the Task 1 fixtures.

**Interfaces:** `JobsState.read(nativeState, context)` returns a fresh normalized catalog/player view or reason; `Jobs.propose(view, settings, reservations)` returns one Task 2 proposal or a blocker. The proposal identifies the stable job ID, expected cost and state revision; the transport adapter maps it through the verified native dispatch seam.

**Steps:** fail locked/insufficient energy/city/mastery/level-up/catalog-change/active-controller cases, the supported policy choices and a shared reserve; implement a pure reader/planner; rerun tests and compile. **Acceptance:** no guess from missing fields, no paid-controller call, no action when native Auto Jobs already owns the domain.

### Task 9: Confirm Jobs and connect the UI

**Status:** Offline fake-adapter path implemented. `JobsEvidence` captures the
selected Job completion baseline before send and requires a matching identity,
successful reply, newer full Sync/revision and increased completion count to
confirm. `JobsRuntime` injects clock, transport, storage and identity, starts
paused, then composes JobsState/Jobs → Scheduler → Session/Broker. Optional
`JobsRuntime` injection into App displays pending, confirmed, rejected and
uncertain states on Jobs only; no production adapter, timer or live send exists.
Focused evidence/runtime/UI flow tests and the full 105-test suite pass. The
inert 0.1.1 executor bundle is unchanged. See [Jobs evidence](../m3-jobs-evidence.md).

**Files:** create `src/features/JobsEvidence.luau`, `tests/test_jobs_flow.py`; modify `src/App.luau`, `src/ui/EmberAdapter.luau` and focused UI tests after rereading the Ember reference.

**Interfaces:** `JobsEvidence.capture(proposal, beforeRaw)` and `evaluate(proposal, beforeHeader, afterRaw, reply, baseline)` return confirmed/rejected/pending with exact supporting fields. App accepts an optional injected JobsRuntime and exposes desired/effective/waiting/uncertain status on the Jobs panel. The broker remains the only sender.

**Steps:** fail the full settings → proposal → send → delayed state → confirmation path, rejection, late replication, disable/stop, missing evidence and renderer exception; implement the integration; rerun engine/Jobs/UI tests and compile every release module and generated fallback if present. **Acceptance:** Jobs is the only gameplay feature available in this build; its panel never calls a remote directly or reports success on send alone.

### Task 10: Prove the runnable Jobs slice and record evidence

**Status:** Local proof and limits recorded; current native transport/runtime
contract, executor storage, production packaging and live UI/action evidence
remain open. Do not label Task 9's fake send as a working game action.

**Files:** update `docs/parity.md`, `docs/roadmap.md`, root `docs/AGENT_HANDOFF.md` and a focused Jobs evidence note. Modify code only for verified defects.

**Work:** Recheck current client/tool schemas and place/account/build, choose a naturally eligible low-cost Job, capture exact before/after replicated state, response and broker journal, then stop. If no current client is available, record Jobs as locally tested and leave live confirmation open. Separately inspect UI navigation, sidebar scroll, F8, focus and cleanup without a gameplay send.

**Acceptance:** source, local tests, rendered UI and live outcome have separate labels; one confirmed Job must show matching identity and resource/progress change. A blocked or ambiguous result remains blocked/uncertain. Review the resulting diff, update the 50-ID parity row only as evidence permits, then continue M4–M11 one independently configurable feature slice at a time.

## After Jobs: full function coverage

The [roadmap](../roadmap.md) M4–M11 checklists and [parity register](../parity.md) remain the complete implementation queue: earned claims/Operations/skills; money/property/prestige; Heists/Favors; city/global Bosses and Takedown; player Combat; Crew/gear/inventory; Shop/Market/Family/Territory; then goal controllers. For each action use the same sequence: current native contract → separate permission/settings → pure decision → broker request → exact confirmation/recovery → UI state → focused tests → scoped live evidence. Supporting profiles, diagnostics, AFK behavior and release work are tracked in M2/M12. No row is complete merely because its switch exists.

**Checkpoint after Tasks 1–4:** fake tests prove single ownership, one-second spacing and exact 45-second uncertainty handling; no gameplay send exists. **After Tasks 5–7:** active native owners block competing work, stop/restart recovery is conservative, and a complete verified release initializes once. **After Tasks 8–10:** Jobs has end-to-end local proof, an observable UI status, and a separately labelled live result if a current client is available. Reassess the next milestone only after these checks.
