# Next-tier Safehouse upgrades: offline slice

Status 2026-10-21: offline reader, planner, evidence, three UI limits,
fake-runtime/UI integration and focused/full checks complete. See
[Safehouse evidence](../m5-safehouse-upgrades.md). Native adapter and
live server outcome remain open.

Saved `0.26.487.1` `SafehouseTab` lines 509–543 displays the next
`Config.SAFEHOUSE` tier, requiring `Config.highestLevel(data)` and
its listed cash cost. Lines 659–668 send
`UpgradeSafehouse:InvokeServer()` without arguments. Current config
has 18 increasing tiers through level 215. Server validation and
actual response shape remain unverified.

1. Read a fresh complete Sync, exact current tier, current 18-tier
   catalog, highest current/ever level and cash. Fail closed on absent
   or changed catalog fields.
2. Add an OFF-default Safehouse switch with maximum tier, maximum
   next-tier cost and cash-to-keep. Propose only tier + 1 when level,
   cap and cash/uncertain-reserve checks pass.
3. Confirm successful reply plus newer complete Sync where the exact
   tier increases by one. A reply alone, stale state or a jump is
   pending. Cash may change concurrently, so do not claim exact spend.
4. Integrate fake broker/UI status, verify and document adapter/live
   gaps. No property replacement or Prestige action runs.
