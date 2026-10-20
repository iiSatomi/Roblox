# Local design preview

This is a browser design/debug tool, not Ember executing outside Roblox and not a runnable gameplay hub.

Open `standalone.html` locally for a self-contained preview. No server, packages, internet access, account files or game bridge are needed. All controls affect simulated in-memory choices only. The file is source when viewed on GitHub; this repository has not been deployed as a website.

Maintained files are `index.html`, `styles.css`, `app.mjs`, `model.mjs` and `catalog.json`. Regenerate the standalone artifact from the Roblox workspace root:

```powershell
node idle-mafia-ember/tools/build_preview.mjs
node --test idle-mafia-ember/tests/preview-model.test.mjs
```

Try the sample choices, Combat permission/policy, Properties goal/Custom limits, feature search, Pause/Resume, Emergency Stop/F8 and sample situations. Scenarios explain low health, native Auto Jobs ownership, closed Market and unconfirmed requests. They are not a gameplay simulator or proof of native formulas.

Nine local model/schema tests pass. Automated visual testing is still unverified: this environment's browser security policy blocks local URL/file navigation. Actual Ember rendering/scaling, pointer/focus, respawn and cleanup need a separate inert Roblox check later.
