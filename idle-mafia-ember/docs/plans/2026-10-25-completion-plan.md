# Idle Mafia Ember remaining-feature completion plan

> Execution order and work discipline now live in [tasks/todo.md](../../tasks/todo.md) and [tasks/plan.md](../../tasks/plan.md), approved October 28. This document retains technical specifications and historical evidence; do not restart broad audits or treat its old checkbox states as a competing queue.

**Goal:** Deliver a modular GitHub loadstring whose advertised features have complete configuration, planning, dispatch, outcome confirmation, recovery and disable/unload behavior, with live evidence tracked separately.

**Architecture:** Keep feature behavior in its owning `src/tabs/<tab>/` modules and the existing focused readers/planners/evidence modules. All actions use the existing broker and one durable account-scoped request owner. Read queries and cross-tab goals join that owner during final integration; they do not create independent mutation loops.

**Stack:** Luau, Ember, injected Python/Lupa tests, commit-pinned GitHub modules and manifest.

## October 28 measured inventory supersedes older summaries

Use the [counted inventory](../completion-inventory-2026-10-28.md) and JSON: **23/55 local bounded scopes, 22 partial, 10 blocked actions; 0/55 current-release live verified**. 41.8% is the local milestone only, not overall effort/completion. Nine gameplay plus four utility tab scopes locally covered; 12 gameplay tabs unfinished. Fresh suite: **1292 run, 1291 passed, one analyzer skip**, 36.970 seconds; catalog matches; 277 unique modules. Entry still allows only Jobs/city Bosses. Legacy 231-setting parity, shared closure, packaging and live acceptance remain separate.

Older task checkboxes/progress summaries below are historical and do not override this inventory/latest evidence. Continue owned Market listing, then withdrawal/list and buy/list per the Market runtime plan. Inventory lists subsequent tab order and exact blockers.

## Starting point and meaning of done

- Working tree: `C:/Users/asato/.codex/worktrees/idle-mafia-release/Roblox`.
- All paths below are relative to its `idle-mafia-ember/` directory unless marked otherwise.
- Inventory at the original plan: 25 tabs, 55 feature controls, 230 source modules and 23 IDs with native call mappings. Latest recorded manifest preflight: 271 source modules within the consistent 512-module loader/builder bound. A mapping or module count is not a completion claim.
- Latest recorded full local run: **1240 run, 1239 passed, one skipped** on October 28 (34.309 seconds), after explicit Crew recovery UI, exact definite-unsent evidence, and capability-conditioned availability. The skip requires the external official Luau analyzer. Source inventory is **274 modules**; all 55 ledger IDs match the catalog. See [explicit Crew recovery](../m33-crew-explicit-recovery.md), [saved outcomes](../m32-crew-saved-outcomes.md), [Crew runtime](../m31-crew-runtime-owner.md) and prior milestones. Published entry remains `9da6d31`, allowing Jobs and city Bosses; local changes remain unpublished. Only executor-origin Jobs have live confirmation in supplied evidence.
- Every feature has three independent milestones: **C** = complete code and UI wiring; **T** = meaningful local integration scenarios pass; **L** = current-client action and exact result observed. Publication is a fourth release milestone.
- A blocker-only module, a visible switch, a pure planner test, or a native `ok=true` log cannot complete C/T/L by itself. Read-only features complete L through observed query/display behavior and zero mutation calls.
- No overall completion percentage until every row below has an explicit C/T/L status and a linked result. Count features, not files or tests. C/T completion can advance while L waits for a client.

## Standing constraints

- October 27 source correction: the old `*-full` folder was filtered by a fixed module-name list. The supplied place has now yielded 278 inert sources in primary `imports/idle-mafia-2026-10-27-all-sources/`. Read [coverage correction](../source-coverage-2026-10-27.md) before repeating a missing-source claim. Event Shop and Crew Recall contracts are now available; earlier absence blockers are superseded. Re-audit remaining source gaps against that manifest.

- Work tab by tab. Finish the current tab's implementation, injected end-to-end wiring and focused verification before moving on. Shared architecture and cross-tab coordination are specified now and implemented in Task 24; tab work uses the same injected seams.
- Finish ordinary code without asking again for permission. Complete offline code, configurations, previews and recovery for sensitive actions too; keep their live execution dependent on the applicable user choices.
- No MCP use. Use the saved game/source and supplied Cobalt logs. Request additional evidence only for an exact unresolved contract after checking those sources.
- No live Stamina consumption while the Territory-war restriction stands. This does not prevent offline Combat, healing, or contribution implementation.
- All feature defaults are off. A user-created autoload profile may restore enabled choices and start them without a default pause. Import/preview alone never executes an action.
- One logical active request, one-second default/minimum spacing, quarter-second planner checks. At first-send +45 seconds, mark unconfirmed/skipped, record duplicate exposure, release scheduling ownership and cool down that feature. Late callbacks cannot alter a newer request. Never describe expiry as server cancellation.
- User decisions still needed for live player attacks, Prestige reset, dismissals/sales, shared Family spending and Gold budgets are attached to the relevant row; they do not postpone ordinary coding or unrelated features. Do not infer authorization for real-money purchases.
- Preserve stable member/item identity, bound/tradable custody, resource reserves and cleanup on disable, profile changes, unload and client-version change.
- Use ordinary action automation. Controller modes must follow their actual supported entitlement/stop contract; do not substitute fake ownership for an unknown contract.
- No GitHub update during tab implementation. Package and publish only at the release task, with reviewed contents and the existing destination authorization.

## Current progress — refreshed October 26

This checkpoint supersedes the original starting-state column below. Historical test totals in earlier checkpoints are preserved; the latest run above distinguishes executed tests from the skipped test. C/T complete means the documented scope passed local integration, not current-client verification.

| Tasks | Completed implementation/local evidence | Still open |
| --- | --- | --- |
| 01–06 | Operations start/collect, Bank deposit/withdraw, Properties, Safehouse, Shop and Skills C/T complete; evidence links are in each task. | L for these eight controls; shared integration and publication. |
| 07 | Group income-modifier activation C/T; supported Ladder and source-enabled Monthly exact effects and App scenarios. | Income-based Cash/active XP extension; saved Monthly disabled; whole Rewards C/T and all L remain open. |
| 08 | Free Briefcases C/T complete. Earned-only Event Shop buyer/evidence, persistent separate exposure/attempts, bound-medal reservations, explicit paused allowance reset, actual host attribute/clock binding and queued-call checks pass. | Feature-specific restart reconciliation, release migration, mixed paid/earned origin order and L. |
| 09 | Contract entry and bonus claims C/T complete; selected goal request module. | Auto Contracts arbitration in Task 24; L. |
| 10 | Non-consuming Trophy claims C/T complete; Trophy Focus request module. | Goal arbitration in Task 24; consuming routes excluded; L. |
| 11 | Guarded healing, quoted hire parity, late-slot/high-tier support, bounded replacement planner/store/settings/tab route and App/native-adapter cycle; 73 Crew tests pass. | Actual member/item/funded-Cash reservations, durable usage and dispatch/recovery hooks in Task 24; native Auto Roll lacks bounded-spend contract; L. |
| 12 | Cosmetics, unbound Chests and player Restoratives C/T complete. | Shared item reservations in Task 24; L. |
| 13 | Ordinary Collection deposit C/T complete with exact custody and five native count tiers. | Full cross-tab reservation acceptance in Task 24; L. |
| 14–15 | Heist read ownership component, Favor limits/settings and exact recorded sequence gap. | Mutation sequence/result identity and recovery; C/T and L remain incomplete. |
| 16 | Native city Boss/Shop catalog; six call signatures; Global native attributes/access; Family state and exact claim follow-up through shared owner. | Family hit-back and actual reward-effect proof, player/war controllers, complete acceptance and L. |
| 17 | Earned payout call/minimum setting, durable offline transaction lifecycles and complete tab-local controls/projection. Watch now has actual shared pagination/RAP/history, filters/terms/aging and App display; bounded research C/T complete. Saved transaction reservations connected. | Durable usage/intent recovery, lifecycle/send hooks, earned-payout ledger, trade dispatch and L. Trading routes remain blocked; whole-Market C/T unfinished. |
| 18 | Cash/loose-only Gold/Stamina actual shared info reads, source-key-bound attachment, persistent separate limits/custody/full pending data, explicit paused run reset, exact personal receipt/debit evidence and three-currency App/native-adapter scenarios. | Feature-specific restart reconciliation, release migration, mixed-origin Gold contract, full cross-feature acceptance and L. |
| 19 | Individual stationing, exact duty proof, durable own recall, residency components; actual shared map/district/Residency/fort reads, native season host and full-Sync holder bonuses. App displays selected garrison capacity/shield observations. | Broader Family capacity acceptance, usage/deployment/defender ownership and lifecycle hooks, effective residence optimization, full runtime acceptance and L. |
| 20 | Source-bound reset preview/settings/planner/call/evidence and App/native-adapter test. | Durable sent usage/intent recovery, native arbitration/current preview in Task 24; L. |
| 21 | Jobs tab C/T parity: all 102 saved Jobs and 17 tiers, Vespera/Exiles unlock boundaries and native yielding. | Shared goal arbitration in Task 24; current-release L smoke. |
| 22 | Overview/Profiles/Settings/Activity tab-local C/T complete, including bounded runtime views and staged JSON transfer. | Real shared-runtime status ownership and current-client UI acceptance. |
| 23 | All 55 catalog controls have explicit route/evidence/blocker entries in the October 28 ledger; recovered Crew/Rewards/Event Shop/Heist/Boss contracts rechecked. | Legacy individual-setting parity inventory and explicitly unresolved feature contracts. |
| 24–26 | Shared host mutation/membership lane, bounded read coordinator, owned confirmation reads, Heist/Family attachments and tab cleanup implemented/tested. | Remaining read sources, shared reservations/durable intents/hooks/goals; packaging and authorized current-client acceptance/publication. |

**Latest completed slice:** [Family runtime integration and queued-choice cancellation](../m18-family-runtime.md), following shared request/read integration and Rewards effects. The [55-control ledger](../feature-wiring-ledger-2026-10-28.md) keeps unfinished dependencies explicit. Continue Task 24's remaining sources/reservations/durable intents and Task 23's legacy-setting parity; no tab-local sender bypasses the shared owner.

## Execution rule for every tab task

1. Read only that tab's modules, source references and tests; record exact remote name, argument order/arity, sequence owner and native outcome fields in its feature evidence notes. Do not invent an argument to fill a gap.
2. Reproduce the missing user-visible behavior with one focused failing integration scenario through the real descriptor, App settings and fake transport. Pure helper tests are supplemental.
3. Complete its settings, reader, planner, call description and outcome evaluator. Add a focused tab-local call module where needed; `NativeCallPlan` delegates to reviewed modules rather than becoming another huge script. Bind those modules in `RuntimeHost` and the tests together.
4. Exercise success, rejection, stale snapshot/quote, 45-second uncertainty, late reply, disable and reload only where that feature's effects require them. Verify an exact result; do not count a request as success.
5. Run focused tests. Run the full suite when changing shared contracts, then record C/T evidence and the precise L script/assertion still needed. Commit a bounded local checkpoint after review; no push.
6. If a required game fact is absent, write one evidence item with the missing fact, sources already checked and the smallest user-run observation needed. Finish every independent part of that tab, leave its row unfinished, then move to the next executable task. Revisit these rows before release acceptance.

The common local commands are:

```powershell
# From the release-worktree repository root; the installed Lupa path is local-only.
$env:PYTHONPATH='C:\Users\asato\AppData\Local\Temp\idle-mafia-lupa;C:\Users\asato\.codex\worktrees\idle-mafia-release\Roblox\idle-mafia-ember\tests'
python -B -m unittest test_automation_runtime test_native_call_plan
python -B -m unittest discover -s idle-mafia-ember/tests -p 'test_*.py'
python -B idle-mafia-ember/tools/build_release_manifest.py --preflight
git diff --check
```

## Feature ledger — all 55 controls

Status below is the starting implementation state, not a completion mark. `Mapped` means an existing NativeCallPlan branch; `Partial` means domain code exists but execution is incomplete; `Blocked` means a blocker or missing action contract remains. Each row's completion requires C/T/L as defined above.

| Task | Feature ID | Starting state | Remaining deliverable and exact acceptance |
| --- | --- | --- | --- |
| 01 | `operations` | Mapped | Start an eligible selected Operation into exactly one new native slot; prove quote debit and preserve other runs. |
| 01 | `collect` | Mapped | Collect the selected ready array entry; prove its stable native slot disappears and other slots keep their runs. |
| 02 | `bank` | Mapped | Deposit only calculated surplus after current fee and planned purchase reservations; prove exact cash/bank movement. |
| 02 | `withdraw` | Mapped | Fund only a currently enabled, affordable purchase; withdraw rounded exact shortfall, confirm transfer, then replan the purchase. |
| 03 | `properties` | Mapped | Wire goal selection and current quote/capacity; prove one selected build, exact debit and unchanged other property counts. |
| 04 | `safehouse` | Mapped | Honor tier/level/cash caps; prove one tier increment and exact quoted debit, then stop at configured maximum. |
| 05 | `shop` | Mapped | Use current rotation and cash quote, yield to native Auto Buy, buy selected eligible offer and prove item/stock/cash changes. |
| 06 | `skills` | Mapped | Wire selected stat/batch/cap; prove exact allocations and point cost without changing other stats. |
| 07 | `playtime` | Mapped | Resolve eligible weekday/weekend/Mystery reward and resource effect; prove exact ladder claim marker and reward. |
| 07 | `groupBonus` | Mapped | Refresh actual membership, claim once when eligible, prove native claimed flag/reward; never join automatically. |
| 07 | `monthlyRewards` | Mapped | Claim the earned current UTC day; prove date/claim marker and reward, with no catch-up purchase. |
| 08 | `briefcases` | Mapped | Use only free picks; prove one new selected reveal, one free-pick decrement and unchanged previous reveals. |
| 08 | `eventShop` | Blocked | Implement current offer/catalog reader, medal budget, selected-item buyer and exact medal/item proof including origin restrictions. |
| 09 | `contracts` | Mapped | Claim exact completed daily/weekly entry in the current reset period; prove selected marker and earned reward. |
| 09 | `bonuses` | Mapped | Claim eligible period bonus separately; account for immediate refills and prove the matching bonus marker. |
| 09 | `autoContracts` | Blocked | Produce goal requests for supported objectives; Task 24 executes through existing planners, with explicit borrowing policy and objective progress proof. |
| 10 | `trophies` | Mapped, limited IDs | Classify every current ready Trophy route; implement supported non-consuming claims beyond the two reviewed IDs only with exact source/proof. Keep trade-ins separately scoped. |
| 10 | `trophyFocus` | Blocked | Select one supported goal and emit its ordinary action route; Task 24 arbitrates it and stops on actual goal completion. |
| 11 | `crew` | Partial | Map native Auto Equip, coalesce roster/inventory changes, suppress no-ops and confirm the resulting owned loadout. |
| 11 | `crewGear` | Partial | Compare native loadout baseline; implement only supported exact member/slot swaps, reserve copies, prove each swap and recover interrupted plans. |
| 11 | `crewRoll` | Blocked | Complete bounded ordinary replacement flow with funded intent before dismissal, rarity/quality limits and stable IDs. Native Auto Roll mode additionally needs supported ownership and verified stop-on-disable. |
| 11 | `crewSort` | Partial | Map native sorting and prove the returned roster order while preserving the same unique member set. |
| 11 | `crewHeal` | Partial | Map exact injured-member heal; honor Stamina reserve and prove injury recovery plus actual cost. Offline tests now; live test waits for war restriction. |
| 11 | `crewTrain` | Partial | Map selected training/duration, reserve home/concurrency capacity and cash, prove exact member training start and cleanup. |
| 11 | `crewHire` | Partial | Hire into an exact empty slot at a current quote; prove one new stable member and exact debit. No implicit dismissal. |
| 11 | `crewHealItems` | Partial | Own item sequence/cooldown, select exact member and stack, prove one item decrement and injury improvement. |
| 12 | `cosmetics` | Partial | Map selected profile cosmetic operation; prove the worn slot and preserve Inventory/Collection ownership. |
| 12 | `chests` | Partial | Wire owned unbound crate selection/batch/luck/cap; prove exact crate consumption and returned rewards. |
| 12 | `restoratives` | Partial | Wire all nine supported consumables, independent player cooldown/sequence and useful thresholds; prove selected stack and pool change. |
| 13 | `collectionDonate` | Partial | Map exact surplus deposit with five native thresholds, base/variant identity and bound custody; prove equal inventory decrease/Collection increase. |
| 14 | `heists` | Partial, sequence blocked | Establish current sequence ownership, fund bounded start, persist intent, prove exact personal run identity and recover owned uncertain sends. |
| 14 | `heistCollect` | Blocked | Obtain addressable result identity; implement collect with owned sequence and exact result/reward proof, including reload recovery. |
| 14 | `sabotage` | Partial, sequence blocked | Own sequence and selected target, enforce separate opt-in/daily/resource cap, prove the selected sabotage outcome. |
| 15 | `favors` | Partial, sequence blocked | Share the native sequence contract correctly with Heists; select eligible help target, enforce daily/energy caps and prove exact help/reward. |
| 16 | `bosses` | Mapped | Verify city-stage selection, health/Stamina limits and one-hit accounting; live attack waits for war restriction. |
| 16 | `bossShop` | Mapped | Wire current token quote, selected gear/crate and attempt budget; prove exact token/item movement. |
| 16 | `globalBossAttack` | Mapped | Connect current event/access/personal state; prove one personal hit and exact reply damage under health/Stamina/run limits. |
| 16 | `globalBossClaim` | Mapped | Connect settlement and participation; claim exact run and distinguish already auto-claimed rewards from a new claim. |
| 16 | `familyBossAttacks` | Mapped | Connect Family/week/stage/free-charge state, protect Tickets, and prove one free-charge attack with exact result. |
| 16 | `familyBossClaims` | Mapped | Claim exact earned week/stage, confirm marker and reward, and reconcile earlier claims after reload. |
| 16 | `combat` | Blocked | Implement target/scout filtering, separate opt-in, limits, cooldowns and exact fight outcome. Do not invent hidden cash or guaranteed win odds. |
| 16 | `warCombat` | Blocked | Add war-specific eligibility/target filters and result proof through the same fight engine; no shared implicit PvP permission. |
| 17 | `marketWatch` | Partial | Connect bounded complete browse, prices and RAP reads; show fresh opportunities and aging-listing review with zero purchase/list calls. |
| 17 | `marketManage` | Mapped | Collect earned payout; prove exact listing/payout and Gold delta and persist a confirmed ledger. |
| 17 | `marketRent` | Partial | Complete rental transaction/attempt record, selected native term, Gold reserve and exact spend/expiry proof. |
| 17 | `marketSell` | Partial | Complete exclusions/custody, optional Collection withdrawal, quote and listing transaction with per-step proof and interrupted recovery. |
| 17 | `marketFlip` | Partial | Complete research → budgeted buy → owned item → listing transaction, persist stage and stop for review on uncertainty. |
| 18 | `familyCash` | Blocked | Implement current Family/cost/perk reader, separate amount/cap and contribution call; prove own debit and selected shared increment. |
| 18 | `familyStamina` | Blocked | Implement native-cost perk rotation and reserve/cap; prove exact cost and selected perk contribution. Live testing waits for war restriction. |
| 18 | `familyGold` | Blocked | Implement independent default-zero Gold budget and current quote; prove own Gold debit and selected shared contribution. |
| 19 | `territoryWatch` | Partial | Connect city-scoped map/residency reads and display ownership, capacity, top-two bonuses, season and fortification with no mutation calls. |
| 19 | `station` | Blocked | Implement exact own-member station/recall, current city capacity and defense/home protections; prove member duty and district assignment. |
| 19 | `residency` | Blocked | Compare effective bonus/rent, preview previous lease effect, implement bounded move and prove exact new residence/cost. |
| 20 | `prestige` | Blocked | Implement readiness preview, explicit reset option/per-load cap, current reset call and exact rank/level/EXP proof; no reset during offline work. |
| 21 | `jobs` | Mapped, live-confirmed earlier | Preserve working Jobs while adding native catalog parity for all zones, selected/mastery goals and current-release regression; reverify new release. |

## Ordered implementation tasks

Each task below uses the six-step execution rule. Existing file stems are implementation starting points; newly proposed modules are explicitly marked **create**. Do not import or patch the legacy generated Fluent runtime to fill a recode gap.

### 01 — Operations: first implementation task

Files: `src/tabs/operations/Module.luau`, `src/features/OperationsStart.luau`, `OperationsCollect.luau`, `OperationsEvidence.luau`, `OperationsCollectEvidence.luau`, `src/transport/NativeCallPlan.luau`, `src/App.luau`.

- [x] Exercise the real Operations tab and App settings through `NativeDispatchAdapter` with fake native remotes, not a planner-only stub.
- [x] Complete collect → new full Sync → replan → start for shifted array indices and stable native slots; the separate collect setting does not enable start.
- [x] Prove exact slot preservation, resource reserve, full capacity, rejection and uncertainty behavior in the focused Operations/Runtime tests. Start proof now requires the current catalog quote, exact cash debit and all prior stable slots.
- [x] Record **C/T complete; L pending** for `operations` and `collect` in [Operations evidence](../m4-operations.md). Current-client collect/start still requires one bounded before/reply/after observation. Continue with Task 02.

Task 01 local checkpoint (2026-10-25): App → broker → `NativeDispatchAdapter` → `CollectOperation(2)` → newer full Sync with native slot 3 removed → replan → `StartOperation("op_fence")` → newer full Sync with the selected run and 200 Cash debit passed. The test uses a fake executor. Focused suite: 82 tests passed; full offline suite: 815 tests passed, one skipped. No live calls or GitHub update.

### 02–06 — Complete Money, Property, Safehouse, Shop and Skills, in that order

These are five separate tab checkpoints, not one combined milestone.

| Task | Files to finish | Focused evidence and acceptance scenario |
| --- | --- | --- |
| 02 Money | `src/tabs/money/Module.luau`; `src/engine/FundingCoordinator.luau`, `PurchaseSavings.luau`; `src/features/BankDeposits*.luau`, `PurposeWithdrawals*.luau` | `test_money_tab.py`, `test_bank_deposits.py`, `test_purpose_withdrawals.py`, `test_funding_coordinator.py`: funded purchase competes with saving, fractional balance rounds correctly, disabled purchase never withdraws, uncertainty reserves remain held. |
| 03 Property | `src/tabs/property/Module.luau`, `NativePropertyCatalog.luau`; `src/features/Properties*.luau` | `test_properties.py`: each policy chooses an eligible quoted property, capacity/reserve block correctly, exact one-build proof rejects unrelated changes. |
| 04 Safehouse | `src/tabs/safehouse/Module.luau`; `src/features/SafehouseUpgrades*.luau` | `test_safehouse_upgrades.py`: upgrade up to selected cap, stop on level/cash restriction, replan after confirmed funding. |
| 05 Shop | `src/tabs/shop/Module.luau`; `src/features/ShopBuy*.luau`; `src/engine/ShopQuoteProducer.luau` | `test_shop_cash.py`, `test_shop_quote_producer.py`: stale rotation/changed quote aborts before send, native Auto Buy takes ownership, exact selected purchase confirms once. |
| 06 Skills | `src/tabs/skills/Module.luau`; `src/features/Skills*.luau`; `src/game/SkillsState.luau` | `test_skills.py`, `test_skills_tab.py`: each selected stat uses current cost and cap; other allocations remain unchanged. |

- [x] Complete Task 02 and record **C/T complete; L pending** for `bank` and `withdraw`. The real App settings passed fake native-adapter `BankDeposit(35000)` with 15,000 Cash kept, exact 3,500 fee and 31,500 Bank gain; `Withdraw(2000)` confirmed exact transfer and replanned one enabled Safehouse upgrade. Disabled purpose, fractional rounding, purchase savings and uncertainty are covered by focused tests. Money suite: 70 passed; full offline suite: 817 passed, one skipped. See [Bank evidence](../m5-bank-deposits.md) and [withdrawal evidence](../m5-purpose-withdrawals.md).
- [x] Complete Task 03 and record **C/T complete; L pending** for `properties`. App → broker → native adapter sent `BuyProperty("p_b", nil)` with arity two; a newer full Sync confirmed one selected count increase, unchanged other counts and exact 200 Cash debit. The three goal policies, quote, cap, capacity and reserve paths have focused coverage. Property suite: 13 passed. See [Property evidence](../m5-property-build.md).
- [x] Complete Task 04 and record **C/T complete; L pending** for `safehouse`. The Task 02 App/native-adapter path confirmed `UpgradeSafehouse()` at tier 3 with exact 3,000 Cash debit, then a tier-4 cap prevented another request. Focused Safehouse/native path: 8 passed. See [Safehouse evidence](../m5-safehouse-upgrades.md).
- [x] Complete Task 05 and record **C/T complete; L pending** for `shop`. The current native quote producer now accepts finite fractional server time while retaining rotation checks. App → producer → broker → native adapter sent `BuyShopItem("w_a", nil, 120)` and confirmed the selected stock marker, one item, one bought count and exact 120 Cash debit from a newer full Sync. Native Auto Buy, stale rotation and changed quote block through focused tests. Shop/call suite: 25 passed. See [Shop evidence](../m5-shop-cash.md).
- [x] Complete Task 06 and record **C/T complete; L pending** for `skills`. App → broker → native adapter sent `AllocateSkillPoint("energy", 2)`, and a newer full Sync confirmed two allocations, exact two-point debit, unchanged other stats and no send after the selected cap. All current cost rules, point limits and rejected/changed quote paths have focused coverage. Skills suite: 9 passed. See [Skills evidence](../m4-skills.md).

### 07 — Rewards

Files: `src/tabs/rewards/Module.luau`, `NativeRewardsSource.luau`; `src/engine/RewardsProofProducer.luau`; existing Playtime/GroupBonus/MonthlyRewards readers, planners and evidence.

- [x] Wire current source data and all three settings through App; current eligibility/wait reasons are visible. The saved monthly config remains disabled.
- [ ] Finish every reward-effect variant. Group property-income modifier is now source-bound and C/T complete; fixed Cash/items/Gold/Seals, refills, fresh XP, mystery and source-enabled Monthly require exact effects. Unsupported ready rungs do not starve supported rewards. Income-based Cash and active XP extension rules remain unknown; saved Monthly is disabled. Marker suppression, membership freshness and UTC rollover remain covered. See [Rewards effects](../m16-reward-effects.md); whole Rewards C/T and all L remain open.
- [x] Run `test_playtime_claims.py`, `test_group_bonus.py`, `test_monthly_rewards.py`, `test_native_rewards_source.py`, `test_rewards_tab.py` with an App-to-fake-remote scenario for each control. `ClaimLadder(5)`, `ClaimGroupBonus()` and synthetic future-config `ClaimMonthly()` all reached native adapter and confirmed their exact markers. Fixed `NativeCallPlan` to accept the actual `YYYY-MM` monthly key; focused Rewards/Runtime/Call suite: 92 passed.

### 08 — Events

Files: `src/tabs/events/Module.luau`, `EventShopBlocked.luau`; `src/features/FreeBriefcases*.luau`. Create `src/tabs/events/EventShopState.luau`, `EventShopBuy.luau`, `EventShopEvidence.luau`, and `NativeEventShopCatalog.luau` after grounding their fields in saved source.

- [x] Finish free Briefcase settings → call → exact reveal proof; free count zero must never spend a key. App/native adapter sent `BriefcaseAction("open", 2)`; `source="free"`, one free-pick decrement, the selected new reveal and preserved prior reveal confirmed from a newer full Sync. `briefcases` C/T complete, L pending. Focused Events/Briefcase suite: 9 passed.
- [ ] Extract current Event Shop offer/window, medal origin restrictions and native purchase shape; implement selected reward, reserve and attempt cap with default off.
- [ ] Replace the blocker descriptor only when real reader/planner/evidence exist. Add `tests/test_event_shop.py`; extend `test_events_tab.py` and `test_free_briefcase_picks.py`.
- [ ] Test closed window, changed price, restricted origin, insufficient medals, already purchased and exact item/medal deltas. Missing source evidence remains an explicit unfinished row, not a completed disabled toggle.

Event Shop remains C/T/L incomplete. **Superseded October 27:** the complete place extraction contains `EventShopTab` and `EventShop`, including offer definitions, medal-origin handling and `EventShopAction("buy", key, 1)`. The old filtered-export absence was not a place-wide absence. Revisit implementation using [the recovered sources](../source-coverage-2026-10-27.md); no further broad log dump is needed for those shapes.

### 09 — Contracts

Files: `src/tabs/contracts/Module.luau`, `ContractGoalState.luau`, `ContractGoalBlocked.luau`; current ContractEntries/ContractBonuses modules. Create `src/tabs/contracts/ContractGoalRequests.luau`.

- [x] Complete independent entry and bonus claims against current reset identity. App/native-adapter fake flow sent exact `ContractAction("claim", 1, nil)` then separate `ContractAction("claimbonus", nil, nil)` and confirmed each marker from newer full Sync. `contracts` and `bonuses` C/T complete, L pending.
- [x] Convert supported objectives into read-only goal requests carrying selected contract, reset identity, route and observed progress. The saved Config defines `ops` as **collect finished Operations**; duration is passive `playtime`, correcting the earlier plan wording. Jobs count/energy and Operation collection routes are implemented; all remaining template keys and limits are listed in [Contract goal evidence](../contract-goal-requests-2026-10-25.md).
- [x] Add separate default-off Jobs, Operation-start and Operation-collection borrowing choices without silently enabling another tab. The tab exposes requests for Task 24 and never sends a second remote itself. `autoContracts` as a whole remains C/T incomplete until Task 24 executes requests through the shared arbiter.
- [x] Extend `test_contracts_tab.py`, `test_contract_entry_claims.py`, `test_contract_bonus_claims.py`; create `test_contract_goal_requests.py` for route selection, completion, reset and disabled borrowing. Focused Contract suite: 19 passed.

### 10 — Trophies

Files: `src/tabs/trophies/Module.luau`, `TrophyFocusState.luau`, `TrophyFocusBlocked.luau`; `src/game/EarnedTrophiesState.luau`, `src/features/EarnedTrophies*.luau`. Create `src/tabs/trophies/TrophyGoalRequests.luau`.

- [x] Enumerate the current catalog's owned/ready/progression/trade-in routes and close the two-ID claim limitation where source supports a non-consuming claim. The saved InventoryTab invokes `ClaimTrophy(item.id)` for ready trophies and borders/backgrounds; catalog set/trade-in and `requiresItems` entries remain excluded. `trophies` C/T complete, L pending; see [Trophy claim evidence](../m4-earned-trophies.md).
- [x] Add selected-goal read-only requests through the same interface as Contracts, preserve the separate claim toggle, and observe newer ready/owned state. The default-off route choices are in the UI; `trophyFocus` C/T remains incomplete until Task 24 connects shared arbitration and stops borrowing after ownership.
- [x] Extend `test_earned_trophies.py` and runtime integration; create `test_trophy_goal_requests.py`. Bound/Collection copies, unsupported routes and consuming trade-ins cannot become ordinary claims. Focused Trophy/UI suite: 88 passed, one skipped; cosmetic App/broker test also passed.

### 11 — Crew & Gear: finish eight controls before leaving the tab

Files: `src/tabs/crew/Module.luau`, `AutoEquipCrew.luau`, `CrewSort.luau`, `CrewGear.luau`, `CrewHeal.luau`, `CrewTrain.luau`, `CrewHire.luau`, `CrewHealItems.luau`, `CrewRollState.luau` and native catalogs. Create `CrewCallPlan.luau` and `CrewReplacement.luau` in that directory.

- [ ] In order: native Auto Equip, sorting, Stamina heal, item heal, training, empty-slot hire, exact gear swaps, bounded replacement/rarity improvement.
- [ ] For each, translate the existing proposal intent into its source-backed call and wire App settings; verify actual arity and sequence instead of blindly forwarding the intent's `remote` string.
- [ ] Implement one stable-member reservation shared by gear, training, healing and stationing; tab tests inject it until Task 24. Keep unavailable-home Crew protections.
- [ ] Replacement persists selected member, funded hire and attempt cap before dismissal; on uncertain dismissal/hire it stops that transaction for reconciliation. Native controller mode must stop on disable/unload and cannot borrow the ordinary replacement budget.
- [ ] Extend the eight `tests/test_crew_*.py` behavior suites and `test_all_tab_composition.py`; add `test_crew_call_plan.py` and `test_crew_replacement.py`. Required failures: member moved/replaced, item no longer loose, training capacity changed, interrupted replacement, no-op equip, unavailable native controller.

October 26 partial checkpoint: `CrewCallPlan` now owns reviewed signatures for Auto Equip, Sort, Stamina Heal, Train, empty-slot Hire and Gear. Their intents are primitive so the shared proposal validator accepts them; the saved Hire call sends the tier with two trailing nils, not the locally quoted cost. Auto Equip and Sort passed App/native-adapter fake scenarios. `CrewHeal` now reads source-backed heal cost/duration from a Crew-enriched snapshot. The full tab remains unfinished: item healing lacks a saved member-targeted remote, Auto Roll/replacement need bounded controller ownership and stop/reconciliation, and shared stable-member reservations await Task 24. See [Crew contract gaps](../crew-contract-gaps-2026-10-26.md). No live Stamina call was made.

### 12 — Inventory

October 27 Crew follow-up: [replacement evidence](../m15-crew-replacement.md) supersedes the historical hire argument omission and missing replacement-component claim. The new ordinary one-dismiss/one-hire store, settings and tab route pass a durable App/native-adapter cycle. Native controller start remains blocked because the saved call has no spend cap. Whole Crew C/T remains open until Task 24 installs live lifecycle/counter/reservation hooks; 73 Crew cases and the 1063-test full run pass.

Files: `src/tabs/inventory/Module.luau`, `Cosmetics.luau`, `Chests.luau`, `Restoratives.luau` and native catalogs. Create `InventoryCallPlan.luau` and `PlayerItemSequence.luau` in that directory if current source requires the sequence owner.

- [x] Finish cosmetics, unbound chest opening and all supported restorative routes with actual call descriptions and complete App custom settings. `InventoryCallPlan` owns the saved signatures; the App/native-adapter fake exercised all three controls.
- [x] Separate the player item clock from Crew item healing; honor native cooldown and sequence, useful recovery threshold, batch/cap and bound-first policy. Each full Sync supplies the player sequence; no extra cached owner is needed. The native crate luck rule now supplies a same-Sync proof.
- [x] Extend the Inventory feature tests and `test_inventory_call_plan.py`; add source/producer and App scenarios. Exact unbound crate loss, reward IDs, no useful recovery, cosmetic ownership vs display, changed sequence and reload are covered. See [Inventory checkpoint](../m4-inventory.md). `cosmetics`, `chests` and `restoratives` C/T are complete; L is pending. Cross-feature item reservations remain Task 24.

### 13 — Collection

Files: `src/tabs/collection/Module.luau`, `CollectionDonate.luau`, `NativeCollectionCatalog.luau`; `src/engine/CollectionProtection.luau`. Create `src/tabs/collection/CollectionCallPlan.luau`.

- [x] Wire ordinary base-item deposit to the saved `CollectionAction("deposit", id, count)` signature and count existing `@variant` Collection custody in its tier calculation. The saved config has five Collection count tiers (1, 10, 100, 1000, 5000), correcting this plan's earlier seven-tier assumption. Preserve worn/spare and bound custody and confirm exact newer-Sync movement.
- [ ] Integrate unfinished Crew and Market transaction reservations through Task 24's shared seam. The current protection proof covers selected Gear/Cosmetic plans; an injected item reserve reduces or blocks Collection surplus, but blocked Market Sell has no active selected-sale reservation yet.
- [x] Extend `test_collection_donate.py` and `test_collection_protection.py`; add `test_collection_call_plan.py` and an App/native-adapter deposit scenario. Gear/Cosmetic protection, injected reserve and variant count cases pass. The donation-versus-live-sale transaction scenario awaits Task 24. See [Collection checkpoint](../m4-collection.md). Ordinary deposit C/T is complete; full `collectionDonate` acceptance and L remain pending.

### 14 — Heists

Files: `src/tabs/heists/Module.luau`, `BoardQuery.luau`, `BoardReadRuntime.luau`, `SequenceRecovery.luau`; existing HeistStart, HeistCollect, Sabotage reader/planner/evidence modules. Create `HeistSequenceOwner.luau` and `HeistCallPlan.luau` under `src/tabs/heists/`.

- [ ] Identify the saved client's sequence allocator and status recovery contract, including interaction with manual native activity and Favor help. The overlapping values in the supplied trace are insufficient by themselves.
- [ ] Persist owned mutation identity before start/sabotage/collect; only poll status for an owned sent sequence. Reconcile native manual advancement without guessing the next sequence.
- [ ] Implement addressable result collection; replace `HeistCollect`'s permanent blocker with an actual proposal and exact run/reward proof once result identity is established.
- [ ] Connect board proof through `NativeSnapshotReader:AttachHeistBoard` using the final shared reader interface; source changes invalidate the proof.
- [ ] Extend `test_heist_start.py`, `test_heist_collect_blocker.py`, `test_heist_sequence_recovery.py`, `test_sabotage.py`, `test_heist_board_read_runtime.py`; create `test_heist_sequence_owner.py`. Cover manual sequence advance, duplicate status, missing ledger record, wrong result, late reply and reload.

October 26 missing-fact checkpoint: saved `HeistsTab-b2b8f5308e73.lua` initializes its private sequence at zero and increments it on each native UI mutation, then polls `status` with that same value. The supplied Cobalt trace shows sequenced Heist calls but not server ownership rules. The saved result has a Heist ID and reward summary but no unique result ID; `collect` passes nil as its second argument. There is no server implementation in the saved client snapshot. A hub allocator could collide with native UI or manual actions, so start, sabotage, help and collect remain blocked; a status-only read may inspect only an already owned sent record. The exact current-client/server observation and existing fail-closed behavior are in [Heist sequence recovery](../m6-heist-sequence-recovery.md). Follow the missing-fact rule: continue offline Task 15 then Task 16; do not invent a sequence.

### 15 — Favors

Files: `src/tabs/favors/Module.luau`; `src/features/FavorHelp.luau`, `FavorHelpEvidence.luau`; `src/game/FavorsState.luau`; the Heist sequence owner from Task 14.

- [ ] Bind help to the correctly shared or separate native sequence domain established in Task 14, with exact target and board generation.
- [x] Finish tab-local policy settings, daily sent-attempt cap, Favor/Energy reserves, relation choices and native per-target help limit. App controls are default-off; proposal and send-time evidence both enforce the selected values. Shared Heist sequence remains blocked.
- [ ] Extend `test_favor_help.py`, `test_heists_favors_tab_modules.py` with interleaved start/help/manual native action and exact successful progress. Custom limits and relation tests pass offline; interleaving needs Task 14 sequence ownership.

October 26 partial checkpoint: Favors has separate configurable daily attempts, resource reserves and eligible relation choices. The saved board and durable attempt counter still determine native per-target and daily limits. No Favor send was enabled or live-tested because the private Heist mutation sequence is unresolved. Continue Task 16 under the missing-fact rule.

### 16 — Combat: Bosses, claims, Shop, then player modes

Files: `src/tabs/combat/Module.luau`, `PlayerTargetState.luau`, `HitListQuery.luau`, `BlockedFight.luau`; existing city/Global/Family Boss and BossShop modules. Create `TargetSelection.luau`, `PlayerFight.luau`, `PlayerFightEvidence.luau`, `CombatCallPlan.luau` under this tab.

- [ ] Complete six existing Boss/claim/Shop controls through current state readers, caps and exact proof. Native read sources join Task 24's shared reader.
- [ ] Implement hit-list/search/scout selection, own/Family/war exclusions, health/Stamina reserves, per-target hospitalization cooldown and sent-attack caps. Keep mugging and war targeting separate.
- [ ] Persist only necessary bounded target history; fresh evidence is required before acting. Target failure must not starve the queue. Native and custom Boss controllers must not compete.
- [ ] Extend `test_bosses.py`, Global/Family Boss suites, `test_boss_shop_buy.py`, `test_player_target_state.py`, `test_combat_tab_module.py`; create `test_player_fight.py`, `test_combat_target_selection.py`. Live Stamina/PvP tests stay outside the current authorized test window.

October 26 partial checkpoint: current-client `BossStages` plus `Config.BOSS` now derives full-Sync-bound city stage and Boss Shop proof, with a bounded 129-stage window. All six existing Boss/claim/Shop signatures are routed through a Combat-owned `CombatCallPlan`; this does not enable player attacks. City Boss/Shop state readers, Combat tab integration and the native binding pass local tests. Full suite: **866 passed, one skipped**; manifest preflight **239 modules**. Global and Family Boss board sources, player/war target controllers, current-client outcome confirmation and live verification remain open. See [Combat Boss catalog checkpoint](../m6-combat-boss-catalog.md). Continue Task 16 under the missing-fact rule; do not send live Stamina during the Territory war.

### 17 — Black Market

Files: `src/tabs/blackMarket/Module.luau`, existing quote/custody/preflight/evidence modules; `src/features/MarketReadRuntime.luau`, MarketBrowse/Prices/Rap and MarketEarnings modules. Create `MarketTransactions.luau` and `MarketCallPlan.luau` in this tab.

- [ ] Finish research and earned payout first. Research shows fresh bounded results, pagination completeness and reasons for rejected candidates; it cannot buy.
- [ ] Complete rental, owned-item listing, optional Collection withdrawal-to-list, and flip buy-to-list as separate durable transactions, in that order.
- [x] Add missing selection, item exclusions, minimum profit/demand, Gold reserve, run spend/attempt caps and rental controls to catalog/App; no budget shared implicitly between sell/flip/rent. Tab-owned `MarketSettings` projects the generic App scalars into actual existing helper shapes; this completes configuration only.
- [ ] Persist stage, listing/member/item identity, expected amounts and uncertainty before each send. Reconcile an interrupted stage before advancing; no duplicate relisting or replayed buy.
- [ ] Extend existing `test_market_*.py` suites; create `test_market_transactions.py` and `test_market_call_plan.py`. Include restart between buy/list, changed listing/price, bound copy, shop expiry, concurrent Collection protection and exact confirmed payout.

October 26 partial checkpoint: earned payout now uses tab-owned `MarketCallPlan`, a visible minimum earned Gold and nil-as-zero Gold custody in complete Sync. `MarketResearchView` reports bounded opportunities and per-listing rejection reasons from complete fresh browse data without sending. Full suite **871 passed, one skipped**; UI catalog check passed and manifest preflight scanned **241 modules**. The read scheduler/UI feed and all buy/list/rent transactions remain blocked. See [Black Market checkpoint](../m7-black-market-checkpoint.md). Continue the Task 17 transaction sequence; carry shared read ownership to Task 24.

October 26 rental custody addendum: `MarketTransactions` now persists a one-period rental baseline and pre-send `sent` stage, refuses another rental across restart, and requires exact newer shop-expiry/Gold evidence before an `observed` state. It holds ambiguous results without retry. It is not wired to dispatch; `marketRent` remains blocked. Full suite **875 passed, one skipped**; preflight **242 modules**.

October 26 owned-listing custody addendum: the same store now persists exact loose/bound item custody, price, quantity and preexisting listings before an owned listing send; state-only recovery recognizes one matching new listing and loose-item debit across a restarted session. Different price/count/custody remains uncertain and no retry is made. This is a preflight-only component: `marketSell` still has no dispatch path, and Task 24 must arbitrate item reservations. Full suite **878 passed, one skipped**; preflight **242 modules**.

October 26 durable-flow addendum: Collection withdrawal-to-list and flip buy-to-list now persist first-stage evidence, exact observed custody and origin-bearing prepared listing stages across restart. Fresh real preflights remain required; changed item/quantity/original ask/source purchase, stale snapshots, server-time regression, corrupt records and failed persistence cannot advance the lifecycle. Recovery preserves the native 3600-second age across local clock resets; explicit current `now` is required at follow-up preparation. The focused suite ran **73 tests, all passed**; full suite ran **904, 903 passed and one skipped**. UI Catalog and **242-module** preflight passed. No send path was added; this does not complete whole-Market C/T. Continue remaining Task 17 settings/wiring, retaining Task 24 reader/reservation ownership and L as open work. See the completed [batch record](2026-10-26-market-durable-flows.md).

October 26 configuration addendum: all five Market entries have tab-owned scalar controls and strict helper projections, including explicit item scope/exclusions, protected spares, optional Collection withdrawal, demand/net/margin choices and independent zero-default spend/attempt caps. Nine new tests exercise catalog→Settings/App→tab mapping, actual helper shapes, old-profile defaults, malformed choices and zero transport. Market suite **176 run, all passed**; UI/settings/profile/composition suite **83 run, 82 passed and one skipped** (overlapping suites). Catalog generation/check and **243-module** preflight passed. Parent will run full regression after integration; no new full result is claimed. The remaining concrete boundary is fresh read/custody/result ownership, shared reservations/run counters, persisted broker lifecycle hooks before dispatch, earned-payout ledger and L. Keep buy/list/rent blocked. See [configuration evidence](../m7-market-settings.md); continue Task 18, returning at Task 24.

### 18 — Family

Files: `src/tabs/family/Module.luau`, `src/game/FamilyState.luau`, `src/features/FamilyBlocked.luau`. Create `FamilyContributions.luau`, `FamilyContributionEvidence.luau`, `FamilyCallPlan.luau` under the tab.

- [ ] Extract current perk costs, contributor identity and contribution action; implement Cash, Stamina and Gold as separate descriptors and limits.
- [ ] Recheck Family membership, perk target and quote before sending. Prove own resource debit plus matching contribution; unrelated Family activity is not our success.
- [ ] Extend `test_family_tab.py`; create `test_family_contributions.py` covering membership changes, concurrent Family contributions, cap/reserve exhaustion and ambiguous shared increments.

October 27 partial checkpoint: the tab now has all three separate settings/planners, source-bound personal Family info, four-argument `FamilyCallPlan`, exact member-ledger plus own-resource evidence and a real Cash App/broker/native-adapter fake scenario. Defaults are off with zero run budgets/attempts. Stamina uses reviewed 1/5 batches and exact target progress; mixed-origin Gold remains blocked because debit order is unverified. Full suite **925 run, 924 passed, one skipped**; Catalog matched and manifest scanned **247 modules**. See [Family evidence](../m8-family-contributions.md). Whole C/T remains open until Task 24 owns current info reads, durable sent usage and shared reservations; no live spend occurred. Continue Task 19 under the integration-boundary rule.

### 19 — Territory

Files: `src/tabs/territory/Module.luau`, `TerritoryState.luau`, `TerritoryReadRuntime.luau`, `TerritoryMapQuery.luau`, `ResidencyQuery.luau`, `ReadAttachment.luau`, `TerritoryBlocked.luau`. Create `Stationing.luau`, `Residency.luau`, `TerritoryCallPlan.luau` in the tab.

- [ ] Finish read-only city map/watch first, including current capacity, season, shield, fortification and effective top-two bonuses.
- [ ] Implement own-member station/recall/recovery using shared member reservations, district capacity and home/defense protections. Training and stationing cannot take the same member.
- [ ] Implement residence comparison and move with current rent/cap and explicit previous-lease effect. If native rollback is unavailable, state that in the preview; do not invent recovery.
- [ ] Extend `test_territory_tab.py`, `test_territory_read_runtime.py`, `test_territory_map_query.py`; create `test_territory_stationing.py` and `test_territory_residency.py`. Cover city/Family change, full district, lost membership, lease expiry and interrupted move.

### 20 — Prestige

Task 19 October 27 partial checkpoint: [Territory evidence](../m9-territory.md) records all tab-specific components and the exact remaining Task 24 ownership boundary. Full suite **985 run, 984 passed, one skipped**; Territory suite **76 passed**; Catalog matched and preflight scanned **255 modules**. No live action. Continue Task 20; do not repeat the old missing-CrewRecall-source claim.

Files: `src/tabs/prestige/Module.luau`, `src/game/PrestigeState.luau`, `src/features/PrestigeBlocked.luau`. `PrestigeReset.luau` owns the tightly coupled reset planner/evidence/call description.

- [x] Complete tab-owned preview of lost level/EXP, gained rank and current requirements; add explicit reset choice and per-load limit. Actual current preview/status connection remains Task 24.
- [ ] Implement source-backed reset intent and exact rank/reset-state confirmation with durable attempt suppression. Reload cannot silently repeat an uncertain reset.
- [x] Extend `test_prestige_tab.py`; create `test_prestige_reset.py` for requirements, changed rank/EXP/catalog, caps, exact newer reset and actual late callback. Durable restart acceptance remains Task 24. See [Prestige evidence](../m10-prestige.md); no live reset.

### 21 — Jobs release parity

Files: `src/tabs/jobs/Module.luau`, `NativeJobCatalog.luau`; existing Jobs reader/planner/evidence; `preview/catalog.json`.

- [x] Check all 102 saved Job IDs/17 tiers, including Vespera and Exiles, against selected choices. Existing choices already match; generated Catalog remains current.
- [x] Verify balanced/XP/cash/mastery/selected policies, native Auto Jobs yielding, exact completion increments and current-level unlock boundaries with another completed tab selected.
- [x] Run Jobs suites and one App-to-native-adapter scenario: 41 passed. Retain earlier live Jobs evidence; new release smoke remains open. See [Jobs parity](../m11-jobs-parity.md).

### 22 — Overview, Profiles, Settings and Activity

Files: `src/tabs/overview/Module.luau`, `profiles/Module.luau`, `settings/Module.luau`, `activity/Module.luau`; `src/storage/ProfileStore.luau`, `Settings.luau`; `src/ui/EmberAdapter.luau`; `src/App.luau`; `preview/catalog.json`.

- [x] Overview: separate active feature/phase, selected blockers, unconfirmed counts/affected features and registered adapters from supplied actual runtime status.
- [x] Profiles: account/place-scoped save/preview/rename/autoload, current saved vs modified vs selected state and bounded settings JSON export/import preview. Unsupported keys and storage failures remain visible; import does not activate/save.
- [x] Settings: preserve current advertised options; fence obsolete theme callbacks, handle refused updates truthfully, reset queued selections and respect unload.
- [x] Activity: bounded public send/confirmed/rejected/unconfirmed history and actionable fixed explanations without raw reasons, request keys, credentials or account payloads.
- [x] Add meaningful utility/profile/settings regressions and retain startup/autoload/corruption/UI-error/unload scenarios. Full 1013 run, 1012 passed, one analyzer skip; independent follow-up profile review 13 passed. Named/imported sparse profiles replace missing choices with catalog defaults, and obsolete saved-name callbacks cannot change the autoload target. See [utility evidence](../m12-utility-tabs.md). Current-client UI acceptance remains open.
- [x] Read primary `docs/Ember-UI-Reference.md`; use existing pinned APIs only. No new Ember API was assumed.

### 23 — Finish the tab wiring ledger

- [x] Account for all 55 catalog controls in the [explicit route/evidence/blocker ledger](../feature-wiring-ledger-2026-10-28.md). Missing routes/cleanup/tests remain named unfinished work rather than completed features. The ledger's 55 unique IDs match the actual catalog.
- [ ] Remove placeholder-only implementations from the completed set. Keep exact unresolved evidence/decision rows open with a concrete observation request, then continue completed rows toward integration.
- [ ] Close the original parity inventory: any feature or setting not represented in the 55 controls must be restored, merged into a named current control, or explicitly accepted as out of scope. Do not silently drop legacy behavior.

### 24 — Final shared integration (global requirements kept here)

Modify: `src/engine/Broker.luau`, `AutomationRuntime.luau`, `RuntimeAssembly.luau`, `Scheduler.luau`, `ReadBudget.luau`; `src/transport/RuntimeHost.luau`, `RuntimeDriver.luau`, `NativeDispatchAdapter.luau`, `NativeRemoteResolver.luau`, `NativeSnapshotReader.luau`; `src/storage/Checkpoint.luau`. Create focused `src/engine/RequestLane.luau`, `GoalCoordinator.luau`, `ResourceReservations.luau`, and `src/transport/ReadCoordinator.luau` only for responsibilities not already provided by an existing module.

Planned shared interfaces (new interfaces, not claims of existing functions):

```lua
-- RequestLane owns scheduled and invoked work, not server cancellation.
lane:TryAcquire(kind, actionKey, deadline) -- token or nil, reason
lane:Owns(token)                        -- boolean
lane:Release(token, outcome)            -- boolean; stale token cannot release a newer owner

-- Goals choose existing feature planners; they never invoke remotes.
goals:Resolve(context, settings, requests) -- effective feature goals, visible reasons

-- Read coordinator returns only snapshot-bound staged results.
reads:Step(snapshot, enabledReads)      -- status
reads:Close()                          -- fences queued/late results
```

- [x] Reserve the shared request lane before deferring a callback. Mutation, shared read and native membership queues acquire/fence ownership before native invocation; future recovery hooks must use the same lane.
- [x] Reconcile the native resolver with 45-second mutation expiry. A two-coroutine regression proves an expired physical call cannot block or clear a newer owner; the broker retains duplicate exposure and cooldown. This is logical release, not physical cancellation. See [shared request/read integration](../m17-shared-request-reads.md).
- [x] Apply bounded read deadlines/backoff and fair scheduling. Hung-query logical expiry cannot indefinitely hold the lane; expired generations cannot populate caches or release a newer lease. This never cancels a physical invocation.
- [x] Connect actual Heist board, Family info/Boss state, Global Boss attributes, Market research and Territory map/district/Residency/fort reads to staged sources/shared ownership. No caller-supplied proof is promoted without source identity/freshness validation.
- [x] Bind actual Event Shop native rows/MW and account attributes/native clock through RuntimeHost. Preserve tab-owned direct-emission guard through composition; recheck changes before queued invocation and refund only known-unsent work. See [host and queue evidence](../m28-event-shop-host.md). Restart/migration/L remain open.
- [x] Bind actual Territory SeasonLive/native SeasonRules.status and verify holder bonus sources through native Sync/assembler/App. Native calendar fallback is explicit; stamped facts cannot substitute another season number. Source closes on host/tab unload. See [Territory host evidence](../m29-territory-season-host.md).
- [x] Display selected district garrison count/cap and observed shield time from matching accepted facts. Changed selection, Family, snapshot or outside-map details cannot substitute another district; missing cap stays unknown. See [detail and cleanup](../m30-territory-detail-and-unload.md).
- [ ] Complete remaining source/controller acceptance: player/war targeting, Family reward/hit-back, broader Territory Family deployment capacity, and recorded Heist/result contracts.
- [ ] Implement resource/item/member reservations and transaction ownership across training, healing, stationing, Collection, Market, Shop, Bank and goals.
- [x] Connect actual Crew replacement owner, funded hire/member reservations, persistent cycle usage, pre-send/direct-emission/reply/outcome hooks and exact saved-checkpoint reconciliation through App/reload. Disable/settings changes stop continuation; close fences old callbacks. Callback-only success, missing replies and unrelated state never become proof. See [runtime](../m31-crew-runtime-owner.md) and [saved outcomes](../m32-crew-saved-outcomes.md).
- [x] Expose explicit paused review/recovery for known-unsent prepared Crew records, failed immediate preflights and separately proven rejected hire. Exact adapter evidence handles the write-ahead/unload no-invocation window without old-owner main-file/CP writes. Unknown sent outcomes remain held. Native Auto Roll remains outside the bounded route; warning now depends on actual owner/review capability after verification. See [explicit recovery](../m33-crew-explicit-recovery.md).
- [x] Actual guarded Crew item healing, local numbered unsent-action recovery, earned Market payout/confirmed ledger and bounded one-period rental now have actual App/reload acceptance. Rental caps persist with pending custody; paused reset is explicit; exact Gold plus observed-time extension bounds required. See m34–m37. This does not close native recall/Heist allocation, trading, migration or L.
- [x] Persist full original intent, complete planning snapshot and captured feature baseline atomically with custody/usage. JSON-safe bounded data retains numeric/sparse keys. Lightweight metadata avoids planner-path payload copies. See [pending data](../m22-pending-action-data.md).
- [x] Persist current native returned results without treating them as confirmation. Conflicting/malformed later values preserve the original baseline; stopped/deadline-passed callbacks cannot write. Same-scope file commits/reloads are fenced against yielding-write interleaving. See [saved returns](../m23-returned-result-durability.md).
- [x] Add explicit Settings preview/confirm for current-scope Event Shop/Family run counters. Paused, no pending/held assets, exact scope/totals and expiring single-use preview required; no profile/startup reset, no gameplay call. Resume is fenced during save. Selected completed keys clear only after success; server retry cooldowns remain. Release migration remains separate. See [allowance reset](../m27-explicit-allowance-reset.md).
- [ ] Implement feature-specific cross-session reconciliation. Own recall request-ID highwater, disarm stale callbacks, discard only known-unsent prepared records, and retain sent uncertainty. Release/pin migration must explicitly reconcile compatible old pending records rather than hiding them in a new release scope. Legacy records without full baselines/results remain unresolved.
- [x] Capacity-only prerequisite moved forward when Event Shop brought the package to 258 and the complete inert bundle failed at the old cap. `src/loader/Manifest.luau` and `tools/build_release_manifest.py` now consistently allow 512. Both boundary tests accept 512/refuse 513; oversized loader input performs zero fetch/compile. Loader/builder/inert-bundle suite: 22 passed. Keep modular files; gameplay coordination stays here.
- [ ] Use recovered source identities: `healId` for member healing and `dutyToken`/`dutyAt` for deployments. Do not substitute a slot or nonunique name when source supplies a stable action identity. Recheck Crew healing's new guarded payload/cost/sequence before enabling its routes. Season `SeasonLive`/native `SeasonRules.status` and read-only `fortview` tab connections are now implemented; their L remains pending.
- [ ] Implement goal arbitration with manual settings, Heists → Favors → Operations priority, Contract/Trophy goals and optional event preference. Respect borrowing choices; one effective action and visible origin, no hidden enable.
- [ ] Finish recovery/late-callback/session-change behavior for all stateful actions and propagate exact reasons to UI. All-off startup and explicitly enabled autoload remain as specified.
- [x] Family contribution info and budget owner are connected. Limits are charged atomically with pending actions and persist through reload; caller usage is discarded. App captures per-feature choices at admission; disable/changed choices cancel only known-unsent dispatches and safely restore their charge. Other feature changes do not cancel the action; duplicate callbacks cannot send or refund twice. Full-intent recovery/reset/migration and cross-feature reservations remain open. See [Family runtime](../m18-family-runtime.md).
- [ ] Tests: extend engine broker/session/recovery/scheduler, runtime host/driver/loop, all-tab composition and App suites; create `test_request_lane.py`, `test_goal_coordinator.py`, `test_read_coordinator.py`, `test_resource_reservations.py`.

Required cross-feature integration assertions:

```text
queued read + admitted write -> exactly one current owner before either callback runs
mutation at t=0, no proof at t=45 -> skipped/unconfirmed; other eligible work can proceed
old callback after new owner -> no outcome/cache/checkpoint change for new owner
training + station + gear on same member -> one reservation, other actions wait
Collection + Market sale of same copy -> one custody owner, exact remaining quantity
Contract goal + manual Jobs -> one Jobs request, visible effective goal, no double spend
disable/unload during queued work -> zero new native calls; stale callbacks fenced
autoload all-off/custom-enabled/corrupt -> respectively idle/run selected/fail closed visibly
```

### 25 — Local release package and current-client test build

Files: `tools/build_release_manifest.py`, `Loader.luau`, `Bootstrap.luau`, `ReleaseAdapters.luau`, `ExecutorEntry.luau`, `RuntimeEntry.luau`, `manifest.json`; current-release evidence notes.

- [ ] Review and locally commit completed source. Build the manifest from that exact commit; never repin uncommitted or guessed bytes. Verify module count against the loader limit and keep all imports in the recode.
- [ ] Run full suite, module compilation, complete-cache/offline fallback, corrupted hash, partial download, interrupted startup, reload and rollback tests. Record any skipped gate and its reason.
- [ ] Produce a clear feature availability list from actual C/T status. Keep unresolved rows visible and unfinished; do not call the release full parity while any intended feature remains incomplete.
- [ ] Publish the reviewed modules/manifest/entry to the existing preview branch and PR at the final publication step, using existing user authorization subject to tool review. Attach/update the existing PR if publishing it. Do not expose private logs, tokens or account files.
- [ ] Provide one pinned loadstring and a bounded diagnostic switch so a user-run test records attempted feature, current version, reply classification and state proof without credentials.

### 26 — Current-client acceptance and final closure

- [ ] Verify current version/contract, load all modules, exercise navigation, scaling/input focus, profile autoload and unload/reload.
- [ ] In order, test an eligible earned claim, one ready Operation collection, one bounded Operation start, then each eligible non-Stamina action with before/reply/after data. Test one feature at a time before simultaneous runs.
- [ ] For a missing source contract, provide an exact read-only diagnostic or one ordinary native UI observation to capture; do not ask for another broad log dump. The supplied logs are already available and must be used first.
- [ ] Schedule Stamina/PvP/destructive/shared-spend tests only after the applicable standing restriction is lifted or exact user scope is known. A feature may be C/T complete while its L box remains open.
- [ ] Run the planned sustained observation and mixed-feature scenarios with bounded resources, errors, reconnect/reload and 45-second uncertainty. Check no duplicate loops or competing controllers.
- [ ] Mark final completion only when every intended ledger row has C/T/L evidence, every advertised control works, the current pinned GitHub loadstring contains it, and remaining explicit exclusions have been agreed rather than inferred.

## Evidence and decision queue

| Item | Work to complete before asking the user | Exact remaining user/client input if still necessary |
| --- | --- | --- |
| Heist/Favor sequence and result identity | Inspect saved allocator/recovery source and existing traces; implement allocator/recovery tests | Narrow current allocator/status/result observation if the saved source cannot establish the contract. |
| Event Shop / Family / Territory missing contracts | Find current native handler, quote source and before/after fields; build off-default modules | One specific eligible native UI action trace or read-only state observation for the missing field. |
| Market, replacement and shared spending | Complete previews, explicit budgets, custody, per-step recovery and injected tests | Which item/member/resource may be used and its cap for the live trial, only if existing permission does not cover it. |
| Prestige/PvP | Complete offline implementation, preview, limits and recovery | Exact live reset/attack scope; no blanket account access interpreted as permission. |
| Stamina | Finish all code and fake-clock scenarios | User ends the Territory-war no-Stamina restriction before live consumption. |
| Current release verification | Prepare the pinned package and minimal diagnostics | User runs it and supplies focused results; MCP remains unused. |

## Continuation instruction

**Next action: independent item-specific Market sale reads, then owned-item listing usage/lifecycle/recovery and paused review UI; withdrawal/list and buy/list afterward.** m34–m39 completed actual Crew item acceptance, local numbered definite-unsent recovery, earned payout/confirmed ledger, bounded rental caps/source/reset/App acceptance and stale-envelope fences (1292 run, 1291 passed, one analyzer skip; 277 modules). Source follow-up identifies the native Market presence gate as a manual challenge/lockout; listing must stop for native user resolution, not fabricate a position or completion proof. Next native recall/Heist allocation, defender/admission ownership, execution/release migration and goals remain separate from local request IDs. Preserve unresolved PvP/reward/origin contracts, broader Family capacity and Task 23 old-setting parity. Whole-Crew/trading/Family/Territory/Prestige/Event Shop C/T remain unfinished on recorded acceptance. Tasks 01–06 remain C/T complete; tests are not feature counts. See [Market runtime plan](2026-10-28-market-runtime.md) and [Crew plan](2026-10-28-crew-runtime.md).
