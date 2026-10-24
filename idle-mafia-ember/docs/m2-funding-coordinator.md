# Offline purchase-funding coordinator

`FundingCoordinator` derives a same-snapshot funding request only when
the separate Bank funding switch and an originating ordinary purchase
switch are enabled. For Operations, it first runs the existing planner
with current cash. If no purchase is affordable, it applies the same
policy to potential cash backed by replicated banked funds and asks
only for the selected Operation's exact carried-cash requirement.
For Safehouse, it only considers a next tier that passes level, tier
and cost caps but is blocked by its cash reserve. Operations take
priority. Neither path sends a purchase or a withdrawal.

`AutomationRuntime` optionally calls the coordinator after validating a
fresh context. It adds the derived request to a shallow planning
snapshot for the withdrawal reader and send preflight; it does not
change the supplied snapshot. A later raw Sync confirms the exact
withdrawal transfer, and the purchase planner runs again on new
balances. Existing adapter-provided requests remain accepted under
the reader's same-account/snapshot checks. The coordinator is absent
from the default inert UI build.

Local evidence: 211 Python/Lupa tests, including a shared-broker
withdrawal → confirmation → Safehouse replan scenario, 12 Node tests,
catalog check, changed Luau compilation and both analyzer modes pass.
The sequence is fake-adapter-only. Native Sync, purchase quote,
withdrawal response, durable storage and live ordering remain
unverified. More purchase domains require their own source-backed
coordinator branches.
