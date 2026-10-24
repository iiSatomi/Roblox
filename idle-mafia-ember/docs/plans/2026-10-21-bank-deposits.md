# Guarded cash bank deposits: offline slice

Status 2026-10-21: offline reader, planner, evidence, two UI limits,
fake-runtime/UI integration and focused/full checks complete. See
[Bank deposit evidence](../m5-bank-deposits.md). Native savings adapter
and live server outcome remain open.

Saved `0.26.487.1` `BankTab` lines 24–40 and 79–98 sends
`BankDeposit:InvokeServer(amount)` and shows reply `kept`/`fee`.
Lines 175–178 display `cash`, `banked` and the native no-fee derived
benefit; current `Config.BANK.depositFee` is 10%. The server outcome
and rounding remain unverified. The old hub defaulted to a 10,000
deposit threshold and zero explicit cash-to-keep.

1. Add explicit threshold and cash-to-keep controls; require a fresh
   full Sync, current fee metadata and adapter-supplied same-snapshot
   purchase savings. Never bank reserved or uncertain cash.
2. Propose one exact integer excess amount through the shared broker.
   The expected fee is display metadata only; do not treat it as an
   accepted server quote or grant no-fee entitlement.
3. Require successful reply with internally consistent `kept` and
   `fee`, then newer full Sync showing exact cash decrease and banked
   increase. A reply alone stays pending.
4. Integrate fake runtime/UI status and verify. Purpose-specific
   withdrawals remain a separate feature.
