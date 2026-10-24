# Ordinary Global Boss attacks: offline slice

`GlobalBossAttackState`, `GlobalBossAttack` and
`GlobalBossAttackEvidence` provide a separate opt-in intent for the
native `GlobalBossAction:InvokeServer("attack")` call. The reader
requires an accessible live `id_startAt` event run, known native
health and stamina, and the account's own Global Boss record. The
planner requires at least 75% health before the hit, keeps one
stamina in reserve, permits at most 25 sent hits per run, and spaces
attempts by at least five native-server seconds. The 75% threshold
is a conservative local buffer; the current server's hit-back
formula has not been observed.

The checkpoint writes the run key, sent-hit count and native-server
send time with the unresolved action before transport. These limits
survive restart and count unconfirmed sends. Preflight repeats the
same run, access, live window, resources and usage proof. A positive
reply with damage confirms only after a newer same-run personal
`gb.hits` and `gb.dmg` increase. Event-wide damage cannot prove this
account's hit. Missing evidence follows the shared 45-second
unconfirmed/skipped deadline and feature cooldown; a skip does not
cancel a server action.

Offline evidence: 294 Python/Lupa tests, 12 Node tests and catalog
check pass. This is one of 21 fake-adapter descriptors. The
distributed Ember 0.1.1 prototype is inert; production storage,
native snapshot/transport adapters, current response shape and live
outcome are unverified. No paid controller or refill is used.
