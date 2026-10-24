# Account-scoped profile storage: offline slice — implemented locally

The Ember prototype currently stages and reapplies one profile in
memory. Add a separate `ProfileStore` around an injected atomic
`Read/Write` adapter. Scope records by account and place, accept only
bounded profile names and scalar schema-1 values approved by the
current Settings model, cap saved profiles, and return copies.

Reading a saved profile must never activate features or resume the
runtime. The App can preview and deliberately apply a selected
profile through its existing paused `ApplyProfile` path in a later UI
slice. A corrupt read, failed write or wrong-scope record must fail
closed without overwriting the current model. Keep storage contents
local; no executor-specific filesystem call or account data is
committed in source.

Tests cover account/place separation, rejected fields, copies,
capacity, failed I/O and read-only load. This is fake atomic storage
evidence, not a production executor persistence claim.

An opt-in App/Profiles UI bridge is also implemented and tested:
Save, Preview and separate paused Apply. The default 0.1.1 bundle
is unchanged. See `../m1-profile-store.md`.
