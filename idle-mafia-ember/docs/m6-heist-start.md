# Personal Heist start: offline slice

Saved native 0.26.487.1 `HeistsTab` calls
`HeistAction:InvokeServer("start", heistId, sequence)`. The source
catalog has seven tiered Heists. `HeistStart` selects an eligible
personal run only from a current idle board with a known server day,
positive startsLeft and no bust cooldown. It checks level, stake,
energy and shared reservations. Best chest ranks crate count before
tier; Highest tier ranks tier. The UI's Custom choice currently uses
the same eligible pool and tier ranking because it has no Custom
fields yet. Its intent flags that a future native adapter must own
sequence allocation; it does not invent or borrow the UI's counter.
The saved client starts that counter at zero, increments it for a new
action, and then polls `HeistAction("status", arg1, sequence)` with the
same value for up to 120 seconds. `pending` and `rate_limited` keep the
poll loop; `no_pending` resets it to retry the mutation. This behavior
is client source evidence only. A recode sender needs a durable
account-scoped sequence and restart/status recovery before it can map
the action safely; the current call plan deliberately leaves it unmapped.

Preflight repeats the selected board and quote checks. A positive
reply does not confirm the start. Confirmation needs a normalized
reply `runId` that matches a newer personal board's new run ID,
selected Heist ID and one fewer start. The saved UI does not establish
that the native reply provides `runId`; without it, the fake broker
keeps the action pending and ultimately applies the existing
45-second unconfirmed skip/cooldown. This can leave duplicate risk and
must be verified before any production transport sends the action.

The feature is registered with the shared **fake** runtime and
existing Heists UI control. Local evidence: 245 Python/Lupa tests,
12 Node tests, catalog check, changed Luau compilation and both
analyzer modes pass. No real Heist request was sent or confirmed.
