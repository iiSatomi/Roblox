# Ordinary Jobs evidence and current boundary

The optional `JobsRuntime` composes a pure Jobs reader/planner, shared
scheduler, one-owner broker and checkpoint ledger. It has no Roblox globals,
executor APIs, direct UI remote call or timer. App uses it only when a trusted
caller injects an instance; the distributed Ember 0.1.1 prototype does not.
Jobs begins paused and needs an explicit UI Resume and enabled Jobs switch.

Before a send, the broker captures the selected Job's completion count from a
complete, identity-matched native snapshot. It also rechecks the
selected catalog key, current unlock, mastery-discounted energy cost,
available energy, proposal exposure and absence of a native Auto Jobs
run; a changed quote aborts the send. A successful reply alone stays
pending. Confirmation requires the same session/account/place/release, a newer
revision and full Sync, plus an increased completion count for that selected
Job. An explicit failed reply rejects only when matching progress has not
advanced. Other Jobs, energy changes and partial Syncs cannot confirm. A
simultaneous manual/native completion is still a possible attribution ambiguity;
the hub yields when native Auto Jobs is active and does not call this live proof.

At 45 seconds after first send, an unconfirmed action is marked skipped with
duplicate risk, stays in the checkpoint ledger and cools down Jobs. Pause and
disable prevent new sends while allowing evidence observation and deadline
expiry. An explicit server `rate_limited` rejection also cools the rejected feature
for its bounded `retryIn` interval while unrelated features remain eligible.
Stop/unload prevents new sends; storage failure blocks sending. The UI
shows a sent action as awaiting exact progress, and unresolved exposure as
unconfirmed rather than successful. No production storage or cross-process
ownership adapter has been verified.

Latest local evidence on 2026-10-21: 319 Python/Lupa tests and 12 Node preview
tests pass, with the catalog check and changed Luau compile/analyze clean.
Tests use
injected synthetic state, fake clock/storage/transport and Ember controls; they
do not prove Roblox layout, wire arguments or server acceptance. Next obtain a
current client contract and verified native dispatch seam, construct the
durable adapters and production package, and observe one naturally eligible
low-cost Job with before/after state and broker journal. Keep the old hub sender
off during that check.
