# Daily and weekly Contract entries: offline slice

Status 2026-10-21: offline reader, planner, evidence, fake-runtime/UI
integration and focused/full checks complete. See [entry evidence](../m4-contract-entries.md).
Native adapter and live server outcome remain open.

Saved native `0.26.487.1` `ContractsTab` renders `contracts.daily[i]`
and `contracts.weekly[i]` with `done` and `claimed` markers. Lines
1497 and 1554 call `ContractAction:InvokeServer("claim", i, nil)` and
`ContractAction:InvokeServer("claimweekly", i, nil)`. It accepts a
legacy single weekly object; the current config has five daily and five
weekly tiers. Bonus claims use different commands and remain separate.

1. Add failing tests for fresh complete Sync, current five-entry tiers,
   exact row IDs, replicated done/unclaimed readiness, both periods,
   legacy singleton weekly shape and reset-boundary guards.
2. Add one separately enabled entry proposal, preferring a ready daily
   entry before a weekly entry, with exact period/index/row ID.
3. Capture the selected baseline before fake send. Confirm only after a
   successful reply and newer complete Sync with the same row ID and
   claimed marker before that period's reset. A changed row or reply
   alone is not success.
4. Integrate the shared fake runtime and Ember status, run focused/full
   checks and document remaining native adapter/live evidence.
