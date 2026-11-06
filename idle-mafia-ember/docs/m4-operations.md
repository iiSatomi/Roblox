# Operations: offline ordinary-action slice

Saved client `0.26.487.1` provides the current client action surface:
`OpsTab` computes the 1–4 slot count from highest level and the actual
`derived.fourthSlot` value (lines 291–306), sends a catalog ID to
`StartOperation` (lines 360–380), sends the current active-array index to
`CollectOperation` (lines 536–550), and shows collection only when replicated
`remaining <= 0` (lines 870–926). The catalog fields and crate bucket odds
are in `GameData` around lines 1475–1786 and 2889 onward. These are saved
client facts, not verified server validation or live wire captures.

`OperationsState` accepts only a fresh matching complete Sync, validates the
active array and current catalog, and copies cash, level, respect and native
slot entitlement. Ready runs still occupy slots. `OperationsStart` requires
separate enablement, an unlocked Operation, a free slot and cash after reserved
and uncertain exposure. “Highest tier” currently means the latest eligible
entry in the native catalog order, a deterministic progression preference
rather than a server tier. “Best chest” ranks chance-weighted expected bucket
rarity for primary and bonus crates; missing odds block that policy only. No
crate is promised by a probability.

`OperationsCollect` is separately enabled and selects only a run whose
replicated `remaining` is nonpositive. Its intent retains the current active
array index and selected catalog ID. The future transport must recheck this
index immediately before dispatch. `OperationsEvidence` and
`OperationsCollectEvidence` require a successful reply plus matching newer
full-Sync active-run addition or removal. Reply alone is pending. A manual
concurrent action on the same Operation could remain an attribution ambiguity;
no live result is claimed. Instant finish, vouchers, cancellation, paid slots
and purchases are outside these paths.

`AutomationRuntime` now demonstrates Jobs, Operation start and collection
through one injected broker/session/checkpoint. It starts paused, checks
enabled feature proposals from one snapshot, and uses the scheduler's
Heists → Favors → ready collection → Operation start → other priority.
Unconfirmed actions skip at first send +45 seconds, remain in the ledger and
cool only their feature; unrelated eligible work may continue. App can
optionally display all three feature statuses, but the distributed 0.1.1 UI
still has no runtime injection, game transport, timer or production storage.

Local evidence on 2026-10-20: 131 Python/Lupa tests, 12 Node tests, Luau
compilation and old/new analyzer checks pass. The Operations tests use fake
clock, storage, transport and synthetic full Syncs. A real adapter, current
server response shape, durable storage, live Ember behavior and exact game
outcomes remain unverified. No new release bundle or GitHub update was made.
