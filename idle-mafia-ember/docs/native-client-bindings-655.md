# Native binding compatibility — place version 655

The client is native version `0.26.646.1`, place version `655`.
The remaining exact version-648 checks prevented combat preflight and player
display facts, and did not require RemoteLink on the current version. Updating
those three checks to reviewed `654`/`655` preserves the existing controller, function,
instance, wrapper, resource and membership guards.

The client later transferred to version 654. Normalized Config, PropsTab,
ProfilePopup and RemoteLink sources matched the reviewed 655 artifacts;
FightTab differed only in decompiled local layout. The current identity
diagnostic passed again. Unknown versions remain blocked.

Private current-source review covered FightTab, ProfilePopup, RemoteLink,
Config and PropsTab. The native wrapper is reused unchanged; its private
validation value is never read or reconstructed. No native callback or busy
flag is modified by these bindings.

| Private review artifact | SHA-256 |
| --- | --- |
| Config | `3ab5562d0f52d3fd1dad4e0a5004db5de7316ed609e061425cc28fbf366faca6` |
| PropsTab | `dd07cee8808677cae6470b1bb6da49dcd62588763326bbb8b80b2f3699109946` |
| ProfilePopup | `8afe072d88842c457e5d388d0d445dc54445d57c01827c2c89256859dc36eb9b` |
| RemoteLink | `2297b13663b369ae5fd87dcfa7556e3834e403b099ebaddf0fc7fe989f46e5d3` |

The manager's live identity diagnostic passed all attack, busy, feedback,
Scout, context and wrapper checks. Production observers then returned:

- Player information: `Current() == true`, property multiplier `0.985`,
  36 copied property catalog rows.
- Combat frame: estimated attack `5263.87743`, health `300`, stamina `30`,
  no shield, native busy `false`, global cooldown `0`, and an empty target set.
- Native rules: hospital health `20`, Attack/Scout quote `1`, maximum exposure
  `5`, target cooldown `30`, daily target cap `5`, variance `0.2`, cap `5000`.

These were read-only production observer checks. They establish current
bindings and estimates, not Attack/Scout server outcomes. Property income
uses the supplied snapshot's server time; the native PropsTab display also
advances time by `State.sinceSync()` between Syncs.

New version-655 tests first reproduced five failures in the old binding.
After the scoped changes, 87 tests and 29 subtests passed across native
bindings, Prestige reset/controller, RuntimeHost, CombatTab and
AutomationRuntime. Coverage includes wrapper/module failure, guarded attack
and Scout preflight, maximum exposure plus follow-up attack reserve,
busy/resource rejection, copied display facts and unknown-version rejection.
