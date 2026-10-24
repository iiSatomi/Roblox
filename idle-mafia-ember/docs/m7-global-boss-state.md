# Read-only Global Boss event state

`GlobalBossState` accepts a same-account/snapshot current event and
local player-ID proof alongside a full native Sync. It derives the
saved client's `id_startAt` run key, keeps personal damage/hits only
when `native.gb.run` matches, applies public/private test access,
and classifies pending, live, exhausted, expired, settling and done.
Live remaining HP follows the saved rules: maximum HP minus recorded
damage and linear time decay. A done result is claimable only with
matched participation, an unclaimed personal record, access and the
seven-day results grace window.

The view is optional shared Context data. It sends no `attack`,
`claim` or board request, and it does not add an action descriptor.
The adapter-supplied event shape, runtime clock, actual permissions
and server outcomes need live verification. This local slice passes
286 Python/Lupa tests and changed Luau compilation/old/new analysis;
the default Ember 0.1.1 remains inert.
