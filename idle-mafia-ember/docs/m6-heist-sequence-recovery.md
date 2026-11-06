# Heist sequence ownership and recovery

The four ordinary controls now use one current native HeistsTab.act queue.
Reviewed place 654 exposes act at init upvalue 37; place 655 uses 38. The
controller verifies native context, GUI, wrappers, functions and upvalues on
each read and dispatch. It never writes native flags, pending state or the
counter. Unsupported versions or changed identities retire the binding.

HeistTransactions durably records the exact action, baseline and expected next
native sequence before dispatch. A second durable marker precedes entry into
act; act allocates its own counter synchronously. Dispatch rechecks counter
and baseline after storage writes. Start/help/sabotage/collect share this
owner, including the separately enabled Favors page.

Native act polls for up to 120 seconds and can retry its original sequence on
no_pending. Those are the game's native semantics, not an exactly-once
guarantee. The hub does not replay or independently allocate after timeout.
Its request lease can expire earlier; physical busy still gates the global
request scheduler. The durable action and checkpoint uncertainty remain held.
The native success callback records late replies after the lease expires.

Once the native worker is clear, an owned sent record can issue only
HeistAction("status", originalArgument, originalSequence). Numeric row IDs
remain numeric; collect preserves its nil middle argument. Pending,
rate-limit, busy and presence replies keep waiting; no_pending remains
unresolved. Terminal status replies still need action-specific newer state.
No native pending flag is cleared to force progress.

Start requires the exact returned run ID and matching new owned board run.
Help/Sabotage require the same row/owner, exact personal count increment,
Favors debit and durable usage evidence. Collection addresses the native
personal result slot with no invented server result ID. It hashes every
validated scalar field in the complete summary and rechecks that signature,
server day and current native counter after durable writes. Confirmation
requires an exact collected/reward reply and a newer empty personal slot;
disappearance alone cannot confirm it.

Recovery loads the original scoped baseline and saved terminal reply. New
session IDs and reset revisions stay intact; explicit evidence readers never
fabricate headers. Terminal receipts preserve original and observed evidence
through canonical snapshot projection. Restored preparations that never
reached the sending marker are known unsent and fence older writers; sent
or ambiguous actions remain held without replay.

Offline coverage includes changed sources/counters/results, storage refusal,
late callback, timeout, numeric IDs, transient replies, restart and receipt
reload. A private account-sized snapshot produced a reloadable terminal ledger
of about 259 KB without raising any storage limit. Fresh full suite: 778 tests
and 214 subtests passed; one optional analyzer test skipped.

The manager live-verified the place-654 controller and board reads, then ran one
eligible Favor help through public settings with a daily attempt cap of one.
Native sequence 1 returned ok=true, Cash 165000 and XP 183 for heist_vault;
the newer board confirmed the personal help and the checkpoint cleared with
no uncertainty or storage fault. A restart retained the confirmed sequence-1
receipt and consumed daily attempt, with no active action. Start, Collect and Sabotage remain unaccepted live: the
cheapest start needs 25 Energy while this account's maximum is 20, and there
is no current collectible result.
