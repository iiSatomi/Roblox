# Ordinary Favor help: offline slice — implemented locally

Saved client `HeistsTab` calls `HeistAction("help", row.id,
localSequence)` and renders `favorsLeft`, `helpFavorCost`,
`helpEnergyCost`, `helpMaxPerHeist`, `helpCashCap`, row relationship
flags and per-player `helpsUsed` (falling back to `helped`). The
recode's separate Favors switch will require a current unqueried
board, an exact row ID, eligible level, active expiry, no prior
sabotage on that row, enough Favors and energy after reserves, and a
same-account native-day usage proof from the checkpoint's fake-storage
tested write-ahead count.
Sent attempts, including unconfirmed ones, consume the daily cap;
the checkpoint updates that proof atomically with the unresolved
action before dispatch. A production atomic storage adapter remains open.

The simplified UI has Best reward, Highest tier and Custom policies
but has not yet exposed the legacy relationship and reserve controls.
Use the legacy defaults (Friends & family, five helps/day, five Favors
and ten energy to keep) until the settings mapping is finished. Best
reward ranks positive cash then XP; Highest tier ranks catalog level.
Custom uses the same eligible pool and best-reward ranking for now.

Confirmation requires a positive reply plus a newer same-account
board where the selected row's personal helpsUsed rises by exactly
one and favorsLeft falls by the current cost. Missing rows or an
unconfirmed reply remain pending under the shared 45-second rule.
No Favor refill or Gold spend is part of this slice.

Implemented in `FavorsState`, `FavorHelp`, `FavorHelpEvidence`,
`Checkpoint` and the shared runtime proof injection. The registry
has a separate `favors` descriptor. See `../m6-favor-help.md` for
limits and test evidence.
