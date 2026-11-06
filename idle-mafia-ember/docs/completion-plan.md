# Feature completion plan

Owner: coordinating agent. Coding agents: Sol 6.1, high reasoning.

## Acceptance criteria

Every catalog feature must have an implemented request/planning path, current
client integration, meaningful regression coverage, and a recorded live outcome
or an explicit unmet prerequisite. A blocked, skipped, or untested feature is
not counted as complete. UI-only success and syntax compilation do not count as
gameplay verification. Completion remains open until all required criteria pass.

## Work sequence

1. Review the current Ember dependency and repair/test the inert UI startup.
2. Inventory every feature against current implementation, disabled contracts,
   runtime assembly, live prerequisites, and evidence requirements.
3. Repair current-client bindings, beginning with Prestige; regression-test
   identified defects before changing production logic.
4. Integrate feature groups in isolated changes. The manager owns integration,
   release assembly, and the single live-test queue. Agents do not compete for
   account state or send concurrent gameplay requests.
5. Test each available feature in game with bounded actions, before/after state,
   exact replies, and cleanup. Record unavailable seasonal/account prerequisites
   explicitly and continue independent work.
6. Recheck shutdown, restart recovery, profiles, pacing, ownership, and UI state.
7. Run the full offline suite, live compiler checks, independent code review,
   and coherent release-pin verification before calling a release ready.

## Ownership

| Workstream | Owner | First deliverable |
| --- | --- | --- |
| Ember dependency and UI | ui_completion | Dependency review, tested adapter/builder changes |
| Feature coverage | feature_inventory | Complete catalog-to-runtime status matrix and next code slices |
| Prestige binding | prestige_completion | Root cause, regression and narrow binding fix |
| Live tests and integration | manager | Single-client test ledger, current state and release assembly |

## Starting evidence

Recovery baseline: 626 Python tests passed, one optional analyzer skip,
110 subtests, 12 preview checks. All 297 Luau files compiled in Potassium.
The last live inspection found game 0.26.646.1, changed Ember SHA-256, and no
Prestige controller binding. These are starting observations, not fresh results
for this completion session.

## Current status

In progress. User authorized execution and in-game function testing. Existing
feature guards and exact outcome evidence remain required. No completion claim
will be based solely on the absence of console errors.
