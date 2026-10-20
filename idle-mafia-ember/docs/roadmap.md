# Idle Mafia Ember recode — delivery roadmap

Date: 2026-10-20. Status: proposed roadmap, no implementation started.

**Goal:** Replace the current hub with freshly written, maintainable Luau and an Ember interface while preserving the complete reviewed feature set and its protections.

**Architecture:** Focused domain modules produce decisions from validated state. A single broker/supervisor owns requests, uncertainty, recovery and lifecycle. Ember renders application state and submits local commands.

**Technology:** Luau, reviewed/pinned Ember, GitHub-hosted modules with a short commit-pinned loader, native source-backed adapters, fake-clock/transport scenario tests, and actual Roblox UI checks. A generated single-file fallback is optional.

**Primary references:** [Design](design.md), [parity register](parity.md), `docs/Ember-UI-Reference.md`, `skills/idle-mafia-hub/SKILL.md`, newest `docs/AGENT_HANDOFF.md` sections.

This is the full-project sequencing and acceptance plan requested by the user. It is intentionally not executable implementation code. After design approval, write a detailed implementation plan for each bounded milestone, including exact typed interfaces and focused test commands, before its scripts. Do not scaffold the whole tree or dispatch agents just because a future milestone can be divided.

## Global constraints

- New source lives in `idle-mafia-ember/`; legacy source/bundles remain unchanged until deliberate cutover.
- Primary distribution is a short loader plus separate modules hosted on GitHub at one reviewed commit. Do not fetch individual modules from a moving branch, embed credentials, or upload unrelated workspace/account/game-extraction data.
- Fresh implementation: no copy/paste, production imports or wrappers around old modules. Use old source/tests only to extract requirements and known failure scenarios.
- UI design and an inert Ember prototype precede gameplay scripts.
- Preserve all 50 feature registry IDs and the supporting/controller areas in the parity register, or record an explicit reviewed disposition for unavailable/unsafe behavior.
- Separate feature switches, sensitive permissions, currencies, confirmed outcomes and unconfirmed attempts.
- One locally admitted outbound request; one-second default/minimum send spacing; 0.25-second planner checks; 45-second first-send uncertainty deadline; 45–300-second affected-feature cooldown after unconfirmed skip.
- Preserve Heists → Favors → Operations → other eligible work. Do not claim a one-second maximum or server cancellation.
- No new game calls without current contract evidence; no automatic bot-check answers, production confirmation bypass, real-money purchases, or anti-cheat evasion.
- Implementation, offline checks, actual Ember rendering and live action outcomes have separate evidence labels.
- Preserve unrelated staged/untracked workspace work. New docs use dated paths rather than replacing historical `tasks/plan.md`.

## Dependency order

```text
M0 evidence + parity + approved design
  -> M1 inert Ember prototype + reviewed layout
  -> M2 engine/lifecycle with fake transport
  -> M3 first real vertical slice: Jobs
  -> M4 claims + Operations + skills
  -> M5 money + properties + prestige
  -> M6 Heists + Favors + sabotage
  -> M7 city/global Bosses + Takedown
  -> M8 player Combat + history
  -> M9 Crew + gear + inventory
  -> M10 Market + Territory
  -> M11 goal controllers + event preference
  -> M12 parity closure + import + endurance + cutover
```

This is implementation order, not scheduler priority. High-risk broker/uncertainty feasibility is proved in M2 before feature breadth. Profiles/storage foundations start in M1/M2, not as an end-of-project patch. Each broad milestone below must be executed as the listed separately verified slices.

## M0 — evidence baseline and design acceptance

Scope: documentation/evidence only.

- [x] Read current project workflow/handoff, inspect current feature/control registry and source structure.
- [x] Read the durable Ember reference; check accessible official docs and record inability to retrieve current source bytes.
- [x] Confirm grouped pages, focused summaries and collapsed advanced settings with the user.
- [x] Incorporate the user's GitHub/separate-module preference into the delivery architecture.
- [x] Write architecture/UI proposal, 50-ID parity inventory and this delivery roadmap.
- [ ] Review the concrete design and proposed intentional differences with the user.
- [ ] Expand the parity inventory to every current control/settings key/default and transaction; distinguish dormant historical settings.
- [ ] Obtain current game source/read-only evidence when available; compare native build, catalogs, remotes and shapes against October 11.
- [ ] Fetch/review/fingerprint the actual Ember source and dependency terms; test whether the known October 12 discrepancies still apply.
- [x] Select the existing public `iiSatomi/Roblox` repository and dedicated `idle-mafia-ember/` recode root.
- [ ] Establish supported HTTP/compilation/hash/cache primitives and a release destination before publishing executable modules; no embedded credentials.

Acceptance: agreed layout/behavior scope; complete setting dispositions; evidence gaps named per feature. If fresh game evidence is unavailable, M1 and fake-engine work can proceed using clearly labeled fixtures; gameplay adapters remain blocked on their own missing evidence.

Artifacts: updated design/parity, new versioned native-contract register and sanitized fixture provenance. Never store private tokens/account config values in docs.

## M1 — UI prototype, before gameplay

Proposed source: `ui/EmberAdapter.luau`, `ui/Bindings.luau`, page/panel modules, `storage/Settings.luau`, `storage/Profiles.luau`, `App.luau` in prototype-only composition.

Slices:

- [ ] Build one representative Overview and Heist group with mock state. Keep the transport absent and buttons incapable of sending gameplay requests.
- [ ] Prototype the loader with inert modules: one commit/manifest, initialize-once exports, verified complete prefetch/cache, and no partial application startup on failed downloads or compilation.
- [ ] Resolve actual sidebar scrolling, group density, control search, long catalogs and status visibility at target/minimum viewport sizes.
- [ ] Apply the approved feature pattern to all 14 proposed sections, with catalog-based placeholder data clearly labeled as sample data.
- [ ] Implement the settings model and inert profile preview with typed false/enum/color/multi-selection handling; no run-on-hydration behavior.
- [ ] Check delayed callbacks, `Set` rejection, theme subscriptions, destroy/recreate, F8 visibility, appearance save failures and reduced motion.
- [ ] Inspect actual Roblox Ember rendering with gameplay dispatch disabled and record screenshots/observations where available.

Acceptance: all current functions have a clear destination; common tasks do not require reading long diagnostic paragraphs; UI state cannot send game actions; actual layout is reviewable before adapters are added. If an actual renderer is unavailable, label the prototype unverified and keep this rendering gate open.

Checkpoint: review the real UI and revise navigation now. Do not spend gameplay effort around an unreviewed layout.

## M2 — reliability engine with no game mutations

Proposed source: session/capabilities, shared contracts, broker/lifecycle/scheduler/policy/resource ledger/recovery, Files, Journal/Health/Export; fake adapters and state fixtures.

Slices:

- [ ] Lock exact typed contracts for snapshots, decisions, proposals, records, confirmation, intent and view state. Establish explicit module/dependency/checksum manifest, deterministic modular release and source mapping.
- [ ] Implement a single fake-transport broker, send-time pacing, preflight, early read timeout, state/reply evidence policy and deduplication.
- [ ] Implement the exact 45-second skip/cooldown, immutable first-send time, bounded late-result records and callback/session fencing.
- [ ] Implement priority/fairness and empty/waiting/stale-state behavior; demonstrate background read budgets and shared dependency cooldowns.
- [ ] Implement separate desired/effective state, session pause/stop, durable uncertainty and resource exposure; settings/profile hydration stays local-only.
- [ ] Exercise duplicate load, concurrent legacy-hub detection, failed writes, corrupt schemas, account switch, teleport and unload without clearing uncertain ownership.

Required scenario examples: no second admitted call while one is owned; no skip at 44.999 seconds; exactly one skip at 45 seconds; no same-feature immediate retry; other eligible work resumes; a response at 46 seconds cannot release a newer action or double-count; stop prevents all new sends; no stale proposal after setting changes; no renderer exception kills the heartbeat.

Acceptance: all invariants pass with deterministic fake time and inspectable journals. All release modules and any optional fallback bundle compile/parse. Partial downloads, wrong hashes, module cycles, compilation failure and duplicate module resolution cannot start or duplicate a sender. No live mutation is needed to prove engine feasibility.

## M3 — first vertical gameplay slice: Jobs

Proposed source: current-game State/Catalog readers and compatibility, Jobs adapter/planner/confirmer, Jobs panel, focused fixtures/scenarios.

- [ ] Establish fresh native-state freshness/account/build guards and current Job request/outcome contract.
- [ ] Implement the full Job rule surface: choices/city/mastery/modes, bounds, energy reserve, current discounts/events and clear no-work reasons.
- [ ] Connect settings → planner → broker → confirmation → status/journal, with all other game mutations unavailable.
- [ ] Prove rejection, delayed replication, level-up/catalog change, disable/stop, and missing-field behavior offline.
- [ ] When an authorized current session is available, render and observe a narrowly scoped naturally eligible Job through exact before/after evidence.

Acceptance: one complete feature works without a special-case bypass, direct UI remote, global shared-local runtime or legacy imports. Refine the shared pattern here before multiplying features.

## M4 — ordinary claims, Operations and skill allocation

Slices, each with its own panel/settings/adapter/proof/tests:

- [ ] Earned playtime and existing-member group claims.
- [ ] Daily/weekly contract entries and separately enabled completion bonuses.
- [ ] Earned trophy/cosmetic claims excluding item-consuming routes; read-only trophy progress.
- [ ] Native skill batch allocation and caps.
- [ ] Operation collection, then separate Operation starting with catalog/slot/cost/timer filters.
- [ ] Free Briefcase picks, then separately permissioned owned-key use and caps.

Acceptance: every claim has an exact identity and cannot repeat from stale readiness; Operations retain future scheduler priority; crate awards do not enable crate opening; key use is distinct from free picks.

## M5 — money, property and personal progression

Slices:

- [ ] Deposit/exact-shortfall funding and purpose-specific bank permissions, fees and cash-to-keep/reservations.
- [ ] Cash property purchases, selection/modes/limits and accumulating cash without deposit starvation.
- [ ] Safehouse upgrades, then separately enabled prestige with current requirements/send caps.
- [ ] Separately protected property replacement with a durable exact delete → buy state machine, restart proof and honest no-rollback behavior.

Acceptance: budget and uncertain exposure cannot be spent twice; external spending invalidates a quote; a property transaction cannot resume at a guessed stage; missing recovery storage blocks risky replacement. Destructive live checks require explicit scope and are not implied by planning.

## M6 — Heists, Favors and sabotage

Slices:

- [ ] Read-only fresh board adapter and sequence/session ownership validation.
- [ ] Personal result collection, then separate personal start.
- [ ] Favor helper selection/relationships/rewards, resources and persistent native-day cap.
- [ ] Separate sabotage opt-in and board-confirmed limits, only after its current contract is established.
- [ ] Shared board-read cooldown, uncertainty recovery, late evidence and startup reconciliation.

Acceptance: Heists → Favors → Operations precedence passes scenario tests; waiting boards yield appropriately; no borrowed sequence guessing, immediate replay, or success for missing result; a board-family failure leaves unrelated domains usable.

## M7 — Bosses and shared Takedown

Slices:

- [ ] Native city Boss stages, daily state and health/hit-back/encounter protections.
- [ ] Separate Boss Token Shop choice, reserve, purchase proof and send cap.
- [ ] Global Boss state watcher, separate live attack and settled claim, event/run identity, resource proof and attempted caps.
- [ ] Family Takedown reads and exact reward claims, then separately enabled free attacks with Ticket protection and rank strategy.

Acceptance: no city/player/global/Family identity mixing; stale event/run cannot act or claim; no intended Ticket spending; Combat mirror updates the same Takedown setting without recursive callbacks.

## M8 — player Combat and persistent history

Slices:

- [ ] Read-only mug/scout/evidence import and native outgoing-attack observer with deduplication and account separation.
- [ ] Hit-list/saved-user lookup/scout/profile discovery with exact IDs, freshness, fair turns, bounded native refresh and persisted evidence.
- [ ] Ordinary target selection, explicit player permission, payout/risk/win/health/stamina/cost/level/daily checks and high-value memory.
- [ ] Native war identity/targets and separate war policy; shield/hospitalization/temporary rejection cooldowns and fallback behavior.
- [ ] Exact Scout/Attack confirmation policies, late logs, activity/earnings evidence and clear heuristic labels.

Acceptance: no attack from importing/selecting a profile, inspecting a target or enabling a goal alone; no invented hidden cash or guaranteed win probability; a bad target cannot starve others. Live PvP needs explicit authorization beyond this planning request.

## M9 — Crew, loadouts and inventory

Execute as separate domain slices:

- [ ] Crew sorting, healing and read-only rarity/base-quality/reporting.
- [ ] Training, contract empty-slot hire and reservations of available home Crew.
- [ ] Current normal dismiss/hire reroll rules, rarity/quality/worst-first/luck controls and durable funded continuation.
- [ ] Native auto-equip with no-op suppression; read-only joint player/Crew/Collection/set outlook.
- [ ] Safe one-step gear and cosmetic transactions, then separately enabled complete-set multi-step plans.
- [ ] Safe surplus Collection deposit and detailed protected/unsupported-item reasons.
- [ ] Unbound chest opening with current native luck, batch/selection/cap and separate luck-only condition.
- [ ] All nine restoratives, per-resource thresholds/modes, native stack/cooldown/sequence proof, separately enabled tradable use.

Acceptance: shared ownership/item reservations prevent competing gear/donation/equip operations; bound/equipped/training/stationed/recovering state stays protected; reroll never dismisses before durable funding/intent checks; the theoretical report never becomes automatic permission to execute a multi-swap plan.

## M10 — Shop, Market, Family and Territory

This milestone is a container for independent feature slices, not one giant change:

- [ ] Cash Shop selection/current quotes/rarity override, optional cosmetics/crates and purpose-specific bank funding. Preserve Gold Shop as unavailable until its exact request is established.
- [ ] Read-only Market research with pagination/shape/cache/fairness tests.
- [ ] Sold-earnings collection and durable confirmed ledger.
- [ ] Separate rental with native quote/reserve/attempt cap.
- [ ] Owned-item sale with exclusions, Collection checkpoint preservation, optional withdrawal, pricing/demand and exact listing proof.
- [ ] Separate flip buy → relist with durable identity/limits and manual review on uncertain steps.
- [ ] Separate cash/stamina/Gold Family contributions, native perk rotation and condition/cap semantics.
- [ ] Read-only Territory map/station advice; then own-residency planning/move.
- [ ] Separately enabled station, exact own recall/status/recovery, quiet transfer/training rotation and health recovery coordination.

Acceptance: manual bot-check pause cannot be bypassed; closed shop blocks sale research when appropriate; uncertain sale/rent/flip does not become repeated spend; Family/territory permission cannot be borrowed; combat/training/station routines agree on member availability and quiet-defense requirements.

## M11 — goals and strategy without competing controllers

- [ ] Contract-priority preference for effective routines, including combined Job-count/energy and Operation duration cases.
- [ ] Auto Contracts with supported objective coverage, explicit ordinary-activity borrowing policy and precise unsupported blockers.
- [ ] Trophy Focus through the same intents/policy/broker, with owned/ready/blocked goal states and exact selected route.
- [ ] Optional native event ordering and per-feature luck conditions; no hidden enabling or priority violation.
- [ ] Exercise simultaneous manual work, contract goal, trophy goal and event preference; display one effective origin/reason and avoid duplicate proposals.

Acceptance: all goals use existing feature execution paths and limits; no second planner dispatch loop; unsupported objectives never advertise completed automation. Historical broad Auto Progression remains a separately reviewed future decision.

## M12 — parity closure, imports, endurance and cutover

- [ ] Resolve every feature/control/setting disposition against the original inventory. Check all page locations and default/permission semantics.
- [ ] Complete legacy profile/data import preview, new stable-ID account storage, active/selected/autoload behavior, saving/error states and unresolved legacy-work blockers.
- [ ] Verify modular release determinism, dependency hash/provenance, Luau compile/type checks, source maps and absence of old production imports; test release-pinned loading, network failure, complete cache recovery and update/rollback isolation.
- [ ] Run all new feature/scenario/UI checks; run the old suite only if legacy code changed, and report it separately.
- [ ] Inspect all actual Ember pages, narrow/large viewports, search/filter behavior, reduced motion, keybinds and unload/reload cleanup.
- [ ] Run long fake-clock failure/endurance scenarios, then at least 60 minutes of actual UI/read-only observation with bounded resources and healthy heartbeats.
- [ ] Record current-scenario live action evidence where authorized; leave unavailable evidence gaps explicit. Do not manufacture full parity from local tests alone.
- [ ] Publish the reviewed modular source, commit-pinned entry loader/manifest, developer guide, settings map, feature evidence matrix, recovery guide and known limits to the chosen GitHub destination. Publish an optional same-source fallback bundle if useful.
- [ ] Perform deliberate fallback/cutover rehearsal with one sender and intact backups; keep legacy runnable until acceptance.

Acceptance: the design's definition of done is met; no unexplained missing functions or controls; no unsupported feature presented as operational; no live success claim without observed proof. Features awaiting game evidence block a claim of complete functional replacement, even if the rest is usable.

## How each implementation slice is handled

1. Update the exact feature contract and settings mapping from current evidence.
2. Write a bounded implementation plan with exact files/interfaces and acceptance cases.
3. Author meaningful failing pure/scenario checks for the new behavior.
4. Write fresh production code, connect its existing UI panel, and run focused checks.
5. Check the complete new engine/feature suite when shared behavior changes; compile every release module and any optional fallback bundle, then validate the release manifest and loader.
6. Inspect actual UI behavior and record separate live-action evidence only within authorized scope.
7. Review the change, update parity/evidence/handoff, and mark only proven outcomes complete.

Do not force a test for decorative copy/spacing or rerun unrelated suites to inflate evidence. Use tests for permissions, request state, resource/item decisions, persistence, and failure recovery.

## Main risks and decisions

| Risk | Response / acceptance evidence |
| --- | --- |
| Game changed after October 11 | New native source/shape checks per feature; no guessing arguments or formulas. |
| Ember source changed or cannot be retrieved | Prototype only after reviewed bytes are obtained; retain the October 12 caveats as unverified until rechecked. |
| Another large runtime grows | Focused domain files, typed inputs/results, no UI effects in planners, review oversized modules. |
| 45-second release leaves old server work uncertain | Exact unconfirmed record, duplicate-risk log, bounded cooldown, exposure accounting and late-result fencing; no cancellation claim. |
| Feature preservation misses hidden settings | Per-control/default inventory, not just top-level toggles; parity closure required before replacing legacy. |
| Broad rewrite stays half-finished | Complete vertical slices with a working modular release and explicit feature availability at each checkpoint. |
| GitHub download/update mixes incompatible modules | One commit-pinned manifest, verified complete prefetch/cache, no network module fetches during gameplay, no live hot swapping. |
| Config import restarts dangerous work | Read-only import preview, inactive imported profile, explicit new-hub activation and unresolved-work reconciliation. |
| UI looks alive while engine is stalled | Independent render/state/scheduler/broker health; visible wait reasons and fault scenarios. |
| Live mutations used casually as tests | Prove engine/policy offline; actual gameplay checks require appropriate current authorization and exact outcome evidence. |

## Next bounded task

Review this design and its intentional differences. Then complete M0's per-setting/native-contract audit and obtain reviewed Ember bytes, followed by M1's inert UI prototype. No gameplay recode is started by this planning milestone.
