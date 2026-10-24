# Bounded background native reads: offline slice

Status: admission/failure logic checked offline; native adapter open.

The shared planner needs current Sync, catalog and auxiliary facts, but
unbounded polling can duplicate reads and let a stalled callback clog
freshness. Add a pure `ReadBudget` admission gate for future native
read adapters. It grants at most one due read per call, one in flight
globally, minimum per-source intervals and a bounded timeout. A
completion token fences late callbacks. Failures/timeouts back off
only the affected source; successful reads resume its normal cadence.

Test fairness across sources, cadence, one-in-flight, timeout/late
completion fencing and failure recovery with the fake monotonic clock.
The budget does not itself call any Roblox API or transport.
