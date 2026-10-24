# Read-only city Boss stages

`BossStageState` reads a full native Sync and a same-account,
same-snapshot adapter proof of source-derived stage rows and stamina
cost. It uses the saved `BossStages` UTC `%Y%j` day rule for `done`,
keeps keyed remaining HP within the catalog maximum, and marks a
stage unlocked only through `best + 1`, level eligibility and an
uncleared daily slot. Missing or malformed proof stays unknown in the
shared Context. No `BossAction` is sent, and there is no `bosses`
feature descriptor yet.

This is an offline read contract for the next city Boss action slice.
The native catalog adapter, hit-back/resource policy, per-day attempt
accounting, exact mutation evidence and live shape verification remain
open. The saved client source is used as inert requirements data, not
imported at runtime.
