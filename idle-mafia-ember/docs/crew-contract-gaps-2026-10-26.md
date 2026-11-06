# Crew unresolved native contracts — October 26, 2026

> **Later October 27 checkpoint:** current hire is `CrewAction("hire", tier, quotedCost, nil)`, not the old omitted quote. Hire capture/evidence and late-slot/high-tier limits are corrected. Bounded ordinary replacement now has saved stages, settings, tab/call binding and an App/native-adapter cycle test. Native Auto Roll still has no demonstrated bounded-spend contract. See [Crew replacement checkpoint](m15-crew-replacement.md). Full regression: 1063 run, 1062 passed, one analyzer skip; whole Crew C/T/L still requires Task 24 ownership/reservations/recovery.

> **Implementation update, October 27:** both guarded three-argument heal descriptions and flat item intents now cross App/shared-broker/native-adapter fake scenarios. Capture rechecks current quote, identity, exposure and sequence; confirmation checks exact resource/custody debit and configured injury reduction. Actual `healId` now distinguishes duplicate names. Focused healing suite: 20 passed. See [guarded healing evidence](m13-guarded-crew-healing.md). Shared reservations/recovery, rolling/replacement and live acceptance remain open. The old signatures and missing-source descriptions below are historical, not current execution contracts.

> **Source correction, October 27:** the full place extraction includes `CrewHealModal-e3e00803a8de.lua`, `HenchmanHealingRules-a9bdbd860508.lua` and `ConsumableRules-41f72f0dc973.lua`. The historical missing-item-call claim below is superseded. Stamina heal is `CrewAction("heal", slot, {memberId=healId, injuredUntil=...})`; item heal is `CrewAction("healitem", slot, {itemId=..., fromBound=..., memberId=healId, injuredUntil=..., sequence=henchmanConsumableUseSequence})`. Crew cooldown/sequence is separate from the player's. Revisit the existing Crew planners, cost producer, call plan and tests against these complete sources; do not request another broad log or treat old two-argument healing as current parity. Shared stable-member reservations should use actual `healId` when available. No live Stamina test is authorized by this source correction.

Task 11 uses the saved `CrewTab-19f0c510d205.lua` and the supplied Cobalt
logs. Six ordinary signatures are source-backed in `CrewCallPlan`: Auto Equip
`AutoEquipCrew()`; Sort `CrewAction("sort", nil, nil, nil)`; Stamina Heal
`CrewAction("heal", slot)`; Train `CrewAction("train", slot, nil, nil)`;
empty-slot Hire `CrewAction("hire", tier, nil, nil)`; and Gear
`CrewEquip(slot, kind, itemId)`. The local quote/identity guards and newer
Sync evidence are independent of an unverified live server result. Stamina
Heal must not be live-tested during the Territory-war restriction.

## Crew item healing

The saved CrewTab contains no `"healitem"` command or member-targeted item
call. The saved InventoryTab and BossTab call `UseConsumable(itemId,
fromBound, sequence)` for the player inventory/pool; neither source supplies
a Crew member target. Neither supplied Cobalt log contains `healitem`.
`CrewHealItems` has an offline candidate reader and custody/evidence logic,
but its intent has no reviewed native call, so the UI marks it blocked and
the bound native plan refuses it. The smallest additional observation is
one normal client Crew item-heal action with outbound remote name, complete
argument count/values, reply fields and before/after member injury, item
stack and sequence. Do not infer a member argument from the existing player
`UseConsumable` call.

## Auto Roll and replacement

The saved CrewTab starts the controller with
`CrewAction("autoroll", emptySlot, tier, target)` and stops all with
`CrewAction("autorollstop", nil, nil, nil)`. The read-only `CrewRollState`
observes the native `derived.autoRoll` entitlement and rolling slots.
Starting remains blocked until the runtime can own and reconcile the
controller, stop it on disable/unload, and bound its ongoing Cash spend.
Replacement also needs a stable member reservation and separate dismissal
authorization; no draft intent may dismiss a trained, stationed, assigned,
rolling or recovering member. Task 24 owns shared arbitration, while Task 11
still owes the tab-local controller/replacement code and tests.
