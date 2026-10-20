# Idle Mafia - Ember recode

Fresh Idle Mafia hub, planned around Ember UI and separate maintainable Luau modules.

**Status: planning. No runnable loader, UI prototype, or gameplay modules have been added yet.**

This folder is reserved exclusively for the new recode. Legacy scripts elsewhere in the repository are not part of it. All future recode source, UI, loader, tests, release metadata and documentation belong under this folder.

## Planning documents

- [Design and Ember UI layout](docs/design.md)
- [Feature parity register](docs/parity.md) - all 50 current feature IDs and supporting systems
- [Delivery roadmap](docs/roadmap.md)

The first implementation milestone is an inert Ember UI prototype. Gameplay scripts follow a reviewed layout and a tested request/recovery engine. Features will be freshly implemented from reviewed requirements and current game evidence; old production modules will not be copied, imported, or wrapped.

## Planned organization

```text
idle-mafia-ember/
  README.md
  docs/             design, parity, roadmap and future evidence
  Loader.luau       future short release-pinned entry script
  src/
    App.luau        future composition/startup
    ui/             Ember pages, panels and bindings
    features/       focused gameplay domains
    engine/         scheduling, requests, policies and recovery
    game/           validated state/catalogs and native adapters
    storage/        profiles and settings
    diagnostics/    journals, health and redacted exports
    loader/         module registry and verified fetching/cache
  tests/            offline logic, failure scenarios and UI contracts
  vendor/           reviewed dependencies where redistribution permits
  manifest.json     future release module/dependency/checksum manifest
```

Only this README and `docs/` exist at this milestone. The remaining paths describe the intended structure, not implemented functionality.

## Loading and releases

A short entry script will select one reviewed release commit, load its matching modules and reviewed Ember dependency, validate the complete release, and compose the application. Feature modules will not be fetched independently from a moving branch during gameplay. A failed or incomplete startup must not start gameplay actions. The exact loader capabilities still need verification in the intended runtime.

## Project boundaries

- Keep every automation separately configurable and preserve its protections.
- Preserve the existing one-second minimum pacing, one-request ownership, and exact 45-second unconfirmed-action policy with affected-feature cooldown.
- Keep configuration and account data local; never commit credentials, account files, private logs, executor data or extracted game snapshots here.
- Record implementation, offline verification, actual UI rendering and confirmed live outcomes separately.
- Keep the legacy hub available during development and never run competing senders together.
