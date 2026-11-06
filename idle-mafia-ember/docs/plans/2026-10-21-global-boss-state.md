# Global Boss event state: read-only offline slice — implemented locally

The saved `GlobalBossTab` uses the current event `id_startAt` as a
run key, matches native `gb.run` for personal damage/hits/claimed,
and calls `GlobalBossAction("attack")` or `("claim")` separately.
`GlobalBossRules.isLive` requires status live, current time within
start/end, and positive HP after time decay plus recorded damage.
Private test events require an exact local user ID; results have a
seven-day grace window.

Add an account/snapshot-labelled read-only event proof and optional
shared Context view. Validate full native Sync, local user ID,
event identity/times/HP/damage/status and personal run matching.
Expose live/pending/settling/done, access, remaining HP and claimable
facts without guessing an action. Wrong-run personal state must not
create participation. No remote call or descriptor in this slice.

Test status transitions, private access, time decay, wrong-run
participation, result grace and malformed proof. Actual event shape,
native adapters and live outcome remain unverified.

Implemented in `GlobalBossState` and optional shared `Context`
injection. See `../m7-global-boss-state.md`.
