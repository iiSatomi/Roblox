# City Boss staged state: read-only offline slice — implemented locally

The saved native `BossTab` sends `BossAction("stageAttack", stage)`.
`BossStages.view` uses `bossStage.best`, keyed HP, and a `done` map
only when `bossStage.day` equals UTC `%Y%j`. `lockReason` blocks stages
beyond `best + 1`, above player level, and stages already cleared that
day. `BossStages.get` supplies stage level, max HP and worst hit-back.

Create a read-only reader with an account/snapshot-labelled adapter
proof of the selected stage catalog and stamina cost. It validates
the native full Sync, server time, player health/stamina, stage state,
catalog identifiers and daily map. It exposes unlock/done/remaining-HP
facts and keeps unknown or malformed state from becoming a proposal.
Attach it as an optional shared Context reader; no BossAction call or
feature descriptor in this slice.

Tests: current-day done versus next-day reset, progression gate,
invalid/mismatched proof and optional Context behavior. Only after
this passes should a separate action planner/evidence slice add
hit-back/health reserves, daily attempt bounds and exact response
proof. The saved source is inert evidence, not a runtime import.
Implemented in `BossStageState` and optional `Context` injection.
See `../m7-boss-stage-state.md`. Production catalog and mutation
adapters remain open.
