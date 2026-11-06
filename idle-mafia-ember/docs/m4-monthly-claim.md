# Monthly earned claim: dormant offline slice

Saved client `0.26.487.1` `DailyRewards` lines 35–104 computes UTC
month/day and a 30-day maximum from `data.monthly`; `MonthlyCalendar` lines
190–215 checks `Config.MONTHLY_CALENDAR.enabled` and sends
`ClaimMonthly:InvokeServer()` without arguments. The saved `Config` has
`MONTHLY_CALENDAR.enabled=false`, so the current saved build gives no usable
monthly claim path. This is client evidence, not a server result.

`MonthlyRewardsState` requires a matching fresh complete Sync, an enabled
current config, trusted server UTC time, a valid monthly record and distance
from the UTC-day boundary. `MonthlyRewards` proposes one exact month/day/next
claim only when separately enabled. `MonthlyRewardsEvidence` requires a
successful reply plus newer same-day full Sync whose monthly claimed count
increases by one and whose lastDay matches that UTC day. A reply alone,
month rollover or changed day stays pending. No catch-up, calendar purchase
or fabricated elapsed time is included.

The fake runtime/UI displays the native-disabled reason. Synthetic tests
exercise an enabled future config, but do not establish that such a config
exists live. The distributed inert UI 0.1.1 remains unchanged. Current
transport, response, server validation, actual reward and live UI behavior
are unverified.
