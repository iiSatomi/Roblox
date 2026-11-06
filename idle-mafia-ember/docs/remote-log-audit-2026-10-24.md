# October 24 Cobalt remote-log audit

Source: the user-supplied `2026-10-24T18_49_47Z.log` (1.64 GB). This is a
passive client trace, not server code or permission to replay calls. Generated
code and session identifiers in the log were treated as data and were not run
or copied into this project. Counts below are outgoing call headers in the
captured interval, not completed gameplay outcomes.

| Area | Captured calls | What the trace establishes | Remaining gate |
| --- | ---: | --- | --- |
| Jobs | `DoJob` 4 | One native call carried the client wrapper's first argument; three executor-origin calls from `NativeRemoteResolver.luau` sent only `j_oldharbor`. All four replies contained `ok=true`. The Sync immediately before/after each executor call shows `j_oldharbor` completions 77→78, 78→79, and 79→80. | This verifies those three ordinary Job completions in the captured client session. Preserve the direct resolver path; other Job IDs and later game versions still need their own evidence. |
| Heists/Favors | `HeistAction` 5 | Four `board` reads and one `ledger` call; the board reply has `ok=true` and rows. The saved Heists UI routes `ledger` through its sequence/status loop. | No captured start, collect, help, or sabotage mutation. Keep them blocked until durable sequence allocation, status recovery and exact result identity are proven. The board read may be staged separately. |
| Operations | `StartOperation` 0, `CollectOperation` 0 | No wire evidence for starting or collecting an Operation in this interval. | Recheck live current-slot identity and exact replies before enabling either send. The separate current-client state probe found a 23-entry catalog and three active entries; it was not an action trace. |
| Shop and Bank | `BuyShopItem` 3, `BankDeposit` 3 | Native Shop calls used item ID, explicit nil quantity, and a quoted cash amount; all six replies contained `ok=true`. Post-purchase Syncs show the selected items newly owned and marked in `shopRotation.bought`. Three deposit Syncs show cash decreasing and banked balance increasing. Current Sync omits `shopBought` and carries fractional cash and banked balances. | Current rotation, stock, quote and cash-reserve proofs remain required. No executor-origin Shop/Bank call was captured. Shop reader/evidence were corrected locally for the observed optional `shopBought`, fractional cash, and exact rotation-plus-item grant. Bank deposit/withdrawal and savings/funding paths were corrected locally for fractional balances and integer outgoing amounts. |
| Crew and Collection | `CrewAction` 3, `AutoEquipCrew` 1, `UnequipAllCrew` 1, `CollectionAction` 3 | Crew samples cover sort and training; Collection samples cover `depositall` and `withdrawall`. Their replies contained `ok=true`. | Bulk custody and gear protection must be checked before any automation. This trace does not authorize bulk deposit/withdraw or establish exact state changes. |
| Inventory | `OpenCrate` 11 | Native crate-opening replies contained `ok=true`. | No executor test, item-custody proof or approval for irreversible inventory use. |
| Family and Territory | `FamilyAction` 20; `TerritoryAction` 346 | Family calls include 14 `info` and six `contribute`. Territory calls include 310 `alerts`, 23 `attack`, six `fortview`, three `fortrepair`, three `fortenergy`, and one `stationall`. | Shared spending and war/stamina actions remain blocked. The user is in a Territory war and requested no stamina use. Do not replay these calls. |
| Bosses and player fights | `FamilyBossAction` 32; `Attack` 2 | Family Boss calls include 31 state reads and one attack; no ordinary `BossAction("stageAttack")` was captured. | Boss and player/war outcomes remain unverified for the recode; do not test stamina actions during the war. |

Other captured names include `GetHitList`, `MailAction`, `SeasonAction`,
`ResidencyAction`, `PlayerProfile`, and ambient Sync/tick/notification events.
An `ok=true` reply alone is a call result, not proof that saved account state
advanced. The Job and selected Shop/Bank claims above additionally use
before/after Sync evidence. The trace cannot show server-side validation
logic or confirm calls that were not made.

Implementation consequence: the new tab-local `BoardReadRuntime.luau` can
queue the observed read-only Heist board call under `ReadBudget`, and accepts
its reply only against the originating full Sync. It is offline-tested but
not connected to the published App or release manifest. Heist mutations and
all other newly mentioned sends remain gated. The Shop correction is also
offline-tested and is not in the published runtime. Next: connect the Heist
read lane to the shared lifecycle without changing the gameplay allowlist,
then obtain focused action/result evidence for Operations before enabling
its sends. The Bank balance correction is offline-tested; no recode Bank
action was sent, and the trace contains no purpose-withdrawal call.
