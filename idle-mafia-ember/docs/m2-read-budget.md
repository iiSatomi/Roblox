# Bounded background native reads

`ReadBudget` is a pure admission gate for future native read adapters.
It grants one due source at a time, enforces each source's minimum
interval, and has one global in-flight slot. Its fake monotonic clock
sets a bounded callback deadline. A timed-out read is marked failed,
the affected source backs off, and its old completion token cannot
change the next read. Close fences the active token and all future
admissions. Success restores normal cadence. Status exposes
per-source next time, failure count and in-flight state.

The Market read composition retains an invocation latch after budget
timeout, so an already-running executor call cannot overlap the next
read. A queued callback checks token ownership immediately before
invoking and skips if the deadline passed.

This is not connected to a Roblox reader or the inert Ember build. It
does not assert that a background read completed or that its snapshot
is fresh; a native adapter must still validate each result before the
shared context can use it. Local evidence: 234 Python/Lupa tests,
12 Node tests, Luau compilation and both analyzer modes pass.
