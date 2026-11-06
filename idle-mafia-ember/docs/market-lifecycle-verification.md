# Market lifecycle verification — November 6, 2026

New behavioral coverage exercises current BlackMarket tab modules, owned
research caches, transaction owners and the ordinary engine/broker/adapter
path. These are offline tests, not live trade acceptance.

- Sell: bounded loose-item listing, exact newer owned listing and item debit,
  persistent attempt limit, separately owned withdrawal output and continuation.
- Flip: researched foreign listing, quoted ordinary Gold purchase, exact acquired
  copy hold, fresh resale research, only that copy listed, independent buy/list
  limits and retained bought-copy custody after rejection.
- Rent: one quoted period, exact Gold/expiry evidence, restart, attempt/spend
  persistence and known-unsent rollback without refunding a saved reply.
- Manage: exact earnings-to-Gold transfer, numbered durable payout, idempotent
  replay of accounting only, restart, stale writers and write/corruption failures.

The composed tests include ResourceReservations and real tab reservation
sources. Tests use the broker's one-second spacing between purchase and listing;
no pacing guard is bypassed. Separate transaction tests cover changed custody,
source/generation mismatch, persistence refusal and pending-return holds.

Failing regressions exposed two outcome-ordering defects: rental allowances
could be refunded after a saved pending reply, and transient negative Rent/payout
replies could become terminal rejection. Both now retain custody/attempts until
their own exact outcome is known.

Current private place-654 MarketTab review confirmed absent loose/bound Gold
keys mean zero. Rental quote/evidence now preserve that native behavior while
rejecting malformed present values. Artifact SHA-256:
`78ac7b0cc68c0fc66cd98de75eeec3e2bc4da96f289bb02a6f0d07abb1e05f3b`.
Native source remains private.

Current native Config quotes one Gold per twelve hours. One bounded live rental
returned success, extended the lease by the quoted period and debited one bound
Gold while leaving loose Gold unchanged. The original action stayed pending
under its earlier loose-only evidence rule. Reviewed evidence now requires both
pools to be non-increasing, their combined debit to equal the quote and the
lease expiry to fall within the observed processing interval. No debit priority
is assumed. Rental custody reserves total Gold and checks the public total-Gold
reserve against other held funds and both item origins.
Where another action holds a specific Gold origin, that pool must independently
cover the full rental quote plus its held copies; a richer other pool cannot
justify spending those copies.

The original durable pending record and a genuinely complete newer native Sync
confirm through the revised evidence and runtime recovery in offline replay,
including a new runtime session. The record, action key, saved baseline, original
origin-specific custody and charged allowance require no migration. A normal
live restart then reconciled the original saved rental: pending and uncertainty
counts became zero, storage stayed healthy and the original one attempt/one
Gold charge remained. No new rental was sent and no pending record was manually
cleared.

Focused files: test_market_sell_runtime.py, test_market_transaction_lifecycle.py,
test_market_rent_lifecycle.py, test_market_payout_ledger.py and
test_market_recovery_projection.py and test_market_strict_writes.py. Fresh full
suite after these changes: 874 tests and 369 subtests passed; one optional
analyzer test skipped.
