# Reviewed development release checklist

This packages the integrated development source. It does not certify all gameplay
outcomes. Keep the [feature matrix](feature-completion-matrix.md) and
[live ledger](live-validation-2026-11-06.md) as the acceptance record. The manager
owns commits, current-client execution and publishing; no pins were changed by
this audit.

Fresh settings have all 55 feature switches off. Runtime mode starts its scheduler
unpaused; an explicitly saved next-launch or autoload profile can enable its saved
choices immediately. Preserve that behavior and do not describe every launch as
paused or all-off. Test a genuinely fresh storage launch separately from profile
autoload and unresolved-action recovery. Never relabel or delete old release
ownership, usage, checkpoints or custody to make a new release start.

## Freeze and commit source S

- Finish reviews, meaningful offline tests, catalog generation, Luau compilation
  and bounded live evidence. Keep private captures, native source, dependency
  bytes, executor files and local build tools ignored. Review the staged file list.
- Run `tools/build_release_manifest.py --preflight`: the audit found 298 unique
  Luau modules; the builder and loader limit is 512. Include every new `src` module.
- Commit the reviewed source, root loader/bootstrap/adapters, tests and public
  documentation on the working branch. Do not update entry pins yet. Record the
  full lowercase 40-character source SHA as **S**. Use a development release
  description rather than claiming every feature is live-complete.

Commands below run from `Roblox/idle-mafia-ember`. Substitute actual reviewed SHAs.
The Git executable must be on PATH for the Python builder's subprocesses. If Git
reports repository ownership, supply this repository's existing scoped
`safe.directory` configuration; do not use a global wildcard.

```powershell
& '..\..\.venv\Scripts\python.exe' tools/build_release_manifest.py --preflight
& '..\..\.venv\Scripts\python.exe' -m pytest -q
git status --short
# Stage only the reviewed public paths, then inspect before committing.
git -c core.autocrlf=false add -- src tests preview/catalog.json tools README.md docs Loader.luau Bootstrap.luau ReleaseAdapters.luau ExecutorEntry.luau
git diff --cached --stat
git diff --cached --check
git commit -m 'Integrate reviewed Idle Mafia development runtime'
$releaseSourceSha = (git rev-parse HEAD).Trim()
```

## Build exact Git blobs and commit manifest M

The builder hashes **committed source bytes** and rejects a different working
source list or any byte mismatch. This Windows checkout has global
`core.autocrlf=true`, no `.gitattributes`, and mixed indexed LF/CRLF files. A clean
Git status alone does not prove byte equality. Do not normalize files after S or
hash PowerShell text output. An isolated checkout with conversion disabled retains
each committed blob exactly, including any intentional CRLF.

```powershell
$releaseExactTree = Join-Path (Get-Location).Path '.private/release-exact'
git -c core.autocrlf=false worktree add --detach $releaseExactTree $releaseSourceSha
$releaseExactProject = Join-Path $releaseExactTree 'idle-mafia-ember'
& '..\..\.venv\Scripts\python.exe' (Join-Path $releaseExactProject 'tools/build_release_manifest.py') --project $releaseExactProject --commit $releaseSourceSha --output (Join-Path $releaseExactProject 'manifest.json')
[IO.File]::WriteAllBytes((Join-Path (Get-Location).Path 'manifest.json'), [IO.File]::ReadAllBytes((Join-Path $releaseExactProject 'manifest.json')))
git -c core.autocrlf=false add -- manifest.json
git diff --cached --stat
git commit -m 'Pin complete development module manifest'
$releaseManifestSha = (git rev-parse HEAD).Trim()
```

The worktree command must fail if its destination already exists; choose a new
private destination rather than overwriting it. M changes only `manifest.json`;
its `releaseCommit` must equal S. Re-running the builder against the exact S
checkout must reproduce the manifest. Never replace S with M inside the manifest.

## Pin entries and commit E

Derive SHA-256 from raw Git blobs, using Python subprocess byte output rather than
PowerShell pipelines or decoded text. Example, with actual S and M substituted:

```powershell
& '..\..\.venv\Scripts\python.exe' -c "import hashlib,subprocess; s='SOURCE_SHA'; m='MANIFEST_SHA'; paths=['Loader.luau','src/loader/Manifest.luau','Bootstrap.luau','ReleaseAdapters.luau','ExecutorEntry.luau']; print('manifest.json',hashlib.sha256(subprocess.check_output(['git','show',m+':idle-mafia-ember/manifest.json'])).hexdigest()); [print(p,hashlib.sha256(subprocess.check_output(['git','show',s+':idle-mafia-ember/'+p])).hexdigest()) for p in paths]"
```

- Set `RuntimeEntry.luau` sourceCommit=S, manifestCommit=M, the manifest blob
  digest from M and all five bootstrap module digests from S. Keep exact-byte
  rejection for the separately reviewed external Ember URL; do not commit its bytes.
- Current reviewed live pins are place `73897506680154`, PlaceVersion **654**,
  native GameVersion **0.26.645.1**, fingerprint
  `7032df7733506f1f80739faca9c9d66d688d6d5a38b2a506b1e8de1fd6c22c78`, and Ember
  `0aebb331911619d0c791de1d0d3e9b2e51ead3fb4472cd038807155ad8bcf412`.
  Re-observe before execution. The observer's canonical fingerprint includes
  PlaceVersion. Although bindings contain reviewed 654/655 layouts, the entry's
  single exact fingerprint supports only its pinned current contract.
- Replace the old Jobs/Bosses-only allowlist with all **55 exact catalog IDs** set
  true. This exposes permissions; it does not enable feature switches or bypass
  prerequisites, evidence, storage ownership or resource guards. Compare the set
  exactly against `preview/catalog.json`, including the four goal/watch features.
- If updating `TestEntry.luau`, give it the same coherent S/M/bootstrap/Ember pins
  while retaining `activateRuntime=false`. Its existing offline test currently
  fetches an older committed 25-page UI; update the fixture dependency digest and
  expected 26 pages only with the coherent new entry. Keep runtime entry integration
  tests separate so an inert smoke test cannot stand in for runtime acceptance.
- Commit only the reviewed entry changes and their packaging regressions as E.
  Recheck every pin against Git blobs, all 55 accessible/off fresh controls, profile
  autoload behavior, hash-tamper rejection, startup ownership and cleanup. The new
  source SHA changes durable release identity: existing account scopes require
  explicit reviewed migration and remain preserved until then.
- Only then publish the authorized branch/PR and verify fetched raw committed
  bytes equal the local blobs. Do not move pins to a mutable branch or claim new
  live outcomes from offline packaging checks. Dependency distribution/hosting
  review remains documented in the Ember dependency review; third-party source
  stays private.

Audit verification: manifest preflight accepted 298 modules; release manifest,
adapters, Bootstrap, old inert entry, full composition and UI checks passed
85 tests and two subtests, with one optional analyzer skip. The integrated full
suite then passed 878 tests and 369 subtests, with one optional skip. These results
precede any new entry pins and do not verify future S/M/E artifacts.
