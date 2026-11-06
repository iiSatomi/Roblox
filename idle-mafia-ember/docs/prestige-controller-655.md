# Prestige controller verification — November 6, 2026

The missing controller binding was caused by the exact `PlaceVersion == 648`
requirement. The connected client is place `73897506680154`, version `655`
(native version label `0.26.646.1`). The native Prestige controller's init,
open, and FightTab confirmation upvalue layout remains the reviewed layout.
The binding accepts explicitly reviewed place versions `654` and `655`;
unsupported versions and changed native identities still fail closed. After a
server transfer to 654, normalized PrestigeModal/Prestige rules source matched
655. FightTab differed only in decompiled local layout; the same identity
diagnostic passed. Each controller retains its captured place version.

Private decompilation review confirmed that PrestigeModal checks native
eligibility, opens the native confirmation dialog, sets its busy flag, and
invokes the linked `PrestigeAction` with the single argument `"prestige"`.
The native eligibility function uses the configured maximum rank and next
rank level. FightTab still owns the shared confirmation callback; a pending
callback or any open modal prevents controller-clear proof.

SHA-256 of the private review artifacts, including the decompiler header:

| Artifact | SHA-256 |
| --- | --- |
| PrestigeModal | `fb0725b47ea2e4d0160fcd343f5dee01f45686bf4b8a4bf89dbe89e74d66e6b5` |
| Prestige rules | `ac6e4f4a03ac39262deb60299da072d26466cb4b73a10123a51d9b4b39effa1b` |
| FightTab | `710237ccb3e2270ecf047b93fc27c1b41f3f9d6600fd88a9a91554476db65429` |

Native source artifacts remain private and are not part of this change.

The manager ran the read-only identity diagnostic on the connected client.
All identity groups passed, including native State/Config/player context,
init/open/confirmation relationships, GUI ancestry, and the linked remote.
The updated production binding returned `Current() == true` and:

```text
rank=1, level=92, xp=6984, ready=false
controllersClear=true, busy=false, confirmationPending=false, modalOpen=false
```

The live thresholds were `200,200,200,210,220,230`, maximum rank `6`.
An actual reset was not eligible: rank 1 requires level 200. No reset request
was sent. The binding is live-verified as an observer; a successful server
reset outcome remains unverified until the account meets its prerequisite.

The new version-655 behavioral regression initially failed because the
controller was nil. After the narrow version update, the focused controller,
binding, and Prestige suites passed: 15 tests and 29 subtests. Coverage includes
unknown versions, busy/pending/visible modal arbitration, changed identities,
wrapper replacement, close/retirement, reset permission and attempt limits,
capture revalidation, exact success/rejection evidence, and restart recovery.
