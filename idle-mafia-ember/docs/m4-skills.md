# Skills: offline native batch slice

Saved client `0.26.487.1` `Hud` lists the six allocation stats near line
2258, computes pending cost from `skillPoints`, `allocs` and `Config.allocCost`
around lines 2317–2369, and sends `AllocateSkillPoint(stat, count)` in batches
of up to 100 near lines 2575–2595. `Config` lines 39–113 defines the current
per-stat cost progression. The 100 count is a UI batch limit, not evidence of
a universal server limit or a successful live request.

`SkillsState` requires a matching fresh complete Sync, current six-rule
adapter catalog and exact native points/allocations. `Skills` is separately
enabled; it uses one chosen stat, a user-set maximum allocation and a batch
cap of at most 100. The default maximum is one allocation. It computes the
sum of each native-rule cost and exposes skill points to the shared broker's
resource/uncertainty accounting. `SkillsEvidence` confirms only a successful
reply plus newer full Sync with the chosen allocation increment and matching
point deduction. A concurrent manual allocation or level-up can make the
result ambiguous, so it remains pending. No reset or respec is included.

The existing Skills Ember panel now has stat, maximum and batch controls in
the source catalog; the optional fake-adapter runtime exposes waiting and
outcome state there. The distributed inert 0.1.1 bundle remains unchanged.
Local evidence: 138 Python/Lupa tests, 12 Node preview tests, changed Luau
compilation and new analyzer check pass. Current adapter shapes, actual
server limits/reply, durable storage, live effect and gameplay packaging are
unverified.
# 2026-10-25 Task 06 checkpoint

**Code/UI (C) and local integration (T): complete. Live (L): pending.**
The actual App controls and injected native adapter sent
`AllocateSkillPoint("energy", 2)` with arity two. A newer full Sync
showed exactly two more Energy allocations, a two-point debit and
unchanged other stat allocations. A following snapshot at the chosen
allocation cap scheduled no repeat. Focused Skills/Runtime tests: 9
passed. No live call, Stamina consumption or GitHub update occurred.

For L, record current points, all six allocations and reviewed cost
rules from a full Sync; the exact selected stat/count native call and
reply; then a newer full Sync proving only the selected allocation
changed by that count and points fell by the quoted total.
