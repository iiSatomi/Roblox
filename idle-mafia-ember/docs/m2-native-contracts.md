# M2 shared and Jobs contract — offline source checkpoint

Date: 2026-10-20. Evidence is the inert extracted client for native
`0.26.487.1`, not a live client or saved server implementation. Source line
numbers below refer to the ignored `.private/place-2026-10-20/` files. No
extracted code, seed or account data belongs in the recode.

## Ordinary Jobs path

| Fact | Saved client evidence | Implementation consequence |
| --- | --- | --- |
| Catalog | `GameData-7f11ce4db37f.lua:6–17` provides stable `JOBS` entries including `id`, `level`, `energy`, `cash`, `xp`; `:1130–1135` builds `JOBS_BY_ID`. | Read the current native catalog; never use a permanent hand-written Job list. |
| State | `JobsTab-c0dacdf1aff6.lua:205–209` reads `data.jobs[id]` with `completions`, `masteryProgress`, `masteryTier`; `:823–827` compares level and energy from `pools.energy`. | Require fresh catalog and player state. The Job's exact current effective energy cost needs native mastery context. |
| UI cost | `JobsTab:775–783` rounds catalog energy after the current mastery discount and clamps it to at least one. `Config-e07fd1c45e85.lua:165–183` defines mastery discounts. | This is client display evidence, not proof of a server quote. Recompute from fresh native rules and revalidate before sending. |
| Ordinary action | `JobsTab:416–429` gates repeated clicks and invokes `u2.Remotes.DoJob:InvokeServer(job.id)`. `:432–478` handles `ok`, `code == "rate_limited"`, `retryIn`, `cash` and `xp`. | A Jobs adapter can propose the stable Job ID. A return is reply evidence; it does not alone prove saved account progression. Rate limits need explicit cooldown. |
| Native owner | `JobsTab:933–959` checks `(data.derived or {}).autoJobs` for entitlement and `type(data.autoJob) == "table"` for an active run. `:1044–1087` reads `autoJobCurrent` and `autoJobWaiting`. | Entitlement and activity are different. Active or unknown controller state blocks hub Jobs. Do not call `AutoJobAction` for ordinary Jobs. |
| Wrapped remotes | `MWClient-2dd0835af927.lua:176–183` supplies `RemoteLink.wrap(Remotes)` to the UI. `RemoteLink-6ed10c485cd3.lua:12–45` may transform remote calls before they reach the wire. | The UI's argument list is not a verified raw-wire contract. A live adapter must use a verified supported dispatch seam; never embed private handshake data. |
| Replication | `State-eda8e0618d7c.lua:14–24,56–72` owns latest state and changed callbacks. `MWClient:749–752` accepts `Sync`. `MWClient:836–877` applies `AutoJobTick` fields for auto runs. | Manual DoJob replication timing and exact return-to-state relation remain unverified. The confirmer must check the same Job record and resource/progress change, and retain uncertainty when evidence is ambiguous. |
| Server time | `MWClient:754–756` advances saved `serverNow` from ping elapsed; `State:22–23,60–63` tracks local time since sync. | Native reset/buff/expiry calculations need current server time; the 45-second request deadline uses monotonic local elapsed time instead. |

Shared economic and buff inputs are separate from this first Job transport
slice. `DecreeRules-d5304a5a005c.lua:17–27,308` describes Market/hire decree
effects and Family exemption; `GlobalBuffKinds-8eca1c22333d.lua:21,76,324`
and `DailyBuffRules-9880354c79e5.lua:25–28,113` expose Job XP/mastery and
other effective buffs. Task 5 must normalize those from current state rather
than assuming values or stacking badge text. Their runtime state paths and
server application remain unverified here.

`preview/catalog.json` defines `jobs.enabled` and `jobs.policy` (`Balanced`,
`XP`, `Cash`, `Mastery`, `Selected job`, `Custom`). They are current UI choices,
not proof that selection, city or mastery overrides have a runtime settings
schema yet. Before Task 8, map useful legacy selected-job/city/mastery inputs
to a compact validated schema and mark unsupported values visibly. `jobs.enabled`
defaults false and a profile import remains paused.

## Shared action record

Every proposal carries a session/account/place/release identity, a current
snapshot revision and capture time, feature, unique action key, flat validated
intent and finite nonnegative resource exposure. The broker records these
distinct states:

1. `proposed`: a pure planner decision; no request admitted or sent.
2. `admitted`: the single broker owner waiting for the allowed send time.
3. `sent`: transport called once and first-send monotonic time fixed.
4. `returned`: callback received; no success inferred from it alone.
5. `confirmed` or `rejected`: action-specific evidence evaluator resolves it.
6. `skipped_unconfirmed`: exactly 45 seconds after first send without adequate
   evidence; log duplicate risk, release the broker and cool down this feature.

Late replies and late state evidence remain attributed to the original action
identity; they cannot release a newer broker owner or count success twice.
Initial feature/resource arbitration and the fake-storage checkpoint boundary
are documented in [the session note](m2-checkpoint.md). A real atomic executor
storage adapter and live verification remain open.

## Evidence still required before any real Job request

- Confirm current client/place/build and the supported dispatch path. The
  decompiled wrapped call is not enough to choose raw wire arguments.
- Observe actual ordinary DoJob response shape and before/after Job record,
  energy, cash and XP for one naturally eligible action. Distinguish unrelated
  external resource changes from this Job's result.
- Check active native Auto Jobs status and profile/account freshness in the
  current session. Missing activity data is unknown, not stopped.
- Verify the source-derived cost and current unlocks against live state. Server
  validation, rate limits and manual Job replication are unavailable offline.

The fixtures in `tests/fixtures/job-snapshots.lua` are **synthetic test
states** using source-named fields; they are not recorded account data or
assertions that the server accepted an action.

The initial `Context` adapter accepts a **caller-supplied** `native.fullSync`
marker. It is not a game field: set it only when the reader has a complete
replicated Sync. An `autoJob` table means active; absence in a known complete
Sync means inactive; absence in partial or unclassified data means unknown.
Economic and buff values currently report unknown until their native helper
inputs can be normalized without guessing.
