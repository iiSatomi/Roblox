# Selected cash Shop offer — Task 05

Saved Shop UI calls `BuyShopItem(itemId, nil, quotedCash)` for the ordinary
cash offer. The hub reads the current rotation, native stock and current
cash quote, and yields when native Auto Buy is active. Gold purchases are
outside this control.

**Code/UI (C) and local integration (T): complete. Live (L): pending.**
On 2026-10-25, an App → quote producer → broker → injected native-adapter
scenario sent `BuyShopItem("w_a", nil, 120)` with arity three. A newer full
Sync in the same rotation showed the selected bought marker, one added
item, one bought-count increment and exactly 120 Cash spent. The producer
now accepts a finite fractional native clock such as `1220.25` while
rejecting the rotation boundary and mismatched stock/quote. Focused
Shop/call tests: 25 passed. No live call or GitHub update occurred.

For L, record a current full Sync with rotation slot, stock, selected
cash quote, Cash, owned count and native Auto Buy state; the exact call
and reply; then a newer full Sync in the same slot with the selected
bought marker, item grant and exact Cash debit. A reply alone is pending.
