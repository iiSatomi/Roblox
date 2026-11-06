# Black Market durable sale flows implementation plan

> **For agentic workers:** Use the executing-plans workflow to implement this tightly coupled batch in order. The user selected one GPT-6.1 Sol subagent at high reasoning. Track steps here; the parent reviews the resulting implementation and verification before closure.

**Goal:** Complete an offline, durable withdrawal-to-list and buy-to-list transaction lifecycle that survives restart without replaying an uncertain mutation.

**Architecture:** Extend the existing tab-owned transaction store and evidence modules, keeping native call dispatch unchanged. Derive follow-up listing inputs from the stored baseline plus fresh observed custody, pass them through existing sale/flip preflights, and persist the next listing stage before it could ever be sent. This is one implementation batch within master Task 17; current-client reads, reservations and runtime dispatch remain explicit Task 24 integration dependencies.

**Tech Stack:** Luau modules and Python unittest/Lupa fixtures already in the release worktree.

## Global constraints

- Work in `C:/Users/asato/.codex/worktrees/idle-mafia-release/Roblox/idle-mafia-ember`.
- Read primary workspace `skills/idle-mafia-hub/SKILL.md` and `docs/AGENT_HANDOFF.md` first.
- Preserve unrelated dirty files. No commits, GitHub updates, MCP, live client actions, Gold spending or Stamina use in this batch.
- All feature defaults stay off; do not modify autoload behavior.
- `MarketCallPlan` continues to reject buy/list/rent. No remote execution belongs in these components.
- One account/place/release-scoped active transaction. Persist before advancing. Uncertain sends remain unresolved and cannot be automatically replayed.
- Preserve the existing storage key and existing rent/list records. Do not silently discard pending data or rename its key without migration.
- State evidence establishes an observed result, not unique attribution to our remote. The future runtime still needs the single mutation owner and shared reservations.
- Keep the existing one-second spacing and 45-second broker deadline unchanged. This non-sending durable store does not own broker timing.
- Keep code modular. If transaction validation/state transitions make the existing store unwieldy, extract a focused tab-local module and update explicit require maps in tests.

## Baseline and file responsibilities

- `src/tabs/blackMarket/MarketTransactions.luau`: durable rent/list baseline, prepared/sent/observed lifecycle, account isolation; extend to withdrawal/buy and next-stage listing.
- `MarketCollectionWithdrawEvidence.luau`: exact base-item transfer, unchanged bound/variant/Gold custody and Collection checkpoint.
- `MarketBuyEvidence.luau`: exact loose Gold debit/item increment, unchanged bound custody and owned listings.
- `MarketListEvidence.luau`: exact single new listing and item debit; reuse for second-stage listing.
- `MarketSellListPreflight.luau` / `MarketFlipListPreflight.luau`: fresh custody, quote, shop slots/expiry and net/margin checks; keep these the decision gate.
- `src/tabs/blackMarket/Module.luau`: inject evidence/preflight modules through the tab factory, with no independent scheduler.
- `tests/test_market_transactions.py`: existing seven rent/list scenarios; retain them.
- Create `tests/test_market_transaction_flows.py`: complete local lifecycle with real preflight/evidence/store modules and injected persistence.
- Extend `tests/test_market_collection_withdraw.py`, `tests/test_market_buy_evidence.py`, `tests/test_market_list_evidence.py` where the evidence interface changes.
- Update explicit dependency maps in `tests/test_simple_tab_modules.py` and `tests/test_all_tab_composition.py` only if required.
- Update this plan, `docs/m7-black-market-checkpoint.md`, the master plan and primary `docs/AGENT_HANDOFF.md` with measured results and remaining scope.

## Batch A — durable two-stage sales

### 1. State-only observations with restart ordering

- [x] Add `observe(baseline, after) -> boolean` to withdrawal and buy evidence. Capture finite nonnegative native `serverNow`; require full Sync, same account/place/release, and a valid session. Within one session require a higher revision; across sessions require a strictly newer server timestamp. Never compare reset local revisions across sessions.
- [x] Preserve ordinary `evaluate(...)` reply requirements. State-only observation must not turn missing/rejected/rate-limited replies into ordinary broker confirmation. For withdrawal observe exact loose `+quantity`, collected `-quantity`, unchanged bound/variant/Gold balances, and checkpoint floor. For buy observe exact loose Gold `-price`, item `+1`, unchanged bound balances and owned listings.
- [x] Add failing tests before implementation: same timestamp after restart fails; newer timestamp with local revision reset passes only with all exact deltas; changed bound/variant or extra debit fails; malformed timestamps fail. Reuse actual fixtures rather than string-matching code.

```python
# Shape of restart assertion in the existing Harness fixtures:
after.session = "restarted-session"
after.revision = 0
after.native.serverNow = baseline.serverNow + 1
self.assertTrue(evidence.observe(baseline, after))
after.native.serverNow = baseline.serverNow
self.assertFalse(evidence.observe(baseline, after))
```

### 2. Persist withdrawal and purchase stages

- [x] Extend the factory compatibly: `new(storage, scope, listEvidence, withdrawEvidence, buyEvidence)`. Existing callers using three arguments continue to work. `Module:NewTransactions` supplies all three evidence modules.
- [x] Add `PrepareWithdraw(proposal, before)` and `PrepareBuy(proposal, before)` returning `boolean, reason`. Use real evidence capture, enforce preflight-only feature/kind and scope, and persist the exact baseline plus intended listing quantity/price/source listing. Reject any active transaction and invalid or overlarge persisted records.
- [x] Reuse `MarkSending()` for the prepared first stage. `Reconcile(raw)` observes exact withdrawal/buy custody, persists the observed intermediate stage and records the confirming server time. Repeated reconciliation is idempotent. A storage failure never advances the in-memory record.
- [x] Deep-copy nested baseline/listing/variant maps on persistence and `Active()`. Bound lengths/counts/numbers when recovering records. Missing evidence, corrupt data, wrong scope, failed persistence and ambiguous deltas cannot clear or advance a transaction.
- [x] Preserve rent/list behavior and old storage data. `ClearObserved()` must refuse observed intermediate withdrawal/buy records so callers cannot accidentally discard custody before listing.

```python
self.assertTrue(tx.PrepareBuy(tx, proposal, before)[0])
self.assertTrue(tx.MarkSending(tx)[0])
restarted, reason = module.new(storage, scope, listing, withdraw, buy)
self.assertIsNone(reason)
self.assertFalse(restarted.PrepareBuy(restarted, proposal, before)[0])
self.assertEqual(restarted.Reconcile(restarted, ambiguous)[0], "uncertain")
self.assertEqual(restarted.Reconcile(restarted, exact)[0], "observed")
self.assertFalse(restarted.ClearObserved(restarted)[0])
```

### 3. Fresh follow-up preflight and durable listing transition

- [x] Add `ListingContext(raw, now) -> txView?, reason`. It returns the exact existing preflight shape, derived solely from the persisted intermediate transaction and freshly revalidated exact custody. Withdrawal view: stage `withdrawn`, itemId, withdrawnQuantity, plannedQuantity, beforeLoose/beforeBound/beforeCollected, checkpointFloor, confirmedRevision/confirmedAt, listAttempts. Buy view: stage `bought`, itemId, sourceListingId, buyPrice, beforeLoose, boundBefore, confirmedRevision/confirmedAt, listAttempts. Include current session/account/place/release.
- [x] Use current-session revision and injected local `now` only after a fresh full Sync proves custody; use persisted server time to bound recovery age to the existing 3600-second preflight window. Include local snapshot age (maximum 15 seconds), reject captures more than one second in the future, and permit bounded negative rebased `confirmedAt` after a local clock reset in both preflights. Repeated calls or restarts must not renew this age indefinitely. Reject server-time regression, stale observation, wrong item and changed custody.
- [x] Feed the view through the real `MarketSellListPreflight.assess` or `MarketFlipListPreflight.assess` with current custody/quote/listings/terms/settings. Do not synthesize a successful quote or skip margin, shop-expiry, slot, protected-copy or attempt checks.
- [x] Add `PrepareFollowupList(proposal, before, now) -> boolean, reason`. Require explicit finite current local `now` and a fresh `ListingContext` snapshot binding; reject delayed or backwards-clock preparation. Accept only the matching preflight-only listing for the active observed intermediate record: exact feature, item, quantity, original intended ask and withdrawal/purchase identity. Capture current list baseline with `MarketListEvidence`. Persist a prepared list record retaining its origin and attempt count, then require `MarkSending` before `Reconcile` can observe a listing. An arbitrary prepared/running/uncertain first stage cannot be bypassed.
- [x] Permit clearing only the final observed listing. Ambiguous or rejected-looking state remains held; this batch adds no automatic retry or release of uncertain custody.

```python
view, reason = restarted.ListingContext(restarted, fresh, now)
self.assertIsNone(reason)
listing_proposal, reason = preflight.assess(
    view, custody, quote, listings, terms, settings, now)
self.assertIsNone(reason)
self.assertTrue(restarted.PrepareFollowupList(
    restarted, listing_proposal, fresh, now)[0])
self.assertTrue(restarted.MarkSending(restarted)[0])
again, reason = module.new(storage, scope, listing, withdraw, buy)
self.assertEqual(again.Reconcile(again, exact_listed)[0], "observed")
self.assertTrue(again.ClearObserved(again)[0])
```

### 4. Integration scenarios and verification

- [x] Test both full flows with actual tab factory, transaction store, preflight and evidence modules. Restart after first send, after observation, and after list send. Assert zero transport calls; this batch has no send path.
- [x] Cover changed ask/quantity/source listing, shop expiration/full slots, depleted margin, bound/Collection changes, stale quote, clock/session reset, corrupt persisted maps, persistence failure at each transition and attempts to start a second transaction. Confirm original rent/owned-list cases still pass.
- [x] Run focused tests and fix failures:

```powershell
$env:PYTHONPATH='C:\Users\asato\AppData\Local\Temp\idle-mafia-lupa;C:\Users\asato\.codex\worktrees\idle-mafia-release\Roblox\idle-mafia-ember\tests'
python -B -m unittest test_market_transactions test_market_transaction_flows test_market_collection_withdraw test_market_buy_evidence test_market_list_evidence test_market_sell_list_preflight test_market_flip_list_preflight test_simple_tab_modules test_all_tab_composition
```

- [x] Run the full suite once after focused checks pass, then UI and manifest checks. Request shell escalation for Git-backed fixtures if required; do not bypass tests. Report actual run/pass/skip totals separately.

```powershell
python -B -m unittest discover -s tests -p 'test_*.py'
python -B tools/build_ui_prototype.py --check
python -B tools/build_release_manifest.py --preflight
git diff --check -- idle-mafia-ember/src/tabs/blackMarket idle-mafia-ember/tests idle-mafia-ember/docs/plans
```

- [x] Update evidence and plan checkboxes only after checks. Explain that this completes durable offline lifecycle components while Market runtime reads/reservations, remaining settings and dispatch remain unfinished. Next action remains master Task 17 tab-local settings/wiring, then Task 18 under the missing-fact rule.
- [x] Parent review: inspect scope isolation, record validation/deep copies, cross-session age checks, unchanged ordinary reply requirements and zero new dispatch. Address substantive findings and rerun affected tests before calling the batch complete.

## Execution record

- Baseline: 878 tests ran, one skipped; 242 modules scanned. No fresh run claimed by plan creation.
- Plan reviewed against existing preflight field names and evidence interfaces on October 26. No new game remote or argument contract is assumed.
- Status: implemented by the requested Sol 6.1/high subagent and reviewed by the parent; durable offline components only. No commits, publication, MCP or live actions.
- Red/green evidence: six new state-observation tests failed for missing `observe`, then passed. Durable-flow tests failed for missing preparation methods before implementation. Additional failing regressions covered negative local epochs, delayed preparation, nil rental snapshots and pending/rate-limited ordinary replies.
- Final focused command above: **73 run, 73 passed, zero skipped**. Final full command above: **904 run, 903 passed, one skipped** (`Ran 904 tests in 24.609s`, `OK (skipped=1)`). Full verification used shell escalation for Git-backed fixtures, without changing those tests.
- UI: `Luau catalog matches JSON`. Manifest: `Scanned 242 Luau modules; IDs are unique`. Scoped diff/whitespace checks passed. Both complete flows use the real tab factory, listing reader, preflight/evidence/store modules and injected storage, with zero transport calls.
- Parent review identified local-epoch rebasing and delayed-preparation freshness issues; both are fixed and regression-tested. Follow-up preparation now takes explicit current `now`, includes snapshot age in elapsed native age, and preserves the original intended ask. This signature/age clarification is recorded above. No extra dependency modules were introduced; schema/copy helpers remain local to the compatible store factory.
- Remaining scope: Task 17 tab-local configuration/wiring, fresh runtime readers and research presentation, Task 24 read/item reservation ownership, trade dispatch and current-client L. Whole-Market C/T is still unfinished. Continue Task 17, then Task 18 under the missing-fact rule.
