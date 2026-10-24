# Idle Mafia - Ember recode

Idle Mafia hub using Ember UI and separate Luau modules.

## GitHub test entries

`TestEntry.luau` remains the pinned UI-only baseline. `RuntimeEntry.luau`
is a separate functional preview: it verifies the release manifest and
module hashes, binds the current MW client, and permits only ordinary Jobs
and Boss stages. Every feature switch starts off. The functional entry is
unpaused by default, so enabling Jobs or Bosses begins work when a valid
current snapshot is available. Profiles can be saved per account and place;
the Profiles tab has explicit controls to set or disable autoload. Autoload
only activates a saved profile whose enabled features are permitted in this
preview. Purchases, player attacks, and the other tabs are unavailable in
this entry.

Profiles displays selected and staged differences in both entries. Saved
profile selection and autoload controls appear only when account/place-scoped
storage is available. Choosing a saved profile fills the name field without
applying its choices. Settings offers session-only theme selection/reset, window
centering, and a clear connection-mode indicator. Each gameplay row reports
whether the current entry can run that feature.

Offline tests cover assembly, state seeding, profiles, native call shapes and
request coordination. The functional entry has not yet been confirmed on a
live Roblox client; a successful load alone does not prove server action
acceptance. The current-client version and fingerprint checks deliberately
stop startup if the game contract has changed.
Verified module bytes are cached by SHA-256, so unchanged modules can be
reused across release commits. Each launch still checks every byte against
the pinned manifest; missing or corrupt modules are fetched again.

The [tab completion plan](docs/plans/2026-10-22-tab-completion.md) tracks
all 25 UI tabs. All 25 `src/tabs/<tab>/` entries now own their UI;
the gameplay tabs also own the existing
offline action descriptors and explicit blocked contracts. Jobs, Operations
and Heists have saved-source catalog adapters; Combat has bounded read-only
target queries, and Crew has a read-only roster and border-custody slice.
The first commit-pinned functional preview is prepared; remaining tabs need
current-client integration and verification.

**Status: The published `TestEntry.luau` loaded its UI in the user's client. A separate Jobs/Bosses functional entry passes offline tests but has not been live-verified. All 25 tabs render; only Jobs and ordinary Boss stages are enabled in the functional preview. Other action paths remain offline-tested or blocked pending tab-by-tab verification.**

The offline engine now includes copied request contracts, a monotonic fake
clock, one-request broker, one-second pacing, exact 45-second uncertainty
handling, a bounded journal, initial native Jobs ownership/resource arbitration,
and a fake-storage-tested session/checkpoint ledger. A commit-pinned release
validator/loader is fake-adapter-tested. Its bootstrap now requires an
independent exact commit pin; `tools/build_release_manifest.py` only emits a
manifest when every Luau source matches that Git commit. Read-only economic and effective
buff contexts and a bounded background-read gate are fake-adapter-tested.
The personal Heist board has a read-only offline adapter contract. An opt-in
runtime host now constructs the executor file, event and remote adapters behind
an account/place/version/source gate. Current-client binding and the
commit-pinned manifest are implemented. Jobs and Operations state, planning,
request evidence and an injected shared App runtime pass local tests, but
live gameplay results remain unverified. [The next-slices plan](docs/plans/2026-10-20-engine-jobs.md)
tracks the remaining engine and ordinary Jobs work.

A [pure native call plan](docs/m2-native-call-plan.md) records saved-client
argument shapes for the supported offline features, and an injected
adapter preserves trailing nil arguments without connecting a Roblox
remote. A [read-only snapshot boundary](docs/m2-native-snapshot-reader.md)
distinguishes observed full Syncs from ordinary State ticks. They are attached
only in the guarded functional entry, not the UI-only baseline.

This folder is reserved exclusively for the new recode. Legacy scripts elsewhere in the repository are not part of it. All future recode source, UI, loader, tests, release metadata and documentation belong under this folder.

## Actual Ember prototype

The first fresh Luau UI slice is implemented: 25 tabs, 55 feature choices,
validated in-memory profiles, exclusive gear strategies, pause/stop and unload.
It is **inert**: gameplay transport and account I/O are absent. The private local
executor file is `.private/IdleMafia-Ember-UI-0.1.1.lua`; see
[build/run instructions and verification limits](docs/ember-ui-prototype.md).
The user confirmed that version 0.1.1 runs without console errors or executor
Problems. Detailed interaction/lifecycle checks and gameplay verification remain
separate from this initial execution result.

The current direction is to automate ordinary native actions for Jobs, city
Bosses and similar systems. Paid-controller unlocking is no longer a recode
task. Existing active native automation must still be detected and yielded to.

## Planning documents

- [Design and Ember UI layout](docs/design.md)
- [Feature parity register](docs/parity.md) - all 50 current feature IDs and supporting systems
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
