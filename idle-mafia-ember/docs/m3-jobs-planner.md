# M3 ordinary Jobs reader and planner — offline

The saved `0.26.487.1` client shows ordinary Jobs through the UI's wrapped
`DoJob(job.id)` call, while the rendered Job list uses catalog level, energy,
cash, XP and saved mastery tier/progress. `JobsTab:775–827` applies the current
mastery energy discount and checks level and energy. The wrapper may transform
wire arguments; no server acceptance or exact raw call is established.

`JobsState.read(raw, context)` requires one complete native Sync with matching
identity/revision, an inactive native Jobs controller, current catalog key,
catalog entries, mastery rules, level, energy and Job progress records. It
copies a normalized view and applies the displayed energy rounding formula.
The adapter must update snapshot revision when either native state or catalog
rules change. A partial Sync, missing field, duplicate Job ID or invalid tier
blocks the reader. `native.fullSync` is an adapter-supplied marker for a
complete Sync, not a field established in the saved game state. This is a
client-side planning estimate, not a server quote.

`Jobs.propose(view, settings, reservations)` returns a validated ordinary Job
intent and expected energy exposure. It never invokes a remote. XP and Cash
rank reward per displayed energy. Balanced ranks the sum of XP and Cash,
normalized to each eligible set's maximum, per energy. Mastery targets the
closest unfinished next tier; Selected job requires an exact current ID.
These ranking semantics are provisional design choices, not native controller
behavior. Deterministic ID tie breaks and current level/energy/reserve checks
apply. Custom policy and explicit city selection block until their settings
and native restrictions are defined. The current UI has only a policy choice;
it lacks a selected Job ID control, so that mode cannot yet be used from App.

The planner's `intent.targetId` is a stable Job ID and `intent.catalogKey`/
`expectedCost` support preflight; a later verified transport adapter must map
the intent to the actual native dispatch seam. Job success still needs an
action-specific confirmer over replicated progress/resources. No live Job,
remote call, saved account change or UI binding was made in this slice.
