# Updated place audit — native 0.26.487.1

Date: 2026-10-20. Evidence: user-supplied place file, inspected as inert data. No game source was executed and no live client or gameplay action was used for this audit.

## Baseline and evidence quality

- Input: `GameSave_73897506680154.rbxl`, 1,855,869 bytes.
- SHA-256: `a45286db115f2696000b859e8435439620c853bb33179f66a7c78029a504bca6`.
- `GameVersion` returns **0.26.487.1**. The legacy hub targets **0.26.253** from October 11.
- The newest bundled UpdateNotes entry is **0.26.454**, October 19. Release-note version and actual client version differ; neither should be substituted for the other.
- Extracted **260 unique nonempty script-name/source-hash records** from 278 script-name instances. This includes Roblox core/player modules and is not a count of game features or server scripts.
- **40 of the 48 script records in the prior selected extraction have changed bytes**; all prior selected names are present. Renumbered decompiler variables and presentation changes contribute to those byte differences. This is not proof of 40 changed remote contracts.
- Many other modules were not included in the earlier selected extraction. Their presence in this complete extraction does not establish their introduction date. Monthly rewards, for example, are newly identified missing hub coverage, not asserted to be newly released on October 20.
- Raw extraction and local comparison files are kept under `.private/place-2026-10-20/`, ignored by this project's `.gitignore` and excluded from publication. Public evidence contains only metadata, source locations and summarized findings.

`native-evidence-2026-10-20.json` records source hashes and verified textual anchors. Line numbers below are physical lines in the extracted file, not decompiler comment line numbers. Decompiled code is evidence of client intent; missing code, runtime response shapes, actual server acceptance, and state replication still require their own checks.

## Changes that alter the recode design

| Area | Source-backed finding | Required plan change |
| --- | --- | --- |
| Native automation | Jobs exposes `autoJob`, `autoJobCurrent`, `autoJobWaiting` and `derived.autoJobs`; Shop exposes `autoBuyRules` and `derived.autoBuy`. Native controllers use `AutoJobAction`/`AutoBuyAction`. | Detect native activity before hub-owned Jobs/Shop planning. Show the owner and wait rather than running competing loops. Native gamepass purchase, entitlement bypass and automatic takeover are excluded. Add optional owned-controller integration only after exact contract and permission review. |
| Crew native rolling | Crew has multi-slot native Auto Roll targeting in addition to normal hire/dismiss. | Preserve the hub's distinct normal reroll implementation, but yield occupied/rolling slots. Never require the native entitlement for ordinary hub hires or use native entitlement-only methods without ownership. |
| Shared economics | City decrees change cash Shop price, hire cost and Market selling fee; ruling-Family members have penalty exemptions. Native fee helpers use integer/permille rounding and minimum per-item fees. | Add a shared fresh economic context before Shop, Market and Crew code. Reserve/debit the exact current quote. Family membership, ruling Family, decree revision and grace/rotation changes invalidate proposals. Avoid fixed fee percentages. |
| Gold Shop | The current Shop source now shows the previously missing request arguments: cash uses item ID, nil rotation argument and quoted cash; Gold uses item ID, rotation slot and quoted Gold. | Replace the old “unknown arguments” blocker with “current client call observed; server response/confirmation pending.” Gold remains a separate OFF-default permission with reserve, quote and attempted-spend cap. No Gold purchase is authorized by this audit. |
| Collection tiers | Config now lists thresholds **1 / 10 / 100 / 1,000 / 5,000 / 10,000 / 25,000**, with multipliers 1–7. | Every gear, surplus-deposit and Market withdrawal calculation must use the full native tier table. Protect the highest achieved tier, including the two new thresholds. |
| Collection item identity | Collection totals aggregate base IDs using the native item-key splitter across both bound and unbound deposited stacks. Native UI supports depositing worn profile cosmetics, with the release notes saying they remain equipped. | Model display selection separately from loose item custody; avoid reserving an unnecessary loose cosmetic copy or double-counting one item's stat contribution. Keep exact variant/binding identity for transfers. Verify upgraded/bound transaction behavior before enabling it; do not infer permission for bulk operations. |
| Crew consumable healing | Crew healing now has an item path using the member's stable `healId`/member identity, injury timestamp and a henchman-specific sequence. Stamina healing also supplies identity/injury facts. | Separate stamina healing from owned health-item healing, with distinct preferences/caps and bound-first policy. Revalidate exact member identity instead of trusting a reused array index. Recall cooldown is not automatically equivalent to an injury that consumables can heal. |
| Consumable timing | Config specifies separate **3-second player** and **3-second henchman** cooldowns. `ConsumableRules.readyIn` reads separate ready-at fields using native server time. | Remove the old assumed 10-second shared cooldown. Keep independent sequence/clock state, while both request types still use the one-request broker and one-second outbound minimum. |
| Playtime claims | Seven rungs include a 90-minute personal XP boost, 120-minute Mystery reward and 180-minute bound Consumables Crate. Rewards vary by level tier; the 90-minute rung becomes **3 Gold Bars on weekends** in this snapshot. | Resolve reward kind before claiming, retain saved claim tier, and show temporary-benefit/refill conditions. Do not promise the XP boost every day or automatically open an awarded crate. Mystery rewards require observed actual contents. |
| Monthly rewards | `DailyRewards.monthlyState` and `MonthlyCalendar` expose a native UTC day/month claim path, up to 30 days per month, using `ClaimMonthly`. | Add separately configurable earned monthly claim coverage. Test month changes, February length, first eligible claim and duplicate proof. No catch-up purchase or time manipulation. |
| Combined buffs | `GlobalBuffKinds` combines administrator, decree and daily/weekend effects. Its helpers use maximum selection for several overlapping values rather than multiplying/summing all visible badges. | Introduce one current buff context and use the native composition rules. Include personal XP effects where present in native derived state; do not double count a weekend and admin 2X bonus. |
| Operation timers and rewards | `OpsTab` uses `derived.operationRate` and `OperationCardArt` displays catalog crate/bonus-crate chances. | Rank with current known rate and source-described drops. Ready collection requires replicated slot readiness; do not treat a UI timer estimate or a probability as a guaranteed reward. |
| Global Boss expansion | Catalog includes Hellfire, The Judge and Violet Vale (`hellfire`, `judge`, `cat`); rules support pending starts, time-based boss HP decay, varying medals and public/private event access. | Resolve event catalog dynamically; distinguish scheduled/live/settled, actual player damage and timed decay. Enforce native access; never activate a private/test event from the hub. Drop chance is not guaranteed and remaining HP loss is not proof this player attacked. |
| Global Boss auto-claim | October 13 notes describe automatic settlement at the next event/close. The actual automatic settlement path is server-side and absent from this extraction. | Reconcile already-claimed rewards and event transitions without replaying a claim. Keep automatic settlement as documented intent until exact state evidence proves it; do not credit rewards merely because the next event appeared. |
| Takedown damage | Updated Config includes current per-stage hit-back percentages and HP scaling fields. | Derive health safety from current helpers/fields, not the old formula or the notes' “less damage” wording. Keep free-charge/Ticket, weekly identity and stamina safeguards. |
| Gear/catalog growth | New VIOLET, CONTEMPT, JACKPOT and IVORY set definitions and additional event/crate gear exist. Rarity metadata includes the ninth tier. | Use native items/set catalogs and full rarity selectors; protect binding and restrictions. Read-only loadout comparisons must label reachable versus theoretical changes. Do not hand-maintain a small old set list. |
| Safehouse | Native catalog adds The Sovereign Hotel at level 200 and The Founder's Estate at 215. | Catalog-derived cap, unlock and progression preview; preserve explicit user limits. Prestige and highest-ever-level rules must not be collapsed into current level alone. |
| Territory V3 | Eight city catalogs contain **852 unique district IDs**. City-scoped ownership/lockouts, old-ID successors and duty/residency remapping are native concepts. | Replace the old flat-map assumption before station/residency/Family goal code. Scope caches and requests by city/district, migrate saved district selections with a preview, and reject ambiguous old IDs. |
| Territory bonuses | `TerritoryBonusRules.select` takes the best **two districts per bonus kind**, then caps the result; current derived bonuses are authoritative. | Compute marginal residency/holding value against active/inactive bonus selections. Do not sum every owned district or assume moving to the largest nominal district always helps. |
| Territory defense/recovery | Tier 7/8 garrison capacities are 250/300; capture/shipment shields, city eviction/relocation/reclaim locks and fortifications affect readiness and recovery. | Check current capacity, own stable member IDs, district health/ownership/shield/lock status and clinic/recovery effects before station or recall. Keep defense and combat/training resource ownership coordinated. |
| Seasons | `SeasonRules.SEASONS[1]` starts at **2026-10-21 19:00 UTC (3 PM New York)** and lasts **14 days**. October 19 notes describe four-week seasons. | Display configured season timing rather than hardcoding the notes' four weeks or midnight start. Add read-only season/history/rank tracking first; server response validation remains pending. |
| Fortifications | Native keys are Barricade, Guard Posts, Back-Alley Clinic and Apartment Block, each up to level 5; costs include Gold/energy and rival sabotage. Config unlock is **2026-10-20 17:00 UTC (1 PM New York)**. | Add read-only effects/countdown coverage and incorporate effects into relevant safety facts. Gold donations, construction, sabotage and leader actions remain separate future scope with distinct permissions, not part of ordinary station automation. Source timing is not proof the live server has unlocked. |
| Event Shop | Native `EventShopAction('buy', key, 1)` spends bound Event Medals. `paidMedals` tracks paid-origin medals; restricted-account crate eligibility uses only the free-earned balance. | Add watch/preview first and an independent selected-item medal buyer as a later OFF-default feature. Honor native region/origin restrictions, price/open-window/reserve/attempt limits, and item/medal proof. Medal purchase never enables crate opening or Robux purchasing. |
| Mail, mutiny and leadership | The native client contains a mailbox, offline gifting, Family mutiny and expanded leadership/decree actions. | Surface read-only/manual availability if useful. Do not add automated outgoing gifts, recipient messages, votes, leadership changes, evictions or Family policy spending from this recode authorization. |
| Native dispatch | MWClient passes remotes through its native wrapper; visible call-site parameters are not necessarily raw RemoteFunction parameters. | Establish the supported native dispatch seam and exact response contracts before gameplay. Never publish/copy live handshake values, invent prefix arguments, bypass native access checks, or infer raw calls from a decompiled UI expression alone. |
| Network latency | Recent notes describe busy-server heist/collect performance fixes, not guaranteed latency. | Preserve the exact user-selected 45-second unconfirmed policy and late-result fencing. Do not shorten it because the notes say processing improved. |

## Native source anchors

All anchors refer to `.private/place-2026-10-20/<name>-<hash-prefix>.lua`; full hashes and per-finding anchors are in the accompanying evidence JSON. No raw source is published.

| Area | Source locations inspected |
| --- | --- |
| Versions and release history | `GameVersion` line 5; `UpdateNotes` lines 7–62 for October 11–19 entries |
| Native automation ownership | `JobsTab` lines 935–960, 1952, 2414; `AutoBuy` lines 80–110, 897; `CrewTab` lines 1606–1638 |
| Quotes and economics | `ShopTab` lines 982–1000, 1325–1357; `Config` lines 535–549, 2861–2925; `DecreeRules` lines 296–335; `MarketTab` fee calculation call sites |
| Collection identity and thresholds | `Config` lines 2015–2057; `CollectionTab` lines 75–101, 720–750; `InventoryTab` worn-cosmetic menu; October 15 notes |
| Healing and clocks | `Config` lines 1609–1612; `ConsumableRules` lines 46–71; `HenchmanHealingRules` lines 13–54; `CrewHealModal` lines 470–560; `ServerClock` lines 51–64 |
| Rewards and buffs | `Config` lines 754–888; `DailyRewards` lines 23–180; `MonthlyCalendar` lines 265–286; `DailyBuffRules` schedule/weekend helpers; `GlobalBuffKinds` mult/amount functions |
| Event rules | `GlobalBossRules` lines 6–23, 134–200, 306–359; `GlobalBossTab` lines 1494, 2127, 2177; `EventShop` lines 277–315; `EventShopTab` lines 249–309 |
| Cities and bonuses | Eight `Catalog_<city>` files; `CityMaps` lines 5–46, 94–116, 198–281, 312–384; `TerritoryBonusRules` lines 6–14, 26–99 |
| Seasons and fortifications | `SeasonRules` lines 8–32, 58–147; `SeasonView` SeasonAction read sites; `FortifyRules` lines 6–32, 115–146; `Config` lines 1361–1419 |
| Native dispatch | `MWClient` RemoteLink initialization and wrapped Remotes context; `RemoteLink` public wrapping interface. Runtime/private values deliberately omitted. |

## Revised build order

1. Refresh the design and setting/feature dispositions using this evidence. Keep the 50-ID old-hub parity baseline separate from newly proposed features.
2. Build an inert Ember prototype around the revised page map and sample states for native ownership, taxes, rewards, event timing and stale city data.
3. Build server-time/economic/buff/native-ownership contexts and prove the broker with fake transport before any gameplay adapter.
4. Rebuild existing personal features as complete slices. Add low-risk monthly claims and separate Crew item healing in their reward/inventory milestones.
5. Add read-only city/decree/season/fortification/Event Shop views before transactional Market/Territory automation. Develop optional medal buying only after its own contracts and limits are proven.
6. Keep broad shared-Family, social, premium and destructive additions out of automatic migration. Review exact current contracts before any newly authorized action.

## Verification still required

- Decompiler omissions and runtime shapes for each request/reply; current live build may differ from this saved client.
- Actual Ember source/API retrieval, dependency review and rendering. This place save does not contain Ember.
- Profile/account migration and all legacy setting dispositions, including display-only/dormant options.
- Real native automation state persistence, actual spend/consumption, delayed replication and external/manual changes.
- Collection worn-cosmetic custody, exact upgraded/bound transfer behavior and reachable loadout evidence.
- Native server-side auto-claim, live season/fortification activation, region restrictions and real Event Shop outcomes.

These are explicit evidence gates, not invented working toggles or completed feature claims.
