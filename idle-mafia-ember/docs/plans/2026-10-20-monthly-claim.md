# Monthly earned claim: disabled-config offline slice

Saved client `DailyRewards` lines 35–104 computes UTC month/day and next
claim from `data.monthly`; `MonthlyCalendar` lines 190–215 checks
`Config.MONTHLY_CALENDAR.enabled` and sends `ClaimMonthly:InvokeServer()`
without arguments. The saved `Config` has `enabled=false`. No usable claim
is implied for that build.

1. Test a fresh complete Sync reader with trusted server UTC timestamp,
   current config-enable flag, valid monthly marker, 30-day cap and
   midnight/month boundaries. Disabled config must block.
2. Test a separately enabled proposal for one exact UTC month/day/next-day
   identity, with no catch-up/purchase action.
3. Test successful reply plus newer complete Sync showing the same-month
   claimed count advanced by one and lastDay matching the original UTC day.
4. Add optional fake-runtime/UI status wiring; keep the inert bundle and live
   claim status unchanged. Record the source/config limitation.

**Status:** All four offline tasks implemented and locally verified against
synthetic enabled/disabled snapshots. The current saved config disables this
feature; native adapter, server response, actual claim and packaging remain
open.
