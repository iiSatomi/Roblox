# Completion execution plan — November 6, 2026

Baseline: merged source `30cf3832142a0cf32802273ea962808e76a4ceda`,
published entry `8d7ecb9fa26f308c91b426e03b71acdefadce734`.
The user authorized continued coding and in-game testing through Potassium.

## Responsibilities

- Manager: current-client evidence, all live execution, integration, independent
  reviews, release verification and progress reports roughly every ten minutes.
- Storage agent: reviewed migration of nonempty saved state, preserving unresolved
  actions, original evidence, counters, allowances and receipts; offline tests first.
- Feature agent: Family, Prestige, War, Event and Collection gaps, native contracts
  and focused regression tests. Coordinate changes to shared modules.
- Runtime agent: all 55 control acceptance rows, remaining runtime/UI integration
  gaps, and executable test recipes for Crew, Market, Heist, Territory and economy.

Only the manager runs live scripts, preventing simultaneous native actions.
Agents use Sol 6.1 high and share this checkout; no overlapping file ownership.

## Execution order

1. Inventory every control and distinguish implementation, offline verification,
   historical live evidence, current-release live evidence and unavailable cases.
2. Implement and test nonempty cross-release migration. Keep original snapshots;
   carry unresolved actions and usage forward without inventing settlement evidence.
3. Start the merged runtime with all controls off, inspect actual native availability,
   and verify pause, stop, unload and reload before bounded gameplay cases.
4. Test available features individually with explicit settings and bounded attempts.
   Check the native response and authoritative resulting state, plus durable reload.
   Diagnose failures before changing code. Then test shared-resource interactions.
5. Cover events and prerequisites when available; record exact missing facts for
   cases that cannot run. An unavailable event does not count as successful gameplay.
6. Review changes independently, run relevant regressions and the final full suite,
   compile Luau, rebuild exact Git-byte release pins, publish and smoke-test.

## Completion accounting

Historical live baseline is 19/55 controls (35%), compared with 0/55 at the start
of recovery. A UI load or a passing unit test does not add live-confirmed controls.
The acceptance ledger records broader case coverage separately; 100% completion
requires every control's intended behavior and applicable recovery paths to pass.
Keep external prerequisites explicit instead of lowering the completion criteria.

Current first dependency: canonical saved Operation has a successful reply but an
unresolved outcome and held Cash. Preserve it during migration; do not replay or
clear it merely to start the new runtime. Other stored usage also remains binding.
