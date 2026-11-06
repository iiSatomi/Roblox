# Free-charge-only Family Takedown attacks: offline slice

`FamilyBossAttackState`, `FamilyBossAttacks` and
`FamilyBossAttacksEvidence` add a separate opt-in intent for the
saved `FamilyBossAction:InvokeServer("attack")` call. It requires a
complete current-week, same-Family stage view, **zero held Tickets**,
at least one free charge, known native health/stamina, and a
positive conservative stage hit-back bound from a future adapter.
The planner keeps at least 50% maximum health and the saved native
hospital floor of 20 health after that bound, plus one stamina in
reserve. These are local safety rules; the current server hit-back
calculation remains unverified.

The checkpoint writes at most 25 sent hits per week/Family and five
native-server seconds between sends with the unresolved action
before dispatch. Unconfirmed sends count. Preflight repeats the
exact week, Family, stage, zero-Ticket and resource checks. A
positive reply confirms only after a newer same-week personal
damage increase of at least the reply damage and an increase in
free-charge use, with Tickets still zero. This slice never spends a
Ticket or buys a refill. The common 45-second unconfirmed/skipped
deadline and feature cooldown apply; a skip does not cancel a
server action. Confirmation also works when the hit advances to a
new stage and the completed stage no longer has an attack quote.

Offline evidence: 316 Python/Lupa tests, 12 Node tests, catalog
check and changed Luau compilation/analysis pass. The registry has
23 fake-adapter descriptors. Default Ember 0.1.1 remains inert;
native transport, actual response shape and live outcome are
unverified.
