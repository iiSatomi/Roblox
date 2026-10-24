# Guarded Bank deposits: offline ordinary-action slice

Saved native `0.26.487.1` `BankTab` lines 24–40 and 79–98 sends
`BankDeposit:InvokeServer(amount)` and reads reply `kept`/`fee`.
Lines 175–178 displays replicated `cash`, `banked` and the derived
`noBankFees` entitlement. Current `Config.BANK.depositFee` is 10%.
The actual server validation and rounding are not visible in the
client source.

`BankState` requires a fresh matching complete Sync, valid balances,
current fee metadata, known no-fee status and adapter-supplied purchase
savings tied to the same account and snapshot. The Bank panel adds a
minimum excess amount (default 10,000) and explicit cash-to-keep
(default zero). `BankDeposits` preserves the greater of that keep
amount, purchase savings and current reservations, then excludes
uncertain cash. It proposes one exact integer excess amount through
the shared fake broker. The expected fee rate is display metadata,
not a server quote or a way to grant fee exemption.

`BankDepositsEvidence` requires a successful reply with nonnegative
`fee`, positive `kept`, `fee + kept == amount`, and a newer complete
Sync with exact cash decrease and banked increase. It also requires
zero reported fee when native no-fee was present. A reply alone or
ambiguous concurrent balance change stays pending. Withdrawals remain
separate and require an enabled purchase purpose; this slice never
withdraws money.

The Bank panel can show fake-broker status. The distributed inert Ember
0.1.1 bundle remains unchanged. Local evidence: 193 Python/Lupa tests,
12 Node tests, catalog-generation check, new Luau compilation and both
analyzer modes pass. Standalone EmberAdapter analysis retains existing
Roblox-global/local-shadow diagnostics; the new controls use its
existing numeric Input path. The savings adapter, true bank response
shape, native transport, durable storage and live outcome remain open.
