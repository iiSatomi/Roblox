# Idle Mafia Ember feature inventory

Bounded implementation and external acceptance are separate. Current source has41 Local and14 Partial scopes; no overall completion percentage is claimed. See the machine-readable inventory for each feature's supported behavior and exact remaining requirement.

Current source:3458 passing tests,zero skips;303 modules/27 UI tabs;309 compiled files;12 preview tests. r34 extracted:3377 passed/81 explicit private-capture skips. Native bounded Custom Scout/Attack and Job/Scout/Attack confirmed;all-off same-source real-file reload preserved allowances/receipt with0 RPC. RuntimeEntry remains Jobs/city Bosses only;no publication. Current checkpoint:[tasks/todo.md](../tasks/todo.md).

## Counting rules

- Local: configuration and documented App/fake-native-adapter or read/display acceptance for the named bounded scope, with exact expected effect. This does not imply every variant, complete shared integration or server-observed success.
- Partial: substantial components/tests exist, but named controller, source, recovery, ownership or variant requirements are incomplete.
- Blocked: the advertised action cannot be completed through the current descriptor/call path. Previews, planners and read-only data may exist.
- Release-complete requires local scope, shared integration, intended parity, a packaged entry and current-client acceptance. These uneven work packages do not receive an invented overall percentage.

## Tab inventory

| Tab | Local | Partial | Blocked | Remaining controls |
| --- | ---: | ---: | ---: | --- |
| Overview | Utility scope | - | - | Current-client navigation/status/autoload/unload acceptance |
| Player | Utility scope | - | - | Native data provider checked read-only; full new in-game Ember UI/release acceptance remains |
| Heists | 0 | 3 | 0 | Start personal Heists, Collect Heist results, Heist sabotage |
| Jobs | 1 | 0 | 0 | Release migration and current-client acceptance |
| Operations | 2 | 0 | 0 | Release migration and current-client acceptance |
| Favors | 0 | 1 | 0 | Help with Favors |
| Combat | 4 | 4 | 0 | Mug players, Fight war targets, Use free Takedown attacks, Claim Takedown rewards |
| Crew & Gear | 8 | 0 | 0 | Release migration and current-client acceptance |
| Inventory | 3 | 0 | 0 | Release migration and current-client acceptance |
| Collection | 1 | 0 | 0 | Release migration and current-client acceptance |
| Money | 2 | 0 | 0 | Release migration and current-client acceptance |
| Property | 1 | 0 | 0 | Release migration and current-client acceptance |
| Safehouse | 1 | 0 | 0 | Release migration and current-client acceptance |
| Prestige | 0 | 1 | 0 | Prestige when ready |
| Shop | 1 | 0 | 0 | Release migration and current-client acceptance |
| Black Market | 5 | 0 | 0 | Release migration and current-client acceptance |
| Family | 3 | 0 | 0 | Release migration and current-client acceptance |
| Territory | 1 | 2 | 0 | Station my Crew, Choose my residence |
| Contracts | 3 | 0 | 0 | Release migration and current-client acceptance |
| Trophies | 1 | 1 | 0 | Work toward a trophy |
| Skills | 1 | 0 | 0 | Release migration and current-client acceptance |
| Rewards | 1 | 2 | 0 | Claim playtime rewards, Claim monthly reward |
| Events | 2 | 0 | 0 | Release migration and current-client acceptance |
| Profiles | Utility scope | - | - | Inert real-file save/reload/selection/sync/unload accepted; production activation/autoload remains migration-gated |
| Settings | Utility scope | - | - | Current-client navigation/status/autoload/unload acceptance |
| Activity | Utility scope | - | - | Current-client navigation/status/autoload/unload acceptance |

## Every gameplay control

All current-release live checks remain pending. This table preserves bounded scope and remaining work rather than treating an available call as completion.

| Control | Status | Implemented scope | Still needed |
| --- | --- | --- | --- |
| `jobs` | Local | Local bounded; actual App acceptance for native city membership (11), inclusive level/current-cost bounds (13), Job count/capacity-aware Highest tier/named mastery (16), shared reserve/queued guards and existing exact native progress confirmation | Shared goals/current release smoke; native Auto Jobs yielding retained |
| `operations` | Local | Local bounded; 32 App cases: selected IDs, optional level/duration/primary-crate bounds, six goals, exact slot/cash and saved-start recovery without replay | Shared goals and release acceptance |
| `collect` | Local | Local; `CollectOperation`, exact slot removal | Shared goals and release acceptance |
| `heists` | Partial | Owned native sequence, exact quota/run custody, borrowed Contract/Trophy routes and purpose-bound Bank funding accepted locally; one additional approved current-client start confirmed. | Broader mixed gameplay and historical unknown/custody/allowance reconciliation; the old r11 start remains held without replay. |
| `heistCollect` | Partial | Exact original run/result, owned awarded XP, full item-origin custody and completed positive-receipt recovery across server changes; late board proof rechecked for the same fresh Sync. | Broader mixed gameplay and historical unknown reconciliation; current acceptance covers the one specifically approved result. |
| `favors` | Partial | Owned shared native sequence/call mapping, native capped quotes, exact resources and XP projection, interruption/rejection/recovery implemented. | One specifically approved positive help confirmed on build654; current-client rejection, level-up bonus and mixed-gameplay acceptance remain. One-use allowance consumed. |
| `sabotage` | Partial | Owned native sequence, independent caps and exact row/custody recovery; fresh board-correlated owner profiles enforce configured Alliance/Enemy choices and refuse missing friendship/Family facts. | Current-client sabotage gameplay/mixed acceptance and historical reconciliation; missing owner proof remains guarded. |
| `combat` | Partial | Ordinary Attack/Scout, separate budgets/history/receipt persistence plus atomic source-owned native busy/gateway ownership implemented; cleanup retains unknown token/proxy custody. Public profiles with complete stats no longer require absent private-only flags or Scout quotes; unknown War shields remain guarded. | Current automated gameplay/mixed-feature acceptance and historical unknown/custody/allowance reconciliation; used or ambiguous native Scout provenance refuses. |
| `warCombat` | Partial | Separate War targets/Scout/Attack policy, source-owned scoring/caps, independent allowances and exact result/lifecycle integrated; shared native Combat owner implemented. | Active War roster/profile/correlated scoring and result acceptance unavailable; missing exact Attack cost refuses. |
| `bosses` | Local | Local bounded: six reviewed build-653 legacy selection modes with one native winner quote; optional inclusive level limits; separate load/stage/day/best confirmed hit/Stamina caps and local-clock confirmation delay. Exact queued/saved/unnumbered recovery and cleanup retry idempotence accepted; durable daily attempted caps remain. | Current-client native concurrency/gameplay, historical action/custody migration and mixed-feature executable acceptance; complete selection remains reviewed-build653-specific. |
| `bossShop` | Local | Local bounded; 20 actual App tests, selected current quote, exact debit/item origin, saved recovery, held reward custody and unsent send-cap refund | Current-client/release migration; per-session cap remains explicitly scoped |
| `crew` | Local | Local bounded; Actual native Auto Equip App/shared Market/member custody, stable roster outcome and exact saved recovery | Current-client/native concurrency and release migration |
| `crewGear` | Local | Local bounded; Actual targeted native gear swaps; stable member, loose/bound/returned-item proof, pending inventory custody and saved recovery | Unidentified non-player members remain unavailable; current-client and migration |
| `crewRoll` | Local | Local bounded ordinary cycle; scoped owner/allowance/funding, emission/reply/outcome hooks, exact saved-outcome recovery, paused prepared/rejected-hire review and unload receipts through App | Whole-Crew/shared-source/current-client acceptance and execution/release migration; native Auto Roll excluded from this bounded scope |
| `crewSort` | Local | Local bounded; Actual native sort App/shared roster custody, stable member/equipment/pinned-slot proof and saved recovery | Current-client/native concurrency and release migration |
| `crewHeal` | Local | Local bounded; Actual native Stamina heal App/member-episode proof, shared reserve, exact debit/timer change and saved recovery | No live Stamina validation; current-client and migration |
| `crewTrain` | Local | Local bounded; Actual current-catalog training App, stable member/home/Cash reserve, exact debit/time bounds and saved start/completion recovery | Observed timer bounds infer client quote behavior; current-client and migration |
| `crewHire` | Local | Local bounded actual App empty-slot hire, current quote, atomic persistent attempts/Cash exposure, zero-default limits, exact saved/unsent/rejected recovery and paused allowance reset | Legacy pending hire migration, current-client quote/identity/native concurrency and publication |
| `crewHealItems` | Local | Local; actual App/adapter, member/origin reservations, native Crew sequence/cooldown and exact saved-outcome recovery | Concurrent native UI/current-client acceptance; execution/release migration |
| `cosmetics` | Local | Local; exact background/border calls/custody | Cross-feature item reservation acceptance |
| `collectionDonate` | Local | Local; ordinary surplus deposit, exact loose custody and actual App preservation of saved Market listing copies plus user spares | Acceptance alongside future active Market selling and remaining Crew workflows; current-client/release acceptance |
| `chests` | Local | Owned unbound crate batches, actual luck/custody plumbing, optional persistent total allowance independent of batch size;29 actual-App allowance cases cover interruption/rejection/unload, exact recovery, initialized-count corruption, legacy unknown usage and paused reset. | Current-client crate/luck/custody outcomes, historical reconciliation and executable release activation. |
| `restoratives` | Local | Local; per-pool Off/Shared/Balanced/Small/Large policies, exact fractional thresholds and legacy zero-disable/baseline thresholds; Balanced minimizes waste before size, preserving bound-origin priority; actual App queued disable/unload acceptance | Shared item/pool ownership; keep player/Crew sequences separate |
| `bank` | Local | Local; exact fee/deposit App scenario | Shared purchase and transaction reservations |
| `withdraw` | Local | Separate Heist, Property, Operation, Safehouse and Cash Shop purpose permissions; actual wrapped eligibility, queued retarget/disable checks and durable pending-purpose holds. | Current-client purpose-funding/purchase acceptance and historical custody/allowance reconciliation. |
| `properties` | Local | Local bounded; 23 App cases: selected IDs, inclusive level bounds, Highest tier, exact quote/other ownership and saved-build recovery; replacement excluded | Shared funding and source acceptance |
| `safehouse` | Local | Local; exact upgrade/cost/cap App scenario | Shared funding and release acceptance |
| `prestige` | Partial | Durable reset attempts plus atomic native busy-cell ownership protecting both native reset entry guards; physical custody survives45second logical release/unload until return. Actual App fake-native acceptance implemented. | Exact positive current-server reset reply and integrated gameplay acceptance remain unverified; no live reset sent. |
| `shop` | Local | Single, all, selected and category Cash offers; native stale/absent rotation semantics, exact price/rarity/owned caps, scoped Bank permission and durable cumulative Cash allowance. Actual App success/rejection/recovery, disable/unload, uncertain custody and independent caps accepted locally. | Passive-income purchase confirmation still requires exact debit/authoritative charge evidence; Gold lane, live gameplay and historical allowance carryover remain guarded. |
| `marketWatch` | Local | Local bounded read-only research; actual shared pagination/RAP/history, filters/terms/aging and App display | Current-release L; cached/partial coverage shown; no trading |
| `marketSell` | Local | Local bounded ordinary loose-item and opted-in unbound Collection surplus listing; actual App/broker/adapter, exact effects, separate attempts, saved/unsent/rejected recovery and paused observed-item release; inert legacy item/kind/rarity exclusion migration reaches actual listing/withdrawal dispatch guards without attempt charges | Current-client verification, shared release migration and publication |
| `marketFlip` | Local | Local bounded actual App buy/owned-list lifecycle; independent research, ordinary-Gold budget, per-copy listing caps, exact effects, restart/unsent/rejection/paused recovery | Current-client acceptance, shared release migration and publication |
| `marketRent` | Local | Local bounded one-period App/runtime/source/loose-Gold custody, durable caps and paused reset, exact saved-reply/bounded-time effect | Current-client timing/Gold scope/L, execution/release migration; no permanent entitlement |
| `marketManage` | Local | Local; actual earned-payout App/adapter/restart, exact aggregate transfer and idempotent confirmed ledger | Current-client L/release; individual historical sale attribution is not established by aggregate payout |
| `familyCash` | Local | Local bounded; actual App/read adapter, exact saved contribution/debit and rejection recovery; independent persistent limits, unsent refund and shared reserves | Release/profile migration and current-client acceptance |
| `familyStamina` | Local | Local; exact native batches1or5, optional known-ID multi-perk rotation in native order, maxed/nonfitting skips, confirmed-only session cursor and exact saved recovery; independent persistent limits/custody; inert single/multi-perk legacy import including runners default | Release/profile migration and authorized current-client Stamina verification |
| `familyGold` | Local | Local bounded loose-only Gold; exact member receipt/debit, saved recovery, persistent limits and shared origin custody | Mixed-origin native debit order remains unknown and blocked; release/profile migration and current-client acceptance |
| `familyBossAttacks` | Partial | Partial; free-only planner/call/evidence and saved allowance support exact numeric/string Family IDs; fresh query exists but injected attack-bound proof is cleared at actual Combat boundary | Native hit-back calculation/helper absent from supplied client; Config percentages/scaling alone do not establish a safe bound |
| `familyBossClaims` | Partial | Explicit Family-less historical claims supported with native inFamily=false and original historical week/source; no former-Family inference. | Existing Family-less historical reward setup unavailable; current-client claim acceptance pending. |
| `territoryWatch` | Local | Local bounded; actual App/shared map, district, fort, season and holder-bonus reads; independent Family capacity/unknown/over-cap display and ownership conflicts | Current-client read/display and release acceptance; zero mutation |
| `station` | Partial | Station/Recall custody and independent attempts, source-owned native CityMaps selection, exact four-argument map reads and status-only settlement; one approved member Recall confirmed through actual App. | Broader Station/Recall/mixed gameplay and historical native provenance; observed transaction breadcrumb is retained for normal next-owner cleanup. |
| `residency` | Partial | Partial; 22 actual App cases for owned admission, explicit request/replacement consent, exact native lease/rent, independent persisted caps, saved/rejected/unsent recovery and paused reset | Effective resident/Family bonus stacking and comparison source contract; release/profile migration and current-client acceptance |
| `contracts` | Local | Local; exact entry claim/App scenario | Shared integration and release acceptance |
| `bonuses` | Local | Local; separate exact bonus claim/App scenario | Shared integration and release acceptance |
| `trophies` | Local | Local; earned non-consuming claim/App scenario | Shared integration; consuming routes are excluded from this scope |
| `skills` | Local | Local; current cost/stat/cap App scenario | Shared integration and release acceptance |
| `playtime` | Partial | Partial; supported reward markers plus exact effects, App saved refill recovery, restart-clock ordering and partial/negative holds | Exact income-based Cash amount/rounding and active XP-boost extension rule; migration and current-client acceptance |
| `groupBonus` | Local | Local; membership + exact income-modifier activation/App | Actual membership/read ownership in shared lane; no auto-join |
| `monthlyRewards` | Partial | Partial; source-gated supported reward effects and exact saved recovery/negative markers; saved native calendar remains disabled | Saved native calendar disabled; current enabled-source acceptance required |
| `autoContracts` | Local | Actual tab-composed goal arbitration for explicitly borrowed, already-enabled Jobs, Operations/start+collect and personal Heist starts. Native objective progress stays separate from ordinary action success. | Historical/profile migration and current-client mixed-goal acceptance; unmapped/manual objectives remain excluded. |
| `trophyFocus` | Partial | City mastery/property and selected ready claims plus personal Heist start/collection through the actual shared native owner and tab composition.27 new mixed App cases cover opt-ins,limits,progress,rejection,unload,recovery and contention. | Favor/Sabotage and consuming/manual Trophy routes remain separate/guarded; historical/profile migration and current-client mixed-goal verification remain. |
| `globalBossAttack` | Local | Local bounded: owned event/source, exact hit evidence and durable25-attempt event cap plus independent optional per-load send cap, fractional/zero semantics, health/buffer and source-owned cooldown-aware2..120s preference. Queued/interrupted/rejected/unconfirmed/reload acceptance; changed cooldown preserves terminal evidence. | Current-client hit-back/settlement validation, historical migration and mixed-feature executable acceptance. Configured Health buffer is not a proven server damage bound. |
| `globalBossClaim` | Local | Local bounded: exact owned reward/custody and durable one-attempt event cap plus independent optional fractional/zero per-load send cap; known-unsent refund, rejection/unknown charge and source-change settlement accepted. | Current-client automatic settlement/award variants, historical migration and mixed-feature executable acceptance. |
| `briefcases` | Local | Local; earned free case/App scenario | Shared source and release acceptance; no paid case |
| `eventShop` | Local | Local bounded earned-only acquisitions; 13 added actual App saved-recovery/uncertainty/custody cases plus 21 existing shop cases, exact medal debit/award and independent durable caps/reset | Release/profile migration and current-client acceptance; paid or mixed medal origins remain blocked |

## Shared work - separate from feature points

Implemented and locally exercised: modular tab descriptors; all-off defaults/custom-profile autoload; shared single request lane; bounded reads; resource/item/member reservations; full pending intents/replies; 45-second skipped/unconfirmed handling; numbered definite-unsent facts; same-module stale-owner storage guards; explicit Crew recovery; persistent Family/Event/rental allowances and paused resets; bounded activity/status views. These are infrastructure, not extra finished features.

Still unfinished:

1. Feature-specific saved-outcome recovery for remaining stateful actions, retaining accepted exact Family/Event/Prestige cases while closing remaining unsupported variants and future deployment flows.
2. Native Heist/Favor sequence/result ownership and recall request highwater. Local checkpoint IDs do not solve native sequencing.
3. Remaining Crew/Boss/deployment/defender ownership, budgets, source attachment and full actual-App acceptance.
4. Contract/Trophy goal arbitration through existing planners with visible origin and explicit borrowing choices.
5. Fresh-execution ownership and release/pin migration. Same-module read/compare/write guards do not establish cross-process atomic locks.
6. Legacy parity: 231 settings are inventoried, but their dispositions remain planned rather than implemented migrations. The 55-control denominator does not claim all old settings are resolved. Paid-controller entitlement bypass is not implemented or credited.
7. A new pinned package/entry that exposes the tested features, cache/startup/rollback checks, publication, then current-client and mixed-feature acceptance.

## Ordered remaining work

Follow the single ordered queue in [tasks/todo.md](../tasks/todo.md). Completed bounded scopes stay in the inventory above; exact external blockers are recorded in that queue. Native sequence/controller implementations are locally accepted. Current work is extracted release verification; remaining gameplay/source/history gates are external and stay explicit in that queue.

## Evidence and audit corrections

The [master plan](plans/2026-10-25-completion-plan.md) links the original feature evidence. Current status is this inventory; older task checkboxes remain historical.

- Crew item healing moves from stale Partial to Local based on [m34](m34-crew-item-runtime.md), [m35](m35-numbered-unsent-recovery.md) and actual App tests.
- Ordinary Collection surplus deposit moves to Local based on actual saved-Market-copy protection in [m19](m19-resource-reservations.md). Concurrent future active Market/Crew acceptance remains open.
- Favor help, Auto Contracts and Trophy Focus move from vague Partial to Blocked action: their planners/requests exist, but missing sequence/call ownership or explicit blocker descriptors prevent execution.
- The other Local scopes retain their recorded acceptance. [Crew lifecycle](m31-crew-runtime-owner.md), [Crew review](m33-crew-explicit-recovery.md), [Market research](m21-market-research-runtime.md), [payout](m36-market-earned-payout.md) and [rental](m37-bounded-market-rental.md) provide recent integration evidence.
- These corrections are inventory changes, not newly implemented features.
- Fresh full suite: **1292 run, 1291 passed, one external official-analyzer skip**, 36.970 seconds. First restricted run had two Git-fixture access errors; rerun with read-only fixture access passed.
- Catalog matches generated Luau; manifest preflight reports **277 unique modules**. Neither modules nor test counts contribute to completion percentage.
- No live client, MCP, gameplay action, commit or publication. This is a source/test/document inventory, not a full line-by-line correctness review.
- [Machine-readable inventory](completion-inventory-2026-10-28.json). Future milestones must update named rows and show old/new counts; no unsupported overall estimate.
