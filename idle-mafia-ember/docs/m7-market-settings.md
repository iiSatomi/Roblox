# Task 17 Market configuration checkpoint

October 26: all five Market controls now own their catalog preferences and Ember controls. `MarketSettings.project(featureId, scalarOptions, runState)` converts App's existing generic per-feature scalar mapping into the existing helper shapes; `BlackMarketTab:ProjectSettings` delegates it. There is no App-specific Market branch, reader, scheduler or sender in this slice.

| Activity | Projected helper settings | Required run facts |
| --- | --- | --- |
| `marketWatch` | `selection`, `watch`, `aging` | None |
| `marketSell` | `selection`, `custody`, `quote`, optional `withdraw`, `directList`, `followupList`; separate `listingAttempts` and `withdrawAttempts` | `transactionOpen`, `listingAttempts`, `withdrawAttempts` |
| `marketFlip` | `selection`, `watch`, `buyBudget`, `followupList`; separate `spent` and `attempted` | `transactionOpen`, `spent`, `attempted` |
| `marketRent` | `rent` and `attempted`; `rent.maxGoldSpend` is this activity's remaining run spend | `spent`, `attempted` |
| `marketManage` | `earnings` with `enabled` and `minEarnings` | None |

Every feature switch defaults off. Selection defaults to **Selected item** with an empty ID, which blocks projection until the user selects an ID or explicitly chooses **All eligible items**. Collection withdrawal is a separate default-off choice, with its own quantity and attempt limits. Sell/list, flip purchases/listing, and rentals have independent attempt limits; flip and rental spend limits default to zero and cannot borrow from each other. Missing or malformed run facts block projection; the future owner must supply counters retained across uncertain sends rather than reset them at each evaluation. Rental Gold reserve follows the existing native helper's total-Gold semantics; flip reserve protects loose Gold.

The catalog includes spare-copy/quantity protection, item/kind/rarity exclusions, recent-sales/units thresholds, sale net and flip margin/percent, demand coverage, RAP floor, undercut, aging review, Collection limits and independent spend/attempt limits. CSV text validation is opt-in on the exclusion fields only; it bounds text/tokens, trims whitespace, rejects empty tokens and invalid IDs, and the projector deduplicates them into maps. Unknown kinds and rarities fail closed. Reviewed saved `Config.MARKET.groupOfKind` plus `GameData` misc kinds supply the nine allowed kinds; `GameData.RARITY_NAMES` has nine rarities. These are the October 11 source files, not current-client assertions.

`BlackMarketTab:AllowsItem(projected, item)` applies explicit scope and exclusions before any research/custody selection. It proves no tradability or custody. The future reader/planner must call it, then use the projected helper settings with fresh native facts. Existing sale custody and flip preflight also receive the exclusion maps. Neither raw `watch` settings alone nor a successful scope check authorizes an action.

UI construction uses the existing Group, Input, Toggle and Dropdown APIs in a short schema-driven tab-owned loop. The reviewed workspace Ember reference was read, and pinned Ember source SHA-256 `c6ec2ad2ad732a2ed704d044fd068b685d7e6c2613f60a07c39316666576390a` was checked. Parent attempts to fetch current official docs/export were unavailable; no new Ember API was assumed. Offline UI doubles verify control/value binding, not actual Roblox rendering.

Verification:

- `python -B -m unittest discover -s tests -p 'test_market*.py'`: **176 run, 176 passed, zero skipped**.
- `python -B -m unittest test_ui_prototype test_simple_tab_modules test_all_tab_composition test_market_settings test_profile_store`: **83 run, 82 passed, one skipped**. This overlaps the Market suite; do not add the counts.
- `python -B tools/build_ui_prototype.py`: generated Catalog; `--check`: **Luau catalog matches JSON**.
- `python -B tools/build_release_manifest.py --preflight`: **243 unique modules**.
- Parent reviewed configuration shapes, explicit scope, independent zero budgets and scoped generic text validation. Nine new tests cover catalog→Settings/App→tab projection, actual helper acceptance, malformed fields/run facts, old-profile defaults and zero transport.
- Parent full regression after this slice passed on October 27: **913 run, 912 passed, one skipped**. Subsequent Family implementation passed **925 run, 924 passed, one skipped**. No commits, MCP, live actions, Gold/Stamina use or publication.

## Remaining Task 17 execution boundary

The configuration component is complete; whole-Market C/T and L remain unfinished. Research still needs current native catalog/browse/price/RAP ownership, fresh snapshot/custody input construction and bounded result presentation. Trade planning still needs the common item reservations against Crew/Collection, durable per-activity run counters and account transaction recovery owned by the runtime. Task 24 must connect those reads and reservations to the common arbiter.

Broker send hooks must persist the appropriate `Prepare*` and `MarkSending` transitions before any actual mutation dispatch, preserve one active request and the existing one-second/45-second behavior, and reconcile exact newer custody before another stage. The earned-payout ledger and complete tab runtime acceptance remain open. `MarketCallPlan` still maps only earned payout; buy/list/rent remain blocked. There is no safe tab-local bypass for the missing shared owner. Continue Task 18 Family under the integration-boundary/missing-fact rule, then return to Task 17 at Task 24 and before release acceptance.
