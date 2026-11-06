# Feature completion matrix

Inventory date: 2026-11-06. This audit reads the current working source, not the
historical milestone descriptions. No gameplay calls or account writes were made
by the inventory agent. Live execution is owned by the coordinating agent.

## Completion and evidence rules

The catalog contains **26 pages and 55 feature switches**. RuntimeAssembly
constructs **21 gameplay tab modules**; the five other pages are Overview, Player,
Profiles, Settings, and Activity. All 55 switches have descriptors in the modular
composition. That is registration coverage, not implemented-action coverage.
The older 31-row FeatureRegistry.build/requirements list is a legacy assembly
subset; FeatureRegistry.fromTabs is the current composition path.

Live acceptance remains feature-specific. The coordinating agent has confirmed
bounded ordinary Jobs, Operation start/collection, Playtime, Bank, daily
Contract claims, Family Cash/Stamina contributions and Market earnings collection
with exact successful replies and newer native evidence, no
storage fault and no uncertainty. Other rows still require current-client contract validation
and a manager-owned live result. A successful claim, purchase or action needs the
exact returned result plus the relevant newer game state. Read-only features need
an observed read and visible report. Blocked and unmet-prerequisite rows remain
open under completion-plan.md.

Status meanings:

- **Path**: reader, planner, evidence and dispatch route exist in current source;
  current-client and live acceptance remain unproven.
- **Conditional**: an implemented path replaces a blocked fallback only when
  current source adapters, storage or transaction owners are constructed.
- **Gap**: the effective current path cannot perform the advertised activity.
- **Read**: intentionally read-only functionality; no mutation is needed.

For compactness, module names in the table omit `.luau`. A name such as JobsState
is `src/game/JobsState.luau`; ordinary planners and evidence are in `src/features/`.
Names qualified by a tab are in `src/tabs/<tab>/`. Each row is registered by that
page's `Module.luau` through RuntimeAssembly -> TabComposition ->
FeatureRegistry.fromTabs -> AutomationRuntime. `NativeCallPlan` is the base call
router; CrewCallPlan, InventoryCallPlan, CollectionCallPlan, CombatCallPlan,
MarketCallPlan, FamilyCallPlan and TerritoryCallPlan are the tab-specific routers
composed by RuntimeHost.

Test filenames below are relative to `tests/`. They describe existing coverage,
not a claim that all current branches are exercised. `test_all_tab_composition.py`
checks that all catalog IDs register and startup stays paused; its fixtures omit
many newer optional capabilities, so fallback registration can pass while an
implemented branch is untested.

## Every catalog feature

| ID | Page | Effective modules and runtime route | Source status / limitation | Existing focused tests | Live prerequisite and required outcome |
| --- | --- | --- | --- | --- | --- |
| jobs | jobs | JobsState; Jobs; JobsEvidence; NativeJobCatalog; NativeCallPlan | Path; coordinating agent confirmed one bounded live action with newer native progress | test_jobs_state.py, test_jobs_planner.py, test_jobs_evidence.py, test_jobs_flow.py, test_jobs_runtime.py | Unlocked chosen Job, Energy and gear requirements; exact reply and Job/mastery/resource changes. |
| operations | operations | OperationsState; OperationsStart; OperationsEvidence; NativeOperationsCatalog; NativeCallPlan | Path; one bounded live start and collection confirmed; exact funding may use separately enabled withdraw | test_operations_state.py, test_operations_planner.py, test_operations_evidence.py | Free Operation slot and affordable eligible quote; owned running entry and exact debits. |
| collect | operations | OperationsState; OperationsCollect; OperationsCollectEvidence; NativeCallPlan | Path; one ready owned live collection confirmed | test_operations_collect.py | Ready owned Operation; exact index disappears/advances and rewards reconcile. |
| heists | heists | HeistBoardState; HeistStart/Evidence; NativeHeistCatalog; BoardQuery; shared HeistRuntime/Transactions; native act via HeistCallPlan | Conditional path implemented: native owns sequence allocation; durable claim and status-only restart recovery; live controller read passed 654 | test_native_heist_controller.py, test_heist_runtime.py, test_heist_transactions.py, test_heist_dispatch.py, test_heist_start.py | Account cannot afford minimum 25 Energy with current effective maximum22 (base20); no start sent. Idle eligible board and exact successful run receipt/new board remain required. |
| heistCollect | heists | HeistCollection bound reader/planner/evidence; shared HeistRuntime/Transactions and native act | Conditional path implemented: complete personal-slot summary hash, server day and native counter rechecked at dispatch; historical fallback stays blocked | test_heist_collection.py, test_heist_runtime.py, test_heist_recovery_projection.py; historical test_heist_collect_blocker.py | No current personal result. Exact collected/reward reply plus newer empty personal slot required; disappearance alone never confirms. |
| favors | favors | FavorsState; FavorHelp/Evidence; shared Heist board, HeistRuntime/Transactions and native act | Conditional path live-accepted once on 654: native sequence 1, exact successful reply/newer board, clean checkpoint/no uncertainty; restart retained receipt and daily attempt | test_favor_help.py, test_heists_favors_tab_modules.py, test_heist_accounting_composition.py, shared Heist runtime/dispatch/recovery tests | Manager cap1 helped heist_vault; exact reply Cash 165000 / XP 183. Restart had usage1 and no active action; new attempts require eligible Friend/Family row and current limits. |
| sabotage | heists | SabotageState; Sabotage/Evidence; shared HeistRuntime/Transactions and native act | Conditional path implemented with foreign-owner relation checks, daily usage and durable sequence custody | test_sabotage.py, shared Heist runtime/dispatch/recovery tests | Eligible non-Friend/non-Family foreign run and limits; exact sabotage count, usage and debits. Live mutation outcome remains open. |
| combat | combat | PlayerTargetState.readSelection; PlayerFightPlanner; PlayerScoutEvidence/PlayerFightEvidence; FightReceipts; PlayerFightLedger; HitListQuery/PlayerProfileQuery; CombatCallPlan | Conditional: real ordinary Attack/Scout path; BlockedFight fallback without receipt/history/profile owners | test_combat_recovery_projection.py actual quote/profile/Scout/Attack, settled receipt and daily reset; test_combat_saved_lookup.py exact seed, pacing/expiry/source retirement; test_player_fight_ledger.py thresholds/demotion, duplicate/cap, restart/torn-write/corruption; native wrapper guards separately | Current hit list/profile, notification owner, durable history, eligible target, explicit nonzero independent Attack/Scout limits; owned terminal fight and settlement, or exact Scout resource/cache change. Live action acceptance remains open. |
| warCombat | combat | HitListQuery war roster/exact bounded SearchTarget quote; PlayerTargetState.readWarSelection; PlayerProfileQuery; PlayerFightPlanner war lane; Scout/Fight evidence; FightReceipts/Ledger; CombatCallPlan; native WarStatus cache admission/guard | Conditional Path after this session's repair: independent war permission/limits, authoritative scoring enemy identity and fresh owned Scout required; ordinary targets cannot substitute | test_war_combat.py covers complete read/quote/Scout/Attack/settled receipt/history flow and adverse permissions/identities/limits/cache payloads; existing target/tab/native/router/UI tests pass | Active war and eligible scoring enemy are still required for live action acceptance. Current manager read found no active war/targets. Native cache admission can be verified with the no-war read without opening Family UI. |
| bosses | combat | BossesState/BossStageState; Bosses; BossesEvidence; NativeBossCatalog; CombatCallPlan | Path; dispatch rechecks current Boss catalog | test_boss_stage_state.py, test_bosses.py | Eligible uncompleted stage, required Health/Stamina; exact stage progression and cost. |
| bossShop | combat | BossShopBuyState/BossShopState; BossShopBuy; BossShopBuyEvidence; NativeBossCatalog; CombatCallPlan | Path; selected item, quantity, reserve and send cap | test_boss_shop_state.py, test_boss_shop_buy.py | Unlocked selected item and Tokens; exact inventory gain and Token debit. |
| crew | crew | AutoEquipCrew; RosterState; CrewCallPlan | Path; native set-aware Auto Equip protects unavailable members | test_crew_auto_equip.py | Useful gear/equipment change; resulting native equipment and nondecreasing intended totals. |
| crewGear | crew | CrewGear; GearSets; CrewCallPlan | Path; only loose unbound safe swaps, no Collection withdrawal or multi-step set plan | test_crew_gear.py | Eligible loose gear and available member; exact slot custody and set-aware stat outcome. |
| crewRoll | crew | CrewReplacement; CrewReplacementTransactions/Runtime/RecoveryReview; ResourceReservations; replacement call router | Conditional: bounded funded replacement verified offline through real Crew tab/engine/broker/adapter; no live dismissal accepted. Native ongoing Auto Roll remains deliberately unsupported | test_crew_replacement_lifecycle.py and test_crew_replacement_composition.py cover consent, both stages, exact evidence, persistence refusal, restart, rejected/pending holds and aggregate cash reserve; test_crew_roll_state.py keeps native Auto Roll blocked | Durable custody, selected protected-safe slot, explicit dismissal consent and nonzero caps. Restarted prepared/sent stages cannot emit; only exact observed-empty custody can continue its original funded hire. Ordinary dismissal has no server identity guard. |
| crewSort | crew | CrewSort; CrewCallPlan | Path | test_crew_sort.py | Reorderable home Crew; exact stable order with unavailable members preserved. |
| crewHeal | crew | CrewHeal; reviewed Config.TERRITORY heal rules; CrewCallPlan | Path | test_crew_heal.py | Injured home member, Stamina above reserve; exact member recovery timestamp/debit. |
| crewTrain | crew | CrewTrain; NativeTrainingCatalog; CrewCallPlan | Path | test_crew_training.py | Eligible rarity/member, training capacity, home count and Cash; exact member training state and quote debit. |
| crewHire | crew | CrewHire bound to ContractGoalState; NativeHireCatalog; CrewHireUsage; ContractGoalRequests; CrewCallPlan | Path repaired: empty-slot hires belong to exact current incomplete native hires row; requires separate autoContracts, borrowHires and crewHire permissions plus persistent attempted/spend limits | test_crew_hire.py covers six composed permission/limit combinations, unscoped rejection, exact quote/member/Cash and native contract progress; test_goal_composition.py and UI defaults cover explicit borrowing | Current incomplete native hire contract, empty slot, tier quote and positive run caps. Exact new member/Cash debit and same row progress +1; changed row/reset/unchanged progress stay pending. |
| crewHealItems | crew | CrewHealItems; NativeHealItemCatalog; CrewCallPlan | Path; separate owned-item permission and native Crew cooldown | test_crew_heal_items.py | Injured eligible member, allowed owned item/custody and cooldown; exact consumed copy and member recovery. |
| cosmetics | inventory | Cosmetics; InventoryCallPlan | Path; stronger loose safe background/border swaps | test_inventory_cosmetics.py | Eligible loose cosmetic; exact equipped item and custody-safe stat outcome. |
| collectionDonate | collection | CollectionDonate; NativeCollectionCatalog; CollectionProtection; CollectionCallPlan | Path; unbound safe surplus only | test_collection_donate.py, test_collection_protection.py | Surplus after worn/spare/reservation exclusions; exact loose decrease and Collection increase. |
| chests | inventory | Chests; NativeCrateCatalog; NativeCrateLuckSource/CrateLuckProducer; InventoryCallPlan | Path; owned unbound only | test_inventory_chests.py | Eligible owned unbound crate and current luck proof; exact crate debit and returned loot custody. |
| restoratives | inventory | Restoratives; NativeRestorativeCatalog; InventoryCallPlan | Path; thresholds, bound-first custody and player cooldown | test_inventory_restoratives.py | Resource below configured threshold, useful allowed item and cooldown; exact item debit and pool recovery. |
| bank | money | BankState; BankDeposits; BankDepositsEvidence; NativeBankCatalog; NativeCallPlan | Path; protects purchase savings and uncertain Cash | test_bank_deposits.py, test_purchase_savings.py | Excess Cash after reserves/claims and deposit fee; exact Cash/Bank movement. |
| withdraw | money | WithdrawalState; PurposeWithdrawals; PurposeWithdrawalsEvidence; FundingCoordinator; NativeCallPlan | Path; only enabled Operation/Safehouse exact shortfall | test_purpose_withdrawals.py, test_funding_coordinator.py | Separate enabled purpose, insufficient wallet, sufficient Bank and cap; exact funded shortfall with no repeated withdrawal. |
| properties | property | PropertiesState; Properties; PropertiesEvidence; NativePropertyCatalog; NativeCallPlan | Path; Cash-income no-slot buy, no Gold-income/replacement | test_properties.py | Eligible selected quote within reserve/cap/level/ownership bounds; exact owned count and Cash debit. |
| safehouse | safehouse | SafehouseState; SafehouseUpgrades; SafehouseUpgradesEvidence; NativeSafehouseCatalog; NativeCallPlan | Path | test_safehouse_upgrades.py | Available eligible upgrade and affordable current quote; exact level and Cash debit. |
| prestige | prestige | PrestigeState; PrestigeReset; nativePrestigeController; checkpoint usage; PrestigeReset.describe | Conditional path repaired for reviewed 654/655 identities; production observer passed, rank 1 / level 92 / not ready | test_native_prestige_controller.py, test_prestige_reset.py, test_prestige_tab.py | Requires level 200 at current rank, explicit allowReset/maxResets and clear controllers. No reset sent; exact rank/reset outcome remains open. |
| shop | shop | ShopState; ShopBuy; ShopBuyEvidence; NativeShopCatalog/NativeQuoteSource; ShopQuoteProducer; NativeCallPlan | Path; Cash-only exact native quote | test_shop_cash.py, test_native_shop_quote_source.py, test_shop_quote_producer.py | Eligible chosen item/current quote and reserves; exact item custody and Cash debit. |
| marketWatch | blackMarket | MarketResearchController; MarketBrowse/MarketPrices/MarketRap; ReadCoordinator/ReadBudget/RequestLane; MarketBrowsePages; MarketResearchView | Conditional Read: bounded current browse/price/RAP hypothetical opportunity report; no mutation sender | test_market_watch_integration.py real tab/composed runtime/shared lane/controller/view report, complete pagination, changed rows, exclusions/expiry, mutation lease and close fences; existing browse/price/read tests | Current Market presence and read lease; bounded accepted pages, price/RAP and visible opportunity report. Live report acceptance remains open. |
| marketSell | blackMarket | MarketSellRuntime; MarketTransactions; MarketSellDirect/ListPreflight; MarketCollectionWithdrawPreflight/Evidence; MarketListEvidence; MarketCallPlan | Conditional path: loose-item and separately permitted Collection-surplus custody lifecycle; live acceptance open | test_market_sell_runtime.py real research/tab/engine/broker/adapter flow; test_market_transaction_lifecycle.py withdrawal/list holds, restart, rejection, limits and storage refusal | Owned safe tradable surplus, active shop, slot and owned quote; exact optional withdrawal, acquired hold and matching listing. No live sale outcome yet. |
| marketFlip | blackMarket | MarketSellRuntime in marketFlip mode; MarketTransactions; MarketFlipPreflight/MarketBuyEvidence/MarketFlipListPreflight; MarketCallPlan | Conditional path: ordinary Gold buy followed by only acquired copy listing; live acceptance open | test_market_sell_runtime.py real research/custody/engine buy-to-list flow with independent limits; test_market_transaction_lifecycle.py restart, rejected listing retains bought copy | Qualifying foreign listing, explicit ordinary Gold budget, current quote and shop capacity; exact purchased item/Gold and owned new listing. No live buy/list outcome yet. |
| marketRent | blackMarket | MarketRentRuntime; NativeMarketCatalog; MarketRentQuote/Evidence/Usage; MarketCallPlan | Live accepted: one-period native rental debited bound Gold; normal restart reconciled original saved action with no new rent, healthy storage and zero pending/uncertain | test_market_rent_lifecycle.py exact combined debit, lease, restart, custody/reserve and refund guards; test_market_sell_runtime.py composed bound-funded cap1 path | Current terms and cap; native Config costs 1 Gold per 12h. Both pools must not increase and combined debit must exactly match quote; exact expiry/reply required. Original attempt/spend stayed 1/1; no resend or refund. |
| marketManage | blackMarket | MarketEarningsState; MarketEarnings; MarketEarningsEvidence; MarketPayoutLedger; MarketCallPlan | Conditional path live-confirmed: one collect95, earnings95 to0, loose Gold320 to415, bound24 unchanged; clean checkpoint/no uncertainty | test_market_payout_ledger.py exact/idempotent/restart/CAS/failure/corruption; test_market_sell_runtime.py composed payout records exactly once; test_market_earnings.py | Future payouts require positive sold earnings and durable ledger; exact zero earnings/ordinary Gold gain. Current live receipt is recorded in manager ledger. |
| familyCash | family | FamilyContributionState; FamilyContributions.cash; FamilyContributionEvidence/Usage; FamilyQuery; verified player source; FamilyCallPlan | Conditional path live-confirmed after named-account/configured-cap repair: amount100, own donated counter +100, exact Cash debit, no uncertainty/storage fault | test_family_named_identity.py real query/reader/tab/runtime/checkpoint donation and restart, 57/60-member receipts and over-cap rejection; test_conditional_feature_contracts.py exact personal receipt/debit and foreign actor rejection | Future donations require current owned Family info, Cash reserve, native minimum100 and positive remaining caps. Current live receipt is in manager ledger. |
| familyStamina | family | FamilyContributionState; FamilyContributions.stamina; shared verified actor/evidence/query/usage; FamilyCallPlan | Conditional path live-confirmed: one Stamina to Enforcers, progress32446 to32447; exact settlement, no uncertainty/storage fault | test_conditional_feature_contracts.py real personal receipt/debit/perk completion, usage/refund/restart guards; test_conditional_recovery_projection.py | Future donations require exact selected perk quote, current personal counter, Stamina reserve and remaining caps. Current live receipt is in manager ledger. |
| familyGold | family | FamilyContributionState; FamilyContributions.gold; shared verified actor/evidence/query/usage; ResourceReservations; FamilyCallPlan | Conditional path expanded by explicit opt-in: loose-only default still blocks mixed balances; allowNativeGoldPool permits native total-Gold payment without guessing priority | test_family_gold_pool.py default/typed permission, either/split exact debit, origin increase rejection, retained permission/restart, held-origin and total reserve guards; actual named-account runtime/native-adapter permission revocation/refund and durable one-Gold settlement; shared contribution/projection tests | Family membership, separate switch, positive caps and reserve; mixed balances require explicit total-Gold permission. Both pools must not increase, combined debit must equal amount, and own donatedGold must rise exactly. Live acceptance remains open. |
| familyBossAttacks | combat | FamilyBossAttackState/FamilyTakedownState; FamilyBossAttacks/Evidence; FamilyBossQuery; CombatCallPlan | Path; free attacks only | test_family_takedown_state.py, test_family_takedown_attacks.py | Family event active, free attack remaining and eligible stage; exact attack count and owned event progression. |
| familyBossClaims | combat | FamilyBossClaimState/FamilyTakedownState; FamilyBossClaims/Evidence; FamilyBossQuery; CombatCallPlan | Path; exact week/stage claim | test_family_takedown_claims.py | Unclaimed earned stage/week reward; exact claimed marker and reward custody. |
| territoryWatch | territory | TerritoryState; TerritoryMapQuery; DistrictQuery/FortificationQuery; TerritoryReadSources; TerritoryBonuses/SeasonSource; native CityMaps | Conditional Read: current holdings/bonuses/capacity/season/details report | Territory query/attachment tests; test_territory_city_binding.py; real reader/budget/coordinator five-second Sync regression; native capacity marker regression | Map and district reads accepted live. Same-Sync attachment guards remain; dependency readiness no longer consumes failure backoff. Optional season/fortification acceptance remains conditional. |
| station | territory | Stationing; RecallRuntime/Transactions; NativeRecallController; TerritoryReadSources/CallPlan; checkpoint usage and durable member reservations | Conditional: explicit Station/Recall modes, one own selected stable member, bounded attempts and defense reserves; uncertain Recall is status-only | test_conditional_feature_contracts.py; test_recall_transactions.py; test_native_recall_controller.py; test_recall_runtime.py composed Module/Broker/sender/checkpoint; projection tests | Current 654 native controller bound live. Exact private owned snapshot passes read/capture after preserving nonselected legacy deployment tokens. Bounded live mutation remains pending; selected returning member still needs real healId and exact token. |
| residency | territory | Residency; ResidencyQuery; TerritoryReadSources/CallPlan; checkpoint usage | Conditional: selected admission and same-kind resident contribution/rent comparison; capped gains and unverified tradeoffs refused | test_residency_comparison.py; real admission evidence/usage/restart in test_conditional_feature_contracts.py; projection tests | Current active same-kind share/rent and native bonus total/cap must be verified. Current free 6.5% residence dominates selected 4% with 1% rent, so no move is justified. No cross-kind valuation, all-district ranking or automatic rollback. |
| contracts | contracts | ContractEntriesState; ContractEntries/Evidence; NativeContractCatalog; NativeCallPlan | Path; one daily native row claim confirmed live | test_contract_entry_claims.py | Completed unclaimed daily/weekly row before reset; exact claim flag and rewards. |
| bonuses | contracts | ContractBonusesState; ContractBonuses/Evidence; NativeContractCatalog; NativeCallPlan | Path | test_contract_bonus_claims.py | Completed eligible daily/weekly set and unclaimed bonus; exact period bonus marker/rewards. |
| trophies | trophies | EarnedTrophiesState; EarnedTrophies/Evidence; NativeTrophyCatalog; NativeCallPlan | Path; item-consuming trade-ins remain manual | test_earned_trophies.py, test_trophies_tab.py | Native ready non-trade-in Trophy; exact owned Trophy/reward custody. |
| skills | skills | SkillsState; Skills/Evidence; NativeSkillCatalog; NativeCallPlan | Path | test_skills.py, test_skills_tab.py | Unspent points and current selected stat rules; exact allocated count/point debit/stat totals. |
| playtime | rewards | PlaytimeState; Playtime/Evidence; NativeRewardsCatalog/Source; RewardEffects; NativeCallPlan | Path | test_playtime_claims.py, test_native_rewards_source.py | Ready unclaimed ladder step and exact reward proof; step marker and reward effects. |
| groupBonus | rewards | GroupBonusState; GroupBonus/Evidence; NativeRewardsSource; NativeCallPlan | Path | test_group_bonus.py, test_native_rewards_source.py | Verified group membership and unclaimed availability; exact claim marker/reward. |
| monthlyRewards | rewards | MonthlyRewardsState; MonthlyRewards/Evidence; NativeRewardsSource; NativeCallPlan | Path; native feature may be disabled | test_monthly_rewards.py, test_native_rewards_source.py | Monthly enabled, exact month/today/next day and eligible reward; exact claimed day and reward effects. |
| autoContracts | contracts | ContractGoalState; ContractGoalRequests.derive/observe; AutomationRuntime.goalRoutes; ContractGoalBlocked fallback | Path after registry repair: explicit Jobs/Energy, Operation start/collect and scoped empty-slot Hire goals; other goal types remain excluded | test_contracts_tab.py, test_goal_composition.py, test_crew_hire.py, test_all_tab_composition.py cover real composition, separate permission/borrowing, exact progress/reset and close | Explicit origin plus ordinary feature switches/borrow choices; native contract progress from bounded ordinary action and reset-safe stop. Hire goals require separate borrowHires, crewHire, selected tier and positive attempt/spend caps. |
| trophyFocus | trophies | TrophyFocusState; TrophyGoalRequests.derive/observe/propose/canUseProposal; AutomationRuntime.goalRoutes; TrophyFocusBlocked | Path after registry repair: target-specific ordinary route arbitration; no independent sender | test_trophies_tab.py, test_goal_composition.py, test_all_tab_composition.py cover target selection, ordinary bounds/reserves, permission and ready/owned state | Selected native goal, ordinary/borrow permissions and target-specific catalog; exact progress/ready/owned transition. Unsupported trade-in routes remain manual. |
| globalBossAttack | combat | GlobalBossAttackState/GlobalBossState; GlobalBossAttack/Evidence; NativeGlobalBossSource; CombatCallPlan | Path; rechecks current event identity | test_global_boss_state.py, test_global_boss_attack.py | Active event/run and eligible Health/Stamina/cooldown; exact attack receipt/contribution and cost. |
| globalBossClaim | combat | GlobalBossClaimState/GlobalBossState; GlobalBossClaim/Evidence; NativeGlobalBossSource; CombatCallPlan | Path | test_global_boss_claim.py | Earned claim for current run/event identity; exact claimed state and drop custody. |
| briefcases | events | FreeBriefcasesState; FreeBriefcases/Evidence; NativeCallPlan | Path; free picks only, independent from Event Shop attributes | test_free_briefcase_picks.py, test_events_tab.py | Active Briefcase event with free eligible pick; exact opened slot/free allowance and rewards. |
| eventShop | events | NativeEventShopSource; EventShopBuyer; EventShopUsage; EventShopBuyer.describe | Conditional path repaired against current654 source: multi-currency rows validated, only earned-Medal offers eligible; exact buy,key,1,medal call; separate persistent reserve/spend/attempt custody | test_event_shop_lifecycle.py real tab/runtime/native adapter purchase, exact custody, source/window/expiry retirement and unsent refund, paid/reserve/cap gates, restart without replay; test_conditional_feature_contracts.py and projection tests | Current full Sync has zero earned Medals; no purchase sent. Future acceptance needs active window, selected Medal offer, balance and limits, exact debit/acquisition. Candy/Corn spending and automatic opening/use remain outside this feature. |

## Focused implementation priorities

1. **Goal descriptor connection repaired locally.** The inventory found that
   FeatureRegistry.fromTabs discarded `spec.goals` supplied by both tab modules.
   This session now preserves the module and validates its derive/observe
   contract. Failing regressions first showed missing Contract routing, an
   unrelated Cash-best Job selected for a Trophy, and accepted malformed modules.
   Real composed-runtime tests now cover those behaviors, separate switches and
   borrow permission, ordinary level/Energy limits, native Contract progress and
   reset identity, ready/owned status, and paused/closed behavior. Live
   acceptance and additional objective families remain open.
2. **Accept the Heist paths live when eligible.** Four switches now share the
   reviewed native act queue and a durable action ledger. Offline tests exercise
   timeout, late reply, restart, exact board/reward evidence and source changes.
   Native retries retain the game's semantics; the hub never independently
   allocates or replays a mutation. Current account Energy prevents start and
   there is no collectible result. One bounded Favor help has been accepted live;
   Sabotage and unavailable Start/Collect outcomes remain open.
3. **War combat implemented locally; live prerequisite remains.** Reviewed
   Family WarRosterView and shared FightTab.WarStatus establish the enemy and
   scoring contract. The implementation combines that owned roster with an exact
   bounded SearchTarget quote, profile/friendship evidence, independent war
   Attack/Scout allowances, and existing owned terminal receipt/history handling.
   Native warning, shield, busy, cooldown, Family and resource guards remain
   enforced. Validated owned roster reads update only the native WarStatus read
   cache, matching the game's UI behavior; opening native War UI is unnecessary.
   The current account has no active war, so successful live attacks remain open.
4. **Accept Prestige after its level prerequisite.** Reviewed 654/655 bindings
   and exact identity guards now expose the current controller. The production
   read passed; current level 92 is below required level 200. Reset acceptance
   remains open without consuming a reset attempt.
5. **Accept reviewed conditional paths with exact live custody evidence.** The
   expanded suites now cover ordinary PvP receipts/history, funded Crew replacement,
   Market custody, Family contribution, Territory mutations and Event Shop. Current
   live reads exposed real Family capacity and Event Shop currency/call-arity
   mismatches; regression-first repairs now use the reviewed native contracts.
   Remaining available paths need bounded live outcomes. Dedicated ordinary Combat
   tests cover both-clock Lookup spacing, expiry, exact seed identity/source retirement,
   High-value thresholds/demotion and capacity, duplicate receipts, restart and
   storage failure/corruption alongside the composed receipt coverage.
6. **Reconcile the UI and release.** Heists/Favors expose their native path only
   when the current controller and durable owner are composed. Historical blocker comments and fallback fixture
   tests are not evidence that their optional current runtime is absent. Review
   dependency bytes, compose a coherent published release and perform bounded
   manager-owned live tests for every available row.

## Shared live acceptance prerequisites

- Confirm game version, fingerprint and each current source capability for the
  actual release being tested. Recovery saw game `0.26.646.1`; older public pins
  target older source/runtime versions. Local edits do not update public pins.
- Use one request queue and one account owner. Start paused with every feature
  off, apply only the row's explicit limits, capture before state, execute a
  bounded action/read, capture exact return and newer state, and pause/clean up.
- Preserve attempted allowances, item/Gold/Cash custody and unresolved work across
  stop/reload. Never reset those merely to make another test eligible.
- Record unavailable seasonal events, missing membership/war/Family, no ready
  reward, no eligible target/item, insufficient balances or unmet rank/level as
  explicit unmet prerequisites. They remain unverified, not complete.
- Independently verify profiles, Settings migration, global resource reserves,
  pace/read budget, Activity recovery, pause/resume/stop and UI close/reopen.
  These support pages are not extra catalog feature switches.

## Inventory verification

Fresh local command: `.venv/Scripts/python.exe -m pytest` on
`test_all_tab_composition.py`, `test_feature_registry.py`,
`test_heist_collect_blocker.py`, and `test_native_call_plan.py`:
**22 passed, 29 subtests passed**. This confirms the audited composition and
existing blocker/call-plan behavior. It does not exercise Roblox UI or establish
any successful server outcome.

After the goal registry repair, the new goal integration tests plus tab
composition/registry, Contract/Trophy tabs, AutomationRuntime and Scheduler checks
passed: **81 tests and 10 subtests**. The goal test module alone passed **11 tests
and eight subtests**. This is offline regression evidence only.

After the war path and bounded native cache adapter, the focused war, Combat
tab/target/native/router, RuntimeHost and UI checks passed **120 tests and 35
subtests**, with one optional analyzer skip. No gameplay call was made by this
agent. Live war action acceptance is still blocked by the absent active war.


## Bounded recovery snapshot contracts

All 51 action-capable switches have explicit tested recovery projections. The
four goal/watch switches do not emit their own actions. Complete native state and
all six headers are retained, conflicting duplicate aliases fail, malformed graphs
remain rejected, and the original storage limits are unchanged. See the
[per-feature capture owners, retained fields and private size-review limits](recovery-snapshot-contracts.md).

Fresh full-suite verification after the Family named-account/capacity and current
Event Shop currency/call repairs passed **867 tests and 358 subtests**, with one
optional analyzer skip. Subsequent Lookup and PlayerFightLedger checks passed
**eight tests and four subtests**. These are offline results; current live outcomes
and unmet prerequisites remain in the [manager's ledger](live-validation-2026-11-06.md).
