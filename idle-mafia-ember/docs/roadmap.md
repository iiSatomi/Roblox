# Idle Mafia Ember recode — delivery roadmap

Date: 2026-10-20. Status: evidence audit, inert Ember UI 0.1.1 and offline Jobs request/lifecycle integration are implemented. The user ran 0.1.1 without console errors or executor Problems. Detailed layout/interaction checks, native runtime adapters, production release and all live gameplay functions remain open.

The chosen direction is ordinary native action automation for Jobs, Bosses and
the other reviewed domains. Paid-controller unlocking is outside this recode.
The [Ember UI prototype](ember-ui-prototype.md) has 26 offline
Python/Lupa/Luau-analysis checks, 12 Node checks and Luau compilation. Clean
startup is user-confirmed; detailed rendering and gameplay are unverified.

**Goal:** Replace the current hub with freshly written, maintainable Luau and an Ember interface while preserving the complete reviewed feature set and its protections.

**Architecture:** Focused domain modules produce decisions from validated state. A single broker/supervisor owns requests, uncertainty, recovery and lifecycle. Ember renders application state and submits local commands.

**Technology:** Luau, reviewed/pinned Ember, GitHub-hosted modules with a short commit-pinned loader, native source-backed adapters, fake-clock/transport scenario tests, and actual Roblox UI checks. A generated single-file fallback is optional.

**Updated evidence:** [Place audit](place-audit-2026-10-20.md), [source fingerprints/anchors](native-evidence-2026-10-20.json), [simpler UI](ui-simplification.md), [local prototype plan](ui-prototype-plan.md).

**Primary references:** [Design](design.md), [parity register](parity.md), `docs/Ember-UI-Reference.md`, `skills/idle-mafia-hub/SKILL.md`, newest `docs/AGENT_HANDOFF.md` sections.

This is the full-project sequence and acceptance plan. The [next implementation
plan](plans/2026-10-20-engine-jobs.md) breaks M2 and M3 into reviewable tasks
with exact files and verification. Later broad milestones need equally bounded
plans before implementation.

## Progress as of October 20

| Area | Current evidence | Remaining outcome |
| --- | --- | --- |
| M0 evidence and design | Updated place audit, 50-ID parity inventory, 55-control native-use audit, 231-key settings inventory, reviewed Ember 3.0.0 bytes. | Finish dynamic control/profile/transaction binding map and runtime contracts as the affected features are built; resolve Ember distribution before a public runnable release. |
| M1 UI | Local preview and actual Ember UI 0.1.1 with 25 tabs/55 controls, in-memory settings, pause/stop/profile validation. An opt-in profile store and Save/Preview/paused Apply path now pass fake-storage/UI checks; the distributed 0.1.1 remains memory-only. User reports clean startup. | Check actual layout, interaction, F8, focus, scaling, sidebar scrolling, theme and unload/reload; provide production executor profile storage and verify it live. |
| M2 engine and release foundation | Offline Tasks 1–4 provide a source-labelled Jobs contract, copied request headers, monotonic fake clock, one-owner broker, one-second spacing, exact 45-second skip/cooldown and bounded journal. Task 5 partially adds fresh context, separate native ownership/activity for Jobs, Shop, Crew Roll and city Bosses, resource/priority arbitration, read-only decree/Family economic and effective buff views, and a bounded background-read gate. Task 6 adds fake-storage-tested lifecycle and write-ahead uncertainty ledger plus a two-slot crash-recovery core over injected file/JSON/SHA primitives; checkpoint use now requires strict recovery to prevent rollback of sent attempts. Task 7 has a fake-adapter-tested manifest validator and loader. A checked registry composes 25 offline feature descriptors; a fake-adapter coordinator derives exact Operation/Safehouse funding needs. A read-only snapshot staging module now distinguishes observed Syncs from tick changes, and saved native call descriptions cover most non-sequenced actions. | Connect a current-client Sync source, individual native readers, actual executor storage primitives and cross-process ownership, production release manifest and verified hash/fetch/cache/compile adapters, plus live transport contract. The release still has no game calls. |
| M3 Jobs | Native client source identifies an ordinary Job UI action. Pure state/planner, selected-Job evidence and opt-in App → shared broker → UI status integration pass synthetic fake-adapter tests. Preflight rechecks the selected quote, unlock, energy, proposal exposure and native controller state; source `rate_limited/retryIn` replies cool down only that feature. No game send exists. | Verify current runtime inputs and actual dispatch arguments, build durable storage and native transport adapters, then narrowly verify one live action when a current client is available. |
| M4 Operations, Skills and earned claims | Pure ordinary Operation start/ready collection, native skill batch, earned playtime ladder, daily/weekly Contract entries and completion bonuses, free Briefcase picks, existing-member Group bonus, config-gated monthly claim, and two Gold-mastery trophy claim readers/planners/evidence use the same fake-adapter broker; none is live or packaged. The saved monthly config is disabled. | Verify current native indexes/rules/membership and response/state shapes; provide durable adapters, then narrowly observe each live path later. Owned-key Briefcase use and remaining trophy/cosmetic catalog are open. |
| M5 Bank deposits | Exact excess-cash proposal preserves user keep amount, same-snapshot purchase savings and uncertain cash; reply fee/kept plus replicated transfer prove an offline claim. Two Bank limits are exposed in the source UI catalog. | Build native savings/transport/storage adapters and verify real server rounding/outcome later. The rest of M5 remains open. |
| M5 purpose-specific withdrawals | An exact shortfall proposal requires the separate funding switch, originating Operation/Safehouse switch, same-snapshot purchase request and per-withdrawal cap. Newer cash/banked transfer is fake-adapter-tested. | Build a native purchase coordinator to produce/fence requests, then verify real transfer. Never turn this into periodic full-bank withdrawal. |
| M5 Safehouse upgrades | Next-tier-only proposal checks current 18-tier catalog, highest level, maximum tier/cost and cash reserve; newer exact tier proof is fake-adapter-tested. Three Safehouse limits are exposed in the source UI catalog. | Build native catalog/transport adapters and verify real server outcome later. Other Property actions and Prestige remain open. |
| M5 Property builds | A nondestructive no-slot `BuyProperty` intent checks current quote, level, capacity, ownership limit and cash reserves; fake broker requires exact newer owned-count proof. Existing Property policy and three limits are used. | Build current native catalog/capacity/discount and transport adapters, verify real outcome. Deletion, moving, replacement and Prestige remain open. |
| M7 Bosses | City staged attacks, Global Boss event/attack/claim paths, free-charge Family Takedown attacks and current/historical claim rows, weekly Family Takedown state, and selected-item Boss Shop purchase have offline coverage. The shop has reserve, unlock, durable session send cap and token/item evidence checks. | Validate current native adapters/responses, actual shop custody, remaining current-week reward semantics, then live-confirm each action when a client is available. |
| M4–M11 feature domains | All 50 legacy IDs and five added controls have UI entries and a parity disposition. Read-only Black Market browse and price history have bounded response parsers and a fake-tested shared read-budget composition. Sold-earnings collection is a separate offline descriptor with exact Gold-transfer evidence. | Implement every domain as separately verified ordinary-action slices; connect current native queries, UI bindings and live proof. A visible switch is not an implemented function. |
| M12 closure | Acceptance and cutover criteria defined. | Finish imports, release checks, feature-by-feature evidence, endurance and deliberate cutover. |

**Live functional completion today: 0 of 50 legacy gameplay feature IDs; 0 of 55
gameplay controls are wired to production requests.** The existing Fluent hub remains the
working fallback. Each row in the [parity register](parity.md) stays pending
until its new implementation and evidence are recorded. Offline source evidence
does not establish server acceptance or live success.

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
- [x] Read the durable Ember reference and official docs; subsequently retrieve and fingerprint the served Ember 3.0.0 source.
- [x] Confirm grouped pages, focused summaries and collapsed advanced settings with the user.
- [x] Incorporate the user's GitHub/separate-module preference into the delivery architecture.
- [x] Write architecture/UI proposal, 50-ID parity inventory and this delivery roadmap.
- [x] User authorized starting and requested source-based updates, local UI testing and substantially simpler menus/logic with the same functions.
- [x] Inventory all 231 Core.defaults keys and 52 literal control IDs with proposed dispositions.
- [ ] Finish dynamic-control, special permission, profile-field and transaction binding maps against the simpler schema.
- [x] Extract updated user-supplied place as inert data: native 0.26.487.1, 260 script-source records, 40/48 old selected sources changed, 42 checked anchors and 852 unique city districts. Runtime response shapes remain unverified.
- [x] Audit all 55 planned controls, six supporting systems and 15 configured pass keys for native replacement/reuse. Record 80 verified source anchors in the [native decision register](native-reuse-decisions.json) and [gear/reuse design](native-reuse-audit.md). Native server internals and runtime effects remain unverified.
- [x] Fetch/review/fingerprint actual Ember bytes: 3.0.0, unchanged October 12 SHA-256; callback, false-value and close-revert discrepancies remain. See [dependency review](ember-dependency-review.md).
- [ ] Resolve dependency redistribution terms before publishing third-party bytes or a runnable remote release loader. No license found in the served Lua; source remains private.
- [x] Select the existing public `iiSatomi/Roblox` repository and dedicated `idle-mafia-ember/` recode root.
- [ ] Establish supported HTTP/compilation/hash/cache primitives and a release destination before publishing executable modules; no embedded credentials.

Acceptance: agreed layout/behavior scope; complete setting dispositions; evidence gaps named per feature. If fresh game evidence is unavailable, M1 and fake-engine work can proceed using clearly labeled fixtures; gameplay adapters remain blocked on their own missing evidence.

Artifacts: updated design/parity, new versioned native-contract register and sanitized fixture provenance. Never store private tokens/account config values in docs.

## M1 — local simplified UI, then actual Ember prototype

Proposed source: `ui/EmberAdapter.luau`, `ui/Bindings.luau`, page/panel modules, `storage/Settings.luau`, `storage/Profiles.luau`, `App.luau` in prototype-only composition.

Slices:

- [x] Author local interactive design preview with 25 dedicated system tabs with 55 activity/permission controls including every legacy ID, four Combat Custom overrides and three Property overrides. No game bridge, account files or gameplay transport.
- [x] Run twelve local model/schema tests, including dedicated-tab ownership, mutually exclusive gear strategies, atomic conflicting-profile rejection and JS syntax checks.
- [ ] Verify actual browser layout, navigation/search, disclosure controls and narrow/wide states. Automated local URL/file navigation is blocked by browser security policy; visual checks remain open. Standalone HTML is available.
- [ ] Prototype the release loader with inert modules: one commit/manifest, initialize-once exports, verified complete prefetch/cache, and no partial application startup on failed downloads or compilation. This can follow the pure M2 broker work but must precede a public gameplay release.
- [ ] Resolve actual sidebar scrolling, group density, control search, long catalogs and status visibility at target/minimum viewport sizes.
- [x] Implement actual Ember methods for 25 dedicated tabs/55 switches with local-only labels, compact goals and bounded Custom inputs. Construction is offline-tested; real layout stays unverified.
- [x] Implement the current scalar settings schema and inert in-memory profile staging: false/enum/finite-number validation, atomic gear conflicts, paused hydration and validated UI rollback. No color/multi-selection preference is exposed in this slice; typed adapters are required before adding either.
- [x] Offline-test initial/superseded/unload callbacks, setter rejection/rollback failure, render-failure atomicity and destroy/recreate/partial-startup cleanup. F8 and reduced motion are configured; actual theme painting, input/focus and visibility remain unverified. Appearance persistence is disabled, not tested as successful storage.
- [x] Obtain a user-run startup diagnostic check of 0.1.1: no console errors or executor Problems reported. This does not certify the interactions below.
- [ ] Inspect actual Roblox Ember layout and interactions with gameplay dispatch disabled; record specific observations when available.

Acceptance: all current functions have a clear destination; most features expose 2–4 primary controls and Custom has at most six useful overrides; no mirrored settings or giant Advanced dump. Local browser checks and actual Ember rendering are distinct gates. Keep both visual gates open until observed; offline state tests do not establish rendering.

Checkpoint: review the real UI and revise navigation now. Do not spend gameplay effort around an unreviewed layout.

## M2 — reliability engine with no game mutations

Offline Tasks 1–4 in the [engine/Jobs implementation plan](plans/2026-10-20-engine-jobs.md)
are complete at their stated scope. Their 13 focused tests exercise the fake
transport. Task 5 is partially implemented with six context/scheduler checks.
The broader M2 items below remain open until native contexts,
durable recovery and release assembly are delivered.

Proposed source: session/capabilities, shared contracts, broker/lifecycle/scheduler/policy/resource ledger/recovery, Files, Journal/Health/Export; fake adapters and state fixtures.

Slices:

- [ ] Lock a small typed policy/settings model, shared snapshot/decision/proposal/record contracts and migration semantics.
- [ ] Establish native server-time, economic/decree/exemption, effective buff and native-automation ownership contexts from the updated source before gameplay. Use the supported native dispatch seam; never hardcode private handshake values.
- [ ] Distinguish each native entitlement from actual controller activity. Implement ordinary permitted-action planning as the chosen baseline and yield matching work to existing native activity. Unknown activity cannot be treated as stopped. Paid-controller unlocking is outside the current plan.
- [ ] Observe the native AFK session-refresh flow before adding duplicate idle protection. Checkpoint uncertain work and validate account/place/release on return; do not assume a loader survives or auto-restarts across teleport.
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
- [x] Connect settings → planner → broker → confirmation → status/journal with injected fake adapters; production wiring and live proof remain open.
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

Offline note: collection/start and skill allocation now have pure proposals and
state evidence, plus shared fake-broker/UI tests. Derived operation rate is not
yet used for scheduling; actual transport and live proof remain open. See
[Operations evidence](m4-operations.md), [Skills evidence](m4-skills.md)
and [Group claim evidence](m4-group-claim.md). The
[monthly path](m4-monthly-claim.md) is deliberately dormant because the
saved native config disables it. [Earned trophy claims](m4-earned-trophies.md)
currently cover only Vespera and Exiles Gold-mastery rewards.
[Earned playtime claims](m4-playtime.md) cover seven native ladder rungs
with replicated readiness and same-day claimed-marker evidence.
[Contract entry claims](m4-contract-entries.md) cover completed daily and
weekly rows. [Completion bonuses](m4-contract-bonuses.md) have a separate
switch and marker proof; exact reward delivery remains unverified.
[Free Briefcase picks](m4-free-briefcases.md) use replicated free balance
and same-board reveal proof; owned-key spending remains open.
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

The read-only personal board adapter passes offline tests. It does not
send Heist actions or infer a unique result identity from `heistId`.
Personal Heist start selection and exact-run evidence now pass the
shared fake broker; native sequence/reply identity remain unverified.
Ordinary Favor help selection and confirmation use the same fake broker.
Its native-day sent-attempt count is atomically written with the
unresolved checkpoint in fake storage; production storage remains open.
Separate Heist sabotage selection and exact-row evidence now pass
the fake broker with their own daily attempt count and opt-in switch.

Slices:

- [x] Read-only fresh personal board adapter and account/session
  validation offline; live shape and mutation sequence ownership open.
- [x] Personal start selection and exact-run evidence offline; native reply identity open.
- [ ] Personal result collection after result identity/sequence proof.
- [x] Favor helper selection/relationships/rewards, resources and fake-storage native-day cap offline; actual adapter and Custom controls open.
- [x] Separate sabotage opt-in, identity/relationship limits and exact-row evidence offline; native sequence/response and live outcome open.
- [ ] Shared board-read cooldown, uncertainty recovery, late evidence and startup reconciliation.

Acceptance: Heists → Favors → Operations precedence passes scenario tests; waiting boards yield appropriately; no borrowed sequence guessing, immediate replay, or success for missing result; a board-family failure leaves unrelated domains usable.

## M7 — Bosses and shared Takedown

The read-only staged city Boss adapter is implemented offline. See
[Boss stage state](m7-boss-stage-state.md).
An ordinary guarded `stageAttack` descriptor now also passes the
shared fake broker; see [Boss attacks](m7-boss-stage-attack.md).
A [read-only Global Boss view](m7-global-boss-state.md) now tracks
the exact event run, access, decay and claimability offline.
An [offline settled-claim path](m7-global-boss-claim.md) uses one
write-ahead send per exact run and native claimed-state confirmation.
An [ordinary Global Boss attack path](m7-global-boss-attack.md)
requires a personal hit/damage increase. [Boss Token Shop](m7-boss-shop-state.md)
and [Family Takedown](m7-family-takedown-state.md) have separate
read-only views. The [current-week Takedown claim path](m7-family-takedown-claims.md)
and [free-charge attack path](m7-family-takedown-free-attacks.md) use
separate guarded intents through the fake broker.

Slices:

- [x] Read-only native city Boss staged/day/HP/unlock state offline.
- [x] City Boss health/hit-back planning, daily send accounting and exact staged attack evidence offline; production/live proof open.
- [x] Read-only Global Boss event/run/access/settlement state offline.
- [x] Separate settled Global Boss claim attempt/evidence offline; live proof open.
- [x] Guarded ordinary Global Boss attack/send accounting and personal hit evidence offline; live proof open.
- [x] Read-only Boss Token Shop quote/token/item custody and crate unlock state offline.
- [x] Read-only weekly Family Takedown/free-charge state offline.
- [x] Current-week stage 1–5 Family Takedown claim send accounting and exact newer claimed-stage evidence offline.
- [x] Free-charge-only Family Takedown attack safety, weekly send cap and personal damage/free-use evidence offline.
- [ ] Separate Boss Token Shop choice, reserve, purchase proof and send cap.
- [ ] Production Global Boss watcher: scheduled starts, current public/access checks, changing medal rules and already-auto-settled rewards.
- [x] Exact unexpired historical Family Takedown claim rows, including per-week write-ahead attempt accounting and legacy checkpoint migration, offline.
- [ ] Remaining current-week reward semantics, current server hit-back and rank-strategy validation.

Acceptance: no city/player/global/Family identity mixing; stale event/run cannot act or claim; no intended Ticket spending; Combat owns the Takedown controls; related pages link there without editable mirrors.

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
- [ ] Native set-aware Auto Equip as the default operation, coalesced relevant-change triggers, no-op suppression, scope/custody validation and exact state proof. Native already claims two- and three-piece sets; do not build a second default optimizer.
- [ ] Read-only constrained-goal comparison against the native baseline. Implement custom swaps/complete-set plans only for a demonstrated objective gap with ownership, exact per-step proof and recovery. Keep cosmetics separate until native coverage is established. Never enable native and custom loadout owners together.
- [ ] Safe surplus Collection deposit with all seven native thresholds, variant/base-ID/bound custody, worn-cosmetic display/ownership separation and detailed unsupported-item reasons.
- [ ] Unbound chest opening with current native luck, batch/selection/cap and separate luck-only condition.
- [ ] All nine player restoratives, compact recovery policy/useful thresholds, independent three-second player clock, exact stack/sequence proof and separately enabled tradable use.

Acceptance: native operation reuse removes duplicate optimization/sort work; unsupported native custody guarantees remain a blocker rather than an assumption. Shared ownership/item reservations prevent competing gear/donation/equip operations; bound/equipped/training/stationed/recovering state stays protected; reroll never dismisses before durable funding/intent checks; the comparison report never becomes automatic permission to execute a multi-swap plan. Native controller use requires real ownership; ordinary hire/replacement remains separately bounded.

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

Connect the [M2 Task 5](plans/2026-10-20-engine-jobs.md)
read budget and economic/buff context to production native adapters.
The offline
lifecycle, loader core and Jobs vertical slice already have fake-adapter
checks. Keep detailed UI acceptance and live gameplay outcomes open
until actually observed.
