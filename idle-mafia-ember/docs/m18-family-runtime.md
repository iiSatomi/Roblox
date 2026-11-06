# Family contribution runtime checkpoint — October 28

Family Cash, loose-only Gold and selected-perk Stamina now have connected current-info reads and durable independent budget ownership in the local release worktree. This is offline implementation and fake-client integration; no live contribution, Stamina use or publication occurred.

## Current data and limits

The Family tab contributes one `familyInfo` source to the shared `ReadCoordinator`: exact `FamilyAction("info")`, five-second interval, the existing bounded read deadline/backoff and no independent mutation loop. Accepted info is pinned to the source key, full Sync header, current Family and account's numeric actor ID. The proof keeps only personal counters and bounded perk maps. Pending/rate-limited replies, old generations, changed membership and wrong source keys cannot attach; every new Sync invalidates old info. Tab closure fences its query.

`FamilyContributionUsage` owns three separate attempt and resource-exposure totals. Checkpoint writes the selected charge and pending action atomically before scheduling. Its proof replaces caller-provided usage. Confirmed, rejected or uncertain invoked attempts retain their charge; these totals are conservative budget exposure, not a report of resources actually spent. Corrupt/missing lanes, unsupported saved usage, stale counters and failed persistence fail closed.

Limits survive reloads in the same account/place/release scope. Reload, profile change and feature toggling do not start a new allowance. There is no automatic budget-reset operation. Release migration and explicit reviewed reset/recovery remain open shared work; do not hide a pending old release record by repinning.

Only a definite known-unsent scheduling refusal or pre-invocation cancellation refunds its exact reserved charge. The rollback checks that later usage has not advanced. It removes the pending record and restores the budget in one write. Negative server replies and the 45-second unconfirmed outcome never automatically refund it.

## Last pre-invocation preference check

App supplies a read-only snapshot of the selected feature's own values to `AutomationRuntime:SetSelectionGuard`. Broker binds those values at admission and checks them immediately before native invocation. Disable, pause, changed amount/policy/limits or an applied profile can cancel a queued action without issuing a remote; changes to another feature do not cancel it.

This cancellation has a separate local callback and journal outcome, `cancelled_unsent`; it is not a fabricated server reply or server cancellation. Native dispatch callbacks are single-use. A duplicate callback cannot refund an already invoked action. Actual invoked/unconfirmed actions still retain their original first-send +45-second deadline, duplicate exposure and cooldown.

The Family UI now reports actual runtime status instead of its obsolete permanent “not connected” label. That field only renders text; execution still depends on enabled settings, current source/evidence, selected reserves/budgets/attempts and shared broker ownership. All feature switches and default contribution budgets remain off/zero. The [current Ember documentation](https://rbx.lol/docs/ember) and workspace reference were rechecked; no Ember API or dependency was changed. Automatic review initially rejected the presentation change as live spending; source inspection established its read-only role and the smaller presentation-only patch passed review. No live permission was inferred.

## Evidence and remaining work

Tests run the actual App, tab descriptor, source query, native snapshot attachment, shared lane, checkpoint and fake native adapter for all three currencies. They confirm exact four-argument calls, personal receipts and newer resource debits; preserve limits and uncertainty through reload; ignore forged usage; restore known-unsent budgets; fence unload/disable/amount changes and duplicate callbacks.

Full regression: **1134 run, 1133 passed, one external official-analyzer skip**, 30.895 seconds. Catalog matched JSON; manifest preflight scanned **266 unique modules**; scoped patch whitespace checks passed. Published entry remains `9da6d31`.

Whole-Family C/T remains open for cross-feature funded-Cash/item reservations, full-intent recovery, explicit allowance reset/release migration and final shared acceptance. Mixed loose/bound Gold still lacks a proven debit-order contract. All current-release L results remain pending; live Stamina remains outside the authorized test window. Continue Task 24 with the remaining shared sources/reservations and recovery hooks.
