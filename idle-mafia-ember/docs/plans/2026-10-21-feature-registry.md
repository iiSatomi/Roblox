# Offline feature registry and composition

Status 2026-10-21: registry, integration replacement and checks
complete. See [composition evidence](../m2-feature-registry.md).
Release manifest/native adapters remain open.

`AutomationRuntime` accepts an injected descriptor array. The current
fake integration test constructs it manually, so each new reader/planner/
evidence slice can be omitted from a future release without a failure.
The release loader already exports each module under a manifest ID.

1. Define one ordered registry of the implemented offline feature IDs
   and their reader/planner/evidence export names. Do not import or
   execute any game service here.
2. Validate that each ID occurs once, each export implements its method,
   and each ID has a matching UI catalog switch. Fail atomically if a
   required piece is absent; no partial descriptor array.
3. Replace the fake integration test's hand-written descriptor list
   with registry construction, and test missing exports/duplicate UI
   IDs. Keep the default App inert and production packaging deferred.
