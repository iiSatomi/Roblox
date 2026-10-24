# Boss Token Shop state: read-only adapter

The saved native `BossTab` totals bound and loose `boss_token`
inventory, reads fixed `BossStages.SHOP_BY_ITEM` quotes, and hides
locked crates. `BossShopState` accepts a complete native snapshot
and an account/capture-matched catalog proof from a future adapter.
It validates unique item IDs, item kind, positive integer prices,
explicit unlock state and bound/loose custody. An optional `Context`
reader exposes the result or an unknown reason; it never invokes
`BossAction`.

The saved buy call is `BossAction:InvokeServer("shopBuy", item,
quantity)`. This reader never spends tokens. The separate opt-in offline
action is documented in [Boss Shop purchase](m7-boss-shop-purchase.md).
Current native adapters and live server outcomes remain unverified.

Current offline evidence for the combined shop read/action path is in the
purchase document. Default Ember 0.1.1 remains inert.
