# Family Takedown: read-only weekly state

`FamilyTakedownState` accepts a complete native snapshot and an
account/capture-matched current `FamilyBossAction("state")` result
from a future adapter. It validates the exact week/Family/stage,
current reset time, personal damage, held Tickets, bounded exact
week/stage unexpired claim records and native free-charge fields.
It computes regenerated free charges using the saved
client's `nextFreeAt`/`freeRegen` rule against native `serverNow`.
An optional `Context` reader exposes this view or an unknown reason.
Claims are informational in this slice.

This does not invoke `FamilyBossAction`. A later attack must require
an actual free charge and separately guard health, stamina and
exact weekly/stage evidence, so held Tickets cannot be consumed by
the automation. Claims need a separate exact week/stage path. The
current server response and replica shapes remain unverified.

Missing claim expiry leaves that row informational and out of the
unexpired claim list. Offline evidence: 303 Python/Lupa tests, 12 Node tests, catalog
check, changed Luau compilation and analysis pass. Registry remains
21 fake-adapter descriptors; default Ember 0.1.1 remains inert.
