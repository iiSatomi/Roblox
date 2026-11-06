# Settled Global Boss claim: offline slice

`GlobalBossClaimState`, `GlobalBossClaim` and
`GlobalBossClaimEvidence` add a separate opt-in ordinary
`GlobalBossAction:InvokeServer("claim")` intent. The read-only event
view must show a done, accessible, participated, unclaimed exact
`id_startAt` run inside the seven-day results window. The local
checkpoint atomically records one sent claim attempt for that run
before dispatch. A later event run starts with zero; an unconfirmed
send still consumes its run's attempt.

Preflight repeats the exact event, personal run, claim window and
attempt proof. A positive reply confirms only after a newer
same-account native `gb` record has `claimed=true` on the same run.
No reward is inferred from a response or local attempt count alone.
Missing evidence remains unconfirmed under the common 45-second
policy. The distributed Ember 0.1.1 prototype remains inert; actual
storage, transport, game response and outcome are unverified.

Offline evidence: 290 Python/Lupa tests, 12 Node tests, catalog
check, changed Luau compilation and both analyzer modes pass.
