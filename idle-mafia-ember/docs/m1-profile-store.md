# Account-scoped profiles: offline slice

`ProfileStore` validates schema-1 scalar settings through the current
Settings model and persists at most 16 named profiles under an
account/place-scoped key. It accepts an injected atomic decoded-table
`Read/Write` adapter; no executor filesystem implementation or
account data is included in source. Malformed, wrong-scope or
unreadable stores fail closed. Loading returns a copy and does not
change current controls or resume automation.

When a `ProfileStore` module, storage adapter and account identity
are injected into `App`, the Profiles tab exposes a name field,
Save locally and Preview saved profile. Preview stages the saved
profile; the existing Apply staged choices command validates it,
updates controls and leaves the app paused. The default shipped
0.1.1 prototype has no storage injection and keeps its original
memory-only controls. Executor storage capabilities, multi-process
ownership, migrations and actual UI interaction remain unverified.

The shared runtime now publishes its registered feature IDs in
status. Ember status rows use that map, so new descriptors show
their broker wait/confirmation reason while unsupported switches
continue to say UI only.
