# Returned result durability — October 28

Broker now persists a current native return through Session/Checkpoint before reporting the return event. `PendingAction` retains that primitive result alongside the original intent/snapshot/baseline, with the same bounded JSON representation. A different later result cannot replace the first; malformed results cannot destroy the baseline. A successful reply is still not action confirmation: the normal feature-specific replicated-state evidence remains required.

Stopped owners and old/deadline-passed callbacks cannot write returned results. Checkpoint serializes commits for the same loaded owner/scope; a yielding file write cannot be interleaved with another save or a scope reload. Known storage conflicts/failures refuse further admission rather than letting an older payload erase a newer action. This does not solve cross-release migration or claim physical invocation cancellation.

Four new tests cover native return persistence/restart without confirmation, malformed result preservation, coroutine/yielding-write fencing and unload/late callbacks. Full **1181 run, 1180 passed, one external official-analyzer skip**, 26.500 seconds. Catalog matches JSON; preflight **270 unique modules**. No MCP, live action, Stamina use, spending, commit or publication; published entry remains `9da6d31`.

Next: feature-specific restart reconciliation using these saved inputs/results; durable usage and actual Crew/Market/recall lifecycle hooks; request highwater, defender/admission ownership; explicit allowance reset/release migration; shared goals. Legacy records with insufficient data stay unresolved; no saved request is replayed by this milestone.
