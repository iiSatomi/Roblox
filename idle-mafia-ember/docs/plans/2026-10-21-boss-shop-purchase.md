# Selected Boss Shop purchase

Status 2026-10-22: offline selected-item descriptor implemented and
locally checked; production transport and live outcome remain open.
The saved `BossTab` calls
`BossAction:InvokeServer("shopBuy", item, quantity)`. Gear uses
quantity 1; crates offer 1 or the native maximum 10. Crates require
their native stage unlock. The request can spend the current Boss Token
balance, so the planner must use a selected item, selected crate quantity,
an explicit token reserve, and a per-session send cap. A positive reply
alone is not purchase confirmation.

Implement in this order:

1. Extend the Boss Shop view with the exact selected catalog entry, current
   loose/bound token totals, item custody, unlock status, and a stable catalog
   key. Unknown rows remain unavailable.
2. Add saved `bossShop` controls for item ID, crate quantity (1 or 10), token
   reserve, and maximum sends per session. Keep it disabled by default. Gear
   quantity is always 1; crate quantity is capped at 10.
3. Add a pure planner requiring the selected item to exist, remain unlocked,
   fit the token reserve, and have enough quoted tokens. Use only the exact
   native item ID and quantity in the intent.
4. Persist sent-attempt count before dispatch, including unconfirmed attempts,
   and require local usage proof during preflight. Action keys must not permit
   retries to evade the configured cap after a restart.
5. Capture token and selected-item counts before dispatch. Confirm only after
   a positive native reply, newer revision, a matching token decrease at
   least equal to the quoted total, and the selected inventory increase by
   at least the requested quantity. Handle crate reward routing only if the
   saved native state has a complete bounded inventory representation.
6. Register the descriptor and UI settings; add fake-broker tests for locked
   crates, gear quantity, crate quantity, reserve, changed quote, cap/restart,
   rejection, and exact post-purchase evidence. Run the catalog and Luau
   checks.

Evidence anchor: saved `BossTab-d7d6eed84b44.lua` renders native `SHOP_BY_ITEM`,
checks `BossStages.crateUnlocked`, and invokes `shopBuy` at the saved UI
handlers. `BossStages-bfbcb42c74e6.lua` sets `SHOP_CRATE_MAX` to 10. Server
validation, reward inventory deltas, wrapped transport arguments, and live
outcomes remain unverified; do not claim the offline action is live-ready.
