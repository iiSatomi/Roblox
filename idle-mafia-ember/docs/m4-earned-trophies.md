# Earned Gold-mastery trophies: offline claim slice

Saved client `0.26.487.1` `InventoryTab` lines 751–762 separately maps
item-consuming set trade-ins. Lines 1048–1052 and 3375–3399 call
`ClaimTrophy(itemId)` for a ready ordinary trophy. Lines 3750–3785 read
`derived.trophyReady` and the owned loose/bound inventory. `ItemsData` lines
2695–2721 identifies the Vespera `t_eldersignet` and Exiles
`t_grudgeledger` Gold-mastery trophies. These facts show the client action
surface, not an accepted server request.

`EarnedTrophiesState` requires a fresh matching complete Sync, current item
catalog and complete loose/bound Inventory and Collection custody. It
validates readiness and ownership and selects only those two
proven non-consuming IDs. `EarnedTrophies` is separately enabled and sends
one item ID. `EarnedTrophiesEvidence` requires a successful reply plus newer
complete Sync where that exact item leaves the ready list and appears as
exactly one owned copy. A reply alone stays pending. No set
trade-in, item consumption, display change or paid route is included.

October 26 Task 10: the saved `InventoryTab-21d7512031c8.lua` calls
`ClaimTrophy(item.id)` for ready locked trophies (lines 1030, 1064),
ready borders/backgrounds (line 1107), and an ordinary ready claim button
(line 2782). Its set-claim modal uses `CITY_SETS` and
`TROPHY_TRADE_INS` (lines 729–742, 782–835); those item-consuming IDs
remain excluded by `NativeTrophyCatalog`. The catalog-backed planner now
accepts any ready, unowned trophy/border/background without `tradeIn` or
`requiresItems`. It checks loose/bound Inventory and Collection copies;
the evidence evaluator requires the exact ID to leave the ready list and
appear as one owned copy in a newer full Sync. The call plan takes one
catalog-bound ID. This broadens the old two-ID limitation without allowing
set trade-ins as ordinary claims.

`TrophyFocusState` classifies current owned, ready, manual trade-in and
unready catalog rows. `TrophyGoalRequests` emits only a selected ordinary
route with its own default-off borrowing choice and has a read-only
ready/owned observer. Unsupported routes and consuming trade-ins emit no
request. It cannot send until Task 24 connects the common goal arbiter;
the claim toggle stays separate. A current-client exact claim outcome and
goal progress remain live-unverified. The distributed release is unchanged.
