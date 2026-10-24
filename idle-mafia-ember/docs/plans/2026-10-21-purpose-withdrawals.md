# Purpose-specific Bank withdrawals: offline slice

Status 2026-10-21: offline reader, planner, evidence, cap control,
fake-runtime/UI integration and focused/full checks complete. See
[purpose-withdrawal evidence](../m5-purpose-withdrawals.md). A native
purchase coordinator and live outcome remain open.

Saved `0.26.487.1` `BankTab` lines 44–61 and 107–125 sends
`Withdraw:InvokeServer(amount)` and reads `cash`/`banked`.
The recode must not periodically empty the Bank: a future purchase
coordinator will supply a same-snapshot exact shortfall for an enabled
Operation or Safehouse purpose.

1. Require fresh complete balances and a same-account, same-snapshot
   funding request naming an implemented purchase feature, a stable
   purchase ID and required carried cash. Reject stale or malformed
   requests.
2. Require separate `withdraw` opt-in, current originating feature
   opt-in, user maximum withdrawal and enough banked balance. Propose
   only `requiredCash - currentCash`, never full balance.
3. Confirm successful reply plus newer complete Sync with exact banked
   decrease and cash increase. Replan the purchase after confirmation;
   this module never sends its underlying purchase.
4. Integrate fake broker/UI status. No real funding request adapter,
   storage or live transfer exists yet.
