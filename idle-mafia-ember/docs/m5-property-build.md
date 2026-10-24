# Ordinary Property builds: offline slice

The saved native 0.26.487.1 Property UI calls
`BuyProperty:InvokeServer(propId, optionalSlot)` and its normal Build
button omits the slot. `PropertiesState` reads a complete catalog,
replicated ownership and same-snapshot capacity/discount proof. Its
quote rounds `baseCost * 1.18^owned`, then applies the capped Territory
build discount and rounds again. The planner chooses one eligible
property under level, capacity, per-property ownership, purchase cap,
cash-to-keep and uncertain-cash limits. Best value compares income per
price; Most income and Next tier select by their named metrics. Custom
currently uses the same best-value ranking with its numeric limits.

Only the ordinary no-slot build intent is produced. Deletion, moving
and replacement are outside this path. A successful reply alone stays
pending; a newer complete Sync must show the exact selected owned
count rise by one. The offline registry and fake broker exercise the
path, but no production native transport or live server outcome is
verified.

Local evidence: 233 Python/Lupa tests, 12 Node tests, changed Luau
compilation and both analyzer modes pass. Current native capacity and
discount proof shape still needs a live adapter.
