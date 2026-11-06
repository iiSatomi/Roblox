# Ember dependency review — October 20, 2026

Reviewed input: `https://rbx.lol/ember.lua`, fetched as data, never executed during
this review. The 298,230-byte file reports Ember `3.0.0`.

SHA-256:
`c6ec2ad2ad732a2ed704d044fd068b685d7e6c2613f60a07c39316666576390a`

This is byte-for-byte identical to the October 12 workspace reference. That
reference remains the starting API inventory; line numbers below refer to these
exact bytes. Official [control documentation](https://rbx.lol/docs/ember/controls/overview)
and [lifecycle documentation](https://rbx.lol/docs/ember/guides/lifecycle) were
also accessible during this check. Some other web-tool fetches failed; a public
shell download provided the actual source bytes.

## Findings and adapter decisions

- `Configure`, lines 196–229: configure before creating controls; set
  `Storage = false`. In this source a boolean changes the existing storage
  table's Enabled field. No profile/account persistence is delegated to Ember.
- Toggle setter, lines 2461–2472: supports `Set(value,true)` and returns true.
  Dropdown setters can refuse values. Treat a false setter return as failure,
  independently of whether `pcall` succeeds.
- Control installation, lines 4609–4632: initial/restored callbacks are spawned.
  Disable startup effects, ignore initial/restored/reapplied/reverted origins,
  reject superseded callback values and fence callbacks after unload.
- `GetValues`/`SetValues`, lines 5701–5730: false values still disappear from the
  bulk setter and refusal returns are still ignored. Use a typed scalar model
  and individual silent setters; do not use bulk snapshots for profiles.
- Close reversion, lines 6172–6187: the false-value fallback discrepancy remains.
  Specify `RevertTo = false` and register independent model teardown before
  creating value controls.
- Groups inherit from their owner, lines 4131–4145. Nested Custom groups are
  supported; they can be hidden when their policy is not Custom.
- Sidebar uses a `ScrollingFrame` with automatic Y canvas size, lines 7071–7075.
  This establishes the implementation mechanism, not usable 25-tab scrolling
  at the target resolution. Actual rendering remains unverified.

No redistribution license was found in the downloaded Lua header/body. This
does not establish that redistribution is prohibited or permitted. Third-party
source is not committed. The builder accepts only the reviewed fingerprint and
creates a **private local** executor file. Resolve dependency terms and reviewed
release hosting before publishing a runnable remote loader.

## Verification boundary

Official Luau compiler `0.743` was downloaded from the
[Luau project release](https://github.com/luau-lang/luau/releases/tag/0.743).
Windows archive SHA-256:
`9e019b584ea653e53781f1b9f25aa192175f2c057bbf88fc7f72e2720d710b31`.
Compiler binaries/archive are private build tools, not published dependencies.
The assembled Ember/application file compiles without executing it. Offline
contract tests use a deliberately asynchronous Ember double, not Roblox GUI
objects. Neither check establishes actual UI rendering or gameplay behavior.
