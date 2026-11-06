# Live validation — 2026-11-06

These observations come from the manager-owned Potassium session. Offline tests
do not substitute for a feature's live outcome. Development payloads are private
and are not published release pins.

Confirmed live paths now cover **17 of 55 feature switches (31%, rounded)**,
up from the **0 of 55** recovery baseline. This counts switches with a confirmed
path; other modes, lifecycle checks and unmet prerequisites remain open. The
integrated development source was pushed as
`491ca8967867a50b4170ccd852da6257f4777ab8`; final manifest/entry packaging is separate.

## Observed

- Jobs: exactly one `DoJob("j_watch")` returned `ok=true`, 3 XP and 89 Cash.
  The runtime then confirmed the newer native Job completion state. It ended
  paused with no storage fault and zero uncertain actions. The earlier attempt
  was cancelled before native invocation; it did not run a second Job.
- Operations: exactly one `StartOperation("op_fence")` returned `ok=true`.
  The newer native state confirmed the owned running entry and exact 200 Cash
  debit. After server readiness, one `CollectOperation(1)` returned 26 XP and
  1996 Cash; the runtime confirmed the owned run's removal and reward state.
  No uncertainty or storage fault remained.
- Fresh runtime startup placed the Ember window in PlayerGui automatically.
  The successful Operation test had no UI error. A restart after the confirmed
  Job loaded paused with no pending record or replay.
- Playtime: exactly one `ClaimLadder(2)` returned `ok=true, robux=false` and the
  newer native marker/reward evidence confirmed it. The fractional-seconds
  reader repair was required for this account. No uncertainty remained.
- Bank: one native deposit was confirmed by the runtime's exact receipt/state
  validator. The journal records 1629114103 game Cash deposited; the account's
  native no-fee entitlement was true. Passive income increased the excess above
  the initially planned 1000-Cash margin. The diagnostic hook used the wrong
  remote label, so it did not separately print the raw receipt; there was one
  admitted/sent/returned/confirmed journal sequence and no uncertainty.
- Reviewed native clients 654 and 655; the game reconnected from 655 to 654.
- Ember UI booted, then the modular runtime booted paused with all switches off.
- Prestige controller identity checks passed. The account is level 92; the next
  reset requires level 200. No reset was submitted.
- Combat and player-stat native bindings returned current data. War status had
  no active war or scoring targets; no attack was submitted.
- Heist board and native sequence controller reads succeeded. Starting the
  cheapest run requires 25 Energy; the observed account had 22. No start,
  sabotage, or collect mutation has yet been submitted.
- Favors: one native `help` action used sequence 1 with a one-attempt daily
  limit. Its durable reply returned `ok=true`, 165000 Cash and 183 XP. The
  exact newer board confirmed the help; the native total increased from 1312
  to 1313. Persisted daily usage is one attempt, the transaction is inactive,
  and the runtime ended paused with no storage fault or uncertainty.
- Contracts: exactly one `ContractAction("claim", 2, nil)` returned `ok=true`,
  one Seal and 10364580262 game Cash. The previously completed daily
  `c_punchclock` row became claimed in newer native state. The runtime confirmed
  it and ended with zero uncertainty and no storage fault.
- Market rental: exactly one `MarketAction("rent", 1)` opened the shop for
  twelve hours. Loose Gold stayed 320 and bound Gold decreased from 25 to 24.
  The old evidence rule left the successful send uncertain. After reviewed
  total-Gold evidence and reservation fixes, a normal restart reconciled the
  original saved receipt against a genuine newer full Sync. Pending records and
  uncertainty became zero, with no storage fault or second rental. Persisted
  usage still records one attempt and one Gold spent.
- Family Cash: one `FamilyAction("donate", 100, nil, nil)` returned success.
  The runtime confirmed the exact personal donation counter and Cash debit,
  with one-attempt/100-Cash limits. The own donation counter increased from
  3650000000300 to 3650000000400. No uncertainty or storage fault remained.
- Family Stamina: one `FamilyAction("contribute", "enforcers", 1, nil)`
  returned success and advanced the selected perk progress from 32446 to 32447.
  Exact resource, personal counter and perk evidence confirmed the action under
  a one-Stamina/one-attempt limit. No uncertainty or storage fault remained.
- Family Gold: one `FamilyAction("donategold", 1, nil, nil)` returned success
  with `allowNativeGoldPool=true`, amount 1, total reserve 438, run budget 1 and
  maximum one attempt. Loose Gold stayed 415; bound Gold decreased from 24 to 23,
  making the combined balance decrease exactly from 439 to 438. The personal
  `donatedGold` counter increased from zero to one. The runtime confirmed the
  exact receipt and newer state, retaining one attempted donation with zero
  uncertainty and no storage fault. This observed debit does not establish a
  general server payment priority; the loose-only default remains unchanged.
- Market earnings: one `MarketAction("collect")` returned 95 Gold. Earnings
  became zero; loose Gold increased from 320 to 415 and bound Gold stayed 24.
  The runtime confirmed the exact payout, with zero uncertainty and no fault.
- City Bosses: one ordinary `BossAction("stageAttack", 1)` defeated the stage.
  The reply reported 10 Tokens, one Loot Crate and 148 XP. Exact newer stage
  and resource evidence confirmed the single hit; no uncertainty or fault remained.
- Boss Shop: after the separately documented unsent test-wrapper recovery and
  clean restart, one `BossAction("shopBuy", "crate_loot", 1)` bought one crate.
  Tokens decreased from 6544 to 6530 and exact inventory evidence confirmed the
  purchase. Persisted session attempts are one; uncertainty and storage faults
  are zero.
- Territory district and residency view requests returned current data. Recall
  sent one owned request for member slot 33 in `jade_harbor_053`, with a
  one-attempt limit and minimum garrison 31. The initial reply was pending;
  status-only resolution and newer roster state subsequently confirmed it.
  The member returned home. No uncertainty or storage fault remained.
- Territory Watch: a coherent report was sampled across 60 seconds with accepted
  native map/district reads and zero mutations. It showed 15 of 112 city districts
  held, Family capacity 15 of 15, season 2 in preparation, and selected-district
  garrison 59 of 200 with bonuses and shield data. No fault or uncertainty remained.
- Restoratives: one `UseConsumable("con_medkit_large", true, 111)` returned
  success with gain 67 and Health 300 of 300. Newer native state showed Health
  rising from 233 to 300, bound Medkits decreasing from four to three and
  consumable sequence advancing from 111 to 112. The bounded test enabled only
  Health recovery with minimum useful gain 10; one attempt confirmed with no
  uncertainty or storage fault.
- Anti-idle 1.0.0 was installed in Potassium autoexec. Sixty-four input
  pulses succeeded with zero failures. A later check reached 96 successful pulses.
  This is observed activity, not a guarantee
  against future disconnects or server restarts.

## Bugs reproduced by live testing

1. A bounded single-Job test was refused before dispatch because recovery data
   exceeded the 262144-byte encoder budget. Removing the duplicate `data` alias
   helped but was insufficient for the fully enriched runtime snapshot. The
   exact private failing record is retained for diagnosis. A Jobs-specific
   evidence projection now passes that record's capture/decode/recapture check
   without raising storage limits. No Job was sent during the failing probes.
2. In a coroutine that returned from a wrapped native request, Ember's input
   getter failed with a missing `Plugin` capability error. The same getter
   succeeded in a fresh executor call. No identity or capability was changed.
   Native callbacks now queue observations for the UI owner's timer. A live
   probe also verified that moving our window from CoreGui to PlayerGui allows
   the getter to succeed immediately after the same wrapped request; startup
   integration subsequently passed the live Operation and Favor tests.
3. Ember's disabled-storage configuration still attempted a theme read. The
   adapter now disables the existing storage configuration before configuring
   Ember; the regression is covered offline.
4. Recall startup assumed the persisted account name was a numeric user ID.
   The current client now supplies its verified numeric ID separately while
   retaining the existing account-name storage keys. The patched runtime
   booted successfully and the bounded Recall subsequently confirmed.
5. Territory map requests use native city IDs, while district catalog entries
   use display names. The adapter now resolves IDs through the native CityMaps
   lookup. Territory capacity's native `checkedAt` ordering marker was also
   incorrectly compared to a seconds timestamp. Both fixes have regressions;
   live acceptance of the patched report remains open.
6. A manager-owned Boss Shop test wrapper asserted the wrong command name
   before calling the native resolver. Its zero-attempt witness established no
   native invocation, but the outer runtime conservatively retained request 15.
   Following independent review, the manager appended the exact original
   request/baseline through `Checkpoint.RecordUnsent`. Normal recovery recorded
   `recovered_unsent`, removed the pending record and rolled back that unsent
   attempt. No raw checkpoint edit, invented game reply or token change was used.
   This one-off instrumentation recovery does not make unknown executor errors
   evidence of non-invocation.

## Still open

The integrated frozen source passed 913 Python tests and 465 subtests, with one
optional analyzer skip. All 298 source modules plus Bootstrap and Loader compiled
and passed their development SHA-256 checks in Potassium (300 files). These checks
do not replace the remaining live gameplay outcomes.

The 17 switches with a confirmed live path are Jobs, Operation start, Operation
collection, Playtime, Bank, Favors, Contracts, Market rental, Family Cash, Family
Stamina, Market earnings, City Bosses, Boss Shop, Station/Recall, Family Gold,
Territory Watch and Restoratives.
The other **38 of 55** remain unverified live; no partial or blocked result is
counted as another completed switch.

Market Watch remains unverified: real browse replies succeeded, but pagination
restarted before a complete current report became available. The manager is
capturing the read timeline; no trade was sent by this watch probe.

Remaining per-feature successful action/receipt/new-state validation, broader
live lifecycle/restart checks, and publication of the integrated feature changes.
The recovery, anti-idle and
startup-cleanup commits have been pushed to `codex/idle-mafia-recovery`.
Screenshot capture timed out twice; no screenshot was
produced. Features with missing account/event prerequisites remain unverified.
