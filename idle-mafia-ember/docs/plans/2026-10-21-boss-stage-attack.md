# City Boss stage attack: bounded offline action slice — implemented locally

Saved `BossTab` uses `BossAction:InvokeServer("stageAttack",
stage)`. `BossStages` exposes an ordinary `best + 1` progression
stage, UTC `%Y%j` daily clear, keyed HP and worst hit-back. The
simplified UI has one `bosses` switch without policy fields.

Add a separate Boss action reader/planner/evidence descriptor. Prefer
the next uncleared progression stage, then the lowest eligible daily
repeat. Require an explicit catalog row for the next stage, known
native health/stamina and a 50% health floor after worst hit-back.
Hold one stamina and cap sends conservatively at 100 hits and 100
stamina per native day with five native-server seconds between Boss
sends. Persist the count and last send time atomically with the
unresolved action before dispatch; unconfirmed sends consume the cap.
The saved game may impose additional server limits; these are local
guards, not server behavior claims.

Preflight must recheck stage/day/HP/health/cost and daily proof. A
positive reply plus newer same-account native state must show the
selected stage's remaining HP decrease or a fresh daily clear and
progression change. Missing evidence stays unconfirmed under the
shared 45-second policy. No paid `stageAuto`, refill or Gold action.

Tests cover next-stage selection, daily repeats and resets, health,
stamina and cap guards, atomic write/restart, exact-stage evidence and
shared fake broker. Native adapter, actual reply/state shape and live
server acceptance remain open.

Implemented through `BossesState`, `Bosses`, `BossesEvidence`, the
shared registry/runtime and checkpoint proof. See
`../m7-boss-stage-attack.md` for the verified scope and open adapters.
