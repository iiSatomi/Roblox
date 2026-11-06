# M2 inert release loader boundary

`Manifest.inspect(manifest)` validates a pinned 40-hex commit, safe relative
`src/*.luau` paths, unique module IDs and paths, dependency lists and acyclic
order before any path is fetched. `Manifest.validate(manifest, bytesByPath,
sha256)` also checks every byte string against its declared 64-hex SHA-256.
The hash provider is injected and trusted; the offline tests use Python's
actual SHA-256. Neither function executes a module.

`Loader.start(fetch, cache, compile, manifest, dependencies)` fetches each
module from `manifest.releaseCommit`, which must equal the bootstrap's
independent `dependencies.expectedCommit` pin before any fetch. It falls back to a matching verified cache
entry, validates the complete set, compiles every module, then executes exports
in dependency order. It calls `App.start` once after all exports exist. A
partial download, wrong hash or compile error starts no module or App. Module
initialization itself must be side-effect-free until App starts; a top-level
execution error can occur after an earlier export has executed. Cache writes
are best effort and never override digest checks. A duplicate call returns the
same live App, another release is rejected, and `Loader.close()` calls App's
destroy hook. A self-closed App with `alive == false` permits a fresh start.

`Bootstrap.start(release, adapters, activateRuntime)` now supplies the independent
commit/version/contract pins, checks the executor SHA-256 against a known answer,
derives account identity from the current player,
checks the place before any loader work, and passes only the reviewed adapters
to `Loader`. Its default is the inert App; the current-client host, automation
and storage require the explicit third argument `true`. A full-source local
integration test loaded all 25 inert tabs through `Bootstrap` and `Loader`.

`ReleaseAdapters.new(commit, api)` now assembles a fixed raw-GitHub fetch path,
commit-scoped local cache and compiler adapter. It accepts only safe `src/*.luau`
paths for the exact 40-hex commit, bounds each response to 1 MB and reads back
cache writes. The Loader remains responsible for checking each SHA-256 before
module execution. A local full-release test fetched and cached all 211 modules,
then started the same inert 25-tab App from the verified cache with HTTP
unavailable. The actual executor HTTP and file primitives have not been used
through this release adapter in the current client.

`ExecutorEntry.start(release, services, activateRuntime)` joins the reviewed
bootstrap, release adapters, Loader and executor primitives without embedding
credentials or a moving URL. The full local test starts the inert App through
this entry after the cache-only restart. The entry module is source code, not
yet a packaged executable release: the final committed manifest, pinned Ember
distribution and executor-side packaging remain to be prepared.
With HTTP unavailable, corrupting one cached module makes the Loader reject
the complete startup before App creation.

The source is **not a runnable remote release**. No production `manifest.json`
exists. `tools/build_release_manifest.py --commit <full-sha>` is prepared to
create one after the recode is committed; it refuses uncommitted, missing or
extra Luau source. The current executor's hash, timer and file primitives were
validated read-only, but the release adapters have not run as a complete App
in the client. A reviewed Manifest validator
and Ember dependency still need to be supplied. Ember distribution terms and
single-version module hosting remain unresolved. No gameplay call was involved
in these loader tests.
