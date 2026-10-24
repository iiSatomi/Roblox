# Boss Shop selected purchase: offline slice

The opt-in `bossShop` descriptor chooses only the exact item ID selected in
the Ember catalog. The saved native `BossTab` calls
`BossAction:InvokeServer("shopBuy", item, quantity)`. Gear always uses one;
crates may use one or ten. Planning requires a complete account-matched
catalog, an unlocked selected item, a current positive price, enough loose
plus bound Boss Tokens after the configured reserve and uncertain token
exposure, and a saved session send cap (default one). The UI remains off by
default. The selected list is the saved 15-item catalog, not a live discovery.

Preflight checks the quote, catalog key, unlock, custody, reserve and
checkpoint-injected attempt count immediately before dispatch. The checkpoint
increments the count before transport; an unconfirmed send still counts.
The one-owner broker retains its 45-second unconfirmed skip/cooldown, and the
spent quote remains uncertain exposure until reconciled. A positive reply
confirms only with a newer full Sync showing at least the quoted token debit
and an increase of the selected item by the purchased quantity. A negative
reply rejects unless contradictory state evidence exists.

This is fake-adapter logic only. Current server validation, wrapped transport
arguments, actual item custody (especially crates), and live response/state
shapes need a current client. No native send or production adapter was added.
Local evidence: 325 Python/Lupa tests, 12 Node tests, catalog check, nine
changed Luau files compile/analyze cleanly. The default distributed Ember
0.1.1 UI remains inert; functional/live parity stays 0/50.
