# Contract completion bonuses: offline slice

Status 2026-10-21: offline reader, planner, evidence, fake-runtime/UI
integration and focused/full checks complete. See [bonus evidence](../m4-contract-bonuses.md).
Native adapter and live award observation remain open.

Saved `0.26.487.1` `ContractsTab` lines 923–968 shows a daily bonus
after every daily row is claimed and a weekly bonus after every weekly
row is claimed. Lines 1575 and 1593 send
`ContractAction:InvokeServer("claimbonus", nil, nil)` and
`("claimweeklybonus", nil, nil)`. Current `Config.CONTRACTS` gives two
Seals plus full Energy for daily, and 12 Seals plus `crate_fixervault`
for weekly. These rewards are source metadata, not observed delivery.

1. Require fresh complete Sync, current five-entry tiers, exact claimed
   rows, reset window and current bonus reward metadata.
2. Keep a separate OFF-default `bonuses` switch and propose only one
   ready unclaimed period, with its exact reset and command.
3. Capture baseline and confirm only a successful reply plus newer
   full Sync where that period's bonus marker turns true before reset.
   Award contents remain unverified until a native adapter can supply
   reliable post-claim inventory/resource evidence.
4. Integrate fake broker and Ember status, verify locally and update
   handoff. No refill action, crate opening or Contract shop action.
