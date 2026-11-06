# Market state-only recovery — October 28

The actual Black Market tab now observes its loaded transaction store during snapshot enrichment, once per current scope/session/revision/time. It calls the existing exact-custody `MarketTransactions:Reconcile` route; it never submits, resumes or replays a saved command. Prepared/ambiguous records stay held. Exact terminal rental/listing outcomes can become observed and release their reservations; observed buy/withdraw intermediates keep their intended output until the remaining continuation hooks are complete.

The actual all-tab RuntimeAssembly scenario now saves a rental, marks its sent state, verifies unchanged state stays sent/held, supplies the exact newer duration plus loose-Gold debit, then proves the store becomes observed and the hold disappears while all feature settings remain off. The fake native transport records zero gameplay calls. Existing store cases cover exact listing/buy/withdraw reconciliation, restart and intermediate custody.

Full **1181 run, 1180 passed, one external official-analyzer skip**, 26.702 seconds. Catalog matches JSON; **270 unique modules**; full scoped tracked diff and new recovery-file whitespace checks pass. No Roblox/Potassium MCP, live action, Stamina use, spending, commit or publication; published entry remains `9da6d31`.

This connects Market's existing state-recovery path to the runtime lifecycle. Generic checkpoint reconciliation, durable trade budgets, request/continuation ownership, pre-send/direct-emission hooks and trading acceptance remain unfinished. All current-release L remains pending. Continue the authoritative Task 24 queue; preserve saved uncertain actions and do not infer a server cancellation from scheduler expiry.
