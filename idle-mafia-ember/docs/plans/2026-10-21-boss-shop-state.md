# Boss Token Shop read-only state

Status 2026-10-21: implemented and optional Context integration
verified by two new offline tests; 296 Python/Lupa tests total.
The purchase action remains open.

The saved `BossTab` reads `BossStages.SHOP_BY_ITEM`, totals
`inventoryBound.boss_token + inventory.boss_token`, uses
`BossStages.crateUnlocked`, and sends
`BossAction:InvokeServer("shopBuy", item, quantity)` only on a
purchase. First add a read-only validated quote/custody view.
Require a complete native snapshot, account/capture-matched current
catalog proof, unique item IDs, positive integer prices, explicit
crate unlock state, and valid bound/loose counts. Do not infer that
displayed affordability proves the server will accept a purchase.
Keep action, durable per-load cap, item selection UI and evidence
for a later separately verified slice.
