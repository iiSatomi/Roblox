# M2 session and checkpoint boundary

The offline session wraps the request broker. `Pause` blocks new proposals and
unsent requests while letting a sent request reach its original 45-second
deadline or receive state-based confirmation. `Stop`/`Close` permanently block
new sends, discard an admitted but unsent owner and release the in-process
initialization guard. A sent owner stays unresolved in the checkpoint.

Before `transport.Send`, the broker calls the injected checkpoint hook. A
failed write prevents the send and exposes `storageFault`. The checkpoint
persists only account/place/release scope, feature, action key and resource
exposure: no raw replies, intent payloads, account state or credentials. It
keeps multiple unresolved records, so another feature's later send cannot
replace an earlier uncertain action. On rejoin with a new session ID, a matching
feature, action key or positive resource exposure remains blocked. Unrelated
resource domains can continue. Confirmed or rejected actions clear a record
only after the broker's action-specific evidence decision; a 45-second skip
keeps the record and logs duplicate risk.

`Checkpoint.new(storage)` expects `Read(key)` and `Write(key, decodedTable)`.
The adapter must make writes atomic and durable before returning, raise or
return `false` on failure, and isolate table mutations. `Load(account, place,
release)` rejects corrupt data. This repository currently uses a fake in-memory
adapter only; no Roblox executor file API, atomic replacement, multi-process
lease or profile migration has been verified. The in-process duplicate guard
does not protect two independent executor VMs. If an adapter cannot meet that
contract, leave sending disabled rather than treating the fake-storage tests
as a production recovery guarantee. A storage fault stays visible and blocks
further work for the session.

The remaining integration must attach an adapter and Session to App, prove
account/place/release identity and the real native transport, and inspect the
native AFK refresh flow before adding any idle fallback. No gameplay request
was sent while developing this slice.
