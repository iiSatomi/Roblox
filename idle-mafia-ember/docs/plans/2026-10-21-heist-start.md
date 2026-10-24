# Personal Heist start: offline slice

Status: pure planner/evidence and fake-broker integration implemented;
native sequence and run-ID reply remain unverified.

The saved 0.26.487.1 client calls `HeistAction("start", heistId,
localSequence)`. The current catalog has seven tiered Heists with
level, stake, energy and crate-count fields. Implement a pure proposal
for a fresh idle personal board with a known server day, positive
startsLeft, no bust cooldown, sufficient level/cash/energy and shared
reservations. Best chest ranks crate count, then tier; Highest tier
ranks tier; the UI's Custom choice currently uses the same eligible
pool until its controls are defined. The proposal leaves sequence
allocation to a future native transport adapter.

Preflight repeats the exact board/cost conditions. Confirmation
requires a reply-supplied normalized `runId` matching a newer,
same-account personal board with the selected Heist and exactly one
fewer start. The saved UI does not prove the reply contains such an
ID, so actual confirmation remains blocked until verified. Absence of
that proof must stay pending and reach the 45-second unconfirmed
path; no reply alone counts as success.

Test selection, resource caps, stale/ambiguous board, preflight,
matching/mismatched run evidence and shared fake broker integration.
