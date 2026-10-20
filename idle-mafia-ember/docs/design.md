# Idle Mafia Ember recode — proposed design

Date: 2026-10-20. Status: planning proposal; gameplay implementation has not started.

## Brief and decisions

Build a fresh Idle Mafia hub with Ember, preserving the current hub's useful functions while replacing its implementation. The user explicitly requested a full recode, clear organization, UI planning before gameplay scripts, maintainability, stability, reliability, and preparation for future game changes. Do not copy/paste, rename, wrap, or import the old production modules into the new application.

The user selected **grouped pages with clear summaries**, focused feature pages, and collapsed advanced options. Routine layout and architecture decisions in this proposal use that preference. Review this proposal before implementation; approval of the page organization is not approval of every proposed gameplay change.

Follow-up preference: the user authorized GitHub hosting if useful and prefers separate modules loaded by a short main UI/entry script. The primary delivery design is now a GitHub-hosted modular release with a small loader. The user selected the existing public `iiSatomi/Roblox` repository and requested a dedicated `idle-mafia-ember/` folder containing only the new recode. This folder is the canonical recode root; the surrounding workspace and legacy scripts are outside its publication scope.

Deliverables from this planning milestone:

- This design: architecture, UI, reliability, migration, and acceptance criteria.
- [Feature parity register](parity.md): current functions, placement, and preservation requirements.
- [Delivery roadmap](roadmap.md): ordered, gated milestones. Detailed implementation recipes follow approval of this design and current game evidence.

## Evidence and limits

The baseline is the source-built **Fluent v0.48.57**, identified in `scripts/build_mafia_hub.py`, with native compatibility target `0.26.253`. The latest local full game-source extraction is `imports/idle-mafia-2026-10-11-full/`; its `GameVersion` returns `0.26.253`. Neither is proof of the current October 20 game contract.

Inspected the project workflow, handoff, Ember workspace reference, current module/build structure, feature-label/status registry, feature controls, settings defaults, planner/controller references, and recent git history. This is a planning audit, not a line-by-line certification of every old behavior. The first implementation milestone expands it to every setting and transaction.

The old source is already partly modular. Its main concentration points are `Core.lua` (3,053 lines), `Planner.inc.lua` (1,948), `Interface.inc.lua` (1,273), and `Actions.inc.lua` (1,131). Splitting another large runtime into include files would preserve the coupling the user wants removed. These counts describe the files inspected on October 20, not a permanent code-size limit.

The handoff reports 971 local/mock tests for v0.48.57. That historical result has **not been rerun for this documentation-only milestone** and does not validate a rewrite. Some old features have live observations; many remain local-only. Fresh evidence must be recorded per new feature.

The lower Coverage and Safety sections of `docs/IdleMafia-Hub.md` and several handoff paragraphs describe older releases. Examples include the obsolete five-second global minimum, indefinite pending behavior, entitlement-based Crew Auto Roll, and older Progression UI. Current source and newest feature evidence take precedence. The current interface exposes Auto Contracts and Trophy Focus; it does not expose the historical Auto Progression master controller. Do not accidentally promise the historical controller as an existing current function.

On October 20 the official [Ember overview](https://rbx.lol/docs/ember) and [lifecycle documentation](https://rbx.lol/docs/ember/guides/lifecycle) were accessible. Raw `ember.lua` could not be fetched through the web reader (unsupported content type), and shell fetching failed DNS resolution. Consequently the workspace's October 12 static findings remain **unrechecked source findings**, not verified facts about today's served bytes. Review and fingerprint the actual dependency before implementation.

No live client was inspected, no gameplay request was sent, no settings were changed, and no bundle was rebuilt during planning.

## Approach considered

| Approach | Benefit | Cost / decision |
| --- | --- | --- |
| **Fresh modular Luau application, GitHub-hosted modules with a small loader** | Independent domain logic, one request owner, thin Ember views, readable source, focused updates | Requires a version-consistent loader and network/cache failure handling. Recommended following the user's GitHub/module preference. |
| Fresh single handwritten script with tidy sections | Quick initial setup | UI and behavior will tend to grow together again. Rejected for maintainability. |
| New Ember UI wrapped around existing modules | Fastest feature reuse | Carries old coupling and violates the requested fresh implementation. Rejected. |

Keep the old hub available as a separately runnable fallback. The new application must never require the old one to run. Developers maintain focused source files with comments and contracts. An optional generated single-file release can remain a troubleshooting/offline alternative built from the exact same new modules; it is not the primary maintained source or preferred delivery path.

### GitHub delivery and module loading

The user's executable entry script stays short. It selects a reviewed release and hands startup to a loader; `App.luau` composes Ember views, the engine and features. Neither entry script contains feature implementations. Individual modules return explicit exports/factories with dependencies supplied by composition; they do not start loops or send requests while being downloaded/initialized.

```text
short user entry script
  -> loader fixed to one release commit
    -> release manifest and required modules from that same commit
      -> validate complete release, compile modules, resolve dependencies once
        -> App: construct state + Ember pages, then enable explicit startup
```

Roblox's normal module mechanism must not be assumed to fetch arbitrary GitHub URLs. This executor-based deployment needs a small custom loader using confirmed HTTP/source-compilation capabilities, with an explicit module-ID registry and dependency resolver. Establish supported primitives in M0/M1; do not invent compatibility with an untested runtime.

Release rules:

1. One loader selects one full commit SHA. Every module, manifest and reviewed Ember dependency comes from that release or its separately pinned dependency. Never independently fetch each module from moving `main`/`latest` URLs. GitHub documents that [commit-based file links preserve the exact version](https://docs.github.com/en/repositories/working-with-files/using-files/getting-permanent-links-to-files), whereas branch file contents can change.
2. The manifest declares schema/build ID, module paths/IDs, dependency order and expected bytes/hashes. Validate paths, reject unknown/duplicate IDs and dependency cycles, and verify the complete required set before starting the application. Pinning avoids mixed releases; checksums detect inconsistent/corrupt bytes and do not independently establish publisher authenticity.
3. Prove a portable or runtime-provided hash verifier before relying on integrity checks. Do not silently skip required validation when an API is unavailable. Compile downloaded modules before activating the session; a syntax or module-contract error must not leave a partly started sender.
4. Prefetch modules for the selected release at startup, with bounded attempts/timeouts. Module resolution after startup uses the in-memory registry; gameplay actions do not trigger fresh GitHub downloads. Cache exports so loading two panels cannot construct two brokers or feature loops.
5. An optional filesystem cache is keyed by commit and verified manifest. Write a staged complete set and mark it usable only after checks succeed. Never mix partial/new files with old cached modules. If network access fails, use only an explicitly supported complete verified cache of the selected release; otherwise show a startup error and send nothing.
6. No automatic hot reload or switching release under an active transaction. Updating changes the next launch's selected release after stop/reconciliation; rollback chooses a complete prior release and preserves account settings/uncertainty records.
7. Public raw modules would be readable by other people. Choose an existing authorized repository or a dedicated repository and its visibility before publishing. Never embed GitHub credentials in the loader. A private repository needs a separately reviewed access/distribution method; do not assume anonymous raw access or token injection is acceptable.
8. Publish only the reviewed new source, dependency files permitted for redistribution, tests, docs and release metadata. Exclude account data, logs, extracted game snapshots, executor files and unrelated projects. Keep local developer work and production release selection distinct.

This loader is a packaging boundary, not a second gameplay scheduler. GitHub availability affects startup/update; it must not be a dependency for each gameplay action. Versioning/cache failures are part of the reliability test plan.

## Product principles

1. Show what the hub is doing, why it is waiting, and what would allow it to continue.
2. Give every automation its own switch. A strategy or goal can request work only within an explicit, visible activity policy.
3. Use one authoritative settings model. Two controls for the same value never create two independent values.
4. Distinguish **desired on**, **allowed**, **ready**, **sent**, **confirmed**, and **unconfirmed**.
5. Treat unknown game state as unknown. Do not manufacture a value, cooldown, successful result, profitable sale, or probability.
6. Contain a feature failure so unrelated compatible routines can continue.
7. Preserve established resource, item, player-combat, Family, and transaction protections.
8. Update game contracts through adapters and evidence, rather than patching UI callbacks.

## Ember UI design

### Visual direction

Use a quiet, legible control panel: Slate-inspired charcoal surfaces, warm copper emphasis, neutral text, and restrained status colors. Suggested tokens are background `#171B22`, surface `#202630`, border `#343E4C`, text `#ECEFF4`, secondary text `#B4BECC`, and accent `#D7A66A`. Contrast must be checked in the actual Ember renderer before accepting the palette; use a tested built-in theme if it falls short. Reserve red for errors/stop, amber for waits/uncertainty, and green for confirmed outcomes. Every status also has text.

Use Ember's supported fonts and control styles first. No external font or image dependency is required. Keep effects modest, respect reduced motion, and offer theme/effects preferences. Avoid a custom UI framework or decorative splash screen.

Desktop target: approximately 900 × 620 with a 210-pixel rail, scalable within the viewport. Check the actual minimum readable size during the UI prototype. Smaller screens use stacked controls and scrolling. Verify Ember's sidebar overflow before committing to all section labels; do not assume native nested navigation or custom tabs that Ember does not provide.

### Page map

The following are Ember sections. The groupings inside them are collapsible Ember groups, not a second navigation framework.

| Page | Visible summary and primary groups |
| --- | --- |
| Overview | Session health, current action, next choice, active blockers, resources, event summary, pause/resume, Emergency Stop, unload |
| Goals & Rewards | Auto Contracts, contract-priority preference, objective selection, Trophy Hunter/Focus, contract/bonus/playtime/group claims, Briefcases, skill allocation |
| Heists & Favors | Personal start and collect, Favor help, sabotage, board/control status, reserves and daily limits |
| Jobs & Operations | Separate Job and Operation groups; job choice/mastery/city, Operation start and collect, selectors and limits |
| Combat | Player-attack permission, ordinary mugs, war targets, discovery/scouting, safety, target history and recent outcomes |
| Bosses & Events | City Boss stages, Boss Token Shop, Global Boss attack and claim, event eligibility and caps |
| Crew & Gear | Rerolls, healing, sorting, training, native equip, custom gear/sets, read-only whole-loadout outlook, transaction recovery |
| Inventory & Collection | Cosmetic optimization, safe surplus deposit, chest opening, restoratives, item protection and Collection explanation |
| Shop & Market | Cash Shop, read-only Market research, owned-item sale, flip, rent, earnings collection, exclusions, active transaction/ledger |
| Money & Property | Banking and funding permissions, property purchases/replacement, Safehouse, prestige, budgets and reserved cash |
| Family & Territory | Takedown attacks/rewards, separate cash/stamina/Gold contributions, Territory watcher/station/recall, training/recovery rotation, residency |
| Profiles | Active versus selected profile, create/save/load/autoload, import preview, account identity, deletion |
| Settings | Appearance/layout/keybinds, idle protection, event-priority preference, supported timing controls, notification/privacy preferences |
| Diagnostics | Compatibility, feature health, action history, timing, storage failures, recovery details, redacted export |

Shop & Market and Family & Territory use extracted subpanel files so a visually grouped page cannot become another monolithic source file. A future split into additional sections remains possible without changing stable settings IDs.

### Common feature pattern

Each automation follows the same order:

1. A one-line purpose and current status/reason.
2. Its own run toggle and the most common choice or two.
3. A short effective-limits summary, including limits hidden in collapsed groups.
4. Collapsed **Selection**, **Limits**, and **Advanced** groups when applicable.
5. A compact last-result line with timestamp, and a link/button to its filtered Diagnostics view.

Disabled controls explain their missing requirement. Turning a control off changes backend eligibility immediately; disabling an Ember row by itself is not a stop mechanism. Hiding an advanced group does not disable its saved limits. Missing access/unlock and absent compatible state are distinct from feature errors.

Use text inputs for large currency amounts and exact counts; sliders for bounded percentages and small ranges. Show units and whether zero disables a rule. Keep catalog identity separate from display names. For long catalogs, use a filter input and a small filtered dropdown; Ember's built-in dropdown has no documented internal option search. Filtering must preserve selected IDs outside the visible results, and duplicate labels must remain distinguishable.

Window search matches feature labels, descriptions, and groups. Also provide an Overview **Show feature** selector for direct section selection/group expansion. Neither navigation control changes settings or sends actions.

### Text wireframe: Overview

```text
Idle Mafia                         [Search controls] [Hide]
Account / native build / hub build
-----------------------------------------------------------
Overview             Session: Running   State: fresh 0.2s
Goals & Rewards      Current: Collect Operation  [3s elapsed]
Heists & Favors       Next: Best eligible Job
Jobs & Operations    [Pause] [Emergency Stop · F8] [Unload]
Combat               -------------------------------------
Bosses & Events      Resources   Cash / Energy / Stamina / HP
Crew & Gear          Attention   Crew: waiting for recovery
Inventory ...        Activities  Jobs: Ready
Shop & Market                    Favors: Waiting · daily cap
...                  Last result Operation collected · 12:41
                     [Show feature] [View recent activity]
-----------------------------------------------------------
Running · Heist board in 8s · Profile: Farming · Saved
```

These values illustrate layout only; they are not runtime observations. Standard Ember Status/Description rows may replace columns if that yields better readable layout without custom controls.

### Text wireframe: a feature group

```text
PERSONAL HEISTS
Waiting · next free slot in 04:20
[ ] Start personal heists      [ ] Collect results
Priority [Best chest]          Maximum duration [2 hours]
Limits: Energy keep 10 · maximum stake $... · 6 helpers
> Selection
> Limits
> Advanced
Last result: Confirmed collection at 12:41
[View activity]
```

### Overview and stop semantics

- **Pause** blocks new requests globally while retaining desired feature choices and observing an already-sent action. Resume uses fresh state and preflight; it does not replay a queue. Pause is a session state, not a silent rewrite of the active profile.
- **Emergency Stop / F8** disables effective automation and goal execution immediately, clears unsent proposals, and stops idle input. It cannot recall sent requests. Keep a session stop latch through UI rebuild; explicit Resume is required before saved desired switches become effective again. Display which choices will resume. Do not automatically start a different account session from a stopped old session.
- **Unload** performs stop, safely persists settings and unresolved evidence, destroys owned UI/connections, and prevents future sends. It must not erase an uncertain transaction. If necessary, a minimal non-sending observer remains for an outstanding transport callback; it has no UI or restart authority.
- The F8 listener belongs to the session supervisor and works when rendering is degraded or the window is hidden. Avoid duplicating an Emergency Stop button on every page; use a persistent status-bar action if supported, otherwise the visible Overview action plus the global key.

### Ember integration rules

Read `docs/Ember-UI-Reference.md` and review the actual served source before writing the adapter. Pin a reviewed copy with provenance/hash, subject to its redistribution terms; if redistribution is not permitted, load a reviewed immutable artifact through an explicitly documented dependency policy. Do not fetch an unreviewed mutable latest release on each launch.

- Construct session state, storage, cleanup ownership, and command guards before UI controls.
- Build all views inertly; never start gameplay from `FireOnStart`, an initial/restored callback, reapply, or a control setter.
- Ember callbacks dispatch validated local settings/commands. The engine alone dispatches game requests.
- `ui/EmberAdapter.luau` owns library-specific handle differences, typed values, disposal, and rendering failures. Domain modules never reference Ember handles.
- Application settings/profiles own gameplay persistence. Ember persistence, if enabled, owns only layout/appearance in a separate namespace. Avoid competing stores for run toggles.
- Update controls individually and check setter results. Do not depend on `SetValues` for false booleans or raw `GetValues` for JSON serialization until current-source tests establish safe behavior.
- Hydrate controls silently from validated settings. A hydration barrier and session generation make delayed initial callbacks harmless.
- Track subscriptions and connections; explicitly fence spawned tasks. For any close-reverting automation control, set `RevertTo=false` and retain independent supervisor cleanup.
- Refresh changed status text at most once per second for ordinary display; critical stop/uncertainty state renders immediately. Rendering exceptions cannot kill planning or create requests.
- Do not include the old confirmation-bypass testing option in normal gameplay settings. Fault injection belongs in an offline test harness. Preserve timing visibility and diagnostics without advertising unsafe production execution as a parity requirement.

## Fresh source architecture

Proposed new root: `idle-mafia-ember/`. The old `mafia/`, its builder, and `IdleMafia-FluentHub.lua` remain a separate product until cutover.

```text
idle-mafia-ember/
  README.md                         entry point and developer guide
  Loader.luau                       short version-pinned public entry
  src/
    App.luau                        composition and explicit startup stages
    app/Session.luau                session generation, pause/stop/unload
    app/Capabilities.luau           platform capability discovery
    loader/Modules.luau             verified fetch/cache and module registry
    engine/Contracts.luau           shared typed data contracts
    engine/Scheduler.luau           eligibility, priorities, fairness
    engine/RequestBroker.luau       only outbound request owner
    engine/ActionLifecycle.luau     confirmation, uncertainty, late evidence
    engine/Policy.luau              effective per-feature authorization
    engine/ResourceLedger.luau      reserves, funding, exposure, confirmed spend
    engine/Recovery.luau            journals, startup reconciliation
    game/StateReader.luau           normalize native state into snapshots
    game/CatalogReader.luau         native catalogs and helper metadata
    game/Compatibility.luau         feature capability/shape checks
    game/adapters/<domain>.luau     exact request and response contracts
    features/<domain>/              focused planners, rules, confirmers
    features/<domain>/Transaction.luau  only for multi-step domains
    goals/Contracts.luau            supported objective intents
    goals/Trophies.luau             progress and goal intents
    goals/EventPriority.luau        optional ordering of eligible actions
    storage/Settings.luau           schema, defaults, validation, migrations
    storage/Profiles.luau           profile semantics and import preview
    storage/Files.luau              bounded writes, backups, capabilities
    diagnostics/Journal.luau        bounded action lifecycle events
    diagnostics/Health.luau         independent loop/state/UI health
    diagnostics/Export.luau         sanitized evidence bundle
    ui/EmberAdapter.luau            reviewed Ember API boundary
    ui/Bindings.luau                local commands and state subscriptions
    ui/pages/<page>.luau            page composition only
    ui/panels/<domain>.luau         reusable feature-specific groups
  tests/unit/                       pure planners and settings
  tests/scenarios/                  fake clock/transport/state journeys
  tests/ui/                         Ember adapter/hydration contracts
  tests/fixtures/                   sanitized, versioned native examples
  vendor/                           reviewed dependency and provenance
  manifest.json                    module IDs/dependencies, release checksums
  build/                            release metadata, optional fallback bundle
```

The filenames are a proposed ownership map, not empty files to generate now. Add domain files only when their slice is implemented. Pure modules accept injected state, clock, settings, and context; they do not access `game`, executor globals, disk, or UI. Keep Roblox/executor effects in explicit ports. Use strict Luau types for new production modules where available, and avoid hidden circular initialization through a shared global table.

Target modules a developer can read in one sitting: roughly 150–350 lines of logic where practical. More than 500 lines triggers a responsibility review, not arbitrary fragmentation. A page may assemble several panels. No new `Core` dumping ground, global all-features switch statement, or concatenated shared-local runtime includes.

### Data flow and ownership

```text
native reads -> validated snapshot/catalog -> feature planners
                         ^                     |
validated settings -> policy/goal intents -> proposals
                                              |
                                    scheduler + resource ledger
                                              |
                                    broker immediate preflight
                                              |
                                    exact native adapter request
                                              |
replication/validated reply -> feature confirmation -> journal/store
                                              |
                                view state -> Ember render
```

Only `RequestBroker` invokes adapters for network requests, including read-only queries. Feature planners return a proposal or a typed wait/block reason. Goal controllers return intents; they cannot change user toggles or call remotes.

Conceptual contracts to lock before implementation:

| Contract | Required information and rule |
| --- | --- |
| Snapshot | Account/place/server identity, native build, revision, observed time, freshness per subsystem, normalized state; no missing-number-to-zero conversion |
| FeatureDecision | Ready proposal or state `off/waiting/blocked/degraded`, stable reason code, user text, optional next check time |
| ActionProposal | Feature/action IDs, origin (manual/contract/trophy), exact target identity, snapshot revision, expiry, authorization requirements, costs, resource/item reservations, adapter action ID |
| ActionRecord | Unique local ID, session generation, state, first-send timestamp, evidence policy, before-state facts, attempt/exposure counters, outcome; no secret data |
| Confirmation | `confirmed`, `rejected`, or `pending`, with exact evidence and identity; absence of evidence cannot produce success |
| GoalIntent | Goal identity, supported eligible activity, preference and reason; sensitive permissions remain external to the goal |
| ViewState | Desired/effective on state, controller source, current reason, last action/outcome, fresh/stale state and next check time |

These describe data requirements, not final API signatures. Define exact Luau signatures in the approved foundation implementation plan. Avoid inventing remote names or argument shapes from these local concepts.

## Reliability contract

### Request lifecycle

```text
proposed -> validated -> sent -> observing -> confirmed
                                   |          rejected
                                   |          unconfirmed/skipped (45s)
unsent -> discarded (disabled / stale / changed identity / policy)
```

Once sent, an action is never treated as an unsent proposal. Its monotonic first-send deadline is exactly 45 seconds. Before that deadline, an uncertain mutation retains local action ownership. Successful invocation alone is not a generic confirmation; each adapter declares whether exact replicated proof, a validated action-specific reply, or both are required. Document any current Scout/Attack reply fallback explicitly and recheck it against current native behavior rather than applying it to all actions.

At 45 seconds, record **unconfirmed/skipped**, release local admission ownership, record duplicate risk, and cool down the owning feature/shared transaction family for 45–300 seconds. Other eligible features may continue. This is the existing user-selected tradeoff; it does not cancel a server request and cannot guarantee that an old invocation has stopped executing remotely. Never report both “strictly one outstanding server invocation” and “release a hung invocation after 45 seconds” as guarantees.

There is at most one locally admitted outbound request at a time. All sequential reconciliation reads use that same transport admission path. While a transport call is actually unresolved before the deadline, observe passive replicated state rather than starting parallel probes. When transport has returned but confirmation still needs a query, that action owns the next serialized reconciliation read. Bounded read-only timeouts release earlier with backoff.

Keep bounded identity-keyed late-result records after release. Late callbacks cannot release a new action's gate, re-enable a stopped feature, replay a mutation, overwrite a new session, or count a result twice. A conclusive matching late result may amend the historical record and resource accounting exactly once; expose the amendment and revalidate conflicting work before any later send.

Actions involving a partly completed multi-step transaction may require manual review after release. Releasing the global slot does not authorize guessing the transaction's next step. Heists/Favors/sabotage share protocol and cooldown ownership where current evidence requires it.

### Scheduling and competing work

- Default/minimum outbound send spacing remains **one second**; planner eligibility checks every **0.25 seconds**. This is not a one-second maximum between requests or a verified safe server rate.
- Hard safety and session pause/stop checks precede every selection and send.
- Preserve **Heists → Favors → Operations → other eligible work**. Shared board/funding prerequisites inherit the action's priority; a waiting/ineligible feature yields.
- After those tiers, use deterministic fair turns with bounded optional event/contract/trophy preference. A repeatedly ready background researcher cannot consume all combat turns; a recurring rejected target cannot starve saved-target lookup.
- Re-evaluate after each confirmed result or relevant state revision. Keep at most one provisional next choice rather than a long stale action queue.
- Preflight immediately before send checks current identity, policy, resource/item ownership, native unlock/cost, target, timers, cooldown, attempt cap, quote/luck freshness, and transaction stage.
- Event priority only reorders already-permitted work. It cannot enable crates, hires, spending, attacks, or Family mutations.
- A feature exception yields a typed error/backoff for that feature. Shared adapter failure cools its dependents; a missing global state source stops sends globally while health display continues.
- Do not permit watchdogs to start a second scheduler when a loop or network request is slow. Monitor scheduler heartbeat, native-state freshness, broker progress, and UI rendering separately.

### Resources, inventory, and transactions

The resource ledger records cash/bank/Gold/energy/stamina/health and protected items as distinct assets. Features declare reservations; banking cannot remove cash saved for an eligible property purchase. Bank withdrawals are exact-shortfall, purpose-specific permissions, followed by confirmation and a fresh action preflight. A reserve is not proof the resource is still available after manual activity.

Track **attempted exposure** separately from **confirmed spend**. For finite send caps such as Global Boss attacks, rent, Boss Shop, and prestige, an unconfirmed send still consumes the attempt cap. Retain each feature's existing confirmed-use limits and track possible unconfirmed use alongside them so a silent completion cannot escape a spending cap. Do not relabel session caps as persistent daily limits. Daily limits use the native day/reset definition and account identity, with persistence.

Transaction state machines cover property replacement, reroll dismiss/hire, gear withdraw/equip/deposit and complete sets, Market withdraw/buy/list/collect, heist sequence flow, and Territory recall/recovery/station. Each step has exact pre-state, expected proof, protected identities, ownership and restart rules. Store intent before a risky step; storage failure blocks a mutation that depends on durable recovery. Do not promise rollback for deletion, consumed currency, sold items, completed attacks, or other irreversible server effects. A compensating action needs its own verified contract and permission.

Uncertain native heist sequence ownership cannot be fixed by inventing the next number. Missing ownership or interrupted old-hub work displays a blocker and requires evidence or a fresh session. Do not automatically replay old saved transaction records.

### State, storage, reload, and game updates

- Capability detection covers filesystem, clipboard, HTTP/dependency loading, input provider, clocks, and supported runtime APIs. Read-only UI can work without file saving; risky workflows requiring durable journals stay unavailable with a clear reason.
- Use per-subsystem freshness, revision, and shape validation. Invalid required fields block only dependent actions. Native helpers/catalogs are preferred to hardcoded reward/unlock/price assumptions.
- Global native version mismatch is visible; feature-level contract evidence decides availability. An unknown request/response shape fails closed for that feature without disabling known compatible functions.
- Choose account storage by place ID and stable user ID; retain display name as metadata. Separate new files under `IdleMafiaEmber/<placeId>/<userId>/`. Never merge accounts by a display-name match.
- Files use schema version, bounded size, serialized writes, backups, and write/read-back checks. Use temp/replace only if actual filesystem primitives support it; do not advertise atomic replacement on executors that lack rename.
- A corrupt file is quarantined and explained; defaults do not silently authorize automation. Memory-only mode states that recovery does not survive session termination.
- Reloading the new hub must find the old new-hub supervisor before replacing Ember UI. Refuse a second sender while an earlier instance owns work. Detect an active legacy Fluent controller as a conflict and explain a safe handoff; never run both hubs together.
- Respawn invalidates character references and relevant snapshots; it does not reinstall the broker or duplicate features. Teleport writes checkpoint/uncertainty where possible and stops. Manual rerun remains baseline; optional future re-execution must never replay actions.
- Bot-check detection pauses sends and exposes native manual resolution. No solving, auto-answering, bypass, or anti-cheat evasion is part of the recode. The old automatic Market answer path is explicitly excluded; preserve observation, pause, and sanitized evidence capture instead.

## Feature preservation and behavior changes

The companion parity register covers all **50 IDs** in the current feature-label registry plus controllers, settings, observations, profiles and recovery. Every row gets a new-source owner, UI control mapping, current-native evidence, offline tests, and live evidence before it can be called complete. A registry ID is not necessarily an independent toggle: `withdraw` is a funding permission, `crewHire` is contract-owned, and sabotage uses its own saved option.

Preserve outcomes and safeguards, not bugs, old implementation structure, obsolete API calls, or unsupported toggles. All user-visible settings need a disposition: preserved, renamed/mapped, merged with equivalent semantics, unavailable due to missing current evidence, or deliberately excluded with explanation. The next audit must extract every control/default and record its disposition; 50 feature IDs alone are not proof of all-setting parity.

Explicit proposed differences requiring review with the design:

- Add non-destructive Pause/Resume and a stop latch separate from saved desired settings.
- Make goal borrowing visible as an explicit activity permission matrix; Auto Contracts/Trophy Focus can preserve their current ordinary-personal borrowing behavior, while sensitive actions keep separate opt-ins.
- Import legacy profiles through a local preview. Preserve settings and data, but do not let importing silently start automation. After first review, retain explicit new-hub autoload/resume preferences, including the chosen player-combat permission.
- Remove production confirmation bypass and automatic bot-check answers. Neither belongs in a reliability-oriented runtime.
- Keep destructive property replacement and Crew dismissal separately protected and off in fresh/imported-unreviewed sessions. Do not add new destructive inventory actions.
- Treat the historical broad Auto Progression controller as a later optional product decision. Do not resurrect it by quietly reading obsolete settings into new behavior.

## Configuration and import UX

The Profiles page always shows **Active profile** separately from **Selected profile** and states whether edits sync to the active one. Profile selection alone never activates it. Preserve create, save selected, load now, next-run load, autoload, autoload off, explicit deletion, account overview, and durable mug/scout/Market data where schemas can be proven.

First legacy import reads existing files without modifying them, validates account/place/schema, previews mapped controls and unavailable functions, and lists enabled automation, permission, currencies, destructive options, and unresolved transactions. Import produces a new inactive profile. Enabling it is a distinct deliberate action. Existing uncertain journal/gear/Market/property/heist records must block affected actions until reconciled; a new filename is not proof old work disappeared.

Active-profile edits synchronize through one debounced settings writer. Runtime counters, late evidence, transaction stages, and display-only values remain outside profile snapshots. A profile switch pauses new sends and applies one validated settings revision when the current action is settled or explicitly in its documented uncertainty recovery state. UI hydration never dispatches requests. Failed saving is visible; do not show “Saved” merely because the writer was scheduled.

## Verification strategy and definition of done

Use newly authored tests and fixtures. Old tests are useful for identifying requirements and historical failures; passing the old suite alone cannot validate new modules, and copied production functions are forbidden. Reference old behavioral cases in the evidence register without importing old production modules.

| Layer | Evidence required |
| --- | --- |
| Pure logic | Boundary values, missing fields, stale facts, filters/reserves, exact IDs, no-goal permission escalation, deterministic tie-breaking |
| Lifecycle scenarios | Fake monotonic clock, transport replies, replication order, 44.999/45/late-result boundaries, duplicate replies, early read timeout, stop/profile switch/unload/rejoin |
| Cross-feature scenarios | Banking/property reserve, gear/native-equip exclusion, station/combat/training recovery, goal overlap, heist priority, Market research versus combat fairness |
| Persistence | Corrupt/truncated files, unsupported schemas, unavailable writes, interrupted staged write, two-account separation, username change, active versus selected profiles |
| Ember adapter | False-value restore, setter refusal, delayed startup callbacks, silent hydration, large catalog filtering, destroy/recreate, hidden window, display failure |
| Build/static | Deterministic modular release/manifest, dependency provenance, strict type/static checks where supported, every module and optional fallback Luau compile/parse including function/local/register limits, source mapping, no old runtime import |
| Module delivery | One commit across every fetch, partial/missing/corrupt downloads, syntax/export failure, bounded retries, cycles/duplicate IDs, verified complete cache only, initialize once, no sends before complete startup or during update |
| Actual UI | Ember rendering in Roblox with all gameplay dispatch disabled; size/scroll/search/groups/theme/keybinds and every page checked |
| Feature live check | Current native build, exact version/account, narrowly scoped authorization, naturally eligible action, before/after proof, recorded rejection/uncertainty and recovery |

Engine fault cases must demonstrate: no new send after stop; no success for missing proof; exactly one unconfirmed outcome at 45 seconds; bounded retry and research; no gate release by an old callback; unaffected routines continuing after a scoped failure. Run long fake-clock scenarios with bounded histories/caches and at least a 60-minute observed UI/read-only session before final cutover. Time alone is not acceptance: journals must show health, bounded storage, cleanup, and no duplicate senders.

A feature is **implemented** when new code and tests exist, **offline verified** when its checks actually pass, and **live verified** only for the specific observed current contract/scenario. A request being sent or accepted is not a completed gameplay result. Keep these labels visible in release notes.

Full replacement acceptance:

- Every parity and setting-disposition row is resolved; no unexplained missing function.
- All pages have reviewed actual Ember behavior and useful waiting/error states.
- No feature sends outside broker/policy/preflight, and no old runtime code is used.
- Scheduler/lifecycle/recovery invariants pass the failure scenarios above.
- Old files/account data remain recoverable; fallback never runs alongside the new hub.
- Each supported game action has a current evidence entry. Features without sufficient evidence are visibly unavailable and prevent claiming complete functional parity until resolved.
- Published evidence states what was tested offline, rendered live, and confirmed as a game outcome.

## Future improvements after parity

Prioritize measured improvements: event/deadline-aware planning from verified timers; better target-cache freshness and research fairness; state-backed spend/earnings attribution; a bounded dependency route for contract/trophy blockers; durable Territory intent; reachable whole-loadout optimization with proven ordering; and an optional dedicated Progression controller if still wanted. None may bypass permissions or act on a theoretical optimum as if it were an executable transaction.

Do not add a generic plugin ecosystem, arbitrary user scripting, a remote update service, global optimization claims, speculative trades/sieges, premium purchases, or a second scheduling engine. Extend the feature registry and adapters when a concrete supported use case exists.

## Design self-review

- Fresh source, separate distribution, and no old production imports satisfy the recode requirement.
- UI grouping is confirmed by the user; detailed palette/layout and behavior differences remain proposed.
- Current source is distinguished from historical Progression and outdated documentation.
- One local gate, 45-second uncertainty release, and possible lingering remote execution are described consistently.
- Source freshness and inaccessible current Ember bytes are explicit evidence gaps, assigned to the first milestone.
- The roadmap covers every parity area without claiming untested scripts exist.
- This document makes no new gameplay authorization and no claim of guaranteed server reliability.
