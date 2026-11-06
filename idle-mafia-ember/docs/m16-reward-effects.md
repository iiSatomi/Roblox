# Rewards effect checkpoint — October 28

Rewards now requires its tab-owned `RewardEffects` module. A successful reply and newer claim marker are necessary but insufficient: the captured source-defined award must also appear in the matching full Sync. Pending and rate-limited replies cannot confirm concurrent claim markers.

- Group: recovered `Config.GROUP.incomeBonus=.1` and `PropsTab:133` establish a property-income multiplier activated by `groupBonus`. Its exact flag/modifier confirms the claim without an invented immediate Cash award. Membership freshness remains required.
- Ladder: fixed Cash, crate/item/Seal/Gold quantities, explicit bound custody, full Energy/Stamina capacity, fresh XP boost duration and mystery reply item plus actual acquisition are checked. Unspecified item origin permits an exact combined loose/bound increase; explicit bound rewards require the matching bucket. The claimed tier must equal the captured highest-level tier.
- Mystery: `DailyRewards.mysteryPool/mysteryRoll/mysteryReelItems` and `SafehouseTab:839` establish highest-level regular eligibility, premium prize identities and the one-crate fallback. `InventoryTab:2396` reads the reply's `mystery` field. The checker observes the returned item and custody; it does not predict randomness or purchase a crate.
- Weekend: the same trusted, read-only native rule is evaluated at capture and observation. This fixes the case where shared planning attached a weekend proof but the later raw observation lacked it.
- Monthly: source day overrides/default awards are copied and checked if the actual configuration enables the calendar. Saved build `0.26.530` has it disabled; the enabled test fixture does not enable it in the game.
- Queue: an unsupported ready rung is omitted so another supported ready reward can proceed.

Income-based Cash (`minutes`) remains unsupported until the actual payout rule is established. Fresh XP duration assumes application within the captured-to-observed server-time window; active-boost extension/stacking is unsupported. Those cases return a visible reason before any proposal. Concurrent unrelated balance changes can leave a real claim unconfirmed; this is preferable to inventing attribution. The existing 45-second unconfirmed rule remains unchanged.

Verification: 17 new focused Group/effect/pipeline cases; full suite 1080 run, 1079 passed, one external official-analyzer skip (31.110s). After making the effect dependency mandatory, composition/UI/runtime-focused checks ran 67 tests, 66 passed and the same skip. Catalog matched JSON; preflight scanned 261 unique modules. No live/MCP action, Stamina use, commit or publication. Current-client outcomes remain unverified.

Group tab-local C/T is complete; whole Rewards remains partial for income Cash/active XP rules and disabled-calendar current-client acceptance. Next: recovered Heist/Combat contracts and wiring ledger, then Task 24 shared ownership/integration.
