# Local UI prototype — first implementation slice

Authorized 2026-10-20 by the user's request to start, update from the supplied save, test UI locally and simplify menus. This slice implements a design preview only; actual Ember and gameplay adapters follow separately.

## Files and interfaces

- `preview/catalog.json`: page/feature labels, policy choices, optional Custom control descriptions and simulated limits. Every legacy feature ID appears once; no raw game source/account data.
- `preview/model.mjs`: `createState(features)`, `setEnabled(state,id,on)`, `setPolicy(state,id,value)`, `applyValues(state,values)`, `pause(state)`, `resume(state)`, `stop(state)`, `featureStatus(state,feature)`. All return local state/results and have no transport, timers, storage or browser dependencies.
- `preview/app.mjs`: DOM rendering and local event bindings only.
- `preview/index.html`, `preview/styles.css`: accessible layout with 25 dedicated system tabs, persistent simulated-data notice, concise status, normal controls and bounded Custom disclosures.
- `tests/preview-model.test.mjs`: Node's built-in test runner, meaningful false-value, stop-latch, policy validation, external ownership, resource wait and feature coverage, dedicated-tab ownership, exclusive gear strategies and conflicting-profile cases.

## Ordered tasks

1. Write model tests, run `node --test idle-mafia-ember/tests/preview-model.test.mjs` and confirm failure because the new model is missing.
2. Implement only the small immutable state model needed by those tests; rerun the same command. No game/network adapter is present.
3. Add the compact catalog and static browser view; validate IDs against the 50-ID parity section and enforce Custom field count <=6.
4. Serve only `preview/` on `127.0.0.1`, inspect it through the browser, and exercise Combat/Properties, search, Custom and stop behavior. Inspect narrow/wide wrapping and console errors where available. Save actual preview screenshots.
5. Document tested behavior and remaining actual Ember/native gates; update the roadmap and publish only reviewed recode files.

Success is a usable local design/debug tool with source-backed feature labels, simpler menus and proven local control behavior. It is not a working Roblox automation release or a pixel-exact Ember emulator.
