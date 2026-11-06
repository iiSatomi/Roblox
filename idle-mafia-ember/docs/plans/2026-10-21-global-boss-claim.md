# Settled Global Boss claim: offline action slice — implemented locally

Saved `GlobalBossTab` sends `GlobalBossAction("claim")` for a done
event. The read-only view already requires an exact `id_startAt` run,
personal matched damage, access, unclaimed state and a seven-day
result window. Add a separately enabled `globalBossClaim`
descriptor and a write-ahead one-send-per-run checkpoint proof. A
new event run may reset the local attempt count; an unconfirmed send
still consumes the prior run's attempt.

Preflight repeats the exact run, done/claimable state and count.
A positive reply needs a newer same-account native personal `gb`
record with the same run and `claimed=true`. Do not infer rewards
from a response alone. Missing proof remains unconfirmed under the
shared 45-second policy. No attack, Gold or item purchase.

Tests cover wrong run, already claimed, grace, fake restart cap,
exact confirmation and shared broker. Production storage/transport
and live response shape remain open.

Implemented through the separate descriptor, shared fake runtime
and checkpoint. See `../m7-global-boss-claim.md`.
