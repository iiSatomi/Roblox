# Ember dependency review — November 6, 2026

Reviewed input: [hosted Ember source](https://rbx.lol/ember.lua), downloaded as
data to the ignored `.private/ember-2026-11-06.lua`. The source reports `3.0.0`,
contains 299,145 bytes, and has SHA-256:

`0aebb331911619d0c791de1d0d3e9b2e51ead3fb4472cd038807155ad8bcf412`

The previous review covered 298,230 bytes at SHA-256
`c6ec2ad2ad732a2ed704d044fd068b685d7e6c2613f60a07c39316666576390a`.
Those original bytes are unavailable locally; this is an independent review of
the integration contracts in the current source, not a claimed complete diff.
Line numbers below refer to the current exact bytes. Official
[controls documentation](https://rbx.lol/docs/ember/controls/overview) and
[lifecycle documentation](https://rbx.lol/docs/ember/guides/lifecycle) were read
alongside the source.

## Storage finding and correction

`Configure`, lines 196–236, recognizes `Storage = false`, but any supplied
`Storage` value also triggers `Ember.LoadThemes()` at line 221. `LoadThemes`,
lines 7661 onward, calls `Store.get("themes")`; `Store.get`, lines 358–378,
does not check `Config.Storage.Enabled`. If executor file functions exist, this
can read `ember/themes.json` and write a `.corrupt` copy when decoding fails.
Configuration also attempts to flush an existing dirty cache before applying
the new storage setting. Consequently, the old adapter's `Storage = false`
was insufficient to guarantee an inert start without settings I/O. This
corrects the storage conclusion in the October review.

The adapter now validates the reviewed public `Ember.Config.Storage` table,
sets `Enabled = false` before configuration/window creation, and omits the
`Storage` option from `Configure`. This avoids both the storage-change flush
and theme-reload branch. Individual value controls still use `Save = false`;
window layout saving stays off. Themes come from the built-in palette. The app
does not call `LoadThemes`, `Store.get`, or the optional theme editor.

The asynchronous test double now represents the discovered configuration read.
The new regression failed with one external-read attempt before the adapter
change and passes with zero after it. It does not emulate Roblox rendering.

## Callback, lifecycle, and API compatibility

- Toggle `Set(value, silent)`, lines 2461–2472, preserves explicit false and
  suppresses the callback when silent. Input setters, lines 2649–2657, accept
  scalar text; numeric preferences remain converted by the application.
- `installControl`, lines 4564–4659, preserves callback origins for startup and
  restoration. Optional `OnEnabled`/`OnDisabled` dispatch preserves those origins;
  this application does not use these optional edge callbacks. Controls remain
  configured with `FireOnStart = false`, `Save = false`, and `Reapply = false`.
- `SetValues`, lines 5741–5753, still loses explicit false through its `and/or`
  expression and counts a refused setter as applied if `pcall` succeeds. Keep
  the adapter's sorted scalar setters, refusal checks, rollback, and degraded
  state on failed rollback. Do not use this bulk API for profile hydration.
- `Destroy`, lines 6632–6708, runs reverts before destroy listeners, then
  disconnects resources and releases GUI instances. Reverts identify their
  origin at lines 6213–6222. Application callbacks reject reverted origins,
  validate current handle values, and fence queued work after destruction.
  Explicit application unload fences the model before invoking Ember teardown.
- `RevertTo = false` remains necessary: the fallback getter at lines 6202–6204
  can discard a false value. Independently stopping the model remains required.
- `ReplaceExisting` matches window identity and destroys matching prior windows
  at lines 6726–6735. Group inheritance at lines 4154–4167 remains compatible
  with nested Custom groups. The tab rail is a scrolling frame with automatic
  Y canvas size at lines 7094–7098; actual usability still needs live inspection.
- No dynamic script loader or gameplay remote invocation was found in this
  dependency. Its sole `game:HttpGet` call, line 7725, is inside opt-in
  `ImportTheme`, which parses JSON rather than executing it. The application
  exposes only built-in theme selection and does not call that function.

## Verification and release boundary

Fresh focused verification: `pytest tests/test_ui_prototype.py -q` produced
60 passes and one optional analyzer skip. This includes startup-origin fences,
stale callbacks, false profile hydration, rollback refusal, failed-rollback
freeze, constructor cleanup, replacement, and the new storage-read regression.
The private-input builder test accepts these reviewed bytes and rejects an
appended-byte mutation. It skips when private dependency data is unavailable.

`tools/build_ui_prototype.py --check --ember .private/ember-2026-11-06.lua`
verified the generated catalog and built the private 611,000-byte inert UI at
`.private/IdleMafia-Ember-UI-0.1.38.lua`. The builder fingerprint was updated only
after this review and retains exact-byte rejection. No published entry pin was
changed in this workstream. The manager owns live rendering/compiler checks
and release assembly; these local results do not establish gameplay outcomes.

No redistribution license was found in the source. Third-party bytes remain
ignored private inputs; the prior review's publishing boundary still applies.
