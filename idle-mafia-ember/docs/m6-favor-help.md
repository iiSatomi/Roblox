# Ordinary Favor help: offline slice

Saved client source calls `HeistAction:InvokeServer("help", row.id,
sequence)` through its queued mutation helper. The new `favors`
descriptor selects an eligible current board row with its original
string or numeric ID. It requires a friend or Family relationship,
eligible level, unexpired run, no personal sabotage, a remaining
per-run help slot, and Favor/energy reserves. Best reward ranks capped
cash then XP; Highest tier ranks level. Custom currently shares the
Best reward ranking because the simplified UI has no Favor-specific
Custom inputs. The temporary legacy defaults are five attempts per
native day, five Favors and ten energy held in reserve.

The checkpoint now stores the native-day sent-attempt count in the
same atomic write as the unresolved action. It increments before
transport dispatch, so an unconfirmed send, exception or restart does
not silently restore a daily attempt. A newer native day starts at
zero. The shared runtime derives the day from the current unqueried
Heist board and injects the checkpoint count; caller-provided usage
counts are discarded. Actual executor storage still needs an atomic
adapter and cross-process ownership, so this is fake-storage evidence,
not a live durable guarantee.

Preflight rechecks the exact row, day count, native costs, per-run cap,
relationship and resource reserves. Confirmation needs a positive
reply and newer same-account board with the same row owner, the
personal help count increased by one and the exact Favor debit. The
checkpoint count is a local send guard, not server success proof.
Missing or ambiguous evidence remains pending under the shared
45-second unconfirmed policy. No Favor refill or Gold purchase is sent.

Current offline evidence: 257 Python/Lupa tests, 12 Node tests,
catalog check, changed Luau compilation and both analyzer modes.
There is no production native transport or live confirmation.
