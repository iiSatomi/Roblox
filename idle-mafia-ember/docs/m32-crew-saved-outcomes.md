# Crew saved outcome reconciliation — October 28

The actual runtime now asks a feature-specific recovery hook to interpret its complete saved checkpoint. Crew requires the original scoped proposal/baseline, actual saved native reply, stable owner and durable cycle totals, plus exact newer state. It can observe while all features are off and clear the matching generic checkpoint without sending any request. A proven empty slot keeps its funded continuation; a completed hire keeps the spent allowance. Missing reply, changed Cash, an unrelated member change or uncertain native effect retains custody and sends nothing.

The two-store terminal window is covered: if transaction cleanup succeeds but generic checkpoint cleanup fails, reload can match the original exact hire effect with its persisted cycle usage and finish only that checkpoint cleanup. It cannot turn an unrelated empty slot or generic success reply into a completed cycle. Recovered prepared requests still have no emission arm.

Saved reconciliation has a distinct `reconciled_saved` event and separate runtime recovery status. A same-session 45-second skip remains `skipped_unconfirmed`; its original duplicate-risk history and cooldown remain even if later saved evidence settles its held exposure. Activity describes saved observation without reporting another native request or counting the skip as a normal confirmation.

Coroutine tests exposed/fixed two write races: another tick entering the same first preparation, and a newer tick trying cleanup while an earlier checkpoint cleanup save yielded. Broker marks an in-progress preflight; runtime serializes recovery cleanup and fences post-yield work against unload/stopped state and stale snapshots. Existing current request/lease ownership still surrounds direct invocation.

Full **1227 run, 1226 passed, one external official-analyzer skip**, 32.087 seconds. Catalog matches JSON; **273 modules**; scoped whitespace passes. All evidence is offline. No MCP/live action/Stamina/spending/commit/publication; published entry remains `9da6d31`.

Next: explicit paused preview/confirm for known-unsent prepared Crew records and separately proven rejected hire cleanup. It must never discard a sent unknown outcome, restore consumed budget automatically or invoke a replacement. Retain the static availability warning until this recovery review and remaining acceptance are verified; automatic review previously rejected removing it. Other Crew features, current-client source acceptance, cross-release migration and the remaining Task 24 owners/goals remain open.
