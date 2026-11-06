# Task 18 Family contribution checkpoint

October 27: the Family tab now owns separate Cash, Gold and Stamina contribution planners, source-bound state, personal outcome evidence, settings and exact call descriptions. This is offline implementation/local integration; no current-client result is claimed.

## Reviewed call and state evidence

- Saved `FamilyTab-869d07b99846.lua` invokes `FamilyAction("donate", amount, nil, nil)` and `FamilyAction("donategold", amount, nil, nil)` in the donation button handlers. Its Stamina perk buttons invoke `FamilyAction("contribute", perkId, 1, nil)` or the five-point equivalent. `FamilyCallPlan` preserves four argument positions and has no vault purchase, upgrade, withdrawal, membership or war route.
- Saved Config supplies `FAMILY.donateMin`, `contributeMax`, `staminaPerkCosts` and the Stamina-kind perk tracks. Source data is copied by `FamilyContributionState`; a complete Sync, matching release and source catalog are required.
- Supplied October 25 Cobalt log contains the ordinary donation and five-point `enforcers` contribution calls, and Family replies with member `donated`, `donatedGold`, `contributed` and `perkProgress` fields. These establish argument/field shapes, not universal server acceptance. No session tokens or member data are copied here.

## Behavior

`FamilyQuery:Prepare(snapshot)` and `Stage(snapshot, request, reply)` fence query generations and bind info to the same account/session/release/revision/capture and native Family. The parsed proof retains only the actor's counters and bounded perk maps. Duplicate member IDs, wrong membership, malformed resources and stale generations fail closed. Missing native zero-level/progress entries follow the saved UI's zero default.

Three independent controls expose amount, reserve, run budget and sent-attempt cap; budgets and attempts default to zero and feature switches default off. Stamina additionally selects a reviewed perk and allows the saved one- or five-point batches. A batch cannot exceed the current remaining perk cost. Configured limits and resource exposure are checked again at capture. Each planner needs a snapshot-bound per-feature usage proof; missing usage cannot reset the limits to zero.

Confirmation requires a positive non-pending/non-rate-limited receipt with the actor's exact counter increment, plus a newer complete Sync with the exact personal resource debit and the same Family. Stamina also checks the selected perk's exact progress or level-boundary transition. Another member's vault increase is insufficient, and unrelated vault activity does not invalidate an otherwise exact personal receipt.

Gold currently requires zero bound Gold and sufficient loose Gold. The saved evidence does not establish debit order for mixed-origin donations; that case remains blocked rather than guessing. No reset, dismissal, sale or shared vault purchase was added.

## Verification and remaining work

- Focused Family/UI/composition/host suite: **91 run, 90 passed, one skipped**.
- Full release-worktree suite: **925 run, 924 passed, one skipped** (`Ran 925 tests in 29.513s`, `OK (skipped=1)`).
- UI Catalog matched JSON; manifest preflight scanned **247 unique modules**.
- A real App/settings → Family descriptor → shared broker → NativeDispatchAdapter → injected native executor scenario sent exactly one four-argument Cash donation, then confirmed its personal receipt/debit. Separate local cases cover Gold/Stamina signatures, exact perk rollover, changed membership, stale queries, mixed Gold custody, zero/exhausted budgets, resource reservations, malformed state, altered exposure and pending/rate-limited replies.

Whole-Family C/T remains open: Task 24 must schedule and attach the info proof from the current source, derive durable usage from actual sent attempts (including uncertainty), fence it on disable/profile/session changes, and own shared resource reservations. Production snapshots currently lack that connected source/usage; the UI reports the concrete dependency. `RuntimeHost` installs the Family call plan when present, but fresh proof and run ownership are still mandatory before a proposal. Live shared spending and Stamina tests remain outside this offline task. Continue Task 19 Territory, then revisit at final integration.
