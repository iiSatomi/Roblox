# Offline feature registry and composition

`FeatureRegistry` now lists the 25 implemented offline descriptors in
one order: personal Heist starts, ordinary Favor help,
separate sabotage, Jobs,
city Boss attacks, selected Boss Shop purchases, ordinary Global Boss attacks, settled Global Boss
claims, free-charge Family Takedown attacks and current-week stage
claims,
Operation start/collection, Skills, Group bonus,
Monthly claim, two earned trophies, Playtime, Contract entries/bonuses,
free Briefcase picks, Bank deposits, Safehouse upgrades,
purpose-specific withdrawals, ordinary no-slot Property builds and
sold Market earnings collection. Each entry names a reader,
planner and evidence export. `requirements()` returns a copy of those
names for release assembly. `build(exports, catalog)` checks every
method and matching UI feature ID, rejecting missing/duplicate entries
without returning a partial descriptor array. The shared fake-runtime
integration test now loads and composes through this registry.

The registry does not fetch code, read Roblox state, construct a
transport or start automation. A future manifest may use its module
names, but a production release still needs reviewed dependency hashes,
native snapshots, durable storage and live request validation. The
current local result is in the shared handoff. Default Ember 0.1.1
remains inert.
