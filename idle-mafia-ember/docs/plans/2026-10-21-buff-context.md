# Effective buff context: offline slice

Status: implemented and checked offline; native/live proof remains open.

Saved native `GlobalBuffKinds` chooses the maximum of global, decree
and daily effects for each key; its daily schedule comes from
`DailyBuffRules`. The initial reader will accept adapter-supplied,
same-snapshot global/decree expiry and daily-window proof, including
the current native daily ID. It will calculate source, strength and
expiry for Operations, mastery, Boss damage and other supported keys.

1. Reject missing account, snapshot, clock, current daily window or
   invalid buff fields. Do not guess a missing daily rotation.
2. Use native-key defaults, 2x global and personal XP, decree XP 1.25x,
   daily values from the saved native pool, and maximum rather than
   multiplication. At equal strength retain the later known expiry.
3. Attach optional read-only buff view to shared Context, test expiry,
   overlap and malformed proof, then document live verification gaps.

No routine will depend on this context until a current native adapter
can supply validated proof.
