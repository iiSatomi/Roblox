# November 6 completion continuation

All 55 catalog permissions remain available across 27 pages, with fresh switches
off and explicit saved-profile autoload preserved. The reviewed continuation is
published with coherent source, manifest, and entry pins. **The 100% gameplay
acceptance target is not yet met.** Bounded results remain separate from support
for every advertised mode.

The [recovery report](recovery-2026-11-06.md) describes the earlier recovered-r35
merge and its immutable published pins. Its test totals and migration limitations
are historical checkpoints. This continuation records subsequent work without
replacing that history.

## Latest feature completion pass

The latest source is `1e6b680`; its manifest is `f01fff0` and entry is
`2a90ea5`. These pins are published, but their new in-game startup and feature
acceptance are **pending**: Potassium lists the client while neither console nor
file heartbeat scripts execute. Roblox's recent log contains DNS failures;
the precise cause of the stalled execution connection is not established.
The previous runtime was paused and destroyed before staging. No new migration
or gameplay action has been confirmed for this release.

Implemented and independently reviewed:

- Heist/Favor continuity can recognize a verified fresh native controller epoch
  while retaining imported quotas and historical receipts. No counter is reset.
- Playtime income-Cash and active-XP rewards can prove the exact claimed tier and
  reset through owned terminal success and later native state. Exact income
  payout and XP extension amounts remain unverified, rather than estimated.
- Market research browses the native base-item family and preserves exact
  upgraded IDs for pricing, demand, custody and listing. Loose upgraded copies
  are supported; upgraded Collection withdrawal remains unsupported because
  the native selector cannot prove exact origin. Zero-sales responses with no
  average are cached and reported as insufficient history, never priced at zero.
- Reviewed code upgrades retain typed Recall, Market and known-unsent records,
  immutable historical receipts, generation integrity and unresolved Operations.

The earlier full baseline passed **3,849 tests and 3,106 subtests**. The
follow-up full run recorded **3,875 passing tests and 3,231 passing subtests**,
but also seven failures: one Residency acknowledgement regression and six
Crew replacement fixture assertions using an insufficient timeout. Those failures
were corrected and rerun in focused groups; the entire suite was not rerun after
the final corrections, so the follow-up full run is not reported as all passing.

Fresh manager verification of final runtime, Residency, Crew replacement and
Market compatibility changes passed **127 tests and 106 subtests**. Independent
final Market review passed **50 tests and 46 subtests**. Final release pin and
entry integration checks passed **16 tests and 59 subtests**. Counts overlap
and must not be added. All **316 tracked Luau files compile**. Existing analyzer
warnings are documented in the individual reviews; no new diagnostics were found.
Private native-fixture requirements described below still apply.

The cumulative ledger now records **19 of 55 controls (about 35%)** with at least
one confirmed native path, plus four read/goal reports. This measures observed
paths, not overall feature completion. The new nineteenth control is Combat
**Scout** request41 on the previous published source, with one Scout attempt and
zero Attack attempts. A subsequent Attack selection had no eligible target.
The original unresolved Operation4 still holds 200 Cash.

The follow-up audit also reproduced and fixed pending-callback custody gaps in
Crew Heal, Crew replacement, Family Boss claims and Market composite transactions.
Ordinary runtime adapters now retain explicit pending replies both live and after
serialized restart; native lifecycle owners can still obtain an independent
terminal status. Market pending replies cannot advance buy/withdraw/list stages,
and Crew replacement cannot turn them into a dismissal or rehire completion.
Crew Heal can confirm exact owned injury reduction despite noncontradictory
Stamina regeneration. Family claims can confirm exact claim consumption and item
awards despite surplus passive Cash; exact Cash delivery remains unverified.
Global Boss claim capture now accepts the same finite positive participation
values as its planner, preserving the exact fractional value and all other proof.

Residency has a narrow acknowledgement contract: an owned successful request
reply may remain pending while a later exact approved lease supplies completion
evidence. Other pending callbacks remain held. Historical Market records that
were incorrectly saved as observed with an unfinished callback retain their
original bytes, stage, usage and reservations, including nested purchase origins;
they cannot authorize continuation or cleanup.

The remaining sections retain evidence for the preceding published release;
their older suite totals and 18-control checkpoint are historical.

## Code and custody

Reviewed storage-lineage activation preserves the original canonical data identity,
nonzero allowances, immutable legacy receipts, and request high-water marks. It
archives source bytes before changing ownership and retains unknown sent actions.
Missing native continuity blocks the affected Heist/Recall route rather than
silently resetting usage. Explicit paused startup can load settings and autoload
choices without sending before Resume.

Subsequent reviewed fixes cover transient and contradictory reply custody,
Group/Contract terminal recovery through normal tab descriptors, a native-owned
Crew hire quote, bounded Crew sort action keys with complete roster baselines,
Shop purchase completion amid passive Cash changes, and the current build-654
Boss selection source. The Residency view parser also accepts the native explicit
`none` status without changing admission or rent limits. Contracts with every
borrowing permission off now report waiting; no ordinary permission is enabled.
A Territory Map read now opts into a one-second admission window, deferring late
starts before budget/lease acquisition so a dependent District read has time.
Existing exact-header and two-second result guards remain unchanged. The manager
subsequently confirmed one bounded Station action on the new stage (request 36),
now included in the cumulative ledger. The imported attempt floor correctly
refused a cap of 1 before an effective cap of 2 allowed one new action.
Final Boss, Boss Shop, Global Boss, Monthly, and source-wrapped Playtime guards
also retain custody for recognized pending/busy callbacks before either outcome.
Stationing can preserve an unidentified unselected home bystander as an exact
observation without making it selectable, counting it toward home defense, or
assigning it a member identity. Ambiguous deployments still block.

Contract claim completion proves the exact native claimed marker for the original
row and reset. It does **not** independently prove exact Cash, XP, or item award
delivery. The Shop alternative proves a purchase outcome; it does not assert an
exact wallet debit, and the authorized quoted-spend allowance remains charged.

## Verification

- The manager's final local combined suite passed **3,820 tests and 3,047 subtests**.
  This includes the read-admission and passive-Cash settlement changes
  (392.91 seconds). All **315 Luau files compiled with zero failures**. The local
  suite includes ignored native Prestige fixtures; a public checkout needs those
  private fixtures for the corresponding tests. Do not publish captured native source.
- Independent focused checks passed: native hire source/Hire runtime/Host/bindings
  **95 tests and 39 subtests**; claim guards and normal terminal recovery
  **64 tests and 193 subtests**; Shop outcome/recovery **58 tests and 53 subtests**;
  Operations custody **58 tests and 13 subtests**; Boss selection/catalog/runtime
  **48 tests**; Residency query/runtime/comparison **41 tests and 3 subtests**;
  Market variant source/quote/report **68 tests and 51 subtests**;
  Skills/Prestige custody and saved recovery **78 tests and 26 subtests**;
  final Boss/reward transient guards **80 tests and 20 subtests**;
  final Station/Recall App/Residency group **123 tests and 32 subtests**;
  read-admission/real Territory source group **70 tests and 28 subtests**,
  independently verified by the manager with **117 tests and 50 subtests**;
  Crew owned-settlement group **67 tests and 66 subtests**;
  Property/Safehouse independently reviewed group **65 tests and 117 subtests**;
  goal routing/status **52 tests and 3 subtests**, with independent
  goal review passing **57 tests and 3 subtests**.
- The fresh build-654 `BossStages.get` capture matches the reviewed archived
  build-653 function exactly after LF normalization. Its gate still retires on
  any subsequent build change. Private native captures remain unpublished.
- These focused batches overlap and must not be added together. All submitted
  followup slices have independent review. Final pin/entry integration passed
  **11 tests and 59 subtests**, and both published entry files compiled.
  Remote branch bytes match the published entry commit; all 309 manifest modules
  match the tested working source.

## Current live evidence and limits

The [live ledger](completion-live-2026-11-06.json) records **18 confirmed mutation
paths** and **four read/goal reports**, across 38 feature rows with prior
observations retained.
The newest confirmations are normal recovery of original Shop
request 27 with zero new purchases, one 14-Token Boss Shop crate, and one
1-Stamina Boss hit. The new 0d stage also confirmed Station request 36, one
explicitly opted-in free Family attack at 37, and Property purchase 38. The Family
attack used 1 Stamina, no tickets, and initially showed 31 Health lost before
regeneration; this does not establish future damage or all attack modes.
Reports cover Territory, Market variant pricing withheld,
existing Trophy ownership, and Contracts waiting with borrowing off. This does not
cover every advertised mode. The exact published RuntimeEntry subsequently loaded
successfully: alive, paused, automation not requested, no storage fault, and the
canonical request high-water remained 38 with only original Operation 4/200 Cash
pending. Published Recall request40 then confirmed and returned the selected
member home; request39 had cancelled before native invocation. A normal published
restart remained alive, paused and not requested at high-water40, retaining only
original Operation4/200Cash. This adds a verified Station branch, not another
feature to the18count, and does not certify every gameplay path.
The [55-control matrix](feature-acceptance-2026-11-06.json) separates implementation,
offline coverage, historical results, current observations, and remaining cases.
The [bounded acceptance recipes](acceptance-recipes-2026-11-06.md) describe exact
settings and prerequisites; they do not assert that a live candidate is available.

The [prerequisite snapshot](completion-prerequisites-2026-11-06.json) inspected
11 features from one genuine fresh enriched snapshot while paused. It made no
native calls and changed no settings. Quotes inspected with switches ignored are
read-only diagnostics, not dispatch authorization or successful gameplay.

Remaining limits include:

- Original Operation request 4 remains unresolved with 200 Cash held. A separate
  bounded Operation selection was refused before invocation because unresolved
  exposure remains. Shop request 27 has reconciled normally without another
  attempt or request-ID increase; its original 375-Cash allowance remains charged.
  Unknown actions are not resent or erased to obtain a passing result.
- Briefcases are currently inactive despite a historical free count. Monthly
  rewards are disabled by native configuration. Event Shop earned currency and
  current offers are unavailable in the recorded prerequisite snapshot.
- Recorded Prestige is level 92 against a native required level of 200, with the
  explicit reset choice off. Recorded Skills have zero available points. A later
  manager read provided full-health/free Family attack proof for the single
  confirmed test. That used the separate unknown-damage opt-in; bounded known
  hit-back mode still requires its own source proof and is not implied accepted.
- Recorded Contract bonuses, Contract entries, earned Trophies, Group bonus,
  Family claims, and Global Boss claims lack a currently eligible unclaimed
  outcome. Global Boss is in its completed phase. These are prerequisites, not
  reasons to manufacture eligibility or mark a mutation accepted.
- The recorded Safehouse level 17 quote is 50T Cash, exceeding approximately
  1.7T Cash plus 28T Bank. Current Heist Energy is 22 against a cheapest cost of
  25. No upgrade, withdrawal, or Heist is implied by these observations.
- Trophy Focus reported existing ownership with zero attempts; this is a goal
  report, not a newly acquired Trophy. Auto Contracts' corrected waiting message
  is now observed live with all borrowing off and zero attempts.
- Market Watch now reports 10 listings and one upgraded variant with pricing and
  trading withheld. Exact item IDs/prices remain intact; this is a read report,
  not an executable price or trade acceptance. Residency's native view now parses,
  then its zero attempt cap blocked admission. A later read reaches the existing
  residence/replacement guard; no Residency mutation is accepted.
- Property and Safehouse owned-outcome/restart adapters are now independently
  reviewed, including immutable legacy-baseline compatibility and normal Safehouse
  descriptor recovery. Selected Property count or exact next Safehouse tier plus
  owned terminal success and later noncontradictory Cash can certify completion.
  Crew training/hire use their exact member/timer/level proof. None estimates
  income or claims an exact wallet debit; original quotes and Hire spend allowance
  remain retained. New Property purchase 38 is accepted; Safehouse remains
  unaffordable, and live Hire/Training alternative acceptance is separate.

The release pins and entry checks are published and remotely verified. Further
bounded native acceptance requires real prerequisites. Inactive or unaffordable
cases remain explicitly unaccepted; the report makes no full-completion claim.

## Release pins

Source: [`1e6b6805f7ddf0545d433396633072a3da2e159a`](https://github.com/iiSatomi/Roblox/tree/1e6b6805f7ddf0545d433396633072a3da2e159a/idle-mafia-ember).

Manifest: [`f01fff0120543ca65a57b594fda01b957b6cd813`](https://github.com/iiSatomi/Roblox/blob/f01fff0120543ca65a57b594fda01b957b6cd813/idle-mafia-ember/manifest.json).
Manifest SHA-256: `7aab1e4ce0c9ddd5fd5b87f6768b26b02bc7900d3e303a9dad9e4b548f1296cf`.

Entry: [`2a90ea5e0c4f461ef2b5422af4001b5168f0f689`](https://github.com/iiSatomi/Roblox/tree/2a90ea5e0c4f461ef2b5422af4001b5168f0f689/idle-mafia-ember).
The entry pins the immutable source and manifest commits above. These supersede
the historical r35-merge pins without rewriting that recovery report.
