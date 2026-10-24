# Offline purchase-funding coordinator

Status 2026-10-21: pure coordinator, optional runtime integration and
focused/full fake-broker tests complete. See [funding evidence](../m2-funding-coordinator.md).
Native adapters and live ordering remain open.

Purpose-specific withdrawal now accepts an adapter-provided funding
request but cannot derive one from implemented purchase planners. The
coordinator should derive one only when `withdraw`, the originating
feature and its current catalog/state are enabled, and the ordinary
planner has no affordable proposal. It must not grant cash or run a
purchase itself.

1. For Operations, call the existing planner on actual cash first;
   if it has no proposal, retry the same policy with potential cash
   backed by replicated banked funds. For Safehouse, distinguish an
   eligible next tier blocked only by cash from tier/level/cap blockers.
2. Produce a same-account/snapshot funding request with exact required
   carried cash, current purchase action key and purpose. Prefer
   Operations over Safehouse. Never derive for a disabled origin.
3. In `AutomationRuntime`, attach the request to a shallow planning
   snapshot only when the adapter did not supply one, then use that
   snapshot for reader/preflight. Observations can use the raw newer
   Sync; withdrawal evidence allows the request to disappear after
   cash arrives.
4. Verify one shared-broker sequence: insufficient cash → exact
   withdrawal → replicated transfer confirmation → fresh purchase
   proposal. No native transport/live outcome is established.
