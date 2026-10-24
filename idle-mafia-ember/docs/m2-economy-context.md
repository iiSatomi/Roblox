# Read-only economic context

`EconomyContext` accepts an adapter-supplied decree, Family and discount
proof only when it belongs to the same account, city and captured Sync as
the shared context. It computes the ruling-Family exemption for
above-default penalties and exposes source-backed cash Shop, Crew hire
and per-item Market fee quotes. A quote key changes with the decree,
Family, discount or sale state so future purchase planners can invalidate
old quotes. Missing or malformed proof leaves the shared economic
context unknown; it does not authorize a purchase or sale.

The formulas come from saved native client 0.26.487.1 `DecreeRules`,
`Config` and `TerritoryBonusRules`. They are advisory until a current
native adapter supplies the proof and a live response establishes server
behavior. Neither the inert Ember build nor the fake runtime sends a
Shop, Crew or Market action from these quotes.

Local evidence: 216 Python/Lupa tests and 12 Node tests pass. The changed
Luau modules compile and analyze in both solver modes. Current client
state shape, live quote arithmetic and server acceptance remain open.
