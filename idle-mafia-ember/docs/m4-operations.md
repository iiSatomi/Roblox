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

## Current bounded acceptance - October 31, 2026

The actual tab/App now supports independently selected IDs and optional inclusive required-level, duration-in-hours and primary-crate-item rarity bounds. Unknown/empty selected lists hold; bounds do not silently clamp. The original Best chest and catalog-order Highest tier goals remain, alongside quoted net Profit/hour, XP/hour, shortest duration and the reviewed legacy Balanced heuristic. Balanced normalizes eligible quoted net profit, XP and primary rarity plus expected-count/100; these rankings do not guarantee rewards. Primary crate rarity is copied from native item metadata, never inferred from the contents' bucket average.

Saved ordinary starts recapture the exact original baseline and reconcile only a matching stored reply, one added target slot, exact cash debit and unchanged prior slots. New session revisions may restart at zero; account/place/release and nonolder native server time remain required. Unknown or mismatched state stays held without replay. Collection keeps its separate switch and existing current-slot/effect checks.

Focused evidence: 32 actual App cases, 22 existing Operation cases, four native-catalog cases and the shared UI/import suites. The final shared suite result is recorded once in tasks/todo.md. Cases include disabled/inverted bounds, missing rarity, selected-list changes before emission, sent confirmation after settings change, rejection, unload, unknown saved outcomes, forged baselines, wrong scope and failed cleanup persistence. No current-client or live outcome is confirmed.

The current official [Input documentation](https://rbx.lol/docs/ember/controls/input) was rechecked for the reused text-input contract; the reviewed dependency pin is retained. Live renderer and native concurrency acceptance remain pending. For live acceptance, capture exact native calls/replies and newer full Syncs preserving unrelated slots and quoted cash. No live trial is authorized in this continuation.
