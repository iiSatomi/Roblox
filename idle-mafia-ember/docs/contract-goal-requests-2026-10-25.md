# Contract goal requests — Task 09 checkpoint

The saved `Config.CONTRACTS.TEMPLATES` source in
`imports/idle-mafia-2026-10-11-full/Config-2dc705424c27.lua` defines
`jobs` as completed Jobs, `energy` as energy spent on Jobs, and `ops`
as **finished Operations collected**. The latter is a count, not an
Operation duration goal. The `playtime` key measures passive time in
seconds even where the UI description says minutes.

**Code/UI and local request-production slice complete; the
`autoContracts` feature remains C/T incomplete until Task 24 shared
execution, and L is pending.** Separate default-off choices govern
borrowing Jobs, Operation starts and Operation collection. Both Operation
choices must be on to create an `ops` request. A request carries the
account/session/release, catalog, period, row ID/index, reset identity,
current progress, remaining amount and permitted routes. Its observer
reports progress only from a newer same-row, same-reset snapshot; it
sends no remote. The existing feature descriptor remains blocked until
Task 24 can arbitrate these requests with manual settings and the one
account request owner.

Current template keys and request coverage:

| Key | Request status |
| --- | --- |
| `jobs`, `energy` | Jobs route with separate explicit borrowing. |
| `ops` | Start + collect route with both borrowing choices; progress measured at collection. |
| `playtime` | Passive wait; no action request. |
| `banked`, `bosshits`, `crates`, `donatecash`, `fightwins`, `heisthelps`, `heistsabos`, `heiststarts`, `hires`, `ladder`, `properties`, `shopbuys`, `siegeswings`, `trades` | No goal request until the exact eligible native effect, safety scope and progress proof are established. Ordinary claim or tab switches do not grant borrowing. |

Independent Contract entry and bonus claim paths are locally complete:
App/native-adapter tests sent `ContractAction("claim", 1, nil)` and then
`ContractAction("claimbonus", nil, nil)`, each with its own newer full-Sync
marker in the same reset. The focused Contract suite passed 19 tests.
Actual claim rewards and current-client outcomes remain unverified.

For live acceptance, observe an enabled, incomplete Contract with row ID,
progress, goal and reset from a current full Sync. Run one ordinary action
under explicit borrowing and record its native reply and next full Sync;
the exact same row must progress before the request can count it. For
entry/bonus claims, record each exact call/reply and next marker separately.
