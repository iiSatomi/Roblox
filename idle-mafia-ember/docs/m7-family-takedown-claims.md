# Current and historical Family Takedown claims: offline slice

`FamilyBossClaimState`, `FamilyBossClaims` and
`FamilyBossClaimsEvidence` add a separate opt-in intent for the saved
native `FamilyBossAction:InvokeServer("claim", week, stage)` call.
Current-week stage claims select stages 1–5 only while the account is
in the same Family. The slice now also selects exact prior-week claim
rows with a known unexpired deadline, even after leaving that Family;
saved UI rows include stage, rank, medal, podium and other rewards.
Unknown or expired rows remain unavailable.

The checkpoint writes sent stage IDs per exact reward week with the
unresolved action before dispatch, and reads the old single-week
checkpoint format for migration. An unconfirmed send consumes that
week/stage attempt. Preflight rechecks reward week, current week,
stage, expiry and usage. Confirmation needs a positive reply and a
newer complete state where the exact claim row is absent before
expiry; current-week stages also require native `claimedStages`.
A positive reply alone does not establish a reward. The
shared broker retains the 45-second unconfirmed/skipped deadline
and feature cooldown; a skip does not cancel the server action.

Offline evidence: see the current test count in
`docs/AGENT_HANDOFF.md`. The registry remains at 23 fake-adapter
descriptors. Default Ember 0.1.1 remains inert; native transport,
actual response shape and live outcome are unverified.
