# Idle Mafia - Ember recode

Fresh Idle Mafia hub, planned around Ember UI and separate maintainable Luau modules.

**Status: updated-place audit and simplified local design preview implemented. Actual Ember UI, release loader and gameplay modules are not implemented yet.**

This folder is reserved exclusively for the new recode. Legacy scripts elsewhere in the repository are not part of it. All future recode source, UI, loader, tests, release metadata and documentation belong under this folder.

## Planning documents

- [Design and Ember UI layout](docs/design.md)
- [Feature parity register](docs/parity.md) - all 50 current feature IDs and supporting systems
- [Delivery roadmap](docs/roadmap.md)
- [Updated place audit: native 0.26.487.1](docs/place-audit-2026-10-20.md)
- [Simpler menus and local testing](docs/ui-simplification.md)
- [Local preview instructions](preview/README.md)

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

`README.md`, `.gitignore`, `docs/`, `preview/`, `tools/build_preview.mjs` and `tests/preview-model.test.mjs` exist. `src/`, `Loader.luau`, `vendor/` and the release manifest are future work. Private extracted game evidence stays in ignored `.private/` and is not published.

## Loading and releases

A short entry script will select one reviewed release commit, load its matching modules and reviewed Ember dependency, validate the complete release, and compose the application. Feature modules will not be fetched independently from a moving branch during gameplay. A failed or incomplete startup must not start gameplay actions. The exact loader capabilities still need verification in the intended runtime.

## Project boundaries

- Keep every automation separately configurable and preserve its protections.
- Preserve the existing one-second minimum pacing, one-request ownership, and exact 45-second unconfirmed-action policy with affected-feature cooldown.
- Keep configuration and account data local; never commit credentials, account files, private logs, executor data or extracted game snapshots here.
- Record implementation, offline verification, actual UI rendering and confirmed live outcomes separately.
- Keep the legacy hub available during development and never run competing senders together.

## Current verification

The supplied place reports native `0.26.487.1` (latest bundled notes `0.26.454`). Forty of the 48 prior selected sources changed; 42 source anchors and 852 unique city district IDs were checked without executing the saved source. All 231 legacy default keys have proposed simplification/migration dispositions.

Ten local state/schema tests and JavaScript syntax checks pass, including dedicated-tab ownership. Automated visual checks are blocked by browser local URL/file security policy; layout and actual Ember rendering remain unverified. No gameplay request or account setting was changed.
