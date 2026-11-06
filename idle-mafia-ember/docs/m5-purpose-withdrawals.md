# Purpose-specific Bank withdrawals: offline ordinary-action slice

Saved native `0.26.487.1` `BankTab` lines 44–61 and 107–125 sends
`Withdraw:InvokeServer(amount)` and displays replicated `cash` and
`banked`. The client source does not prove server acceptance or
transport behavior.

`WithdrawalState` requires a fresh matching complete Sync and a
same-account, same-snapshot funding request. The offline
`FundingCoordinator` now derives one for an enabled Operation or
Safehouse purchase when cash alone blocks it; a real native adapter
and live ordering are still missing. The request must identify an implemented Operation or
Safehouse purpose, a stable purchase key and required carried cash.
`PurposeWithdrawals` requires the separate OFF-default Bank funding
switch, the originating purpose switch and a user maximum withdrawal
(default 1,000,000). It proposes only `requiredCash - cash`, within
banked balance and cap. No request means no withdrawal; it never
periodically empties the Bank.

`PurposeWithdrawalsEvidence` requires a successful reply plus a newer
complete Sync with exact cash increase and banked decrease. A reply
alone or ambiguous balance change stays pending. Confirmation only
funds the purpose; the purchase must be replanned and confirmed
separately. This module does not create funding requests or purchase
anything. The offline coordinator derives requests from the current
enabled purchase plan and the broker fences them across state changes;
native request/response behavior still requires verification.

The Money panel can show shared fake-broker status. The distributed
inert Ember 0.1.1 bundle remains unchanged. Local evidence: 207
Python/Lupa tests, 12 Node tests, catalog check, new Luau compilation
and both analyzer modes pass. Standalone EmberAdapter analysis retains
existing Roblox-global/local-shadow diagnostics. Native coordinator,
transport, durable storage and live transfer remain unverified.
