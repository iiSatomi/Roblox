# Inert Ember UI implementation plan

Authorized 2026-10-20 when the user resumed the approved recode. This is the
next M1 slice, not the gameplay release. Use the existing 25-tab/55-control
design. Jobs, city Bosses, Shop and Crew automation will use ordinary native
action requests; paid-controller unlocking is no longer a development task.

**Goal:** Render the agreed controls in actual Ember with a fresh, testable
settings model and lifecycle, without any gameplay dispatch or account I/O.

**Architecture:** A generated catalog feeds a pure settings model. An Ember
adapter owns handles and a small application owns local commands, profile
validation, pause/stop and teardown. The application receives its modules and
Ember explicitly. A local builder embeds reviewed Ember bytes into a private
executor file; no network or dynamic downloads are present in that file.

**Technology:** Luau modules using Lua-compatible syntax; Python unittest and
Lupa for offline behavior; existing Node preview tests. Test doubles validate
the adapter contract, not Roblox rendering.

## Constraints

- All implementation is fresh and under `idle-mafia-ember/`.
- No legacy production imports; no live MCP, purchases or gameplay requests.
- No automatic profiles, persistence, controller activation or hidden callbacks.
- Preserve false booleans, validate enums/numbers, reject unknown fields and
  conflicting gear owners atomically. Profile application always pauses.
- Stop clears desired activity; choosing another switch cannot release Stop.
- Native and custom gear remain mutually exclusive, including profile imports.
- Ember bulk SetValues/GetValues are not a profile serialization boundary.
- Configure storage off before controls. Explicit false close-revert targets,
  F8 visibility, reduced motion, a scrollable sidebar and teardown guards.
- Keep actual browser/Roblox rendering unverified until observed. Do not retry
  the previously blocked browser routes.
- M2 retains one sender, 1s minimum/0.25s planning, exact 45s uncertainty deadline
  and feature cooldown; this UI contains no sender.

## Files and interfaces

- `tools/build_ui_prototype.py`: generate `src/ui/Catalog.luau` from the existing
  JSON, check generation drift, and optionally assemble the private executor
  file from exact SHA-256-reviewed Ember bytes.
- `src/storage/Settings.luau`: `new(catalog)`, `Validate(profile)`,
  `Commit(values)`, `Set(key,value)`, `Snapshot()`, `Pause()`, `Resume()`, `Stop()`.
  Snapshots contain schema/versioned scalar preferences, never session state.
- `src/ui/EmberAdapter.luau`: `new(ember,catalog,callbacks)`, `Render(model)`,
  `ApplyValues(values)`, `Destroy()`. Validate setters and roll back UI changes
  before accepting an import; freeze editing if rollback fails.
- `src/App.luau`: `start(dependencies)` returns local command/profile/session
  operations. Constructor failure destroys the partial UI; unload fences all
  queued callbacks and clears selected activities.
- `tests/test_ui_prototype.py`, `tests/ember_double.lua`: exercise actual new
  modules with a deliberately asynchronous Ember double and no Roblox/network.

## Ordered work

- [x] Write failing model, import, callback and adapter lifecycle tests.
- [x] Run them and record the expected missing-module failures.
- [x] Generate the catalog and implement the smallest model/adapter/application
  satisfying these tests; test each slice before broadening.
- [x] Verify UI refusal rollback, construction failure, delayed callbacks,
  partial profiles, false hydration, gear exclusion and stop/unload.
- [x] Check dependency bytes and static API anchors; record license uncertainty
  without publishing third-party source. Build only the private executor file.
- [ ] Run new offline tests, existing preview tests, generation/parse/whitespace
  checks. Document evidence and remaining rendering/loader/gameplay work.
- [ ] Review the scoped diff, publish recode changes on the existing draft PR
  branch, and update the shared handoff.
