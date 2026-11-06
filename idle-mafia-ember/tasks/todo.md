# Single execution queue

Follow [plan.md](plan.md). This replaces competing historical queues, not their technical requirements.

## Current checkpoint — recovered-drive merge, November 6

- Use the recovered r35 files as the baseline. The earlier recovery is preserved
  on `codex/idle-mafia-recovery`; reviewed changes have been ported onto the newer
  architecture. See [the current recovery report](../docs/recovery-2026-11-06.md).
- All 55 controls are available with fresh switches off. Runtime activation still
  requires native compatibility and valid saved-state ownership; historical
  unresolved actions and allowances must not be discarded to bypass migration.
- Original and merged UI startup have been checked in-game with automation off.
  Historical live coverage is 19/55 controls, not a claim of full gameplay coverage
  for this merged release. Final release verification is recorded in the report.
- The sections below are recovered historical evidence. Earlier narrow approvals,
  publication holds and r34 pins describe that earlier session, not this release.

## Historical r34 checkpoint (preserved)

- Current r34 source6ca721a28f00e5185804d47e4d3051e4970a96c9,manifest6a56cec5a8fa64a096b4efa1f68a821d77930dbc,entry280c790c3017cd326d7e69da0e43e2d0a157ed9e.3458 source passed/0 skipped,136.868s;309 compiled,303 modules,official analyzers,catalog/manifest and12 preview passed. Extracted3458 run:3377 passed/81 explicit private-capture skips,136.902s. Archive r34 functional/extracted/entry identity and private-capture exclusion verified. Jobs/city Bosses entry only;unpublished.
- Implemented/local:UTC daily rollover preserves raw Sync/owned allowances/unknowns;ordinary confirmed Scout survives temporary list invalidation with128-row/1800s bounds and still needs fresh owned roster/profile;War current-roster boundary retained. Exact reviewed current FightTab fingerprint admitted;6 used request/confirmation fragments match,ProfilePopup unchanged,busy guard reviewed.50 focused native Combat cases pass. No arbitrary hash,pristine/native-owner or challenge guard relaxed.
- Live/build655:r34D one Scout+Attack confirmed,win/Cash190609392/actual Attack Stamina1;r34E separate new Job+Scout+Attack confirmed,win/Cash356904179/actual Attack Stamina1. Each has independent Scout/Attack exposure5,one attempt each,pending0,closed,its100-Cash setup exactly restored. Prior targets/consumed Job markers not replayed. Same-source real-file all-off reload preserves both allowances and exact settled receipt,zero RPC. Broader modes,live interruption/challenges and historical migration remain unaccepted.
- Test accounting:200 Cash in exact r34B deposits left in Bank;600 Cash positive-only deposits lack exact retained effects(r33:200,Combat r34B:100,Combat r34C:100,Favor r34B:100,Favor r34C:100);keep those uncertain. D/E restored their own200 only. No unrelated Bank delta assigned or historical unknown cleared. r34C sent0 Combat because private fixture required2 profiles;D/E reuse one valid profile and eliminate redundant refresh transfers.
- Favor follow-up/build655:one new Job confirmed,zero Help,pending0,closed. Actual App diagnostic accepts current native Favor board and same-day usage;terminal guard is No eligible Favor help. Native board51 runs,only1 Friend/Family run and above current level92;eligible related0. Current quote1 Favor/2 Energy fits the8-Energy cap. Level-up setup is33309 XP away vs12-140 eligible-tier help XP;do not grind/consume items for setup. Two positive100-Cash setup deposits lack exact retained effects and remain uncertain.
- Next executable:.private/favor-mixed-r34d-cached.luau,prepared/compiled,NOT dispatched. Requires an existing unexpired Friend/Family Heist with required level<=92 and an unused help slot;user asked asynchronously to notify when one is available. One free owned preflight precedes any setup transfer;quote0..8 Energy must match the actual proposal. Caps1 Favor/8 Energy plus1 distinct new Job/max1 Energy,no Stamina/items/start/collect/replay. Prior mixed/proof scopes closed,pending0,helps0;never repeat their confirmed Job or reset usage. Native connection is ready;last console486;no active test.
- Canonical details:docs/native-sync-acceptance-2026-11-05.json(currentFollowup.combatScoutHandoff.r34). Preserve original Lin8 home,slot9 missing unique healId,all old nonempty custody/allowances,user-held Prestige/War/Family-less/Heist Energy/XP stacking,Monthly-disabled source and missing damage/income/residence facts. No whole-feature completion from these bounded successes;broader activation/publication gates remain.

## Active feature acceptance checklist

- [x] Server-transfer implementation/local acceptance: owned OnTeleport shutdown, queued/physical interruption, exact unsent new-server recovery and Heist/Recall unknown custody. Natural live transfer acceptance remains unconfirmed; no automatic reload or replay.

- [x] Heist/Favor quote handoff, exact old goal scoring/selection/limits and inert import acceptance; native protocol/recovery is implemented; external acceptance remains below.

- [x] Read-only saved-state review before activation, Crew scope discovery, zero-write actual inert Ember acceptance; historical reconciliation remains open.

- [x] City Boss full reviewed selection, optional bounds and independent confirmed encounter caps/local-clock delay, including old unnumbered recovery and interrupted cleanup.

- [x] Global Boss health/buffer/delay and independent fractional/zero per-load send caps; cooldown changes preserve terminal/claim evidence and durable event caps.

- [x] Alliance/Enemy local utility:24 acceptance tests; native directory query separately live-probed. Actual inert Ember UI/profile/unload plus nonempty real-file all-off new-Host autoload accepted in recorded source scopes; gameplay/release migration remains. Shared final-preflight yield race fixed; blocked hostile lanes remain blocked.

- [x] Legacy restorative per-pool/zero-disable/fractional intent, exact Family1-or5 amounts and confirmed multi-perk rotation; independent review and actual App lifecycle/recovery acceptance.

- [x] Read-only Player tab: native stats/property provider, confirmed hub-mug rate sampling, zero-send App acceptance, stale/source/identity fences and unavailable trust labeling; 15 focused tests including 3 App cases.

- [x] Ordinary Combat source/view/planner/settings/Attack/Scout, exact immediate accepted-terminal/graceful-close recovery and ordinary active-war exclusions: 343 scoped cases, 103 App cases, 26 actual planner cases. Unknown outcomes without durable terminal proof, native/manual ownership and executable/live acceptance remain open; separate war actions stay unmapped.

- [x] Exact lookup of retained owned ordinary identities: explicit source opt-in, 11 query/11 App cases and current native schema checked read-only. Custom/default high-value memory and high-first fallback are accepted below; historical migration remains open.

- [x] Owned custom/default high-value rules, high-only and optional high-first/ordinary-fallback selection, fair explicit lookup and durable recovery:61 high-value/27 saved-search tests. Four legacy high-value preferences import inertly; historical records remain held for reconciliation.

- [x] Current string Family identity: owned claim reads, exact award custody, disable/unload, saved recovery and attack allowance persistence; bounded selection rejects ambiguous mixed ID domains. Native whole-feature gaps remain below.

- [x] Review-before-port completed for all 13 shared incomplete controls; Station review failures reproduced and corrected. Per-control decisions: docs/parity.md. Monthly Rewards is new-only.

- [x] Legacy Station maximum-deployed cap: replicated plus saved uncertain targets, exact cancellation/confirmation/restart and inert import acceptance.

- [x] Inert legacy sale exclusions and explicit withdrawal-off: strict conversion/review and actual listing/Collection App guards accepted.

- [x] Property selected-ID/level/Highest-tier and exact saved-build acceptance: 23 actual App cases; ordinary builds only.

- [x] Operation selection/bounds/six goals and exact saved-start acceptance: 32 actual App cases; separate collection switch preserved.

- [x] Trophy city-specific mastery/property selection through existing ordinary planners and exact eligible-proposal priority.
- [x] Broader Property/selected-claim acceptance and borrowed personal Heist start/collection through real tab composition; native progress and independent opt-ins/caps preserved.
- [x] Fresh-chunk registry ownership and old-owner write/callback fencing within tested same-client scopes; historical/cross-release migration remains below.
- [x] Scoped first-adoption migration:23 explicit reviewed preference exclusions, exact preserved-source receipt, truly empty older checkpoint acknowledgment, production real-file profile/save/autoload/reload/unload; all switches off, pending0. Nonempty older custody/usage is not adopted.
- [ ] Remaining nonempty historical migration, executable/mixed gameplay and publication acceptance.

## Remaining controls, ordered by tab

Finish a tab before advancing unless an exact recorded dependency prevents all remaining work. Completed scopes are not listed again. Each row links to the full remaining acceptance in the inventory.


### Heists

- [ ] `heists` - One approved native start confirmed; broader mixed gameplay and historical reconciliation remain. Old r11 unknown remains held, no replay.
- [ ] `heistCollect` - One approved collection and exact saved-receipt recovery confirmed; broader mixed gameplay and historical reconciliation remain.
- [ ] `sabotage` - Fresh owner Family proof and Alliance/Enemy policy implemented; current-client gameplay/mixed acceptance and historical reconciliation remain. Missing membership proof still holds.

### Favors

- [ ] `favors` - Earlier one-help approval consumed. Current r34 board/day proof accepted but no eligible related run;negative,level-up and mixed Help gameplay acceptance remain. Level92 needs33309 XP;eligible-tier help XP12-140. See current checkpoint for exact setup/compiled preflight.

### Combat

- [ ] `familyBossAttacks` - Native hit-back calculation/helper required; actual mutation remains unavailable
- [ ] `familyBossClaims` - User put the unavailable Family-less historical-reward setup/test on hold. Local implementation retained.
- [ ] `combat` - Bounded current Custom Scout/Attack plus Job/Scout/Attack and same-source real-file allowance/receipt reload accepted. Broader modes/native interruptions/challenges,historical nonempty custody/allowance reconciliation and production release migration remain;used or ambiguous native Scout provenance refuses.
- [ ] `warCombat` - User put active-War setup/gameplay acceptance on hold. Local implementation retained; missing exact Attack cost still refuses.

### Territory

- [ ] `station` - One exact-member Recall confirmed. Ordinary Station currently refuses because deployed slot9 lacks a stable native identity;no restoration sent. Native city mapping/storage and transfer/custody tests pass. Broader gameplay/historical provenance remains.
- [ ] `residency` - Bounded admission/recovery accepted; effective resident/Family composition and optimization source remain

### Prestige

- [ ] `prestige` - User put remaining live quote/reset acceptance on hold until level200. Local implementation retained; no reset authorized or sent.

### Rewards

- [ ] `playtime` - Native income-Cash claim observed; general formula/rounding absent, automatic income-Cash remains guarded. Fixed-award precision corrected; XP stacking stays guarded.
- [ ] `monthlyRewards` - Saved native calendar disabled; current enabled-source acceptance required

### Trophies

- [ ] `trophyFocus` - Personal Heist start/collection and mixed Contract/Job routes accepted locally; Favor/Sabotage and consuming/manual routes stay separate. Current Contract/Jobs route accepted live(three Jobs,48→51);borrowed-Heist Energy setup user-held(max22<25),other goal combinations remain.

## Shared closure and release (no feature points)

- [x] Native Heist/Recall highwater and Combat/Prestige/controller ownership implemented in bounded scopes. Current-client gameplay and historical unknown ownership remain separate gates below.
- [x] Contract/Trophy arbitration for the already accepted ordinary routes; preserve manual choices and priority.
- [x] Personal Heist goal routes use the implemented native owner; actual tab composition, rejection, disable/unload, saved recovery and mixed arbitration accepted. Current-client mixed-goal verification remains below.
- [ ] Finish other feature-specific saved recovery and fresh-execution ownership/release migration, then mixed-feature acceptance.
- [x] All231 legacy settings have explicit dispositions:146 reviewed mappings,84 deliberate exclusions,one schema marker;127 declared routes. Six extra Shop/Bank fields have validated scoped dispositions. This is import disposition coverage, not historical reconciliation or full old-control parity.
- [ ] Local commit-pinned entries and source-only publication tree prepared/tested; broader activation,current-client acceptance and final GitHub publication remain gated.
- [ ] Current-client verification: navigation/profiles/autoload/unload, then exact per-feature outcomes and combined runs. Record live evidence separately; respect current scoped/broad user authorizations,held setups and native challenges.

## Blocker register

Current source follow-up: build654 used Combat/Scout/confirmation hashes, PrestigeModal, complete Heist and Recall sources match reviewed contracts; Player-info display expressions/data shapes match. The native Heist120-second/no_pending loop and Recall allocator are now guarded by source-owned leases; they are not delegated as unbounded workers. Monthly remains disabled. After the next daily reset, one tier4 Cash rung was claimed with native positive reply/marker and observed wallet increase; general Cash formula/rounding remains unproved. See docs/native-cash-reward-2026-11-05.json. FamilyBossView hash-only does not resolve its missing hit-back bound. See docs/native-server-transfer-2026-11-04.json and prior evidence; unexamined contracts retain their guards.

Heists/Favors: source-owned shared native counter/epoch, terminal-only status, complete result identity and exact start/collect/Favor/Sabotage recovery are implemented in NativeHeistLease/HeistProtocol. The old r11 start stays held after a server/controller change. A separate specifically approved start and collection were confirmed once; both allowances are consumed. One separately approved Favor help is also confirmed. Missing: broader mixed gameplay, Favor rejection/level-up bonuses and Sabotage outcome acceptance. Local checkpoint IDs never substitute for native sequence ownership; no replay of the old start. See docs/native-ownership-2026-11-03.json.

Family attacks: build654/0.26.645.1 FamilyBossView hash matches the prior inspected source. The inspected view does not calculate a prospective hit-back bound; hitBack is used from the returned attack animation result. Config percentages/scaling do not establish the server formula, rounding or maximum. The state read was in-Family with zero claims and no attack bound. String Family IDs are now accepted without coercion through read/planning/evidence/checkpoint paths; missing native damage proof still prevents actual attacks. Current evidence: docs/native-remaining-contracts-2026-11-01.json.

Family claims after leaving: explicit inFamily=false historical rows with a supplied earlier week now work through query/reader/runtime and exact award recovery; no former Family identity is fabricated. Missing: an existing Family-less historical reward setup and current-server claim outcome acceptance. The user previously had no such setup available; do not leave a Family to manufacture one.

When blocked, record: feature | exact missing fact | source/file/range already checked | smallest required observation | independent next step. Do not use absence of live access to postpone feasible offline implementation.

Old-script reuse check (October 31): `mafia/Residency.lua:195-219` supplies the ported home/deployed count constraint. `mafia/Heists.lua:H.begin/H.request` uses a session-local counter and status call; it does not establish ownership against current native counters. `mafia/FamilyBoss.lua` supplies existing free-charge/Ticket/resource guards, without the missing current hit-back calculation. Preserve those native blockers; old mutation code is not proof of current native arbitration or settled outcomes.

Current migration evidence (updated November5): local Potassium contains435 diagnostic snapshots plus the journal, ending October17 at ID311384. The connected client has newer diagnostics. Its current100-row journal (nextId352448) contains56 confirmed labels and44 response_received rows; all44 are corroborated zero-cost board/info/state queries. The earlier interpretation as44 unresolved mutations was incorrect. Legacy history remains incomplete, and the actual older-release Ember checkpoint plus consumed allowances still require scoped migration review. r18 now supports explicitly reviewed first adoption when exact legacy bytes still match and the old checkpoint is genuinely empty. Actual production-root real-file profile save/autoload/reload/unload passed with all switches off and pending0; original files preserved. Nonempty old receipts/usage still refuse. Do not delete legacy files, reset usage or replay old actions. See docs/local-potassium-log-review-2026-11-05.json and docs/native-ownership-2026-11-03.json.

## Deferred

Unrelated refactors, appearance redesign, generalized frameworks, redundant audits, automatic cleanup of retained evidence and speculative optimizations. No deferred item is work unless it becomes a demonstrated prerequisite or the user requests it.

Player/war Combat: Ordinary Attack/Scout, separate budgets/history/receipt persistence plus atomic source-owned native busy/gateway ownership implemented; cleanup retains unknown token/proxy custody. Separate War targets/Scout/Attack policy, source-owned scoring/caps, independent allowances and exact result/lifecycle integrated; shared native Combat owner implemented. Remaining: Current automated gameplay/mixed-feature acceptance and historical unknown/custody/allowance reconciliation; used or ambiguous native Scout provenance refuses. Active War roster/profile/correlated scoring and result acceptance unavailable; missing exact Attack cost refuses.

Territory Recall: NativeRecallLease and RecallRuntime now preserve native highwater, same-controller provenance, status-only recovery, full roster/slot custody and interruption/rejection/disable handling. Unknown_request is not replay authority. Manual challenges remain native. One approved exact-member Recall is confirmed. Missing: broader Station/Recall/mixed acceptance; earlier unprovable native activity cannot be adopted. See docs/native-ownership-2026-11-03.json.

Residency optimization: ResidencyPanel-8b0f262596b3.lua returns native kind/share/rent and explicitly warns when landlord rent >= share. ResidencyRules-09374078d55b.lua supplies resident share; TerritoryBonusRules-234e0dc21c97.lua selects the top two Family holder bonuses and caps per-kind values. Supplied client code does not establish the server composition/counterfactual rule between resident and Family bonuses. Missing fact: effective before/after same-kind total including holder caps for a candidate/previous residence. Bounded explicitly selected admission/replacement is implemented, without claiming automatic effective optimization or rollback.

Prestige (live acceptance on user-requested hold): Durable reset attempts plus atomic native busy-cell ownership protecting both native reset entry guards; physical custody survives45second logical release/unload until return. Actual App fake-native acceptance implemented. Remaining: Exact positive current-server reset reply and integrated gameplay acceptance remain unverified; no live reset sent.

Rewards: Config-e0542a83bbf3.lua supplies LADDER_CASH_MINUTES=15 and LADDER_CASH_FLOOR=10000; DailyRewards-88e624cc4b74.lua displays minutes of income. No supplied server handler establishes the exact selected income base/rounding or extension of an already-active XP boost. Missing facts remain those exact formulas/receipts; supported fixed items/refills/first XP boosts and their exact saved recovery proceed. November3 read-only Config on place-version653 again confirmed MONTHLY_CALENDAR.enabled=false; the remaining reward-source inspection was Config0.26.635/place648. DailyRewards still leaves income Cash as minutes/flat and supplies no active XP extension formula; keep these exact gaps and the calendar gate. The user chose to keep active XP stacking guarded; do not activate/consume a boost for a probe. See docs/native-remaining-contracts-2026-11-01.json and the focused acquisition record.

Trophy source/acceptance: saved ItemsData/GameData/Config establish city mastery/property targets and distinguish personal Heist completion from Favor/Sabotage awards. Personal Heist start/collect goals now reuse the native owner through actual TabComposition; exact native progress/readiness remains the only goal-completion evidence. The registry no longer drops goal controllers.27 actual mixed App cases cover independent borrowing/ordinary switches,selection/caps,rejection,45-second unknowns,same-owner status recovery,queued and in-flight unload,newer checkpoint preservation and Contract-to-Job arbitration. Favor/Sabotage goals remain separate/guarded; no invented Trophy threshold or readiness.
