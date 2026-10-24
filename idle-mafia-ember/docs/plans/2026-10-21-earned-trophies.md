# Earned Gold-mastery trophy claims: offline slice

Saved client `0.26.487.1` `InventoryTab` lines 751–762 lists the item-consuming
set-trophy routes; lines 1048–1052 and 3375–3399 send `ClaimTrophy(itemId)`
for a ready ordinary claim. Lines 3750–3785 populate readiness from
`derived.trophyReady` and ownership from `inventory`/`inventoryBound`.
`ItemsData` lines 2695–2721 names the Vespera and Exiles Gold-mastery
trophies. These are client facts, not a successful server claim.

1. Add failing tests for matching fresh full Sync, explicit ready marker,
   current item catalog, zero owned copies, malformed arrays/counts and
   refusal of known consuming trophy IDs.
2. Implement one separately enabled `trophies` proposal. Initial allowlist
   contains only `t_eldersignet` and `t_grudgeledger`; never call the set
   trade-in remote or consume inventory.
3. Require successful reply plus newer complete Sync showing the selected
   trophy owned and no longer ready. Reply alone remains pending.
4. Wire the existing Trophies panel to the shared fake broker, run focused
   and full local checks, and document the unverified native transport and
   remaining earned-claim catalog.

**Status:** All four offline tasks implemented with a two-ID allowlist.
Synthetic fake-adapter tests pass; the full earned catalog and live behavior
remain open.
