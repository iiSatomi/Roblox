# Idle Mafia - Ember recode

Fresh Idle Mafia hub, planned around Ember UI and separate maintainable Luau modules.

**Status: updated-place audit and simplified local design preview implemented. Actual Ember UI, release loader and gameplay modules are not implemented yet.**

This folder is reserved exclusively for the new recode. Legacy scripts elsewhere in the repository are not part of it. All future recode source, UI, loader, tests, release metadata and documentation belong under this folder.

## Actual Ember prototype

The first fresh Luau UI slice is implemented: 25 tabs, 55 feature choices,
validated in-memory profiles, exclusive gear strategies, pause/stop and unload.
It is **inert**: gameplay transport and account I/O are absent. The private local
executor file is `.private/IdleMafia-Ember-UI-0.1.lua`; see
[build/run instructions and verification limits](docs/ember-ui-prototype.md).
Actual Roblox rendering remains unverified while MCP is unavailable.

The current direction is to automate ordinary native actions for Jobs, city
Bosses and similar systems. Paid-controller unlocking is no longer a recode
task. Existing active native automation must still be detected and yielded to.

## Planning documents

- [Design and Ember UI layout](docs/design.md)
- [Feature parity register](docs/parity.md) - all 50 current feature IDs and supporting systems
- [Delivery roadmap](docs/roadmap.md)
- [Updated place audit: native 0.26.487.1](docs/place-audit-2026-10-20.md)
- [Simpler menus and local testing](docs/ui-simplification.md)
- [Native reuse and gear audit](docs/native-reuse-audit.md) - all 55 controls, six supporting systems and 15 pass keys
- [Local preview instructions](preview/README.md)
- [Actual Ember UI prototype](docs/ember-ui-prototype.md)
- [Reviewed Ember dependency](docs/ember-dependency-review.md)

The user requested the same functions with substantially fewer configuration options. The first slice is a local interactive design preview with 25 dedicated system tabs, including separate Heists, Jobs, Collection, Money, Property, Shop and Black Market tabs. Combat groups player fights, city Bosses, Family Takedown and Global Bosses, and has four Custom overrides and Properties has three. All 50 old feature IDs remain accounted for. Actual Ember and gameplay scripts follow the simplified layout and a tested request/recovery engine. Features will be freshly implemented from reviewed requirements and current game evidence; old production modules will not be copied, imported, or wrapped.

## Planned organization

```text
idle-mafia-ember/
  README.md
  docs/             design, parity, roadmap and current source evidence
  preview/          interactive simulated UI and standalone HTML
  tools/            standalone preview generator
  Loader.luau       future short release-pinned entry script
  src/
    App.luau        inert UI composition; gameplay follows separately
    ui/             generated catalog and actual Ember adapter
    features/       focused gameplay domains
    engine/         scheduling, requests, policies and recovery
    game/           validated state/catalogs and native adapters
    storage/        current scalar model; persistent profiles follow separately
    diagnostics/    journals, health and redacted exports
    loader/         module registry and verified fetching/cache
  tests/            offline logic, failure scenarios and UI contracts
  vendor/           reviewed dependencies where redistribution permits
  manifest.json     future release module/dependency/checksum manifest
```

`src/App.luau`, `src/storage/Settings.luau`, `src/ui/EmberAdapter.luau` and generated
`src/ui/Catalog.luau` now exist, with offline tests and a private local builder.
The remote `Loader.luau`, gameplay modules, persistent account profiles and
release manifest remain future work. Private dependency/compiler bytes,
assembled executor files and extracted game evidence stay in ignored `.private/`.

## Loading and releases

A short entry script will select one reviewed release commit, load its matching modules and reviewed Ember dependency, validate the complete release, and compose the application. Feature modules will not be fetched independently from a moving branch during gameplay. A failed or incomplete startup must not start gameplay actions. The exact loader capabilities still need verification in the intended runtime.

## Project boundaries

- Keep every automation separately configurable and preserve its protections.
- Preserve the existing one-second minimum pacing, one-request ownership, and exact 45-second unconfirmed-action policy with affected-feature cooldown.
- Keep configuration and account data local; never commit credentials, account files, private logs, executor data or extracted game snapshots here.
- Record implementation, offline verification, actual UI rendering and confirmed live outcomes separately.
- Keep the legacy hub available during development and never run competing senders together.

## Current verification

The supplied place reports native `0.26.487.1` (latest bundled notes `0.26.454`). Forty of the 48 prior selected sources changed; 42 source anchors and 852 unique city district IDs were checked without executing the saved source. All 231 legacy default keys have proposed simplification/migration dispositions. The native reuse audit additionally checks all 55 feature controls against 80 source anchors: native set-aware equip/sort are preferred, custom gear needs a demonstrated gap, and owned controllers are conditional delegates.

Twenty new Python/Lupa checks and the twelve existing Node preview checks pass.
The actual Ember/application executor file compiles using official Luau 0.743.
These checks establish offline behavior and compilation, not rendered Roblox
layout or live gameplay. Native/custom gear conflict rejection, false imports,
UI rollback, callback fencing and startup cleanup are covered. Automated browser
visual checks remain blocked by the existing local-navigation policy. No
gameplay request or account setting was changed.
