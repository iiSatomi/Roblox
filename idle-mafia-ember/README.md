# Idle Mafia - Ember recode

The current development source contains 26 UI pages and 55 feature switches,
composed through 21 gameplay tab modules. See the [feature completion matrix](docs/feature-completion-matrix.md)
for the actual request paths, regression coverage and live prerequisites, and the
[completion plan](docs/completion-plan.md) for acceptance criteria.

This is an actively tested development build. Registration, syntax compilation
and offline tests do not establish gameplay completion. The coordinating agent
owns the current-client integration and bounded live-test queue; unavailable
account, war, event or seasonal prerequisites remain explicit open items.
Confirmed live paths cover **17 of 55 feature switches (31%, rounded)**, up from
**0 of 55** at recovery. Other modes and the remaining 38 switches still need
live acceptance. See the [live validation ledger](docs/live-validation-2026-11-06.md)
for exact outcomes and unmet prerequisites.

Current repairs include composed Contract/Trophy goal routing, independently
bounded war Combat with authoritative enemy-roster checks, and contract-owned
empty-slot Crew hires. Hire borrowing starts off and still requires the separate
hire switch, selected tier, positive limits and a current incomplete native hire
contract. All account-changing actions retain their evidence and recovery guards.

The inert UI preview and historical milestone documents describe earlier work;
the completion matrix takes precedence for current source status. Recovery setup
and starting observations are in the [November 6 recovery report](docs/recovery-2026-11-06.md).
The published release and its pins must be rebuilt and verified before a release
is called ready. No private account snapshots or native source captures are shipped.

## Planning documents

- [Design and Ember UI layout](docs/design.md)
- [Feature parity register](docs/parity.md) - historical feature IDs and supporting systems
- [Delivery roadmap](docs/roadmap.md)
- [Next implementation tasks: engine and Jobs](docs/plans/2026-10-20-engine-jobs.md)
- [Offline ordinary Operations evidence](docs/m4-operations.md)
- [Offline earned playtime claims](docs/m4-playtime.md)
- [Offline daily and weekly Contract claims](docs/m4-contract-entries.md)
- [Offline Contract completion bonuses](docs/m4-contract-bonuses.md)
- [Offline free Briefcase picks](docs/m4-free-briefcases.md)
- [Offline guarded Bank deposits](docs/m5-bank-deposits.md)
- [Offline next-tier Safehouse upgrades](docs/m5-safehouse-upgrades.md)
- [Offline purpose-specific Bank withdrawals](docs/m5-purpose-withdrawals.md)
- [Offline ordinary Property builds](docs/m5-property-build.md)
- [Read-only personal Heist board](docs/m6-heist-board.md)
- [Offline personal Heist starts](docs/m6-heist-start.md)
- [Offline ordinary Favor help](docs/m6-favor-help.md)
- [Offline separate Heist sabotage](docs/m6-sabotage.md)
- [Read-only city Boss stages](docs/m7-boss-stage-state.md)
- [Offline ordinary city Boss attacks](docs/m7-boss-stage-attack.md)
- [Read-only Boss Token Shop quotes](docs/m7-boss-shop-state.md)
- [Read-only weekly Family Takedown state](docs/m7-family-takedown-state.md)
- [Offline current and historical Family Takedown claims](docs/m7-family-takedown-claims.md)
- [Offline free-charge Family Takedown attacks](docs/m7-family-takedown-free-attacks.md)
- [Read-only Global Boss event state](docs/m7-global-boss-state.md)
- [Offline settled Global Boss claims](docs/m7-global-boss-claim.md)
- [Offline ordinary Global Boss attacks](docs/m7-global-boss-attack.md)
- [Offline feature composition registry](docs/m2-feature-registry.md)
- [Two-slot decoded-table storage core](docs/m2-redundant-store.md)
- [Read-only native snapshot boundary](docs/m2-native-snapshot-reader.md)
- [Saved native call descriptions](docs/m2-native-call-plan.md)
- [Read-only Market browse staging](docs/m8-market-browse.md)
- [Offline sold Market earnings collection](docs/m8-market-earnings.md)
- [Account-scoped profile storage](docs/m1-profile-store.md)
- [Offline purchase-funding coordinator](docs/m2-funding-coordinator.md)
- [Read-only economic context](docs/m2-economy-context.md)
- [Read-only effective buff context](docs/m2-buff-context.md)
- [Bounded background native reads](docs/m2-read-budget.md)
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
  Loader.luau       offline-tested release-pinned loader core
  Bootstrap.luau    pin and current-client activation entry point (offline-tested)
  ReleaseAdapters.luau  pinned fetch/cache/compile adapters (offline-tested)
  ExecutorEntry.luau  joins reviewed pins, adapters and executor services
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
`ExecutorEntry.luau`, `Bootstrap.luau`, `ReleaseAdapters.luau` and `Loader.luau` load the full inert
modular App in local tests, including a verified-cache offline restart. A
production manifest, packaged client-side entry, current-client full-App test and
gameplay outcomes remain pending. Private dependency/compiler bytes,
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

The latest full result is **533 Python/Lupa offline tests** and **12 Node
preview checks**; see the shared handoff for the exact milestone evidence.
The actual Ember/application executor file compiles using official Luau 0.743.
These checks establish offline behavior and compilation, not rendered Roblox
layout or live gameplay. Both analyzer generations accept the current wrapper
and App. Embedded sources are compiled separately before execution; the wrapper
does not statically check their contents. Native/custom gear conflict rejection, false imports,
UI rollback, callback fencing and startup cleanup are covered. Automated browser
visual checks remain blocked by the existing local-navigation policy. No
gameplay request or account setting was changed.
