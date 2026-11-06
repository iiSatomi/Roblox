# Rewards effect evidence gap — 2026-10-25

> October 28 implementation supersedes the historical gap below: Group's actual income modifier is now bound and tested; fixed Ladder awards/refills/fresh XP/mystery and source-enabled Monthly effects require both the exact marker and actual effect. The required tab module skips unsupported Cash/active-XP rows without starving other earned rewards. See [current Rewards checkpoint](m16-reward-effects.md). Income-based Cash and active XP extension still need exact rules; saved Monthly remains disabled. All current-release L results are pending.

> October 27 complete-source recheck: `DailyRewards-88e624cc4b74.lua` now supplies calendar/rung resolution, mystery pool and reward descriptions. More importantly, Group is an income modifier: current `Config.GROUP.incomeBonus = 0.1`, and `PropsTab-250649ceb95a.lua:133` explicitly multiplies property income by `1 + Config.GROUP.incomeBonus` when `native.groupBonus` is true. Its `ClaimGroupBonus()` call is at line 2425. Do not require an invented immediate Cash/item award for Group completion. Next implementation should bind the source-backed income modifier and the exact claimed flag to its test/availability claim; do not promote C/T solely from this documentation note. Playtime variable prize origin/effects and disabled Monthly still need their own reviewed contracts. No new current-client outcome is claimed.

> October 27: re-audit this gap against the complete `imports/idle-mafia-2026-10-27-all-sources/` manifest, including `DailyRewards` and all reward/config helpers. The earlier `*-full` export was filtered. Do not infer absence from that export or ask for more source before checking the recovered definitions. No complete reward-effect or live confirmation is newly claimed by this note.

Task 07's App → native adapter wiring and exact claim-marker checks pass
offline for Playtime, Group bonus and a synthetic enabled monthly config.
These markers establish a recorded claim, but the implementation does not
yet prove each awarded resource or item. **Task 07 C/T remain incomplete;
all three L statuses remain pending.**

Sources checked: the saved client calls and reward definitions summarized
in `m4-playtime.md`, `m4-group-claim.md` and `m4-monthly-claim.md`; the
supplied remote-log audit in `remote-log-audit-2026-10-25.md`; and the
current `PlaytimeEvidence`, `GroupBonusEvidence` and
`MonthlyRewardsEvidence` modules. The remote log records `ClaimLadder(2)`
with `ok=true`, but no matching before/after full Sync or prize payload.
The saved monthly config is disabled. No trustworthy group-bonus resource
delta or complete per-kind Playtime award response contract was found in
those sources.

Smallest observations needed later, one claim at a time and only when
eligible: a current full Sync with all relevant balances, pools, buffs,
inventory and claimed markers; exact native claim arguments and reply;
then the next full Sync with the matching marker plus the actual resource,
item or buff change. For Monthly, first observe a current client with the
feature enabled in native config; do not force-enable it in the live game.
If the prize is variable or applied outside the available Sync, record the
actual reply and settled native state before defining an evaluator.

The independent code now in place includes current source gating,
membership refresh, UTC day/month handling, no automatic group join, and
zero-argument monthly transport after correcting its `YYYY-MM` key.
