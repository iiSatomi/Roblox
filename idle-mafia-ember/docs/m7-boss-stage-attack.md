# Ordinary city Boss attacks: offline slice

The saved `BossTab` uses `BossAction:InvokeServer("stageAttack",
stage)` for a manual hit. The separate `bosses` descriptor now
prefers the next uncleared stage (`best + 1`) and falls back to the
lowest eligible daily repeat. It requires a source-backed stage row,
native auto-run inactivity, level/unlock/day eligibility, one stamina
held after the hit, and health remaining at least 50% of maximum
after the stage's worst hit-back. Paid `stageAuto` is untouched.

The shared checkpoint atomically records sent Boss hits and stamina
with each unresolved action before the fake transport dispatches.
Conservative limits are 100 hits and 100 stamina per native UTC
`%Y%j` day, plus five native-server seconds between Boss sends. An
unconfirmed send still consumes this count. A newer day resets it;
caller-provided usage counts are discarded in the shared runtime.
These are local protections, not claims about server rate limits.

Preflight repeats the selected stage, quote, native auto state,
health/stamina and daily proof. A positive reply needs a newer
same-account snapshot showing the selected stage's HP fall or a
fresh daily clear. The local count alone never confirms server
success. Missing evidence follows the common 45-second unconfirmed
skip/cooldown, with duplicate risk. Production atomic storage,
cross-process ownership, current native catalog/response shape and
live server behavior remain unverified.

Offline evidence: 269 Python/Lupa tests, 12 Node tests, catalog
check, changed Luau compilation and both analyzer modes pass. The
default Ember 0.1.1 script is still inert.
