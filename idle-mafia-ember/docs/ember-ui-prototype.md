# Actual Ember UI prototype 0.1

This is the first fresh Luau composition for the recode: 25 dedicated tabs,
55 independently selectable activities/permissions, compact goals and bounded
Custom controls. It uses actual Ember methods. No gameplay sender, native game
module, account file, timer or network loader exists in this application.

## Local executor file

The local build is `.private/IdleMafia-Ember-UI-0.1.lua`. Paste its contents into
the executor to inspect the UI. It creates only the prototype; no test has
executed it in Roblox yet. F8 shows/hides it. Unload closes it and invalidates
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
$py = 'C:\Users\asato\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py -m unittest discover -s idle-mafia-ember/tests -p test_ui_prototype.py -v
node --test idle-mafia-ember/tests/preview-model.test.mjs
python idle-mafia-ember/tools/build_ui_prototype.py --check
```

Generate the catalog after editing its JSON; rebuild the private executor file
only from the exact reviewed Ember source:

```powershell
python idle-mafia-ember/tools/build_ui_prototype.py --ember idle-mafia-ember/.private/ember-2026-10-20.lua
& 'idle-mafia-ember/.private/luau-compiler/luau-compile.exe' --null idle-mafia-ember/.private/IdleMafia-Ember-UI-0.1.lua
```

The builder never downloads or executes dependency source. See
[dependency review](ember-dependency-review.md) for the fingerprint, API findings,
private-source policy and compiler provenance. A fresh checkout must supply
reviewed bytes itself; no mutable-URL executor loader is published.

## Evidence and remaining checks

Twenty offline Python/Lupa checks cover local state, typed profile rejection,
false hydration, gear exclusion, stop latch, superseded/initial callbacks,
construction/recreation, failed setters, rollback failure, render-failure
atomicity, initial-render cleanup and dependency/generation guards. Twelve
existing Node preview tests remain applicable. Official Luau compilation checks
the real dependency and assembled file; it does not execute them.

Actual Roblox layout, focus, nested group/search interaction, F8, 25-tab sidebar
scrolling, theme painting and destroy/recreate are **unverified**. Browser layout
also remains unverified under the existing local-navigation restriction. Keep
these acceptance checks open; no gameplay request or account change was made.
