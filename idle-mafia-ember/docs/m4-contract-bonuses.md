# Contract completion bonuses: offline claim slice

Saved native `0.26.487.1` `ContractsTab` lines 923–968 offers the
daily and weekly bonuses only after every entry for that period is
claimed. Lines 1575 and 1593 send
`ContractAction:InvokeServer("claimbonus", nil, nil)` and
`("claimweeklybonus", nil, nil)`. Current `Config.CONTRACTS` awards
two Seals and a full Energy refill daily, or 12 Seals and a
`crate_fixervault` weekly. These are client-side reward definitions;
actual award delivery is unobserved.

`ContractBonusesState` requires a fresh matching complete Sync, valid
current five-entry tiers and reward metadata, every prerequisite row
claimed, a stable row signature and at least five seconds before the
period reset. `ContractBonuses` has a separate OFF-default switch and
proposes one daily bonus before weekly. `ContractBonusesEvidence` requires
a successful reply plus newer complete Sync with the same prerequisite
rows and exact bonus marker set before the same reset. A reply alone,
row replacement or rollover stays pending. The marker proves claim
state; it does not prove the exact Energy, Seals or crate award. No
refill action, crate opening or Contract shop purchase runs.

The Bonuses panel can show shared fake-broker status. The distributed
inert Ember 0.1.1 bundle is unchanged. Local evidence: 181 Python/Lupa
tests, 12 Node tests, catalog check, new Luau compilation and both
analyzer modes pass. The standalone EmberAdapter analyzer retains its
existing Roblox-global/local-shadow diagnostics; the new status branch
uses the existing `Status:Set` path. Native adapter, actual response
shape, award observation, durable transport and live gameplay remain
unverified.
