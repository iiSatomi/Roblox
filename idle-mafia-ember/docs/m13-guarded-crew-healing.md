# Recovered-source Crew healing correction

October 27, offline only. Complete saved `0.26.530` source supersedes the old two-argument Stamina call and missing-item-call claim. `CrewHealModal-e3e00803a8de.lua` sends exactly three arguments:

```lua
CrewAction("heal", slot, {memberId = healId, injuredUntil = injuredUntil})
CrewAction("healitem", slot, {
    itemId = itemId, fromBound = fromBound, memberId = healId,
    injuredUntil = injuredUntil, sequence = henchmanConsumableUseSequence,
})
```

The Crew call description constructs payload tables after shared validation of flat primitive intents; old nested item `args` made proposals fail that validation. No paid controller is enabled or represented as owned.

`Config.territoryHealCost` clamps `ceil(max(remaining,0)*healStaminaCost/healSeconds)` between 1 and the configured maximum. Stamina capture replans the quote, member eligibility, reserve, intent and declared exposure immediately before dispatch. Confirmation requires the same `healId`, exact configured timer reduction (or full resolution), positive nonpending/non-rate-limited reply, and newer complete Sync with exact Stamina debit. Pool regeneration or identity clearing can leave this strict observation unconfirmed. Neither a reply nor a timer decrease alone confirms.

`HenchmanHealingRules-a9bdbd860508.lua` permits three reviewed health consumables: 25/50 percent reduce at most `ceil(injurySeconds*percent/100)` seconds, while 100 percent reduces all remaining injury. Capture checks sequence/cooldown, member, item origin, declared exposure and intent. Confirmation requires one selected-stack debit with the opposite stack unchanged, matching `sequence+1` and returned/current `readyAt`, the same member and expected injury reduction. The player restorative sequence is independent. Missing first-use sequence/ready fields in a complete Sync use native zero defaults; malformed present values still fail.

Identity checks use actual `healId`: duplicate display names/rarities are permitted when IDs differ, and duplicate IDs are refused. Healing permits slots through 46. Replacement, duty/training/rolling/recall conflicts and stale quote/sequence remain blocked. Stable member/item reservations and durable full-intent recovery remain Task 24; item-heal UI names that boundary instead of claiming a missing saved call. Whole Crew C/T and L remain open, including rolling/replacement.

Focused command: `python -B -m unittest test_crew_heal test_crew_heal_items test_crew_call_plan test_crew_healing_pipeline` — **20 passed**. Tests include actual App → shared broker → fake native adapter for both methods, exact effects, disable, tampering, unchanged resources, changed member/sequence, short-injury scaled cost, full medkit and duplicate-name identities. A final integrated run follows Event Shop work. No MCP, live healing, Stamina use, item use, commit or publication occurred.
