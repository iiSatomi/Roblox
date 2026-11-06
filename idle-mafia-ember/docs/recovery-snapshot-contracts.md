# Bounded action recovery snapshot contracts

`src/storage/PendingAction.luau` declares the extra top-level snapshot fields
required to reproduce each feature's captured evidence. The map covers all
**51 action-capable catalog switches**. `autoContracts`, `trophyFocus`,
`marketWatch` and `territoryWatch` derive goals or perform owned reads; they never
submit their own checkpoint action.

Every action retains all six headers (`session`, `account`, `place`, `release`,
`revision`, `capturedAt`) and the **complete native Sync**. `fullSync` is retained
if present. The duplicated top-level `data` alias is omitted only when bounded
identity/deep comparison proves it equals `native`; conflicting duplicates fail.
There is no blanket native-field pruning. The complete incoming snapshot graph
must still satisfy the original node/depth/key/string/finite-value/cycle checks.
The final action, baseline and reply remain subject to the original **262144-byte**
limit. Unknown future feature contracts retain their complete snapshot and fail
closed if it is too large. Adding a catalog action requires an explicit contract
and regression before changing that behavior.

## Capture owners and retained fields

Capture paths below are relative to `src/` and omit `.luau`. Bound wrappers and
restart validators must be considered alongside the named static evidence. A
missing required proof never becomes authorization merely because the encoder
accepted the data; its owning capture/recovery validator still rejects it.

| Feature | Owning capture/recovery path | Additional retained top-level fields |
| --- | --- | --- |
| bank | features/BankDepositsEvidence | bankConfig, purchaseSavings |
| bonuses | features/ContractBonusesEvidence | catalogKey, contractBonusConfig, contractConfig |
| bossShop | features/BossShopBuyEvidence | bossShopProof, bossShopUsageProof |
| bosses | features/BossesEvidence | bossStageProof, bossUsageProof |
| briefcases | features/FreeBriefcasesEvidence | briefcaseRules, caseEvent, catalogKey |
| chests | tabs/inventory/Chests | crateLuckProof, ownedCrateCatalog |
| collect | features/OperationsCollectEvidence | catalogKey, operationCatalog |
| collectionDonate | tabs/collection/CollectionDonate | collectionCatalog, collectionProtection |
| combat | tabs/combat/PlayerFightEvidence + PlayerScoutEvidence | hitListProof, playerFightHistoryProof, playerFightProof, playerFightUsageProof |
| contracts | features/ContractEntriesEvidence | catalogKey, contractConfig |
| cosmetics | tabs/inventory/Cosmetics | None; full native and headers suffice |
| crew | tabs/crew/AutoEquipCrew | None; full native and headers suffice |
| crewGear | tabs/crew/CrewGear | None; full native and headers suffice |
| crewHeal | tabs/crew/CrewHeal | healRules |
| crewHealItems | tabs/crew/CrewHealItems | healItemCatalog |
| crewHire | tabs/crew/CrewHire + contracts/ContractGoalState | catalogKey, contractTemplates, crewHireUsageProof, economyProof, hireCatalog |
| crewRoll | tabs/crew/CrewReplacement | crewReplacementOwnerProof, crewReplacementSourceKey, crewReplacementUsageProof, economyProof |
| crewSort | tabs/crew/CrewSort | None; full native and headers suffice |
| crewTrain | tabs/crew/CrewTrain | trainingCatalog |
| eventShop | tabs/events/EventShopBuyer + NativeEventShopSource | eventShopProof, eventShopUsageProof |
| familyBossAttacks | features/FamilyBossAttacksEvidence | familyAttackProof, familyAttackUsageProof, familyTakedownProof |
| familyBossClaims | features/FamilyBossClaimsEvidence | familyClaimUsageProof, familyClaimUsageProofs, familyTakedownProof |
| familyCash | tabs/family/FamilyContributionEvidence + FamilyContributionState | familyActorProof, familyContributionCatalog, familyContributionProof, familyUsageProof |
| familyGold | tabs/family/FamilyContributionEvidence + FamilyContributionState | familyActorProof, familyContributionCatalog, familyContributionProof, familyUsageProof |
| familyStamina | tabs/family/FamilyContributionEvidence + FamilyContributionState | familyActorProof, familyContributionCatalog, familyContributionProof, familyUsageProof |
| favors | features/FavorHelpEvidence | catalogKey, favorUsageProof, heistBoardProof, heistCatalog |
| globalBossAttack | features/GlobalBossAttackEvidence | globalAttackUsageProof, globalBossProof, localUserIdProof |
| globalBossClaim | features/GlobalBossClaimEvidence | globalBossProof, globalClaimUsageProof, localUserIdProof |
| groupBonus | features/GroupBonusEvidence | catalogKey, groupConfig, groupMembership |
| heistCollect | tabs/heists/HeistCollection | catalogKey, heistBoardProof, heistCatalog, heistControllerProof |
| heists | features/HeistStartEvidence | catalogKey, heistBoardProof, heistCatalog |
| jobs | features/JobsEvidence | catalogKey, jobCatalog, masteryRules |
| marketFlip | tabs/blackMarket/MarketSellRuntime + MarketBuyEvidence + MarketListEvidence | None; full native and headers suffice |
| marketManage | features/MarketEarningsEvidence | None; full native and headers suffice |
| marketRent | tabs/blackMarket/MarketRentRuntime + MarketRentEvidence | marketRentTermsProof, marketRentUsageProof |
| marketSell | tabs/blackMarket/MarketSellRuntime + MarketListEvidence + MarketCollectionWithdrawEvidence | None; full native and headers suffice |
| monthlyRewards | tabs/rewards/RewardEffects + features/MonthlyRewardsEvidence | catalogKey, monthlyConfig |
| operations | features/OperationsEvidence | catalogKey, operationCatalog |
| playtime | tabs/rewards/RewardEffects + features/PlaytimeEvidence | catalogKey, ladderCatalog, ladderTiers, weekendBuff |
| prestige | tabs/prestige/PrestigeReset | catalogKey, prestigeCatalog, prestigeUsageProof |
| properties | features/PropertiesEvidence | catalogKey, propertyCatalog, propertyProof |
| residency | tabs/territory/Residency | residencyUsageProof, residencyView |
| restoratives | tabs/inventory/Restoratives | restorativeCatalog |
| sabotage | features/SabotageEvidence | catalogKey, heistBoardProof, heistCatalog, localUserIdProof, sabotageUsageProof |
| safehouse | features/SafehouseUpgradesEvidence | catalogKey, safehouseCatalog |
| shop | features/ShopBuyEvidence | catalogKey, shopCatalog, shopQuoteProof |
| skills | features/SkillsEvidence | catalogKey, skillRules |
| station | tabs/territory/Stationing + RecallRuntime | stationCatalogProof, stationReservationProof, territoryDistrict, territoryMap |
| trophies | features/EarnedTrophiesEvidence | catalogKey, trophyCatalog |
| warCombat | tabs/combat/PlayerFightEvidence + PlayerScoutEvidence | playerFightProof, playerFightUsageProof, warRosterProof |
| withdraw | features/PurposeWithdrawalsEvidence | fundingRequest |

## Deliberate nested projections

Station and Recall read only the selected district's city and garrison cap from
`stationCatalogProof`. Recovery retains those two selected map entries only when
the intent names the same district as `territoryDistrict.district.id`; it retains
the complete source identity, current map, district, reservations and native Crew.
It never substitutes a capacity or city. A changed selected city/cap still fails
recapture. This avoids serializing the unrelated global district catalog.

Ordinary Combat preserves the selected owned high-value membership for an
explicit high-only action. The live ledger retains the complete history and target
catalog. This existing bounded projection does not manufacture membership or
change target selection. War actions preserve their independently owned roster.

Market Sell/Flip recovery invokes static custody evidence, restoring its
`preflightOnly` flag locally exactly as `MarketSellRuntime.recoverSaved` does.
Research/queued-dispatch owners remain live capabilities and are never serialized.
Recall, Crew replacement, Market custody and Heist sequence owners maintain their
own strict transaction ledgers; these projected snapshots cannot replay an action.

Family Gold retains its explicit `allowNativeGoldPool` intent permission and both
original Gold balances in the captured baseline. The default still requires a
loose-only balance. Native-total payment must be explicitly selected; recovery
recaptures that permission and requires each origin to be nonincreasing, the exact
combined debit and the exact personal `donatedGold` receipt. No payment priority or
replay capability is serialized. Pending total-Gold exposure protects both origins.

## Regression and size evidence

The projection regression suites use real planners, bound capture validators and
existing feature fixtures. They add an oversized unrelated catalog, then verify
complete native equality, exact baseline recapture, `PendingAction.Copy` and
`Same`. They include both Attack/Scout lanes, Station/Recall, both funded Crew
replacement stages and Sell/Withdraw/Buy/List Market stages. The catalog guard
checks all 51 action IDs and preserves unknown-feature fail-closed behavior.
The private real failed Jobs capture also roundtrips, without committing account
data. Cycle/function/nonfinite/conflicting-alias and required-oversize cases stay
rejected under the original limits.

A separate private size-only diagnostic reused the earlier actual full-native
multi-tab snapshot. It is **not gameplay or evidence acceptance**: 20 features
were missing at least one conditional proof, and synthetic intent/baseline fields
were used only to measure encoding. The largest complete-field minimal case was
Collection at 221160 bytes. Station's unselected incomplete case was 251601 bytes;
an explicitly synthetic selected-district case with a roster-shaped baseline was
202185 bytes. Fresh full action/proof/baseline/reply captures remain necessary for
live acceptance. No missing-prerequisite feature is counted as complete from those
measurements.
