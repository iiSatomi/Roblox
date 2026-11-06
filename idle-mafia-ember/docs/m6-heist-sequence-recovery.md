# Heist sequence recovery boundary

Saved native `HeistsTab` calls `HeistAction(command, arg1, sequence)`, then
`HeistAction("status", arg1, sequence)` for the same local sequence. It
starts its sequence counter at zero on UI creation. `pending` and
`rate_limited` continue polling. On `no_pending`, the native UI retries
the mutation; this recode **does not** infer that replay is safe.

`src/tabs/heists/SequenceRecovery.luau` can describe a **status-only**
call for a sent action record loaded by a future trusted, durable store.
It checks account, place, release, action type, original argument,
sequence and sent marker. It never chooses a sequence, sends a call,
replays a mutation or marks the action successful. `reported` means a
status reply exists, not that the board or inventory confirms it.
`no_pending` and malformed replies remain unresolved.

The saved result renderer exposes Heist ID and reward fields, but no
unique result ID. The saved source has no server-side sequence validator
or evidence that a `start` reply contains the `runId` required by the
current confirmation check. `HeistBoardState` therefore copies a
validated result summary while keeping `resultAddressable = false`.
The separately enabled `heistCollect` descriptor returns a clear
identity/sequence blocker and cannot propose a send; its evidence
capture also refuses admission. Start and sabotage remain unmapped in
`NativeCallPlan` for the same sequence-ownership reason.

Before enabling a mutation, establish from the current client and
server-observed behavior how a sequence is uniquely allocated across
the native UI and hub, whether a pending record survives restart, what
`status` and `no_pending` mean, and which stable run/result identity
confirms each action. Then wire durable account-scoped storage,
status-only recovery and action-specific state confirmation. None of
that has been live-verified here.
