# Sold-listing earnings collection

The saved `MarketTab` exposes already-earned `market.earnings` and the
tradable Gold balance at `inventory.gold_bar`. Its collection button
calls `MarketAction("collect", nil, nil, nil)` through a four-argument
wrapper. This action does not buy, list, remove or spend an item.

`MarketEarningsState`, `MarketEarnings` and
`MarketEarningsEvidence` add an opt-in offline descriptor. A complete,
identity-matched Sync must show positive earnings and a valid Gold
balance. The default minimum is one earned Gold; a larger local minimum
may be supplied. Preflight rechecks both exact balances immediately
before write-ahead/send. A positive reply remains pending until a newer
complete Sync shows earnings at zero and tradable Gold increased by the
exact prior earnings amount. Concurrent sales or another Gold change
can leave the action unconfirmed; the existing 45-second skip/cooldown
then applies and the checkpoint retains duplicate-risk exposure.

`FeatureRegistry` includes the descriptor and `NativeCallPlan` retains
the saved four-argument shape. No executor remote, real storage, UI
binding or live confirmation is connected. Market buy/list/rent paths
remain separate and unimplemented.
