# Earned Gold-mastery trophies: offline claim slice

Saved client `0.26.487.1` `InventoryTab` lines 751–762 separately maps
item-consuming set trade-ins. Lines 1048–1052 and 3375–3399 call
`ClaimTrophy(itemId)` for a ready ordinary trophy. Lines 3750–3785 read
`derived.trophyReady` and the owned loose/bound inventory. `ItemsData` lines
2695–2721 identifies the Vespera `t_eldersignet` and Exiles
`t_grudgeledger` Gold-mastery trophies. These facts show the client action
surface, not an accepted server request.

`EarnedTrophiesState` requires a fresh matching complete Sync and current
item catalog, validates readiness and ownership, and selects only those two
proven non-consuming IDs. `EarnedTrophies` is separately enabled and sends
one item ID. `EarnedTrophiesEvidence` requires a successful reply plus newer
complete Sync where that exact item leaves the ready list and appears in
owned loose or bound inventory. A reply alone stays pending. No set
trade-in, item consumption, display change or paid route is included.

The existing Trophies panel can display shared fake-broker status. The
distributed inert 0.1.1 bundle remains unchanged. Local evidence:
160 Python/Lupa tests, 12 Node tests, catalog-generation check, changed
Luau compilation and both analyzer modes pass. Remaining earned
trophies/cosmetics, runtime data shape, server outcome, native transport,
durable storage and live UI are open.
