# Feature-first execution policy

Approved direction: user requested faster completion with less waste, October 28, 2026.
This file controls execution order and work discipline. Existing technical acceptance and safety requirements remain in force. The old master plan supplies specifications, not a second work queue.

## Resume in under one focused read pass

Read the current shared handoff section, this file, and [todo.md](todo.md). Then open only the active feature's technical specification, relevant modules and focused tests. Use targeted searches rather than reading the entire historical handoff. Reuse the existing source references. Do not repeat the inventory or re-audit completed tabs unless new evidence requires it.

## Work rules

1. One active feature and one owning tab. Finish its settings -> current data -> planner -> dispatch -> exact effect -> required recovery -> disable/unload path. No placeholder-only switch counts as delivery.
2. Build the smallest complete supported behavior first, then remaining promised variants within that tab. Partial scope must stay visible; do not mark a whole control complete while a required variant is omitted. MarketSell includes its optional withdrawal/list continuation.
3. Reuse existing readers, planners, evidence, stores and broker hooks. Add shared infrastructure only for a demonstrated failing acceptance case in the active feature. Record the case in todo before broadening scope. Fix concrete correctness defects when found; do not strip protections to improve counts.
4. No speculative refactors, generic frameworks, redesigns, extra audits or new milestone documents. Track unrelated improvements under Deferred. Keep modules owned by their tab; do not consolidate into a huge script.
5. A concrete external/source blocker gets one recorded item: missing fact, exact sources checked, smallest needed observation, and work still possible offline. After that, complete independent work in the same tab; move tabs only when remaining work genuinely depends on that fact. Revisit only with new evidence. Difficulty or unfamiliar code is not an external blocker.
6. Code directly by default following the completed delegation pilot and subsequent user discussion. Subagents require a specific useful independent assignment; do not duplicate implementation/review or reopen the manager experiment routinely.
7. Do not use remaining quota as a work objective. Continue useful requested implementation; do not loop, retest or generate documentation to consume allowance.

## Verification proportional to the change

- For gameplay behavior, add/reproduce the focused failing acceptance case before changing it. Verify actual App/descriptor and fake native adapter behavior, not only helper functions or a successful reply.
- During iteration run the affected feature suites. Test success, relevant rejection/stale input, changed custody/limits, disable/unload, and uncertain-send/restart behavior appropriate to that action. Reuse shared contract tests rather than duplicating them in every feature.
- Run the full suite after changes to shared contracts/engine/storage or at tab closure, and at final packaging. A genuine new failure may require additional runs. Do not repeat a passing full suite for documentation-only changes.
- Run catalog checks when settings/UI catalog change; manifest preflight when imports/modules change. Document-only edits need link/count/format checks.
- Obtain source documentation when an API-dependent change requires it; do not repeatedly fetch unchanged docs for plain internal logic.

## Definition of local feature acceptance

All three must be true:
1. Actual runtime wiring performs the advertised bounded behavior with explicit configuration and current source-derived inputs.
2. Exact effect and applicable resource/custody/uncertainty/recovery/disable cases pass meaningful integration tests; no fabricated server facts.
3. UI availability and remaining limits agree with implementation; update the existing inventory row with evidence.

Local, shared-integration, packaged and live milestones remain separate. Count each of 55 controls once. Never infer an overall completion percentage from tests, modules or partial tasks. Starting baseline is 23 Local / 22 Partial / 10 Blocked; no feature credit for this workflow setup.

## Small checkpoints, not a second project

At a meaningful feature milestone update todo's current checkpoint in place (behavior changed, test result, exact next action). Update inventory Markdown/JSON and the wiring ledger only when a feature status or material remaining requirement changes. Update the shared handoff's current execution section in place, at most six bullets; do not append another long milestone history. Technical specs change only if their contract changed. Do not copy the same full narrative across five files.

Progress reports: named delivered behavior; feature count delta (or explicitly no count change); one concrete next step/blocker. Never promise a feature per turn or guaranteed speed/usage savings.

## Constraints retained

Current continuation: the user approved finishing the remaining work and cleared the NativeClientBindings transfer; its read-only check passed. The specifically approved one-Heist test costing10,000 game Cash/25 Energy was sent exactly once. A matching native run and daily-start decrement were observed, but the original record remains held after its server/controller changed. That old allowance remains consumed. A separate explicit approval on2026-11-04 authorizes exactly one additional Corner Store start (10000 Cash/25 Energy) and only its collection; the new start and its collection are confirmed under their durable one-use guard. Read-only completed-receipt recovery accepted the exact saved reward custody after a server change; both sends are consumed. A separate current approval authorizes exactly one Friend/Family Favor help capped at1 Favor/8 Energy, followed only by result reads; no Cash, Stamina, items, start, collection or replay. This Favor was sent once and confirmed; its allowance is consumed, with durable pending0/attempted1. Evidence is in docs/native-server-transfer-2026-11-04.json. The separately approved Rare Capo Strongbox purchase was sent exactly once and confirmed after the current UI-context corrections: one crate granted, exact75000000 carried-Cash debit in the correlated native snapshot, zero pending. A fresh on-disk Checkpoint read confirms attempted1/spent75000000/pending0; its one-use approval is consumed. No Bank withdrawal or crate opening occurred. Current evidence is in docs/native-shop-acceptance-2026-11-04.json. The separately approved Rafael slot14 Recall was sent once and confirmed; that approval is consumed. Neither approval authorizes replay or clearing the old unknown action. Latest user approval supersedes the prior Bank restriction: carried and Bank Cash, Heist/Operation collection and necessary completion tests are authorized. Preserve uncertain custody, native manual challenges, held tests and publication gates. Latest steering: the user confirms new daily rewards are ready and puts Prestige plus active-War/Family-less tests on hold. The one free Cash ladder fact check completed: one native tier4/60minute claim, positive reply/marker and correlated Cash increase observed; no spending. The reply lacks an exact Cash amount, so general income-Cash automation remains guarded. The one-use marker is consumed; keep the user-held tests out of the executable queue. The local/connected log review corrected the44 response-only entries: they are read-only board/info/state refreshes, not missing mutation outcomes. No44 original transaction receipts are required; actual older-release custody/usage migration remains separate and no unknowns are cleared. The current Shop test remains a single purchase with no crate opening or replay. Current status is in tasks/todo.md and docs/native-runtime-acceptance-2026-11-04.json. The bounded BossStages.get inspection completed. Native Heist sequence/lifecycle/result ownership is implemented locally; one current start/collection is accepted, while broader mixed gameplay and historical reconciliation remain. Native challenges, custody and source-evidence requirements remain.

User authorized read-only Potassium inspection for the remaining implementation on November 1, 2026, including Combat, Heists, Recall, reward contracts and executor storage capability/path metadata. The user separately authorized a couple of ordinary Combat test attacks; two were completed November 1 and are documented in docs/native-combat-live-2026-11-01.json. That bounded test does not authorize ongoing automation, additional attacks, scouts, war actions, hooks, resets, purchases or publication. Other live gameplay/Stamina restrictions remain. No live spending or gameplay during offline work. Respect actual entitlement and manual challenge handling; no fake ownership/answer automation. All-off defaults; explicit custom autoload allowed. One logical active request, one-second minimum and quarter-second planning. At first send +45 seconds record skipped/unconfirmed with duplicate risk and cooldown; never call it server cancellation. Preserve uncertain custody, stable identities and origin separation. Live sensitive actions retain their exact consent requirements.

No routine GitHub maintenance during feature work. Packaging/publication is an explicit final work item with a tested pinned entry and availability list, not silently omitted. Existing entry permits only Jobs/city Bosses.

## Resume coordinates and observed usage corrections

Use the existing release checkout `C:/Users/asato/.codex/worktrees/idle-mafia-release/Roblox`; the primary workspace Ember directory is older. Do not rediscover this path every turn. If absent, inspect `git worktree list --porcelain` once.

Run Python from its `idle-mafia-ember` directory. Set `PYTHONPATH` to `C:/Users/asato/OneDrive/Documents/ChatGPT/Roblox/.local-deps` and use `C:/Users/asato/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`. Focused command: `-m unittest discover -s tests -p 'test_market_sell_runtime.py'`. Full command: `-m unittest discover -s tests -p 'test_*.py'`.

Official Luau0.745 is now available locally and verified against its release SHA256; set `LUAU_ANALYZE=C:/Users/asato/OneDrive/Documents/ChatGPT/Roblox/.local-deps/luau-0.745/luau-analyze.exe` for these same test commands so the existing App/wrapper analyzer check runs in both solver generations. Provenance: `artifacts/luau-0.745-provenance.json`. This adds a verification prerequisite, not a new execution queue.

Observed waste: oversized historical handoff/status output, wrong-checkout searches, failed test invocations caused by import paths, repeated full-suite runs for local feature edits, and appending new checkpoint bullets without removing superseded claims. Use bounded reads, these known coordinates, focused iteration, and replace the checkpoint in place. Do not rerun tests for this documentation-only correction. This assessment is qualitative from visible execution; no token-cost attribution was measured.
