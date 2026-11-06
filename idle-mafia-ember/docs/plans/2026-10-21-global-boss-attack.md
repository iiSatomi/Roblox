# Ordinary Global Boss attack: offline action slice

Status 2026-10-21: implemented in pure/fake-adapter modules. The
294 Python/Lupa tests, 12 Node tests and catalog check pass. Native
adapter and live verification remain open.

Saved `GlobalBossTab` sends `GlobalBossAction("attack")` only while
`GlobalBossRules.isLive` holds. Use the read-only event run/access
view and a separate opt-in `globalBossAttack` descriptor. Require
known full native health/stamina, at least 75% health (legacy 50%
floor plus 25% hit-back buffer), one stamina after the source-backed
cost of one, at most 25 sent hits per run, and five native-server
seconds between hits. The checkpoint writes run count/last send time
with the unresolved action before dispatch; unconfirmed sends count.

Preflight repeats the exact live accessible run, health, stamina and
attempt proof. A positive reply needs a newer same-run personal
`gb.hits` and `gb.dmg` increase. Event-wide damage alone never
confirms a personal hit. Missing evidence stays unconfirmed under
the 45-second broker deadline and feature cooldown. No refill or
paid controller action.

Tests: live/pending/closed, private access, reserves/cap/spacing,
checkpoint restart, exact personal evidence and shared broker.
The current server's hidden hit-back formula and live result shape
remain unverified; the 75% gate is a conservative local policy.
