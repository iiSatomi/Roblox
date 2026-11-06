# Next-tier Safehouse upgrades: offline ordinary-action slice

Saved native `0.26.487.1` `SafehouseTab` lines 509–543 displays the
next `Config.SAFEHOUSE` tier and compares its level/cash requirements.
Lines 659–668 call `UpgradeSafehouse:InvokeServer()` with no arguments.
The current config has 18 tiers through level 215. The server's actual
eligibility check and response shape remain unobserved.

`SafehouseState` requires a fresh matching complete Sync, an exact
current tier, current increasing 18-tier catalog, native current/ever
level and cash. `SafehouseUpgrades` is OFF by default and proposes only
the next tier within a chosen maximum tier, maximum next-tier cost and
cash-to-keep. It excludes reserved and uncertain cash. The current
source UI catalog exposes those three limits. `SafehouseUpgradesEvidence`
requires a successful reply plus newer complete Sync with the tier
increased by exactly one and exact quoted Cash debit. A reply alone or unexpected tier
jump stays pending. No Property or Prestige action runs.

The Safehouse panel can show shared fake-broker status. The distributed
inert Ember 0.1.1 bundle remains unchanged. Local evidence: 202
Python/Lupa tests, 12 Node tests, catalog check, new Luau compilation
and both analyzer modes pass. Standalone EmberAdapter analysis retains
existing Roblox-global/local-shadow diagnostics. Native adapter,
response shape, actual spend and live gameplay remain unverified.

## 2026-10-25 Task 04 checkpoint

**Code/UI (C) and local integration (T): complete. Live (L): pending.**
The current evidence evaluator requires the exact quoted Cash debit,
in addition to one tier increase and a successful reply; the older note
above predates this behavior. The App/native-adapter scenario confirmed
a 2,000 withdrawal to fund the enabled tier-4 purchase, then
`UpgradeSafehouse()` at tier 3, a newer full Sync at tier 4 and the exact
3,000 Cash debit. With maximum tier set to 4, another full Sync scheduled
no further request. Focused Safehouse/native tests: 8 passed. No live call
or GitHub update occurred.

For L, record the current tier, next quote, highest level and Cash from a
full Sync; the exact zero-argument `UpgradeSafehouse` call/reply; and a
newer full Sync with exactly one tier increment and quoted Cash debit.
Check the chosen maximum tier stops the following plan.
