# Family, Event Shop and Territory contract audit — November 6, 2026

The prior tests exercised fallback blockers for these conditional features.
`tests/test_conditional_feature_contracts.py` now runs the actual source readers,
planners, evidence, call descriptions, and durable Checkpoint/PendingAction
implementation using deterministic native-shaped fixtures. No game remote or
account write is performed by these tests. This is offline evidence; live
outcomes belong to the manager's single-client test queue.

## Fixed defects

- Residency evidence accepted `{ok = true, pending = true}` as confirmed if a
  newer matching lease was visible. It now keeps nonterminal replies pending,
  including saved-reply reconciliation. The regression first returned confirmed
  where pending was required, then passed after the change.
- `Checkpoint:Resolve(actionKey, "schedule_failed")` refunded Family and Event
  Shop allowances even after `RecordReply` had persisted a server return. Those
  branches now require a decodable saved attempt with no reply before returning
  the charge. Tests first demonstrated both refunds after a pending reply; the
  corrected path refuses resolution and preserves both record and exposure.
  Legitimate known-unsent refunds still work. This matches existing protections
  for stationing and residency attempts.
- Family durable usage accepted impossible counters: one attempt with zero
  exposure, two attempts with exposure one, and exposure with zero attempts.
  Each contribution charges at least one unit. `copy` and `copyCharge` now reject
  these histories, consistent with Event Shop's existing invariant. Red/green
  tests separately demonstrated the invalid usage and invalid charge acceptance.

## Covered current contracts

- All three Family lanes require the current personally attributable member
  counter, exact owned-resource debit, matching Family/account identity and
  independently bounded attempted/spent usage. Stamina tests cover completing
  a perk level and its progress reset; foreign personal receipts remain pending.
  Unknown usage, mixed ordinary/bound Gold and uncertain Cash exposure block
  planning. Family call descriptions preserve the native four-argument arity.
- Event Shop uses the real `NativeEventShopSource` and buyer together. Tests
  cover exactly earned/bound Medal debit plus acquired item custody, insufficient
  acquisition, unrelated inventory mutation, paid Medal rejection, source closure,
  current-attribute rechecking, and saved-attempt recovery across a new session.
  A foreign account cannot reconcile an old acquisition.
- Stationing selects one stable `healId`, reserves a distinct home defender,
  checks current owned district/map/capacity and bounded attempts, and confirms
  only the selected identity's duty. Reserved home defenders, unidentified
  deployments and pending deployment capacity block planning. The emitted native
  call remains `TerritoryAction("station", districtId, memberSlot, nil)`.
- Residency verifies selected terms, rent/share limits, explicit replacement and
  owner-request permissions, exact new active lease and terminal reply. Recovery
  in a new session requires a newer server clock; absent/newer local revision
  alone is insufficient.
- Real Checkpoint save/reply/resolve/reload tests prove that Family, Event Shop,
  station and residency attempts survive removal of a resolved action record.
  Reusing a stale original allowance cannot admit another attempt.

## Remaining unmet controls and live prerequisites

- The later [Recall integration review](territory-recall-review-2026-11-06.md)
  supersedes the original missing-owner finding: the Territory descriptor now
  wraps ordinary Stationing with the durable Recall owner. The lower-level
  Stationing planner still refuses Recall when used without that owner. Native
  reader binding and composed offline tests have passed; the bounded live
  mutation outcome remains the manager's responsibility.
- The later [residence comparison review](residency-comparison-review-2026-11-06.md)
  supersedes the missing comparison finding. One selected candidate is compared
  against current native resident contribution, rent and bonus caps. Different
  bonus kinds and unverified tradeoffs are refused; there is no all-district
  ranking, fabricated combined total, or automatic rollback.
- Family actions still need live membership, personally attributable info and
  affordable independent allowance; Stamina also needs a nonmaxed selected perk.
  Stationing needs an owned unshielded district with capacity and safe home Crew.
  Residency needs current matching admission terms and a qualifying selected
  district. Event Shop needs active native shop attributes, a currently supported
  offer and earned Medals. Missing prerequisites remain unverified.
- No current live spend/outcome was observed in this workstream. Native shapes
  were checked against the manager's privately saved current FamilyTab/Config
  evidence, while live source validation remains manager-owned.

## Verification

Fresh focused command covering conditional contracts, the standalone anti-idle
helper, and existing engine sessions: **48 passed, 14 subtests passed**. The
conditional module alone contributes 14 tests and 14 subtests; anti-idle has nine
tests. The broader concurrent suite snapshot had 696 passes, one optional analyzer
skip and 158 subtests, with five failures from Heist tests whose new implementation
was being written and one stale historical war UI blocker assertion. Those
parallel-work failures were reported to their owners; this is not a full-suite
green claim.
