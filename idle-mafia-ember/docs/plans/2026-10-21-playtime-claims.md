# Earned playtime ladder: offline slice

Status 2026-10-21: offline reader, planner, evidence, fake-runtime/UI
integration and focused/full checks complete. See [claim evidence](../m4-playtime.md).
Native adapter and live server outcome remain open.

Saved client `SafehouseTab` lines 391–405 and 596–622 reads
`playtime.todaySeconds` and `laddersClaimed` for readiness, then sends
`ClaimLadder:InvokeServer(index)` around lines 832–852. Its UI adds a local
`sinceSync()` estimate; automation will wait for replicated seconds instead.
`Config.LADDER` lists seven thresholds and reward variants; `DailyRewards`
lines 113–157 chooses the level tier and weekend override using
`DailyBuffRules.isWeekend(ServerClock.now())`.

1. Add failing tests for fresh complete Sync, seven current rung definitions,
   ascending thresholds, level tiers, current UTC day, and adapter-supplied
   same-day weekend state. Resolve the actual 90-minute XP versus weekend
   Gold kind, 120-minute Mystery and 180-minute bound crate.
2. Emit one separately enabled, ready and unclaimed rung-index proposal.
   No estimated elapsed-time claims or purchase/refill actions.
3. Require successful reply plus newer same-UTC-day complete Sync with the
   selected rung's claimed tier marker. A reply alone stays pending.
4. Wire shared fake-runtime/UI status, run focused/full checks and record
   missing native adapter/server evidence. Do not rebuild the inert bundle.
