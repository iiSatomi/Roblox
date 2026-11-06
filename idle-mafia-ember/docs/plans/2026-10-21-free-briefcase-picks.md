# Free Briefcase picks: offline slice

Status 2026-10-21: offline reader, planner, evidence, fake-runtime/UI
integration and focused/full checks complete. See [free-pick evidence](../m4-free-briefcases.md).
Native adapter and live server outcome remain open.

Saved `0.26.487.1` `BriefcasesTab` lines 95–149 reads native
`briefcase` season/board/free state and live `GlobalCaseSeason` and
`GlobalCaseEnd` attributes. Lines 1001–1059 send
`BriefcaseAction:InvokeServer("open", index)` for both free and key
picks. `BriefcaseRules` defines 12 cases, `caseKey(i) == "c" .. i`,
current version 0 and free-pick limits. A free pick is not a distinct
remote command; actual cost must be observed in reply/state.

1. Require a fresh full Sync, current active season, matching board
   config, replicated positive free balance, valid opened map and an
   unopened case. Choose the first unopened case, no prize prediction.
2. Use a separate OFF-default `briefcases` opt-in for free picks only.
   Never intentionally send with zero free balance or use/purchase keys.
3. Confirm only a successful reply with `source == "free"`, plus a
   newer same-board full Sync showing selected case opened and free
   balance lower by one. A board-clear transition remains pending until
   separately modeled. This is stricter than the native visual update.
4. Integrate fake broker/Ember status, test stale/changed season, key
   source and board transition, and record native/live uncertainty.
