# Read-only personal Heist board

Saved native 0.26.487.1 `HeistsTab` reads
`HeistAction:InvokeServer("board")`. `HeistBoardState` accepts a
complete, unqueried board wrapped by a future adapter with the current
account and Sync capture identity. It distinguishes idle, active,
settling and result states, validates a personal run ID and catalog
type, and preserves optional board clock/start/cooldown facts as
unknown when absent. A queried search board or a board showing both a
personal run and result is rejected.

The native UI sends `start`, `collect` and follow-up `status` through
its own locally allocated sequence. This reader does not send or
recreate that sequence. The visible result has a `heistId`, but the
reviewed renderer does not establish a unique result key or exact
collection proof. Results are therefore visible but explicitly
unaddressable by automation until the mutation contract is verified.
The shared `Context` optionally reads this view and marks it unknown
when board proof is missing; the fake runtime injects the reader.

Local evidence: 240 Python/Lupa tests, 12 Node tests, Luau compilation
and both analyzer modes pass. No production board transport or live
result is verified.
