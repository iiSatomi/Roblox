# Idle Mafia Ember recode — delivery roadmap

Date: 2026-10-20. Status: start authorized; updated-place audit and first local UI/state prototype completed. Actual Ember/gameplay implementation remains pending.

**Goal:** Replace the current hub with freshly written, maintainable Luau and an Ember interface while preserving the complete reviewed feature set and its protections.

**Architecture:** Focused domain modules produce decisions from validated state. A single broker/supervisor owns requests, uncertainty, recovery and lifecycle. Ember renders application state and submits local commands.

**Technology:** Luau, reviewed/pinned Ember, GitHub-hosted modules with a short commit-pinned loader, native source-backed adapters, fake-clock/transport scenario tests, and actual Roblox UI checks. A generated single-file fallback is optional.

**Updated evidence:** [Place audit](place-audit-2026-10-20.md), [source fingerprints/anchors](native-evidence-2026-10-20.json), [simpler UI](ui-simplification.md), [local prototype plan](ui-prototype-plan.md).

**Primary references:** [Design](design.md), [parity register](parity.md), `docs/Ember-UI-Reference.md`, `skills/idle-mafia-hub/SKILL.md`, newest `docs/AGENT_HANDOFF.md` sections.

This is the full-project sequencing and acceptance plan requested by the user. It is intentionally not executable implementation code. After design approval, write a detailed implementation plan for each bounded milestone, including exact typed interfaces and focused test commands, before its scripts. Do not scaffold the whole tree or dispatch agents just because a future milestone can be divided.

## Global constraints

- New source lives in `idle-mafia-ember/`; legacy source/bundles remain unchanged until deliberate cutover.
- Primary distribution is a short loader plus separate modules hosted on GitHub at one reviewed commit. Do not fetch individual modules from a moving branch, embed credentials, or upload unrelated workspace/account/game-extraction data.
- Fresh implementation: no copy/paste, production imports or wrappers around old modules. Use old source/tests only to extract requirements and known failure scenarios.
- Simplified UI design and a local interactive preview precede an inert actual Ember rendering check and gameplay scripts. Preserve capabilities, not all 231 tuning options.
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
- [x] User authorized starting and requested source-based updates, local UI testing and substantially simpler menus/logic with the same functions.
- [x] Inventory all 231 Core.defaults keys and 52 literal control IDs with proposed dispositions.
- [ ] Finish dynamic-control, special permission, profile-field and transaction binding maps against the simpler schema.
- [x] Extract updated user-supplied place as inert data: native 0.26.487.1, 260 script-source records, 40/48 old selected sources changed, 42 checked anchors and 852 unique city districts. Runtime response shapes remain unverified.
- [ ] Fetch/review/fingerprint the actual Ember source and dependency terms; test whether the known October 12 discrepancies still apply.
- [x] Select the existing public `iiSatomi/Roblox` repository and dedicated `idle-mafia-ember/` recode root.
- [ ] Establish supported HTTP/compilation/hash/cache primitives and a release destination before publishing executable modules; no embedded credentials.

Acceptance: agreed layout/behavior scope; complete setting dispositions; evidence gaps named per feature. If fresh game evidence is unavailable, M1 and fake-engine work can proceed using clearly labeled fixtures; gameplay adapters remain blocked on their own missing evidence.

Artifacts: updated design/parity, new versioned native-contract register and sanitized fixture provenance. Never store private tokens/account config values in docs.

## M1 — local simplified UI, then actual Ember prototype

Proposed source: `ui/EmberAdapter.luau`, `ui/Bindings.luau`, page/panel modules, `storage/Settings.luau`, `storage/Profiles.luau`, `App.luau` in prototype-only composition.

Slices:

- [x] Author local interactive 13-page design preview with 55 activity/permission controls including every legacy ID, four Combat Custom overrides and three Property overrides. No game bridge, account files or gameplay transport.
- [x] Run nine local model/schema tests and JS syntax checks.
- [ ] Verify actual browser layout, navigation/search, disclosure controls and narrow/wide states. Automated local URL/file navigation is blocked by browser security policy; visual checks remain open. Standalone HTML is available.
- [ ] Prototype the loader with inert modules: one commit/manifest, initialize-once exports, verified complete prefetch/cache, and no partial application startup on failed downloads or compilation.
- [ ] Resolve actual sidebar scrolling, group density, control search, long catalogs and status visibility at target/minimum viewport sizes.
- [ ] Implement the simplified feature pattern in actual Ember across 13 proposed sections after the local design review, with sample data clearly labeled.
- [ ] Implement the settings model and inert profile preview with typed false/enum/color/multi-selection handling; no run-on-hydration behavior.
- [ ] Check delayed callbacks, `Set` rejection, theme subscriptions, destroy/recreate, F8 visibility, appearance save failures and reduced motion.
- [ ] Inspect actual Roblox Ember rendering with gameplay dispatch disabled and record screenshots/observations where available.

Acceptance: all current functions have a clear destination; most features expose 2–4 primary controls and Custom has at most six useful overrides; no mirrored settings or giant Advanced dump. Local browser checks and actual Ember rendering are distinct gates. Keep both visual gates open until observed; offline state tests do not establish rendering.

Checkpoint: review the real UI and revise navigation now. Do not spend gameplay effort around an unreviewed layout.

## M2 — reliability engine with no game mutations

Proposed source: session/capabilities, shared contracts, broker/lifecycle/scheduler/policy/resource ledger/recovery, Files, Journal/Health/Export; fake adapters and state fixtures.

Slices:

- [ ] Lock a small typed policy/settings model, shared snapshot/decision/proposal/record contracts and migration semantics.
- [ ] Establish native server-time, economic/decree/exemption, effective buff and native-automation ownership contexts from the updated source before gameplay. Use the supported native dispatch seam; never hardcode private handshake values.
- [ ] Prove city/district identity and source-schema compatibility boundaries. Establish explicit module/dependency/checksum manifest, deterministic modular release and source mapping.
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
- [ ] Implement one readable Job decision pipeline with a compact goal/policy and useful selected/city/mastery overrides; native costs, unlocks and buffs are automatic. Yield native Auto Jobs and preserve shared reserves without exposing every old bound.
- [ ] Connect settings → planner → broker → confirmation → status/journal, with all other game mutations unavailable.
- [ ] Prove rejection, delayed replication, level-up/catalog change, disable/stop, and missing-field behavior offline.
- [ ] When an authorized current session is available, render and observe a narrowly scoped naturally eligible Job through exact before/after evidence.

Acceptance: one complete feature works without a special-case bypass, direct UI remote, global shared-local runtime or legacy imports. Refine the shared pattern here before multiplying features.

## M4 — ordinary claims, Operations and skill allocation

Slices, each with its own panel/settings/adapter/proof/tests:

- [ ] Earned level/weekday/weekend playtime rewards and existing-member group claims; 90-minute XP versus weekend Gold, 120-minute Mystery and 180-minute bound crate resolve from native state.
- [ ] Separately enabled monthly earned claim, UTC/month boundaries and exact ClaimMonthly proof.
- [ ] Daily/weekly contract entries and separately enabled completion bonuses.
- [ ] Earned trophy/cosmetic claims excluding item-consuming routes; read-only trophy progress.
- [ ] Native skill batch allocation and caps.
- [ ] Operation collection, then separate Operation starting with current slots/cost, derived operation rate and catalog reward probabilities; estimated time is not replicated readiness.
- [ ] Free Briefcase picks, then separately permissioned owned-key use and caps.

Acceptance: every claim has an exact identity and cannot repeat from stale readiness; Operations retain future scheduler priority; crate awards do not enable crate opening; key use is distinct from free picks.

## M5 — money, property and personal progression

Slices:

- [ ] Deposit/exact-shortfall funding and purpose-specific bank permissions, fees and cash-to-keep/reservations.
- [ ] One simple property goal pipeline, meaningful Custom spending/selection limits and accumulating cash without deposit starvation; no configurable native cost-growth/tax internals.
- [ ] Native-catalog Safehouse tiers including levels 200/215, then separately enabled prestige with current requirements/send caps; distinguish current and highest-ever level.
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
- [ ] Catalog-driven Global Boss state watcher and separate live attack/settled claim: scheduled starts, public/access checks, time-decay HP versus player damage, changing medal rules and already-auto-settled rewards.
- [ ] Family Takedown reads and exact reward claims, then separately enabled free attacks with current HP-scaled hit-back, Ticket protection and rank strategy.

Acceptance: no city/player/global/Family identity mixing; stale event/run cannot act or claim; no intended Ticket spending; Combat mirror updates the same Takedown setting without recursive callbacks.

## M8 — player Combat and persistent history

Slices:

- [ ] Read-only mug/scout/evidence import and native outgoing-attack observer with deduplication and account separation.
- [ ] Hit-list/saved-user lookup/scout/profile discovery with exact IDs, freshness, fair turns, bounded native refresh and persisted evidence.
- [ ] One eligibility → evidence → rank pipeline using a simple target policy, explicit player permission, useful payout/health/reserve/source overrides, native eligibility and preserved history. Goals reuse it; no confidence-weight tuning surface or duplicated lanes.
- [ ] Native war identity/targets and separate war policy; shield/hospitalization/temporary rejection cooldowns and fallback behavior.
- [ ] Exact Scout/Attack confirmation policies, late logs, activity/earnings evidence and clear heuristic labels.

Acceptance: no attack from importing/selecting a profile, inspecting a target or enabling a goal alone; no invented hidden cash or guaranteed win probability; a bad target cannot starve others. Live PvP needs explicit authorization beyond this planning request.

## M9 — Crew, loadouts and inventory

Execute as separate domain slices:

- [ ] Crew sorting, exact stable-member stamina healing and read-only rarity/base-quality/reporting.
- [ ] Separately enabled owned health-item healing, recall-versus-injury checks, bound-first/optional tradable stacks and its own three-second sequence/cooldown.
- [ ] Training, contract empty-slot hire and reservations of available home Crew.
- [ ] Current normal dismiss/hire reroll rules, rarity/quality/worst-first/luck controls and durable funded continuation.
- [ ] Native auto-equip with no-op suppression; read-only joint player/Crew/Collection/set outlook.
- [ ] Safe one-step gear and cosmetic transactions, then separately enabled complete-set multi-step plans.
- [ ] Safe surplus Collection deposit with all seven native thresholds, variant/base-ID/bound custody, worn-cosmetic display/ownership separation and detailed unsupported-item reasons.
- [ ] Unbound chest opening with current native luck, batch/selection/cap and separate luck-only condition.
- [ ] All nine player restoratives, compact recovery policy/useful thresholds, independent three-second player clock, exact stack/sequence proof and separately enabled tradable use.

Acceptance: shared ownership/item reservations prevent competing gear/donation/equip operations; bound/equipped/training/stationed/recovering state stays protected; reroll never dismisses before durable funding/intent checks; the theoretical report never becomes automatic permission to execute a multi-swap plan.

## M10 — Shop, Market, Family and Territory

This milestone is a container for independent feature slices, not one giant change:

- [ ] Simplified cash Shop policy with current decree/discount/exemption quotes, optional cosmetics/crates and purpose-specific bank funding; yield native Auto Buy. Gold client arguments are now observed, but exact runtime outcome and separate permission remain gates.
- [ ] Read-only Market research with pagination/shape/cache/fairness tests and native decree-aware permille/minimum-fee calculations.
- [ ] Sold-earnings collection and durable confirmed ledger.
- [ ] Separate rental with native quote/reserve/attempt cap.
- [ ] Owned-item sale with exclusions, Collection checkpoint preservation, optional withdrawal, pricing/demand and exact listing proof.
- [ ] Separate flip buy → relist with durable identity/limits and manual review on uncertain steps.
- [ ] Separate cash/stamina/Gold Family contributions, native perk rotation and condition/cap semantics.
- [ ] City-scoped Territory adapter/selection across 852 catalog districts, native successors/duty/residency migration, top-two bonus effects and lock/capacity/shield context; then own-residency move.
- [ ] Read-only season/decree/fortification views; Season 1 configured 14 days despite notes saying four weeks. Shared Gold construction/sabotage/leadership changes remain deferred.
- [ ] Event Shop preview and separate OFF-default selected-item medal buyer; native free/paid-origin and account restrictions, current prices/window, reserve/attempt cap and item/medal outcome proof.
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
- [ ] Test local UI navigation, compact controls, Custom field budget, search/filter and sample blockers at narrow/large sizes; separately inspect actual Ember scaling, focus/pointer/F8/respawn and unload/reload cleanup.
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

Review the simplified local preview and finish its blocked visual checks, retrieve reviewed Ember bytes, then implement the inert actual Ember view against the compact policy schema. Continue M2 context/broker work with fake transport; gameplay starts only after those gates. Keep the updated-place audit and simplification design authoritative.
