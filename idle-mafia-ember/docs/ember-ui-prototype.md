# Actual Ember UI prototype 0.1.1

This is the first fresh Luau composition for the recode: 25 dedicated tabs,
55 independently selectable activities/permissions, compact goals and bounded
Custom controls. It uses actual Ember methods. No gameplay sender, native game
module, account file, timer or network loader exists in this application.

## Local executor file

The local build is `.private/IdleMafia-Ember-UI-0.1.1.lua`. Paste its contents into
the executor to inspect the UI. It creates only the prototype. The user ran 0.1
and reported that it worked, with editor Problems and icon warnings. Version
0.1.1 was then user-tested with no console errors or executor Problems. F8 shows/hides it. Unload closes it and invalidates
pending local callbacks. Re-running replaces the same-identity prototype.

All feature choices start off and paused. Resume only changes prototype session
state. Labels retain “UI only”; selecting Jobs, Bosses, spending, gear transfers
or combat does not execute that activity. Profiles stages a snapshot in memory;
applying it validates every value, respects explicit false, rejects conflicting
gear owners, and pauses. No named account profiles or legacy settings are read.
Theme changes are local and are not saved.

The prototype is a rendering/interaction checkpoint. Do not treat it as a
replacement for the legacy hub. Gameplay implementation follows the fake-engine
milestone and current-native contracts. The user's latest choice is independent
ordinary-action automation for Jobs/Bosses/etc.; paid controller unlocking is
outside the current development plan. Still detect and yield to any matching
native automation already running so the eventual hub does not compete with it.

## Modules

- `src/storage/Settings.luau`: schema 1 scalar preferences, bounds/enums, atomic
  candidate profiles, gear exclusion and local pause/stop state.
- `src/ui/Catalog.luau`: generated from `preview/catalog.json`; one source of
  truth for 25 tab destinations and 55 feature controls.
- `src/ui/EmberAdapter.luau`: handles, silent validated writes, rollback,
  compact groups, theme/F8 configuration and lifecycle guards.
- `src/App.luau`: explicit dependency composition, profile application and
  local commands. Preferences commit only after fallible UI rendering finishes.

Stable Custom field IDs supplement display labels in the catalog. They do not
change browser preview behavior. Numeric fields use validated Input controls
rather than inventing maximum slider ranges for unbounded budgets.

## Rebuild and test

From the repository root, using Python with Lupa available (this workspace uses
the bundled Python and `PYTHONPATH=.local-deps`):

```powershell
$env:PYTHONPATH = '.local-deps'
$py = 'python'
& $py -m unittest discover -s idle-mafia-ember/tests -p test_ui_prototype.py -v
node --test idle-mafia-ember/tests/preview-model.test.mjs
python idle-mafia-ember/tools/build_ui_prototype.py --check
```

Generate the catalog after editing its JSON; rebuild the private executor file
only from the exact reviewed Ember source:

```powershell
python idle-mafia-ember/tools/build_ui_prototype.py --ember idle-mafia-ember/.private/ember-2026-10-20.lua
& 'idle-mafia-ember/.private/luau-compiler/luau-compile.exe' --null idle-mafia-ember/.private/IdleMafia-Ember-UI-0.1.1.lua
```

The builder never downloads or executes dependency source. See
[dependency review](ember-dependency-review.md) for the fingerprint, API findings,
private-source policy and compiler provenance. A fresh checkout must supply
reviewed bytes itself; no mutable-URL executor loader is published.

Version 0.1.1 embeds sources as separate local chunks rather than inline
functions, keeping their type-inference boundaries intact. It requires the
executor's `loadstring`, precompiles the entire set before executing a module,
names compilation errors by module, then initializes exports once in order.
Missing compilation support or invalid exports stop startup. The App declares
its UI/profile fields before creating callbacks, fixing old-solver field errors.
Sidebar icons use distinct names verified against the pinned Ember catalog:
Overview `home`, Safehouse `shield`, Crew `users`, Family `users-round`.

Compiler checks must include every original source separately, since source
strings are not parsed as code by the wrapper's static analyzer:

```powershell
& 'idle-mafia-ember/.private/luau-compiler/luau-compile.exe' --null idle-mafia-ember/.private/ember-2026-10-20.lua idle-mafia-ember/src/App.luau idle-mafia-ember/src/storage/Settings.luau idle-mafia-ember/src/ui/EmberAdapter.luau idle-mafia-ember/src/ui/Catalog.luau idle-mafia-ember/.private/IdleMafia-Ember-UI-0.1.1.lua
```

## Evidence and remaining checks

Twenty-six offline Python/Lupa/Luau-analysis checks cover local state, typed profile rejection,
false hydration, gear exclusion, stop latch, superseded/initial callbacks,
construction/recreation, failed setters, rollback failure, render-failure
atomicity, initial-render cleanup and dependency/generation guards. Twelve
existing Node preview tests remain applicable. Official Luau compilation checks
the real dependency, application source modules and assembled wrapper; it does
not execute them. New checks cover module delimiter safety, full precompilation,
missing compiler/invalid exports, valid/distinct sidebar icons and App analysis
under both old/new solvers. The analysis regression requires `LUAU_ANALYZE` or
the private official analyzer and explicitly skips when unavailable.

The user confirmed 0.1.1 executes without console errors or executor Problems.
Detailed Roblox layout, focus, nested group/search interaction, F8, 25-tab sidebar
scrolling, theme painting and destroy/recreate remain **unverified**. Browser layout
also remains unverified under the existing local-navigation restriction. Keep
these acceptance checks open; no gameplay request or account change was made.
