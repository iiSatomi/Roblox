# Separate Heist sabotage: offline slice

The saved client calls `HeistAction:InvokeServer("sabotage",
row.id, sequence)` through its mutation queue. The new `sabotage`
descriptor preserves the original string or numeric row ID and
requires an explicit local player ID proof. It excludes self,
friends and Family, then checks level, expiry, zero personal helps,
the per-run sabotage cap, native Favor/energy costs and reserves.
It is a separate opt-in switch and leaves sequence allocation to a
future verified native adapter.

The checkpoint atomically records sent sabotage attempts with the
unresolved action. It caps them at five per native board day and
keeps five Favors and ten energy under the temporary legacy defaults.
An unconfirmed send still consumes an attempt. The shared runtime
derives the day from the board, injects the checkpoint count and
discards caller-supplied counts. Production atomic executor storage
and cross-process ownership are not available yet.

Preflight repeats the exact row, owner, local identity, relationship,
catalog level, usage and resource checks. A positive reply only
confirms with a newer same-account board showing one additional
personal sabotage on the same row/owner and the exact Favor debit.
Missing evidence follows the 45-second unconfirmed skip/cooldown.
No paid controller, Favor refill or Gold spend is involved.

Offline evidence: 276 Python/Lupa tests, 12 Node tests, catalog
check, changed Luau compilation and both analyzer modes pass. The
default Ember 0.1.1 bundle is inert; no real sabotage was sent.
