# Free-charge-only Family Takedown attacks

Status 2026-10-21: offline state, planner, evidence, checkpoint and
fake-broker path implemented. 316 Python/Lupa tests, 12 Node tests,
catalog check and changed Luau compilation/analysis pass. Native
adapter/live proof remain open.

Saved `FamilyBossView` sends `FamilyBossAction:InvokeServer("attack")`.
The native action can spend a held Ticket after free charges run out,
so this slice requires **zero Tickets** and at least one current free
charge. Require current week/Family/stage, a complete native snapshot,
known health/stamina and an adapter-supplied conservative stage
hit-back maximum. Keep at least 50% maximum health and native
hospital floor (20) after that bound, plus one stamina in reserve.
Checkpoint at most 25 sent hits per week/Family and five native
seconds between sends; unconfirmed sends count. Confirm only with a
positive reply, newer same-week personal damage increase at least
equal to reply damage, and newer free-use count increase while
Tickets stay zero. No automatic Ticket use or refill.

Tests: eligibility/safety, exact response, restart cap/spacing and
shared fake broker. The current server hit-back calculation,
response and replication remain unverified.
