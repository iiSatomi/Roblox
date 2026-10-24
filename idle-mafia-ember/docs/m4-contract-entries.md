# Earned daily and weekly Contract entries: offline claim slice

Saved native `0.26.487.1` `ContractsTab` lines 897–968 renders
`contracts.daily[i]` and `contracts.weekly[i]` with `done` and `claimed`
markers. It wraps a legacy single weekly object as index 1. Lines
1497 and 1554 send `ContractAction:InvokeServer("claim", i, nil)` and
`ContractAction:InvokeServer("claimweekly", i, nil)`. Current
`Config.CONTRACTS` has five daily and five weekly tiers. These are client
calls, not proof of server acceptance.

`ContractEntriesState` requires a fresh matching complete Sync, current
five-entry tier catalog, stable row IDs, both reset timestamps and
replicated done/unclaimed markers. It waits five seconds away from a
reset and selects one daily row before a weekly row. `ContractEntries`
is separately enabled and carries period, row index, row ID and reset
identity through the fake broker. `ContractEntriesEvidence` confirms
only a successful reply plus a newer complete Sync showing the same
row claimed before the same reset. A changed/replaced row, rollover or
reply alone stays pending. No contract replacement, shop purchase or
bonus claim runs.

The Contracts panel can show the shared fake-broker status. The
distributed inert Ember 0.1.1 bundle remains unchanged. Local evidence:
175 Python/Lupa tests, 12 Node tests and generated-catalog check pass.
The new Contract Luau modules and App compile and pass old/new analyzer
modes. The standalone UI analyzer still reports its existing Roblox-global
and local-shadow diagnostics; the new status branch uses the existing
`Status:Set` path. Native snapshot/response shapes, durable transport,
actual reward delivery and live gameplay remain unverified.
