# Selected own-member Recall — November 6, 2026

The advertised Station **Recall** mode now has a broker-owned route. Native
`CrewRecall.start` is deliberately unused: the reviewed 654 implementation starts
its own three-second status and fifteen-second resubmission loop. Automation sends
one `TerritoryAction:InvokeServer("recallcrew", requestId, {target})` through the
normal sender. A shared-lane `TerritoryStatus:InvokeServer("recallstatus",
requestId, nil)` can supply the exact settlement. Unknown requests never resubmit.

The source-bound native controller reads the reviewed request counter, epoch
floor, context, remote wrappers and busy flag. It never changes native upvalues.
Root independently live-bound this reader on place version 654 and confirmed a
current, idle controller. Version 655 is not covered by this Recall binding.
Missing or retired binding disables new Recall and status calls while existing
durable member custody remains protected.
The Bootstrap storage account is the player's name. It remains separate from the
verified numeric native `Player.UserId`; both are checked independently. A
numeric-account-only fixture originally concealed that production distinction.

## Permission and evidence

Recall requires the explicit mode, one selected own member and district, a nonzero
deployment attempt limit, a current owned district/map, and the minimum remaining
garrison. Stable `healId`, native deployment token/time, member index, name and
rarity must agree. Reserved, training, rolling, recalling, injured and pending
members are unavailable. The broker independently checks all other custody again
before invocation.
The selected returning member must have its real stable `healId`. A nonselected
legacy member without that field can be preserved by its real, unchanged native
deployment token while it remains deployed. This never creates a `healId`, uses
slot alone as identity, or permits that legacy member to be the returning target.
Missing both identities or duplicate deployment tokens still refuses custody.

Preparation and the sent gate are persisted before emission. Recovered sent
records are status-only; recovered preparation is known unsent. Pending or
negative server returns consume the attempt and keep custody. Confirmation needs
one exact successful settlement and a newer full Crew Sync showing that same
stable member home, with unchanged equipment/training and either no new injury or
the reviewed recall cooldown. Other roster identities must remain intact.

Feature cleanup preserves an exact receipt across the window before generic
checkpoint cleanup. Strict compare-and-write persistence prevents an old owner
from overwriting a newer claim. The shared station attempt counter covers both
modes and cannot be refunded after a persisted return. Duplicate unsent callbacks
are idempotent only for their exact saved receipt.

## Verification and current limit

`test_recall_transactions.py`, `test_native_recall_controller.py` and
`test_recall_runtime.py` exercise actual Luau modules. The composed regression
uses Territory Module, AutomationRuntime, Broker, NativeDispatchAdapter and strict
Checkpoint together: one invocation, pending reply, exact status settlement,
newer Sync, confirmed outcome, no generic record, consumed allowance retained.
Tests also cover absent native binding, restored ownership, stable duplicate
names, changed identities, defense and attempt bounds, unknown-request custody,
and tab enrichment occurring before accounting proofs.

Live read diagnostics also identified three prerequisite defects, each with an
offline regression before repair. District catalogs store display city names,
while map calls require the existing CityMaps ID; both map request selection and
Stationing catalog proof now use that reviewed mapping. Family capacity's
`checkedAt` is a native ordering marker (observed in milliseconds), so Watch no
longer compares it to the seconds-valued Sync clock. Finally, district and fort
reads are eligible only when their exact current map exists. A new Sync clearing
the map does not count as a failed native district call or create exponential
backoff. The real reader/budget/coordinator regression obtains both proofs across
repeated five-second Syncs without weakening snapshot attachment checks.

The feature is ready for the manager's serialized, bounded live mutation test.
This document does not claim that mutation has already passed. The separate
[residence comparison review](residency-comparison-review-2026-11-06.md) describes
the supported selected, same-kind comparison and its explicit limits.
