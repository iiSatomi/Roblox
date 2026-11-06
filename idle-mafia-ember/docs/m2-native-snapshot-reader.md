# Saved native snapshot boundary

`NativeSnapshotReader` is a read-only staging boundary. The saved
`MWClient` wires `Sync.OnClientEvent` to `State.set(payload)`; it also
calls `State.set` after Income, Pools, Auto Job and Auto Roll ticks.
`State.onChanged` and `sinceSync()` therefore do not prove that a full
server Sync arrived. An integrator must call `ObserveSync(payload)` only
from the observed `Sync` event and may call `ObserveChanged(payload)`
for later State changes. Changes before Sync cannot establish readiness.
Later tick/State-change captures carry `fullSync = false`; only an
actual observed Sync capture carries `fullSync = true`, so a tick cannot
stand in for post-action full-Sync confirmation.

Accepted data is copied immediately, then copied again for `Capture()`
so planners cannot mutate saved State or the reader's copy. Capture
exposes the copy as `native` for existing `Context`/feature readers and
includes the bound session identity, a local increasing revision,
monotonic capture time and the event-specific `fullSync` flag. Malformed, cyclic or
oversized data fails without replacing the last good view. The event
timestamp can become stale; the broker still applies its snapshot-age
gate. Individual feature readers must validate required fields and
current catalog values before offering actions.
`Close()` clears the copied account view and rejects delayed callbacks;
the future event integrator must also disconnect its subscriptions.

No `Sync` subscription, `State` module resolution or executor bridge is
connected to the distributed UI. Event ordering, complete payload shape
and live behavior remain unverified. Offline tests cover no-Sync refusal,
copy isolation, revision/capture time, failed-change retention,
`Context` owner readiness and close fencing.
