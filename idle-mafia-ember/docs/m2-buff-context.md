# Read-only effective buff context

`BuffContext` accepts a complete, current native buff proof only when
its account, captured time and server clock match the shared Sync. The
adapter must supply the current daily buff ID/window and global/decree
expiry fields plus the current personal XP boost expiry. The reader
calculates each effective strength, source
and expiry; global, decree and daily effects choose the maximum rather
than stacking. It includes the saved weekday pool and weekend values.
Missing, expired or malformed proof yields an unknown shared context.

Saved native 0.26.487.1 `GlobalBuffKinds` and `DailyBuffRules` establish
the offline formulas. The current daily rotation is supplied by a
future native adapter, so this module does not duplicate native seeded
random scheduling. No planner currently acts on these buff values.
Prestige effects require a separate current-state review.

Local evidence: 222 Python/Lupa tests, 12 Node tests, changed Luau
compilation and both analyzer modes pass. Native adapter fields and
live buff behavior remain unverified.
