# Simpler controls, same capabilities

Updated 2026-10-20 following the user's request for substantially simpler menus and logic, including Combat and Properties. This supersedes the earlier assumption that all old settings should be recreated in collapsed advanced groups.

## What is preserved

Preserve the 50 legacy feature capabilities and their independent permissions, current-native safeguards, useful item/target choices, financial boundaries, and recovery. Do not preserve every tuning knob, duplicate setting, old heuristic, or stale constant as a new control. The 231-key legacy inventory is migration evidence, not the new UI schema.

## The normal interaction

Most features have an On/Off switch, one goal/policy choice, and a short explanation of what happens next. Show at most two to four primary controls for a feature. A single **Custom** disclosure may expose at most six reviewed, useful overrides. If a feature needs more, split independent responsibilities or redesign the policy; do not hide the old 231 options in a giant Advanced menu.

Every routine still has its own switch. Player attacks, Gold/key/medal spending, item consumption, destructive replacement, Family contributions and station/recall retain distinct controls and visible limits. A preset never silently authorizes one of them. Necessary spend/reserve summaries remain visible even when Custom is closed.

Native costs, timers, unlocks, rarity/set lists, fee rounding, buff composition and eligibility are automatic current-state facts, not user configuration. Similar preferences use one consistent goal vocabulary. Keep feature-specific choices when they describe a real outcome: mastery, a selected Job, a particular chest, a desired Crew rarity or a residency bonus.

## Dedicated system tabs — 25 sections

The user explicitly requested a separate tab for each system. This supersedes the initial 13-page grouping: simplify the controls within each tab while keeping unrelated systems apart. Combat owns all related fight routines.

1. Overview — Current action, next choice, blockers, pause/stop, shared context and quick links.
2. Heists — Personal Heist start/collect and separately permitted sabotage.
3. Jobs — Selected or automatic Jobs, goal and native ownership status.
4. Operations — Operation start/collect, goal, slots and budget.
5. Favors — Heist help, eligibility, energy reserve and daily usage.
6. Combat — Player permission, Mugs/War, city Bosses, Boss Token Shop, Family Takedown attacks/claims and Global Boss attacks/claims.
7. Crew & Gear — Rerolls, hiring, training, stamina/item healing, native equip, gear/sets and recovery.
8. Inventory — Cosmetics, owned unbound chests and player restoratives.
9. Collection — Safe-surplus deposits, native checkpoints and protected copies.
10. Money — Bank deposits, reserves and purpose-specific shortfall funding.
11. Property — Property buying goal, cash limits and separately permitted replacement.
12. Safehouse — Next eligible Safehouse tier and upgrade budget.
13. Prestige — Native requirements, reset permission and per-load limits.
14. Shop — Native Shop rotation, item choices and purchase budget.
15. Black Market — Research, listing/selling, flipping, rental and sold-earnings collection.
16. Family — Separate Cash, Stamina and Gold contributions.
17. Territory — Holdings, station/recall/residency and read-only city/season/decree/fortification context.
18. Contracts — Auto Contracts, objective/focus choice and earned entry/completion claims.
19. Trophies — Trophy goal/focus, progress and earned claims.
20. Skills — Chosen stat and earned skill-point allocation.
21. Rewards — Earned playtime, monthly and group claims.
22. Events — Briefcases, effective buffs and Event Shop; Global Boss controls belong only to Combat.
23. Profiles — Active versus selected profile, import preview and explicit activation.
24. Settings — Appearance, idle protection, common resource limits and optional event preference.
25. Activity — Current reasons/recent outcomes; compatibility, timing and technical export collapsed.

Each tab starts with a short summary and owns its controls. Related routines can use small groups within that tab. The sidebar scrolls independently, and search locates features across tabs. No editable controls are mirrored elsewhere; Overview and related pages link to the owning tab instead. Verify the longer rail in actual Ember before gameplay implementation.

## Concrete simplifications

| Area | New normal controls | Backend behavior / optional Custom |
| --- | --- | --- |
| Combat | Allow player attacks; separate Mugs/War switches; Target policy | One eligibility → evidence → rank → send pipeline. Policy supplies conservative screening and bounded discovery; exact ID, health, resources, shields, injury and day limits always apply. Useful Custom: minimum payout, health floor, stamina reserve and target source. Retain read-only estimates without promising wins or exposing many confidence-weight knobs. |
| Properties | Buy properties; Goal | Compare eligible native quotes with a single deterministic score for the chosen goal; coordinate bank saving and exact shortfall funding. Useful Custom: cash to keep, maximum purchase and owned limit/selection. Destructive replacement remains its own OFF-default permission with exact delete/buy recovery. No user-editable native tax, discount, cost-growth or recovery timings. |
| Jobs/Missions | Per-routine switch; Goal; selected item only when needed | Native costs/unlocks/timers, goal-directed ranking and shared reserves. Keep mastery/selected/catalog choices available without showing all min/max bounds on the default page. |
| Crew | Separate function switches; minimum rarity/target training goal; gear strategy | Prefer native set-aware Auto Equip and native sort. Custom gear is an optional constrained goal only after comparison proves a gap; it is mutually exclusive with native equip. Stable member identity, current costs and injury/training/recall checks are automatic. Keep only meaningful funding/quality/reserve overrides. |
| Shop/Market | Separate action switches; item/policy selection; visible budget | Native price/tax/fee calculation, demand/quote freshness and exclusions live in focused planners. Cash, Gold, medals, listings and irreversible transfers keep separate permission/budget boundaries. |
| Inventory | Separate equip/deposit/open/use switches; resource priority | Native cooldowns, correct stack/variant identity and Collection checkpoints automatic. Keep owned-item/size/threshold choices only when they change intended behavior. |
| Family/Territory | Independent contribution/station/recall/residency permissions; purpose/amount | Costs, caps, own-member checks, city/garrison/bonus and lock/recovery facts computed automatically. Season/fortification/decree context is read-only first. |
| Diagnostics | Current reason; recent outcomes; export | Technical retry delays, cache sizes, learning weights, request IDs and state schema are developer diagnostics, not ordinary tuning controls. |

Preset names and numeric values are proposals until current-native planner tests establish them. A cosmetic policy choice in the browser preview is not a verified combat or investment strategy.

## Simpler implementation as well as menus

The [native reuse audit](native-reuse-audit.md) governs replacement choices across all 55 controls. Reuse native operations, rules and batches. The user now chose ordinary available-action automation for Jobs/Bosses/etc.; paid-controller unlocking is outside the current recode task. Keep only the missing goal/limits/scheduling layer. Existing native controller activity remains visible and the hub yields affected work.

Each domain has one readable decision pipeline and one source of truth for limits. Avoid separate nearly identical planners for manual work, contracts, trophies and events. Goals supply an intent to the same planner; they cannot create another sender. Split only meaningful transaction stages; do not build a generic rules language or a compatibility layer that permanently reimplements every legacy knob.

Presets resolve to a small typed policy record, then pure planners consume that record plus native contexts. Do not scatter preset-name comparisons through the runtime. Protocol deadlines, backoff and matching rules are tested engine constants/adapter facts, not config fields to expose just because the old hub exposed them.

## Migration without silent behavior changes

Classify old settings as: merge into a named policy, retain a useful Custom override, compute automatically from native state, migrate runtime usage into the ledger, map presentation, or exclude obsolete/bypass behavior. The settings inventory records candidate dispositions; it does not promise 231 future fields.

Import previews must identify old non-default limits that cannot be faithfully represented. Show the proposed simpler replacement and leave that profile inactive until reviewed. Do not silently drop a user's spending cap, attack permission, target exclusion or unresolved transaction. Do not retain a hidden permanent legacy mode just to claim exact option parity.

## Local UI testing

The browser preview is an interactive **design/test tool**, not the Ember library running outside Roblox. It uses simulated data, no game bridge, no account files and no persistent settings. Test page navigation/search, disclosure density, useful presets/overrides, false-value hydration, pause/stop, blocked states and narrow/wide layout locally.

Offline tests can also exercise the eventual Luau policy/planner/transaction modules with fake clocks, state and transport. They do not validate the game server or real Roblox GUI APIs.

Actual Ember API compatibility, fonts/scaling, pointer/focus behavior, respawn, F8 and cleanup still need a small real Roblox rendering check. First render it with gameplay dispatch absent. A browser screenshot must never be labeled a screenshot of the actual Ember hub.

## Acceptance

- All 50 legacy IDs remain accounted for, while new features have separate proposed coverage rows.
- Heists, Jobs, Combat, Collection, Money, Property, Shop and Black Market each have a dedicated tab; related fight controls appear only in Combat.
- Normal Combat and Properties use the compact controls above; no giant Advanced settings dump.
- Each Custom disclosure stays within six meaningful fields; protected actions remain separately permissioned.
- No mirrored setting copies or goal-specific duplicate planners.
- Preview status always identifies simulated data, cannot contact the game, and never claims live outcomes.
