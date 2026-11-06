# Idle Mafia - Ember recode

Idle Mafia hub using Ember UI and separate Luau modules.

## Current published release

The November 6 merge uses the recovered r35 source and retains the subsequent
native fixes. The [current completion report](docs/completion-2026-11-06.md)
records validation and limits; the [recovery report](docs/recovery-2026-11-06.md)
preserves the earlier baseline and its historical pins.

Run the exact published runtime entry:

```lua
loadstring(game:HttpGet("https://raw.githubusercontent.com/iiSatomi/Roblox/cf6e9cb22e01a3bf66a564973384e76b55faa295/idle-mafia-ember/RuntimeEntry.luau"))()
```

For the inert UI entry, use [TestEntry at the same entry commit](https://raw.githubusercontent.com/iiSatomi/Roblox/cf6e9cb22e01a3bf66a564973384e76b55faa295/idle-mafia-ember/TestEntry.luau).

Published pins: [source e3ba6ca](https://github.com/iiSatomi/Roblox/tree/e3ba6caa213d6af0819445206b6d4435c12e28e4/idle-mafia-ember),
[manifest bc99488](https://github.com/iiSatomi/Roblox/blob/bc99488784f14e8438818c918609a02dd2c5b42d/idle-mafia-ember/manifest.json),
[entry cf6e9cb](https://github.com/iiSatomi/Roblox/tree/cf6e9cb22e01a3bf66a564973384e76b55faa295/idle-mafia-ember).

`TestEntry.luau` starts the UI without gameplay automation. `RuntimeEntry.luau`
allows all 55 independently configured controls across 27 pages. Every fresh
feature switch starts off; explicit profile autoload can restore enabled choices.
A valid current client, feature-specific proof, resource reserves, and durable
usage are still required before a native action can be sent.

The Profiles page previews differences before applying a saved profile and offers
explicit autoload controls. The Player and Alliance/Enemy pages from the recovered
version are preserved. Each gameplay row reports its current availability.

Existing nonempty state from an older release is preserved. Startup refuses an
unreviewed cross-release migration instead of resetting usage or unresolved actions.
In-game startup, read-only native checks, local tests, and confirmed gameplay
outcomes are reported separately; a successful UI load is not full gameplay acceptance.

Verified module bytes are cached by SHA-256, so unchanged modules can be
reused across release commits. Each launch still checks every byte against
the pinned manifest; missing or corrupt modules are fetched again.

## November 6 continuation

See the [completion continuation](docs/completion-2026-11-06.md) for subsequent
storage-lineage, runtime, and feature fixes, verification, and current limits.
The [55-control acceptance matrix](docs/feature-acceptance-2026-11-06.json) and
[bounded live ledger](docs/completion-live-2026-11-06.json) separate implementation
and offline tests from confirmed native paths. Current working builds record
18 confirmed mutation paths and four read/goal reports, including normal saved
Shop recovery without a second purchase; this is not 100% gameplay acceptance.
The coherent source, manifest, and entry pins above are published and remotely
verified. Published-runtime startup, one bounded Recall branch, and normal
restart passed while preserving original unresolved Operation custody. These
checks do not certify all gameplay paths.
The recovery report above remains the earlier published-release checkpoint.

## Historical implementation notes

The following notes describe earlier development checkpoints. Use the current
release description and recovery report above for today's behavior and verification.

The [tab completion plan](docs/plans/2026-10-22-tab-completion.md) tracks
the original 25 UI tabs. The recovered release now has 27 pages; all `src/tabs/<tab>/` entries now own their UI;
the gameplay tabs also own the existing
offline action descriptors and explicit blocked contracts. Jobs, Operations
and Heists have saved-source catalog adapters; Combat has bounded read-only
target queries, and Crew has a read-only roster and border-custody slice.
The first commit-pinned functional preview is prepared; remaining tabs need
current-client integration and verification.

At the original 25-tab checkpoint, the functional entry allowed only Jobs and
ordinary Boss stages. The current release's broader control availability and
separate live acceptance are documented above.

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

## Historical planned organization

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

At this prototype checkpoint, `src/App.luau`, `src/storage/Settings.luau`,
`src/ui/EmberAdapter.luau` and generated `src/ui/Catalog.luau` existed with offline
tests and a private local builder. The loader composed the inert modular App in
local tests, including a verified-cache offline restart; production packaging and
gameplay outcomes remained pending. Current results are linked above.
Private dependency/compiler bytes,
assembled executor files and extracted game evidence stay in ignored `.private/`.

## Historical loading plan

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
