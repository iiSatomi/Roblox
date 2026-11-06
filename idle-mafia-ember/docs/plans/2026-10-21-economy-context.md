# Source-backed economic quote context: offline slice

Status: implemented and checked offline; live proof/quotes remain unverified.

Saved `0.26.487.1` `DecreeRules` lines 190–215 exempts ruling
Family members from above-default penalty percentages. Current
`Config.DECREES` ranges: Shop/Hire -25..25 (default 0), Market 5..15
(default 10). `Config.hireCost` rounds to nearest cash unit;
`TerritoryBonusRules.shopPrice` applies capped Territory discount,
global sale and decree before nearest rounding; `Config.marketFeePerItem`
uses permille, permanent-shop 70% share and minimum fee 1.

1. Read a same-snapshot, same-city normalized decree/Family/bonus view
   supplied by a future native adapter. Unknown identity or percentages
   fail closed; do not silently grant ruling-Family exemption.
2. Calculate effective Shop, Hire and Market percentages using the
   source rule, then expose pure current quote helpers for base cash
   Shop price, Crew hire and per-item Market sale fee.
3. Test exemption, discounts, exact rounding, malformed/stale facts and
   quote-key changes. This is advisory read-only context; purchase and
   sale planners still need exact current transport/state contracts.
