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
count rise by one, the exact quoted cash debit and unchanged other
Property counts. Send-time checks also require the selected quote to
match the planned cash and a complete, unique catalog; ownership over
native capacity blocks enrichment. The offline registry and fake broker exercise the
path, but no production native transport or live server outcome is
verified.

Local evidence: 233 Python/Lupa tests, 12 Node tests, changed Luau
compilation and both analyzer modes pass. Current native capacity and
discount proof shape still needs a live adapter.

## Current bounded acceptance - October 31, 2026

The tab/App adds an independent selected-ID list and optional inclusive required-level bounds. Empty, unknown or inverted choices wait instead of falling back. Highest tier ranks required level, then income, then the existing deterministic tie breakers. Existing value/income/next-tier goals and all cash, capacity, ownership and quote checks remain. This scope produces ordinary builds only; deletion, moving and replacement remain excluded.

Exact saved-build recovery recaptures the stored quote/ownership baseline, requires the stored native reply and matching account/place/release, accepts a restarted session revision only with nonolder native server time, and checks the exact selected count/cash change plus unchanged other property ownership. Unknown outcomes retain exposure without replay. Bounds or selection changes before emission cancel the known-unsent purchase; changes after send do not discard evidence.

Focused evidence: 23 actual App/native-adapter cases plus the existing 12 Property cases and shared UI/import coverage. Cases include boundary/inverted/disabled bounds, stale selections, Trophy borrowing constraints, rejection, unload, exact saved outcomes, forged baselines, scope/time mismatch and unrelated ownership changes. Final shared-suite evidence is in tasks/todo.md. Current-client capacity/discount, native concurrency, source/release and live acceptance remain pending; no purchase occurred.
