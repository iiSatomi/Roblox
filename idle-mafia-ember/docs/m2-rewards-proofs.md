# Rewards source proofs (offline)

`RewardsProofProducer` accepts a release-matched, injected `rewardsSource`. `source:IsWeekend(serverNow)` must use the current native `DailyBuffRules.isWeekend` result at the replicated server time. The producer computes the UTC day and attaches `{active, day}` to that same Sync. The saved client uses `DailyBuffRules.isWeekend(ServerClock.now())`; a copied weekday guess would miss configured overrides.

`source:Membership(account, groupId)` must return a **cached** boolean from the current player's native `IsInGroup` check plus its local monotonic `checkedAt`. The producer accepts it only for the current account, configured Group ID and a check no more than 30 seconds before Sync capture. Membership lookup should run outside the quarter-second planner tick because the native call may yield. The saved Property UI calls `player:IsInGroup(Config.GROUP.id)` before showing the joined state.

`src/tabs/rewards/NativeRewardsSource.luau` now implements this read-only contract for an injected current `DailyBuffRules` module and a separately invoked player-membership lookup. `Refresh(account, groupId)` caches only a boolean and the monotonic completion time for the configured account/group; it prevents concurrent refreshes, clears a failed lookup and never runs inside `RewardsProofProducer`. `Close` clears the cache. Offline fake tests feed both proofs through the producer.

`RuntimeHost` now schedules at most one asynchronous refresh when a full Sync sees missing or older-than-20-second membership. It also exposes `RefreshGroupMembership` for a manual retry. A callback queued before unload is fenced, and `NativeRewardsSource.Close` discards an in-progress result. The current `DailyBuffRules` module and player lookup are still not bound.

`AutomationRuntime` removes snapshot-supplied `weekendBuff` and `groupMembership` before asking this source. With no source or stale membership, the corresponding claim stays blocked. The refreshed membership becomes eligible on a subsequent full Sync; scheduling or completing the lookup is not itself a claim result. Current-client rule equivalence and actual claim outcomes remain unverified.
