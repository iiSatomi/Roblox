# Existing-member Group bonus: offline claim slice

Saved client `0.26.487.1` `PropsTab` checks
`player:IsInGroup(Config.GROUP.id)` around line 190, treats replicated
`groupBonus` as the claimed flag around lines 201–206 and 2577, and sends
`ClaimGroupBonus:InvokeServer()` without arguments around line 2702. The
current `Config.GROUP.id` is 674050067. These are client facts, not a server
validation or observed accepted claim.

`GroupBonusState` requires a matching fresh complete Sync, explicit unclaimed
flag, current group config and a separate recent account/group membership
proof. The future adapter must perform and timestamp that check; the module
never prompts a join. `GroupBonus` is separately enabled and emits a
no-resource claim proposal. `GroupBonusEvidence` requires a successful reply
and newer complete Sync with the same group's claimed flag true. It does not
infer an income change or claim success from a reply alone.

The shared fake-adapter broker and Ember Group bonus panel expose wait and
outcome state in local tests. Actual membership lookup, native transport,
server response, income effect and production bundle are unverified. The
distributed 0.1.1 script remains inert. This slice is covered by synthetic
state and fake transport, not a live claim.
