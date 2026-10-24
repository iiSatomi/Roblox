# Current-week Family Takedown stage claims

Status 2026-10-21: current-week stage 1–5 offline path implemented.
309 Python/Lupa tests, 12 Node tests and catalog check pass;
changed Luau files compile and analyze. Native adapter/live proof
remain open.

Saved `FamilyBossView` sends `FamilyBossAction:InvokeServer("claim",
week, stage)` for an exact claim row and refreshes state. Implement
only current-week stages 1–5 with known expiry and same-Family
membership. The checkpoint keeps a five-stage sent-attempt list for
the current week, written with the unresolved action before send.
An unconfirmed request consumes its stage attempt; a later week
resets the list. Preflight rechecks claim row, expiry, week, Family
and checkpoint usage. A positive reply confirms only with a newer
complete state where that exact claim is gone and the stage appears
in native `claimedStages` before expiry. No response alone proves a
reward. Keep historical and week-end reward claim formats open.

Tests: fail-closed state, bounded selection, claim evidence, durable
restart and fake broker integration. Default distributed Ember 0.1.1
remains inert; actual transport and live response are unverified.
