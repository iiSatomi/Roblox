# Saved native call descriptions

`NativeCallPlan` is a pure, non-sending map for saved-client calls. The
saved `JobsTab` invokes `DoJob(job.id)` and `BossTab` invokes
`BossAction("shopBuy", item, quantity)`. For gear, the saved handler
passes an explicit `nil` third argument; crates pass 1 or 10. The plan
records arity 3 for both. It accepts only the saved 15 Boss Shop item
IDs with matching kind and quantity.

The saved `OpsTab` invokes `StartOperation(op.id)` and
`CollectOperation(current active-array index)`. `ContractsTab` invokes
`ContractAction("claim"/"claimweekly", index, nil)` for earned rows and
`ContractAction("claimbonus"/"claimweeklybonus", nil, nil)` for earned
completion bonuses. `BriefcasesTab` invokes
`BriefcaseAction("open", index)`; the free-pick planner and evidence
must establish free eligibility before this call is considered. Unknown
features and inconsistent period/command pairs fail closed.

The saved `Hud` invokes `AllocateSkillPoint(stat, count)` for a bounded
skill batch. `BankTab` invokes `BankDeposit(amount)` or
`Withdraw(amount)`; the latter's purpose-specific funding proof remains
in its planner/evidence. `SafehouseTab` invokes
`UpgradeSafehouse()` and `PropsTab` invokes `ClaimGroupBonus()` with no
arguments. The adapter accepts zero-argument descriptions so those
native shapes are retained. Selected-amount, next-tier and membership
checks remain separate preflight/evidence requirements. The Group ID is
validated from current membership; it is not a fixed call argument.

The saved Boss views also show ordinary
`BossAction("stageAttack", stage)`, `GlobalBossAction("attack"/"claim")`,
and `FamilyBossAction("attack")` or
`FamilyBossAction("claim", week, stage)`. The call map excludes the
native paid `stageAuto` path. Safe attack, free-charge, participation,
expiry and exact reward eligibility remain planner and evidence gates;
the call shape alone never establishes them.

`PropertyBlock` passes `BuyProperty(propId, nil)` for the no-slot build
intent. `InventoryTab` invokes `ClaimTrophy(item.id)` for the two
non-consuming Gold-mastery IDs supported by the offline planner.
`MonthlyCalendar` invokes `ClaimMonthly()`; the saved monthly config is
disabled, so its separate planner remains dormant unless current
configuration explicitly enables it. Other Property replacement and
Trophy paths remain unmapped.
`SafehouseTab` invokes `ClaimLadder(index)` for an earned playtime rung;
the playtime reader must establish the current server day and exact
replicated readiness before that call is eligible.
The saved Market helper forwards four arguments, including three
trailing `nil`s for sold-earnings `MarketAction("collect")`; collection
requires its own exact newer earnings-to-Gold proof.

`NativeDispatchAdapter` now composes the call plan with injected
`Schedule` and `Invoke` functions. The broker calls its optional
`Validate` method at send-time preflight, before the checkpoint writes a
sent attempt. Unsupported calls release the broker without a send or
uncertain record. A scheduled invocation that throws or returns no table
remains uncertain until action-specific state proof or the existing
45-second deadline; a reply alone never confirms a mutation.
The broker supplies an ownership callback to each scheduled send. A
callback queued past the 45-second deadline, after stop, or after its
owner resolves cannot invoke the remote. An invocation still running
after expiry holds the transport lane until it returns; its late reply
cannot resolve the old owner.
The adapter unpacks arguments through `call.arity` and passes
`Invoke(remote, method, ...)` exact varargs to the injected executor.
This retains trailing `nil` arguments in Contract, Property and gear
Boss Shop calls. Using the table's default length would lose them.
A real executor invoker has not been wired.
Heist start/help/sabotage remain unmapped: saved `HeistsTab` sends
`HeistAction(command, rowId, sequence)` and replays `status` with the
same per-action sequence. The current proposal does not own a durable
sequence/status protocol, so an ordinary call shape alone is insufficient.

Neither module resolves Roblox instances, invokes a real remote, wraps
`RemoteLink`, fetches state, or proves server acceptance. No executor
implementation is injected into the distributed inert UI. A production
adapter still needs current client/wrapper and response validation. Do
not infer a live-ready call from saved UI source alone.

Local evidence: call-plan and injected-dispatch Python/Lupa tests for
exact arguments, fail-closed preflight, delayed reply and 45-second
uncertainty, plus full recode checks in the current handoff.
