# Existing-member Group bonus: offline slice

Saved client `PropsTab` checks `player:IsInGroup(Config.GROUP.id)` near line
190, shows an unclaimed banner while replicated `groupBonus` is false around
lines 201–206 and 2577, and calls `ClaimGroupBonus:InvokeServer()` without
arguments near line 2702. `Config.GROUP.id` is current configuration, not a
hard-coded permission bypass. Client behavior cannot prove server acceptance.

1. Add failing tests for complete fresh Sync, explicit false `groupBonus`,
   matching recent membership proof, and malformed/missing evidence.
2. Add a separately enabled, no-resource proposal for the existing member.
   Do not join the group or treat a visible claim button as membership.
3. Require successful reply plus newer complete Sync with `groupBonus=true`.
   A reply alone or a mismatched group/session remains pending.
4. Wire the shared fake runtime/App status, run local checks and document
   source and live limits. Keep the distributed inert bundle unchanged.

No actual group membership lookup or game request runs in this offline slice;
the future adapter must supply the fresh membership proof.

**Status:** Four offline tasks implemented and focused tests pass. Native
membership lookup, transport, actual claim and packaging are open.
