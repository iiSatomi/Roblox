# Idle Mafia Ember recode — feature parity register

Date: 2026-10-20. Status: planning inventory, **not implemented**.

Baseline: feature-label registry and feature controls in `mafia/runtime/Interface.inc.lua`, settings/defaults and planners in `mafia/Core.lua`, related domain modules, newest handoff sections, and October 11 native snapshot. This registers all 50 current feature IDs. It does not certify old gameplay success or complete the upcoming per-setting/remote audit.

Every row is pending fresh implementation and current-native contract validation. Owners below are proposed new domains under `idle-mafia-ember/src/features/`; rows may share domain files without sharing run switches. Evidence needed for a mutation always includes its exact action-specific outcome, not merely an invocation return.

## Current feature IDs

| Old ID | New domain / page | Behavior and protections to carry forward |
| --- | --- | --- |
| `jobs` | jobs / Jobs & Operations | Selected/automatic jobs; city; XP/cash/energy, Balanced/Highest Tier/count/mastery choices; inclusive level/energy bounds; reserves; combined job-count/energy contract targeting. Recheck current costs/mastery/event helpers. |
| `heists` | heists / Heists & Favors | Personal starts; mode/catalog/level/energy/chest/duration/helper filters; stake and energy reserve; native board sequence ownership and stale-board recovery. |
| `heistCollect` | heists / Heists & Favors | Separate result collection; exact run/result identity and reward-state proof; no inferred successful completion from elapsed time. |
| `favors` | heists / Heists & Favors | Separate help switch; relationship exclusions, tier/reward choice, minimum cash/XP, Favor/energy reserve, durable native-day usage cap; exact board confirmation. |
| `sabotage` | heists / Heists & Favors | Own saved opt-in; non-friend/non-Family eligibility, native costs/per-heist limits, reserves/daily limit and exact board result. No goal may silently enable it. |
| `operations` | operations / Jobs & Operations | Separate start; free slots, selected catalog, level/cost/duration/chest filters, Best Chest/Balanced/Highest Tier/profit/XP choices, cash budget. |
| `collect` | operations / Jobs & Operations | Separate ready-slot collection; exact slot/run identity and replicated collection outcome. |
| `combat` | combat / Combat | Ordinary mugs; explicit player-attack permission, saved/new/high-value targeting, payout/sample/win/health/stamina/level/cost filters, scout/profile evidence, shields/hospitalization/per-day cooldown. |
| `warCombat` | combat / Combat | Independent active-war targets; verified enemy identity, fresh scout ratio, native daily limit, normal-mug handoff when appropriate. Keep Family war target catalog distinct from player hit-list identities. |
| `bosses` | bosses / Bosses & Events | Current native staged city Boss rules, prerequisite/daily state, modes and bounds, health/hit-back/stamina checks, encounter limits and boss-local pacing. |
| `bossShop` | bosses / Bosses & Events | Separate chosen Boss Token item/quantity/reserve, per-load send cap, native eligibility and exact token/reward confirmation. |
| `globalBossAttack` | globalBoss / Bosses & Events | Separate OFF default; event/run identity, live window, participation, health + hit-back buffer, stamina reserve, pacing, sent-attempt run cap, immediate preflight. |
| `globalBossClaim` | globalBoss / Bosses & Events | Separate OFF default; exact settled run, player participation, unclaimed window, attempt cap and claim/reward proof. |
| `crew` | crewGear / Crew & Gear | Native best-gear equip after relevant changes; no repeated no-op requests, protected/unavailable members, coordination with custom optimizer. |
| `crewGear` | crewGear / Crew & Gear | Player + Crew + Collection scoring; sets/bound/equipped protection; safe swaps and guarded multi-step complete sets, exact per-step proof, interrupted-plan recovery, read-only outlook. Do not claim a globally reachable optimum. |
| `crewRoll` | crewReroll / Crew & Gear | Current hub-managed normal dismiss/hire; empty slots first; tier/rarity/base-stat-quality rules, worst-first choice, cash reserve/purpose-specific bank funding, recruitment-luck gate; protect trained/assigned/injured/recovering/rolling Crew. Current source does not require the old Auto Roll entitlement. |
| `crewSort` | crew / Crew & Gear | Separate native sort after composition/training/gear changes; stable fingerprints; pinned/stationed/rolling members remain protected. |
| `crewHeal` | crew / Crew & Gear | Separate native healing of injured Crew, longest injury ordering, stamina reserve and exact recovery-state proof. |
| `crewTrain` | crewTraining / Crew & Gear | Separate training; native rarity/level price, target level, max cost/concurrency, available home-Crew minimum, exact member/timer/cash proof. |
| `crewHire` | crewReroll / Goals & Rewards | Bounded Auto Contracts hire for an empty slot only; chosen tier/max cash. A contract-owned activity, not an unrestricted hire loop; never dismisses for the contract. |
| `cosmetics` | cosmetics / Inventory & Collection | Joint background/border evaluation, final weighted stats and Collection effects, native slots, protected bound/equipped state and confirmed rearrangement. |
| `collectionDonate` | collection / Inventory & Collection | Separate safe-surplus deposit; native batches, reserve equipped/set/gear candidates, checkpoint protection, skip explanations. Unsupported/upgraded/bound consumptions remain unavailable unless separately established. |
| `chests` | inventory / Inventory & Collection | Separate unbound chest opening; owned-only, selected/all eligible chests and batch/cap, crate-luck-only gate, current native luck preflight and reward/count proof. Never auto-buy or open bound crates. |
| `restoratives` | inventory / Inventory & Collection | All nine native Health/Energy/Stamina sizes, per-resource threshold and size preference, bound first; tradable use separate; native cooldown/sequence and exact stack/resource proof. Never use Upgrade Insurance. |
| `shop` | shop / Shop & Market | Cash-only native rotation quote; selected/buy-all, category/rarity/owned cap/price rule, optional rarity override, separate cosmetics/crates/bank permissions, quote expiry, purchase limits. Gold Shop remains unavailable until its contract is verified. |
| `marketWatch` | marketResearch / Shop & Market | Read-only listing/price/sales/supply research and reports, bounded pages/cache/batches, current response validation, cash-Shop opportunity comparison, fair scheduling. |
| `marketFlip` | marketTrading / Shop & Market | Separate OFF default; verified buy → list flow, recent-demand/margin/price limits, Gold reserve/budget, open shop/slot, exclusions, exact item/listing identity and durable review on uncertainty. |
| `marketRent` | marketTrading / Shop & Market | Separate OFF default; current native rental quote, shop expiry, Gold reserve, per-load attempted rent cap and expiry/resource proof. Do not assume old one-Gold price is permanent. |
| `marketSell` | marketTrading / Shop & Market | Separate owned-item listing; loose/unbound/protected copies, optional guarded Collection withdrawal, checkpoint preservation, type/rarity/item blacklist, demand filter, net-Gold/RAP/undercut rules and send cap. Each step confirms. |
| `marketManage` | marketTrading / Shop & Market | Separate sold-earnings collection; minimum threshold, earnings/Gold proof; active/aging listing report and durable ledger. Aging reports do not authorize cancellation/repricing. |
| `bank` | money / Money & Property | Excess-cash deposit threshold/cash-to-keep and native fee awareness; preserve active purchase savings and budget reservations. |
| `withdraw` | money / Money & Property | Purpose-specific bank-funding permission and exact-shortfall/withdrawal limit, confirmed transfer before replan. Not a standalone periodic withdrawal routine. |
| `properties` | properties / Money & Property | Current scaled price, catalog and inclusive filters, ROI/income/tier choices, ownership/session/per-action limits, cash saving; separately protected destructive replacement and durable restart evidence. |
| `safehouse` | properties / Money & Property | Next eligible native tier, level/affordability and tier/budget cap, exact tier/spend proof. |
| `prestige` | progression / Money & Property | Separate native requirement/rank and per-load send caps; exact rank/level-reset proof. Protect against re-evaluating stale pre-prestige catalogs/state. |
| `contracts` | rewards / Goals & Rewards | Separate completed daily/weekly entry claims; native current schema and legacy migration support where justified, exact entry identity. |
| `bonuses` | rewards / Goals & Rewards | Separate completion-bonus claim; all prerequisites claimed, identify energy refill and crate award; no automatic crate opening. |
| `trophies` | rewards / Goals & Rewards | Earned native trophy/cosmetic claim, ownership/readiness check; exclude item-consuming set trade-ins. |
| `briefcases` | events / Goals & Rewards | Separate free picks; first unopened case rather than invented prize prediction; owned-key spending separate with cap; exact board reveal, never buy keys. |
| `skills` | rewards / Goals & Rewards | Chosen native stat, allocation cap and verified batch/cost limit; exact points/allocation proof. |
| `playtime` | rewards / Goals & Rewards | Earned playtime cash/crates; separate energy-refill preference and threshold; do not fake elapsed time or infer a separate login reward. |
| `groupBonus` | rewards / Goals & Rewards | Claim only for verified existing group membership and eligibility; no auto-join. |
| `familyCash` | family / Family & Territory | Separate OFF default, amount/reserve/per-load cap, Family response/counter and cash proof. |
| `familyStamina` | family / Family & Territory | Separate OFF default, native batch/reserve/cap, selected-perk rotation/maxed skip; hospital/stationed conditions preserve current OR semantics when both selected. |
| `familyGold` | family / Family & Territory | Separate OFF default and default-zero cap; tradable Gold only, reserve/amount and exact contribution proof. |
| `familyBossAttacks` | takedown / Family & Territory | Separate free-charge weekly Takedown attacks; zero held Tickets where native action can consume them, health/stamina safety, Steady/Rank focus, exact weekly/stage proof. Mirror on Combat shares the same setting. |
| `familyBossClaims` | takedown / Family & Territory | Separate exact week/stage reward claims; fresh native response and disappearance/claimed proof, no assumed completed reward. |
| `territoryWatch` | territory / Family & Territory | Read-only holdings/bonuses/garrison and station advice, exact district/family/user identities; no attack, siege, orders, or station permission from watching. |
| `station` | territory / Family & Territory | Separate station; home/maximum-deployment limits, exact own-Crew/garrison proof; separately enabled quiet recall/transfer, training rotation and low-health combat recovery; native recall request/status/recovery ordering, minimum retained defenders, cooldown and exact preflight. |
| `residency` | territory / Family & Territory | Separate own-residence selection/move, catalog bonus, allowed districts, rent and improvement limits; recheck native admission and exact resident status. No Family policy changes. |

## Controllers and supporting functions outside the 50-ID list

| Area | Preservation / improvement requirement |
| --- | --- |
| Auto Contracts | Supported ordinary-personal objective execution, objective selector/exclusions, visible borrowing permissions, hire budget and prerequisite/blocker explanations. Sensitive PvP/Favor/Family/sabotage opt-ins stay separate. Unsupported districts/siege/trade objectives stay visibly manual until exact flows are proven. |
| Contract Focus | Only reprioritizes already-effective activities; combined job-count/energy behavior and short-Operation objectives. Distinguish this preference from Auto Contracts starting permitted ordinary work. |
| Trophy Hunter and Focus | Read-only native progress/ownership/next blockers, chosen target, goal execution through permitted activities, claim when ready, precise explanation for unsupported routes. No item-consuming trade-ins. |
| Historical Progression | Older design/history only; absent from current interface. Keep documented as a possible future controller, not secretly enabled parity code. |
| Event awareness | Native cash/XP/mastery/regen/Operation/Boss/Takedown/luck/Shop-sale state; visible remaining time, optional event ordering, per-feature luck conditions and correct current helper values. |
| Combat memory | Per-account mug history/totals, exact saved-user search, high-value promotion/demotion, persisted scout/evidence freshness, attack/scout activity log, observed native outgoing attacks and cooldown reasons; redact exports. |
| Crew advice | Native rarity/base-stat percentile, set/Collection breakdown, read-only whole-loadout and station outlook; no false global-optimum guarantee. |
| Market memory | Confirmed buy/list/sale/earnings ledger, research freshness, aging listing suggestions, restart reconciliation. Automatic bot-check answers are deliberately excluded; native manual resolution/pause remains. |
| Profiles | Create/save/select/load-now/next-run/autoload/off/delete/account overview, active-profile sync, themes/layout, schema migration/import preview. Preserve data without silent action on first import. |
| Session reliability | Place/account guard, one sender, one-second minimum/quarter-second planning, exact 45-second skip with duplicate-risk log and cooldown, late proof, bounded failure backoff, heartbeat independent of stale UI/state, stop/unload/teleport checkpoint. |
| Idle protection | Separate opt-in, capability-aware non-click input method and input/idle observations, clean stop; no forced game mutation or anti-cheat claim. |
| Diagnostics | Native compatibility, precise blockers, bounded action journal, send/response/confirmation pacing, state/UI/storage health, redacted export/copy and bot-check evidence capture. |
| Shared settings | Health/stamina/energy floors, bank funding permissions, reserves, purchase limits, stable catalog selectors, per-feature caps and sensitive-action permissions; shared values synchronized without callback loops. |

## Intentional exclusions and unresolved contracts

- No production confirmation bypass or automated bot-check answers.
- No new Robux/real-money purchases, anti-cheat evasion, trade automation, destructive inventory sales/trade-ins/upgrades, or broad Family policy/siege automation.
- Existing Market listing/selling, Crew dismissal and property deletion are explicitly bounded parity areas, not new authority to execute them during development. Keep their distinct opt-ins and live authorization requirements.
- Old unsupported Gold Shop settings do not justify an active new toggle. Show unavailable status until native arguments/outcome are established.
- No automatic replay of uncertain legacy actions or transport cancellation claim.

## Completion record required during implementation

Expand each row into a concrete record containing: stable new feature ID, every mapped setting/control/default, new source path, native build/source location, exact request/reply/state contract, fixtures, offline checks and date/results, live rendering evidence, live gameplay evidence, and unresolved limits. This proposal establishes coverage responsibility; those records supply proof.
