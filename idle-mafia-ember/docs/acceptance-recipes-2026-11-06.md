# Bounded acceptance recipes, 6 November 2026

These are proposed settings for the current 55-feature catalog, not new live acceptance claims. Read current `docs/completion-live-2026-11-06.json` for observed outcomes. Source: `preview/catalog.json`, `src/storage/Settings.luau`, and the owning planner/evidence modules. This document contains no account identity or native source.

Pause before setting controls, disable all other ordinary features and goal borrowing, assert every `Host:Set(key, value)` succeeds, then enable only the chosen recipe. Use the manager's single-attempt gate and exact pre-invoke validation. Do not reset allowances, replace profiles, clear unknown actions, or create fake prerequisites. Keep the original unresolved Operation custody and every other unresolved receipt. Original Shop request 27 has now reconciled through normal recovery in the manager-tested fbf working build, with zero new attempts and request high-water unchanged at 33; do not resend it. A setting cap is an absolute durable cap; use verified effective historical usage, including imported carry, rather than assuming zero.

The initial twelve recipes already supplied cover `jobs`, `collect`, `chests`, `playtime`, `crew`, `crewGear`, `crewSort`, `collectionDonate`, `bank`, `withdraw`, `properties`, and `shop`. Current readiness must be read again; prior inventory or resource counts are not current guarantees. CrewSort now uses a bounded SHA256 action key with its full exact roster baseline retained; use the reviewed patched source before retrying.

## First: free claims and reports

Each row uses its exact scalar key. All listed booleans are real booleans, not text.

| Feature | Host:Set updates | Prerequisite and maximum effect |
|---|---|---|
| Contract entries | `contracts.enabled=true` | One first ready daily/weekly row, unchanged current reset and native row identity. No spending. No row selector; inspect the proposed period/index before invoke. |
| Contract bonuses | `bonuses.enabled=true` | All rows in that native period already claimed, bonus unclaimed, reset safely future. One bonus; daily can refill Energy. Separate from entry claims. |
| Earned Trophies | `trophies.enabled=true` | One native-ready catalog-proven non-consuming reward. Item-consuming trade-ins remain manual. No item selector; inspect proposed target ID. |
| Group reward | `groupBonus.enabled=true` | Native unclaimed flag plus verified current membership proof no older than 30 seconds. One no-argument claim; no joining or membership changes. |
| Market earnings | `marketManage.custom.minEarnings=1`, `marketManage.enabled=true` | Positive replicated earnings. One collection of all earnings, exact earnings-to-loose-Gold evidence. No listing, buying, rental or spending. |
| Cosmetics | `cosmetics.policy="Balanced"`, `cosmetics.enabled=true` | One loose background/border giving nonnegative Attack and Defense with positive combined gain. Existing bound cosmetic custody anywhere blocks unverified origin precedence. No purchase or Collection withdrawal. |
| Contract goal report | `autoContracts.custom.borrowJobs=false`, `autoContracts.custom.borrowOperations=false`, `autoContracts.custom.borrowCollect=false`, `autoContracts.custom.borrowHeists=false`, `autoContracts.custom.borrowHires=false`, `autoContracts.enabled=true` | Current goal catalog/rows. With ordinary features off there is no gameplay call. Inspect runtime `Status().goals.autoContracts` for current requests/exclusions. This tests reporting, not goal progress. |
| Trophy goal report | `trophyFocus.custom.goalId="t_fb_spyglass"`, all five `borrowJobs`, `borrowProperties`, `borrowOperations`, `borrowBanking`, `borrowHeists` fields under `trophyFocus.custom` set false, `trophyFocus.enabled=true` | Use this ID only if still present in the current native catalog; a known owned target can report `owned`. `trophies.enabled=false` and ordinary routes off prevent a claim. Inspect `Status().goals.trophyFocus`; do not claim progression. |

Territory report:

```lua
Host:Set("territoryWatch.custom.cityId", "jade_harbor")
Host:Set("territoryWatch.custom.districtId", "jade_harbor_053")
Host:Set("territoryWatch.custom.showSeason", true)
Host:Set("territoryWatch.custom.showFortifications", false)
Host:Set("territoryWatch.enabled", true)
```

Use those selectors only when the current catalog/map still confirms them. Requires current Family and coherent map plus district read. Zero mutations; season data may legitimately be absent. Enable `showFortifications=true` separately only for an explicit extra report and current read support. Read reports can be accepted as reports without claiming any territory acquisition.

Market report:

```lua
Host:Set("marketWatch.custom.scope", "Selected item")
Host:Set("marketWatch.custom.selectedItemId", "w_pipe")
Host:Set("marketWatch.enabled", true)
```

Keep `marketSell`, `marketFlip`, `marketRent` disabled. Retain default minimum sales/units and coverage rules. Native query uses the exact selected item and one bounded cumulative page budget. Native base-item searches can return upgraded siblings such as `w_pipe@6`; preserve every exact returned item ID and price. Any upgraded variant in the bounded response withholds all Watch/Flip/Sale pricing, including base-item quotes. The displayed report states the variant count and that pricing/trading are withheld; pagination completion is separate from pricing completion. A partial, stale or small report likewise provides no executable sale/flip quote. An owned item is not required to read its market. Replace the selector only with another exact catalog-eligible ID after inspection.

## One bound restorative

Prefer a genuinely depleted Energy pool after a Job; do not spend resources just to manufacture damage. Current Playtime rewards may already have filled the pool.

```lua
Host:Set("restoratives.policy", "Small first")
Host:Set("restoratives.custom.healthPolicy", "Off")
Host:Set("restoratives.custom.energyPolicy", "Small first")
Host:Set("restoratives.custom.staminaPolicy", "Off")
Host:Set("restoratives.custom.healthBelow", 0)
Host:Set("restoratives.custom.energyBelow", 100)
Host:Set("restoratives.custom.staminaBelow", 0)
Host:Set("restoratives.custom.minUsefulPercent", 10)
Host:Set("restoratives.custom.custody", "Bound only")
Host:Set("restoratives.enabled", true)
```

Requires one real bound Energy restorative, useful recovery at least 10% of maximum, ready cooldown and native sequence. Maximum consumption: one bound item, zero Gold/Cash. The planner chooses the item; no item-ID selector exists. A Health-only variant uses `healthPolicy="Small first"`, `healthBelow=100`, `energyPolicy="Off"`, `energyBelow=0`, and otherwise the same controls. Use only if deficit meets the configured useful threshold.

## Crew selectors

Crew injury tests require an actually injured home member with stable heal ID, no training/rolling/duty conflict. Do not create an injury. Only one healing recipe should be enabled.

| Feature | Exact settings | Maximum and limitations |
|---|---|---|
| Stamina heal | `crewHeal.custom.staminaReserve=S-1`, `crewHeal.enabled=true`, where `S` is a fresh integer current Stamina value | Pre-invoke require `intent.expectedCost==1`; one Stamina and one injury-time reduction. Native formula can quote more than 1 for longer injuries; reserve blocks those at unchanged S. Reserve alone is not a permanent cost cap when Stamina regenerates. |
| Item heal | `crewHealItems.policy="con_bandages"`, `crewHealItems.custom.minRemaining=300`, `crewHealItems.enabled=true` | One selected bandage, bound first then ordinary. There is no bound-only toggle: require `intent.fromBound==true` at the manager's gate if ordinary item use is not intended. Native injury must have at least 300 seconds remaining. |
| Training | `crewTrain.custom.minRarity=4`, `crewTrain.custom.targetLevel=1`, `crewTrain.custom.maxCost=100000`, `crewTrain.custom.maxConcurrent=1`, `crewTrain.custom.cashReserve=1000000`, `crewTrain.enabled=true` | At most 100,000 Cash and one training start, keeps one available home member. Current reviewed Config's rarity-4 first level is 100,000 Cash/5 minutes. No eligible rarity-4 level-0 member means no action. One bounded training start is recorded as confirmed in the live ledger; the reviewed working-tree settlement also accepts an owned positive result with the same original member and exact timer or completed level on a strictly later native clock. This certifies the training outcome, not an exact wallet debit. |
| Empty-slot hire | `crewHire.policy="street"`, `crewHire.custom.maxCost=12500`, `crewHire.custom.cashReserve=1000000`, `crewHire.custom.maxAttempts=A+1`, `crewHire.custom.maxSpend=U+12500`, `crewHire.enabled=true` | One existing empty native slot, at most 12,500 Cash including permitted native hire tax. `A/U` are trusted effective attempt/spend totals. Current build-654 source-owned `Config.hireCost`/`DecreeRules.pctFor` quote is required and rechecked immediately before dispatch; changed decree, roster, family, city, stale clock or retired source blocks. No dismiss or replacement. Rolling roster and duplicate name/rarity rows still block. The reviewed working-tree alternative can settle passive-Cash cases only from the owned positive reply and exact replicated new member with a real new healId, unchanged other roster, and strictly later native clock. It does not estimate a wallet debit or waive the original quoted-spend allowance. |

For CrewSort, one call can reorder many movable rows. Player/deployed/rolling rows stay pinned; changed gear/member identity does not count as a confirmed sort. For CrewGear, absence of positive gain is prerequisite-unavailable, not proof of a swap. Bulk Crew AutoEquip `changed=false` is a valid native no-op and is not improved gear.

## Family contributions

Fresh actor-bound Family information and native personal counters are mandatory. `A/U` below mean the trusted effective current lane attempt/spend totals after carry, not a zeroed new session. Set maxAttempts to `A+1` and runBudget to `U+amount`, within the actual catalog bounds. Disable other Family spenders.

| Feature | Exact controls before `.enabled=true` | Maximum |
|---|---|---|
| `familyCash` | `familyCash.custom.amount=100`, `.reserve=1000000`, `.runBudget=U+100`, `.maxAttempts=A+1` | 100 Cash; native minimum must still be at most 100. Imported historical spend must remain counted. Positive personal donated-Cash counter is required. Prefer after Cash settlement review. |
| `familyStamina` | `familyStamina.custom.amount=1`, `.reserve=S-1`, `.runBudget=U+1`, `.maxAttempts=A+1`, `.selectedPerk="enforcers"`, `.selectedPerks=""` | 1 Stamina. Exact native selected track exists, not maxed, and +1 fits its next-level cost. Fresh S; shared reservations remain authoritative. |
| `familyGold` | `familyGold.custom.amount=1`, `.reserve=G-1`, `.runBudget=U+1`, `.maxAttempts=A+1`, `.allowNativeGoldPool=true` | 1 total native Gold, where G is freshly verified loose+bound minus existing custody. This explicit permission allows either/split native pool debit; no origin priority is asserted. If false, bound Gold must be zero. |

Family Takedown claims use only `familyBossClaims.enabled=true`; require a genuine owned eligible reward and exact current challenge/run identity. One claim, no attack/consumption. A familyless saved personal claim is supported only when its reviewed claim continuation proof is current. Do not invent a dead boss, weekly token, or personal entitlement.

## Territory mutations: wait for a reviewed exact target

Station settings: `station.custom.mode="Station"`, `.districtId=<exact current district ID>`, `.memberSlot=<verified stable home slot>`, `.minHome=2`, `.minGarrison=1`, `.maxStationed=D+1`, `.maxAttempts=A+1`, then `station.enabled=true`. D is the current count of own deployed plus uncertain members; A is the trusted effective attempt count, including any imported floor (canonical0 plus imported1 needs an absolute cap2 for one new send). Requires Family-owned district, native capacity, stable selected identity and home reserves. An unidentified unselected home bystander can be preserved as an exact bounded observation, but cannot be selected, counted toward home defense or assigned member custody. Unidentified deployed or pending rows still block. No Cash/Gold spend, but one member becomes unavailable at home. Do not move a member already held by recovery/training/another owner. The manager should require exact member key and district in its gate. Recall is a different `.mode="Recall"` continuation requiring typed imported-receipt validation plus current native lease continuity and exact queued ownership; binding a source alone is not permission.

Residency settings: `residency.policy="Selected bonus"`, `residency.custom.districtId=<exact current ID>`, `.selectedKind=<exact native kind>`, `.maxRentPct=0`, `.minSharePct=1`, `.allowReplace=false`, `.allowRequests=false`, `.maxAttempts=A+1`, `residency.enabled=true`. This accepts at most one zero-rent open admission with a verified positive same-kind effective bonus comparison. The native view's explicit `status="none"` is now supported; it does not override the zero-rent cap (a 1% quote still blocks). No automatic search for another district. Existing residence, full/closed/request-only district, missing derived bonus totals, or no verified improvement correctly blocks. Never replace an existing residence for an acceptance tick.

## Market mutations: prerequisite-gated

Rental: `marketRent.custom.maxAttempts=A+1`, `.maxGoldSpend=U+Q`, `.goldReserve=G-Q`, `marketRent.enabled=true`. Q is the exact current native one-period quote, A/U durable rent counters, G fresh total Gold after custody. Pre-invoke require quote Q equal the reviewed amount and periods1. One native period, at most Q Gold from either/split pool. It deliberately blocks if derived MarketShop is active or current lease has at least120 seconds remaining. Do not pay to extend an unexpired shop merely to obtain a success.

Selling: `marketSell.custom.scope="Selected item"`, `.selectedItemId=<reviewed spare ID>`, `.keepLoose=1`, `.maxQuantity=1`, `.fromCollection=false`, `.maxWithdraw=1`, `.maxWithdrawAttempts=0`, `.minNet=2`, `.likelyOnly=true`, `.maxListings=L+1`, `.maxListAttempts=A+1`, `marketSell.enabled=true`. Preserve default minimum sales10/units14 and floor95%; require existing active native rental, one genuinely unreserved loose spare above protection, complete fresh covered market/prices/sales evidence, free slot and sufficient history. One item becomes a listing, zero buying or rental. L must be the actual count used by the current listing cap, not assumed zero. A is durable listing attempts; caps at most20. A posted listing is not a completed sale.

Flipping: keep disabled until a real complete quote exists. Exact controls are `marketFlip.custom.scope="Selected item"`, `.selectedItemId=<reviewed ID>`, `.maxBuy=1`, `.sessionBudget=U+1`, `.goldReserve=G-1`, `.maxAttempts=A+1`, `.maxListAttempts=L+1`, `marketFlip.enabled=true`; keep default profit, coverage, history and floor rules. Requires one genuinely foreign listing priced at most1 Gold and verified profitable followup sale with active shop/free slot. Full custody must cover the buy-to-list sequence. No synthetic bargain or stale/partial quote may be used; this is a conditional recipe, not a currently available candidate.

## Remaining acceptance rows and known blockers

These eighteen rows complete the audit of the catalog beyond the twelve initial and twenty-five additional selectors above:

| Feature IDs | Prerequisite or current limitation |
|---|---|
| `operations` | Another bounded new start is distinct from the original unresolved start. Keep its Cash custody and do not replay it. No extra operation is necessary while collection remains available. |
| `heists`, `heistCollect`, `favors`, `sabotage` | Actual native board/controller/run identity and exact selected target/consent where applicable. Reviewed typed legacy receipts and immutable current native-source binding can conditionally permit a route; admission checks the current counter before acquisition, and queued dispatch requires the exact owned lease afterward. Missing/changed/retired continuity blocks only the affected route. It does not clear a legacy receipt, reset quota, or prove present board eligibility; unrelated unresolved exposure and resource checks still apply. |
| `combat`, `warCombat` | Fresh owned scout/native challenge lease, exact verified target and independent limits; War additionally needs current authoritative active-war roster. No blind target or warning bypass. Family damage custody can block player attacks. |
| `bosses`, `familyBossAttacks`, `globalBossAttack` | Separate damage/Stamina permissions, current native encounter, genuine personal eligibility and Health floors. Do not spend Health just to create healing prerequisites. Family unknown hit-back requires its separate explicit permission and full-health custody. |
| `bossShop` | Positive correct tokens and remaining effective session allowance. Imported consumed session floor remains counted; a new owner does not create a free send. |
| `crewRoll` | Deliberate dismiss/hire replacement with protected member/gear and full funded budget. Ordinary empty-slot CrewHire is preferable; no destructive acceptance recipe is recommended. |
| `prestige`, `skills` | Current captured state has no eligible Prestige reset and no available Skill points. Do not fabricate these or reset character progress merely to tick acceptance. |
| `monthlyRewards` | Current reviewed native monthly calendar is disabled. Honest unavailable state is the available outcome. |
| `globalBossClaim` | Genuine current personal global-encounter reward entitlement; no attack required merely to test the selector. |
| `briefcases`, `eventShop` | Current actual event and earned entitlement/Medals required. Captured native Briefcase event is inactive and EventShop earned Medals were zero; re-read before any conclusion. |

`safehouse` is among the additional twenty-five selectors but intentionally has no low-cost execution recipe: `safehouse.custom.maxTier=<current tier+1>`, `.maxCost=<explicit reviewed native next-tier quote>`, `.cashReserve=1000000`, `safehouse.enabled=true`. The cost can be substantial, must be user-authorized in context, and use the independently reviewed outcome/restart adapter and exact native quote. A native next-tier result certifies upgrade completion, not an exact wallet debit.

Properties, Safehouse, CrewHire and CrewTrain now have separately reviewed exact owned-outcome alternatives, with the old exact-debit paths retained. Property completion requires the selected owned count +1 with all other Property counts unchanged; Safehouse requires exactly the next tier. Both require owned nontransient terminal success, strictly later native time and Cash no lower than before minus quote. Safehouse now has normal owning-descriptor saved recovery. Legacy receipts keep their original baseline schema; local recapture omits only the additive clock field when originally absent. Crew alternatives require strictly later native time and the exact new member or original-member training proof; they retain the original quote and reject transient or contradictory evidence. Some bounded Property/Training paths already confirmed, but new alternatives still need current live acceptance. Do not estimate income, relax a shared wallet rule, or replay an unknown attempt.

The separate reviewed Shop rule is now manager-tested in normal recovery: original request 27 settled without another purchase or request-ID increase. It requires an owned nontransient positive reply, the exact new original-slot purchase marker and loose item grant, unchanged other origins, lifetime increment when tracked, strictly later native time, and Cash no lower than before minus quote. This certifies purchase completion, not exact wallet debit. Original saved baseline bytes and quoted-spend allowance remain preserved. Contract entry/bonus completion similarly certifies the exact claimed marker/reset, not independent delivery of every Cash/XP/item award.

Recipe control verification: nine groups covering 120 concrete scalar keys were accepted by the actual Catalog/Settings model. Dynamic-cap samples validate key/type acceptance only; they do not assert current historical usage or live readiness. No runtime/native call was made by this audit.
