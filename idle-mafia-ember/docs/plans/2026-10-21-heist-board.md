# Read-only personal Heist board: offline slice

Status: reader implemented and checked offline; mutations remain open.

Saved native `HeistsTab` reads `HeistAction:InvokeServer("board")`,
then renders `mine`, `result`, `rows`, `startsLeft` and `bustWait`.
The UI's mutation wrapper sends a local sequence to `start`, `status`
and `collect`; a hub cannot borrow that counter or infer server
acceptance from it. Its result renderer uses `heistId` but shows no
unique result key. First build a read-only board view that accepts a
full, account-labelled board response and current Sync. It will
distinguish idle, active, settling, result and ambiguous states,
validate a concrete mine ID and known heist type, and leave result
collection unaddressable until exact identity/reconciliation evidence
is established. No Heist mutation is authorized by this reader.

Test matching account/session, stale/queried/incomplete boards,
result-vs-mine ambiguity and valid active/settling states. Keep
Heist request dispatch and sequence ownership for later live review.
