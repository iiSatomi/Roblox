# Earned playtime ladder: offline claim slice

Saved client `0.26.487.1` `SafehouseTab` lines 391–405 and 596–622
reads `playtime.todaySeconds` and `laddersClaimed`; lines 832–852 call
`ClaimLadder:InvokeServer(index)`. The UI estimates elapsed time after a
Sync, but `PlaytimeState` uses only replicated seconds. `Config.LADDER`
contains seven rungs at 300, 900, 1800, 3600, 5400, 7200 and 10800
seconds, with level tiers 1, 10, 30 and 102. `DailyRewards` lines 113–157
resolves level and weekend variants using server time. The 90-minute
reward is a weekday XP boost or weekend 3 Gold Bars; later rungs include
Mystery and a bound Consumables Crate.

`PlaytimeState` requires a fresh complete matching Sync, current seven-rung
catalog, server UTC day, valid claimed markers and adapter-supplied
same-day weekend state. It chooses the first ready unclaimed rung.
`Playtime` sends only that rung index through the shared fake broker.
`PlaytimeEvidence` requires a successful reply and a newer complete Sync
on the same UTC day with the selected rung's claimed-tier marker. A reply
alone stays pending. The marker proves claim state, not the exact prize
contents. No elapsed-time spoofing, energy refill or crate opening runs.

The Playtime panel can show fake-broker status; the distributed inert 0.1.1
bundle is unchanged. Local evidence: 168 Python/Lupa tests, 12 Node tests,
catalog-generation check, changed Luau compilation and both analyzer modes
pass. The future native adapter must supply trustworthy `weekendBuff`
and current catalog fields. Native transport, actual response shape, award
observation and live UI/gameplay remain unverified.
